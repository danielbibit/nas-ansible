from typing import Literal

from grafana_foundation_sdk.cog.encoder import JSONEncoder
from grafana_foundation_sdk.builders import (
    alerting,
    prometheus,
    expr
)
from grafana_foundation_sdk.models import alerting as alerting_model

PROMETHEUS_UID = 'Ao-uhfy7k'
FOLDER = 'NAS'
EVALUATION_INTERVAL = '1m'

# Keys accepted by the alerting file provisioning format; the SDK also emits
# API-only keys (orgID, folderUID, ruleGroup) that are set at group level instead
PROVISIONING_RULE_KEYS = {
    'uid', 'title', 'condition', 'data', 'noDataState', 'execErrState',
    'for', 'annotations', 'labels', 'isPaused', 'notification_settings'
}


def prometheus_rule(
    uid: str,
    title: str,
    query: str,
    operator: Literal['gt', 'lt'],
    threshold: float,
    for_: str,
    severity: Literal['warning', 'critical'],
    summary: str,
    description: str,
    no_data_state: Literal['Alerting', 'NoData', 'OK'] = 'OK',
) -> alerting.Rule:
    """Rule with an instant Prometheus query (A) and a threshold (B) on every returned series"""
    return (
        alerting.Rule(title)
        .uid(uid)
        .condition('B')
        .for_val(for_)
        .no_data_state(no_data_state)
        .exec_err_state('Error')
        .labels({'severity': severity})
        .annotations({'summary': summary, 'description': description})
        .with_query(
            alerting.Query('A')
            .datasource_uid(PROMETHEUS_UID)
            .relative_time_range(alerting_model.RelativeTimeRange(from_val=600, to=0))
            .model(
                prometheus.Dataquery()
                .expr(query)
                .instant()
                .ref_id('A')
            )
        )
        .with_query(
            alerting.Query('B')
            .datasource_uid('__expr__')
            .model(
                expr.TypeThreshold()
                .expression('A')
                .ref_id('B')
                .conditions([
                    expr.ExprTypeThresholdConditions().evaluator(
                        expr.ExprTypeThresholdConditionsEvaluator()
                        .type(operator)
                        .params([threshold])
                    )
                ])
            )
        )
    )


def encode_group(name: str, rules: list[alerting.Rule]) -> str:
    """Encode rules as a Grafana alerting provisioning file"""
    encoder = JSONEncoder(sort_keys=True, indent=2)
    built_rules = []
    for rule in rules:
        rule_json = encoder.default(rule.build())
        built_rules.append({k: v for k, v in rule_json.items() if k in PROVISIONING_RULE_KEYS})

    return encoder.encode({
        'apiVersion': 1,
        'groups': [{
            'orgId': 1,
            'name': name,
            'folder': FOLDER,
            'interval': EVALUATION_INTERVAL,
            'rules': built_rules,
        }]
    })
