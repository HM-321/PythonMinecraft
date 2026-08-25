#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This build is Apple Silicon only. Run on an arm64 Mac."
  exit 1
fi

python3 -m pip install -r requirements.txt

rm -rf \
  build/MinecraftBuildServer \
  dist/MinecraftBuildServer \
  dist/MinecraftBuildServer.app

python3 -m PyInstaller \
  --clean \
  --noconfirm \
  --windowed \
  --name MinecraftBuildServer \
  --add-data "Template.json:." \
  --hidden-import tkinter \
  --hidden-import tkinter.messagebox \
  --exclude-module ursina \
  --exclude-module panda3d \
  --exclude-module pygame \
  --exclude-module screeninfo \
  --exclude-module hid \
  server.py

if [[ ! -d dist/MinecraftBuildServer.app ]]; then
  echo "Build failed: dist/MinecraftBuildServer.app was not created."
  exit 1
fi

rm -rf dist/MinecraftBuildServer
mkdir -p dist/MinecraftBuildServer

ditto \
  dist/MinecraftBuildServer.app \
  dist/MinecraftBuildServer/MinecraftBuildServer.app

echo "Built: dist/MinecraftBuildServer.app"
echo "Package: dist/MinecraftBuildServer/MinecraftBuildServer.app"