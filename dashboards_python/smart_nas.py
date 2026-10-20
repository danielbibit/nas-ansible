from grafana_foundation_sdk.cog.encoder import JSONEncoder
from grafana_foundation_sdk.builders import (
    dashboard,
    prometheus,
    stat,
    timeseries,
    table,
    common as common_builder
)
from grafana_foundation_sdk.models import (
    common,
    prometheus as prometheus_models,
    dashboard as dashboard_model
)

time_series_min_step = '5m'

DEV = 'instance=~"$host", device=~"$disk"'

YEAR = 365.25 * 86400


def attribute(attribute_id, value_type='raw'):
    return (
        f'smartctl_device_attribute{{{DEV}, attribute_id="{attribute_id}", attribute_value_type="{value_type}"}}'
    )


def per_disk(expr):
    """One row per disk, so the table merge joins every query on instance and device"""
    return f'max by (instance, device) ({expr})'


def zfs_by_disk(metric):
    """ZFS names leaf vdevs by their by-id name, which is the exporter's device label"""
    return f'label_replace({metric}{{instance=~"$host", leaf="true"}}, "device", "$1", "vdev", "(.*)")'


def attribute_column(value_type):
    """Drop the labels that differ between value types, so the table merge joins them into one row"""
    return (
        f'max without (attribute_value_type, attribute_flags_long) '
        f'(smartctl_device_attribute{{{DEV}, attribute_value_type="{value_type}"}})'
    )


def instant_table(expr):
    return (
        prometheus.Dataquery()
        .expr(expr)
        .format(prometheus_models.PromQueryFormat.TABLE)
        .instant()
    )


def per_device(expr):
    return prometheus.Dataquery().expr(expr).legend_format('{{device}}').interval(time_series_min_step)


def thresholds(*steps):
    return dashboard.ThresholdsConfig().mode(dashboard_model.ThresholdsMode.ABSOLUTE).steps([
        dashboard_model.Threshold(value, color) for value, color in steps
    ])


def color_background():
    return dashboard_model.DynamicConfigValue(
        id_val='custom.cellOptions',
        value={'type': 'color-background', 'mode': 'basic'}
    )


def column(*steps, unit=None):
    values = [
        dashboard_model.DynamicConfigValue(id_val='thresholds', value=thresholds(*steps).build()),
        color_background(),
    ]
    if unit:
        values.append(dashboard_model.DynamicConfigValue(id_val='unit', value=unit))
    return values


def organize(rename, exclude=('Time', '__name__', 'instance', 'job')):
    return dashboard_model.DataTransformerConfig(
        id_val='organize',
        options={
            'excludeByName': {name: True for name in exclude},
            'renameByName': rename,
            'indexByName': {name: i for i, name in enumerate(rename)},
        }
    )


ERRORS = ((0, 'transparent'), (1, 'red'))

# Model and serial come from the info metric, pool and vdev from the ZFS exporter.
# Disks outside ZFS (boot SSD) are added back by the `or on(...)` branch.
DISK_INFO = (
    f'(smartctl_device_power_on_seconds{{{DEV}}}'
    f' * on(instance, device) group_left(model_name, serial_number) smartctl_device{{{DEV}}})'
)
DISK_INFO_WITH_POOL = (
    f'{DISK_INFO}'
    f' * on(instance, device) group_left(zpool, parent)'
    f' max by (instance, device, zpool, parent) ({zfs_by_disk("zfs_vdev_state")})'
    f' or on(instance, device) {DISK_INFO}'
)

ZFS_ERRORS = (
    f'{zfs_by_disk("zfs_vdev_read_errors")}'
    f' + {zfs_by_disk("zfs_vdev_write_errors")}'
    f' + {zfs_by_disk("zfs_vdev_checksum_errors")}'
)

# SSDs report no rotation rate
HDD = f'smartctl_device_rotation_rate{{{DEV}}}'

# Sectors the disk could not read (pending, offline uncorrectable) or had to remap (reallocated)
BAD_SECTORS = f'sum by (instance, device) ({attribute(5)} or {attribute(197)} or {attribute(198)})'

