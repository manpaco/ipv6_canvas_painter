#!/usr/bin/env bash

BASE_URI="https://canvas.openbased.org/"

# Show the URIS to the canvas where the images are being painted
for link in *; do
    if [[ -h "$link" ]]; then
        file="$(readlink -f "$link")"
        echo "${BASE_URI}#1.00,$(cat "${file}.xy") --> $file"
    fi
done
