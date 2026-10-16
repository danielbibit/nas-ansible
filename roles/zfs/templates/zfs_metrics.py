#!/usr/bin/env python3
"""Export ZFS pool, vdev, scan and dataset metrics for node_exporter's textfile collector

TODO: switch to JSON output once the host runs OpenZFS >= 2.3 (Ubuntu 24.04 ships 2.2).
`zpool status -j`, `zpool list -j` and `zfs list -j` (with `--json-int`) replace the
text parsing in collect_status(), which reads the vdev tree from indentation and the
scan line with regexes and is the fragile part of this script. The JSON scan stats
also expose start/end times, examined/issued bytes and errors directly.
Keep the metric names unchanged so the Grafana dashboard keeps working.
"""
import os
import re
import subprocess
import tempfile
import time
from collections import defaultdict

OUTPUT = '{{ zfs_textfile_directory }}/zfs.prom'
ENV = {**os.environ, 'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'}

HELP = {
    'zfs_zpool_size_bytes': 'Total size of the pool.',
    'zfs_zpool_allocated_bytes': 'Allocated space in the pool.',
    'zfs_zpool_free_bytes': 'Free space in the pool.',
    'zfs_zpool_fragmentation_ratio': 'Free space fragmentation of the pool.',
    'zfs_zpool_capacity_ratio': 'Used capacity of the pool.',
    'zfs_zpool_health': 'Pool health, 1 for the current state.',
    'zfs_zpool_data_errors': 'Number of files with permanent data errors.',
    'zfs_zpool_scan_in_progress': 'Whether a scrub or resilver is running.',
    'zfs_zpool_scan_progress_ratio': 'Progress of the running scrub or resilver.',
    'zfs_zpool_scan_last_end_timestamp_seconds': 'When the last scrub or resilver finished.',
    'zfs_zpool_scan_last_errors': 'Errors found by the last scrub or resilver.',
    'zfs_vdev_state': 'Vdev state, 1 for the current state.',
    'zfs_vdev_read_errors': 'Read errors on the vdev since the last clear.',
    'zfs_vdev_write_errors': 'Write errors on the vdev since the last clear.',
    'zfs_vdev_checksum_errors': 'Checksum errors on the vdev since the last clear.',
    'zfs_dataset_used_bytes': 'Space used by the dataset and its children.',
    'zfs_dataset_available_bytes': 'Space available to the dataset.',
    'zfs_dataset_referenced_bytes': 'Space referenced by the dataset.',
    'zfs_dataset_used_by_snapshots_bytes': 'Space used by snapshots of the dataset.',
    'zfs_dataset_compress_ratio': 'Compression ratio of the dataset.',
    'zfs_dataset_snapshots': 'Number of snapshots of the dataset.',
    'zfs_metrics_last_run_timestamp_seconds': 'When this script last ran successfully.',
}

metrics = defaultdict(list)


def add(name, labels, value):
    metrics[name].append((labels, value))


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True, env=ENV).stdout


def escape(value):
    return str(value).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def collect_pools():
    for line in run('zpool', 'list', '-Hp', '-o', 'name,size,alloc,free,frag,cap,health').splitlines():
        name, size, alloc, free, frag, cap, health = line.split('\t')
        labels = {'zpool': name}
        add('zfs_zpool_size_bytes', labels, size)
        add('zfs_zpool_allocated_bytes', labels, alloc)
        add('zfs_zpool_free_bytes', labels, free)
        if frag != '-':
            add('zfs_zpool_fragmentation_ratio', labels, int(frag) / 100)
        add('zfs_zpool_capacity_ratio', labels, int(cap) / 100)
        add('zfs_zpool_health', {**labels, 'state': health.lower()}, 1)


SCAN_DONE = re.compile(r'(scrub repaired|resilvered) .* with (\d+) errors on (.+)$')
SCAN_RUNNING = re.compile(r'(scrub|resilver) in progress since')
SCAN_PERCENT = re.compile(r'([\d.]+)% done')
DATA_ERRORS = re.compile(r'(\d+) data errors')


def parse_scan(pool, lines):
    """Parse the 'scan:' line and its continuation lines"""
    text = ' '.join(lines)
    labels = {'zpool': pool}

    running = SCAN_RUNNING.search(text)
    add('zfs_zpool_scan_in_progress', labels, 1 if running else 0)
    if running:
        percent = SCAN_PERCENT.search(text)
        if percent:
            add('zfs_zpool_scan_progress_ratio', labels, float(percent.group(1)) / 100)

    done = SCAN_DONE.search(lines[0])
    if done:
        function = 'scrub' if done.group(1) == 'scrub repaired' else 'resilver'
        # Collapse padding such as 'Oct  1' before parsing
        finished = time.mktime(time.strptime(' '.join(done.group(3).split()), '%a %b %d %H:%M:%S %Y'))
        add('zfs_zpool_scan_last_end_timestamp_seconds', {**labels, 'function': function}, int(finished))
        add('zfs_zpool_scan_last_errors', {**labels, 'function': function}, done.group(2))