# Columns of the attributes by disk table, keyed by attribute id because vendors name some
# attributes differently (Samsung calls 199 CRC_Error_Count, WD and Seagate UDMA_CRC_Error_Count)
COMMON_IDS = {
    'Power on hours': 9,
    'Start/stop': 4,
    'Power cycles': 12,
    'Load cycles': 193,
    'Spin retry': 10,
    'Reallocated': 5,
    'Pending': 197,
    'Offline uncorrectable': 198,
    'UDMA CRC': 199,
}
COMMON_COLUMNS = ['Temp', *COMMON_IDS]
# Seagate packs extra values into the raw temperature attribute, the exporter's temperature is clean
COMMON_ATTRIBUTES = ' or '.join(
    f'label_replace(max by (device) ({expr}), "attribute", "{name}", "", "")'
    for name, expr in [
        ('Temp', f'smartctl_device_temperature{{{DEV}, temperature_type="current"}}'),
        *((name, attribute(attribute_id)) for name, attribute_id in COMMON_IDS.items()),
    ]
)

builder = (
    dashboard.Dashboard('SMART - nas')
    .uid('smart_nas')
    .tooltip(common.TooltipDisplayMode.SINGLE)

    .with_variable(
        dashboard.QueryVariable('host')
        .label('host')
        .query('label_values(smartctl_device, instance)')
        .refresh(dashboard_model.VariableRefresh.ON_TIME_RANGE_CHANGED)
        .sort(dashboard_model.VariableSort.ALPHABETICAL_ASC)
        .include_all(False)
    )

    .with_variable(
        dashboard.QueryVariable('disk')
        .label('disk')
        .query('label_values(smartctl_device{instance=~"$host"}, device)')
        .current(dashboard_model.VariableOption(selected=True, text='All', value='$__all'))
        .refresh(dashboard_model.VariableRefresh.ON_TIME_RANGE_CHANGED)
        .sort(dashboard_model.VariableSort.ALPHABETICAL_ASC)
        .multi(True)
        .include_all(True)
    )

    # === Overview ===
    .with_row(dashboard.Row('Overview'))

    .with_panel(
        stat.Panel()
        .title('Disks')
        .with_target(prometheus.Dataquery().expr(f'count(smartctl_device{{{DEV}}})').instant())
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('SMART failed')
        .description('Disks whose overall self-assessment is not PASSED')
        .with_target(
            prometheus.Dataquery().expr(f'count(smartctl_device_smart_status{{{DEV}}} == 0) or vector(0)').instant()
        )
        .thresholds(thresholds(*ERRORS))
        .color_mode(common.BigValueColorMode.BACKGROUND)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('Disks with bad sectors')
        .description('Reallocated, pending or offline uncorrectable sectors above zero')
        .with_target(prometheus.Dataquery().expr(f'count({BAD_SECTORS} > 0) or vector(0)').instant())
        .thresholds(thresholds(*ERRORS))
        .color_mode(common.BigValueColorMode.BACKGROUND)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('Unreachable disks')
        .description('smartctl failed to read the disk (exit status bits 0-2)')
        .with_target(
            prometheus.Dataquery()
            .expr(f'count(smartctl_device_smartctl_exit_status{{{DEV}}} % 8 > 0) or vector(0)')
            .instant()
        )
        .thresholds(thresholds(*ERRORS))
        .color_mode(common.BigValueColorMode.BACKGROUND)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('Hottest disk')
        .with_target(
            prometheus.Dataquery()
            .expr(f'max(smartctl_device_temperature{{{DEV}, temperature_type="current"}})')
            .instant()
        )
        .thresholds(thresholds((0, 'green'), (45, 'yellow'), (50, 'red')))
        .unit('celsius')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('Oldest disk')
        .description('Power-on time, not age since purchase')
        .with_target(prometheus.Dataquery().expr(f'max(smartctl_device_power_on_seconds{{{DEV}}})').instant())
        .thresholds(thresholds((0, 'green'), (5 * YEAR, 'yellow'), (7 * YEAR, 'red')))
        .unit('s')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(4)
    )

    .with_panel(
        table.Panel()
        .title('Disks')
        .description(
            'SMART counters are lifetime values from the disk, ZFS errors are cumulative since the last zpool clear. '
            'Pending and offline uncorrectable sectors can drop back to zero once rewritten, check the history below.'
        )
        .with_target(instant_table(DISK_INFO_WITH_POOL).ref_id('A'))
        .with_target(instant_table(per_disk(f'smartctl_device_smart_status{{{DEV}}}')).ref_id('B'))
        .with_target(
            instant_table(per_disk(f'smartctl_device_temperature{{{DEV}, temperature_type="current"}}')).ref_id('C')
        )
        .with_target(instant_table(per_disk(attribute(5))).ref_id('D'))
        .with_target(instant_table(per_disk(attribute(197))).ref_id('E'))
        .with_target(instant_table(per_disk(attribute(198))).ref_id('F'))
        .with_target(instant_table(per_disk(attribute(199))).ref_id('G'))
        .with_target(instant_table(per_disk(attribute(193))).ref_id('H'))
        .with_target(instant_table(per_disk(ZFS_ERRORS)).ref_id('I'))
        .with_transformation(dashboard_model.DataTransformerConfig(id_val='merge'))
        .with_transformation(organize({
            'device': 'Disk',
            'model_name': 'Model',
            'serial_number': 'Serial',
            'zpool': 'Pool',
            'parent': 'Vdev',
            'Value #A': 'Power on',
            'Value #B': 'SMART',
            'Value #C': 'Temp',
            'Value #D': 'Reallocated',
            'Value #E': 'Pending',
            'Value #F': 'Uncorrectable',
            'Value #G': 'CRC errors',
            'Value #H': 'Load cycles',
            'Value #I': 'ZFS errors',
        }))
        .override_by_name('Disk', [dashboard_model.DynamicConfigValue(id_val='custom.width', value=380)])
        .override_by_name('Power on', column((0, 'transparent'), (5 * YEAR, 'yellow'), (7 * YEAR, 'red'), unit='s'))
        .override_by_name('SMART', [
            dashboard_model.DynamicConfigValue(id_val='mappings', value=[dashboard_model.ValueMap(options={
                '0': dashboard_model.ValueMappingResult(text='FAILED', color='red', index=0),
                '1': dashboard_model.ValueMappingResult(text='PASSED', color='green', index=1),
            })]),
            color_background(),
        ])
        .override_by_name('Temp', column((0, 'transparent'), (45, 'yellow'), (50, 'red'), unit='celsius'))
        .override_by_name('Reallocated', column(*ERRORS))
        .override_by_name('Pending', column(*ERRORS))
        .override_by_name('Uncorrectable', column(*ERRORS))
        .override_by_name('CRC errors', column((0, 'transparent'), (1, 'yellow')))
        # Most desktop and NAS disks are rated for 300k-600k load/unload cycles
        .override_by_name('Load cycles', column((0, 'transparent'), (300000, 'yellow'), (600000, 'red')))
        .override_by_name('ZFS errors', column(*ERRORS))
        .sort_by([common_builder.TableSortByFieldState().display_name('Pool').desc(False)])
        .height(12)
        .span(24)
    )

    # === History ===
    .with_row(dashboard.Row('History'))

    .with_panel(
        timeseries.Panel()
        .title('Temperature')
        .with_target(per_device(f'smartctl_device_temperature{{{DEV}, temperature_type="current"}}'))
        .unit('celsius')
        .height(9)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Bad sectors')
        .description('Reallocated + pending + offline uncorrectable sectors')
        .with_target(per_device(BAD_SECTORS))
        .min(0.0)
        .decimals(0)
        .height(9)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Interface CRC errors')
        .description('Errors on the SATA link, usually a bad cable, backplane slot or controller port')
        .with_target(per_device(f'max by (device) ({attribute(199)})'))
        .min(0.0)
        .decimals(0)
        .height(9)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Load cycles per day')
        .description('Head parking, aggressive idle timers wear the drive out')
        .with_target(per_device(f'max by (device) (increase({attribute(193)}[1d]))'))
        .min(0.0)
        .decimals(0)
        .height(9)
        .span(12)
    )

    # === SSD ===
    .with_row(dashboard.Row('SSD'))

    .with_panel(
        stat.Panel()
        .title('SSD wear')
        .description('Samsung Wear_Leveling_Count, normalized from 100 (new) to 0 (rated endurance reached)')
        .with_target(
            prometheus.Dataquery()
            .expr(f'100 - max by (device) ({attribute(177, "value")})')
            .legend_format('{{device}}')
            .instant()
        )
        .thresholds(thresholds((0, 'green'), (70, 'yellow'), (90, 'red')))
        .unit('percent')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(5)
        .span(8)
    )

    .with_panel(
        stat.Panel()
        .title('SSD data written')
        .with_target(
            prometheus.Dataquery()
            .expr(
                f'max by (device) ({attribute(241)}'
                f' * on(instance, device) group_left() smartctl_device_block_size{{{DEV}, blocks_type="logical"}})'
                f' unless on(device) {HDD}'
            )
            .legend_format('{{device}}')
            .instant()
        )
        .unit('bytes')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(5)
        .span(8)
    )

    .with_panel(
        timeseries.Panel()
        .title('SSD writes per day')
        .with_target(per_device(
            f'max by (device) (increase({attribute(241)}[1d])'
            f' * on(instance, device) group_left() smartctl_device_block_size{{{DEV}, blocks_type="logical"}})'
            f' unless on(device) {HDD}'
        ))
        .unit('bytes')
        .min(0.0)
        .height(5)
        .span(8)
    )

    # === Attributes ===
    .with_row(dashboard.Row('Attributes'))

    .with_panel(
        table.Panel()
        .title('Attributes by disk')
        .description(
            'Raw values of the attributes WD and Seagate disks have in common, the same set as the monthly email report. '
            'Empty cells are attributes the disk does not report.'
        )
        .with_target(instant_table(COMMON_ATTRIBUTES))
        .with_transformation(dashboard_model.DataTransformerConfig(
            id_val='groupingToMatrix',
            options={'rowField': 'device', 'columnField': 'attribute', 'valueField': 'Value'},
        ))
        .with_transformation(dashboard_model.DataTransformerConfig(
            id_val='organize',
            options={
                'renameByName': {'device\\attribute': 'Disk'},
                'indexByName': {name: i for i, name in enumerate(['device\\attribute', *COMMON_COLUMNS])},
            },
        ))
        .override_by_name('Disk', [dashboard_model.DynamicConfigValue(id_val='custom.width', value=380)])
        .override_by_name('Temp', column((0, 'transparent'), (45, 'yellow'), (50, 'red'), unit='celsius'))
        .override_by_name('Spin retry', column((0, 'transparent'), (1, 'yellow')))
        .override_by_name('Reallocated', column(*ERRORS))
        .override_by_name('Pending', column(*ERRORS))
        .override_by_name('Offline uncorrectable', column(*ERRORS))
        .override_by_name('UDMA CRC', column((0, 'transparent'), (1, 'yellow')))
        .override_by_name('Load cycles', column((0, 'transparent'), (300000, 'yellow'), (600000, 'red')))
        .sort_by([common_builder.TableSortByFieldState().display_name('Disk').desc(False)])
        .height(12)
        .span(24)
    )

    .with_panel(
        table.Panel()
        .title('All attributes')
        .description(
            'Raw values of some attributes are packed by the vendor, '
            'Seagate read/seek error rates and temperature raw values are not plain counts'
        )
        .with_target(instant_table(attribute_column('value')).ref_id('A'))
        .with_target(instant_table(attribute_column('worst')).ref_id('B'))
        .with_target(instant_table(attribute_column('thresh')).ref_id('C'))
        .with_target(instant_table(attribute_column('raw')).ref_id('D'))
        .with_transformation(dashboard_model.DataTransformerConfig(id_val='merge'))
        .with_transformation(organize(
            {
                'device': 'Disk',
                'attribute_id': 'ID',
                'attribute_name': 'Attribute',
                'attribute_flags_short': 'Flags',
                'Value #A': 'Value',
                'Value #B': 'Worst',
                'Value #C': 'Threshold',
                'Value #D': 'Raw',
            },
        ))
        .override_by_name('ID', [dashboard_model.DynamicConfigValue(id_val='custom.width', value=60)])
        .override_by_name('Disk', [dashboard_model.DynamicConfigValue(id_val='custom.width', value=380)])
        .sort_by([common_builder.TableSortByFieldState().display_name('Disk').desc(False)])
        .height(16)
        .span(24)
    )
)

if __name__ == '__main__':
    print(JSONEncoder(sort_keys=True, indent=2).encode(builder.build()))
