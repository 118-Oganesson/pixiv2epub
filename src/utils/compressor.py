import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Union
import logging
import concurrent.futures

from ..data.models import CompressionResult


def _human_readable_size(n: Optional[int]) -> str:
    """
    バイト数を人間が読みやすい単位に変換して返す（1 kB = 1024 B）。
    例: 123 -> "123 B", 2048 -> "2.00 kB", 3145728 -> "3.00 MB"
    """
    if n is None:
        return "N/A"
    n_float = float(n)
    units = ["B", "kB", "MB", "GB", "TB"]
    i = 0
    while n_float >= 1024 and i < len(units) - 1:
        n_float /= 1024.0
        i += 1
    if units[i] == "B":
        return f"{int(n_float)} {units[i]}"
    return f"{n_float:.2f} {units[i]}"


class ImageCompressor:
    REQUIRED_TOOLS = ["pngquant", "jpegoptim", "cwebp"]

    def __init__(self, config: Dict):
        """
        画像圧縮クラス初期化。
        初期化時に必要なコマンドラインツールの存在を確認します。
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        comp_conf = config.get("compression", {})
        self.skip_if_larger = comp_conf.get("skip_if_larger", True)
        self.force = comp_conf.get("force", False)
        self.max_workers = comp_conf.get("max_workers", 4)

        self.png_options = comp_conf.get("pngquant", {})
        self.jpeg_options = comp_conf.get("jpegoptim", {})
        self.webp_options = comp_conf.get("cwebp", {})

        self.png_options.setdefault("skip_if_larger", self.skip_if_larger)
        self.jpeg_options.setdefault("skip_if_larger", self.skip_if_larger)
        self.webp_options.setdefault("skip_if_larger", self.skip_if_larger)

        # コマンドラインツールの存在チェック
        self.tools_available: Dict[str, bool] = {}
        for tool in self.REQUIRED_TOOLS:
            if shutil.which(tool):
                self.tools_available[tool] = True
            else:
                self.tools_available[tool] = False
                self.logger.warning(
                    f"コマンド '{tool}' が見つかりません。この形式の画像は圧縮されません。"
                )

    def detect_format(self, path: Union[str, Path]) -> Optional[str]:
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
        if output_dir is None:
            output_dir = input_path.parent / self.output_dir_name
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / input_path.name

    def compress_file(
        self,
        input_path: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        options: Optional[Dict] = None,
        *,
        return_bytes: bool = False,
        write_output: bool = True,
    ) -> CompressionResult:
        """単一ファイルを圧縮します。"""
        input_path = Path(input_path)
        start_time = time.time()

        if not input_path.is_file():
            self.logger.error(f"ファイルが見つかりません: {input_path}")
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
            self.logger.warning(f"対応していない画像形式です: {input_path}")
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

            if options is None:
                options = {}

            if fmt == "png":
                merged_options = self.png_options.copy()
                merged_options.update(options)
                tool = "pngquant"
                res = self._compress_pngquant(input_path, tmp_out_path, merged_options)
            elif fmt == "jpeg":
                merged_options = self.jpeg_options.copy()
                merged_options.update(options)
                tool = "jpegoptim"
                res = self._compress_jpegoptim(input_path, tmp_out_path, merged_options)
            else:  # webp
                merged_options = self.webp_options.copy()
                merged_options.update(options)
                tool = "cwebp"
                res = self._compress_cwebp(input_path, tmp_out_path, merged_options)

            duration = time.time() - start_time

            if not res.success:
                self.logger.error(f"{tool} による圧縮に失敗しました: {input_path}")
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
                # ツールがエラーコード0を返してもファイルが生成されない場合がある
                self.logger.error(
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
            skip_if_larger_opt = merged_options.get(
                "skip_if_larger", self.skip_if_larger
            )

            if (
                compressed_size >= original_size
                and skip_if_larger_opt
                and not self.force
            ):
                data = tmp_out_path.read_bytes() if return_bytes else None
                self.logger.info(
                    f"圧縮結果が元より大きいためスキップ: {input_path} ({_human_readable_size(original_size)} -> {_human_readable_size(compressed_size)})"
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
                self.logger.info(
                    f"圧縮完了: {input_path} -> {final_out_path} | "
                    f"元: {_human_readable_size(original_size)}, 圧縮後: {_human_readable_size(compressed_size)}, 削減: {_human_readable_size(saved_bytes)} ({saved_percent:.2f}%)"
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
        options: Optional[Dict] = None,
        *,
        return_bytes: bool = False,
        write_output: bool = True,
    ) -> List[CompressionResult]:
        """
        バッチ圧縮。return_bytes/write_output を各ファイルに適用します。
        """
        paths_to_process: List[Path] = []
        if isinstance(input_paths, (str, Path)) and Path(input_paths).is_dir():
            base_dir = Path(input_paths)
            if recursive:
                paths_to_process = [p for p in base_dir.rglob("*") if p.is_file()]
            else:
                paths_to_process = [p for p in base_dir.iterdir() if p.is_file()]
        elif isinstance(input_paths, list):
            paths_to_process = [Path(p) for p in input_paths]
        else:
            raise ValueError(
                "input_pathsにはディレクトリパスかファイルパスのリストを指定してください。"
            )

        max_workers = max_workers or self.max_workers
        results: List[CompressionResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for p in paths_to_process:
                futures.append(
                    executor.submit(
                        self.compress_file,
                        p,
                        output_dir,
                        options,
                        return_bytes=return_bytes,
                        write_output=write_output,
                    )
                )
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                except Exception as e:
                    self.logger.error(f"画像圧縮中にエラーが発生しました: {e}")
                    continue
                results.append(result)
        return results

    def _run_command(
        self, cmd: List[str], timeout: int = 60
    ) -> Dict[str, Union[bytes, int]]:
        try:
            self.logger.debug(f"コマンド実行: {' '.join(cmd)}")
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                check=False,
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
                "stderr": str(e).encode("utf-8", errors="replace"),
            }

    def _compress_pngquant(
        self, input_path: Path, tmp_out_path: Path, options: Dict
    ) -> CompressionResult:
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

        cmd = ["pngquant"]
        colors = options.get("colors", 256)
        quality = options.get("quality", None)
        speed = options.get("speed", 3)
        strip = options.get("strip", True)
        cmd.append(str(colors))
        if quality:
            cmd.extend(["--quality", quality])
        cmd.extend(["--speed", str(speed)])
        if strip:
            cmd.append("--strip")
        # 出力は tmp_out_path に
        cmd.extend(["--force", "--output", str(tmp_out_path), str(input_path)])
        result = self._run_command(cmd)
        stdout_text = (
            result["stdout"].decode("utf-8", errors="replace")
            if result["stdout"]
            else ""
        )
        stderr_text = (
            result["stderr"].decode("utf-8", errors="replace")
            if result["stderr"]
            else ""
        )
        success = result["returncode"] == 0 and tmp_out_path.is_file()
        if not success:
            self.logger.error(f"pngquantによる圧縮に失敗しました: {stderr_text}")
        return CompressionResult(
            input_path,
            tmp_out_path if success else None,
            None,
            None,
            None,
            None,
            "pngquant",
            " ".join(cmd),
            stdout_text,
            stderr_text,
            success,
        )

    def _compress_jpegoptim(
        self, input_path: Path, tmp_out_path: Path, options: Dict
    ) -> CompressionResult:
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
        # jpegoptimはstdoutでなく一時ファイルへ書き出すようにして、バイナリ取得を簡単にする
        max_quality = options.get("max_quality", 85)
        strip_all = options.get("strip_all", True)
        progressive = options.get("progressive", None)
        preserve_timestamp = options.get("preserve_timestamp", True)
        # jpegoptim は --dest ディレクトリ指定が可能なので tmp_dir を使う
        # tmp_out_path.parent を作る（tmp_out_path は tmp_dir/<name>）
        tmp_out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["jpegoptim"]
        cmd.append(f"-m{max_quality}")
        if strip_all:
            cmd.append("--strip-all")
        if progressive is True:
            cmd.append("--all-progressive")
        elif progressive is False:
            cmd.append("--all-normal")
        if preserve_timestamp:
            cmd.append("--preserve")
        # --stdoutではなく、--dest を使って一時ディレクトリへ出力
        # jpegoptim の --dest は出力先ディレクトリを指定する形式
        tmp_dest_dir = str(tmp_out_path.parent)
        cmd.extend(["--dest", tmp_dest_dir, str(input_path)])
        result = self._run_command(cmd)
        stdout_text = (
            result["stdout"].decode("utf-8", errors="replace")
            if result["stdout"]
            else ""
        )
        stderr_text = (
            result["stderr"].decode("utf-8", errors="replace")
            if result["stderr"]
            else ""
        )
        # jpegoptim は tmp_dest_dir に同名ファイルを書き出すはず
        generated = tmp_out_path.is_file()
        success = result["returncode"] == 0 and generated
        if not success:
            self.logger.error(f"jpegoptimによる圧縮に失敗しました: {stderr_text}")
        return CompressionResult(
            input_path,
            tmp_out_path if success else None,
            None,
            None,
            None,
            None,
            "jpegoptim",
            " ".join(cmd),
            stdout_text,
            stderr_text,
            success,
        )

    def _compress_cwebp(
        self, input_path: Path, tmp_out_path: Path, options: Dict
    ) -> CompressionResult:
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

        cmd = ["cwebp"]
        quality = options.get("quality", 75)
        lossless = options.get("lossless", False)
        near_lossless = options.get("near_lossless", None)
        preset = options.get("preset", None)
        m_level = options.get("m", 4)
        alpha_q = options.get("alpha_q", 100)
        metadata = options.get("metadata", "none")
        if lossless:
            cmd.append("-lossless")
        else:
            cmd.extend(["-q", str(quality)])
        if near_lossless is not None:
            cmd.extend(["-near_lossless", str(near_lossless)])
        if preset in {"photo", "picture", "drawing", "icon", "text"}:
            cmd.extend(["-preset", preset])
        cmd.extend(["-m", str(m_level)])
        cmd.extend(["-alpha_q", str(alpha_q)])
        cmd.extend(["-metadata", metadata])
        cmd.extend([str(input_path), "-o", str(tmp_out_path)])
        result = self._run_command(cmd)
        stdout_text = (
            result["stdout"].decode("utf-8", errors="replace")
            if result["stdout"]
            else ""
        )
        stderr_text = (
            result["stderr"].decode("utf-8", errors="replace")
            if result["stderr"]
            else ""
        )
        success = result["returncode"] == 0 and tmp_out_path.is_file()
        if not success:
            self.logger.error(f"cwebpによる圧縮に失敗しました: {stderr_text}")
        return CompressionResult(
            input_path,
            tmp_out_path if success else None,
            None,
            None,
            None,
            None,
            "cwebp",
            " ".join(cmd),
            stdout_text,
            stderr_text,
            success,
        )
