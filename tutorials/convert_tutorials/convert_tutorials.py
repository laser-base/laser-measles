#!/usr/bin/env python3
"""Convert .py tutorial files to .ipynb notebooks using jupytext."""

import glob
import os
import subprocess
import sys


def convert_tutorials():
    """Convert all tut_*.py files to notebooks."""
    # Change to the tutorials directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Find all tutorial Python files
    py_files = glob.glob("tut_*.py")

    if not py_files:
        print("No tutorial files found matching pattern 'tut_*.py'")
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
