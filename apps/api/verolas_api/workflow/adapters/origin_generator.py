"""Verolas Origin AI Design adapter.

Tool key: `verolas.origin.generator`. Used by the Verolas Origin
template's `ai_design` node. Reads the project brief from the upstream
`submit_project` node's outputs and asks Anthropic Claude to propose
3 to 5 structural concept options.

The model is a design assistant. The engineer (the next `select_option`
gate and the `engineer_refine_seal` manual node) remains the
responsible designer. Copy and prompts reinforce that framing.

When `settings.anthropic_api_key` is unset (tests, or dev deployments
without the secret), the adapter returns a stubbed payload with three
generic options so the workflow still progresses end-to-end.
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

logger = logging.getLogger(__name__)


_PROMPT_TEMPLATE = """You are Verolas Origin, a structural concept design
assistant for licensed engineers. The engineer is the responsible designer
and will refine and seal the chosen option; your job is to propose a
shortlist they can choose from quickly.

Given the project brief below, generate **between 3 and 5** structural
concept options. Each option must include all of these keys exactly:

- `option_id`: short slug, e.g. "rc-flat-slab", "steel-mrf"
- `summary`: one sentence stating the structural idea
- `bay_grid_m`: typical bay grid in metres, e.g. "7.5 x 8.0"
- `slab_type`: e.g. "flat slab", "waffle slab", "hollow-core PT plank", "CLT panel"
- `primary_structure`: e.g. "RC frame with shear walls", "steel MRF", "CLT panel with steel core"
- `material`: e.g. "concrete C25/30", "steel S355", "glulam GL24h"
- `prelim_load_kN_m2`: rough total load takedown including self-weight
- `boq_estimate_eur_m2`: rough cost per gross floor area, EUR per m^2
- `sustainability_note`: short GWP indication or sustainability tradeoff
- `caveats`: list of 1 to 3 strings flagging risks the engineer should
  verify (e.g. "verify seismic zone amplification", "check vibration
  serviceability for span > 8m")

Output **only** valid JSON of the form:
{{
  "options": [ {{ ...one entry per option... }} ]
}}

Project brief:
---
{brief_text}
---

Building type: {building_type}
Jurisdiction: {jurisdiction}
"""

_FALLBACK_OPTIONS = [
    {
        "option_id": "rc-flat-slab",
        "summary": "Reinforced concrete flat slab on RC columns and shear-wall core.",
        "bay_grid_m": "7.5 x 8.0",
        "slab_type": "flat slab, 240 mm",
        "primary_structure": "RC frame with shear walls",
        "material": "concrete C25/30, rebar B500B",
        "prelim_load_kN_m2": 7.5,
        "boq_estimate_eur_m2": 1450,
        "sustainability_note": (
            "Highest embodied carbon of the three options; partially offset "
            "by 30% recycled aggregate and CEM II/B-S cement."
        ),
        "caveats": [
            "Punching shear at columns must be checked.",
            "Slab deflection for spans > 8 m needs verification.",
        ],
    },
    {
        "option_id": "steel-mrf",
        "summary": "Steel moment-resisting frame with composite floors on metal deck.",
        "bay_grid_m": "8.0 x 9.0",
        "slab_type": "composite metal deck slab, 130 mm topping",
        "primary_structure": "steel MRF with secondary beams",
        "material": "structural steel S355, concrete C25/30 topping",
        "prelim_load_kN_m2": 5.8,
        "boq_estimate_eur_m2": 1620,
        "sustainability_note": (
            "Lower embodied carbon than RC; modular and demountable for end-of-life."
        ),
        "caveats": [
            "Fire protection on exposed beams adds cost.",
            "Floor vibration check needed for slender bays.",
        ],
    },
    {
        "option_id": "clt-hybrid",
        "summary": "CLT panel floors and walls with a steel or RC stair core.",
        "bay_grid_m": "6.0 x 7.5",
        "slab_type": "CLT panel, 180 mm five-layer",
        "primary_structure": "CLT panel-and-wall with steel core",
        "material": "glulam GL24h beams, CLT panels, steel S355 core",
        "prelim_load_kN_m2": 4.2,
        "boq_estimate_eur_m2": 1780,
        "sustainability_note": (
            "Lowest embodied carbon; renewable timber; possible biogenic carbon credit."
        ),
        "caveats": [
            "Acoustic separation between floors needs detailing.",
            "Fire rating R60 typically requires gypsum encapsulation.",
        ],
    },
]


class OriginGeneratorAdapter(NodeAdapter):
    tool = "verolas.origin.generator"

    async def run(
        self,
        ctx: AdapterContext,
        inputs: dict[str, Any],
    ) -> AdapterResult:
        brief = inputs.get("submit_project", {}) or {}
        brief_text = str(brief.get("brief_text") or brief.get("brief") or "").strip()
        building_type = str(brief.get("building_type") or "residential")
        jurisdiction = str(brief.get("jurisdiction") or "DE")

        api_key = ctx.settings.anthropic_api_key if ctx.settings else None
        model = ctx.settings.anthropic_model if ctx.settings else "claude-sonnet-4-6"

        if not api_key:
            logger.info(
                "origin_generator.stub",
                extra={
                    "reason": "no_api_key",
                    "run_id": str(ctx.run_id),
                },
            )
            return AdapterResult(
                outputs={
                    "options": _FALLBACK_OPTIONS,
                    "model": "stub",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "note": (
                        "Anthropic API key not configured; returning a "
                        "generic three-option shortlist. Set "
                        "VEROLAS_API_ANTHROPIC_API_KEY for live model output."
                    ),
                }
            )

        try:
            options = await self._call_claude(
                api_key=api_key,
                model=model,
                brief_text=brief_text or "(empty brief; propose generic options)",
                building_type=building_type,
                jurisdiction=jurisdiction,
            )
        except Exception as exc:
            logger.exception("origin_generator.error", extra={"run_id": str(ctx.run_id)})
            return AdapterResult(
                outputs={},
                error=f"Claude call failed: {exc}",
            )

        return AdapterResult(
            outputs={
                "options": options,
                "model": model,
                "generated_at": datetime.now(UTC).isoformat(),
            }
        )

    async def _call_claude(
        self,
        *,
        api_key: str,
        model: str,
        brief_text: str,
        building_type: str,
        jurisdiction: str,
    ) -> list[dict[str, Any]]:
        """Call Anthropic Claude and parse the JSON response.

        The SDK is sync-only in some versions; we wrap in to_thread so
        the executor stays cooperative under async load.
        """
        prompt = _PROMPT_TEMPLATE.format(
            brief_text=brief_text,
            building_type=building_type,
            jurisdiction=jurisdiction,
        )

        def _invoke() -> str:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            # Concatenate all text blocks. Other block kinds (tool_use,
            # thinking, etc.) don't carry text we want and are skipped.
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
        """Extract the options array from Claude's response.

        The prompt asks for pure JSON, but the model occasionally
        wraps in markdown code fences. Handle both.
        """
        text = raw.strip()
        if text.startswith("```"):
            # Strip opening fence and the optional language tag.
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
            text = text.strip()

        parsed = json.loads(text)
        options = parsed.get("options")
        if not isinstance(options, list):
            raise ValueError("response did not contain an 'options' list")
        return options


register_adapter(OriginGeneratorAdapter())
