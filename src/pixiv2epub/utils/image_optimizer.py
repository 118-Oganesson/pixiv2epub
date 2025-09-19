#
# -----------------------------------------------------------------------------
# src/pixiv2epub/utils/image_optimizer.py
#
# 外部のコマンドラインツールを利用して画像を圧縮する機能を提供します。
# pngquant, jpegoptim, cwebp といった実績のあるツールを抽象化し、
# Pythonから統一的なインターフェースで利用できるようにします。
# -----------------------------------------------------------------------------
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Union
import logging
import concurrent.futures

from ..data_models import CompressionResult


def _human_readable_size(size_bytes: Optional[int]) -> str:
    """バイト数を人間が読みやすい形式の文字列 (kB, MBなど) に変換します。

    Args:
        size_bytes (Optional[int]): バイト単位のファイルサイズ。Noneの場合は 'N/A' を返します。

    Returns:
        str: 人間が読みやすい形式にフォーマットされたファイルサイズの文字列。
    """
    if size_bytes is None:
        return "N/A"
    n_float = float(size_bytes)
    units = ["B", "kB", "MB", "GB", "TB"]
    i = 0
    # 1024未満になるまで単位を大きくしていく
    while n_float >= 1024 and i < len(units) - 1:
        n_float /= 1024.0
        i += 1
    if units[i] == "B":
        return f"{int(n_float)} {units[i]}"
    return f"{n_float:.2f} {units[i]}"


class ImageCompressor:
    """pngquant, jpegoptim, cwebp を利用して画像を圧縮するクラス。

    システムにインストールされている対応ツールを自動的に検出し、
    ファイル形式に応じて最適なツールを使用して圧縮処理を実行します。
    並列処理によるバッチ圧縮もサポートします。
    """

    REQUIRED_TOOLS = ["pngquant", "jpegoptim", "cwebp"]

    def __init__(self, config: Dict):
        """ImageCompressorを初期化します。

        設定辞書から圧縮オプションを読み込み、必須コマンドラインツールが
        システムに存在するかどうかを確認します。

        Args:
            config (Dict): アプリケーション全体の設定辞書。
                'compression' キーに本クラス用の設定が含まれていることを想定しています。
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
        """ファイルパスの拡張子から画像フォーマットを判定します。

        Args:
            path (Union[str, Path]): 判定対象のファイルパス。

        Returns:
            Optional[str]: 'png', 'jpeg', 'webp' のいずれか。
                対応していないフォーマットの場合は None を返します。
        """
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
        """出力ファイルのパスを生成し、必要に応じて出力ディレクトリを作成します。

        Args:
            input_path (Path): 入力ファイルのパス。
            output_dir (Optional[Path]): 出力先のディレクトリ。
                Noneの場合は入力ファイルと同じディレクトリを使用します。

        Returns:
            Path: 生成された出力ファイルのパス。
        """
        if output_dir is None:
            output_dir = input_path.parent
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
        """単一の画像ファイルを圧縮します。

        ファイル形式を自動検出し、対応するコマンドラインツールを呼び出します。
        圧縮処理は一時ディレクトリ内で行われ、安全に処理されます。

        Args:
            input_path (Union[str, Path]): 圧縮する画像のパス。
            output_dir (Optional[Union[str, Path]], optional): 圧縮後のファイルの
                保存先ディレクトリ。None の場合は入力ファイルと同じ場所に保存されます。
                Defaults to None.
            options (Optional[Dict], optional): 圧縮ツールに渡す追加オプション。
                Defaults to None.
            return_bytes (bool, optional): Trueの場合、圧縮後のファイル内容を
                bytesとして `CompressionResult` に含めます。 Defaults to False.
            write_output (bool, optional): Trueの場合、圧縮後のファイルをディスクに
                書き込みます。Falseの場合、`return_bytes`がTrueでなければ圧縮結果は
                破棄されます。 Defaults to True.

        Returns:
            CompressionResult: 圧縮処理の結果を格納したデータクラス。
        """
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

            # 稀にコマンドが成功(exit code 0)しても出力ファイルが生成されないケースに対応する。
            if not tmp_out_path.is_file() or tmp_out_path.stat().st_size == 0:
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
        """複数の画像ファイルやディレクトリを並列で圧縮します。

        Args:
            input_paths (Union[List[Union[str, Path]], str]): 圧縮対象の
                ファイルパスのリスト、またはディレクトリのパス。
            recursive (bool, optional): `input_paths` がディレクトリの場合に
                再帰的に探索するかどうか。 Defaults to False.
            output_dir (Optional[Union[str, Path]], optional): 圧縮後のファイルの
                保存先ディレクトリ。 Defaults to None.
            max_workers (Optional[int], optional): 並列実行する最大スレッド数。
                Noneの場合はクラスのデフォルト値を使用します。 Defaults to None.
            options (Optional[Dict], optional): 各圧縮ツールに渡す追加オプション。
                Defaults to None.
            return_bytes (bool, optional): 圧縮結果をbytesで返すかどうか。
                Defaults to False.
            write_output (bool, optional): 圧縮結果をファイルに書き込むかどうか。
                Defaults to True.

        Returns:
            List[CompressionResult]: 各ファイルの圧縮結果のリスト。

        Raises:
            ValueError: `input_paths` が不正な場合に送出されます。
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
            futures = [
                executor.submit(
                    self.compress_file,
                    p,
                    output_dir,
                    options,
                    return_bytes=return_bytes,
                    write_output=write_output,
                )
                for p in paths_to_process
            ]
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
        """外部コマンドを実行し、結果をキャプチャします。

        Args:
            cmd (List[str]): 実行するコマンドと引数のリスト。
            timeout (int, optional): コマンドのタイムアウト時間（秒）。Defaults to 60.

        Returns:
            Dict[str, Union[bytes, int]]: コマンドの実行結果。
                'returncode', 'stdout', 'stderr' のキーを持つ辞書。
        """
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
        """pngquant を使用してPNG画像を圧縮します。

        Args:
            input_path (Path): 入力PNGファイルのパス。
            tmp_out_path (Path): 圧縮後の一時出力先パス。
            options (Dict): pngquantに渡すオプション。

        Returns:
            CompressionResult: 圧縮処理の結果。
        """
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
        """jpegoptim を使用してJPEG画像を圧縮します。

        Args:
            input_path (Path): 入力JPEGファイルのパス。
            tmp_out_path (Path): 圧縮後の一時出力先パス。
            options (Dict): jpegoptimに渡すオプション。

        Returns:
            CompressionResult: 圧縮処理の結果。
        """
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

        tmp_out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["jpegoptim"]
        max_quality = options.get("max_quality", 85)
        strip_all = options.get("strip_all", True)
        progressive = options.get("progressive", None)
        preserve_timestamp = options.get("preserve_timestamp", True)

        cmd.append(f"-m{max_quality}")
        if strip_all:
            cmd.append("--strip-all")
        if progressive is True:
            cmd.append("--all-progressive")
        elif progressive is False:
            cmd.append("--all-normal")
        if preserve_timestamp:
            cmd.append("--preserve")

        # jpegoptimは標準出力への出力をサポートしていないため、
        # --dest オプションで一時ディレクトリに出力する。
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
        success = result["returncode"] == 0 and tmp_out_path.is_file()

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
        """cwebp を使用して画像をWebP形式に変換・圧縮します。

        Args:
            input_path (Path): 入力画像のパス。
            tmp_out_path (Path): 圧縮後のWebPファイルの一時出力先パス。
            options (Dict): cwebpに渡すオプション。

        Returns:
            CompressionResult: 圧縮処理の結果。
        """
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
