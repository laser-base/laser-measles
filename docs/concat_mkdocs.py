#!/usr/bin/env python3
"""
concat_mkdocs.py — convert the laser-measles MkDocs HTML build to a single markdown file.

Reads from a MkDocs HTML output directory, extracts main content from each page,
converts executed Jupyter notebooks to text, and writes a single combined.md.

Usage:
    python concat_mkdocs.py <mkdocs_site_dir> <executed_notebooks_dir> <output_file>

Example:
    python concat_mkdocs.py ../laser-measles/dist/mkdocs /tmp/executed_tutorials combined_mkdocs.md
"""

import json
import re
import sys
from pathlib import Path

import markdownify
from bs4 import BeautifulSoup

try:
    import laser.measles

    _LASER_MEASLES_VERSION = laser.measles.__version__
except Exception:
    _LASER_MEASLES_VERSION = "unknown"


def extract_markdown(html_path: Path) -> str:
    """Extract main content from a MkDocs HTML page and convert to markdown."""
    text = html_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")

    # MkDocs Material puts content in article or div[role=main]
    content = soup.find("article") or soup.find("div", role="main") or soup.find("div", {"class": "md-content"}) or soup.find("body")
    if content is None:
        return ""

    # Strip navigation, sidebars, search, footer, and breadcrumbs
    for tag in content.find_all(["nav", "footer", "script", "style"]):
        tag.decompose()
    for tag in content.find_all(class_=["md-nav", "md-sidebar", "md-search", "md-header", "md-footer", "headerlink", "md-breadcrumb"]):
        tag.decompose()

    # Fix MkDocs syntax-highlighted code blocks: rendered as a two-column table
    # (class="highlighttable") with line numbers in td.linenos and code in td.code.
    # markdownify converts these to garbled markdown tables. Replace each table
    # with just the <pre><code> from the code cell before markdownify runs.
    for table in content.find_all("table", class_="highlighttable"):
        code_td = table.find("td", class_="code")
        if code_td:
            pre = code_td.find("pre")
            if pre:
                table.replace_with(pre)
            else:
                table.decompose()
        else:
            table.decompose()

    md = markdownify.markdownify(
        str(content),
        heading_style=markdownify.ATX,
        code_language="python",
        strip=["a"],
    )

    # Collapse 3+ blank lines to 2
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def notebook_to_markdown(nb_path: Path) -> str:
    """Convert an executed Jupyter notebook to plain markdown.

    Markdown cells are included as-is.
    Code cells are included as fenced Python blocks.
    Text outputs are included inline after the code fence.
    Image outputs (plots) are skipped.
    """
    with nb_path.open(encoding="utf-8") as f:
        nb = json.load(f)

    parts = []
    for cell in nb["cells"]:
        if cell["cell_type"] == "markdown":
            src = "".join(cell["source"])
            if src.strip():
                parts.append(src.strip())
        elif cell["cell_type"] == "code":
            src = "".join(cell["source"]).strip()
            if not src:
                continue
            parts.append(f"```python\n{src}\n```")
            for output in cell.get("outputs", []):
                otype = output.get("output_type", "")
                if otype in ("stream", "execute_result", "display_data"):
                    text = output.get("text") or output.get("data", {}).get("text/plain", [])
                    if isinstance(text, list):
                        text = "".join(text)
                    if text and text.strip():
                        # Skip lines that look like progress bars or pure decorative output
                        cleaned = re.sub(r"<[^>]+>", "", text).strip()
                        if cleaned:
                            # Annotate Polars schema output that shows i64 for integer columns:
                            # tutorial notebooks use untyped construction so schemas print i64,
                            # but laser-measles requires Int32. Warn the LLM inline.
                            if re.search(r"┆\s*i64\s*┆|┆\s*i64\s*│|│\s*i64\s*┆|│\s*i64\s*│", cleaned):
                                cleaned += "\n# NOTE: 'i64' shown above reflects untyped tutorial code. laser-measles requires Int32 for integer columns (pop, etc.) and str for id."
                            parts.append(f"```\n{cleaned}\n```")

    md = "\n\n".join(parts)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def get_reference_pages(base: Path):
    """Return all reference index.html pages, excluding /base/ subdirs."""
    ref_dir = base / "reference"
    if not ref_dir.exists():
        return []
    pages = sorted(ref_dir.rglob("index.html"))

    # Exclude pages under /base/ directories and base_* subdirectories (internal base classes)
    def is_base(p: Path) -> bool:
        parts = p.relative_to(ref_dir).parts
        return any(part == "base" or part.startswith("base_") for part in parts[:-1])  # exclude index.html itself

    return [p for p in pages if not is_base(p)]


