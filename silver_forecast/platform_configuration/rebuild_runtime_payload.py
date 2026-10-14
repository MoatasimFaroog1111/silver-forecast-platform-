from __future__ import annotations

"""Rebuild the base64-part runtime bundle after runtime artifacts change.

The runtime bundle (models + packaged history + verified reports) is stored
as tar+xz+base64 parts with a strict SHA256 manifest (see
``restore_runtime_artifacts.py``). After the daily market data update changes
a target file, the parts and manifest must be rebuilt so the chain stays
verifiable.

The historical ``runtime_part_repairs.json`` fragment mechanism is retired at
the same time: stale fragments would otherwise be re-merged over the rebuilt
``runtime_v2.part031.b64`` on the next fresh checkout. The repairs document is
replaced with a no-op repair anchored to a stable sentinel file, and every
leftover fragment (and obsolete v1 payload part) is deleted.
"""

import base64
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import tarfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = ROOT / "runtime_artifacts"
MANIFEST_PATH = BUNDLE_DIR / "runtime_payload_manifest.json"
REPAIRS_PATH = BUNDLE_DIR / "runtime_part_repairs.json"
SUPPORTED_FORMAT = "tar+xz+base64-parts-v2"
LEGACY_PART_PREFIX = "forecast_runtime_payload.part"
REPAIRS_FORMAT = "runtime-part-repair-v1"

SENTINEL_NAME = "runtime_repairs_complete.json"
SENTINEL_TEXT = (
    '{"status": "complete", "note": "All runtime part repairs are finished; '
    'rebuild_runtime_payload.py now maintains the bundle."}\n'
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    temp = path.with_name(f".{path.name}.rebuild-{os.getpid()}.tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("format") != SUPPORTED_FORMAT:
        raise RuntimeError(f"Unsupported runtime artifact format: {manifest.get('format')!r}")
    if int(manifest["part_size"]) <= 0:
        raise RuntimeError("Runtime artifact part_size must be positive")
    targets = list(manifest["targets"])
    if not targets:
        raise RuntimeError("Runtime artifact manifest has no targets")
    return manifest


def _pack_targets(targets: list[str]) -> tuple[bytes, dict[str, dict[str, Any]]]:
    """Pack target files into a deterministic TAR and compute integrity."""
    buffer = io.BytesIO()
    integrity: dict[str, dict[str, Any]] = {}
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for relative in sorted(targets):
            source = ROOT / relative
            data = source.read_bytes()
            integrity[relative] = {"size": len(data), "sha256": _sha256(data)}
            info = tarfile.TarInfo(relative)
            info.size = len(data)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue(), integrity


def _retire_repairs_document() -> None:
    """Replace the fragment-repair document with a stable no-op repair."""
    sentinel = BUNDLE_DIR / SENTINEL_NAME
    _atomic_write_bytes(sentinel, SENTINEL_TEXT.encode("utf-8"))
    document = {
        "format": REPAIRS_FORMAT,
        "repairs": [
            {
                "output": SENTINEL_NAME,
                "size": len(SENTINEL_TEXT.encode("utf-8")),
                "sha256": _sha256(SENTINEL_TEXT.encode("utf-8")),
                "fragments": [],
            }
        ],
    }
    _atomic_write_bytes(
        REPAIRS_PATH,
        (json.dumps(document, indent=2) + "\n").encode("utf-8"),
    )


def rebuild_runtime_payload() -> None:
    manifest = _load_manifest()
    part_prefix = str(manifest["part_prefix"])
    part_size = int(manifest["part_size"])
    targets = list(manifest["targets"])

    raw_tar, integrity = _pack_targets(targets)
    archive_xz = lzma.compress(raw_tar)
    encoded = base64.b64encode(archive_xz)

    part_count = (len(encoded) + part_size - 1) // part_size
    parts = [encoded[index * part_size:(index + 1) * part_size] for index in range(part_count)]

    for pattern in (f"{part_prefix}*.b64", f"{LEGACY_PART_PREFIX}*.b64"):
        for path in BUNDLE_DIR.glob(pattern):
            path.unlink()
    for index, part in enumerate(parts):
        (BUNDLE_DIR / f"{part_prefix}{index:03d}.b64").write_bytes(part)

    manifest["part_count"] = len(parts)
    manifest["last_part_size"] = len(parts[-1])
    manifest["encoded_size"] = len(encoded)
    manifest["archive_size"] = len(archive_xz)
    manifest["archive_sha256"] = _sha256(archive_xz)
    manifest["decoded_tar_sha256"] = _sha256(raw_tar)
    manifest["target_integrity"] = integrity
    _atomic_write_bytes(MANIFEST_PATH, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))

    _retire_repairs_document()

    print(
        f"Rebuilt runtime bundle: {len(parts)} part(s), archive {len(archive_xz)} bytes "
        f"(sha256 {manifest['archive_sha256'][:12]}...)"
    )


if __name__ == "__main__":
    rebuild_runtime_payload()
