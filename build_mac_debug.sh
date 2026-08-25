#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This debug build is Apple Silicon only. Run on an arm64 Mac."
  exit 1
fi

python3 -m pip install -r requirements.txt
rm -rf build/MinecraftBuildDebug dist/MinecraftBuildDebug
python3 -m PyInstaller --clean --noconfirm MinecraftBuildDebug.spec

ditto textures dist/MinecraftBuildDebug/textures
ditto sounds dist/MinecraftBuildDebug/sounds
ditto Template.json dist/MinecraftBuildDebug/Template.json

if [[ ! -f dist/MinecraftBuildDebug/textures/dirt.png ]]; then
  echo "Debug build failed: textures were not copied."
  exit 1
fi

echo "Built: dist/MinecraftBuildDebug/MinecraftBuildDebug"
echo "Run from Terminal: ./dist/MinecraftBuildDebug/MinecraftBuildDebug"