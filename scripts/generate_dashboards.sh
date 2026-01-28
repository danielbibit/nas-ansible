#!/bin/sh
set -e

for script in $(pwd)/dashboards_python/*.py; do
    filename=$(basename "$script" .py)
    output_file="$(pwd)/roles/grafana/files/dashboards/${filename}.json"
    python "$script" > "$output_file"
done
