from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    os.chdir(ROOT)
    env = os.environ.copy()
    _load_env_file(ROOT / ".env", env)
    _configure_macos_expat(env)

    mitmdump = _mitmdump_path(ROOT / ".venv", env.get("MITMDUMP_BIN", ""))
    if mitmdump is None:
        print(
            "没有找到本项目虚拟环境里的 mitmdump。\n\n"
            "请先运行：\n"
            "  python setup-venv.py\n\n"
            "不要直接用系统 Python 全局安装 mitmproxy，容易和已有依赖冲突。",
            file=sys.stderr,
        )
        return 1

    policy_path = _env_or_default(env, "GSLOC_POLICY_PATH", ROOT / "policy.json")
    state_path = _env_or_default(env, "GSLOC_STATE_PATH", ROOT / "state.json")
    confdir = _env_or_default(env, "MITMPROXY_CONF_DIR", ROOT / ".mitmproxy")
    restart_flag = _env_path_or_default(env, "GSLOC_RESTART_FLAG", ROOT / ".restart-requested")

    while True:
        restart_flag.unlink(missing_ok=True)
        args = [
            str(mitmdump),
            "--set",
            f"confdir={confdir}",
            "--mode",
            "regular",
            "--listen-host",
            _env_or_default(env, "GSLOC_PROXY_HOST", "127.0.0.1"),
            "--listen-port",
            _env_or_default(env, "GSLOC_PROXY_PORT", "8082"),
            "--set",
            f"gsloc_policy={policy_path}",
            "--set",
            f"gsloc_state={state_path}",
            "--set",
            f"gsloc_manage_user={_env_or_default(env, 'GSLOC_MANAGE_USER', 'admin')}",
            "--set",
            f"gsloc_manage_password={env.get('GSLOC_MANAGE_PASSWORD', '')}",
            "--set",
            f"gsloc_log_level={_env_or_default(env, 'GSLOC_LOG_LEVEL', 'info')}",
            "--set",
            f"gsloc_terminal_log_level={_env_or_default(env, 'GSLOC_TERMINAL_LOG_LEVEL', _env_or_default(env, 'GSLOC_LOG_LEVEL', 'info'))}",
            "--set",
            f"gsloc_log_file={env.get('GSLOC_LOG_FILE', '')}",
            "--set",
            f"gsloc_file_log_level={_env_or_default(env, 'GSLOC_FILE_LOG_LEVEL', _env_or_default(env, 'GSLOC_LOG_LEVEL', 'info'))}",
            "--set",
            f"gsloc_log_format={_env_or_default(env, 'GSLOC_LOG_FORMAT', 'jsonl')}",
            "--set",
            f"gsloc_log_max_bytes={_env_or_default(env, 'GSLOC_LOG_MAX_BYTES', '10485760')}",
            "--set",
            f"gsloc_log_backup_count={_env_or_default(env, 'GSLOC_LOG_BACKUP_COUNT', '5')}",
            "--set",
            f"gsloc_restart_flag={restart_flag}",
            "-s",
            str(ROOT / "gsloc_proxy" / "addon.py"),
        ]

        status = subprocess.run(args, env=env).returncode
        if restart_flag.exists():
            restart_flag.unlink(missing_ok=True)
            continue
        return status


def _load_env_file(path: Path, env: dict[str, str]) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key or not key.replace("_", "").isalnum() or key[0].isdigit():
            continue
        env[key] = _parse_env_value(value.strip())


def _parse_env_value(value: str) -> str:
    if not value:
        return ""
    if value[0] not in ("'", '"'):
        return _strip_inline_comment(value).strip()
    try:
        parsed = shlex.split(value, comments=True, posix=True)
    except ValueError:
        return value
    if not parsed:
        return ""
    return " ".join(parsed)


def _strip_inline_comment(value: str) -> str:
    for index, char in enumerate(value):
        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index]
    return value


def _configure_macos_expat(env: dict[str, str]) -> None:
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
    existing = env.get("DYLD_LIBRARY_PATH")
    env["DYLD_LIBRARY_PATH"] = f"{expat_lib}:{existing}" if existing else expat_lib


def _mitmdump_path(venv_dir: Path, explicit: str = "") -> str | None:
    if explicit:
        resolved = shutil.which(explicit)
        if resolved:
            return resolved
        explicit_path = Path(explicit)
        if explicit_path.exists():
            return str(explicit_path)
        return explicit

    candidates = (
        [venv_dir / "Scripts" / "mitmdump.exe", venv_dir / "Scripts" / "mitmdump"]
        if os.name == "nt"
        else [venv_dir / "bin" / "mitmdump"]
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _env_or_default(env: dict[str, str], key: str, default: str | Path) -> str:
    value = env.get(key)
    if value:
        return value
    return str(default)


def _env_path_or_default(env: dict[str, str], key: str, default: Path) -> Path:
    value = env.get(key)
    return Path(value) if value else default


if __name__ == "__main__":
    raise SystemExit(main())
