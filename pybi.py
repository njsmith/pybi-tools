import sys
import zipfile
import hashlib
import csv
import base64
import os
import os.path
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
from tempfile import TemporaryDirectory
import itertools

SYMLINK_MODE = 0xA000
SYMLINK_MASK = 0xF000
MODE_SHIFT = 16


def path_in(inner, outer):
    return os.path.commonpath([inner, outer]) == str(outer)


def fixup_shebang(base_path, scripts_path, path, data):
    if not data.startswith(b"#!"):
        return data
    script = data.decode("utf-8")
    shebang, rest = script.split("\n", 1)
    interpreter_path = (path.parent / shebang[2:]).resolve()
    if not path_in(interpreter_path, base_path):
        # Could be #!/bin/sh, for example
        return data
    interpreter_relative = os.path.relpath(interpreter_path, path.parent)
    new_shebang = f"""#!/bin/sh
'''exec' "$(dirname "$0")/{interpreter_relative}" "$0" "$@"
' '''
# The above is magic to invoke an interpreter relative to this script
"""
    return (new_shebang + rest).encode("utf-8")


def is_exec_bit_set(path):
    if os.name != "posix":
        return False
    return bool(path.stat().st_mode & 0o100)


def pack_pybi(base, zipname):
    # *_path are absolute filesystem Path objects
    # *_name are relative PurePosixPath objects referring to locations in the zip file
    base_path = Path(base).resolve()
    (pybi_info_path,) = base_path.glob("*.pybi-info")
    pybi_info_name = PurePosixPath(pybi_info_path.name)
    pybi_meta = json.loads((pybi_info_path / "pybi.json").read_text())
    scripts_path = base / pybi_meta["paths"]["scripts"]

    record_name = pybi_info_name / "RECORD"
    records = [(str(record_name), "", "")]

    z = zipfile.ZipFile(zipname, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True)
    with z:
        deferred = []

        def add_file(path):
            name = PurePosixPath(path.relative_to(base_path).as_posix())
            if name == record_name:
                return
            if path.suffix == ".pyc":
                return
            if path.is_symlink():
                if name.parents[0] == pybi_info_name:
                    raise RuntimeError("can't have symlinks inside .pybi-info")
                target = os.readlink(path)
                if os.path.isabs(target):
                    raise RuntimeError(
                        f"absolute symlinks are forbidden: {path} -> {target}"
                    )
                target_normed = os.path.normpath(path.parent / target)
                if not path_in(target_normed, base_path):
                    raise RuntimeError(
                        f"symlink points outside base: {path} -> {target}"
                    )
                # This symlink is OK
                records.append((path, f"symlink={target}", ""))
                zi = zipfile.ZipInfo(str(name))
                zi.external_attr = SYMLINK_MODE << MODE_SHIFT
                z.writestr(zi, target)
            elif path.is_file():
                data = path.read_bytes()
                if path_in(path, scripts_path):
                    data = fixup_shebang(base_path, scripts_path, path, data)

                hasher = hashlib.new("sha256")
                hasher.update(data)
                hashed = base64.urlsafe_b64encode(hasher.digest()).decode("ascii")
                records.append((str(name), f"sha256={hashed}", str(len(data))))

                if is_exec_bit_set(path):
                    mode = 0o755
                else:
                    mode = 0o644
                zi = zipfile.ZipInfo(str(name))
                zi.external_attr = mode << MODE_SHIFT
                zi.compress_type = zipfile.ZIP_DEFLATED

                if name.parents[0] == pybi_info_name:
                    deferred.append((zi, data))
                else:
                    z.writestr(zi, data)
            else:
                pass

        # Add all the normal files, and compute the full RECORD
        for path in sorted(base_path.rglob("*")):
            add_file(path)

        # Add the RECORD file
        record = io.StringIO()
        record_writer = csv.writer(
            record, delimiter=",", quotechar='"', lineterminator="\n"
        )
        record_writer.writerows(records)
        z.writestr(str(record_name), record.getvalue())

        # Add the rest of the .pybi-info files, so that metadata is right at the end of
        # the zip file and easy to find without downloading the whole file
        for zi, data in deferred:
            z.writestr(zi, data)


