# -*- mode: python ; coding: utf-8 -*-
"""
SPEC for ImageAnnotator (one-file GUI, Windows)
· 收集 shapely/libs/*.dll（geos_c.dll 等）
· 收集 shapely / rasterio / fiona 的 .pyd / .dll
· 打包 pyproj 自带的 proj 数据目录（若存在）
· 排除 PySide6
"""

import os, sys, glob, importlib.util, site
from PyInstaller.utils.hooks import (
    collect_dynamic_libs, collect_submodules, collect_data_files
)

block_cipher = None
site_pkgs = site.getsitepackages()[0]

# ── shapely.libs DLL（若存在） ───────────────────────────
shapely_dlls = []
spec = importlib.util.find_spec("shapely")
if spec and spec.submodule_search_locations:
    libs_dir = os.path.join(spec.submodule_search_locations[0], "libs")
    if os.path.isdir(libs_dir):
        shapely_dlls = [(p, ".") for p in glob.glob(os.path.join(libs_dir, "*.dll"))]

# ── 动态库 ──────────────────────────────────────────────
binaries = (
    collect_dynamic_libs("shapely") +
    collect_dynamic_libs("rasterio") +
    collect_dynamic_libs("fiona") +
    shapely_dlls
)

# ── 静态数据 ────────────────────────────────────────────
datas = collect_data_files("rasterio") + collect_data_files("fiona")

spec_pj = importlib.util.find_spec("pyproj")
if spec_pj and spec_pj.submodule_search_locations:
    pj_dir = os.path.join(spec_pj.submodule_search_locations[0], "proj_dir")
    if os.path.isdir(pj_dir):
        datas.append((pj_dir, "share/proj"))

# ── 隐藏导入 ────────────────────────────────────────────
hiddenimports = ["shapely.speedups", "fiona._shim"] + collect_submodules("rasterio")

# ── Analysis ───────────────────────────────────────────
a = Analysis(
    ["test2.py"],           # ← 你的主脚本
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["PySide6", "PySide6.*"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── 单文件 EXE ──────────────────────────────────────────
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=False,         # 单文件必须带 DLL
    name="ImageAnnotator",
    icon="icon.ico",                # 没有图标可删除此行
    console=False,                  # 纯 GUI
)
