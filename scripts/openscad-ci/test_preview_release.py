"""Pure release safety gates. These tests do not need an Apple Silicon runner."""
import hashlib
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

from preview_exporter.verify_release import ARCHIVE, PACKAGE, SOURCE_TAG, SOURCE_COMMIT, verify


class PreviewReleaseTests(unittest.TestCase):
    def make_archive(self, folder: Path, *, machine=0x0100000C, wrapper_mode=0o755):
        prefix = PACKAGE + "/"
        info = {
            "tag": SOURCE_TAG, "commit": SOURCE_COMMIT, "target": "macos-arm64",
            "preview_exporter": True, "preview_scene_schema": 1,
            "headless": True, "opengl": True, "nullgl": False,
        }
        files = {
            "build-info.json": json.dumps(info).encode(),
            "COPYING": b"GPL license",
            "README.md": b"Preview exporter readme",
            "bin/openscad-preview-exporter": b'#!/bin/sh\nexec "$base/OpenSCAD.app/Contents/MacOS/OpenSCAD" "$@"\n',
            "OpenSCAD.app/Contents/MacOS/OpenSCAD":
                b"\xcf\xfa\xed\xfe" + struct.pack("<I", machine) + b"".join(
                    hashlib.sha256(str(i).encode()).digest() for i in range(128)),
        }
        archive = folder / ARCHIVE
        with tarfile.open(archive, "w:gz") as output:
            for name, contents in files.items():
                member = tarfile.TarInfo(prefix + name)
                member.size = len(contents)
                member.mode = (wrapper_mode if name.startswith("bin/") else
                               0o755 if name.startswith("OpenSCAD.app/") else 0o644)
                output.addfile(member, io.BytesIO(contents))
        checksum = folder / (ARCHIVE + ".sha256")
        checksum.write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {ARCHIVE}\n")
        return archive, checksum

    def test_valid_archive_structure_macho_and_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            archive, _ = self.make_archive(folder)
            self.assertEqual(verify(folder), hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_rejects_wrong_cpu_architecture(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make_archive(folder, machine=0x01000007)
            with self.assertRaisesRegex(RuntimeError, "ARM64"):
                verify(folder)

    def test_rejects_nonexecutable_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make_archive(folder, wrapper_mode=0o644)
            with self.assertRaisesRegex(RuntimeError, "not marked executable"):
                verify(folder)

    def test_rejects_corrupt_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _, checksum = self.make_archive(folder)
            checksum.write_text("0" * 64 + "  " + ARCHIVE + "\n")
            with self.assertRaisesRegex(RuntimeError, "SHA256"):
                verify(folder)


if __name__ == "__main__":
    unittest.main()
