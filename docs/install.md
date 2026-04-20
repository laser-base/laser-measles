# Installation

At the command line:

```bash
pip install laser-measles
```

You can also install the in-development version with:

```bash
pip install git+https://github.com/InstituteforDiseaseModeling/laser-measles.git@main
```

## Optional Dependencies

The package supports several optional dependency groups that can be installed for additional functionality:

```bash
# Development dependencies (testing, linting)
pip install laser-measles[dev]

# Documentation dependencies (MkDocs, mkdocstrings)
pip install laser-measles[docs]

# Example dependencies (Jupyter, notebooks, plotting)
pip install laser-measles[examples]

# All optional dependencies
pip install laser-measles[full]
```

### Dependency Groups

**dev**: Development tools for testing and code quality

- pytest: Testing framework
- pytest-order: Ordered test execution

**docs**: Documentation building tools

- mkdocs-material: MkDocs theme with extensive functionality
- mkdocstrings-python: API reference generation from docstrings
- mkdocs-jupyter: Jupyter notebook rendering
- mkdocs-gen-files, mkdocs-literate-nav: Auto-generated API navigation

**examples**: Tools for running examples and tutorials

- jupytext: Jupyter notebook text conversion
- notebook: Jupyter notebook interface
- seaborn: Statistical data visualization
- ipykernel: Jupyter kernel support

**full**: All optional dependencies combined

- Includes all packages from dev, docs, and examples groups

## Development

You can use this github codespace for fast development:

<a href='https://codespaces.new/InstituteforDiseaseModeling/laser-measles'><img src='https://github.com/codespaces/badge.svg' alt='Open in GitHub Codespaces' style='max-width: 100%;'></a>

To run all the tests run:

```bash
tox
```

And to build the documentation run:

```bash
tox -e docs
```

Note, to combine the coverage data from all the tox environments run:

| Platform | Command |
|----------|---------|
| Windows | `set PYTEST_ADDOPTS=--cov-append` then `tox` |
| Other | `PYTEST_ADDOPTS=--cov-append tox` |

You can check that the bump versioning works by running:

```bash
uvx bump-my-version bump minor --dry-run -vv
```

**Note that actual version bumps should be run via the `publish-pypi.yml` GitHub action from the "Actions" tab of the repository (limited to repository administrators).**