def parse_config(pool, lines):
    """Parse the vdev tree, indentation is two spaces per level below the pool"""
    parents = []
    for line in lines:
        fields = line.strip().split()
        if len(fields) < 5 or fields[0] == 'NAME':
            continue
        depth = (len(line.lstrip('\t')) - len(line.lstrip('\t').lstrip(' '))) // 2
        name, state, read, write, cksum = fields[:5]
        if depth == 0:
            # Pool row, already covered by zfs_zpool_health
            parents = [name]
            continue

        parents = parents[:depth] + [name]
        labels = {
            'zpool': pool,
            'vdev': name,
            'parent': parents[-2],
        }
        add('zfs_vdev_state', {**labels, 'state': state.lower()}, 1)
        add('zfs_vdev_read_errors', labels, read)
        add('zfs_vdev_write_errors', labels, write)
        add('zfs_vdev_checksum_errors', labels, cksum)

    # Mark leaves (physical devices): rows that are nobody's parent
    parent_names = {labels['parent'] for labels, _ in metrics['zfs_vdev_state'] if labels['zpool'] == pool}
    for name in ('zfs_vdev_state', 'zfs_vdev_read_errors', 'zfs_vdev_write_errors', 'zfs_vdev_checksum_errors'):
        for labels, _ in metrics[name]:
            if labels['zpool'] == pool:
                labels['leaf'] = 'false' if labels['vdev'] in parent_names else 'true'


def collect_status():
    pool = None
    section = None
    block = defaultdict(list)

    def flush():
        if pool:
            parse_scan(pool, block['scan'] or ['none requested'])
            parse_config(pool, block['config'])
            errors = DATA_ERRORS.search(' '.join(block['errors']))
            add('zfs_zpool_data_errors', {'zpool': pool}, errors.group(1) if errors else 0)

    for line in run('zpool', 'status', '-p').splitlines():
        header = re.match(r'^\s*(pool|state|status|action|see|scan|config|errors):\s?(.*)$', line)
        if header and not line.startswith('\t'):
            key, value = header.groups()
            if key == 'pool':
                flush()
                pool, block = value.strip(), defaultdict(list)
            section = key
            if value.strip():
                block[section].append(value.strip())
        elif section and line.strip():
            block[section].append(line if section == 'config' else line.strip())
    flush()


def collect_datasets():
    snapshots = defaultdict(int)
    for line in run('zfs', 'list', '-Hp', '-t', 'snapshot', '-o', 'name').splitlines():
        snapshots[line.split('@')[0]] += 1

    output = run('zfs', 'list', '-Hp', '-t', 'filesystem,volume',
                 '-o', 'name,used,avail,refer,usedbysnapshots,compressratio')
    for line in output.splitlines():
        name, used, avail, refer, used_snap, ratio = line.split('\t')
        labels = {'zpool': name.split('/')[0], 'dataset': name}
        add('zfs_dataset_used_bytes', labels, used)
        add('zfs_dataset_available_bytes', labels, avail)
        add('zfs_dataset_referenced_bytes', labels, refer)
        add('zfs_dataset_used_by_snapshots_bytes', labels, used_snap)
        add('zfs_dataset_compress_ratio', labels, ratio.rstrip('x'))
        add('zfs_dataset_snapshots', labels, snapshots[name])


def write():
    lines = []
    for name, samples in metrics.items():
        lines.append(f'# HELP {name} {HELP[name]}')
        lines.append(f'# TYPE {name} gauge')
        for labels, value in samples:
            label_text = ','.join(f'{k}="{escape(v)}"' for k, v in labels.items())
            series = name + '{' + label_text + '}' if label_text else name
            lines.append(f'{series} {value}')

    directory = os.path.dirname(OUTPUT)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix='.zfs.prom.')
    with os.fdopen(fd, 'w') as file:
        file.write('\n'.join(lines) + '\n')
    os.chmod(tmp, 0o644)
    os.replace(tmp, OUTPUT)


if __name__ == '__main__':
    collect_pools()
    collect_status()
    collect_datasets()
    add('zfs_metrics_last_run_timestamp_seconds', {}, int(time.time()))
    write()
