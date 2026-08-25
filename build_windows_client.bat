@echo off
setlocal
cd /d "%~dp0"

py -m pip install pyinstaller
py -m PyInstaller --clean --noconfirm MinecraftBuildWindows.spec

if not exist "dist\MinecraftBuild\MinecraftBuild.exe" (
  echo Build failed: Windows client executable was not created.
  exit /b 1
)

echo Built: dist\MinecraftBuild\MinecraftBuild.exe
