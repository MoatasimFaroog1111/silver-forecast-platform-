from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = ROOT / "runtime_artifacts"
REPAIRS_PATH = BUNDLE_DIR / "runtime_part_repairs.json"
SUPPORTED_FORMAT = "runtime-part-repair-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_name(value: str) -> bool:
    return bool(value) and Path(value).name == value and value not in {".", ".."}


def _verified_file(name: str, size: int, sha256: str) -> bytes:
    if not _safe_name(name):
        raise RuntimeError(f"Unsafe runtime repair file name: {name!r}")
    data = (BUNDLE_DIR / name).read_bytes()
    if len(data) != size:
        raise RuntimeError(
            f"Runtime repair fragment size mismatch: {name} (expected {size}, got {len(data)})"
        )
    if _sha256(data) != sha256:
        raise RuntimeError(f"Runtime repair fragment checksum mismatch: {name}")
    return data


def _materialize_repair(repair: dict[str, Any]) -> None:
    output_name = str(repair["output"])
    output_size = int(repair["size"])
    output_sha256 = str(repair["sha256"])
    if not _safe_name(output_name):
        raise RuntimeError(f"Unsafe runtime repair output name: {output_name!r}")

    output = BUNDLE_DIR / output_name
    if output.exists():
        current = output.read_bytes()
        if len(current) == output_size and _sha256(current) == output_sha256:
            for fragment in repair["fragments"]:
                (BUNDLE_DIR / str(fragment["name"])).unlink(missing_ok=True)
            return

    parts = [
        _verified_file(str(fragment["name"]), int(fragment["size"]), str(fragment["sha256"]))
        for fragment in repair["fragments"]
    ]
    payload = b"".join(parts)
    if len(payload) != output_size:
        raise RuntimeError(f"Runtime repair output size mismatch: {output_name}")
    if _sha256(payload) != output_sha256:
        raise RuntimeError(f"Runtime repair output checksum mismatch: {output_name}")

    temp = output.with_name(f".{output.name}.repair-{os.getpid()}.tmp")
    try:
        temp.write_bytes(payload)
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)

    for fragment in repair["fragments"]:
        (BUNDLE_DIR / str(fragment["name"])).unlink(missing_ok=True)


def materialize_runtime_parts() -> None:
    document = json.loads(REPAIRS_PATH.read_text(encoding="utf-8"))
    if document.get("format") != SUPPORTED_FORMAT:
        raise RuntimeError(f"Unsupported runtime repair format: {document.get('format')!r}")
    repairs = document.get("repairs")
    if not isinstance(repairs, list) or not repairs:
        raise RuntimeError("Runtime repair document must contain at least one repair")
    for repair in repairs:
        if not isinstance(repair, dict):
            raise RuntimeError("Runtime repair entry must be an object")
        _materialize_repair(repair)


if __name__ == "__main__":
    materialize_runtime_parts()
