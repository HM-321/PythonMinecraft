# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs


datas = [
    ('Template.json', '.'),
    ('textures', 'textures'),
    ('sounds', 'sounds'),
    ('fonts', 'fonts')
]
datas += collect_data_files('ursina')
datas += collect_data_files('panda3d')
datas += collect_data_files('direct')

hiddenimports = collect_submodules('ursina')
hiddenimports += collect_submodules('direct')
hiddenimports += ['app_runtime']
# コントローラー機能(controller.py)が sdl2 (pysdl2) に依存しているため、
# 以前のように excludes に入れると exe から sdl2 が丸ごと消えて
# コントローラーが一切認識されなくなる。ここで明示的に含める。
hiddenimports += collect_submodules('sdl2')
hiddenimports += ['sdl2dll']

# pysdl2 は SDL2 本体の共有ライブラリ(.dll)を実行時に動的ロードする。
# PyInstallerは動的ロードされるライブラリを自動検出できないため、
# pysdl2-dll が同梱している .dll を明示的にバイナリとして含める。
binaries = []
try:
    binaries += collect_dynamic_libs('sdl2dll')
except Exception:
    pass

analysis = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_runtime_hook.py'],
    excludes=['panda3d.rocket'],
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
