"""Verolas storage primitives.

Three building blocks every file workflow needs:

1. Presigned URL service for direct S3 compatible uploads and downloads.
2. clamd client that streams a file over TCP to a ClamAV daemon and parses
   the verdict.
3. File kind detection that flags macro bearing files (XLSM, DOCM, PPTM,
   etc.) for the sandboxed macro analysis path that the firm knowledge
   ingestion workstream uses.
"""

from verolas_storage.clamd import ClamdClient, ScanResult, ScanVerdict
from verolas_storage.file_kinds import FileKind, classify_file
from verolas_storage.presigned import (
    PresignedDownload,
    PresignedUpload,
    PresignedUrlService,
    StorageSettings,
)

__all__ = [
    "ClamdClient",
    "FileKind",
    "PresignedDownload",
    "PresignedUpload",
    "PresignedUrlService",
    "ScanResult",
    "ScanVerdict",
    "StorageSettings",
    "classify_file",
]
__version__ = "0.0.0"
