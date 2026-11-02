#!/usr/bin/env python3
"""Validate exactly the standalone Apple Silicon release archive, before publishing."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

ARCHIVE = "openscad-preview-exporter-macos-arm64.tar.gz"
PACKAGE = "openscad-preview-exporter-macos-arm64"
SOURCE_TAG = "openscad-2026.11-RC0"
SOURCE_COMMIT = "9ba0cee7c94785fac0ca8dfe040b965a12a25ed1"
RELEASE_TAG = "preview-exporter-openscad-2026.11-RC0"
ARM64_CPU_TYPE = 0x0100000C


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(directory: Path):
    directory = Path(directory)
    archive = directory / ARCHIVE
    checksum = directory / (ARCHIVE + ".sha256")
    if not archive.is_file() or not checksum.is_file() or archive.stat().st_size < 1024:
        raise RuntimeError("Preview Exporter release missing nonempty archive or checksum")
    match = re.fullmatch(r"([0-9a-f]{64})  " + re.escape(ARCHIVE) + r"\n?", checksum.read_text())
    if not match or digest(archive) != match.group(1):
        raise RuntimeError("Preview Exporter SHA256 verification failed")
    with tarfile.open(archive, "r:gz") as package:
        members = {member.name: member for member in package.getmembers()}
        prefix = PACKAGE + "/"
        for name in members:
            parts = PurePosixPath(name).parts
            if not (name == PACKAGE or name.startswith(prefix)) or ".." in parts or name.startswith("/"):
                raise RuntimeError(f"Archive member escapes package: {name!r}")
        required = {
            "build-info.json": False,
            "COPYING": False,
            "README.md": False,
            "bin/openscad-preview-exporter": True,
            "OpenSCAD.app/Contents/MacOS/OpenSCAD": True,
        }
        for suffix, executable in required.items():
            member = members.get(prefix + suffix)
            if member is None or not member.isfile() or member.size == 0:
                raise RuntimeError(f"Missing nonempty packaged file: {suffix}")
            if executable and not (member.mode & 0o111):
                raise RuntimeError(f"Packaged executable is not marked executable: {suffix}")
        main = package.extractfile(members[prefix + "OpenSCAD.app/Contents/MacOS/OpenSCAD"])
        header = main.read(8)
        if header[:4] != b"\xcf\xfa\xed\xfe" or int.from_bytes(header[4:8], "little") != ARM64_CPU_TYPE:
            raise RuntimeError("Main OpenSCAD binary is not a thin macOS ARM64 Mach-O executable")
        wrapper = package.extractfile(members[prefix + "bin/openscad-preview-exporter"]).read().decode("utf-8")
        if 'OpenSCAD.app/Contents/MacOS/OpenSCAD' not in wrapper:
            raise RuntimeError("Packaged exporter wrapper does not start the bundled OpenSCAD")
        metadata = json.load(package.extractfile(members[prefix + "build-info.json"]))
        expected = {
            "tag": SOURCE_TAG, "commit": SOURCE_COMMIT, "target": "macos-arm64",
            "preview_exporter": True, "preview_scene_schema": 1,
            "headless": True, "opengl": True, "nullgl": False,
        }
        for key, value in expected.items():
            if metadata.get(key) != value:
                raise RuntimeError(f"Preview Exporter {key} mismatch: {metadata.get(key)!r}")
    print(f"Verified {archive}: SHA256, ARM64 executable, layout, wrapper, and upstream provenance")
    return match.group(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_release.py <dist-dir>")
    verify(Path(sys.argv[1]))
