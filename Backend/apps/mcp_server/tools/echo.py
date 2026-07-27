"""echo — debug / connectivity smoke test."""

from apps.mcp_server.schemas.echo import EchoInput, EchoOutput


def echo(params: EchoInput) -> EchoOutput:
    return EchoOutput(
        echo=params.message,
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
