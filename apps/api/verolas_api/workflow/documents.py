"""Project-scoped editable workflow documents.

A document is the project's instance of a workflow graph. It carries
its own definition JSONB so users can drag nodes around, add new ones,
remove others. Runs created from a document snapshot its definition,
keeping run history immutable against later edits.

Creation paths:
- Blank: an empty graph (no nodes, no edges, no entry keys).
- From template: the document copies the active definition of the
  named template, recording source_template_id and version for
  provenance.

The runs service `create_run_from_document` consumes a document, builds
a one-shot template version row anchored to no template (template_id
on workflow_template_versions is required, so for run-from-document we
write the snapshot to workflow_runs.definition_snapshot directly and
leave template_version_id NULL).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from verolas_api.workflow.runs import (
    TemplateNotFound,
    WorkflowError,
)
from verolas_api.workflow.schema import (
    DocumentView,
    TemplateDefinition,
)


class DocumentNotFound(WorkflowError):
    pass


class DocumentConflict(WorkflowError):
    """Name + folder collision in the same project."""


def _empty_definition() -> TemplateDefinition:
    return TemplateDefinition(nodes=[], edges=[], entry_keys=[])


async def create_blank_document(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    project_id: UUID,
    folder: str,
    name: str,
    description: str | None,
    created_by_user_id: UUID,
) -> DocumentView:
    """Create an empty document. Folder defaults to '/' if empty."""
    folder = folder or "/"
    if not folder.startswith("/"):
        folder = "/" + folder
    definition = _empty_definition()
    return await _insert(
        conn,
        org_id=org_id,
        project_id=project_id,
        folder=folder,
        name=name,
        description=description,
        source_template_id=None,
        source_template_version_id=None,
        definition=definition,
        created_by_user_id=created_by_user_id,
    )


async def create_document_from_template(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    project_id: UUID,
    folder: str,
    name: str,
    description: str | None,
    template_slug: str,
    created_by_user_id: UUID,
) -> DocumentView:
    """Fork the active version of a template into a new project document."""
    folder = folder or "/"
    if not folder.startswith("/"):
        folder = "/" + folder

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT t.id AS template_id, v.id AS version_id, v.definition
            FROM workflow_templates t
            JOIN workflow_template_versions v
              ON v.template_id = t.id AND v.is_active
            WHERE t.slug = %s
            LIMIT 1
            """,
            (template_slug,),
        )
        row = await cur.fetchone()
    if row is None:
        raise TemplateNotFound(f"template {template_slug!r} not found")

    definition = TemplateDefinition.model_validate(row["definition"])
    return await _insert(
        conn,
        org_id=org_id,
        project_id=project_id,
        folder=folder,
        name=name,
        description=description,
        source_template_id=row["template_id"],
        source_template_version_id=row["version_id"],
        definition=definition,
        created_by_user_id=created_by_user_id,
    )


async def list_documents_for_project(conn: AsyncConnection, project_id: UUID) -> list[DocumentView]:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT id, org_id, project_id, folder, name, description,
                   source_template_id, source_template_version_id,
                   definition,
                   jsonb_array_length(definition->'nodes') AS node_count,
                   created_by_user_id, created_at, updated_at
            FROM workflow_documents
            WHERE project_id = %s
            ORDER BY folder, name
            """,
            (project_id,),
        )
        rows = await cur.fetchall()
    return [_view_from_row(r) for r in rows]


async def get_document(conn: AsyncConnection, document_id: UUID) -> DocumentView:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT id, org_id, project_id, folder, name, description,
                   source_template_id, source_template_version_id,
                   definition,
                   jsonb_array_length(definition->'nodes') AS node_count,
                   created_by_user_id, created_at, updated_at
            FROM workflow_documents
            WHERE id = %s
            """,
            (document_id,),
        )
        row = await cur.fetchone()
    if row is None:
        raise DocumentNotFound(f"document {document_id} not found")
    return _view_from_row(row)


async def update_document(
    conn: AsyncConnection,
    document_id: UUID,
    *,
    name: str | None = None,
    folder: str | None = None,
    description: str | None = None,
    definition: TemplateDefinition | None = None,
) -> DocumentView:
    """Partial update. None fields are not touched."""
    updates: list[str] = []
    params: list[Any] = []
    if name is not None:
        updates.append("name = %s")
        params.append(name)
    if folder is not None:
        norm = folder if folder.startswith("/") else "/" + folder
        updates.append("folder = %s")
        params.append(norm)
    if description is not None:
        updates.append("description = %s")
        params.append(description)
    if definition is not None:
        updates.append("definition = %s::jsonb")
        params.append(json.dumps(definition.model_dump(mode="json")))

    if not updates:
        return await get_document(conn, document_id)

    params.append(document_id)
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            f"""
            UPDATE workflow_documents
            SET {", ".join(updates)}
            WHERE id = %s
            RETURNING id, org_id, project_id, folder, name, description,
                      source_template_id, source_template_version_id,
                      definition,
                      jsonb_array_length(definition->'nodes') AS node_count,
                      created_by_user_id, created_at, updated_at
            """,
            params,
        )
        row = await cur.fetchone()
    if row is None:
        raise DocumentNotFound(f"document {document_id} not found")
    return _view_from_row(row)


async def delete_document(conn: AsyncConnection, document_id: UUID) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM workflow_documents WHERE id = %s",
            (document_id,),
        )
        if cur.rowcount == 0:
            raise DocumentNotFound(f"document {document_id} not found")


async def _insert(
    conn: AsyncConnection,
    *,
    org_id: UUID,
    project_id: UUID,
    folder: str,
    name: str,
    description: str | None,
    source_template_id: UUID | None,
    source_template_version_id: UUID | None,
    definition: TemplateDefinition,
    created_by_user_id: UUID,
) -> DocumentView:
    payload = json.dumps(definition.model_dump(mode="json"))
    async with conn.cursor(row_factory=dict_row) as cur:
        try:
            await cur.execute(
                """
                INSERT INTO workflow_documents (
                    org_id, project_id, folder, name, description,
                    source_template_id, source_template_version_id,
                    definition, created_by_user_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id, org_id, project_id, folder, name, description,
                          source_template_id, source_template_version_id,
                          definition,
                          jsonb_array_length(definition->'nodes') AS node_count,
                          created_by_user_id, created_at, updated_at
                """,
                (
                    org_id,
                    project_id,
                    folder,
                    name,
                    description,
                    source_template_id,
                    source_template_version_id,
                    payload,
                    created_by_user_id,
                ),
            )
        except Exception as exc:
            # Unique violation on (project_id, folder, name).
            if "workflow_documents_unique_name" in str(exc):
                raise DocumentConflict(
                    f"a document named {name!r} already exists in {folder!r}"
                ) from exc
            raise
        row = await cur.fetchone()
        assert row is not None
    return _view_from_row(row)


def _view_from_row(row: dict[str, Any]) -> DocumentView:
    definition = TemplateDefinition.model_validate(row["definition"])
    return DocumentView(
        id=row["id"],
        org_id=row["org_id"],
        project_id=row["project_id"],
        folder=row["folder"],
        name=row["name"],
        description=row["description"],
        source_template_id=row["source_template_id"],
        source_template_version_id=row["source_template_version_id"],
        definition=definition,
        node_count=row["node_count"],
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
