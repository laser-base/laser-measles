---
name: mkdocs-setup
description: >
  Set up MkDocs documentation using the official IDM (Institute for Disease Modeling)
  template. Use this skill when the user wants to add documentation to their repository
  with MkDocs, set up MkDocs Material theme, create a docs site, configure GitHub Pages
  deployment, or mentions wanting documentation for their project. Also trigger when the
  user mentions "mkdocs-template", "mkdocs setup", "add docs to my repo", or "IDM docs".
---

# IDM MkDocs Template Setup

This skill helps users set up MkDocs documentation in their repository using the official
IDM (Institute for Disease Modeling) template from
[krosenfeld-IDM/mkdocs-template](https://github.com/krosenfeld-IDM/mkdocs-template).
It downloads the template files, handles conflicts with existing docs, configures
`mkdocs.yml` for the user's project, and sets up the build environment.

The template is the standard for IDM documentation — the included branding (logos, footer
links, analytics, copyright) is intentional for IDM projects. Non-IDM users can customize
these after setup (see Step 4).

## Overview

The template provides:
- MkDocs Material theme with light/dark mode
- GitHub Actions workflows for PR build checks and GitHub Pages deployment
- Jupyter notebook rendering support
- API reference auto-generation from Python docstrings
- Topic-type examples (tutorials, how-tos, reference, explanations)
- Glossary, search, and content-reuse features

## Step 1: Check the current project state

Before downloading anything, understand what the user already has:

1. **Check for existing `docs/` directory** — if it exists, the user needs to choose how to handle it (see Step 2).
2. **Check for existing `mkdocs.yml`** — if present, confirm whether they want to replace or merge.
3. **Check for existing `.github/workflows/`** — note any existing CI workflows to avoid conflicts.
4. **Identify the dependency management approach** — look for:
   - `pyproject.toml` (modern Python projects — add docs deps as an optional dependency group)
   - `requirements.txt` or `requirements-dev.txt` (add docs deps there)
   - Neither (create `docs/requirements.txt`)

## Step 2: Handle existing docs

If a `docs/` directory already exists, present the user with two options:

**Option A — Replace (recommended for fresh starts):**
Rename the existing folder to `docs-legacy/` and use `docs/` for MkDocs. This is the
standard MkDocs layout and works with the GitHub Actions workflows out of the box.

```bash
mv docs docs-legacy
```

Tell the user they can migrate content from `docs-legacy/` into the new MkDocs structure
at their own pace, and delete `docs-legacy/` when done.

**Option B — Side-by-side:**
Keep existing `docs/` intact and place the MkDocs documentation in `mkdocs-docs/`. This
requires updating `mkdocs.yml` to point to the new directory:

```yaml
docs_dir: mkdocs-docs
```

And updating the GitHub Actions workflows to install from `mkdocs-docs/requirements.txt`
instead of `docs/requirements.txt`.

Ask the user which option they prefer before proceeding. Default recommendation is Option A
since it requires no extra configuration.

## Step 3: Download the template

Download the template files from the repository. This pulls the three key directories:
`.github/` (CI workflows), `mkdocs.yml` (configuration), and `docs/` (content and dependencies).

```bash
curl -sL https://github.com/krosenfeld-IDM/mkdocs-template/archive/refs/heads/main.tar.gz \
  | tar xz --strip-components=1 \
    mkdocs-template-main/.github \
    mkdocs-template-main/mkdocs.yml \
    mkdocs-template-main/docs
```

If the user chose Option B in Step 2, rename the downloaded `docs/` to `mkdocs-docs/` after extraction:

```bash
curl -sL https://github.com/krosenfeld-IDM/mkdocs-template/archive/refs/heads/main.tar.gz \
  | tar xz --strip-components=1 \
    mkdocs-template-main/.github \
    mkdocs-template-main/mkdocs.yml \
    mkdocs-template-main/docs
mv docs mkdocs-docs
```

If `.github/workflows/` already has files, warn the user about potential conflicts with
`mkdocs-ghp.yml` and `mkdocs-pr.yml` before overwriting.

## Step 4: Configure mkdocs.yml

The downloaded `mkdocs.yml` has placeholder values that need updating. Ask the user for
the following, providing smart defaults based on the current repository:

### Required fields

Detect defaults from the git remote (e.g., `git remote get-url origin`) and the directory name:

| Field | Placeholder | How to detect default |
|-------|------------|----------------------|
| `site_name` | `<Package/project name>` | Directory name or repo name from git remote |
| `repo_name` | `InstituteforDiseaseModeling/project` | Parse from `git remote get-url origin` |
| `repo_url` | `https://github.com/InstituteforDiseaseModeling/project` | Parse from `git remote get-url origin` |
| `site_url` | `https://InstituteforDiseaseModeling.github.io/project` | `https://<org>.github.io/<repo>` from the git remote |

Present the detected defaults and ask the user to confirm or change them. For example:

> I detected these values from your git remote:
> - **site_name**: `my-project`
> - **repo_url**: `https://github.com/user/my-project`
> - **site_url**: `https://user.github.io/my-project`
>
> Do these look right, or would you like to change any?

### Optional customization

For **IDM projects**, the template defaults (IDM logo, footer links, Gates Foundation
copyright, Google Tag Manager analytics) are correct out of the box. Just mention that
the user can update them later if needed:

- **API reference**: Update the `api-autonav` modules list and `mkdocstrings` source path if the project has a Python package
- **Site URL**: If the project will use a custom domain (e.g., `docs.idmod.org/<project>`), update `site_url` accordingly

For **non-IDM projects**, let the user know they should replace the IDM-specific branding:

- **Logo and favicon**: Replace `images/idm-logo-transparent.png` and `images/favicon.ico` in the docs images folder
- **Color scheme**: Edit the `palette` section in `mkdocs.yml`
- **Analytics tracking ID**: Update or remove the `analytics` section in `extra`
- **Copyright and footer links**: Update the `copyright` and `extra.social` fields
- **API reference**: Update the `api-autonav` modules list and `mkdocstrings` source path if the project has a Python package

## Step 5: Set up the build environment

The template requires Python packages to build. How to install them depends on the
user's existing setup.

### Detect the dependency management approach

Check what exists in the project root and act accordingly:

**If `pyproject.toml` exists** — suggest adding a `docs` optional dependency group:

```toml
[project.optional-dependencies]
docs = [
    "mkdocs-material",
    "mkdocs-include-markdown-plugin",
    "mkdocs-autorefs",
    "mkdocs-api-autonav",
    "python-markdown-math",
    "pymdown-extensions",
    "mkdocs-jupyter",
    "mkdocstrings",
    "mkdocstrings-python",
    "mkdocs-table-reader-plugin",
]
```

Then install with:
```bash
pip install -e ".[docs]"
```

Update the GitHub Actions workflows to use `pip install ".[docs]"` instead of
`pip install -r docs/requirements.txt`. The `docs/requirements.txt` file can still
be kept for reference or as a fallback.

**If `requirements.txt` or `requirements-dev.txt` exists** — ask the user whether to
add the docs dependencies there or keep them in `docs/requirements.txt` (which the
template already provides). If they want them in an existing file, append the packages.

**If neither exists** — the template already includes `docs/requirements.txt`, so
just use that:

```bash
pip install -r docs/requirements.txt
```

### Remove the example dependency

The template's `docs/requirements.txt` includes `starsim` as an example package for
the sample Jupyter notebook. Remove it — it's only there for the template demo:

```
# Remove this line from docs/requirements.txt:
starsim # this is included only for the purpose of the example notebook
```

### Verify the build

After installing dependencies, test that the docs build:

```bash
mkdocs build
```

If successful, suggest trying the live preview:

```bash
mkdocs serve
```

This starts a local server (usually at `http://127.0.0.1:8000`) that auto-rebuilds
when files change.

## Step 6: Clean up template examples

Let the user know about template content they'll want to customize or remove:

- `docs/tutorials/intro.ipynb` — example Jupyter notebook (replace with their own)
- `docs/topic-types/` — topic-type guidance pages (useful as reference, can remove from nav)
- `docs/mkdocs.md` — the template's own README inclusion (update or remove)
- `docs/includes/glossary.md` — add project-specific terms or clear the example entries
- `docs/images/` — replace IDM logos with project-specific assets

## Quick reference

**Local development commands:**
```bash
pip install -r docs/requirements.txt   # install dependencies
mkdocs serve --watch .                 # live preview (watches source code too)
mkdocs build                           # build static site to site/
```

**GitHub Pages deployment:**
The included workflow (`.github/workflows/mkdocs-ghp.yml`) automatically deploys on
push to `main`/`master`. The PR workflow (`.github/workflows/mkdocs-pr.yml`) validates
the build on pull requests.

**Adding a new page:**
1. Create a `.md` file in `docs/`
2. Add it to the `nav:` section in `mkdocs.yml`
3. Preview with `mkdocs serve`
