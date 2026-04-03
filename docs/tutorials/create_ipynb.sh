#!/bin/bash

# Exit on error
set -e

# Check if a filename was provided as an argument
if [ $# -eq 1 ]; then
    # Convert only the specified file
    py_file="$1"
    if [ -f "$py_file" ] && [[ "$py_file" == *.py ]]; then
        echo "Converting $py_file to notebook..."
        jupytext --to notebook "$py_file"
    else
        echo "Error: '$py_file' is not a valid .py file"
        exit 1
    fi
else
    # Convert all .py files in the current directory
    for py_file in *.py; do
        if [ -f "$py_file" ]; then
            echo "Converting $py_file to notebook..."
            jupytext --to notebook "$py_file"
        fi
    done
fi
