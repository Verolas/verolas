"""Sync the in-process template registry into Postgres at startup.

Calls `app.upsert_global_workflow_template` (a SECURITY DEFINER function
defined in the workflow_engine migration) for each registered template.
The function compares the definition hash against the latest active
version and mints a new version only when the hash changes; otherwise
it returns a 'unchanged' action and we leave the row alone.

The function bypasses FORCE ROW LEVEL SECURITY because the API role
cannot write org_id=NULL rows directly under the policy. All code
templates are Verolas-global (org_id NULL).
"""

from __future__ import annotations

import json
import logging
from typing import TypedDict

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from verolas_api.workflow.registry import registered_templates
from verolas_api.workflow.schema import TemplateSpec

logger = logging.getLogger(__name__)


class _SyncResult(TypedDict):
    template_id: str
    version_id: str
    version: int
    action: str
    slug: str


async def sync_code_templates(pool: AsyncConnectionPool) -> list[_SyncResult]:
    """Upsert every registered template into Postgres. Returns one row per template.

    Safe to call repeatedly. A no-op deploy (no template changed) returns
    an 'unchanged' action for every template and writes no new rows.
    """
    templates = registered_templates()
    results: list[_SyncResult] = []
    async with pool.connection() as conn:
        async with conn.transaction():
            for spec in templates:
                result = await _upsert(conn, spec)
                results.append(result)

    for result in results:
        if result["action"] == "unchanged":
            logger.info(
                "workflow_template_sync.unchanged",
                extra={"slug": result["slug"], "version": result["version"]},
            )
        else:
            logger.info(
                "workflow_template_sync.applied",
                extra={
                    "slug": result["slug"],
                    "version": result["version"],
                    "action": result["action"],
                },
            )
    return results


async def _upsert(conn: AsyncConnection, spec: TemplateSpec) -> _SyncResult:
    definition_payload = spec.definition.model_dump(mode="json")
    definition_hash = spec.definition.hash()
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT app.upsert_global_workflow_template("
            "%s, %s, %s, %s, %s, %s::jsonb, %s)",
            (
                spec.slug,
                spec.name,
                spec.description,
                spec.jurisdiction,
                spec.project_type,
                json.dumps(definition_payload),
                definition_hash,
            ),
        )
        row = await cur.fetchone()
    assert row is not None
    payload = row[0]
    return _SyncResult(
        template_id=str(payload["template_id"]),
        version_id=str(payload["version_id"]),
        version=int(payload["version"]),
        action=str(payload["action"]),
        slug=spec.slug,
    )
