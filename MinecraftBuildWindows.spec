# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


datas = [
    ('Template.json', '.'),
    ('textures', 'textures'),
    ('sounds', 'sounds'),
]
datas += collect_data_files('ursina')
datas += collect_data_files('panda3d')
datas += collect_data_files('direct')

hiddenimports = collect_submodules('ursina')
hiddenimports += collect_submodules('direct')
hiddenimports += ['app_runtime']

analysis = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_runtime_hook.py'],
    excludes=['panda3d.rocket', 'sdl2', 'sdl2.ext'],
    noarchive=False,
)
analysis.binaries = [
    entry for entry in analysis.binaries
    if 'panda3d/rocket' not in entry[1]
]
pyz = PYZ(analysis.pure, analysis.zipped_data)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    [],
    name='MinecraftBuild',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
