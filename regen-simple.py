from pathlib import Path
import hashlib

built_path = Path("built")

(built_path / "index.html").write_text(
    """<!DOCTYPE html>
    <html>
    <head><title>Simple PyBi index</title></head>
    <body>
    <p>
    This is PEP 503-style "simple" API to this collection of prototype "pybi" Python
    interpreter builds.
    <p>
    The Windows builds are repacked versions of the official Nuget packages maintained
    by Steve Dower.
    <p>
    The macOS builds are repacked versions of the official Python.org macOS installers,
    that have been run through Greg Neagle's "relocatablizer".
    <p>
    The Linux builds are custom-built using the same scripts that are used to generate
    the official manylinux2014 image.

    <ul>
      <li><a href="/cpython_unofficial/">cpython_unofficial</a>
    </ul>
    </body>
    </html>
    """)

(built_path / "cpython_unofficial").mkdir(exist_ok=True)

with open(built_path / "cpython_unofficial" / "index.html", "w") as f:
    f.write("<!DOCTYPE html><html><body>\n")
    for pybi_path in built_path.glob("*.pybi"):
        print(pybi_path)
        assert pybi_path.name.startswith("cpython_unofficial-")
        hasher = hashlib.new("sha256")
        hasher.update(pybi_path.read_bytes())
        raw_hash = hasher.digest()
        f.write(
            f"""<br><a href="/{pybi_path.name}#sha256={raw_hash.hex()}">{pybi_path.name}</a>\n"""
        )
    f.write("</body></html>\n")
