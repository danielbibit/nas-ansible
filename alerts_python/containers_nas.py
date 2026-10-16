from _common import prometheus_rule, encode_group

rules = [
    prometheus_rule(
        uid='containers_restart_loop',
        title='Container restarting',
        query='changes(container_start_time_seconds{name!=""}[15m])',
        operator='gt',
        threshold=2,
        for_='0m',
        severity='critical',
        summary='Container {{ $labels.name }} is restarting',
        description='{{ $labels.name }} restarted {{ $values.A.Value }} times in the last 15 minutes.',
    ),
]

if __name__ == '__main__':
    print(encode_group('Containers', rules))
