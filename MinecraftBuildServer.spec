# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.building.build_main import Analysis, EXE, PYZ


analysis = Analysis(
    ['server.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter', 'tkinter.messagebox'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['ursina', 'panda3d', 'pygame', 'screeninfo', 'hid'],
    noarchive=False,
)
pyz = PYZ(analysis.pure, analysis.zipped_data)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    name='MinecraftBuildServer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
