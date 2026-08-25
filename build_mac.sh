#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This build is Apple Silicon only. Run on an arm64 Mac."
  exit 1
fi

python3 -m pip install -r requirements.txt
rm -rf build/MinecraftBuild dist/MinecraftBuild dist/MinecraftBuild.app dist/MinecraftBuild_Data
python3 -m PyInstaller --clean --noconfirm MinecraftBuild.spec

if [[ ! -d dist/MinecraftBuild.app ]]; then
  echo "Build failed: dist/MinecraftBuild.app was not created."
  exit 1
fi

ditto textures dist/MinecraftBuild.app/Contents/Resources/textures
ditto sounds dist/MinecraftBuild.app/Contents/Resources/sounds
ditto Template.json dist/MinecraftBuild.app/Contents/Resources/Template.json

if [[ ! -f dist/MinecraftBuild.app/Contents/Resources/textures/dirt.png ]]; then
  echo "Build failed: textures were not copied into MinecraftBuild.app."
  exit 1
fi

rm -rf dist/MinecraftBuild
mkdir -p dist/MinecraftBuild
ditto dist/MinecraftBuild.app dist/MinecraftBuild/MinecraftBuild.app

echo "Built: dist/MinecraftBuild.app"
echo "Package: dist/MinecraftBuild/MinecraftBuild.app"