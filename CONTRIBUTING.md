# Contributing

Contributions to laser-measles are welcome! This guide explains how to set up a development environment, run tests, and submit changes.

## Development setup

1. Clone the repository:

    ```bash
    git clone https://github.com/laser-base/laser-measles.git
    cd laser-measles
    ```

2. Install in development mode (recommended: use [uv](https://docs.astral.sh/uv/) for faster package management):

    ```bash
    # Using uv (recommended)
    uv pip install -e ".[dev]"

    # Alternative: using pip
    pip install -e ".[dev]"
    ```

3. For the full development environment including docs and examples:

    ```bash
    uv pip install -e ".[full]"
    ```

## Running tests

Run the full test suite with tox:

```bash
tox
```

To combine coverage data from all tox environments:

| Platform | Command |
|----------|---------|
| Windows  | `set PYTEST_ADDOPTS=--cov-append` then `tox` |
| Other    | `PYTEST_ADDOPTS=--cov-append tox` |

## Building documentation

Build and preview the documentation locally:

```bash
tox -e docs
```

The documentation is built with [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) and uses [mkdocstrings](https://mkdocstrings.github.io/) for API reference generation.

## Code style

- Follow [PEP 8](https://peps.python.org/pep-0008/) conventions
- Use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for all public classes, methods, and functions
- Pre-commit hooks are configured in `.pre-commit-config.yaml` — install them with `pre-commit install`

## Submitting changes

1. Create a feature branch from `main`
2. Make your changes with clear, descriptive commit messages
3. Ensure all tests pass (`tox`)
4. Submit a pull request against `main`

## Reporting issues

Bug reports and feature requests can be filed on the [GitHub issue tracker](https://github.com/laser-base/laser-measles/issues).

## Version bumping

Version bumps are managed via the `publish-pypi.yml` GitHub Action (limited to repository administrators). To verify that bump versioning works locally:

```bash
uvx bump-my-version bump minor --dry-run -vv
```
