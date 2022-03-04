# What is this

"Pybi" is a new format for distributing Python interpreters. For more
details, [see this draft
spec](https://github.com/njsmith/posy/blob/main/pybi/README.md).

While working on it, I've made some preliminary pybis for most
versions of CPython 3.6+ on Windows/macOS/Linux, and they're available
here: https://pybi.vorpus.org

This repo has the hacky tools I used to make those preliminary pybis.
Parts of this are pretty sophisticated. Other parts are duct tape and
chicken wire to that will only work for the exact pipeline I used.


# Overview

The Windows pybis are repacks of the official nuget packages
maintained by Steve Dower; `do-win.py` uses the nuget API to find them
all and repack them.

The macOS pybis are repacks for the official macOS framework builds
from https://python.org/downloads, munged by [Greg Neagle's
scripts](https://github.com/gregneagle/relocatable-python) to make
them relocatable. `do-macos.py` scrapes python.org to automatically
find these builds.

The Linux pybis are build by hand, but reusing most of the manylinux
docker image build scripts, with [a few
tweaks](https://github.com/pypa/manylinux/compare/main...njsmith:pybi).
Then `linux_vendor.py` does some hacky stuff to trick auditwheel into
working on an unpacked pybi.


# Notes to self

To add new pybis:

- on sidra, add to built/ directory
- on sidra, run `python3 regen-simple.py`
- go to the $web container in azure portal and get a SAS token
- on sidra, *in built/ directory*, run:

  ```
  az storage blob sync -s . --account-name pybi --container '$web' --sas-token [token]
  ```
