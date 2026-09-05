@echo off
setlocal
cd /d "%~dp0"

py -m pip install pyinstaller
py -m PyInstaller --clean --noconfirm --distpath "dist\client" --workpath "build\client" MinecraftBuildWindows.spec

if not exist "dist\client\MinecraftBuild.exe" (
  echo Build failed: Windows client executable was not created.
  exit /b 1
)

echo Built: dist\client\MinecraftBuild.exe