def add_pybi_metadata(
    base_path: Path, scripts_path: Path, platform_tag: str, out_dir_path: Path
):
    scripts_path = base_path / scripts_path

    if os.name == "nt":
        if not (scripts_path / "python.exe").exists():
            raise RuntimeError(f"can't find python.exe in {scripts_path}")
    else:
        if not (scripts_path / "python").exists():
            if (scripts_path / "python3").exists():
                (scripts_path / "python").symlink_to("python3")
            else:
                raise RuntimeError(f"can't find python in {scripts_path}")

    with TemporaryDirectory() as temp:
        # --no-user is needed because otherwise, on windows, I get:
        #   ERROR: Can not combine '--user' and '--target'
        # Some kind of buggy default, I guess?
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "packaging", "--no-user", "--target", temp],
            check=True,
        )

        pybi_json_code = (
            f"""
import sys
sys.path.insert(0, {temp!r})
"""
            + """
import packaging.markers
import packaging.tags
import sysconfig
import os.path
import json
import sys

markers_env = packaging.markers.default_environment()
# Delete any keys that depend on the final installation
del markers_env["platform_release"]
del markers_env["platform_version"]

# Copied and tweaked version of packaging.tags.sys_tags
tags = []
interp_name = packaging.tags.interpreter_name()
if interp_name == "cp":
    tags += list(packaging.tags.cpython_tags(platforms=["xyzzy"]))
else:
    tags += list(packaging.tags.generic_tags(platforms=["xyzzy"]))

tags += list(packaging.tags.compatible_tags(platforms=["xyzzy"]))

# Gross hack: packaging.tags normalizes platforms by lowercasing them,
# so we generate the tags with a unique string and then replace it
# with our special uppercase placeholder.
str_tags = [str(t).replace("xyzzy", "PLATFORM") for t in tags]

(base_path,) = sysconfig.get_config_vars("installed_base")
paths = {key: os.path.relpath(path, base_path) for (key, path) in sysconfig.get_paths().items()}

json.dump({"markers_env": markers_env, "tags": str_tags, "paths": paths}, sys.stdout)
            """
        )

        result = subprocess.run(
            [scripts_path / "python"],
            input=pybi_json_code.encode("utf-8"),
            stdout=subprocess.PIPE,
            check=True,
        )

    pybi_json_bytes = result.stdout
    pybi_json = json.loads(pybi_json_bytes)

    assert (base_path / pybi_json["paths"]["scripts"]) == scripts_path

    name = pybi_json["markers_env"]["implementation_name"]
    version = pybi_json["markers_env"]["implementation_version"]

    # for now these are all "proof of concept" builds
    name = f"{name}_unofficial"

    for build_number in itertools.count():
        if build_number > 0:
            pybi_name = f"{name}-{version}-{build_number}-{platform_tag}.pybi"
        else:
            pybi_name = f"{name}-{version}-{platform_tag}.pybi"
        pybi_path = out_dir_path / pybi_name
        if not pybi_path.exists():
            break

    pybi_info_path = base_path / f"{name}-{version}.pybi-info"
    pybi_info_path.mkdir(exist_ok=True)

    (pybi_info_path / "PYBI").write_text(
        "Pybi-Version: 1.0\n"
        "Generator: njs-hacky-script 0.0\n"
        f"Tag: {platform_tag}\n"
        + (f"Build: {build_number}\n" if build_number > 0 else "")
    )

    (pybi_info_path / "METADATA").write_text(
        "Metadata-Version: 2.2\n"
        f"Name: {name}\n"
        f"Version: {version}\n"
        # This is the SPDX identifier for the CPython license. The license text is also
        # included in the interpreter itself (see builtins.license), so I guess we don't
        # need to mess around with including it again.
        "License: Python-2.0\n"
    )

    (pybi_info_path / "pybi.json").write_bytes(pybi_json_bytes)

    return pybi_path


def make_pybi(base_path, out_dir_path, *, scripts_path, platform_tag, build_number=0):
    out_dir_path.mkdir(parents=True, exist_ok=True)
    pybi_path = add_pybi_metadata(base_path, scripts_path, platform_tag, out_dir_path)
    pack_pybi(base_path, pybi_path)
