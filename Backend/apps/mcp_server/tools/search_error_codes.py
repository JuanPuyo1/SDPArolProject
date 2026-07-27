"""search_error_codes — troubleshooting knowledge stub."""

from apps.mcp_server.schemas.troubleshooting import (
    ErrorCodeHit,
    SearchErrorCodesInput,
    SearchErrorCodesOutput,
)
from apps.mcp_server.scoping import get_owned_machine


def search_error_codes(params: SearchErrorCodesInput) -> SearchErrorCodesOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    hits = [
        ErrorCodeHit(
            code='STUB-000',
            title='Stub troubleshooting match',
            severity='info',
            summary=(
                f'No error-code index yet for {machine.serial_number}. '
                f'Query was {params.query!r}.'
            ),
            recommended_actions=[
                'Confirm the alarm code on the HMI.',
                'Call search_manual with the same symptom for procedure text.',
            ],
        )
    ][: params.top_k]
    return SearchErrorCodesOutput(query=params.query, hits=hits)
