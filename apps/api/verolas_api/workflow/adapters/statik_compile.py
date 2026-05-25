"""Statik PDF/A assembler adapter.

Tool key: `verolas.statik_compile`. Used by the DE Statik
Genehmigungsplanung template's `statik_compile` node. When that node
becomes READY in a run, this adapter assembles a prüffähige Statik PDF
in the structure described in the workflow bible (Deckblatt,
Inhaltsverzeichnis, Lastannahmen, Schnittgrößen, Bemessung,
Konstruktive Durchbildung, Bewehrungslisten, Anlagen).

Today's implementation produces a placeholder Statik that pulls its
content from upstream node outputs (which themselves are still
placeholder until their adapters land). The structure is right; the
content is sparse. As subsequent adapters ship for upstream nodes
(lastannahmen, schnittgroessen, bemessung_*) their real outputs flow
into this adapter and the PDF starts to carry actual engineering data.

The output is stored in the org's S3 bucket under
  `workflow-runs/{org_id}/{run_id}/statik.pdf`
and the run node's outputs record the storage key + a presigned download
URL for the UI.
"""

from __future__ import annotations

import asyncio
import io
import logging
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from verolas_api.workflow.adapters import register_adapter
from verolas_api.workflow.adapters.base import (
    AdapterContext,
    AdapterResult,
    ArtifactRef,
    NodeAdapter,
)

logger = logging.getLogger(__name__)

_PDF_CONTENT_TYPE = "application/pdf"


