from collections import defaultdict
from pathlib import Path
from auditwheel.lddtree import lddtree
from auditwheel.elfutils import (
    elf_file_filter, elf_find_versioned_symbols, elf_read_dt_needed
)
from auditwheel.policy import lddtree_external_references
from auditwheel.repair import (
    get_wheel_elfdata, copylib, append_rpath_within_wheel
)
from auditwheel.patcher import Patchelf


# Copy/pasted and tweaked from auditwheel.wheel_abi.get_wheel_elfdata
def get_tree_elfdata(base_path: Path):
    versioned_symbols = defaultdict(lambda: set())  # type: Dict[str, Set[str]]
    full_elftree = {}
    full_external_refs = {}

    for fn, elf in elf_file_filter(str(fn) for fn in base_path.rglob("*") if fn.is_file()):
        elftree = lddtree(fn)
        for key, value in elf_find_versioned_symbols(elf):
            versioned_symbols[key].add(value)

        full_elftree[fn] = elftree
        full_external_refs[fn] = lddtree_external_references(elftree, base_path)

    return (full_elftree, full_external_refs, versioned_symbols)


# Copy/pasted and tweaked from auditwheel.repair.repair_wheel
# Takes the path to an unpacked pybi tree, and does the auditwheel vendoring.
# ABI should be something like "manylinux_2_17_x86_64"
def repair(base_path: Path, abi: str, *, lib_sdir=".libs"):
    patcher = Patchelf()

    external_refs_by_fn = get_tree_elfdata(base_path)[1]

    soname_map = {}  # type: Dict[str, Tuple[str, str]]

    dest_dir = base_path / lib_sdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    # here, fn is a path to an ELF file in the wheel, and v['libs'] contains its
    # required libs
    for fn, v in external_refs_by_fn.items():
        ext_libs = v[abis[0]]['libs']  # type: Dict[str, str]
        for soname, src_path in ext_libs.items():
            if src_path is None:
                if (dst_dir / soname).exists():
                    # Already bundled
                    continue
                raise ValueError(('Cannot repair pybi, because required '
                                  'library "%s" could not be located') %
                                 soname)

            new_soname, new_path = copylib(src_path, dest_dir, patcher)
            soname_map[soname] = (new_soname, new_path)
            patcher.replace_needed(fn, soname, new_soname)

        if len(ext_libs) > 0:
            new_rpath = os.path.relpath(dest_dir, os.path.dirname(fn))
            new_rpath = os.path.join('$ORIGIN', new_rpath)
            append_rpath_within_wheel(fn, new_rpath, base_path, patcher)

    # we grafted in a bunch of libraries and modified their sonames, but
    # they may have internal dependencies (DT_NEEDED) on one another, so
    # we need to update those records so each now knows about the new
    # name of the other.
    for old_soname, (new_soname, path) in soname_map.items():
        needed = elf_read_dt_needed(path)
        for n in needed:
            if n in soname_map:
                patcher.replace_needed(path, n, soname_map[n][0])
