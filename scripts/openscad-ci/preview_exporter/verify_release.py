#!/usr/bin/env python3
"""Verify standalone Preview Exporter before uploading any GitHub release asset."""
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile

ARCHIVE = "openscad-preview-exporter-macos-arm64.tar.gz"
SOURCE_TAG = "openscad-2026.11-RC0"
SOURCE_COMMIT = "9ba0cee7c94785fac0ca8dfe040b965a12a25ed1"


def verify(directory: Path):
    directory = Path(directory)
    archive = directory / ARCHIVE
    checksum = directory / (ARCHIVE + ".sha256")
    if not archive.is_file() or not checksum.is_file():
        raise RuntimeError("Preview Exporter release is missing package or checksum")
    match = re.fullmatch(r"([0-9a-f]{64})  " + re.escape(ARCHIVE) + r"\n?", checksum.read_text())
    if not match or hashlib.sha256(archive.read_bytes()).hexdigest() != match.group(1):
        raise RuntimeError("Preview Exporter SHA256 verification failed")
    with tarfile.open(archive, "r:gz") as package:
        names = set(package.getnames())
        prefix = "openscad-preview-exporter-macos-arm64/"
        required = [prefix + n for n in (
            "build-info.json", "COPYING", "README.md",
            "bin/openscad-preview-exporter",
            "OpenSCAD.app/Contents/MacOS/OpenSCAD",
        )]
        for name in required:
            if name not in names:
                raise RuntimeError(f"Preview Exporter package missing {name}")
        metadata = json.load(package.extractfile(prefix + "build-info.json"))
        expected = {
            "tag": SOURCE_TAG, "commit": SOURCE_COMMIT, "target": "macos-arm64",
            "preview_exporter": True, "preview_scene_schema": 1,
            "headless": True, "opengl": True, "nullgl": False,
        }
        for key, value in expected.items():
            if metadata.get(key) != value:
                raise RuntimeError(f"Preview Exporter {key} mismatch: {metadata.get(key)!r}")
    print(f"Verified {archive} with OpenSCAD {SOURCE_TAG}@{SOURCE_COMMIT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_release.py <dist-dir>")
    verify(Path(sys.argv[1]))
