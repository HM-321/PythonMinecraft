# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ('Template.json', '.'),
    ('textures', 'textures'),
    ('sounds', 'sounds'),
    ('fonts', 'fonts'),
]
datas += collect_data_files('ursina')
datas += collect_data_files('panda3d')
datas += collect_data_files('direct')

hiddenimports = collect_submodules('ursina')
hiddenimports += collect_submodules('direct')
hiddenimports += ['app_runtime']

excluded_modules = [
    'panda3d.rocket',
    'sdl2',
    'sdl2.ext',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_runtime_hook.py'],
    excludes=excluded_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    target_arch='arm64',
)
a.binaries = [entry for entry in a.binaries if 'panda3d/rocket' not in entry[1]]
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MinecraftBuild',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='MinecraftBuild.app',
    icon=None,
    bundle_identifier='local.minecraftbuild.game',
    info_plist={
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '11.0',
    },
)