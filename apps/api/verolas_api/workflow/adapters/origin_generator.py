"""Verolas Origin AI Design adapter.

Tool key: `verolas.origin.generator`. Runs on the `ai_options` node.

Pipeline (deterministic engine + optional LLM polish):

1. Pull the reviewed building geometry from the `architectural_review`
   node's outputs (or fall back to the raw `floor_parse` geometry when
   review has not been completed yet).
2. Pull the engineer's roof framing plan from `roof_framing.outputs`.
3. Call `origin.grid.generate_options(geometry, parameters)` to build
   three deterministic structural options (Optimized / Balanced /
   Conservative) with bay grid, takeoff, DCR, constructibility, BoQ.
4. If `settings.anthropic_api_key` is configured, ask Claude to polish
   the `summary`, `sustainability_note`, and `caveats` fields for each
   option. Numerical fields (bay grid, takeoff, DCR, BoQ) are produced
   by the engine and never overwritten by the model.
5. If no API key is set, emit the engine output verbatim.

This split keeps the structural numbers reproducible and engineer-
defensible, while letting the LLM contribute the parts it is actually
good at: natural-language framing and risk-flagging.

The engineer's `select_option` gate then picks one option_id, which
flows into `detail_edit` and `export_seal`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from verolas_api.workflow.adapters import register_adapter
from verolas_api.workflow.adapters.base import (
    AdapterContext,
    AdapterResult,
    NodeAdapter,
)
from verolas_api.workflow.origin.geometry import Geometry
from verolas_api.workflow.origin.grid import StructuralOption, generate_options

logger = logging.getLogger(__name__)


_POLISH_PROMPT = """You are Verolas Origin, a structural concept design
assistant for licensed engineers. The engineer is the responsible
designer; your job is to write tight, decision-useful copy on top of
already-computed structural numbers. You may not change numbers.

For each of the three options below, return polished text for:

- `summary`: one sentence the engineer reads first. Lead with the
  structural idea and the bay grid; do not repeat the variant label.
- `sustainability_note`: 1 to 2 sentences. Reference Embodied Carbon,
  circularity, biogenic credit, or recycled-content levers if relevant.
