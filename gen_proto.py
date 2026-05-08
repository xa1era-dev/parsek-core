#!/usr/bin/env python3
"""
Compiles .proto files with betterproto, then restructures output:
  - X/__init__.py  →  X.py  (top-level packages)
  - packages matching a proto subdirectory stay as directories;
    their merged __init__.py is split into per-proto-file modules
  - empty __init__.py are deleted
"""

import ast
import re
import shutil
import subprocess
from pathlib import Path

PROTO_DIR = Path("core/proto")
GEN_DIR = Path("core/gen")
PLUGIN = Path(".venv/bin/protoc-gen-python_betterproto")

# Subdirectory names in PROTO_DIR that should remain as packages (not flattened)
KEEP_AS_PACKAGES = {p.name for p in PROTO_DIR.iterdir() if p.is_dir()}


def run_protoc() -> None:
    proto_files = sorted(PROTO_DIR.rglob("*.proto"))
    subprocess.run(
        [
            "protoc",
            f"--plugin=protoc-gen-python_betterproto={PLUGIN}",
            f"--python_betterproto_out={GEN_DIR}",
            "--proto_path=.",
            *map(str, proto_files),
        ],
        check=True,
    )


def flatten_packages(base: Path) -> None:
    """
    For each __init__.py under base (deepest first):
    - base/__init__.py: delete
    - subdir matching a proto subdir: split instead (handled separately)
    - X/__init__.py: rename to X.py, remove empty dir
    """
    for init_file in sorted(base.rglob("__init__.py"), reverse=True):
        pkg_dir = init_file.parent
        if pkg_dir == base:
            init_file.unlink()
            continue
        if pkg_dir.parent == base and pkg_dir.name in KEEP_AS_PACKAGES:
            continue
        if not init_file.read_text().strip():
            init_file.unlink()
        else:
            flat = pkg_dir.parent / f"{pkg_dir.name}.py"
            shutil.move(str(init_file), str(flat))
            print(f"  {init_file.relative_to(base)} → {flat.relative_to(base)}")
        if not list(pkg_dir.iterdir()):
            pkg_dir.rmdir()


def _node_line_range(node: ast.ClassDef, lines: list[str]) -> set[int]:
    """0-based indices for the class, including decorators and preceding blank lines."""
    start = node.decorator_list[0].lineno - 1 if node.decorator_list else node.lineno - 1
    while start > 0 and not lines[start - 1].strip():
        start -= 1
    return set(range(start, node.end_lineno))


def split_subpackage(pkg_dir: Path, proto_subdir: Path) -> None:
    """
    Split a merged __init__.py into per-proto-file modules:
      betterproto.Enum subclasses  → <enums_stem>.py
      betterproto.Message subclasses → <other_stem>.py
    Adds a relative import in the message file for the enum names.
    """
    init_file = pkg_dir / "__init__.py"
    if not init_file.exists():
        return

    source = init_file.read_text()
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    class_nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)]

    enum_nodes: list[ast.ClassDef] = []
    msg_nodes: list[ast.ClassDef] = []
    for node in class_nodes:
        bases = [ast.unparse(b) for b in node.bases]
        if any("Enum" in b for b in bases):
            enum_nodes.append(node)
        else:
            msg_nodes.append(node)

    # Header: everything before the first class
    first_line = min((n.lineno for n in class_nodes), default=len(lines) + 1) - 1
    header = "".join(lines[:first_line])

    enum_indices: set[int] = set()
    for n in enum_nodes:
        enum_indices |= _node_line_range(n, lines)

    msg_indices: set[int] = set()
    for n in msg_nodes:
        msg_indices |= _node_line_range(n, lines)

    proto_stems = [p.stem for p in sorted(proto_subdir.glob("*.proto"))]
    enum_stem = next((s for s in proto_stems if "enum" in s), proto_stems[0])
    msg_stem = next((s for s in proto_stems if s != enum_stem), proto_stems[-1])

    # enums.py — no dataclass import needed
    enum_header = re.sub(r"^from dataclasses import dataclass\n", "", header, flags=re.MULTILINE)
    enum_content = enum_header + "".join(l for i, l in enumerate(lines) if i in enum_indices)

    # task.py — add relative import for enums
    enum_names = sorted(n.name for n in enum_nodes)
    enum_import = f"from .{enum_stem} import {', '.join(enum_names)}\n\n"
    msg_content = header + enum_import + "".join(l for i, l in enumerate(lines) if i in msg_indices)

    (pkg_dir / f"{enum_stem}.py").write_text(enum_content)
    (pkg_dir / f"{msg_stem}.py").write_text(msg_content)

    # __init__.py re-exports everything so `import shared` still works
    all_names = sorted(n.name for n in enum_nodes + msg_nodes)
    all_enum_names = ", ".join(sorted(n.name for n in enum_nodes))
    all_msg_names = ", ".join(sorted(n.name for n in msg_nodes))
    init_reexport = (
        f"from .{enum_stem} import {all_enum_names}\n"
        f"from .{msg_stem} import {all_msg_names}\n\n"
        f"__all__ = {all_names!r}\n"
    )
    (pkg_dir / "__init__.py").write_text(init_reexport)
    print(f"  {pkg_dir.name}/__init__.py → {pkg_dir.name}/{enum_stem}.py + {pkg_dir.name}/{msg_stem}.py")


def fix_toplevel_imports(base: Path) -> None:
    """
    After flattening, top-level .py files still have `from .. import X as _X__`
    (generated when they lived inside a sub-package).
    Replace with plain `import X` and update all `_X__.` usages to `X.`.
    """
    for py_file in base.glob("*.py"):
        source = py_file.read_text()
        changed = False

        def replace_import(m: re.Match) -> str:
            nonlocal changed
            changed = True
            return f"import core.gen.{m.group(1)} as {m.group(1)}"

        # `from .. import foo as _foo__`  →  `import foo`
        fixed = re.sub(
            r"^from \.\. import (\w+)(?: as \w+)?$",
            replace_import,
            source,
            flags=re.MULTILINE,
        )

        # Replace all `_foo__.` → `foo.` for each aliased module
        for m in re.finditer(r"^from \.\. import (\w+) as (\w+)$", source, re.MULTILINE):
            mod, alias = m.group(1), m.group(2)
            fixed = fixed.replace(f"{alias}.", f"{mod}.")

        if changed:
            py_file.write_text(fixed)
            print(f"  fixed imports in {py_file.name}")


def main() -> None:
    if GEN_DIR.exists():
        shutil.rmtree(GEN_DIR)
    GEN_DIR.mkdir(parents=True)

    print("protoc...")
    run_protoc()

    print("Flattening packages...")
    flatten_packages(GEN_DIR)

    print("Splitting subpackages...")
    for subdir_name in KEEP_AS_PACKAGES:
        pkg_dir = GEN_DIR / subdir_name
        proto_subdir = PROTO_DIR / subdir_name
        if pkg_dir.exists():
            split_subpackage(pkg_dir, proto_subdir)

    print("Fixing top-level imports...")
    fix_toplevel_imports(GEN_DIR)

    print("Done.")


if __name__ == "__main__":
    main()
