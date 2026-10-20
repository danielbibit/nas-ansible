from _common import prometheus_rule, encode_group


def attribute(attribute_id):
    return f'max by (instance, device) (smartctl_device_attribute{{attribute_id="{attribute_id}", attribute_value_type="raw"}})'


def grew(expr, window):
    """How much a counter grew in the window, ignores drops (pending sectors go back to zero once rewritten)"""
    return f'{expr} - min_over_time(({expr})[{window}:])'


rules = [
    prometheus_rule(
        uid='smart_failed',
        title='SMART health failed',
        query='smartctl_device_smart_status',
        operator='lt',
        threshold=1,
        for_='0m',
        severity='critical',
        summary='{{ $labels.device }} on {{ $labels.instance }} failed its SMART health check',
        description='The disk predicts its own failure. Replace it and check the pool it belongs to.',
    ),

    prometheus_rule(
        uid='smart_reallocated_growing',
        title='Reallocated sectors growing',
        query=grew(attribute(5), '1d'),
        operator='gt',
        threshold=0,
        for_='0m',
        severity='critical',
        summary='{{ $labels.device }} on {{ $labels.instance }} reallocated new sectors',
        description='{{ $values.A.Value }} sectors were remapped in the last day, the disk surface is degrading.',
    ),

    prometheus_rule(
        uid='smart_unreadable_sectors',
        title='Unreadable sectors',
        # Pending sectors wait for a rewrite, offline uncorrectable ones failed the offline scan
        query=f'max by (instance, device) ({attribute(197)} or {attribute(198)})',
        operator='gt',
        threshold=0,
        for_='0m',
        severity='warning',
        summary='{{ $labels.device }} on {{ $labels.instance }} has unreadable sectors',
        description='{{ $values.A.Value }} sectors could not be read. A ZFS scrub rewrites them from the mirror, '
                    'but a disk that grows bad sectors usually keeps growing them.',
    ),

    prometheus_rule(
        uid='smart_crc_errors',
        title='Disk interface CRC errors',
        query=grew(attribute(199), '1h'),
        operator='gt',
        threshold=0,
        for_='0m',
        severity='warning',
        summary='{{ $labels.device }} on {{ $labels.instance }} has new SATA CRC errors',
        description='{{ $values.A.Value }} CRC errors in the last hour, check the cable, backplane slot and controller port.',
    ),

    prometheus_rule(
        uid='smart_high_temperature',
        title='Disk temperature high',
        query='smartctl_device_temperature{temperature_type="current"}',
        operator='gt',
        threshold=50,
        for_='15m',
        severity='warning',
        summary='{{ $labels.device }} on {{ $labels.instance }} is above 50°C',
        description='Disk temperature is {{ $values.A.Value }}°C.',
    ),

    prometheus_rule(
        uid='smart_unreadable_disk',
        title='Disk not readable by smartctl',
        # Exit status bits 0-2 mean smartctl could not talk to the disk, higher bits describe the disk state
        query='smartctl_device_smartctl_exit_status % 8',
        operator='gt',
        threshold=0,
        for_='15m',
        severity='warning',
        summary='smartctl cannot read {{ $labels.device }} on {{ $labels.instance }}',
        description='smartctl exit status bits 0-2 are set, the disk may be missing or not responding.',
    ),

    prometheus_rule(
        uid='smart_ssd_wear',
        title='SSD wear high',
        # Samsung Wear_Leveling_Count, normalized from 100 (new) down to 0
        query='100 - smartctl_device_attribute{attribute_id="177", attribute_value_type="value"}',
        operator='gt',
        threshold=80,
        for_='0m',
        severity='warning',
        summary='{{ $labels.device }} on {{ $labels.instance }} used over 80% of its rated endurance',
        description='Wear is at {{ $values.A.Value }}%, plan a replacement.',
    ),
]

if __name__ == '__main__':
    print(encode_group('SMART', rules))
