"""Fail-closed integration tests against the checked-out upstream OpenSCAD tag."""
import tempfile
import unittest
from pathlib import Path
from shutil import copy2

from build import ROOT, SOURCE_TAG, SOURCE_COMMIT
from preview_exporter.patch import patch_preview_exporter

TAG = "openscad-2026.11-RC0"
COMMIT = "9ba0cee7c94785fac0ca8dfe040b965a12a25ed1"
FILES = ("src/io/export.h", "src/io/export.cc", "src/openscad.cc")


class PreviewExporterTests(unittest.TestCase):
    @unittest.skipUnless(SOURCE_TAG == TAG, "Only the audited RC0 exporter adapter is supported")
    def test_official_tag_is_pinned(self):
        self.assertEqual(SOURCE_COMMIT, COMMIT)

    @unittest.skipUnless(SOURCE_TAG == TAG, "Only the audited RC0 exporter adapter is supported")
    def test_injects_csg_scene_format_into_copy_without_modifying_upstream(self):
        upstream = ROOT / "sources/openscad"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            for name in FILES:
                destination = source / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                copy2(upstream / name, destination)
            patch_preview_exporter(source)
            self.assertTrue((source / "src/preview_scene_exporter.h").is_file())
            self.assertIn("PREVIEW_SCENE,", (source / FILES[0]).read_text())
            self.assertIn('"preview-scene", "csgp"', (source / FILES[1]).read_text())
            self.assertIn('identifierToInfo["csgp"]', (source / FILES[1]).read_text())
            self.assertIn("scad_preview_exporter::exportScene", (source / FILES[2]).read_text())
            for name in FILES:
                self.assertNotIn("scad_preview_exporter::exportScene", (upstream / name).read_text())
            with self.assertRaisesRegex(RuntimeError, "already patched"):
                patch_preview_exporter(source)


if __name__ == "__main__":
    unittest.main()
