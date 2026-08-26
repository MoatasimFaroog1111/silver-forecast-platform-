from __future__ import annotations

import base64
import hashlib
import io
import json
import lzma
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = ROOT / "runtime_artifacts"
MANIFEST_PATH = BUNDLE_DIR / "runtime_payload_manifest.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def restore_runtime_artifacts() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    count = int(manifest["part_count"])
    regular_size = int(manifest["part_size"])
    last_size = int(manifest["last_part_size"])
    part_prefix = str(manifest.get("part_prefix", "forecast_runtime_payload.part"))
    encoded_parts: list[bytes] = []
    for index in range(count):
        path = BUNDLE_DIR / f"{part_prefix}{index:03d}.b64"
        data = path.read_bytes()
        expected_size = last_size if index == count - 1 else regular_size
        if len(data) != expected_size:
            raise RuntimeError(f"Runtime artifact part size mismatch: {path.name}")
        encoded_parts.append(data)

    archive_xz = base64.b64decode(b"".join(encoded_parts), validate=True)
    if _sha256(archive_xz) != manifest["archive_sha256"]:
        raise RuntimeError("Runtime artifact archive checksum mismatch")

    raw_tar = lzma.decompress(archive_xz)
    if _sha256(raw_tar) != manifest["decoded_tar_sha256"]:
        raise RuntimeError("Runtime artifact TAR checksum mismatch")

    expected = set(manifest["targets"])
    with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:") as tf:
        members = tf.getmembers()
        actual = {member.name for member in members if member.isfile()}
        if actual != expected:
            raise RuntimeError("Runtime artifact target set mismatch")
        for member in members:
            pure = PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts:
                raise RuntimeError(f"Unsafe runtime artifact path: {member.name}")
        tf.extractall(ROOT, members=members, filter="data")

    for rel in expected:
        if not (ROOT / rel).is_file():
            raise RuntimeError(f"Restored runtime artifact is missing: {rel}")


if __name__ == "__main__":
    restore_runtime_artifacts()
