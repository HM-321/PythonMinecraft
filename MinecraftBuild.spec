# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all


ursina_datas, ursina_binaries, ursina_hiddenimports = collect_all("ursina")
panda3d_datas, panda3d_binaries, panda3d_hiddenimports = collect_all("panda3d")
direct_datas, direct_binaries, direct_hiddenimports = collect_all("direct")


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=(
        ursina_binaries
        + panda3d_binaries
        + direct_binaries
    ),
    datas=[
        ("Template.json", "."),
        ("textures", "textures"),
        ("sounds", "sounds"),
        ("fonts", "fonts"),
    ]
    + ursina_datas
    + panda3d_datas
    + direct_datas,
    hiddenimports=(
        ursina_hiddenimports
        + panda3d_hiddenimports
        + direct_hiddenimports
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        "pyi_runtime_hook.py",
    ],
    excludes=[
        "panda3d.rocket",
        "sdl2",
        "sdl2.ext",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MinecraftBuild",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MinecraftBuild",
)

app = BUNDLE(
    coll,
    name="MinecraftBuild.app",
    icon=None,
    bundle_identifier=None,
)