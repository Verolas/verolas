"""Workflow HTTP API.

Three routers:

- `org_workflow_router` at /v1/orgs/{slug}/workflows for org-level
  reads (template gallery).
- `project_workflow_router` at /v1/orgs/{slug}/projects/{id}/workflows
  for project-scoped run lifecycle (create, list, fetch, advance,
  cancel).

The product surfaces these as a single "Workflows" pillar; the split
is purely about whose RLS context is needed and which path segment
makes sense in URL form.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from verolas_api.dependencies.org import DbOrgConn
from verolas_api.middleware import sla_tier
from verolas_api.workflow import documents as documents_service
from verolas_api.workflow import runs as runs_service
from verolas_api.workflow.documents import DocumentConflict, DocumentNotFound
from verolas_api.workflow.executor import ExecutorError
from verolas_api.workflow.runs import (
    RunNotFound,
    TemplateNotFound,
    WorkflowError,
)
from verolas_api.workflow.schema import (
    DocumentView,
    RunView,
    TemplateDefinition,
    TemplateView,
)

org_workflow_router = APIRouter(
    prefix="/orgs/{org_slug}/workflows",
    tags=["workflows"],
)
project_workflow_router = APIRouter(
    prefix="/orgs/{org_slug}/projects/{project_id}/workflows",
    tags=["workflows"],
)


# Request bodies.


class WorkflowRunCreateBody(BaseModel):
    """Create a run rooted in either a template (legacy) or a document."""

    model_config = ConfigDict(extra="forbid")

    template_slug: str | None = Field(default=None, min_length=1, max_length=64)
    document_id: UUID | None = None


class WorkflowDocumentCreateBody(BaseModel):
    """Create a workflow document from a template or blank."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    folder: str = Field(default="/", max_length=400)
    description: str | None = Field(default=None, max_length=2000)
    template_slug: str | None = Field(default=None, min_length=1, max_length=64)


class WorkflowDocumentUpdateBody(BaseModel):
    """Partial update of a document."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    folder: str | None = Field(default=None, max_length=400)
    description: str | None = Field(default=None, max_length=2000)
    definition: TemplateDefinition | None = None


class WorkflowGateDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class WorkflowManualDoneBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outputs: dict[str, object] | None = None


class WorkflowNodeAdvanceBody(BaseModel):
    """Union of node-kind-specific actions.

    Exactly one of `gate` or `manual` should be populated, matching the
    node's kind. Routes validate this and dispatch accordingly.
    """

    model_config = ConfigDict(extra="forbid")

    gate: WorkflowGateDecisionBody | None = None
    manual: WorkflowManualDoneBody | None = None


# Helpers.


def _project_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id must be a UUID.",
        ) from exc


def _storage(request: Request) -> Any:
    """Fetch the storage service from app.state; None when not configured."""
    return getattr(request.app.state, "storage_service", None)


def _settings(request: Request) -> Any:
    """Fetch the api Settings from app.state; None when not initialised."""
    return getattr(request.app.state, "settings", None)


# Org-level routes.


@org_workflow_router.get("/templates", response_model=list[TemplateView])
@sla_tier(1)
async def list_workflow_templates(
    deps: DbOrgConn,
    jurisdiction: Annotated[str | None, Query(max_length=8)] = None,
) -> list[TemplateView]:
    """List templates visible to the caller's org plus Verolas globals."""
    conn, _ = deps
    return await runs_service.list_templates(conn, jurisdiction=jurisdiction)


# Project-level routes.


