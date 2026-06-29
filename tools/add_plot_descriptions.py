"""Insert markdown plot-description cells into jupytext percent-format .py
tutorial files.

Driven by a JSON manifest of (tutorial, marker, md_file) inserts. The script
is idempotent: it identifies an already-inserted description by matching the
first line of the markdown file against the next cell after the marker cell,
so re-running makes no changes.

Adapted from laser-base/laser-core's tools/add_plot_descriptions.py — same
manifest format and --check semantics, but reads/writes percent-format .py
files (cells delimited by lines starting with '# %%') instead of .ipynb JSON.
laser-measles tutorial sources live in this format; `scripts/convert_tutorials.py`
runs jupytext to convert them to .ipynb for the docs build.

Manifest format (paths resolved relative to the manifest file's directory):

    [
      {
        "tutorial": "../../docs/tutorials/tut_basic_model.py",
        "inserts": [
          {
            "after_cell_containing": "plt.title(\"Population Distribution\")",
            "md_file": "tut_basic_model_population_scatter.md"
          }
        ]
      }
    ]

Usage:
    python tools/add_plot_descriptions.py tools/plot_descriptions/config.json
    python tools/add_plot_descriptions.py tools/plot_descriptions/config.json --check
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Anchored to start of line; matches '# %%' optionally followed by anything
# (e.g. ' [markdown]'). The whole line is the cell delimiter.
CELL_HEADER = re.compile(r"^# %%(.*)$", re.MULTILINE)


def parse_cells(text):
    """Split percent-format source into cells.

    Returns a list of dicts: {'type': 'code'|'markdown', 'header': str, 'body': str}.
    Any text before the first '# %%' line becomes a 'preamble' cell with type 'preamble'.
    """
    matches = list(CELL_HEADER.finditer(text))
    cells = []
    if not matches:
        return [{"type": "preamble", "header": "", "body": text}]
    if matches[0].start() > 0:
        cells.append({"type": "preamble", "header": "", "body": text[: matches[0].start()]})
    for i, m in enumerate(matches):
        header_line = m.group(0)
        rest = m.group(1).strip()
        cell_type = "markdown" if rest.startswith("[markdown]") else "code"
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end]
        # Strip the trailing newline that belongs to the header line itself,
        # since we'll re-add headers on serialize.
        if body.startswith("\n"):
            body = body[1:]
        cells.append({"type": cell_type, "header": header_line, "body": body})
    return cells


def serialize_cells(cells):
    out = []
    for c in cells:
        if c["type"] == "preamble":
            out.append(c["body"])
            continue
        out.append(c["header"] + "\n" + c["body"])
    return "".join(out)


def code_cell_source(cell):
    # The body of a code cell is just Python — no comment-prefix to strip.
    return cell["body"]


def markdown_cell_source(cell):
    # In percent-format, markdown cell content has each line prefixed with '# '
    # (or just '#' for blank-comment lines). Strip the prefix to get the raw markdown.
    lines = cell["body"].splitlines()
    out = []
    for line in lines:
        if line.startswith("# "):
            out.append(line[2:])
        elif line == "#":
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def find_marker_cell(cells, marker):
    matches = [i for i, c in enumerate(cells) if c["type"] == "code" and marker in code_cell_source(c)]
    if not matches:
        raise LookupError(f"no code cell contains marker {marker!r}")
    if len(matches) > 1:
        raise LookupError(f"marker {marker!r} is ambiguous (code cells at indices {matches})")
    return matches[0]


def heading_of(text):
    lines = text.lstrip().splitlines()
    if not lines:
        raise ValueError("plot-description text is empty or whitespace-only; check the .md file for accidental truncation")
    return lines[0].strip()


def markdown_cell_from_text(text):
    """Build a percent-format markdown cell from raw markdown text."""
    text = text.rstrip() + "\n"
    body_lines = []
    for line in text.splitlines():
        if line == "":
            body_lines.append("#")
        else:
            body_lines.append("# " + line)
    return {
        "type": "markdown",
        "header": "# %% [markdown]",
        "body": "\n".join(body_lines) + "\n\n",
    }


def apply_to_pyfile(py_path, inserts, base_dir, *, write=True):
    text = py_path.read_text(encoding="utf-8")
    cells = parse_cells(text)

    plan = []
    for ins in inserts:
        if "after_cell_containing" not in ins:
            raise ValueError("each insert needs an after_cell_containing marker")
        idx = find_marker_cell(cells, ins["after_cell_containing"])
        md_text = (base_dir / ins["md_file"]).read_text(encoding="utf-8").rstrip() + "\n"
        plan.append((idx, md_text))

    changed = False
    # Apply in reverse so earlier inserts don't shift later positions.
    for idx, md_text in sorted(plan, key=lambda x: x[0], reverse=True):
        wanted_heading = heading_of(md_text)
        next_idx = idx + 1
        already_present = (
            next_idx < len(cells)
            and cells[next_idx]["type"] == "markdown"
            and heading_of(markdown_cell_source(cells[next_idx])) == wanted_heading
        )
        if already_present:
            # Update content if the .md file has changed since last apply.
            existing = markdown_cell_source(cells[next_idx]).rstrip() + "\n"
            if existing != md_text:
                cells[next_idx] = markdown_cell_from_text(md_text)
                changed = True
            continue
        cells.insert(next_idx, markdown_cell_from_text(md_text))
        changed = True

    if changed and write:
        py_path.write_text(serialize_cells(cells), encoding="utf-8")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("manifest", type=Path, help="JSON manifest of inserts")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit with status 1 if any tutorial would change (for CI)",
    )
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    base_dir = manifest_path.parent
    entries = json.loads(manifest_path.read_text())

    any_change = False
    for entry in entries:
        py_path = (base_dir / entry["tutorial"]).resolve()
        changed = apply_to_pyfile(py_path, entry["inserts"], base_dir, write=not args.check)
        print(f"{'CHANGED' if changed else 'ok     '} {py_path}")
        any_change |= changed

    if args.check and any_change:
        sys.exit(1)


if __name__ == "__main__":
    main()
