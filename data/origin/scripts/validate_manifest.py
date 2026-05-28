#!/usr/bin/env python3
"""Validate the local data cache against sources.yaml.

Reports presence per source, computes sha256 for downloaded files,
and tells you which manual fetches are still outstanding.

Usage:
    python validate_manifest.py            # human-readable report
    python validate_manifest.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    data_dir = Path(__file__).resolve().parent.parent
    sources_yaml = data_dir / "sources.yaml"
    manifest = yaml.safe_load(sources_yaml.read_text())

    report: list[dict[str, Any]] = []
    for src in manifest["sources"]:
        sid = src["id"]
        local_path_str = src.get("local_path") or ""
        manual = src.get("manual", False)
        fmt = src.get("format", "")

        if not local_path_str or fmt == "python_package":
            report.append(
                {
                    "id": sid,
                    "status": "not-a-file",
                    "format": fmt,
                    "manual": manual,
                }
            )
            continue

        target = data_dir / local_path_str
        if target.is_dir() or local_path_str.endswith("/"):
            present = target.exists() and any(target.iterdir())
            report.append(
                {
                    "id": sid,
                    "status": "present" if present else "missing",
                    "local_path": str(target.relative_to(data_dir)),
                    "manual": manual,
                    "is_dir": True,
                }
            )
            continue

        if target.exists():
            report.append(
                {
                    "id": sid,
                    "status": "present",
                    "local_path": str(target.relative_to(data_dir)),
                    "size_bytes": target.stat().st_size,
                    "sha256": sha256_of(target),
                    "manual": manual,
                }
            )
        else:
            report.append(
                {
                    "id": sid,
                    "status": "missing",
                    "local_path": str(target.relative_to(data_dir)),
                    "manual": manual,
                    "hint": (
                        "manual download required; see MANIFEST.md"
                        if manual
                        else "run scripts/fetch_all.sh"
                    ),
                }
            )

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"Data manifest validation report ({len(report)} sources)\n")
    width = max(len(r["id"]) for r in report) + 2
    for r in report:
        status = r["status"]
        flag = (
            "OK"
            if status == "present"
            else ("MANUAL" if r.get("manual") else "MISSING")
            if status == "missing"
            else "n/a"
        )
        print(f"  {r['id']:<{width}} [{flag:<7}] {r.get('local_path', '')}")
    missing = [r for r in report if r["status"] == "missing"]
    print(f"\n{len(missing)} missing of {len(report)} sources.")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
