"""Classification tests for the macro detection rule and friends."""

from __future__ import annotations

import pytest

from verolas_storage.file_kinds import FileKind, classify_file


@pytest.mark.parametrize(
    "filename",
    ["report.xlsm", "Budget.XLSM", "report.docm", "deck.pptm", "addin.xlam"],
)
def test_macro_extensions_flag_for_sandbox(filename: str) -> None:
    result = classify_file(filename)
    assert result.kind is FileKind.OFFICE_MACRO
    assert result.requires_macro_sandbox is True


def test_macro_mime_flags_for_sandbox_even_with_unknown_extension() -> None:
    result = classify_file(
        "weird.bin",
        content_type="application/vnd.ms-excel.sheet.macroenabled.12",
    )
    assert result.kind is FileKind.OFFICE_MACRO
    assert result.requires_macro_sandbox is True


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("plan.dwg", FileKind.CAD_DRAWING),
        ("model.ifc", FileKind.CAD_BIM),
        ("revision.dxf", FileKind.CAD_DRAWING),
        ("statik.pdf", FileKind.PDF),
        ("photo.JPG", FileKind.IMAGE),
        ("Bauakte.docx", FileKind.OFFICE_PLAIN),
        ("Kostenschaetzung.xlsx", FileKind.SPREADSHEET_PLAIN),
        ("data.csv", FileKind.SPREADSHEET_PLAIN),
        ("bundle.zip", FileKind.ARCHIVE),
        ("README", FileKind.GENERIC),
    ],
)
def test_non_macro_classifications(filename: str, expected: FileKind) -> None:
    result = classify_file(filename)
    assert result.kind is expected
    assert result.requires_macro_sandbox is False


def test_image_mime_is_recognised_without_extension() -> None:
    result = classify_file("scan", content_type="image/png")
    assert result.kind is FileKind.IMAGE
