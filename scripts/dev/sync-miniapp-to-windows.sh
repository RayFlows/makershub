#!/usr/bin/env bash
set -euo pipefail

# 将 WSL 中的小程序源码同步到 Windows 本地目录。
# 微信开发者工具运行在 Windows 上，直接打开 \\wsl.localhost 路径时文件监听可能延迟或失效。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SOURCE_DIR="${SOURCE_DIR:-$REPO_ROOT/apps/miniapp}"
TARGET_DIR="${1:-${MINIAPP_WINDOWS_DIR:-/mnt/c/Users/Ray/Documents/New project/makershub-miniapp}}"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "source directory not found: $SOURCE_DIR" >&2
  exit 1
fi

case "$TARGET_DIR" in
  ""|"/"|"/mnt"|"/mnt/c"|"/mnt/c/Users"|"/mnt/c/Users/Ray")
    echo "refuse to sync to unsafe target directory: $TARGET_DIR" >&2
    exit 1
    ;;
esac

if [[ "$(realpath -m "$SOURCE_DIR")" == "$(realpath -m "$TARGET_DIR")" ]]; then
  echo "source and target must be different directories" >&2
  exit 1
fi

mkdir -p "$TARGET_DIR"

rsync -a --delete \
  --exclude ".git/" \
  --exclude "project.private.config.json" \
  --exclude "node_modules/" \
  "$SOURCE_DIR/" "$TARGET_DIR/"

echo "miniapp synced"
echo "source: $SOURCE_DIR"
echo "target: $TARGET_DIR"
if command -v wslpath >/dev/null 2>&1; then
  echo "open in WeChat DevTools: $(wslpath -w "$TARGET_DIR")"
fi
