from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = ROOT / "runtime_artifacts"
MANIFEST_PATH = BUNDLE_DIR / "runtime_payload_manifest.json"
SUPPORTED_FORMAT = "tar+xz+base64-parts-v2"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative_path(value: str) -> bool:
    pure = PurePosixPath(value)
    return bool(pure.parts) and not pure.is_absolute() and ".." not in pure.parts


def _load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("format") != SUPPORTED_FORMAT:
        raise RuntimeError(f"Unsupported runtime artifact format: {manifest.get('format')!r}")

    required = {
        "part_prefix",
        "part_count",
        "part_size",
        "last_part_size",
        "encoded_size",
        "archive_size",
        "archive_sha256",
        "decoded_tar_sha256",
        "targets",
        "target_integrity",
    }
    missing = sorted(required.difference(manifest))
    if missing:
        raise RuntimeError(f"Runtime artifact manifest missing keys: {', '.join(missing)}")

    count = int(manifest["part_count"])
    regular_size = int(manifest["part_size"])
    last_size = int(manifest["last_part_size"])
    encoded_size = int(manifest["encoded_size"])
    if count <= 0:
        raise RuntimeError("Runtime artifact part_count must be positive")
    if regular_size <= 0 or last_size <= 0:
        raise RuntimeError("Runtime artifact part sizes must be positive")
    if encoded_size != ((count - 1) * regular_size) + last_size:
        raise RuntimeError("Runtime artifact manifest encoded size is inconsistent")

    targets = list(manifest["targets"])
    if len(targets) != len(set(targets)):
        raise RuntimeError("Runtime artifact manifest contains duplicate targets")
    if any(not _safe_relative_path(target) for target in targets):
        raise RuntimeError("Runtime artifact manifest contains an unsafe target path")
    if set(targets) != set(manifest["target_integrity"]):
        raise RuntimeError("Runtime artifact integrity map does not match target set")

    return manifest


def _read_encoded_payload(manifest: dict[str, Any]) -> bytes:
    count = int(manifest["part_count"])
    regular_size = int(manifest["part_size"])
    last_size = int(manifest["last_part_size"])
    prefix = str(manifest["part_prefix"])
    expected_names = {f"{prefix}{index:03d}.b64" for index in range(count)}
    actual_names = {path.name for path in BUNDLE_DIR.glob(f"{prefix}*.b64")}
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extras = sorted(actual_names - expected_names)
        details: list[str] = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if extras:
            details.append(f"extra={','.join(extras)}")
        raise RuntimeError(f"Runtime artifact part set mismatch ({'; '.join(details)})")

    encoded_parts: list[bytes] = []
    for index in range(count):
        path = BUNDLE_DIR / f"{prefix}{index:03d}.b64"
        data = path.read_bytes()
        expected_size = last_size if index == count - 1 else regular_size
        if len(data) != expected_size:
            raise RuntimeError(
                f"Runtime artifact part size mismatch: {path.name} "
                f"(expected {expected_size}, got {len(data)})"
            )
        encoded_parts.append(data)

    encoded = b"".join(encoded_parts)
    if len(encoded) != int(manifest["encoded_size"]):
        raise RuntimeError("Runtime artifact encoded payload size mismatch")
    return encoded


def _decode_and_verify_archive(encoded: bytes, manifest: dict[str, Any]) -> bytes:
    try:
        archive_xz = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("Runtime artifact payload is not valid base64") from exc

    if len(archive_xz) != int(manifest["archive_size"]):
        raise RuntimeError("Runtime artifact archive size mismatch")
    if _sha256(archive_xz) != str(manifest["archive_sha256"]):
        raise RuntimeError("Runtime artifact archive checksum mismatch")

    try:
        raw_tar = lzma.decompress(archive_xz)
    except lzma.LZMAError as exc:
        raise RuntimeError("Runtime artifact archive is not valid XZ data") from exc

    if _sha256(raw_tar) != str(manifest["decoded_tar_sha256"]):
        raise RuntimeError("Runtime artifact TAR checksum mismatch")
    return raw_tar


def _verified_payloads(raw_tar: bytes, manifest: dict[str, Any]) -> dict[str, bytes]:
    expected = set(manifest["targets"])
    integrity: dict[str, dict[str, Any]] = manifest["target_integrity"]
    payloads: dict[str, bytes] = {}

    with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise RuntimeError("Runtime artifact TAR contains duplicate paths")
        if set(names) != expected:
            raise RuntimeError("Runtime artifact target set mismatch")

        for member in members:
            if not _safe_relative_path(member.name):
                raise RuntimeError(f"Unsafe runtime artifact path: {member.name}")
            if not member.isfile():
                raise RuntimeError(f"Runtime artifact is not a regular file: {member.name}")

            stream = archive.extractfile(member)
            if stream is None:
                raise RuntimeError(f"Unable to read runtime artifact: {member.name}")
            data = stream.read()
            expected_meta = integrity[member.name]
            if len(data) != int(expected_meta["size"]):
                raise RuntimeError(f"Runtime artifact file size mismatch: {member.name}")
            if _sha256(data) != str(expected_meta["sha256"]):
                raise RuntimeError(f"Runtime artifact file checksum mismatch: {member.name}")
            payloads[member.name] = data

    return payloads


def _write_verified_payloads(payloads: dict[str, bytes], manifest: dict[str, Any]) -> None:
    integrity: dict[str, dict[str, Any]] = manifest["target_integrity"]
    for rel, data in payloads.items():
        destination = ROOT / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(f".{destination.name}.restore-{os.getpid()}.tmp")
        try:
            temp.write_bytes(data)
            os.replace(temp, destination)
        finally:
            temp.unlink(missing_ok=True)

        restored = destination.read_bytes()
        expected_meta = integrity[rel]
        if len(restored) != int(expected_meta["size"]):
            raise RuntimeError(f"Restored runtime artifact size mismatch: {rel}")
        if _sha256(restored) != str(expected_meta["sha256"]):
            raise RuntimeError(f"Restored runtime artifact checksum mismatch: {rel}")


def restore_runtime_artifacts() -> None:
    manifest = _load_manifest()
    encoded = _read_encoded_payload(manifest)
    raw_tar = _decode_and_verify_archive(encoded, manifest)
    payloads = _verified_payloads(raw_tar, manifest)
    _write_verified_payloads(payloads, manifest)


if __name__ == "__main__":
    restore_runtime_artifacts()
