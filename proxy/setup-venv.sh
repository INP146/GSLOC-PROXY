#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if command -v brew >/dev/null 2>&1 && brew --prefix expat >/dev/null 2>&1; then
  export DYLD_LIBRARY_PATH="$(brew --prefix expat)/lib:${DYLD_LIBRARY_PATH:-}"
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      version="$($candidate - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
      if "$candidate" - <<'PY' >/dev/null 2>&1
import pyexpat
PY
      then
        case "$version" in
          3.11|3.12|3.13*)
            PYTHON_BIN="$candidate"
            break
            ;;
        esac
      fi
    fi
  done
fi

if [ -z "$PYTHON_BIN" ]; then
  cat >&2 <<'MSG'
没有找到可用的 Python 3.11+，或当前 Python 的 pyexpat 模块不可用。

如果你用 Homebrew Python 3.12 遇到 ensurepip/pyexpat 报错，通常是 expat 依赖缺失或链接异常。可尝试：
  brew install expat
  brew reinstall python@3.12

然后重新运行：
  ./setup-venv.sh
MSG
  exit 1
fi

rm -rf .venv
"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

cat <<MSG
✅ 虚拟环境已创建：$(pwd)/.venv

启动：
  ./run-local.sh
MSG
