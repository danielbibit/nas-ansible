from grafana_foundation_sdk.cog.encoder import JSONEncoder
from grafana_foundation_sdk.builders import (
    dashboard,
    prometheus,
    stat,
    gauge,
    bargauge,
    timeseries,
    table,
    common as common_builder
)
from grafana_foundation_sdk.models import (
    common,
    prometheus as prometheus_models,
    dashboard as dashboard_model
)

time_series_min_step = '1m'

POOL = 'instance=~"$host", zpool=~"$pool"'
LEAF = f'{POOL}, leaf="true"'

STATE_COLORS = {
    'online': 'green',
    'degraded': 'orange',
    'faulted': 'red',
    'offline': 'red',
    'unavail': 'red',
    'removed': 'red',
    'suspended': 'red',
}


def state_mappings():
    return [dashboard_model.ValueMap(options={
        state: dashboard_model.ValueMappingResult(text=state.upper(), color=color, index=i)
        for i, (state, color) in enumerate(STATE_COLORS.items())
    })]


def instant_table(expr):
    return (
        prometheus.Dataquery()
        .expr(expr)
        .format(prometheus_models.PromQueryFormat.TABLE)
        .instant()
    )


def per_pool(expr):
    return prometheus.Dataquery().expr(expr).legend_format('{{zpool}}').instant()


def thresholds(*steps):
    return dashboard.ThresholdsConfig().mode(dashboard_model.ThresholdsMode.ABSOLUTE).steps([
        dashboard_model.Threshold(value, color) for value, color in steps
    ])


def color_background():
    return dashboard_model.DynamicConfigValue(
        id_val='custom.cellOptions',
        value={'type': 'color-background', 'mode': 'basic'}
    )


def organize(rename, exclude=('Time', '__name__', 'instance', 'job', 'leaf')):
    return dashboard_model.DataTransformerConfig(
        id_val='organize',
        options={
            'excludeByName': {name: True for name in exclude},
            'renameByName': rename,
        }
    )


