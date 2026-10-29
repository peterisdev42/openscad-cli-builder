import unittest

from release_metadata import release_channel, with_release_header, yaml_release_header
from sync_release_metadata import ASSET_NAMES, RELEASES, target


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

    def test_all_existing_releases_have_full_commits(self):
        self.assertEqual(len(RELEASES), 3)
        self.assertEqual(len(ASSET_NAMES), 12)
        for tag, config in RELEASES.items():
            with self.subTest(tag=tag):
                self.assertEqual(len(config["commit"]), 40)
                self.assertIn("commit: " + config["commit"],
                              yaml_release_header(tag.removeprefix("openscad-"),
                                                  config["channel"], config["commit"],
                                                  snapshot_url=config.get("snapshot_url")))

    def test_migration_only_changes_release_metadata(self):
        for tag, config in RELEASES.items():
            with self.subTest(tag=tag):
                data = {"id": 123, "tag_name": tag, "body": "Existing download table",
                        "assets": [{"name": name} for name in ASSET_NAMES], "draft": False}
                payload = target(data)
                self.assertEqual(set(payload), {"body", "prerelease", "make_latest"})
                self.assertIn("Existing download table", payload["body"])
                self.assertEqual(payload["prerelease"], config["channel"] != "stable")
                self.assertEqual(payload["make_latest"], "true" if config["channel"] == "stable" else "false")
                self.assertEqual(payload, target({**data, "body": payload["body"]}))


if __name__ == "__main__":
    unittest.main()
