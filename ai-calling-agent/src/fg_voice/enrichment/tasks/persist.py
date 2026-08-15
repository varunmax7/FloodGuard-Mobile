"""Task 7 (§11): flush the accumulated enrichment back to the row.

Only fields that were *explicitly set* on the accumulator overwrite
the row (additive semantics — a task that couldn't run leaves its
field unset and the row keeps whatever it had). This is important
under retry: a partially-successful enrichment shouldn't null out
fields that a previous attempt already populated.

Also appends a `report.enriched` outbox event so any downstream
consumer (SSE fan-out, CSV re-projection, alerts) sees the updated
row. The existing dispatchers in `main.py` are wired to `report.*`,
so they pick this up automatically."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession as SqlAsyncSession

from fg_voice.enrichment.errors import PermanentEnrichmentError
from fg_voice.enrichment.models import EnrichmentContext
from fg_voice.persistence.models import Report
from fg_voice.persistence.outbox import OutboxEventType
from fg_voice.persistence.outbox import append as append_outbox

# Status transitions.
_STATUS_ENRICHED = "enriched"


async def persist(ctx: EnrichmentContext, session: SqlAsyncSession) -> None:
    """UPDATE the row + append the outbox event. Session commit is
    the caller's responsibility (the dispatcher owns the transaction
    boundary so retries are atomic)."""
    row = await session.get(Report, ctx.snapshot.report_id)
    if row is None:
        raise PermanentEnrichmentError(
            f"Report {ctx.snapshot.report_id} disappeared between assemble and persist"
        )
    result = ctx.result
    if result.location_resolved is not None:
        row.location_resolved = result.location_resolved
    if result.dedupe_group_id is not None:
        row.dedupe_group_id = result.dedupe_group_id
    if result.confidence_score is not None:
        # `confidence_score` column added in migration 2026081503.
        row.confidence_score = result.confidence_score
    if result.priority_score is not None:
        row.priority_score = result.priority_score
    row.status = _STATUS_ENRICHED
    row.enriched_at = datetime.now(UTC)

    await append_outbox(
        session,
        event_type=OutboxEventType.REPORT_ENRICHED,
        report_id=row.report_id,
        payload={
            "report_id": str(row.report_id),
            "short_ref": row.short_ref,
            "location_resolved": row.location_resolved,
            "dedupe_group_id": row.dedupe_group_id,
            "confidence_score": row.confidence_score,
            "priority_score": row.priority_score,
            "notes": list(result.notes),
        },
    )


__all__ = ["persist"]
