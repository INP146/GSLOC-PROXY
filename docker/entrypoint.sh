#!/bin/sh
set -eu

copy_default() {
  source_path="$1"
  target_path="$2"

  if [ -n "$target_path" ] && [ ! -e "$target_path" ]; then
    mkdir -p "$(dirname "$target_path")"
    cp "$source_path" "$target_path"
  fi
}

copy_default /defaults/policy.example.json "${GSLOC_POLICY_PATH:-/config/policy.json}"
copy_default /defaults/state.example.json "${GSLOC_STATE_PATH:-/data/state.json}"

exec "$@"
