from pathlib import Path
import hashlib

built_path = Path("built")

(built_path / "index.html").write_text(
    """<!DOCTYPE html>
    <html>
    <head><title>Simple PyBi index</title></head>
    <body>
    <p>
    This is the PEP 503-style "simple" API to this collection of prototype "pybi" Python
    interpreter builds. So far it's just CPython, though it'd be cool to get PyPy in
    here too, maybe even Cinder or Pyston.

    <p>
    The Windows builds are repacked versions of the official Nuget packages maintained
    by Steve Dower.

    <p>
    The macOS builds are repacked versions of the official Python.org framework
    packages, that have been run through Greg Neagle's "relocatablizer" (see
    https://github.com/gregneagle/relocatable-python).

    <p>
    The Linux builds are custom-built using the same scripts that are used to generate
    the interpreters included in the official manylinux2014 (CentOS 7-based) docker
    image. (TODO: add musllinux builds too.)

    <ul>
      <li><a href="/cpython_unofficial/">cpython_unofficial</a>
    </ul>
    </body>
    </html>
    """)

(built_path / "cpython_unofficial").mkdir(exist_ok=True)

with open(built_path / "cpython_unofficial" / "index.html", "w") as f:
    f.write("<!DOCTYPE html><html><body>\n")
    # I guess if we wanted to be fancy we could do a proper version sort, but a naive
    # string sort is still better than nothing.
    for pybi_path in sorted(built_path.glob("*.pybi")):
        print(pybi_path)
        assert pybi_path.name.startswith("cpython_unofficial-")
        hasher = hashlib.new("sha256")
        hasher.update(pybi_path.read_bytes())
        raw_hash = hasher.digest()
        f.write(
            f"""<a href="/{pybi_path.name}#sha256={raw_hash.hex()}">{pybi_path.name}</a><br>\n"""
        )
    f.write("</body></html>\n")
