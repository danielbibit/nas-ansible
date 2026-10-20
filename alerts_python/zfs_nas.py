from _common import prometheus_rule, encode_group

POOL_CAPACITY = '100 * zfs_zpool_allocated_bytes / zfs_zpool_size_bytes'

# Free % of datasets limited by a quota. A dataset without a quota can use all the pool's free space,
# so only datasets with less available than the pool's root dataset are kept.
ROOT_AVAILABLE = (
    'max by (instance, zpool) (zfs_dataset_available_bytes'
    ' and on(instance, dataset) label_replace(zfs_zpool_size_bytes, "dataset", "$1", "zpool", "(.*)"))'
)
QUOTA_FREE = (
    '100 * zfs_dataset_available_bytes / (zfs_dataset_used_bytes + zfs_dataset_available_bytes)'
    f' and (zfs_dataset_available_bytes < on(instance, zpool) group_left() {ROOT_AVAILABLE})'
)

rules = [
    prometheus_rule(
        uid='zfs_pool_capacity_high',
        title='ZFS pool filling up',
        query=POOL_CAPACITY,
        operator='gt',
        threshold=90,
        for_='10m',
        severity='warning',
        summary='Pool {{ $labels.zpool }} on {{ $labels.instance }} is above 90% full',
        description='Pool is {{ printf "%.1f" $values.A.Value }}% full, ZFS gets slower and fragments faster as it fills.',
    ),

    prometheus_rule(
        uid='zfs_pool_capacity_critical',
        title='ZFS pool almost full',
        query=POOL_CAPACITY,
        operator='gt',
        threshold=95,
        for_='5m',
        severity='critical',
        summary='Pool {{ $labels.zpool }} on {{ $labels.instance }} is above 95% full',
        description='Pool is {{ printf "%.1f" $values.A.Value }}% full, free up space before writes start failing.',
    ),

    prometheus_rule(
        uid='zfs_quota_low',
        title='ZFS dataset quota filling up',
        query=QUOTA_FREE,
        operator='lt',
        threshold=10,
        for_='10m',
        severity='warning',
        summary='{{ $labels.dataset }} on {{ $labels.instance }} has less than 10% of its quota free',
        description='Only {{ printf "%.1f" $values.A.Value }}% of the quota of {{ $labels.dataset }} is free.',
    ),

    prometheus_rule(
        uid='zfs_quota_critical',
        title='ZFS dataset quota almost full',
        query=QUOTA_FREE,
        operator='lt',
        threshold=5,
        for_='5m',
        severity='critical',
        summary='{{ $labels.dataset }} on {{ $labels.instance }} has less than 5% of its quota free',
        description='Only {{ printf "%.1f" $values.A.Value }}% of the quota of {{ $labels.dataset }} is free.',
    ),

    prometheus_rule(
        uid='zfs_scrub_overdue',
        title='ZFS scrub overdue',
        # Ubuntu scrubs every second Sunday, so up to 35 days apart, and skips pools that are not ONLINE
        query='(time() - zfs_zpool_scan_last_end_timestamp_seconds{function="scrub"}) / 86400',
        operator='gt',
        threshold=40,
        for_='1h',
        severity='warning',
        summary='Pool {{ $labels.zpool }} on {{ $labels.instance }} was not scrubbed in over 40 days',
        description='Last scrub finished {{ printf "%.0f" $values.A.Value }} days ago. '
                    'The monthly scrub skips degraded pools, run zpool scrub {{ $labels.zpool }} by hand.',
    ),
]

if __name__ == '__main__':
    print(encode_group('ZFS', rules))
