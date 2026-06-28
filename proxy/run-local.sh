#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if command -v brew >/dev/null 2>&1 && brew --prefix expat >/dev/null 2>&1; then
  export DYLD_LIBRARY_PATH="$(brew --prefix expat)/lib:${DYLD_LIBRARY_PATH:-}"
fi

if [ ! -x .venv/bin/mitmdump ]; then
  cat >&2 <<'MSG'
没有找到本项目虚拟环境里的 mitmdump。

请先运行：
  ./setup-venv.sh

不要直接用系统 python3 全局安装 mitmproxy，macOS 自带 Python 3.9 会装到用户 site-packages，容易和已有依赖冲突。
MSG
  exit 1
fi

POLICY_PATH="${GSLOC_POLICY_PATH:-$PWD/policy.json}"
STATE_PATH="${GSLOC_STATE_PATH:-$PWD/state.json}"
MITMPROXY_CONF_DIR="${MITMPROXY_CONF_DIR:-$PWD/.mitmproxy}"
RESTART_FLAG="${GSLOC_RESTART_FLAG:-$PWD/.restart-requested}"

while true; do
  rm -f "$RESTART_FLAG"
  .venv/bin/mitmdump \
    --set "confdir=$MITMPROXY_CONF_DIR" \
    --set "flow_detail=0" \
    --set "termlog_verbosity=error" \
    --mode regular \
    --listen-host 127.0.0.1 \
    --listen-port "${GSLOC_PROXY_PORT:-8082}" \
    --set "gsloc_policy=$POLICY_PATH" \
    --set "gsloc_state=$STATE_PATH" \
    --set "gsloc_manage_user=${GSLOC_MANAGE_USER:-admin}" \
    --set "gsloc_manage_password=${GSLOC_MANAGE_PASSWORD:-}" \
    --set "gsloc_log_level=${GSLOC_LOG_LEVEL:-info}" \
    --set "gsloc_terminal_log_level=${GSLOC_TERMINAL_LOG_LEVEL:-${GSLOC_LOG_LEVEL:-info}}" \
    --set "gsloc_log_file=${GSLOC_LOG_FILE:-}" \
    --set "gsloc_file_log_level=${GSLOC_FILE_LOG_LEVEL:-${GSLOC_LOG_LEVEL:-info}}" \
    --set "gsloc_log_format=${GSLOC_LOG_FORMAT:-jsonl}" \
    --set "gsloc_log_max_bytes=${GSLOC_LOG_MAX_BYTES:-10485760}" \
    --set "gsloc_log_backup_count=${GSLOC_LOG_BACKUP_COUNT:-5}" \
    --set "gsloc_restart_flag=$RESTART_FLAG" \
    -s "$PWD/gsloc_proxy/addon.py"
  status=$?
  if [ -f "$RESTART_FLAG" ]; then
    rm -f "$RESTART_FLAG"
    continue
  fi
  exit "$status"
done
