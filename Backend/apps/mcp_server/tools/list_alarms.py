"""list_alarms — real Alarm history for the scoped machine (Troubleshooting Agent)."""

from apps.machines.models import Alarm
from apps.mcp_server.schemas.troubleshooting import AlarmRecord, ListAlarmsInput, ListAlarmsOutput
from apps.mcp_server.scoping import get_owned_machine

_ACTIVE_STATUSES = ('Open', 'Acknowledged')


def list_alarms(params: ListAlarmsInput) -> ListAlarmsOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    alarms = Alarm.objects.filter(machine=machine)
    if params.active_only:
        alarms = alarms.filter(alarm_status__in=_ACTIVE_STATUSES)
    alarms = alarms.order_by('-timestamp')[: params.limit]
    return ListAlarmsOutput(
        alarms=[
            AlarmRecord(
                alarm_id=alarm.alarm_id,
                timestamp=alarm.timestamp,
                alarm_code=alarm.alarm_code,
                severity=alarm.severity,
                alarm_status=alarm.alarm_status,
            )
            for alarm in alarms
        ]
    )
