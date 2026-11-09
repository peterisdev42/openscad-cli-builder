import unittest

from release_metadata import release_channel, with_release_header, yaml_release_header


class ReleaseMetadataTests(unittest.TestCase):
    def test_channel_classification(self):
        self.assertEqual(release_channel("openscad-2021.01"), "stable")
        self.assertEqual(release_channel("openscad-2026.10-RC2"), "rc")
        self.assertEqual(release_channel("openscad-2026.10-TEST4"), "test")
        self.assertEqual(release_channel("openscad-2026.10.27", snapshot=True), "snapshot")
        with self.assertRaises(ValueError):
            release_channel("openscad-not-a-version")

    def test_header_is_idempotent_and_preserves_download_table(self):
        original = "| OS | URL |\n| :-- | :-- |\n| macOS | https://example.com |"
        first = with_release_header(original, "2026.10.27", "snapshot", "a" * 40)
        self.assertTrue(first.startswith("```yaml\nschemaVersion: 1\n"))
        self.assertIn('version: "2026.10.27"', first)
        self.assertIn("channel: snapshot", first)
        self.assertEqual(first.count("| OS | URL |"), 1)
        self.assertEqual(first.count("schemaVersion: 1"), 1)
        self.assertEqual(first, with_release_header(first, "2026.10.27", "snapshot", "a" * 40))
        updated = with_release_header(first, "2026.10.27", "snapshot", "b" * 40)
        self.assertIn("b" * 40, updated)
        self.assertNotIn("a" * 40, updated)
        self.assertEqual(updated.count("| OS | URL |"), 1)

    def test_yaml_header_for_release_channels(self):
        sha = "a" * 40
        stable = yaml_release_header("2021.01", "stable", sha)
        rc = yaml_release_header("2026.11-RC0", "rc", sha)
        snapshot = yaml_release_header(
            "2026.10.27", "snapshot", sha,
            snapshot_url="https://files.openscad.org/snapshots/OpenSCAD-2026.10.27-x86_64.AppImage")
        self.assertIn("channel: stable", stable)
        self.assertIn("channel: rc", rc)
        self.assertIn("channel: snapshot", snapshot)
        self.assertIn("snapshotUrl:", snapshot)

    def test_header_rejects_invalid_source_and_snapshot_url(self):
        with self.assertRaises(ValueError):
            yaml_release_header("2026.11-RC0", "rc", "bad-sha")
        with self.assertRaises(ValueError):
            yaml_release_header("2026.10.27", "snapshot", "a" * 40,
                                snapshot_url="https://example.com/untrusted.AppImage")


if __name__ == "__main__":
    unittest.main()
