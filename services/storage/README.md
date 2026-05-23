# verolas-storage

Shared storage primitives for Verolas Python services. See `docs/decisions/007-object-storage-foundation.md` for the design and the ADR.

- `presigned.py` presigned upload and download URLs over an S3 compatible backend, single shot and multipart.
- `clamd.py` ClamAV daemon INSTREAM client over raw TCP.
- `file_kinds.py` classification including macro bearing Office file detection.
