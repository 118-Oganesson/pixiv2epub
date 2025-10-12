# FILE: src/pixiv2epub/utils/image_optimizer.py
import concurrent.futures
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from loguru import logger

from ..models.local import CompressionResult
from ..shared.settings import Settings


def _human_readable_size(size_bytes: Optional[int]) -> str:
    """バイト数を人間が読みやすい形式の文字列 (kB, MBなど) に変換します。"""
    if size_bytes is None:
        return "N/A"
    n_float = float(size_bytes)
    units = ["B", "kB", "MB", "GB", "TB"]
    i = 0
    while n_float >= 1024 and i < len(units) - 1:
        n_float /= 1024.0
        i += 1
    if units[i] == "B":
        return f"{int(n_float)} {units[i]}"
    return f"{n_float:.2f} {units[i]}"


class ImageCompressor:
    """pngquant, jpegoptim, cwebp を利用して画像を圧縮するクラス。"""

    REQUIRED_TOOLS = ["pngquant", "jpegoptim", "cwebp"]

    def __init__(self, settings: Settings):
        """
        Args:
            settings (Settings): アプリケーション全体の設定オブジェクト。
        """
        self.settings = settings.compression

        self.tools_available: Dict[str, bool] = {}
        for tool in self.REQUIRED_TOOLS:
            if shutil.which(tool):
                self.tools_available[tool] = True
            else:
                self.tools_available[tool] = False
                logger.warning(
                    f"コマンド '{tool}' が見つかりません。この形式の画像は圧縮されません。"
                )

    def detect_format(self, path: Union[str, Path]) -> Optional[str]:
        """ファイルパスの拡張子から画像フォーマットを判定します。"""
        path = Path(path)
        ext = path.suffix.lower()
        if ext == ".png":
            return "png"
        elif ext in [".jpg", ".jpeg"]:
            return "jpeg"
        elif ext == ".webp":
            return "webp"
        else:
            return None

    def _make_output_path(self, input_path: Path, output_dir: Optional[Path]) -> Path:
        """出力ファイルのパスを生成し、必要に応じて出力ディレクトリを作成します。"""
        if output_dir is None:
            output_dir = input_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / input_path.name

    def compress_file(
        self,
        input_path: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        *,
        return_bytes: bool = False,
        write_output: bool = True,
    ) -> CompressionResult:
        """単一の画像ファイルを圧縮します。"""
        input_path = Path(input_path)
        start_time = time.time()

        if not input_path.is_file():
            logger.error(f"ファイルが見つかりません: {input_path}")
            return CompressionResult(
                input_path,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                f"ファイルが見つかりません: {input_path}",
                False,
            )

        fmt = self.detect_format(input_path)
        if fmt is None:
            logger.warning(f"対応していない画像形式です: {input_path}")
            return CompressionResult(
                input_path,
                None,
                input_path.stat().st_size,
                None,
                None,
                None,
                None,
                None,
                None,
                "対応していない画像形式です",
                False,
            )

        out_path = (
            self._make_output_path(input_path, Path(output_dir) if output_dir else None)
            if write_output
            else None
        )

        with tempfile.TemporaryDirectory(prefix="imgcompress_") as tmp_dir:
            tmp_out_path = Path(tmp_dir) / input_path.name
            original_size = input_path.stat().st_size

            if fmt == "png":
                tool = "pngquant"
                res = self._compress_pngquant(input_path, tmp_out_path)
            elif fmt == "jpeg":
                tool = "jpegoptim"
                res = self._compress_jpegoptim(input_path, tmp_out_path)
            else:  # webp
                tool = "cwebp"
                res = self._compress_cwebp(input_path, tmp_out_path)

            duration = time.time() - start_time

            if not res.success:
                logger.error(f"{tool} による圧縮に失敗しました: {input_path}")
                return CompressionResult(
                    input_path,
                    None,
                    original_size,
                    None,
                    None,
                    None,
                    tool,
                    res.command,
                    res.stdout,
                    res.stderr,
                    False,
                    duration=duration,
                )

            if not tmp_out_path.is_file() or tmp_out_path.stat().st_size == 0:
                logger.error(
                    f"予期せぬエラー: 一時出力ファイルが見つかりません: {tmp_out_path}"
                )
                return CompressionResult(
                    input_path,
                    None,
                    original_size,
                    None,
                    None,
                    None,
                    tool,
                    res.command,
                    res.stdout,
                    "一時出力ファイルが見つかりません",
                    False,
                    duration=duration,
                )

            compressed_size = tmp_out_path.stat().st_size
            if compressed_size >= original_size and self.settings.skip_if_larger:
                data = tmp_out_path.read_bytes() if return_bytes else None
                logger.info(
                    f"圧縮結果が元より大きいためスキップ: {input_path.name} "
                    f"({_human_readable_size(original_size)} -> {_human_readable_size(compressed_size)})"
                )
                return CompressionResult(
                    input_path,
                    None,
                    original_size,
                    compressed_size,
                    0,
                    0.0,
                    tool,
                    res.command,
                    res.stdout,
                    "圧縮後のファイルサイズが元より大きいためスキップ",
                    True,
                    skipped=True,
                    duration=duration,
                    output_bytes=data,
                )

            output_bytes: Optional[bytes] = None
            if return_bytes:
                output_bytes = tmp_out_path.read_bytes()

            if write_output and out_path is not None:
                shutil.move(str(tmp_out_path), out_path)
                final_out_path = out_path
            else:
                final_out_path = None

            saved_bytes = original_size - compressed_size
            saved_percent = (
                (saved_bytes / original_size * 100) if original_size > 0 else 0.0
            )

            if write_output:
                logger.info(
                    f"圧縮完了: {input_path.name} -> {final_out_path.name if final_out_path else 'N/A'} | "
                    f"元: {_human_readable_size(original_size)}, 圧縮後: {_human_readable_size(compressed_size)}, "
                    f"削減: {_human_readable_size(saved_bytes)} ({saved_percent:.2f}%)"
                )

            return CompressionResult(
                input_path,
                final_out_path,
                original_size,
                compressed_size,
                saved_bytes,
                saved_percent,
                tool,
                res.command,
                res.stdout,
                res.stderr,
                True,
                duration=duration,
                output_bytes=output_bytes,
            )

    def compress_batch(
        self,
        input_paths: Union[List[Union[str, Path]], str],
        recursive: bool = False,
        output_dir: Optional[Union[str, Path]] = None,
        max_workers: Optional[int] = None,
        *,
        return_bytes: bool = False,
        write_output: bool = True,
    ) -> List[CompressionResult]:
        """複数の画像ファイルやディレクトリを並列で圧縮します。"""
        paths_to_process: List[Path] = []
        if isinstance(input_paths, (str, Path)) and Path(input_paths).is_dir():
            base_dir = Path(input_paths)
            pattern = "**/*" if recursive else "*"
            paths_to_process = [p for p in base_dir.glob(pattern) if p.is_file()]
        elif isinstance(input_paths, list):
            paths_to_process = [Path(p) for p in input_paths]
        else:
            raise ValueError(
                "input_pathsにはディレクトリパスかファイルパスのリストを指定してください。"
            )

        workers = max_workers or self.settings.max_workers
        results: List[CompressionResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(
                    self.compress_file,
                    p,
                    output_dir,
                    return_bytes=return_bytes,
                    write_output=write_output,
                )
                for p in paths_to_process
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"画像圧縮中にエラーが発生しました: {e}")
        return results

    def _run_command(
        self, cmd: List[str], timeout: int = 60
    ) -> Dict[str, Union[bytes, int]]:
        """外部コマンドを実行し、結果をキャプチャします。"""
        try:
            logger.debug(f"コマンド実行: {' '.join(cmd)}")
            proc = subprocess.run(
                cmd, capture_output=True, timeout=timeout, check=False
            )
            return {
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": b"",
                "stderr": str(e).encode("utf-8", "replace"),
            }

    def _prepare_result(
        self,
        input_path: Path,
        tmp_out_path: Path,
        tool_name: str,
        cmd: List[str],
        result: Dict,
    ) -> CompressionResult:
        """コマンド実行結果をCompressionResultに変換するヘルパー。"""
        success = result["returncode"] == 0 and tmp_out_path.is_file()
        stdout = result["stdout"].decode("utf-8", "replace") if result["stdout"] else ""
        stderr = result["stderr"].decode("utf-8", "replace") if result["stderr"] else ""

        if not success:
            logger.error(f"{tool_name}による圧縮に失敗しました: {stderr}")

        return CompressionResult(
            input_path,
            tmp_out_path if success else None,
            None,
            None,
            None,
            None,
            tool_name,
            " ".join(cmd),
            stdout,
            stderr,
            success,
        )

    def _compress_pngquant(
        self, input_path: Path, tmp_out_path: Path
    ) -> CompressionResult:
        """pngquant を使用してPNG画像を圧縮します。"""
        if not self.tools_available.get("pngquant"):
            return CompressionResult(
                input_path,
                None,
                None,
                None,
                None,
                None,
                "pngquant",
                None,
                None,
                "pngquantコマンドが見つからないためスキップ",
                False,
                skipped=True,
            )

        opts = self.settings.pngquant
        cmd = ["pngquant", str(opts.colors)]
        if opts.quality:
            cmd.extend(["--quality", opts.quality])
        cmd.extend(["--speed", str(opts.speed)])
        if opts.strip:
            cmd.append("--strip")
        cmd.extend(["--force", "--output", str(tmp_out_path), str(input_path)])

        result = self._run_command(cmd)
        return self._prepare_result(input_path, tmp_out_path, "pngquant", cmd, result)

    def _compress_jpegoptim(
        self, input_path: Path, tmp_out_path: Path
    ) -> CompressionResult:
        """jpegoptim を使用してJPEG画像を圧縮します。"""
        if not self.tools_available.get("jpegoptim"):
            return CompressionResult(
                input_path,
                None,
                None,
                None,
                None,
                None,
                "jpegoptim",
                None,
                None,
                "jpegoptimコマンドが見つからないためスキップ",
                False,
                skipped=True,
            )

        opts = self.settings.jpegoptim
        tmp_out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["jpegoptim", f"-m{opts.max_quality}"]
        if opts.strip_all:
            cmd.append("--strip-all")
        if opts.progressive is True:
            cmd.append("--all-progressive")
        elif opts.progressive is False:
            cmd.append("--all-normal")
        if opts.preserve_timestamp:
            cmd.append("--preserve")
        cmd.extend(["--dest", str(tmp_out_path.parent), str(input_path)])

        result = self._run_command(cmd)
        return self._prepare_result(input_path, tmp_out_path, "jpegoptim", cmd, result)

    def _compress_cwebp(
        self, input_path: Path, tmp_out_path: Path
    ) -> CompressionResult:
        """cwebp を使用して画像をWebP形式に変換・圧縮します。"""
        if not self.tools_available.get("cwebp"):
            return CompressionResult(
                input_path,
                None,
                None,
                None,
                None,
                None,
                "cwebp",
                None,
                None,
                "cwebpコマンドが見つからないためスキップ",
                False,
                skipped=True,
            )

        opts = self.settings.cwebp
        cmd = ["cwebp"]
        if opts.lossless:
            cmd.append("-lossless")
        else:
            cmd.extend(["-q", str(opts.quality)])
        cmd.extend(["-metadata", opts.metadata])
        cmd.extend([str(input_path), "-o", str(tmp_out_path)])

        result = self._run_command(cmd)
        return self._prepare_result(input_path, tmp_out_path, "cwebp", cmd, result)
