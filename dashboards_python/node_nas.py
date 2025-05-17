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
from grafana_foundation_sdk.models  import (
    common,
    units,
    prometheus as prometheus_models,
    dashboard as dashboard_model
)

time_series_min_step = '1m'

builder = (
    dashboard.Dashboard("Node Stats - nas")
    .id('node_nas_1')
    .tooltip(common.TooltipDisplayMode.SINGLE)

    .with_variable(
        dashboard.QueryVariable('host')
        .label('host')
        .query('label_values(node_boot_time_seconds, instance)')
        .refresh(dashboard_model.VariableRefresh.ON_TIME_RANGE_CHANGED)
        .sort(dashboard_model.VariableSort.ALPHABETICAL_ASC)
        .include_all(False)
    )

    .with_panel(
        stat.Panel()
        .title('Uptime')
        .with_target(
            prometheus.Dataquery()
            .expr('time() - node_boot_time_seconds{instance=~"$host"}')
        )
        .graph_mode(
            common.BigValueGraphMode.NONE
        )
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
        .title('Memory Usage')
        .with_target(
            prometheus.Dataquery()
            .expr(
                '(node_memory_MemTotal_bytes{instance=~"$host"} - node_memory_MemAvailable_bytes{instance=~"$host"}) ' \
                '/ node_memory_MemTotal_bytes{instance=~"$host"} * 100'
            )
        )
        .thresholds(
            dashboard.ThresholdsConfig().mode(gauge.dashboard.ThresholdsMode.PERCENTAGE).steps([
                dashboard_model.Threshold(70, "green"),
                dashboard_model.Threshold(80, "yellow"),
                dashboard_model.Threshold(90, "red")
            ])
        )
        .unit('percent')
        .min(0.0)
        .max(100.0)
        .height(4)
        .span(4)
    )

    .with_panel(
        table.Panel()
        .title('System Load')
        .with_target(
            prometheus.Dataquery()
            .expr('node_load1{instance=~"$host"}')
            .format(prometheus_models.PromQueryFormat.TABLE)
            .instant()
        )
        .with_target(
            prometheus.Dataquery()
            .expr('node_load5{instance=~"$host"}')
            .format(prometheus_models.PromQueryFormat.TABLE)
            .instant()
        )
        .with_target(
            prometheus.Dataquery()
            .expr('node_load15{instance=~"$host"}')
            .format(prometheus_models.PromQueryFormat.TABLE)
            .instant()
        )
        .with_transformation(
            dashboard_model.DataTransformerConfig(
                id_val='merge'
            )
        )
        .with_transformation(
            dashboard_model.DataTransformerConfig(
                id_val='calculateField',
                options={
                    'mode': 'reduceRow',
                    'include': [
                        "Value #A",
                        "Value #B",
                        "Value #C"
                    ],
                    'reducer': 'sum'
                }

            )
        )
        .with_transformation(
            dashboard_model.DataTransformerConfig(
                id_val='filterFieldsByName',
                options={
                    'include': {
                        'names': [
                            '__name__',
                            'Total',
                        ]
                    }
                }
            )
        )
        .show_header(False)
        .align(common.FieldTextAlignment.LEFT)
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('Free Disk root')
        .with_target(
            prometheus.Dataquery()
            .expr('node_filesystem_free_bytes{mountpoint="/", instance=~"$host"}')
        )
        .thresholds(
            dashboard.ThresholdsConfig().mode(gauge.dashboard.ThresholdsMode.ABSOLUTE).steps([
                dashboard_model.Threshold(0, "red"),
                dashboard_model.Threshold(10 * 1024 ** 3, "green")
            ])
        )
        .unit('bytes')
        .height(4)
        .span(4)
    )

    .with_panel(
        stat.Panel()
        .title('Temperature')
        .with_target(
            prometheus.Dataquery()
            .expr('node_hwmon_temp_celsius{instance=~"$host", sensor=~"temp1"}')
        )
        .unit(units.Celsius)
        .graph_mode(common.BigValueGraphMode.NONE)
        .height(4)
        .span(4)
    )

    .with_panel(
        timeseries.Panel()
        .title('Temperature')
        .with_target(
            prometheus.Dataquery()
            .expr('node_hwmon_temp_celsius{instance=~"$host", sensor=~"temp1"}')
        )
        .unit(units.Celsius)
        .legend(common_builder.VizLegendOptions().show_legend(False))
        .height(4)
        .span(4)
    )

    .with_panel(
        timeseries.Panel()
        .title('CPU')
        .with_target(
            prometheus.Dataquery()
            .expr(
                '''
                100 * sum(
                    rate(node_cpu_seconds_total{ mode=~"system|user", instance=~"$host" }[$__rate_interval])
                )
                /
                count(
                    node_cpu_seconds_total{ mode="user", instance=~"$host" }
                )
                '''
            )
            # .expr('100 * sum(rate(node_cpu_seconds_total{mode=~"system|user"}[$__rate_interval])) by (cpu)')
            .interval(time_series_min_step)
        )
        .unit('percent')
        .height(10)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Disk IO')
        .with_target(
            prometheus.Dataquery()
            .expr('-sum(rate(node_disk_written_bytes_total{instance=~"$host"}[$__rate_interval]))')
            .interval(time_series_min_step)
        )
        .with_target(
            prometheus.Dataquery()
            .expr('sum(rate(node_disk_read_bytes_total{instance=~"$host"}[$__rate_interval]))')
            .interval(time_series_min_step)
        )
        .unit('Bps')
        .height(10)
        .span(12)
    )

    .with_panel(
        table.Panel()
        .title('File Systems')
        .with_target(
            prometheus.Dataquery()
            .expr(
                '''
                100 - (
                    node_filesystem_avail_bytes{
                        device != "tmpfs",
                        instance=~"$host"
                    } * 100
                ) /
                node_filesystem_size_bytes{
                    device != "tmpfs",
                    instance=~"$host"
                }
                '''
            )
            .format(prometheus_models.PromQueryFormat.TABLE)
            .instant()
        )
        .with_transformation(
            dashboard_model.DataTransformerConfig(
                id_val='filterFieldsByName',
                options={
                    'include': {
                        'names': [
                            'device',
                            'fstype',
                            'mountpoint',
                            'Value'
                        ]
                    }
                }
            )
        )
        .unit('percent')
        .height(10)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Network Usage')
        .with_target(
            prometheus.Dataquery()
            .expr('rate(node_network_transmit_bytes_total{instance=~"$host"}[$__rate_interval])')
            .interval(time_series_min_step)
            .legend_format('{{device}}')
        )
        .with_target(
            prometheus.Dataquery()
            .expr('-rate(node_network_receive_bytes_total{instance=~"$host"}[$__rate_interval])')
            .interval(time_series_min_step)
            .legend_format('{{device}}')
        )
        .unit('Bps')
        .height(10)
        .span(12)
    )
)

if __name__ == '__main__':
    print(JSONEncoder(sort_keys=True, indent=2).encode(builder.build()))
