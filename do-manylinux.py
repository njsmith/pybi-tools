# to build local pybi-build-image:
#   (cd ~/manylinux; POLICY=manylinux2014 PLATFORM=x86_64 ./build.sh)
# to use it to build pybis:
#   for VERSION in $(seq -f 3.9.%g 6) $(seq -f 3.8.%g 11) $(seq -f 3.7.%g 11) $(seq -f 3.6.%g 14); do docker run --rm -it -v $(pwd):/host pybi-build-image sh -c "PREFIX=/pyinstall /build_scripts/build-cpython.sh ${VERSION} && /opt/_internal/cpython-3.9.5/bin/python3 -m ensurepip && PYTHONPATH=/host/local-pkgs /opt/_internal/cpython-3.9.5/bin/python3 /host/do-manylinux.py"; done

import sys
from pathlib import Path
import platform

from pybi import make_pybi
from linux_vendor import repair

tag = f"manylinux_2_17_{platform.machine().lower()}"

base_path = Path("/pyinstall")
repair(base_path, tag)
make_pybi(base_path, Path("/host/built"), scripts_path="bin", platform_tag=tag)
