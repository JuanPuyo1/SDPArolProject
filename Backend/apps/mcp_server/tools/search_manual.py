"""search_manual — RAG stub for Manuals Agent."""

from apps.mcp_server.schemas.manual import ManualHit, SearchManualInput, SearchManualOutput
from apps.mcp_server.scoping import get_owned_machine


def search_manual(params: SearchManualInput) -> SearchManualOutput:
    machine = get_owned_machine(
        customer_id=params.customer_id,
        machine_serial=params.machine_serial,
    )
    # Stub hit so orchestrators can exercise the contract before rag_engine lands.
    hits = [
        ManualHit(
            title=f'{machine.model} Use and Maintenance Manual',
            section='Stub result',
            excerpt=(
                f'No vector index yet. Query was {params.query!r} for serial '
                f'{machine.serial_number}. Wire rag_engine to return real passages.'
            ),
            page=None,
            score=0.0,
            source=machine.manual_url or None,
        )
    ][: params.top_k]
    return SearchManualOutput(query=params.query, hits=hits)
