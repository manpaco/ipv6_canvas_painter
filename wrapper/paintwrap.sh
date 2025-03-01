#!/usr/bin/env bash

PROGRAM_DIR="$(dirname "$(readlink "$0")")"
cd "$PROGRAM_DIR" || exit 1

# The tool_dir symlink should point to the directory
# containing the painter.py script
[[ -h tool_dir ]] || {
    echo "No tool_dir symlink found in $(pwd)" >&2
    exit 1
}
tool_dir="$(readlink -f tool_dir)"
if [[ ! -d "$tool_dir" ]]; then
    echo "tool_dir symlink points to non-existent directory" >&2
    exit 1
fi

if [[ ! -d to_paint ]]; then
    echo "No to_paint directory found in $(pwd)" >&2
    exit 1
fi
cd to_paint || exit 1
# Read all symlinks in the to_paint directory
unset -v files
for link in *; do
    if [[ -h "$link" ]]; then
        files+=("$(readlink -f "$link")")
    fi
done
if [[ ${#files[@]} -eq 0 ]]; then
    echo "No symlinks found in $(pwd)" >&2
    exit 1
fi

# Activate the virtual environment
cd "$tool_dir" || exit 1
if [[ ! -d venv ]]; then
    echo "Virtual environment not found in $(pwd)" >&2
    exit 1
fi
# shellcheck source=/dev/null
source venv/bin/activate

# Process all images
for image in "${files[@]}"; do
    echo "Processing $image"
    ./painter.py -c "${image}.xy" -d 0 --reverse "$image"
done
