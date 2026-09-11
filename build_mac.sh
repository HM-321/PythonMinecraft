#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This build is Apple Silicon only. Run on an arm64 Mac."
  exit 1
fi

python3 -m pip install -r requirements.txt

rm -rf \
  build/MinecraftBuild \
  dist/MinecraftBuild \
  dist/MinecraftBuild.app \
  dist/MinecraftBuild_Data \
  dist/mac/client

python3 -m PyInstaller --clean --noconfirm MinecraftBuild.spec

if [[ ! -d dist/MinecraftBuild.app ]]; then
  echo "Build failed: dist/MinecraftBuild.app was not created."
  exit 1
fi

# リソースを配置
ditto textures dist/MinecraftBuild.app/Contents/Resources/textures
ditto sounds dist/MinecraftBuild.app/Contents/Resources/sounds
ditto fonts dist/MinecraftBuild.app/Contents/Resources/fonts
ditto Template.json dist/MinecraftBuild.app/Contents/Resources/Template.json

# 必須リソースを検査
if [[ ! -f dist/MinecraftBuild.app/Contents/Resources/textures/dirt.png ]]; then
  echo "Build failed: textures were not copied."
  exit 1
fi

if [[ ! -f dist/MinecraftBuild.app/Contents/Resources/fonts/JF-Dot-AyuMin18.ttf ]]; then
  echo "Build failed: font was not copied."
  exit 1
fi

# リソース配置後、配布用コピー前に署名
codesign --force --deep --sign - dist/MinecraftBuild.app

# 署名を検証
codesign --verify --deep --strict --verbose=2 dist/MinecraftBuild.app

mkdir -p dist/mac/client
ditto dist/MinecraftBuild.app dist/mac/client/MinecraftBuild.app

echo "Built: dist/mac/client/MinecraftBuild.app"