def concat(mkdocs_dir: str, notebooks_dir: str, output_file: str):
    base = Path(mkdocs_dir)
    nb_dir = Path(notebooks_dir)

    # Main narrative pages
    main_pages = [
        base / "index.html",
        base / "install" / "index.html",
        base / "usage" / "index.html",
    ]

    # Tutorial notebooks (executed), in logical order
    tutorial_names = [
        "tut_quickstart_hello_world",
        "tut_basic_model",
        "tut_model_structure",
        "tut_abm_intro",
        "tut_scenarios",
        "tut_creating_component",
        "tut_abm_vital_dynamics",
        "tut_spatial_mixing",
        "tut_pydantic_component_parameters",
        "tut_state_arrays",
        "tut_random_numbers",
        "tut_vaccination",
        "tut_traveling_waves",
    ]

    # Reference pages (all public, excluding /base/)
    ref_pages = get_reference_pages(base)

    # Minimum content length to include a section (filters empty module-index headings)
    MIN_SECTION_CHARS = 150

    parts = [f"# laser-measles documentation\n\n**laser-measles version: {_LASER_MEASLES_VERSION}**"]
    included = 0
    skipped = 0

    print(f"laser-measles version: {_LASER_MEASLES_VERSION}")
    print("=== Main pages ===")
    for path in main_pages:
        if not path.exists():
            print(f"  skip (not found): {path.relative_to(base)}")
            skipped += 1
            continue
        md = extract_markdown(path)
        if md and len(md) >= MIN_SECTION_CHARS:
            parts.append(f"\n\n---\n<!-- {path.relative_to(base)} -->\n\n{md}")
            print(f"  ok: {path.relative_to(base)}")
            included += 1
        elif md:
            print(f"  skip (too short, {len(md)} chars): {path.relative_to(base)}")
            skipped += 1

    print("\n=== Tutorials (executed notebooks) ===")
    for name in tutorial_names:
        nb_path = nb_dir / f"{name}.ipynb"
        if not nb_path.exists():
            print(f"  skip (not found): {name}.ipynb")
            skipped += 1
            continue
        md = notebook_to_markdown(nb_path)
        if md and len(md) >= MIN_SECTION_CHARS:
            parts.append(f"\n\n---\n<!-- tutorials/{name} -->\n\n{md}")
            print(f"  ok: {name}.ipynb")
            included += 1
        elif md:
            print(f"  skip (too short, {len(md)} chars): {name}.ipynb")
            skipped += 1

    print("\n=== Reference pages (excluding /base/) ===")
    for path in ref_pages:
        rel = path.relative_to(base)
        md = extract_markdown(path)
        if md and len(md) >= MIN_SECTION_CHARS:
            parts.append(f"\n\n---\n<!-- {rel} -->\n\n{md}")
            print(f"  ok: {rel}")
            included += 1
        elif md:
            print(f"  skip (too short, {len(md)} chars): {rel}")
            skipped += 1
        else:
            skipped += 1

    output = Path(output_file)
    output.write_text("\n".join(parts), encoding="utf-8")
    print(f"\nWrote {included} sections ({skipped} skipped) -> {output_file}")
    print(f"Output size: {output.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python concat_mkdocs.py <mkdocs_site_dir> <executed_notebooks_dir> <output_file>")
        sys.exit(1)
    concat(sys.argv[1], sys.argv[2], sys.argv[3])