builder = (
    dashboard.Dashboard('ZFS - nas')
    .uid('zfs_nas')
    .tooltip(common.TooltipDisplayMode.SINGLE)

    .with_variable(
        dashboard.QueryVariable('host')
        .label('host')
        .query('label_values(zfs_zpool_size_bytes, instance)')
        .refresh(dashboard_model.VariableRefresh.ON_TIME_RANGE_CHANGED)
        .sort(dashboard_model.VariableSort.ALPHABETICAL_ASC)
        .include_all(False)
    )

    .with_variable(
        dashboard.QueryVariable('pool')
        .label('pool')
        .query('label_values(zfs_zpool_size_bytes{instance=~"$host"}, zpool)')
        .current(dashboard_model.VariableOption(selected=True, text='All', value='$__all'))
        .refresh(dashboard_model.VariableRefresh.ON_TIME_RANGE_CHANGED)
        .sort(dashboard_model.VariableSort.ALPHABETICAL_ASC)
        .multi(True)
        .include_all(True)
    )

    # === Pools ===
    .with_row(dashboard.Row('Pools'))

    .with_panel(
        stat.Panel()
        .title('Health')
        .with_target(per_pool(
            # The script only exports the current state, so each pool has a single series
            f'max by (zpool) ('
            f'zfs_zpool_health{{{POOL}, state="online"}} * 0 '
            f'or zfs_zpool_health{{{POOL}, state="degraded"}} '
            f'or zfs_zpool_health{{{POOL}, state!~"online|degraded"}} * 2'
            f')'
        ))
        .mappings([dashboard_model.ValueMap(options={
            '0': dashboard_model.ValueMappingResult(text='ONLINE', color='green', index=0),
            '1': dashboard_model.ValueMappingResult(text='DEGRADED', color='orange', index=1),
            '2': dashboard_model.ValueMappingResult(text='FAILED', color='red', index=2),
        })])
        .text_mode(common.BigValueTextMode.VALUE_AND_NAME)
        .color_mode(common.BigValueColorMode.BACKGROUND)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(5)
        .span(4)
    )

    .with_panel(
        gauge.Panel()
        .title('Capacity')
        .with_target(per_pool(f'100 * zfs_zpool_allocated_bytes{{{POOL}}} / zfs_zpool_size_bytes{{{POOL}}}'))
        .thresholds(thresholds((0, 'green'), (80, 'yellow'), (90, 'red')))
        .unit('percent')
        .min(0.0)
        .max(100.0)
        .height(5)
        .span(5)
    )

    .with_panel(
        stat.Panel()
        .title('Usable free')
        .description('Space the datasets can still write, after the space ZFS keeps in reserve')
        .with_target(per_pool(
            f'zfs_dataset_available_bytes{{{POOL}}} '
            f'and on(instance, dataset) label_replace(zfs_zpool_size_bytes{{{POOL}}}, "dataset", "$1", "zpool", "(.*)")'
        ))
        .thresholds(thresholds((0, 'red'), (100 * 1024 ** 3, 'yellow'), (500 * 1024 ** 3, 'green')))
        .unit('bytes')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(5)
        .span(5)
    )

    .with_panel(
        stat.Panel()
        .title('Fragmentation')
        .with_target(per_pool(f'100 * zfs_zpool_fragmentation_ratio{{{POOL}}}'))
        .thresholds(thresholds((0, 'green'), (50, 'yellow'), (70, 'red')))
        .unit('percent')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(5)
        .span(5)
    )

    .with_panel(
        stat.Panel()
        .title('Data errors')
        .description('Files with permanent errors, list them with zpool status -v')
        .with_target(per_pool(f'zfs_zpool_data_errors{{{POOL}}}'))
        .thresholds(thresholds((0, 'green'), (1, 'red')))
        .color_mode(common.BigValueColorMode.BACKGROUND)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(5)
        .span(5)
    )

    .with_panel(
        stat.Panel()
        .title('Last scrub')
        .with_target(per_pool(f'time() - zfs_zpool_scan_last_end_timestamp_seconds{{{POOL}, function="scrub"}}'))
        .thresholds(thresholds((0, 'green'), (35 * 86400, 'yellow'), (45 * 86400, 'red')))
        .unit('dtdurations')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(8)
    )

    .with_panel(
        stat.Panel()
        .title('Last scrub errors')
        .with_target(per_pool(f'zfs_zpool_scan_last_errors{{{POOL}, function="scrub"}}'))
        .thresholds(thresholds((0, 'green'), (1, 'red')))
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(8)
    )

    .with_panel(
        stat.Panel()
        .title('Scrub / resilver progress')
        .with_target(per_pool(f'100 * zfs_zpool_scan_progress_ratio{{{POOL}}}'))
        .no_value('Idle')
        .unit('percent')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(8)
    )

    .with_panel(
        timeseries.Panel()
        .title('Capacity over time')
        .with_target(
            prometheus.Dataquery()
            .expr(f'100 * zfs_zpool_allocated_bytes{{{POOL}}} / zfs_zpool_size_bytes{{{POOL}}}')
            .legend_format('{{zpool}}')
            .interval(time_series_min_step)
        )
        .unit('percent')
        .max(100.0)
        .height(8)
        .span(24)
    )

    # === Disks ===
    .with_row(dashboard.Row('Disks'))

    .with_panel(
        table.Panel()
        .title('Devices')
        .description('Error counters are cumulative since the last zpool clear')
        .with_target(instant_table(
            f'zfs_vdev_read_errors{{{LEAF}}} * on(instance, zpool, vdev) group_left(state) zfs_vdev_state{{{LEAF}}}'
        ))
        .with_target(instant_table(
            f'zfs_vdev_write_errors{{{LEAF}}} * on(instance, zpool, vdev) group_left(state) zfs_vdev_state{{{LEAF}}}'
        ))
        .with_target(instant_table(
            f'zfs_vdev_checksum_errors{{{LEAF}}} * on(instance, zpool, vdev) group_left(state) zfs_vdev_state{{{LEAF}}}'
        ))
        .with_transformation(dashboard_model.DataTransformerConfig(id_val='merge'))
        .with_transformation(organize({
            'zpool': 'Pool',
            'parent': 'Vdev',
            'vdev': 'Device',
            'state': 'State',
            'Value #A': 'Read errors',
            'Value #B': 'Write errors',
            'Value #C': 'Checksum errors',
        }))
        .override_by_name('State', [
            dashboard_model.DynamicConfigValue(id_val='mappings', value=state_mappings()),
            color_background(),
        ])
        .override_by_name('Read errors', [color_background()])
        .override_by_name('Write errors', [color_background()])
        .override_by_name('Checksum errors', [color_background()])
        .thresholds(thresholds((0, 'transparent'), (1, 'red')))
        .height(10)
        .span(24)
    )

    .with_panel(
        timeseries.Panel()
        .title('Device errors over time')
        .with_target(
            prometheus.Dataquery()
            .expr(
                f'zfs_vdev_read_errors{{{LEAF}}} '
                f'+ zfs_vdev_write_errors{{{LEAF}}} '
                f'+ zfs_vdev_checksum_errors{{{LEAF}}}'
            )
            .legend_format('{{vdev}}')
            .interval(time_series_min_step)
        )
        .height(8)
        .span(24)
    )

    # === Datasets ===
    .with_row(dashboard.Row('Datasets'))

    .with_panel(
        table.Panel()
        .title('Datasets')
        .description('Used includes children and snapshots, referenced is the data of the dataset itself')
        .with_target(instant_table(f'zfs_dataset_used_bytes{{{POOL}}}'))
        .with_target(instant_table(f'zfs_dataset_referenced_bytes{{{POOL}}}'))
        .with_target(instant_table(f'zfs_dataset_available_bytes{{{POOL}}}'))
        .with_target(instant_table(f'zfs_dataset_used_by_snapshots_bytes{{{POOL}}}'))
        .with_target(instant_table(f'zfs_dataset_snapshots{{{POOL}}}'))
        .with_target(instant_table(f'zfs_dataset_compress_ratio{{{POOL}}}'))
        .with_transformation(dashboard_model.DataTransformerConfig(id_val='merge'))
        .with_transformation(organize({
            'zpool': 'Pool',
            'dataset': 'Dataset',
            'Value #A': 'Used',
            'Value #B': 'Referenced',
            'Value #C': 'Available',
            'Value #D': 'Snapshots size',
            'Value #E': 'Snapshots',
            'Value #F': 'Compression',
        }))
        .unit('bytes')
        .override_by_name('Snapshots', [dashboard_model.DynamicConfigValue(id_val='unit', value='none')])
        .override_by_name('Compression', [
            dashboard_model.DynamicConfigValue(id_val='unit', value='suffix:x'),
            dashboard_model.DynamicConfigValue(id_val='decimals', value=2),
        ])
        .sort_by([common_builder.TableSortByFieldState().display_name('Used').desc(True)])
        .height(10)
        .span(14)
    )

    .with_panel(
        bargauge.Panel()
        .title('Data by dataset')
        .with_target(
            prometheus.Dataquery()
            .expr(f'zfs_dataset_referenced_bytes{{{POOL}}} > 1024 * 1024')
            .legend_format('{{dataset}}')
            .instant()
        )
        .orientation(common.VizOrientation.HORIZONTAL)
        .display_mode(common.BarGaugeDisplayMode.BASIC)
        .unit('bytes')
        .height(10)
        .span(10)
    )

    .with_panel(
        timeseries.Panel()
        .title('Dataset size over time')
        .with_target(
            prometheus.Dataquery()
            .expr(f'zfs_dataset_referenced_bytes{{{POOL}}} > 1024 * 1024')
            .legend_format('{{dataset}}')
            .interval(time_series_min_step)
        )
        .unit('bytes')
        .height(8)
        .span(24)
    )

    # === I/O ===
    .with_row(dashboard.Row('I/O'))

    .with_panel(
        timeseries.Panel()
        .title('Dataset throughput (read + / write -)')
        .with_target(
            prometheus.Dataquery()
            .expr(f'rate(node_zfs_zpool_dataset_nread{{{POOL}}}[$__rate_interval])')
            .legend_format('{{dataset}} read')
            .interval(time_series_min_step)
        )
        .with_target(
            prometheus.Dataquery()
            .expr(f'-rate(node_zfs_zpool_dataset_nwritten{{{POOL}}}[$__rate_interval])')
            .legend_format('{{dataset}} write')
            .interval(time_series_min_step)
        )
        .unit('Bps')
        .height(10)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Dataset operations (read + / write -)')
        .with_target(
            prometheus.Dataquery()
            .expr(f'rate(node_zfs_zpool_dataset_reads{{{POOL}}}[$__rate_interval])')
            .legend_format('{{dataset}} read')
            .interval(time_series_min_step)
        )
        .with_target(
            prometheus.Dataquery()
            .expr(f'-rate(node_zfs_zpool_dataset_writes{{{POOL}}}[$__rate_interval])')
            .legend_format('{{dataset}} write')
            .interval(time_series_min_step)
        )
        .unit('iops')
        .height(10)
        .span(12)
    )

    # === ARC ===
    .with_row(dashboard.Row('ARC'))

    .with_panel(
        stat.Panel()
        .title('ARC size')
        .with_target(prometheus.Dataquery().expr('node_zfs_arc_size{instance=~"$host"}'))
        .unit('bytes')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(6)
    )

    .with_panel(
        stat.Panel()
        .title('ARC max')
        .with_target(prometheus.Dataquery().expr('node_zfs_arc_c_max{instance=~"$host"}'))
        .unit('bytes')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(6)
    )

    .with_panel(
        stat.Panel()
        .title('Hit ratio')
        .with_target(
            prometheus.Dataquery()
            .expr(
                '''
                100 * increase(node_zfs_arc_hits{instance=~"$host"}[$__range])
                / (
                    increase(node_zfs_arc_hits{instance=~"$host"}[$__range])
                    + increase(node_zfs_arc_misses{instance=~"$host"}[$__range])
                )
                '''
            )
            .instant()
        )
        .thresholds(thresholds((0, 'red'), (80, 'yellow'), (90, 'green')))
        .unit('percent')
        .decimals(1)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(6)
    )

    .with_panel(
        stat.Panel()
        .title('L2ARC size')
        .with_target(prometheus.Dataquery().expr('node_zfs_arc_l2_size{instance=~"$host"}'))
        .unit('bytes')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(6)
    )

    .with_panel(
        timeseries.Panel()
        .title('ARC size')
        .with_target(
            prometheus.Dataquery()
            .expr('node_zfs_arc_size{instance=~"$host"}')
            .legend_format('size')
            .interval(time_series_min_step)
        )
        .with_target(
            prometheus.Dataquery()
            .expr('node_zfs_arc_c{instance=~"$host"}')
            .legend_format('target')
            .interval(time_series_min_step)
        )
        .with_target(
            prometheus.Dataquery()
            .expr('node_zfs_arc_c_max{instance=~"$host"}')
            .legend_format('max')
            .interval(time_series_min_step)
        )
        .unit('bytes')
        .height(8)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('ARC hit ratio')
        .with_target(
            prometheus.Dataquery()
            .expr(
                '''
                100 * rate(node_zfs_arc_hits{instance=~"$host"}[$__rate_interval])
                / (
                    rate(node_zfs_arc_hits{instance=~"$host"}[$__rate_interval])
                    + rate(node_zfs_arc_misses{instance=~"$host"}[$__rate_interval])
                )
                '''
            )
            .legend_format('hit ratio')
            .interval(time_series_min_step)
        )
        .unit('percent')
        .max(100.0)
        .height(8)
        .span(12)
    )
)

if __name__ == '__main__':
    print(JSONEncoder(sort_keys=True, indent=2).encode(builder.build()))
