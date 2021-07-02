import sys
from pathlib import Path
import platform

from pybi import make_pybi
from linux_vendor import repair

arch = platform.processor()

base_path = Path("/builtpy")
repair(base_path)
make_pybi(base_path, "/host", scripts_path="bin", platform_tag=f"manylinux_2_17_{arch}")
