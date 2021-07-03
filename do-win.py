import zipfile
from tempfile import TemporaryDirectory
import shutil
from pathlib import Path
import json
import io

from pybi import make_pybi

import requests
http = requests.Session()

built_path = Path("built").absolute()

def repack_nupkg(tag, nupkg_file, work_path):
    zipfile.ZipFile(nupkg_file).extractall(work_path)

    # actual python environment is nested inside a "tools/" directory
    base_path = work_path / "tools"

    scripts_path = base_path / "Scripts"
    scripts_path.mkdir(exist_ok=True)

    for p in base_path.iterdir():
        if p.suffix in (".exe", ".dll"):
            p.rename(base_path / "Scripts" / p.name)

    for p in (base_path / "Lib" / "site-packages").iterdir():
        if p.name != "README.txt":
            print(f"Blowing away {p}")
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()

    make_pybi(base_path, built_path, scripts_path="Scripts", platform_tag=tag)


def python_nupkg_urls():
    response = http.get("https://api.nuget.org/v3/index.json")
    response.raise_for_status()
    for resource in response.json()["resources"]:
        if resource["@type"] == "PackageBaseAddress/3.0.0":
            base = resource["@id"]
            break
    else:
        raise RuntimeError("nuget.org broken?")
    for pkg in ["python", "pythonx86"]:
        response = http.get(f"{base}{pkg}/index.json")
        response.raise_for_status()
        for version in response.json()["versions"]:
            yield (pkg, version, f"{base}{pkg}/{version}/{pkg}.{version}.nupkg")


for pkg, version, url in python_nupkg_urls():
    if version.startswith("3.5."):
        continue
    if pkg == "python":
        tag = "win_amd64"
    else:
        assert pkg == "pythonx86"
        tag = "win32"
    pybi_name = f"cpython_unofficial-{version}-{tag}.pybi"
    if not (built_path / pybi_name).exists():
        print(f"Building {pybi_name}")
        nupkg_data = http.get(url).content
        with TemporaryDirectory() as work_path:
            repack_nupkg(tag, io.BytesIO(nupkg_data), Path(work_path))
