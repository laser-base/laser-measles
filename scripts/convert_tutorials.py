#!/usr/bin/env python3
"""Convert .py tutorial files to .ipynb notebooks using jupytext."""

import glob
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TUTORIALS_DIR = REPO_ROOT / "docs" / "tutorials"


def convert_tutorials():
    """Convert all tut_*.py files in docs/tutorials/ to notebooks."""
    os.chdir(TUTORIALS_DIR)

    py_files = glob.glob("tut_*.py")

    if not py_files:
        print(f"No tutorial files found matching pattern 'tut_*.py' under {TUTORIALS_DIR}")
        return

    for py_file in py_files:
        print(f"Converting {py_file} to notebook...")
        try:
            subprocess.run([sys.executable, "-m", "jupytext", "--to", "notebook", py_file], check=True)
            print(f"Successfully converted {py_file}")
        except subprocess.CalledProcessError as e:
            print(f"Error converting {py_file}: {e}")
            sys.exit(1)

    print(f"Successfully converted {len(py_files)} tutorial files to notebooks")


if __name__ == "__main__":
    convert_tutorials()