- `caveats`: list of 2 to 4 strings. Each names a specific risk the
  engineer should verify (e.g. "verify punching shear at internal
  columns", "check vibration serviceability for offices").

Output **only** valid JSON of the form:
{{
  "options": [
    {{ "option_id": "...", "summary": "...", "sustainability_note": "...", "caveats": ["..."] }},
    ...
  ]
}}

Engineer context:
- Building type: {building_type}
- Jurisdiction: {jurisdiction}
- Brief: {brief_text}

Options to polish (do not change numerical fields, only the three copy
fields above):
{options_json}
"""


class OriginGeneratorAdapter(NodeAdapter):
    tool = "verolas.origin.generator"

    async def run(
        self,
        ctx: AdapterContext,
        inputs: dict[str, Any],
    ) -> AdapterResult:
        # Source the reviewed geometry. architectural_review writes
        # reviewed_geometry on its outputs; if the engineer skipped
        # review we fall back to the raw floor_parse geometry from
        # geometry_summary + a stub Geometry shape.
        geometry = _resolve_geometry(inputs)
        if geometry is None:
            return AdapterResult(
                outputs={},
                error=(
                    "Could not find reviewed_geometry on architectural_review "
                    "or a geometry payload on floor_parse. Run those steps "
                    "before retrying ai_options."
                ),
            )

        parameters_step = inputs.get("parameters") or {}

        # Build the three deterministic options.
        options: list[StructuralOption] = await asyncio.to_thread(
            generate_options, geometry, parameters_step
        )
        if not options:
            return AdapterResult(
                outputs={},
                error="No floors in geometry; cannot generate structural options.",
            )

        brief = inputs.get("submit_brief") or inputs.get("submit_project") or {}
        brief_text = str(brief.get("brief_text") or brief.get("brief") or "").strip()
        building_type = str(
            brief.get("asset_type")
            or brief.get("building_type")
            or parameters_step.get("asset_type")
            or "residential"
        )
        jurisdiction = str(brief.get("jurisdiction") or parameters_step.get("jurisdiction") or "DE")

        api_key = ctx.settings.anthropic_api_key if ctx.settings else None
        model = ctx.settings.anthropic_model if ctx.settings else "claude-sonnet-4-6"

        if not api_key:
            logger.info(
                "origin_generator.engine_only",
                extra={"reason": "no_api_key", "run_id": str(ctx.run_id)},
            )
            return AdapterResult(
                outputs=_build_outputs(
                    options=options,
                    model="engine",
                    note=(
                        "Anthropic API key not configured; emitting the engine "
                        "shortlist directly. Set VEROLAS_API_ANTHROPIC_API_KEY "
                        "for LLM-polished copy."
                    ),
                ),
            )

        try:
            polished = await self._polish_with_claude(
                api_key=api_key,
                model=model,
                options=options,
                brief_text=brief_text,
                building_type=building_type,
                jurisdiction=jurisdiction,
            )
            polished_by_id = {p["option_id"]: p for p in polished}
        except Exception as exc:
            logger.exception(
                "origin_generator.polish_error",
                extra={"run_id": str(ctx.run_id)},
            )
            return AdapterResult(
                outputs=_build_outputs(
                    options=options,
                    model="engine",
                    note=f"Claude polish failed, returning engine output: {exc}",
                ),
            )

        merged: list[StructuralOption] = []
        for opt in options:
            patch = polished_by_id.get(opt.option_id, {})
            merged.append(
                opt.model_copy(
                    update={
                        "summary": _str_or(patch.get("summary"), opt.summary),
                        "sustainability_note": _str_or(
                            patch.get("sustainability_note"), opt.sustainability_note
                        ),
                        "caveats": _list_or(patch.get("caveats"), opt.caveats),
                    }
                )
            )

        return AdapterResult(
            outputs=_build_outputs(
                options=merged,
                model=model,
                note=None,
            ),
        )

    async def _polish_with_claude(
        self,
        *,
        api_key: str,
        model: str,
        options: list[StructuralOption],
        brief_text: str,
        building_type: str,
        jurisdiction: str,
    ) -> list[dict[str, Any]]:
        """Ask Claude to refine summary + sustainability + caveats only."""
        options_payload = [o.model_dump(mode="json") for o in options]
        prompt = _POLISH_PROMPT.format(
            building_type=building_type,
            jurisdiction=jurisdiction,
            brief_text=brief_text or "(empty brief; propose generic options)",
            options_json=json.dumps(options_payload, indent=2),
        )

        def _invoke() -> str:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            chunks: list[str] = []
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        chunks.append(text)
            return "".join(chunks)

        raw = await asyncio.to_thread(_invoke)
        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> list[dict[str, Any]]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()
        parsed = json.loads(text)
        options = parsed.get("options")
        if not isinstance(options, list):
            raise ValueError("response did not contain an 'options' list")
        for entry in options:
            if not isinstance(entry, dict) or "option_id" not in entry:
                raise ValueError("polished option missing option_id")
        return options


def _resolve_geometry(inputs: dict[str, Any]) -> Geometry | None:
    """Find the best geometry available on upstream nodes."""
    review = inputs.get("architectural_review") or {}
    reviewed = review.get("reviewed_geometry")
    if reviewed:
        try:
            return Geometry.model_validate(reviewed)
        except Exception:
            logger.warning("origin_generator.reviewed_geometry_invalid")
    # fall back: floor_parse outputs may not contain the full geometry
    # inline (only geometry_key); but the executor passes the upstream
    # outputs dict. If geometry_inline was added for tests it lives
    # under floor_parse.geometry_inline.
    parse = inputs.get("floor_parse") or {}
    inline = parse.get("geometry_inline")
    if inline:
        try:
            return Geometry.model_validate(inline)
        except Exception:
            return None
    return None


def _build_outputs(
    *,
    options: list[StructuralOption],
    model: str,
    note: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "options": [o.model_dump(mode="json") for o in options],
        "model": model,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    if note:
        payload["note"] = note
    return payload


def _str_or(candidate: Any, default: str) -> str:
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return default


def _list_or(candidate: Any, default: list[str]) -> list[str]:
    if isinstance(candidate, list) and all(isinstance(x, str) for x in candidate) and candidate:
        return [x.strip() for x in candidate if x.strip()]
    return default


register_adapter(OriginGeneratorAdapter())
