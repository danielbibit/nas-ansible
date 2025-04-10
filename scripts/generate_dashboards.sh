#!/bin/sh
set -e

for script in /workspaces/nas-ansible/dashboards_python/*.py; do
    filename=$(basename "$script" .py)
    output_file="/workspaces/nas-ansible/roles/grafana/files/dashboards/${filename}.json"
    python "$script" > "$output_file"
done
