import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from bs4 import BeautifulSoup
import shutil
import re
import requests
http = requests.Session()

from pybi import make_pybi

# --os-version 10.6, 10.9, 11
#   3.6 has 10.6 and 10.9
#   ...seems inconsistent between point releases and stuff too
# --python-version=

# ...maybe scrape https://www.python.org/ftp/python/ ?

# macos11.pkg -> macosx_11_0_universal2
# macosx10.9.pkg -> macosx_10_9_x86_64
# macosx10.6.pkg -> macosx_10_6_intel

built_path = Path("built").absolute()

version_link_re = re.compile(r"^([0-9]+)\.([0-9]+)(\.[0-9]+)?/")

def find_all_macos_builds():
    r = http.get("https://www.python.org/ftp/python/")
    r.raise_for_status()
    for link in BeautifulSoup(r.text, features="lxml").find_all("a"):
        target = link.get("href")
        match = version_link_re.match(target)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2))
            if (major, minor) >= (3, 6):
                base_url = f"https://www.python.org/ftp/python/{target}/"
                r = http.get(base_url)
                r.raise_for_status()
                for link in BeautifulSoup(r.text, features="lxml").find_all("a"):
                    package = link.get("href")
                    # "python-3.9.6-macos11.pkg"
                    if not package.startswith("python-"):
                        continue
                    version_str = package.split("-")[1]
                    if version_str.startswith("3.6.0a"):
                        # Some 3.6 alphas didn't yet support variable annotations, so
                        # they can't parse current 'packaging'
                        continue
                    if package.endswith("macos11.pkg"):
                        yield (version_str, "macosx_11_0_universal2", "11")
                    elif package.endswith("macosx10.9.pkg"):
                        yield (version_str, "macosx_10_9_x86_64", "10.9")
                    elif package.endswith("macosx10.6.pkg"):
                        yield (version_str, "macosx_10_6_intel", "10.6")


def maybe_repack(py_version, tag, os_version):
    pybi = built_path / f"cpython_unofficial-{py_version}-{tag}.pybi"
    print(f"\n\n\n\n\n\n----------------- Repacking {pybi} ----------------")
    if pybi.exists():
        print("   -> already exists, skipping")
        return
    with TemporaryDirectory() as tempdir:
        subprocess.run(
            [
                "../relocatable-python/make_relocatable_python_framework.py",
                "--python-version", py_version,
                "--os-version", os_version,
                "--destination", tempdir,
                "--pip-requirements", "/dev/null",
            ],
            check=True,
        )
        base_path = Path(tempdir)
        (scripts_path,) = base_path.glob("Python.framework/Versions/3.*/bin")
        (site_packages_path,) = base_path.glob("Python.framework/Versions/Current/lib/*/site-packages")

        for p in scripts_path.glob("pip*"):
            print(f"Blowing away {p}")
            p.unlink()

        for p in site_packages_path.iterdir():
            if p.name != "README.txt":
                print(f"Blowing away {p}")
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()

        print("Removing stdlib `test` module")
        shutil.rmtree(site_packages_path.parent / "test")

        make_pybi(base_path, built_path, scripts_path=scripts_path, platform_tag=tag)


for py_version, tag, os_version in find_all_macos_builds():
    maybe_repack(py_version, tag, os_version)
