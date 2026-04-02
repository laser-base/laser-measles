# docs/gen-files.py
from __future__ import annotations

import logging
from pathlib import Path
from pathlib import PurePosixPath

import mkdocs_gen_files as gen

logger = logging.getLogger(__name__)

SRC = Path("src")
NS = "laser"
NS_ROOT = SRC / NS


def ref_md(dotted: str) -> str:
    """reference/<dotted>/index.md with POSIX separators."""
    return str(PurePosixPath("reference") / "/".join(dotted.split(".")) / "index.md")


def emit_page(dotted: str, body: str | None = None) -> None:
    with gen.open(ref_md(dotted), "w") as f:
        if body is None:
            f.write(f"# {dotted}\n\n")
            f.write(f"::: {dotted}\n")
            f.write("    options:\n")
            f.write("      show_root_heading: true\n")
            f.write("      members_order: alphabetical\n")
            f.write("      show_source: false\n")
        else:
            f.write(body)


# ---------- collect from disk: every module + all ancestor packages ----------
packages: set[str] = set()
modules: set[str] = set()

# Ensure the root 'laser' landing exists so we can nest under it if desired
packages.add(NS)

for py in NS_ROOT.rglob("*.py"):
    if py.name == "__init__.py":
        # still create the package page for its directory
        pkg = py.parent.relative_to(SRC).as_posix().replace("/", ".")
        packages.add(pkg)
        continue

    # module page for each file
    rel_mod = py.relative_to(SRC).with_suffix("")
    dotted_mod = rel_mod.as_posix().replace("/", ".")
    modules.add(dotted_mod)

    # ancestor packages up to 'laser'
    p = py.parent
    while True:
        rel_pkg = p.relative_to(SRC).as_posix().replace("/", ".")
        packages.add(rel_pkg)
        if rel_pkg == NS:
            break
        p = p.parent

# ---------- emit all pages ----------
emitted: set[str] = set()


def emit_once(dotted: str, body: str | None = None) -> None:
    if dotted in emitted:
        return
    emit_page(dotted, body)
    emitted.add(dotted)


# small landing for 'laser'
emit_once(NS, f"# {NS}\n\nRoot namespace for LASER packages.\n")

for name in sorted(packages, key=lambda s: (s.count("."), s)):
    emit_once(name)

for name in sorted(modules, key=lambda s: (s.count("."), s)):
    emit_once(name)

# ---------- SUMMARY.md (two siblings, with correct hierarchical ordering) ----------


def _build_tree(root: str, names: set[str]) -> dict:
    """
    Build a nested dict representing the subtree under `root`.
    Ensures all intermediate parents are present.
    Example tree keys are the *segment* names (e.g., 'generic', 'models', 'SEIR').
    """
    root_parts = root.split(".")
    tree: dict = {}

    def insert(parts: list[str]) -> None:
        node = tree
        for seg in parts:
            node = node.setdefault(seg, {})

    # Consider only entries under the root (including root itself, though we'll render root separately)
    for full in (n for n in names if n == root or n.startswith(root + ".")):
        parts = full.split(".")
        # Add every prefix between root and the leaf
        for i in range(len(root_parts) + 1, len(parts) + 1):
            insert(parts[len(root_parts) : i])  # relative parts under root

    return tree


def _render_tree(root: str, tree: dict) -> list[str]:
    """
    Render the nested dict as literate-nav bullets under `root`.
    Outputs links relative to 'reference/' using '.../index.md'.
    """
    lines: list[str] = []

    def walk(rel_parts: list[str], node: dict):
        # rel_parts is the path under the root (e.g., ['generic', 'models'])
        dotted = ".".join([root, *rel_parts])
        depth = len(rel_parts)  # depth under the root
        indent = "  " * depth  # bullet indent under the root line we'll add earlier
        path = "/".join([root.replace(".", "/"), *rel_parts]) + "/index.md"
        lines.append(f"{indent}- [{dotted}]({path})\n")
        for seg in sorted(node.keys()):
            walk([*rel_parts, seg], node[seg])

    # walk each top-level child under the root
    for seg in sorted(tree.keys()):
        walk([seg], tree[seg])

    return lines


def _write_block(root: str, pool: set[str]) -> list[str]:
    """
    Write the top-level root entry and a properly ordered subtree beneath it.
    """
    if root not in pool:
        return []

    # Top-level root entry (sibling under API reference)
    out: list[str] = [f"- [{root}]({root.replace('.', '/')}/index.md)\n"]
    subtree = _build_tree(root, pool)
    out.extend(_render_tree(root, subtree))
    return out


# Build SUMMARY with the laser.measles block only
summary_lines: list[str] = ["# API reference\n"]
for root in ("laser.measles",):
    summary_lines += _write_block(root, emitted)

with gen.open("reference/SUMMARY.md", "w") as f:
    f.write("".join(summary_lines))
