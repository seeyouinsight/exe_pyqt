import os, sys, site, glob, importlib.util
from PyInstaller.utils.hooks import (
    collect_dynamic_libs, collect_submodules, collect_data_files
)

block_cipher = None
site_pkgs = site.getsitepackages()[0]

# --- shapely.libs DLL --------------------------------------------------------
shapely_dlls = []
spec = importlib.util.find_spec("shapely")
if spec and spec.submodule_search_locations:
    libs_dir = os.path.join(spec.submodule_search_locations[0], "libs")
    if os.path.isdir(libs_dir):
        shapely_dlls = [(os.path.join(libs_dir, f), ".")
                        for f in glob.glob(os.path.join(libs_dir, "*.dll"))]

# --- binaries ----------------------------------------------------------------
binaries = (
    collect_dynamic_libs("shapely") +
    collect_dynamic_libs("rasterio") +
    collect_dynamic_libs("fiona") +
    shapely_dlls
)

# --- data dirs (only if exist) ----------------------------------------------
datas = collect_data_files("rasterio") + collect_data_files("fiona")

proj_dir = os.path.join(site_pkgs, "pyproj", "proj_dir")          # pyproj wheels带的数据
if os.path.isdir(proj_dir):
    datas.append((proj_dir, "share/proj"))

# --- hidden imports ----------------------------------------------------------
hiddenimports = ["shapely.speedups", "fiona._shim"] + collect_submodules("rasterio")

# --- Analysis / EXE (单文件、GUI) -------------------------------------------
a = Analysis(
    ["test2.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["PySide6", "PySide6.*"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=False,           # 单文件
    name="ImageAnnotator",
    console=False,                    # GUI
)
