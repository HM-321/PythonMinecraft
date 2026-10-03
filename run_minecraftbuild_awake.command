#!/usr/bin/env bash
set -euo pipefail

# このファイル自身が置かれているプロジェクトディレクトリを基準にする。
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_EXECUTABLE="$PROJECT_DIR/dist/mac/client/MinecraftBuild.app/Contents/MacOS/MinecraftBuild"

if [[ ! -x "$APP_EXECUTABLE" ]]; then
  echo "実行ファイルが見つかりません。先にビルドしてください。"
  echo "  uv run python build.py --mode client"
  echo "検索先: $APP_EXECUTABLE"
  read -r -p "Enterキーで閉じます..." _
  exit 1
fi

# ゲームの実行中だけ、画面消灯とアイドルスリープを防止する。
exec /usr/bin/caffeinate -di "$APP_EXECUTABLE"
