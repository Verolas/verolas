"""File type classification for the upload pipeline.

The upload service routes files through different verification paths based
on type. Two distinctions matter today:

1. Macro bearing Office files (XLSM, DOCM, PPTM, and friends) must be
   handed off to the sandboxed macro analysis path used by Firm Knowledge
   Ingestion. ClamAV catches known malware, but unknown VBA payloads
   require a sandbox.
2. Engineering artefacts (DWG, DXF, IFC, RVT, PLN) are handled by the CAD
   pipeline once that lands. We classify them now so file metadata carries
   the right kind from the first upload.

The classifier is conservative: when in doubt, return GENERIC.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class FileKind(StrEnum):
    """Broad classification used by the upload pipeline."""

    OFFICE_MACRO = "office_macro"
    OFFICE_PLAIN = "office_plain"
    CAD_DRAWING = "cad_drawing"
    CAD_BIM = "cad_bim"
    PDF = "pdf"
    IMAGE = "image"
    ARCHIVE = "archive"
    SPREADSHEET_PLAIN = "spreadsheet_plain"
    GENERIC = "generic"


_MACRO_EXTENSIONS = frozenset(
    {".xlsm", ".xltm", ".xlsb", ".docm", ".dotm", ".pptm", ".potm", ".ppsm", ".xlam", ".ppam"}
)
_OFFICE_PLAIN_EXTENSIONS = frozenset({".docx", ".dotx", ".pptx", ".potx", ".ppsx"})
_SPREADSHEET_PLAIN_EXTENSIONS = frozenset({".xlsx", ".xltx", ".csv", ".tsv"})
_CAD_DRAWING_EXTENSIONS = frozenset({".dwg", ".dxf", ".dwf", ".dgn"})
_CAD_BIM_EXTENSIONS = frozenset({".ifc", ".ifczip", ".rvt", ".rfa", ".pln", ".skp"})
_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".heic"})
_ARCHIVE_EXTENSIONS = frozenset({".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"})

_MACRO_MIMES = frozenset(
    {
        "application/vnd.ms-excel.sheet.macroenabled.12",
        "application/vnd.ms-word.document.macroenabled.12",
        "application/vnd.ms-powerpoint.presentation.macroenabled.12",
    }
)


@dataclass(frozen=True, slots=True)
class Classification:
    """Result of `classify_file`."""

    kind: FileKind
    requires_macro_sandbox: bool


def classify_file(filename: str, content_type: str | None = None) -> Classification:
    """Classify a file by extension and content type.

    Macro bearing Office files surface `requires_macro_sandbox=True`, which
    the upload pipeline uses to route the file through the sandbox path.
    """
    ext = PurePosixPath(filename).suffix.lower()
    mime = (content_type or "").lower().strip()

    if ext in _MACRO_EXTENSIONS or mime in _MACRO_MIMES:
        return Classification(FileKind.OFFICE_MACRO, True)
    if ext in _OFFICE_PLAIN_EXTENSIONS:
        return Classification(FileKind.OFFICE_PLAIN, False)
    if ext in _SPREADSHEET_PLAIN_EXTENSIONS:
        return Classification(FileKind.SPREADSHEET_PLAIN, False)
    if ext in _CAD_DRAWING_EXTENSIONS:
        return Classification(FileKind.CAD_DRAWING, False)
    if ext in _CAD_BIM_EXTENSIONS:
        return Classification(FileKind.CAD_BIM, False)
    if ext == ".pdf" or mime == "application/pdf":
        return Classification(FileKind.PDF, False)
    if ext in _IMAGE_EXTENSIONS or mime.startswith("image/"):
        return Classification(FileKind.IMAGE, False)
    if ext in _ARCHIVE_EXTENSIONS:
        return Classification(FileKind.ARCHIVE, False)
    return Classification(FileKind.GENERIC, False)


__all__ = ["Classification", "FileKind", "classify_file"]
