from grafana_foundation_sdk.cog.encoder import JSONEncoder
from grafana_foundation_sdk.builders import (
    dashboard,
    prometheus,
    stat,
    gauge,
    timeseries,
    table,
    common as common_builder
)
from grafana_foundation_sdk.models import (
    common,
    units,
    prometheus as prometheus_models,
    dashboard as dashboard_model
)

time_series_min_step = '1m'

HOST = 'instance=~"$host"'
CPUS = f'scalar(count(node_cpu_seconds_total{{mode="idle", {HOST}}}))'
# ZFS ARC is reclaimable cache but the kernel counts it as used, hosts without ZFS count it as 0
ARC = f'(node_zfs_arc_size{{{HOST}}} or node_memory_MemTotal_bytes{{{HOST}}} * 0)'
APPS_MEMORY = f'(node_memory_MemTotal_bytes{{{HOST}}} - node_memory_MemAvailable_bytes{{{HOST}}} - {ARC})'
DISKS = f'{HOST}, device=~"sd.*|nvme.*|vd.*|hd.*"'
DISK_SERIAL = f'* on(instance, device) group_left(serial) node_disk_info{{{HOST}}}'
FILESYSTEMS = f'{HOST}, fstype!~"tmpfs|ramfs|overlay|squashfs|nsfs|zfs|fuse.*", device!="tmpfs"'
PHYSICAL_NICS = f'{HOST}, device!~"lo|veth.*|docker.*|br.*|virbr.*|vmbr.*|tailscale.*|tap.*|fw.*"'


def thresholds(*steps):
    return dashboard.ThresholdsConfig().mode(dashboard_model.ThresholdsMode.ABSOLUTE).steps([
        dashboard_model.Threshold(value, color) for value, color in steps
    ])


def query(expr, legend=None):
    target = prometheus.Dataquery().expr(expr).interval(time_series_min_step)
    return target.legend_format(legend) if legend else target


def instant(expr, legend=None):
    target = prometheus.Dataquery().expr(expr).instant()
    return target.legend_format(legend) if legend else target


def instant_table(expr):
    return (
        prometheus.Dataquery()
        .expr(expr)
        .format(prometheus_models.PromQueryFormat.TABLE)
        .instant()
    )


def stacked():
    return common_builder.StackingConfig().mode(common.StackingMode.NORMAL)