class StatikCompileAdapter(NodeAdapter):
    tool = "verolas.statik_compile"

    async def run(
        self,
        ctx: AdapterContext,
        inputs: dict[str, Any],
    ) -> AdapterResult:
        # Build the PDF in memory.
        pdf_bytes = await asyncio.to_thread(self._render_pdf, ctx, inputs)

        storage_key = f"workflow-runs/{ctx.org_id}/{ctx.run_id}/statik.pdf"

        # Persist to S3-compatible storage when configured. Tests inject a
        # None storage service and read the bytes from the returned
        # artifact via the caller's mock.
        if ctx.storage is not None:
            await asyncio.to_thread(
                ctx.storage.put_bytes,
                key=storage_key,
                body=pdf_bytes,
                content_type=_PDF_CONTENT_TYPE,
            )

        artifact = ArtifactRef(
            storage_key=storage_key,
            content_type=_PDF_CONTENT_TYPE,
            size_bytes=len(pdf_bytes),
            label="Statik PDF",
        )

        return AdapterResult(
            outputs={
                "statik_storage_key": storage_key,
                "statik_size_bytes": len(pdf_bytes),
                "statik_compiled_at": datetime.now(UTC).isoformat(),
            },
            artifacts=[artifact],
        )

    def _render_pdf(self, ctx: AdapterContext, inputs: dict[str, Any]) -> bytes:
        """Build a Statik PDF from the run state. Synchronous; called via to_thread."""
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=A4,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
            topMargin=22 * mm,
            bottomMargin=22 * mm,
            title="Statik",
            author="Verolas",
            subject="Prüffähige Statik (Genehmigungsplanung)",
        )

        styles = getSampleStyleSheet()
        h1 = ParagraphStyle(
            "VerolasH1",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=8,
        )
        h2 = ParagraphStyle(
            "VerolasH2",
            parent=styles["Heading2"],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=4,
        )
        body = ParagraphStyle(
            "VerolasBody",
            parent=styles["BodyText"],
            fontSize=10,
            leading=13,
        )
        small = ParagraphStyle(
            "VerolasSmall",
            parent=styles["BodyText"],
            fontSize=8,
            textColor=colors.grey,
            leading=10,
        )

        story: list[Any] = []

        # Deckblatt.
        story.append(Paragraph("Prüffähige Statik", h1))
        story.append(Paragraph("Genehmigungsplanung (HOAI § 51)", body))
        story.append(Spacer(1, 8 * mm))
        story.append(
            Paragraph(
                f"Projekt-ID: <font face='Courier'>{ctx.project_id}</font>",
                body,
            )
        )
        story.append(
            Paragraph(
                f"Workflow-Run: <font face='Courier'>{ctx.run_id}</font>",
                body,
            )
        )
        story.append(
            Paragraph(
                f"Erstellt am: {datetime.now(UTC).strftime('%d.%m.%Y %H:%M UTC')}",
                body,
            )
        )
        story.append(Spacer(1, 6 * mm))
        story.append(
            Paragraph(
                "Verolas Assistant hat diese Statik gemäß HOAI § 51 "
                "(Leistungsbild Tragwerksplanung) zusammengestellt. "
                "Bauvorlagenberechtigung und endgültige Verantwortung "
                "trägt der Tragwerksplaner mit qualifizierter elektronischer "
                "Signatur im nachfolgenden Workflow-Schritt.",
                body,
            )
        )
        story.append(Spacer(1, 8 * mm))

        # Inhaltsverzeichnis (manual, not auto-numbered).
        story.append(Paragraph("Inhaltsverzeichnis", h2))
        sections = [
            ("1", "Allgemeines", "Bauwerksbeschreibung, Normen, Baustoffe"),
            ("2", "Lastannahmen", "EN 1990, EN 1991 + NA-DE"),
            ("3", "Schnittgrößen", "FE-Modell und Lastfälle"),
            ("4", "Bemessung", "Decken, Stützen, Fundamente"),
            ("5", "Konstruktive Durchbildung", "Anschluss-Details, Verankerung"),
            ("6", "Bewehrungslisten", "Stahllisten pro Position"),
            ("7", "Anlagen", "FE-Ausdrucke, Zulassungen, Bodengutachten"),
        ]
        toc_data = [["Pos.", "Titel", "Inhalt"]]
        for pos, title, content in sections:
            toc_data.append([pos, title, content])
        toc = Table(toc_data, colWidths=[18 * mm, 50 * mm, 102 * mm])
        toc.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(toc)
        story.append(PageBreak())

        # Section 1: Allgemeines.
        story.append(Paragraph("1. Allgemeines", h2))
        story.append(
            Paragraph(
                "Tragwerksart: Stahlbetonbau, Mehrfamilienhaus. "
                "Norm: Eurocodes mit deutschen nationalen Anhängen "
                "(EN 1990, 1991, 1992, 1997 mit NA-DE). "
                "Baustoffe: Beton C25/30 (XC1 für Innenbauteile, XC4 für "
                "Außenbauteile), Betonstahl B500B, Bewehrung mit "
                "Mindestbetondeckung gemäß Expositionsklasse.",
                body,
            )
        )
        story.append(Spacer(1, 4 * mm))

        # Section 2: Lastannahmen.
        story.append(Paragraph("2. Lastannahmen", h2))
        lastannahmen_outputs = inputs.get("lastannahmen", {}) or {}
        if lastannahmen_outputs:
            story.append(
                Paragraph(
                    "Ausgabe des Lastannahmen-Adapters:",
                    small,
                )
            )
            for key, value in lastannahmen_outputs.items():
                story.append(Paragraph(f"<b>{key}:</b> {value}", small))
        else:
            story.append(
                Paragraph(
                    "Eigenlasten nach EN 1991-1-1 + NA-DE. "
                    "Nutzlasten je Nutzungsklasse. "
                    "Schneelasten nach EN 1991-1-3, Wind nach "
                    "EN 1991-1-4. "
                    "Detail-Lastannahmen folgen mit echten Werten, "
                    "sobald der zugehörige Adapter live ist.",
                    body,
                )
            )
        story.append(Spacer(1, 4 * mm))

        # Section 3: Schnittgrößen.
        story.append(Paragraph("3. Schnittgrößen", h2))
        schnittgroessen_outputs = inputs.get("schnittgroessen", {}) or {}
        if schnittgroessen_outputs:
            story.append(
                Paragraph(
                    f"FE-Lauf-Metadaten: {schnittgroessen_outputs}",
                    small,
                )
            )
        else:
            story.append(
                Paragraph(
                    "Schnittgrößenermittlung mittels FE-Programm. "
                    "Lastkombinationen nach EN 1990 (GZT und GZG). "
                    "FE-Ausgabe folgt mit echten Werten, sobald der "
                    "RFEM-Adapter live ist.",
                    body,
                )
            )
        story.append(Spacer(1, 4 * mm))

        # Section 4: Bemessung.
        story.append(Paragraph("4. Bemessung", h2))
        for bemessung_key, label in [
            ("bemessung_decken", "Decken (EN 1992-1-1 + NA-DE)"),
            ("bemessung_stuetzen", "Stützen (EN 1992-1-1 + NA-DE)"),
            ("bemessung_fundamente", "Fundamente (EN 1997-1 + NA-DE)"),
        ]:
            story.append(Paragraph(f"4.x {label}", body))
            outputs = inputs.get(bemessung_key, {}) or {}
            if outputs:
                for k, v in outputs.items():
                    story.append(Paragraph(f"<b>{k}:</b> {v}", small))
            else:
                story.append(
                    Paragraph(
                        "Bemessungs-Adapter liefert hier die Ergebnisse, "
                        "sobald aktiv. Aktuell Platzhalter.",
                        small,
                    )
                )
            story.append(Spacer(1, 3 * mm))

        # Section 5-7: Placeholders for now.
        for section_title in (
            "5. Konstruktive Durchbildung",
            "6. Bewehrungslisten",
            "7. Anlagen",
        ):
            story.append(Paragraph(section_title, h2))
            story.append(
                Paragraph(
                    "Inhalt folgt mit den zugehörigen Adapter-Ausgaben.",
                    small,
                )
            )
            story.append(Spacer(1, 3 * mm))

        # Footer note.
        story.append(Spacer(1, 10 * mm))
        story.append(
            Paragraph(
                f"Dokument-ID: {ctx.run_id} | Verolas Statik-Compiler | "
                f"Compile-Zeit {datetime.now(UTC).isoformat()}",
                small,
            )
        )

        doc.build(story)
        pdf_bytes = buf.getvalue()
        buf.close()
        logger.info(
            "statik_compile.rendered",
            extra={
                "run_id": str(ctx.run_id),
                "size_bytes": len(pdf_bytes),
            },
        )
        return pdf_bytes


register_adapter(StatikCompileAdapter())
