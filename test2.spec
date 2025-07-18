from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules, collect_data_files
import importlib.util, os, glob, site

site_pkgs = site.getsitepackages()[0]

# shapely/libs/*.dll if exist
shapely_dlls = []
spec = importlib.util.find_spec("shapely")
if spec and spec.submodule_search_locations:
    libs_dir = os.path.join(spec.submodule_search_locations[0], "libs")
    shapely_dlls = [(p, ".") for p in glob.glob(os.path.join(libs_dir, "*.dll"))]

binaries = (
    collect_dynamic_libs("shapely") +
    collect_dynamic_libs("rasterio") +
    collect_dynamic_libs("fiona") +
    shapely_dlls
)

datas = collect_data_files("rasterio") + collect_data_files("fiona")

spec_pj = importlib.util.find_spec("pyproj")
if spec_pj and spec_pj.submodule_search_locations:
    pj_dir = os.path.join(spec_pj.submodule_search_locations[0], "proj_dir")
    if os.path.isdir(pj_dir):
        datas.append((pj_dir, "share/proj"))
