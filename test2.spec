# -*- mode: python ; coding: utf-8 -*-
"""
ImageAnnotator one-file SPEC
· 自动查找 shapely/libs/*.dll（若存在）并打包
· 其余设置同前：rasterio/fiona DLL、PROJ/GDAL share、排除 PySide6
"""

import os, sys, site, glob, importlib.util
from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_submodules,
    collect_data_files,
)

block_cipher = None

env_dir   = sys.base_prefix
site_pkgs = site.getsitepackages()[0]

# ── 1. shapely.libs: 动态查找 ─────────────────────────────
shapely_dlls = []
spec = importlib.util.find_spec("shapely")
if spec and spec.submodule_search_locations:
    for base in spec.submodule_search_locations:
        lib_dir = os.path.join(base, "libs")
        if os.path.isdir(lib_dir):
            for dll in glob.glob(os.path.join(lib_dir, "*.dll")):
                shapely_dlls.append((dll, "."))           # 复制到打包根目录
            break                                         # 找到一次即可

# ── 2. 其他动态库 ─────────────────────────────────────────
binaries = (
    collect_dynamic_libs("shapely")      +
    collect_dynamic_libs("rasterio")     +
    collect_dynamic_libs("fiona")        +
    shapely_dlls                         # ← GEOS DLL(若存在)加入列表
)

# ── 3. 静态数据 ───────────────────────────────────────────
datas = (
    [
        (os.path.join(env_dir, "Library", "share", "proj"), "share/proj"),
        (os.path.join(env_dir, "Library", "share", "gdal"), "share/gdal"),
    ]
    + collect_data_files("rasterio")
    + collect_data_files("fiona")
)

# ── 4. 隐藏导入 ───────────────────────────────────────────
hiddenimports = (
    ["shapely.speedups", "fiona._shim"] +
    collect_submodules("rasterio")
)

# ── 5. Analysis ──────────────────────────────────────────
a = Analysis(
    ["test2.py"],               # ← 你的主脚本
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6", "PySide6.*"],   # 排除另一套 Qt
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── 6. one-file EXE ──────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=False,     # 必须包含 DLL
    name="ImageAnnotator",
    icon="lo.png",            # 无图标可删
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,              # 纯 GUI
)
