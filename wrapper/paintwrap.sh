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

if [[ ! -d images ]]; then
    echo "No images directory found in $(pwd)" >&2
    exit 1
fi
cd images || exit 1
# Read all symlinks in the images directory
unset -v files
for path in *; do
    if [[ -h "$path" ]]; then
        target="$(readlink -f "$path")"
        files+=("$target")
    fi
done
if [[ ${#files[@]} -eq 0 ]]; then
    echo "No images found in $(pwd)" >&2
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
