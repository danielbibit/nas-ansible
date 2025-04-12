from grafana_foundation_sdk.cog.encoder import JSONEncoder
from grafana_foundation_sdk.builders import (
    dashboard,
    prometheus,
    timeseries,
    table,
    common as common_builder
)
from grafana_foundation_sdk.models  import (
    common,
    prometheus as prometheus_model,
    dashboard as dashboard_model
)

def set_legend_on_side():
    return common_builder.VizLegendOptions().placement(common.LegendPlacement.RIGHT).show_legend(True)

time_series_min_step: str = '5m'

builder = (
    dashboard.Dashboard("Containers - nas")
    .id('nas_containers_test')
    .tooltip(common.TooltipDisplayMode.SINGLE)

    .with_panel(
        timeseries.Panel()
        .title('Memory Usage')
        .with_target(
            prometheus.Dataquery()
            # Use sum to sum containers with same name after restart
            # name=~".+" to exclude the All sum
            .expr('sum(container_memory_usage_bytes{name=~".+"}) by (name)')
            .interval(time_series_min_step)
            .legend_format('{{name}}')
        )
        .legend(set_legend_on_side())
        .fill_opacity(10.0)
        .unit('bytes')
        .height(8)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('CPU Usage')
        .with_target(
            prometheus.Dataquery()
            .expr('100 * sum(rate(container_cpu_system_seconds_total{name=~".+"}[$__rate_interval])) by (name)')
            .interval(time_series_min_step)
            .legend_format('{{name}}')
        )
        .legend(set_legend_on_side())
        .unit('%')
        .draw_style(common.GraphDrawStyle.LINE)
        .line_interpolation(common.LineInterpolation.LINEAR)
        .height(8)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Network Usage - Download')
        .with_target(
            prometheus.Dataquery()
            .expr('sum(rate(container_network_receive_bytes_total{name=~".+"}[$__rate_interval])) by (name)')
            .interval(time_series_min_step)
            .legend_format('{{name}}')
        )
        .legend(set_legend_on_side())
        .unit('Bps')
        .draw_style(common.GraphDrawStyle.LINE)
        .line_interpolation(common.LineInterpolation.LINEAR)
        .height(8)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Network Usage - Upload')
        .with_target(
            prometheus.Dataquery()
            .expr('sum(rate(container_network_transmit_bytes_total{name=~".+"}[$__rate_interval])) by (name)')
            .interval(time_series_min_step)
            .legend_format('{{name}}')
        )
        .legend(set_legend_on_side())
        .unit('Bps')
        .draw_style(common.GraphDrawStyle.LINE)
        .line_interpolation(common.LineInterpolation.LINEAR)
        .height(8)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Disk Usage - Read')
        .with_target(
            prometheus.Dataquery()
            .expr('sum(rate(container_fs_reads_bytes_total{name=~".+"}[5m])) by (name)')
            .interval(time_series_min_step)
            .legend_format('{{name}}')
        )
        .legend(set_legend_on_side())
        .unit('Bps')
        .draw_style(common.GraphDrawStyle.LINE)
        .line_interpolation(common.LineInterpolation.LINEAR)
        .height(8)
        .span(12)
    )

    .with_panel(
        timeseries.Panel()
        .title('Disk Usage - Write')
        .with_target(
            prometheus.Dataquery()
            .expr('sum(rate(container_fs_writes_bytes_total{name=~".+"}[$__rate_interval])) by (name)')
            .interval(time_series_min_step)
            .legend_format('{{name}}')
        )
        .legend(set_legend_on_side())
        .unit('Bps')
        .draw_style(common.GraphDrawStyle.LINE)
        .line_interpolation(common.LineInterpolation.LINEAR)
        .height(8)
        .span(12)
    )

    .with_panel(
        table.Panel()
        .with_target(
            prometheus.Dataquery()
            .expr('(time() - container_start_time_seconds{name=~".+"})')
            .interval(time_series_min_step)
            .legend_format('{{name}}')
            .format(prometheus_model.PromQueryFormat.TABLE)
            .instant()
        )
        .with_transformation(
            dashboard_model.DataTransformerConfig(
                id_val='filterFieldsByName',
                options={
                    'include': {
                        'names': [
                            'container_label_com_docker_compose_project',
                            'image',
                            'name',
                            'Value'
                        ]
                    }
                }
            )
        )
        .with_transformation(
            dashboard_model.DataTransformerConfig(
                id_val='organize',
                options={
                    'renameByName': {
                        'container_label_com_docker_compose_project': 'Project',
                        'image': 'Image',
                        'name': 'Container',
                        'Value': 'Uptime'
                    }
                }
            )
        )
        .unit('dtdhms')
        .height(12)
        .span(24)
    )
)

if __name__ == '__main__':
    print(JSONEncoder(sort_keys=True, indent=2).encode(builder.build()))
