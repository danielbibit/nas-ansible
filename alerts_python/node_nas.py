from _common import prometheus_rule, encode_group

FILESYSTEM_FILTER = 'fstype!~"tmpfs|ramfs|overlay|squashfs|nsfs|fuse.*"'

rules = [
    prometheus_rule(
        uid='node_target_down',
        title='Scrape target down',
        query='up',
        operator='lt',
        threshold=1,
        for_='2m',
        severity='critical',
        summary='{{ $labels.job }} on {{ $labels.instance }} is down',
        description='Prometheus could not scrape job {{ $labels.job }} for more than 2 minutes.',
        no_data_state='Alerting',
    ),

    prometheus_rule(
        uid='node_high_memory',
        title='High memory usage',
        # The ZFS ARC is released under pressure, so it is not counted as used
        query='(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes'
              ' - (node_zfs_arc_size or node_memory_MemTotal_bytes * 0))'
              ' / node_memory_MemTotal_bytes * 100',
        operator='gt',
        threshold=90,
        for_='10m',
        severity='warning',
        summary='Memory usage on {{ $labels.instance }} is above 90%',
        description='Memory used by applications, excluding the ZFS ARC, is {{ printf "%.1f" $values.A.Value }}%.',
    ),

    prometheus_rule(
        uid='node_filesystem_low',
        title='Filesystem space low',
        query=f'100 * node_filesystem_avail_bytes{{{FILESYSTEM_FILTER}}} / node_filesystem_size_bytes{{{FILESYSTEM_FILTER}}}',
        operator='lt',
        threshold=10,
        for_='10m',
        severity='warning',
        summary='{{ $labels.mountpoint }} on {{ $labels.instance }} has less than 10% free',
        description='Only {{ printf "%.1f" $values.A.Value }}% free on {{ $labels.mountpoint }} ({{ $labels.device }}).',
    ),

    prometheus_rule(
        uid='node_filesystem_critical',
        title='Filesystem almost full',
        query=f'100 * node_filesystem_avail_bytes{{{FILESYSTEM_FILTER}}} / node_filesystem_size_bytes{{{FILESYSTEM_FILTER}}}',
        operator='lt',
        threshold=5,
        for_='5m',
        severity='critical',
        summary='{{ $labels.mountpoint }} on {{ $labels.instance }} has less than 5% free',
        description='Only {{ printf "%.1f" $values.A.Value }}% free on {{ $labels.mountpoint }} ({{ $labels.device }}).',
    ),

    prometheus_rule(
        uid='node_high_temperature',
        title='High temperature',
        query='node_hwmon_temp_celsius{sensor="temp1"}',
        operator='gt',
        threshold=80,
        for_='5m',
        severity='critical',
        summary='{{ $labels.chip }} on {{ $labels.instance }} is above 80°C',
        description='Temperature is {{ printf "%.1f" $values.A.Value }}°C.',
    ),

    prometheus_rule(
        uid='node_high_load',
        title='High system load',
        query='node_load15 / on(instance) count by (instance) (node_cpu_seconds_total{mode="idle"})',
        operator='gt',
        threshold=1.5,
        for_='15m',
        severity='warning',
        summary='Load on {{ $labels.instance }} is above 1.5 per CPU',
        description='15 minute load per CPU is {{ printf "%.2f" $values.A.Value }}.',
    ),
]

if __name__ == '__main__':
    print(encode_group('Node', rules))
