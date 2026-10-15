#!/bin/sh
set -e

mkdir -p "$(pwd)/roles/grafana/files/alerting"

for script in $(pwd)/alerts_python/*.py; do
    filename=$(basename "$script" .py)
    case "$filename" in _*) continue ;; esac
    output_file="$(pwd)/roles/grafana/files/alerting/${filename}.json"
    python "$script" > "$output_file"
done
