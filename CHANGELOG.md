# Changelog

## 0.13.0 (2026-05-14)

* Version bump release

## 0.12.0 (2026-05-13)

* Add tutorials/README.md with learning-path TOC for GitHub browsing
* Standardized results output across components
* Enforce `extra='forbid'` on all component params (fixes parameter forwarding bug)
* Default component name in `add_component` for non-BaseComponent classes
* Standardize verbose flag on `model.params.verbose`
* Add manual workflow to build and upload combined mkdocs.md
* Remove remaining references to Sphinx/RTD; transition to MkDocs + GitHub Pages
* Documentation copyedits and incidence docstring fixes
* ABM snapshot save/load with SEIR continuity tests

## 0.11.2 (2026-04-20)

* Copyedit of all documentation files
* Add ABM snapshot save/load with SEIR continuity tests

## 0.11.1 (2026-04-20)

* Add markdownify to project dependencies for documentation builds

## 0.11.0 (2026-04-20)

* Bump documentation generation to Python 3.12
* Add Python 3.14 support
* Require authorization for releases and publishing

## 0.10.1 (2026-04-14)

* StateArray enhancements: add new capabilities with backward-compatible tests
* Eliminate redundant deaths calculation
* Add importation rates by patch
* Flatten public API for simpler imports
* Migrate README to Markdown
* MkDocs/HTML documentation build for JENNER
* Standardize on GitHub Actions for CI
* Allow Unicode in comments and docstrings
* Documentation improvements and fixes

## 0.10.0 (2026-04-03)

* MkDocs/HTML documentation build working for JENNER
* Use autoclass for classes in autosummary template
* Replace Jupyter-generated PDFs with PNG imagery to fix RTD build

## 0.9.4 (2026-03-27)

* Add importation rates by patch

## 0.9.3 (2026-03-26)

* Flatten public API for simpler imports
* Documentation improvements from MCP testing
* Add `uv.lock` to `.gitignore`
* Update pre-commit configuration and linkcheck ignores for Codecov

## 0.9.2 (2026-03-03)

* Require RasterToolKit >= v0.4.9
* Refactor build steps in publish workflow

## 0.9.1 (2026-02-26)

* Align bump-my-version settings with laser-generic
* Documentation updates: README, installation instructions, AI tool integration

## 0.9.0 (2026-02-20)

* Rename package layout: `src/laser_measles` → `src/laser/measles` (namespace package)
* Declare support for Python 3.13
* Replace `cibuildwheel` with `python -m build` for pure-Python package
* Mark newborns as active in `VitalDynamicsProcess`
* Fix agent selection logic in `ImportationPressureProcess` to handle active agents
* Fix state counter drift and patch initialization in `ConstantPopProcess`
* Add vaccination tutorial; update MCV1 info and tutorials list
* Add regression tests for importation pressure with vital dynamics

## 0.6.3 (2025-06-10)

* Refactor `AdminShapefile` and `GADMShapefile` for improved admin level handling
* Rename `shapefile_path` → `shapefile` in `RasterPatchConfig` for consistency
* Add equal-area calculation and caching note
* Allow newer versions of `laser-core`
* Add pandoc installation in `tox.ini` for docs generation
* Target Python 3.12; use SPDX expression for license

## 0.6.2 (2025-06-10)

* Add grid support and install `rastertoolkit`
* Begin public API surface
* Add cache timestamp management
* Switch project information to reStructuredText
* Remove bundled examples; slim down package

## 0.6.1 (2025-06-09)

* Routine immunization baked into vital dynamics
* Move wheels to `dist/` directory
* Documentation: intro blurb and installation note
* Align bump-my-version search patterns

## 0.6.0 (2025-06-07)

* Biweekly model
* `cibuildwheel` / manylinux wheels for PyPI
* Updated transmission logic
* Switch to `bump-my-version`
* Clean up dependencies; add optional `dev` extras

## 0.0.1 (2024-10-18)

* First release on PyPI.
