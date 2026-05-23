"""Activity log writer.

The Postgres trigger `app.activity_log_chain` computes prev_hash,
this_hash, and seq on INSERT, so the application only supplies the
content fields. This helper exists to keep the call sites short and
the action vocabulary consistent.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from psycopg import AsyncConnection


async def record_activity(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    actor_user_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append a row to the audit chain. The trigger handles the hashing."""
    payload_json = json.dumps(payload) if payload is not None else None
    await conn.execute(
        """
        INSERT INTO activity_log (
            id, org_id, actor_user_id, action, resource_type, resource_id, payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            uuid4(),
            org_id,
            actor_user_id,
            action,
            resource_type,
            resource_id,
            payload_json,
        ),
    )
