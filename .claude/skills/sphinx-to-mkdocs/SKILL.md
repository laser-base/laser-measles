---
name: sphinx-to-mkdocs
description: Converts Sphinx documentation (reStructuredText .rst files) to MkDocs format (Markdown .md files + mkdocs.yml). Use this skill whenever the user wants to convert, migrate, or port documentation from Sphinx/RST to MkDocs, or asks to "convert docs", "migrate to mkdocs", "convert rst to markdown for mkdocs", "switch from sphinx to mkdocs", or anything involving moving a docs/ folder from Sphinx format to MkDocs format. Always invoke this skill for sphinx-to-mkdocs conversions even if the user only says "convert my docs".
---

## Goal

Convert all Sphinx documentation in `docs-legacy/` to MkDocs format, output to `docs/` using the existing MkDocs template. **Never modify the original `docs-legacy/` folder. Never run `git add`, `git commit`, or `git push` — all output stays local only.**

## Step 1 — Survey the source

Before writing any files, read and map the existing Sphinx project:

1. Scan all `.rst` files under `docs/` (use Glob: `docs/**/*.rst`)
2. Read `docs/conf.py` to extract `project`, `author`, `extensions` (especially `sphinx.ext.autodoc`, `sphinx.ext.graphviz`)
3. Read `docs/index.rst` to extract the top-level `.. toctree::` — this becomes the `nav:` root
4. For each page referenced in a toctree, read it and note any nested `.. toctree::` entries (they become sub-nav groups)
5. Inventory assets: images (`_static/`, `_images/`), any `.csv`, `.png`, `.svg` files

Build a mental map: **toctree hierarchy → nav structure**, **file path → output path**.

## Step 2 — Update `docs/` layout

```
docs/                   ← mirrors docs-legacy/ structure
├── mkdocs.yml          ← MkDocs project config
├── index.md
├── <page>.md
└── <subdir>/
    └── <page>.md
```

Copy all image/asset files into the matching path under `docs/`.

## Step 3 — Update `docs/mkdocs.yml`

```yaml
site_name: <project name from conf.py>
nav:
  # Reproduce the full toctree hierarchy here
  - Home: index.md
  - <Section>:
    - <Page Title>: path/to/page.md
```

Preserve every toctree group as a nav section. Page ordering must match the original.

## Step 4 — Convert each .rst file to .md

**Critical rules — apply to every page without exception:**

- **No invented content.** Convert only what is written in the source `.rst` file. Do not add introductory sentences, summaries, or explanatory text that does not exist in the original.
- **Sidebar fidelity.** The `nav:` entries in `mkdocs.yml` drive the sidebar. Each page's place in the nav must exactly reproduce the toctree hierarchy — no extra sections, no collapsed groups, no reordering.
- **Dynamic graphs must survive.** Any `.. graphviz::`, `.. uml::`, or `.. mermaid::` block must appear in the output as a renderable fenced block. Do not flatten them to static images or plain text.

Apply these transformations for every `.rst` file:

### RST → Markdown equivalents

| RST | Markdown (MkDocs) |
|-----|-------------------|
| `=====` / `-----` / `~~~~~` headings | `#` / `##` / `###` |
| `.. note::` | `!!! note` (admonition block) |
| `.. warning::` | `!!! warning` |
| `.. tip::` / `.. hint::` | `!!! tip` |
| `.. important::` | `!!! important` |
| `.. code-block:: lang` | ` ```lang ` fenced block |
| `.. literalinclude:: file` | Inline the file content as a fenced block |
| `.. image:: path` | `![alt](path)` |
| `.. figure:: path` | `![caption](path)` + caption as italics below |
| `.. toctree::` | Remove — already handled in nav |
| `.. contents::` | Remove — MkDocs auto-generates TOC |
| `:ref:\`label\`` | `[text](target-file.md#anchor)` |
| `:doc:\`path\`` | `[title](path.md)` |
| `:class:\`Name\`` | `` `Name` `` |
| `:func:\`name\`` | `` `name()` `` |
| `:meth:\`name\`` | `` `name()` `` |
| `:attr:\`name\`` | `` `name` `` |
| `.. automodule:: mod` | `::: mod` (mkdocstrings syntax) |
| `.. autoclass:: cls` | `::: cls` |
| `.. graphviz::` | ` ```graphviz ` fenced block (pymdownx.superfences) |
| `**bold**` RST bold | `**bold**` (same) |
| `` `code` `` | `` `code` `` (same) |
| `#. item` ordered list | `1. item` |
| `* item` / `- item` | `- item` |
| `.. csv-table::` | Convert to Markdown table `\| col \| col \|` |

### Admonition block format

```markdown
!!! note "Optional title"
    Indented body text here.
    Multiple lines are fine.
```

### Internal link resolution

For `:ref:` labels, scan all `.rst` files for `.. _label:` anchor definitions to map label → file. Then convert to `[text](file.md#label)`. For `:doc:` references, simply swap `.rst` → `.md`.

## Step 5 — Quality check before finishing

After converting all files:

1. Grep `docs_new/` for any leftover RST patterns: `^\.\. `, `:ref:`, `:doc:`, `.. code-block` — fix any found
2. Verify all paths in `mkdocs.yml` nav exist as actual `.md` files
3. Verify all image paths in `.md` files exist under `docs_new/docs/`
4. Confirm `docs/` is untouched (no new or modified files)
5. Confirm no `.md` file contains content absent from its source `.rst` — the conversion must be faithful, not additive

## Step 6 — Build and serve

Run a build to catch any remaining errors:

```bash
cd docs_new && mkdocs build --strict
```

If the build passes, start the local dev server:

```bash
mkdocs serve
```

Report the local preview URL to the user — by default: **http://127.0.0.1:8000**

If `mkdocs build` reports errors (broken links, missing files, unknown plugins), fix each one before reporting done.

## Output summary

After completing, report:
- Total `.rst` files converted
- Any files that needed manual attention
- Plugins required in `mkdocs.yml` (e.g., `mkdocstrings`, `pymdownx.superfences`)
- Build status (pass / errors fixed)
- **Local preview URL: http://127.0.0.1:8000**
