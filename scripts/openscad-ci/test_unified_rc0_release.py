"""RC0 must publish a single CLI Release with the six normal targets and the
macOS ARM64 Preview Exporter as the seventh downloadable package type.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import release
from preview_exporter.verify_release import ARCHIVE as EXPORTER_ARCHIVE


class UnifiedReleaseTests(unittest.TestCase):
    def test_rc0_has_exactly_fourteen_release_assets(self):
        with patch.object(release, "SOURCE_TAG", "openscad-2026.11-RC0"):
            assets = release.release_assets()
            self.assertEqual(len(assets), 14)
            self.assertEqual(len(set(assets)), 14)
            self.assertEqual(assets[-2:], [EXPORTER_ARCHIVE, EXPORTER_ARCHIVE + ".sha256"])
            self.assertEqual(len([a for a in assets if a.startswith("openscad-cli-")]), 12)

    def test_all_other_tags_keep_original_twelve_assets(self):
        for tag in ("openscad-2021.01", "openscad-2026.10-TEST4", "openscad-2026.10.27"):
            with self.subTest(tag=tag), patch.object(release, "SOURCE_TAG", tag):
                self.assertEqual(len(release.release_assets()), 12)
                self.assertNotIn(EXPORTER_ARCHIVE, release.release_assets())

    def test_rc0_release_notes_include_yaml_and_seventh_package(self):
        with patch.object(release, "SOURCE_TAG", "openscad-2026.11-RC0"), \
             patch.object(release, "VERSION", "2026.11-RC0"):
            body = release.release_notes("peterisdev42/openscad-cli-builder")
            self.assertTrue(body.startswith("```yaml\nschemaVersion: 1\n"))
            self.assertIn('version: "2026.11-RC0"', body)
            self.assertIn("channel: rc", body)
            self.assertIn("  commit: " + release.SOURCE_COMMIT, body)
            self.assertIn("/releases/download/openscad-2026.11-RC0/" + EXPORTER_ARCHIVE, body)
            self.assertEqual(body.count(EXPORTER_ARCHIVE + "]("), 1)
            self.assertIn("| macOS (Preview Exporter) | Apple Silicon (ARM64) |", body)

    def test_missing_or_invalid_exporter_blocks_all_rc0_packages(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(release, "TARGETS", ()), \
             patch.object(release, "SOURCE_TAG", "openscad-2026.11-RC0"):
            with self.assertRaises(FileNotFoundError), \
                 patch("preview_exporter.verify_release.verify", side_effect=FileNotFoundError("missing")) as gate:
                release.verify_assets(Path(tmp))
            gate.assert_called_once_with(Path(tmp))

    def test_other_versions_do_not_invoke_exporter_gate(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(release, "TARGETS", ()), \
             patch.object(release, "SOURCE_TAG", "openscad-2026.10-TEST4"), \
             patch("preview_exporter.verify_release.verify") as gate:
            release.verify_assets(Path(tmp))
            gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
