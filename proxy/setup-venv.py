from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MIN_VERSION = (3, 11)


def main() -> int:
    os.chdir(ROOT)
    if sys.version_info < MIN_VERSION:
        print(
            "当前 Python 版本过低，请使用 Python 3.11 或更新版本运行：\n"
            "  python setup-venv.py",
            file=sys.stderr,
        )
        return 1

    _configure_macos_expat()

    if not _has_pyexpat():
        print(
            "当前 Python 的 pyexpat 模块不可用。\n\n"
            "如果你用 Homebrew Python 遇到 ensurepip/pyexpat 报错，通常是 expat 依赖缺失或链接异常。可尝试：\n"
            "  brew install expat\n"
            "  brew reinstall python@3.12\n\n"
            "然后重新运行：\n"
            "  python setup-venv.py",
            file=sys.stderr,
        )
        return 1

    venv_dir = ROOT / ".venv"
    if venv_dir.exists():
        shutil.rmtree(venv_dir)

    _run([sys.executable, "-m", "venv", str(venv_dir)])
    venv_python = _venv_python(venv_dir)
    _run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    _run([str(venv_python), "-m", "pip", "install", "-e", "."])

    print(f"虚拟环境已创建：{venv_dir}")
    print("\n启动：")
    print("  python run-local.py")
    return 0


def _has_pyexpat() -> bool:
    result = subprocess.run(
        [sys.executable, "-c", "import pyexpat"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _configure_macos_expat() -> None:
    if sys.platform != "darwin" or shutil.which("brew") is None:
        return
    try:
        result = subprocess.run(
            ["brew", "--prefix", "expat"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return
    expat_lib = str(Path(result.stdout.strip()) / "lib")
    existing = os.environ.get("DYLD_LIBRARY_PATH")
    os.environ["DYLD_LIBRARY_PATH"] = f"{expat_lib}:{existing}" if existing else expat_lib


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run(args: list[str]) -> None:
    subprocess.run(args, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