@project_workflow_router.post(
    "/runs",
    response_model=RunView,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(1)
async def create_workflow_run(
    request: Request,
    project_id: Annotated[str, Path()],
    body: WorkflowRunCreateBody,
    deps: DbOrgConn,
) -> RunView:
    """Create a run from either a template slug or a document id.

    Runs the executor inline so automated entry nodes complete before
    the response. Exactly one of template_slug or document_id must be set.
    """
    conn, ctx = deps
    pid = _project_id(project_id)
    storage = _storage(request)

    if (body.template_slug is None) == (body.document_id is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of template_slug or document_id.",
        )

    try:
        if body.template_slug is not None:
            return await runs_service.create_run(
                conn,
                org_id=ctx.organization_id,
                project_id=pid,
                template_slug=body.template_slug,
                started_by_user_id=ctx.user_id,
                storage=storage,
                settings=_settings(request),
            )
        assert body.document_id is not None
        return await runs_service.create_run_from_document(
            conn,
            org_id=ctx.organization_id,
            project_id=pid,
            document_id=body.document_id,
            started_by_user_id=ctx.user_id,
            storage=storage,
            settings=_settings(request),
        )
    except TemplateNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# Document CRUD.


@project_workflow_router.post(
    "/documents",
    response_model=DocumentView,
    status_code=status.HTTP_201_CREATED,
)
@sla_tier(1)
async def create_workflow_document(
    project_id: Annotated[str, Path()],
    body: WorkflowDocumentCreateBody,
    deps: DbOrgConn,
) -> DocumentView:
    """Create a workflow document. Either blank or forked from a template."""
    conn, ctx = deps
    pid = _project_id(project_id)
    try:
        if body.template_slug:
            return await documents_service.create_document_from_template(
                conn,
                org_id=ctx.organization_id,
                project_id=pid,
                folder=body.folder,
                name=body.name,
                description=body.description,
                template_slug=body.template_slug,
                created_by_user_id=ctx.user_id,
            )
        return await documents_service.create_blank_document(
            conn,
            org_id=ctx.organization_id,
            project_id=pid,
            folder=body.folder,
            name=body.name,
            description=body.description,
            created_by_user_id=ctx.user_id,
        )
    except TemplateNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@project_workflow_router.get(
    "/documents",
    response_model=list[DocumentView],
)
@sla_tier(1)
async def list_workflow_documents(
    project_id: Annotated[str, Path()],
    deps: DbOrgConn,
) -> list[DocumentView]:
    """List workflow documents for this project, grouped by folder client-side."""
    conn, _ = deps
    pid = _project_id(project_id)
    return await documents_service.list_documents_for_project(conn, pid)


@project_workflow_router.get(
    "/documents/{document_id}",
    response_model=DocumentView,
)
@sla_tier(1)
async def get_workflow_document(
    project_id: Annotated[str, Path()],
    document_id: Annotated[UUID, Path()],
    deps: DbOrgConn,
) -> DocumentView:
    """Fetch a single workflow document with its full definition."""
    conn, _ = deps
    _ = _project_id(project_id)
    try:
        return await documents_service.get_document(conn, document_id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@project_workflow_router.patch(
    "/documents/{document_id}",
    response_model=DocumentView,
)
@sla_tier(1)
async def update_workflow_document(
    project_id: Annotated[str, Path()],
    document_id: Annotated[UUID, Path()],
    body: WorkflowDocumentUpdateBody,
    deps: DbOrgConn,
) -> DocumentView:
    """Partial update of name, folder, description, or definition."""
    conn, _ = deps
    _ = _project_id(project_id)
    try:
        return await documents_service.update_document(
            conn,
            document_id,
            name=body.name,
            folder=body.folder,
            description=body.description,
            definition=body.definition,
        )
    except DocumentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WorkflowError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@project_workflow_router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@sla_tier(1)
async def delete_workflow_document(
    project_id: Annotated[str, Path()],
    document_id: Annotated[UUID, Path()],
    deps: DbOrgConn,
) -> None:
    """Hard-delete a workflow document. Runs already created from it remain (snapshotted)."""
    conn, _ = deps
    _ = _project_id(project_id)
    try:
        await documents_service.delete_document(conn, document_id)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@project_workflow_router.get("/runs", response_model=list[RunView])
@sla_tier(1)
async def list_workflow_runs(
    project_id: Annotated[str, Path()],
    deps: DbOrgConn,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RunView]:
    """List recent runs on this project."""
    conn, _ = deps
    pid = _project_id(project_id)
    return await runs_service.list_runs_for_project(conn, pid, limit=limit)


@project_workflow_router.get(
    "/runs/{run_id}",
    response_model=RunView,
)
@sla_tier(1)
async def get_workflow_run(
    project_id: Annotated[str, Path()],
    run_id: Annotated[UUID, Path()],
    deps: DbOrgConn,
) -> RunView:
    """Fetch a single run with its node list."""
    conn, _ = deps
    _ = _project_id(project_id)
    try:
        return await runs_service.get_run(conn, run_id=run_id)
    except RunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@project_workflow_router.post(
    "/runs/{run_id}/nodes/{node_key}/advance",
    response_model=RunView,
)
@sla_tier(1)
async def advance_workflow_node(
    request: Request,
    project_id: Annotated[str, Path()],
    run_id: Annotated[UUID, Path()],
    node_key: Annotated[str, Path(min_length=1, max_length=64)],
    body: WorkflowNodeAdvanceBody,
    deps: DbOrgConn,
) -> RunView:
    """Advance a single node. Body shape depends on the node kind:

    - For gate.review or gate.approve: include `gate: {decision, note}`.
    - For manual: include `manual: {outputs}` (outputs optional).
    """
    conn, ctx = deps
    pid = _project_id(project_id)
    storage = _storage(request)

    if (body.gate is None) == (body.manual is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Body must include exactly one of `gate` or `manual`.",
        )

    try:
        if body.gate is not None:
            return await runs_service.submit_gate_decision(
                conn,
                org_id=ctx.organization_id,
                run_id=run_id,
                node_key=node_key,
                decision=body.gate.decision,
                note=body.gate.note,
                actor_user_id=ctx.user_id,
                storage=storage,
                project_id=pid,
            )
        assert body.manual is not None
        return await runs_service.mark_manual_done(
            conn,
            org_id=ctx.organization_id,
            run_id=run_id,
            node_key=node_key,
            outputs=body.manual.outputs,
            actor_user_id=ctx.user_id,
            storage=storage,
            settings=_settings(request),
            project_id=pid,
        )
    except RunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (ExecutorError, WorkflowError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@project_workflow_router.post("/runs/{run_id}/cancel", response_model=RunView)
@sla_tier(1)
async def cancel_workflow_run(
    project_id: Annotated[str, Path()],
    run_id: Annotated[UUID, Path()],
    deps: DbOrgConn,
) -> RunView:
    """Cancel a run. Non-terminal nodes are marked skipped."""
    conn, ctx = deps
    _ = _project_id(project_id)
    try:
        return await runs_service.cancel_run(
            conn,
            org_id=ctx.organization_id,
            run_id=run_id,
            actor_user_id=ctx.user_id,
        )
    except RunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


class OriginSealInfoBody(BaseModel):
    """Engineer's seal payload captured at the export_seal step."""

    model_config = ConfigDict(extra="forbid")

    engineer_name: str = Field(min_length=1, max_length=200)
    registration_number: str = Field(min_length=1, max_length=80)
    jurisdiction: str = Field(min_length=1, max_length=64)
    date_iso: str = Field(min_length=4, max_length=64)
    statement: str = Field(default="", max_length=400)


class OriginExportResponse(BaseModel):
    """Outcome of the export pipeline."""

    model_config = ConfigDict(extra="forbid")

    dwg_storage_key: str
    pdf_storage_key: str
    ifc_storage_key: str
    dwg_size_bytes: int
    pdf_size_bytes: int
    ifc_size_bytes: int
    warnings: list[str]


@project_workflow_router.post(
    "/runs/{run_id}/origin/export",
    response_model=OriginExportResponse,
)
@sla_tier(2)
async def export_origin_seal_package(
    request: Request,
    project_id: Annotated[str, Path()],
    run_id: Annotated[UUID, Path()],
    body: OriginSealInfoBody,
    deps: DbOrgConn,
) -> OriginExportResponse:
    """Render the DXF + PDF/A + IFC seal package from upstream nodes.

    Pulls the reviewed geometry, chosen option, detail layout, and
    roof framing from this run's node outputs, runs the three
    renderers, persists the three artifacts under
    `workflow-runs/{org}/{run}/origin/`, and returns the storage keys.
    The engineer marks-done separately with the seal info (the
    `verolas_api.workflow.runs` mark_manual_done path) recording the
    keys on the export_seal node's outputs.
    """
    import asyncio

    from verolas_api.workflow.origin.export import (
        SealInfo,
        build_export_package,
    )

    conn, ctx = deps
    pid = _project_id(project_id)
    _ = pid
    try:
        run = await runs_service.get_run(conn, run_id=run_id)
    except RunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    by_key = {n.node_key: n for n in run.nodes}
    review = by_key.get("architectural_review")
    if review is None or "reviewed_geometry" not in (review.outputs or {}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="architectural_review has not emitted reviewed_geometry yet.",
        )
    reviewed_geometry = review.outputs["reviewed_geometry"]

    ai_node = by_key.get("ai_options")
    options = (ai_node.outputs or {}).get("options") if ai_node else None
    select_node = by_key.get("select_option")
    note = (select_node.outputs or {}).get("note") if select_node else None
    chosen_option = _pick_option_from_note(options, note)

    detail_node = by_key.get("detail_edit")
    detail_layout = (detail_node.outputs or {}).get("refined_option") if detail_node else None
    roof_node = by_key.get("roof_framing")
    roof_framing = (roof_node.outputs or {}).get("roof_framing") if roof_node else None

    storage = _storage(request)
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service not configured.",
        )

    seal = SealInfo(
        engineer_name=body.engineer_name,
        registration_number=body.registration_number,
        jurisdiction=body.jurisdiction,
        date_iso=body.date_iso,
        statement=body.statement,
    )

    try:
        package = await asyncio.to_thread(
            build_export_package,
            project_id=str(project_id),
            run_id=str(run_id),
            reviewed_geometry=reviewed_geometry,
            chosen_option=chosen_option,
            detail_layout=detail_layout,
            roof_framing=roof_framing,
            seal=seal,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Origin export failed: {exc}",
        ) from exc

    base = f"workflow-runs/{ctx.organization_id}/{run_id}/origin"
    dwg_key = f"{base}/sealed.dxf"
    pdf_key = f"{base}/sealed.pdf"
    ifc_key = f"{base}/sealed.ifc"

    try:
        await asyncio.to_thread(
            storage.put_bytes,
            key=dwg_key,
            body=package.dxf_bytes,
            content_type="application/dxf",
        )
        await asyncio.to_thread(
            storage.put_bytes,
            key=pdf_key,
            body=package.pdf_bytes,
            content_type="application/pdf",
        )
        await asyncio.to_thread(
            storage.put_bytes,
            key=ifc_key,
            body=package.ifc_bytes,
            content_type="application/x-step",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storing sealed package failed: {exc}",
        ) from exc

    return OriginExportResponse(
        dwg_storage_key=dwg_key,
        pdf_storage_key=pdf_key,
        ifc_storage_key=ifc_key,
        dwg_size_bytes=len(package.dxf_bytes),
        pdf_size_bytes=len(package.pdf_bytes),
        ifc_size_bytes=len(package.ifc_bytes),
        warnings=package.warnings,
    )


def _pick_option_from_note(
    options: list[Any] | None,
    note: str | None,
) -> dict[str, Any] | None:
    """Match the engineer's gate note to an option_id from ai_options."""
    if not options:
        return None
    if note:
        for opt in options:
            if isinstance(opt, dict):
                opt_id = opt.get("option_id")
                if isinstance(opt_id, str) and opt_id in note:
                    return dict(opt)
        for opt in options:
            if isinstance(opt, dict):
                variant = opt.get("variant")
                if isinstance(variant, str) and variant.lower() in note.lower():
                    return dict(opt)
    first = options[0]
    return dict(first) if isinstance(first, dict) else None


class WorkflowArtifactUrl(BaseModel):
    """Presigned download URL for a workflow-run artifact."""

    model_config = ConfigDict(extra="forbid")

    storage_key: str
    url: str
    method: str
    expires_in: int


@project_workflow_router.get(
    "/runs/{run_id}/artifact",
    response_model=WorkflowArtifactUrl,
)
@sla_tier(1)
async def get_workflow_run_artifact_url(
    request: Request,
    project_id: Annotated[str, Path()],
    run_id: Annotated[UUID, Path()],
    storage_key: Annotated[str, Query(min_length=1, max_length=512)],
    deps: DbOrgConn,
) -> WorkflowArtifactUrl:
    """Return a short-lived presigned download URL for a run artifact.

    Adapters write artifacts under
    `workflow-runs/{org_id}/{run_id}/...`. We validate the key has
    that prefix so a caller cannot use this endpoint to fetch
    unrelated objects. The run is also loaded to confirm it belongs
    to the caller's org (RLS enforces this on the SELECT).
    """
    conn, ctx = deps
    _ = _project_id(project_id)
    try:
        await runs_service.get_run(conn, run_id=run_id)
    except RunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    expected_prefix = f"workflow-runs/{ctx.organization_id}/{run_id}/"
    if not storage_key.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="storage_key does not belong to this run.",
        )

    storage = _storage(request)
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage service not configured.",
        )

    presigned = storage.presign_download(key=storage_key)
    return WorkflowArtifactUrl(
        storage_key=storage_key,
        url=presigned.url,
        method=presigned.method,
        expires_in=presigned.expires_in,
    )
