@echo off
setlocal
cd /d "%~dp0"

py -m pip install pyinstaller
py -m PyInstaller --clean --noconfirm MinecraftBuildServer.spec

if not exist "dist\MinecraftBuildServer.exe" (
  echo Build failed: server executable was not created.
  exit /b 1
)

echo Built: dist\MinecraftBuildServer.exe
