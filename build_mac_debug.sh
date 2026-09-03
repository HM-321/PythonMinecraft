#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This debug build is Apple Silicon only. Run on an arm64 Mac."
  exit 1
fi

python3 -m pip install -r requirements.txt
rm -rf build/MinecraftBuildDebug dist/MinecraftBuildDebug dist/mac/debug
python3 -m PyInstaller --clean --noconfirm MinecraftBuildDebug.spec

mkdir -p dist/mac/debug
ditto dist/MinecraftBuildDebug dist/mac/debug/MinecraftBuildDebug
ditto textures dist/mac/debug/MinecraftBuildDebug/textures
ditto sounds dist/mac/debug/MinecraftBuildDebug/sounds
ditto Template.json dist/mac/debug/MinecraftBuildDebug/Template.json

if [[ ! -f dist/mac/debug/MinecraftBuildDebug/textures/dirt.png ]]; then
  echo "Debug build failed: textures were not copied."
  exit 1
fi

echo "Built: dist/mac/debug/MinecraftBuildDebug/MinecraftBuildDebug"
echo "Run from Terminal: ./dist/mac/debug/MinecraftBuildDebug/MinecraftBuildDebug"