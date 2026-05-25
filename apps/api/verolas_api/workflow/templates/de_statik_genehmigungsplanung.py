"""Verolas template: DE Statik Genehmigungsplanung (HOAI § 51, LP 4).

The first real country template. Models the structural engineering
workflow a German Tragwerksplanungsbüro runs from the Leistungsphase 4
contract (Genehmigungsplanung) through the Bauamt submission, for a
residential Mehrfamilienhaus or comparable Wohngebäude.

Source basis: HOAI § 51 + Anlage 14 (Grundleistungen Tragwerksplanung);
PrüfVBau Bayern + state PrüfVO patterns for the Prüfstatik gate;
DBauV Bayern / Bauportal NRW / ViBa BW for the digital Bauamt
submission node; eIDAS QTSP rules for QES (D-Trust sign-me as the
default DE provider). See verolas-workflow-bible.md for the full
country profile and references.

Graph shape: a linear sequence with one parallel join in the middle:
the three Bemessung tracks (Decken / Stützen / Fundamente) fan out
from Schnittgrößenermittlung and converge at Konstruktive Durchbildung.
This exercises the executor's join logic for the first time in a real
template.

Automated nodes today emit a completion event without doing actual
work; real adapters land in stage 6+ (RFEM webservice, SOFiSTiK via
Bridge, etc.). The params capture the intended adapter so the
swap-in is just code, not template surgery.
"""

from __future__ import annotations

from verolas_api.workflow.registry import register_template
from verolas_api.workflow.schema import (
    EdgeDef,
    NodeDef,
    NodeKind,
    TemplateDefinition,
    TemplateSpec,
)


