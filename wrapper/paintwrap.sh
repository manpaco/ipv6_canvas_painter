#!/usr/bin/env bash

PROGRAM_DIR="$(dirname "$(readlink "$0")")"
cd "$PROGRAM_DIR" || exit 1

# The painter_dir symlink should point to the directory
# containing the painter.py script
[[ -h painter_dir ]] || {
    echo "No painter_dir symlink found in $(pwd)" >&2
    exit 1
}
painter_dir="$(readlink -f painter_dir)"
if [[ ! -d "$painter_dir" ]]; then
    echo "painter_dir symlink points to non-existent directory" >&2
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
cd "$painter_dir" || exit 1
if [[ ! -d venv ]]; then
    echo "Virtual environment not found in $(pwd)" >&2
    exit 1
fi
# shellcheck source=/dev/null
source venv/bin/activate

# Process all images
for image in "${files[@]}"; do
    echo "Processing $image"
    ./painter.py --dry-run -c "${image}.xy" -d 0 --reverse "$image"
done