builder = (
    dashboard.Dashboard("Node Stats - nas")
    # Existing uid assigned by Grafana, kept so links and bookmarks keep working
    .uid('aei8y7ipetnuoc')
    .tooltip(common.TooltipDisplayMode.SINGLE)

    .with_variable(
        dashboard.QueryVariable('host')
        .label('host')
        .query('label_values(node_boot_time_seconds, instance)')
        .refresh(dashboard_model.VariableRefresh.ON_TIME_RANGE_CHANGED)
        .sort(dashboard_model.VariableSort.ALPHABETICAL_ASC)
        .include_all(False)
    )

    # === Overview ===
    .with_row(dashboard.Row('Overview'))

    .with_panel(
        stat.Panel()
        .title('Uptime')
        .with_target(instant(f'time() - node_boot_time_seconds{{{HOST}}}'))
        .graph_mode(common.BigValueGraphMode.NONE)
        .color_scheme(
            dashboard.FieldColor()
            .mode(dashboard_model.FieldColorModeId.FIXED)
            .fixed_color('green')
        )
        .unit('dtdhms')
        .height(4)
        .span(4)
    )

    .with_panel(
        gauge.Panel()
        .title('CPU Usage')
        .with_target(instant(f'100 * (1 - avg(rate(node_cpu_seconds_total{{mode="idle", {HOST}}}[5m])))'))
        .thresholds(thresholds((0, 'green'), (70, 'yellow'), (90, 'red')))
        .unit('percent')
        .min(0.0)
        .max(100.0)
        .height(4)
        .span(4)
    )

    .with_panel(
        gauge.Panel()
        .title('Memory Usage')
        .description('Memory used by applications, the ZFS ARC is excluded because it is released under pressure')
        .with_target(instant(f'100 * {APPS_MEMORY} / node_memory_MemTotal_bytes{{{HOST}}}'))
        .thresholds(thresholds((0, 'green'), (80, 'yellow'), (90, 'red')))
        .unit('percent')
        .min(0.0)
        .max(100.0)
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('Load per CPU')
        .description('Load average divided by the number of CPUs, above 1 means tasks are waiting')
        .with_target(instant(f'node_load1{{{HOST}}} / {CPUS}', '1m'))
        .with_target(instant(f'node_load5{{{HOST}}} / {CPUS}', '5m'))
        .with_target(instant(f'node_load15{{{HOST}}} / {CPUS}', '15m'))
        .thresholds(thresholds((0, 'green'), (0.7, 'yellow'), (1, 'red')))
        .decimals(2)
        .text_mode(common.BigValueTextMode.VALUE_AND_NAME)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('Root Free')
        .with_target(instant(f'node_filesystem_avail_bytes{{mountpoint="/", {HOST}}}'))
        .thresholds(thresholds((0, 'red'), (5 * 1024 ** 3, 'yellow'), (10 * 1024 ** 3, 'green')))
        .unit('bytes')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('Max Temp')
        .with_target(instant(f'max(node_hwmon_temp_celsius{{{HOST}}})'))
        .thresholds(thresholds((0, 'green'), (70, 'yellow'), (80, 'red')))
        .unit(units.Celsius)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(2)
    )

    .with_panel(
        stat.Panel()
        .title('Failed Units')
        .description('systemd units in failed state, listed in the System row')
        .with_target(instant(f'count(node_systemd_unit_state{{state="failed", {HOST}}} == 1) or vector(0)'))
        .thresholds(thresholds((0, 'green'), (1, 'red')))
        .color_mode(common.BigValueColorMode.BACKGROUND)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(2)
    )

    # === CPU ===
    .with_row(dashboard.Row('CPU'))

    .with_panel(
        timeseries.Panel()
        .title('CPU Usage by Mode')
        .description('iowait is time spent waiting on disks')
        .with_target(query(
            f'sum by (mode) (rate(node_cpu_seconds_total{{mode!="idle", {HOST}}}[$__rate_interval])) * 100 / {CPUS}',
            '{{mode}}'
        ))
        .stacking(stacked())
        .fill_opacity(30)
        .unit('percent')
        .min(0.0)
        .max(100.0)
        .height(9)
        .span(16)
    )

    .with_panel(
        timeseries.Panel()
        .title('CPU Pressure')
        .description('Share of time at least one task was waiting for a CPU')
        .with_target(query(f'rate(node_pressure_cpu_waiting_seconds_total{{{HOST}}}[$__rate_interval]) * 100', 'waiting'))
        .unit('percent')
        .min(0.0)
        .height(9)
        .span(8)
    )

    # === Memory ===
    .with_row(dashboard.Row('Memory'))

    .with_panel(
        timeseries.Panel()
        .title('Memory')
        .description('Available includes page cache that can be reclaimed')
        .with_target(query(APPS_MEMORY, 'applications'))
        .with_target(query(ARC, 'ZFS ARC'))
        .with_target(query(f'node_memory_MemAvailable_bytes{{{HOST}}}', 'available'))
        .stacking(stacked())
        .fill_opacity(30)
        .unit('bytes')
        .min(0.0)
        .height(9)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Memory Pressure')
        .description('Waiting: some tasks stalled on memory, stalled: all tasks stalled on memory')
        .with_target(query(f'rate(node_pressure_memory_waiting_seconds_total{{{HOST}}}[$__rate_interval]) * 100', 'waiting'))
        .with_target(query(f'rate(node_pressure_memory_stalled_seconds_total{{{HOST}}}[$__rate_interval]) * 100', 'stalled'))
        .unit('percent')
        .min(0.0)
        .height(9)
        .span(8)
    )

    .with_panel(
        stat.Panel()
        .title('OOM Kills')
        .description('Processes killed by the kernel for lack of memory in the selected time range')
        .with_target(instant(f'increase(node_vmstat_oom_kill{{{HOST}}}[$__range])'))
        .thresholds(thresholds((0, 'green'), (1, 'red')))
        .decimals(0)
        .color_mode(common.BigValueColorMode.BACKGROUND)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(9)
        .span(4)
    )

    # === Disks ===
    .with_row(dashboard.Row('Disks'))

    .with_panel(
        timeseries.Panel()
        .title('Disk Utilisation')
        .description('Share of time the disk was busy, a single disk stuck near 100% is a sign of trouble')
        .with_target(query(
            f'rate(node_disk_io_time_seconds_total{{{DISKS}}}[$__rate_interval]) * 100 {DISK_SERIAL}',
            '{{device}} {{serial}}'
        ))
        .unit('percent')
        .min(0.0)
        .max(100.0)
        .height(9)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Disk Throughput (read + / write -)')
        .with_target(query(
            f'rate(node_disk_read_bytes_total{{{DISKS}}}[$__rate_interval]) {DISK_SERIAL}',
            '{{device}} {{serial}} read'
        ))
        .with_target(query(
            f'-rate(node_disk_written_bytes_total{{{DISKS}}}[$__rate_interval]) {DISK_SERIAL}',
            '{{device}} {{serial}} write'
        ))
        .unit('Bps')
        .height(9)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Disk Read Latency')
        .with_target(query(
            f'(rate(node_disk_read_time_seconds_total{{{DISKS}}}[$__rate_interval]) '
            f'/ rate(node_disk_reads_completed_total{{{DISKS}}}[$__rate_interval])) {DISK_SERIAL}',
            '{{device}} {{serial}}'
        ))
        .unit('s')
        .min(0.0)
        .height(9)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Disk Write Latency')
        .with_target(query(
            f'(rate(node_disk_write_time_seconds_total{{{DISKS}}}[$__rate_interval]) '
            f'/ rate(node_disk_writes_completed_total{{{DISKS}}}[$__rate_interval])) {DISK_SERIAL}',
            '{{device}} {{serial}}'
        ))
        .unit('s')
        .min(0.0)
        .height(9)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('I/O Pressure')
        .description('Waiting: some tasks stalled on I/O, stalled: all tasks stalled on I/O')
        .with_target(query(f'rate(node_pressure_io_waiting_seconds_total{{{HOST}}}[$__rate_interval]) * 100', 'waiting'))
        .with_target(query(f'rate(node_pressure_io_stalled_seconds_total{{{HOST}}}[$__rate_interval]) * 100', 'stalled'))
        .unit('percent')
        .min(0.0)
        .height(8)
        .span(8)
    )

    .with_panel(
        table.Panel()
        .title('File Systems')
        .description('ZFS datasets are on the ZFS dashboard')
        .with_target(instant_table(f'node_filesystem_size_bytes{{{FILESYSTEMS}}}'))
        .with_target(instant_table(f'node_filesystem_avail_bytes{{{FILESYSTEMS}}}'))
        .with_target(instant_table(
            f'100 * (1 - node_filesystem_avail_bytes{{{FILESYSTEMS}}} / node_filesystem_size_bytes{{{FILESYSTEMS}}})'
        ))
        .with_transformation(dashboard_model.DataTransformerConfig(id_val='merge'))
        .with_transformation(
            dashboard_model.DataTransformerConfig(
                id_val='organize',
                options={
                    'excludeByName': {'Time': True, '__name__': True, 'instance': True, 'job': True},
                    'indexByName': {'mountpoint': 0, 'device': 1, 'fstype': 2},
                    'renameByName': {
                        'mountpoint': 'Mount',
                        'device': 'Device',
                        'fstype': 'Type',
                        'Value #A': 'Size',
                        'Value #B': 'Available',
                        'Value #C': 'Used',
                    },
                }
            )
        )
        .unit('bytes')
        .override_by_name('Used', [
            dashboard_model.DynamicConfigValue(id_val='unit', value='percent'),
            dashboard_model.DynamicConfigValue(id_val='decimals', value=1),
            dashboard_model.DynamicConfigValue(id_val='thresholds', value={
                'mode': 'absolute',
                'steps': [
                    {'color': 'green', 'value': None},
                    {'color': 'yellow', 'value': 80},
                    {'color': 'red', 'value': 90},
                ],
            }),
            dashboard_model.DynamicConfigValue(
                id_val='custom.cellOptions',
                value={'type': 'color-background', 'mode': 'basic'}
            ),
        ])
        .height(8)
        .span(10)
    )

    .with_panel(
        stat.Panel()
        .title('Root Free in 30 Days')
        .description('Linear forecast from the last 7 days, 0 or less means / fills up within 30 days')
        .with_target(instant(f'predict_linear(node_filesystem_avail_bytes{{mountpoint="/", {HOST}}}[7d], 30 * 86400)'))
        .thresholds(thresholds((0, 'red'), (5 * 1024 ** 3, 'yellow'), (10 * 1024 ** 3, 'green')))
        .unit('bytes')
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(8)
        .span(6)
    )

    # === Network ===
    .with_row(dashboard.Row('Network'))

    .with_panel(
        timeseries.Panel()
        .title('Network Usage (transmit + / receive -)')
        .with_target(query(
            f'rate(node_network_transmit_bytes_total{{{PHYSICAL_NICS}}}[$__rate_interval])',
            '{{device}} transmit'
        ))
        .with_target(query(
            f'-rate(node_network_receive_bytes_total{{{PHYSICAL_NICS}}}[$__rate_interval])',
            '{{device}} receive'
        ))
        .unit('Bps')
        .height(9)
        .span(16)
    )

    .with_panel(
        timeseries.Panel()
        .title('Network Errors and Drops')
        .with_target(query(
            f'rate(node_network_receive_errs_total{{{PHYSICAL_NICS}}}[$__rate_interval]) '
            f'+ rate(node_network_transmit_errs_total{{{PHYSICAL_NICS}}}[$__rate_interval])',
            '{{device}} errors'
        ))
        .with_target(query(
            f'rate(node_network_receive_drop_total{{{PHYSICAL_NICS}}}[$__rate_interval]) '
            f'+ rate(node_network_transmit_drop_total{{{PHYSICAL_NICS}}}[$__rate_interval])',
            '{{device}} drops'
        ))
        .unit('pps')
        .min(0.0)
        .height(9)
        .span(8)
    )

    # === System ===
    .with_row(dashboard.Row('System'))

    .with_panel(
        timeseries.Panel()
        .title('Temperature')
        .with_target(query(
            # Use the sensor label when the chip provides one, otherwise the sensor name
            f'node_hwmon_temp_celsius{{{HOST}}} '
            f'* on(instance, chip, sensor) group_left(label) node_hwmon_sensor_label{{{HOST}}} '
            f'or on(instance, chip, sensor) '
            f'label_replace(node_hwmon_temp_celsius{{{HOST}}}, "label", "$1", "sensor", "(.*)")',
            '{{chip}} {{label}}'
        ))
        .unit(units.Celsius)
        .height(8)
        .span(16)
    )

    .with_panel(
        table.Panel()
        .title('Failed Units')
        .with_target(instant_table(f'node_systemd_unit_state{{state="failed", {HOST}}} == 1'))
        .with_transformation(
            dashboard_model.DataTransformerConfig(
                id_val='filterFieldsByName',
                options={'include': {'names': ['name']}}
            )
        )
        .with_transformation(
            dashboard_model.DataTransformerConfig(
                id_val='organize',
                options={'renameByName': {'name': 'Unit'}}
            )
        )
        .no_value('None')
        .height(8)
        .span(8)
    )
)

if __name__ == '__main__':
    print(JSONEncoder(sort_keys=True, indent=2).encode(builder.build()))