def _build() -> TemplateSpec:
    nodes = [
        NodeDef(
            key="kickoff",
            kind=NodeKind.MANUAL,
            name="Projektakte anlegen",
            description=(
                "Auftrag bestätigt, Projektakte angelegt, Bauherr und "
                "Architekt-Anforderungen eingelesen. Klärt Gebäudeklasse "
                "nach Landes-LBO und prüft ob Sonderbau vorliegt."
            ),
            params={"step": "kickoff"},
        ),
        NodeDef(
            key="lastannahmen",
            kind=NodeKind.AUTOMATED,
            name="Lastannahmen erstellen",
            description=(
                "Eigenlasten, Nutzlasten (EN 1991-1-1 + NA-DE), Schnee "
                "(EN 1991-1-3), Wind (EN 1991-1-4), ggf. Erdbeben "
                "(EN 1998 + NA). Ergebnis: Lastannahmen-Tabelle pro Position."
            ),
            params={
                "tool": "verolas.lastannahmen",
                "codes": ["EN 1990 + NA-DE", "EN 1991 + NA-DE"],
            },
        ),
        NodeDef(
            key="tragsystem_modell",
            kind=NodeKind.AUTOMATED,
            name="Tragsystem modellieren",
            description=(
                "Statisches System (Stabwerk oder FE) im FEM-Programm "
                "aufgebaut. Idealisierung, Auflagerbedingungen, "
                "Elementeigenschaften gesetzt."
            ),
            params={
                "tool": "dlubal.rfem",
                "fallback_tools": ["sofistik", "frilo"],
            },
        ),
        NodeDef(
            key="schnittgroessen",
            kind=NodeKind.AUTOMATED,
            name="Schnittgrößen ermitteln",
            description=(
                "Schnittgrößenermittlung für alle Last-Kombinationen "
                "nach EN 1990. FE-Lauf mit Konvergenz-Check. Ausgabe: "
                "Maxschnittgrößen je Bauteil."
            ),
            params={"tool": "dlubal.rfem.analysis"},
        ),
        NodeDef(
            key="bemessung_decken",
            kind=NodeKind.AUTOMATED,
            name="Decken bemessen",
            description=(
                "Stahlbetondecken (Geschoss- und Dachdecke) nach "
                "EN 1992-1-1 + NA-DE. GZT- und GZG-Nachweise, "
                "Mindestbewehrung, Verformung."
            ),
            params={
                "tool": "verolas.bemessung.beton",
                "codes": ["EN 1992-1-1 + NA-DE", "DIN EN 13670"],
            },
        ),
        NodeDef(
            key="bemessung_stuetzen",
            kind=NodeKind.AUTOMATED,
            name="Stützen bemessen",
            description=(
                "Stützenbemessung Stahlbeton nach EN 1992-1-1 + NA-DE. "
                "Berücksichtigung Knicklängen, Biege-Druck-Interaktion, "
                "konstruktive Mindestbewehrung."
            ),
            params={
                "tool": "verolas.bemessung.beton",
                "codes": ["EN 1992-1-1 + NA-DE"],
            },
        ),
        NodeDef(
            key="bemessung_fundamente",
            kind=NodeKind.AUTOMATED,
            name="Fundamente bemessen",
            description=(
                "Streifen-, Einzel- oder Plattenfundamente, basierend auf "
                "Bodengutachten. Erdstatik nach EN 1997-1 + NA, "
                "Stahlbetonbemessung nach EN 1992."
            ),
            params={
                "tool": "verolas.bemessung.fundament",
                "codes": ["EN 1997-1 + NA-DE", "EN 1992-1-1 + NA-DE"],
            },
        ),
        NodeDef(
            key="konstruktive_durchbildung",
            kind=NodeKind.MANUAL,
            name="Konstruktive Durchbildung",
            description=(
                "Anschluss-Details, Verankerungslängen, Mindestbewehrung, "
                "Bewehrungsskizzen pro Position. Iteration mit Architekt "
                "über Aussparungen, Brüstungsanschlüsse, Übergänge."
            ),
            params={"step": "detailing"},
        ),
        NodeDef(
            key="statik_compile",
            kind=NodeKind.AUTOMATED,
            name="Statik PDF erstellen",
            description=(
                "Prüffähige Statik als PDF/A zusammengestellt: Deckblatt, "
                "Inhaltsverzeichnis (Positionsnummern), Lastannahmen, "
                "Schnittgrößen, Bemessung je Position, Konstruktive "
                "Durchbildung, Bewehrungslisten, Anlagen (FE-Ausdrucke, "
                "abZ/ETA-Zulassungen, Bodengutachten-Auszüge)."
            ),
            params={
                "tool": "verolas.statik_compile",
                "output_format": "pdf_a",
            },
        ),
        NodeDef(
            key="internal_review",
            kind=NodeKind.GATE_REVIEW,
            name="Internes Vier-Augen-Prinzip",
            description=(
                "Eine zweite tragwerksplanende Person prüft die Statik "
                "intern. Anmerkungen werden im Kommentar festgehalten und "
                "vor dem Prüfstatik-Gate ausgeräumt."
            ),
            params={"assignee_role": "structural_engineer_peer"},
        ),
        NodeDef(
            key="pruefstatik",
            kind=NodeKind.GATE_APPROVE,
            name="Prüfstatik (Vier-Augen extern)",
            description=(
                "Für Gebäudeklasse 4/5 und Sonderbauten zwingend: "
                "Prüfingenieur nach PrüfVBau bzw. Landes-PrüfVO erstellt "
                "Prüfbericht. Auflagen werden in einer Iterationsschleife "
                "abgearbeitet bis Avis F. Für GK 1 bis 3 in den meisten "
                "Bundesländern nicht prüfpflichtig: Engineer markiert das "
                "Gate selbst als genehmigt."
            ),
            params={
                "assignee_role": "pruefingenieur",
                "triggers_obligation": [
                    "gebaeudeklasse_4_5",
                    "sonderbau",
                    "varies_by_bundesland",
                ],
            },
        ),
        NodeDef(
            key="bauvorlagen_pkg",
            kind=NodeKind.AUTOMATED,
            name="Bauvorlagen-Paket zusammenstellen",
            description=(
                "Bauvorlagen Standsicherheit als Einzel-PDF: Statik, "
                "Positionsplan, Brandschutznachweis (falls vom "
                "Brandschutzplaner geliefert), Wärme- und Schallschutz- "
                "Nachweise (sofern Tragwerksplaner-Pflicht), Bodengutachten. "
                "Format konform zu DBauV Bayern bzw. BauPrüfVO NRW."
            ),
            params={
                "tool": "verolas.bauvorlagen_assembler",
                "output_format": "pdf_single_file_no_encryption",
            },
        ),
        NodeDef(
            key="qes_signing",
            kind=NodeKind.GATE_SIGNATURE,
            name="QES auf Bauvorlagen anbringen",
            description=(
                "Qualifizierte elektronische Signatur des bauvorlagen- "
                "berechtigten Ingenieurs nach eIDAS-VO 910/2014 + § 126a "
                "BGB. Standard-Anbieter: D-Trust sign-me (Bundesdruckerei) "
                "oder Skribble. In Niedersachsen Pflicht; in Bayern, NRW, "
                "Berlin, BW empfohlen für die rechtsverbindliche Einreichung."
            ),
            params={
                "qtsp_default": "d_trust_sign_me",
                "qtsp_alternatives": ["skribble", "docusign_eu_qes"],
                "level": "qes",
            },
        ),
        NodeDef(
            key="bauamt_submission",
            kind=NodeKind.SUBMISSION,
            name="Bauantrag beim Bauamt einreichen",
            description=(
                "Hochladen ins Bundesland-Portal: Bayern (Digitaler "
                "Bauantrag, digitalerbauantrag.bayern.de), NRW (Bauportal "
                "NRW), Berlin (eBG), Baden-Württemberg (ViBa BW), Hessen "
                "(Bauportal Hessen). Empfangsbestätigung mit Bauakten- "
                "nummer kommt zurück und wird hier festgehalten."
            ),
            params={
                "portal_by_bundesland": {
                    "BY": "digitalerbauantrag.bayern.de",
                    "NW": "bauportal.nrw",
                    "BE": "berlin.de/ebg",
                    "BW": "service-bw.de (ViBa BW)",
                    "HE": "Bauportal Hessen (ekom21)",
                },
                "receipt_capture_required": True,
            },
        ),
    ]

    edges = [
        EdgeDef(from_key="kickoff", to_key="lastannahmen"),
        EdgeDef(from_key="lastannahmen", to_key="tragsystem_modell"),
        EdgeDef(from_key="tragsystem_modell", to_key="schnittgroessen"),
        # Three parallel Bemessung tracks.
        EdgeDef(from_key="schnittgroessen", to_key="bemessung_decken"),
        EdgeDef(from_key="schnittgroessen", to_key="bemessung_stuetzen"),
        EdgeDef(from_key="schnittgroessen", to_key="bemessung_fundamente"),
        # Join.
        EdgeDef(from_key="bemessung_decken", to_key="konstruktive_durchbildung"),
        EdgeDef(from_key="bemessung_stuetzen", to_key="konstruktive_durchbildung"),
        EdgeDef(from_key="bemessung_fundamente", to_key="konstruktive_durchbildung"),
        # Linear tail.
        EdgeDef(from_key="konstruktive_durchbildung", to_key="statik_compile"),
        EdgeDef(from_key="statik_compile", to_key="internal_review"),
        EdgeDef(from_key="internal_review", to_key="pruefstatik"),
        EdgeDef(from_key="pruefstatik", to_key="bauvorlagen_pkg"),
        EdgeDef(from_key="bauvorlagen_pkg", to_key="qes_signing"),
        EdgeDef(from_key="qes_signing", to_key="bauamt_submission"),
    ]

    definition = TemplateDefinition(
        nodes=nodes,
        edges=edges,
        entry_keys=["kickoff"],
    )

    return TemplateSpec(
        slug="de-statik-genehmigungsplanung",
        name="DE: Statik Genehmigungsplanung",
        description=(
            "Tragwerksplanung von der Genehmigungsplanung bis zur Einreichung "
            "beim Bauamt. Lastannahmen, Schnittgrößen, parallele Bemessung "
            "von Decken, Stützen und Fundamenten, konstruktive Durchbildung, "
            "Statik-PDF, internes Vier-Augen-Prinzip, Prüfstatik, "
            "Bauvorlagen-Paket, QES und Einreichung im Bundesland-Portal."
        ),
        jurisdiction="DE",
        project_type="residential",
        definition=definition,
    )


register_template(_build())
