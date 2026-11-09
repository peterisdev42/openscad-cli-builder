"""Tests for the RC0 Preview Exporter YAML header and body-only repair."""
import copy
import os
import unittest
from unittest.mock import patch

from preview_exporter.metadata import BASE_NOTES, CHANNEL, DOWNLOAD, REPOSITORY, VERSION, release_notes
from preview_exporter.reconcile_release import EXPECTED_ASSETS, run, target
from preview_exporter.verify_release import ARCHIVE, RELEASE_TAG, SOURCE_COMMIT
from preview_exporter import publish


def example_release():
    return {
        "id": 123, "tag_name": RELEASE_TAG, "draft": False, "prerelease": True,
        "name": "OpenSCAD Preview Exporter", "target_commitish": "main",
        "body": BASE_NOTES,
        "assets": [
            {"id": 71, "name": ARCHIVE, "size": 20971520},
            {"id": 72, "name": ARCHIVE + ".sha256", "size": 100},
        ],
    }


class PreviewMetadataTests(unittest.TestCase):
    def test_canonical_header_matches_existing_cli_releases(self):
        self.assertEqual(CHANNEL, "rc")
        self.assertEqual(VERSION, "2026.11-RC0")
        body = release_notes()
        self.assertTrue(body.startswith("```yaml\nschemaVersion: 1\n"))
        self.assertIn('version: "2026.11-RC0"', body)
        self.assertIn("channel: rc", body)
        self.assertIn("upstream:\n  repository: openscad/openscad\n  commit: " + SOURCE_COMMIT, body)
        self.assertIn("Only macOS ARM64", body)
        self.assertIn(f"[{ARCHIVE}]({DOWNLOAD})", body)
        self.assertIn(f"[{ARCHIVE}.sha256]({DOWNLOAD}.sha256)", body)
        self.assertEqual(body.count("```yaml"), 1)
        self.assertEqual(body.count("| OS | Architecture | Download URL | SHA256 |"), 1)

    def test_publisher_uses_same_metadata_generator(self):
        self.assertEqual(publish.NOTES, release_notes())

    def test_idempotent_preserves_legacy_body_and_download_table(self):
        initial = BASE_NOTES + "\n\nAdditional release note.\n"
        first = release_notes(initial)
        self.assertEqual(first, release_notes(first))
        self.assertIn(initial, first)

    def test_only_exact_published_release_and_original_assets_can_be_repaired(self):
        release = example_release()
        self.assertEqual(target(release), release_notes(BASE_NOTES))
        for bad in (
            {"tag_name": "openscad-2026.11-RC0"},
            {"draft": True},
            {"prerelease": False},
            {"body": "Mismatched source"},
            {"assets": [release["assets"][0]]},
            {"assets": [{**release["assets"][0], "size": 0}, release["assets"][1]]},
        ):
            changed = copy.deepcopy(release)
            changed.update(bad)
            with self.subTest(change=bad):
                with self.assertRaises(RuntimeError):
                    target(changed)

    def test_repair_patches_body_only_and_checks_remote_assets(self):
        state = example_release()
        updates = []

        def fake_gh(path, payload=None):
            if payload is not None:
                self.assertEqual(set(payload), {"body"})
                updates.append(copy.deepcopy(payload))
                state.update(payload)
            return copy.deepcopy(state)

        with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main"}), \
                patch("preview_exporter.reconcile_release.gh_api", side_effect=fake_gh):
            run(apply=True)
            run(apply=True)
        self.assertEqual(len(updates), 1)
        self.assertEqual(state["body"], release_notes(BASE_NOTES))
        self.assertEqual({a["name"] for a in state["assets"]}, EXPECTED_ASSETS)

    def test_dry_run_never_mutates(self):
        state = example_release()
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_REF": "refs/heads/main"}), \
                patch("preview_exporter.reconcile_release.gh_api", return_value=state) as api:
            run(apply=False)
        self.assertEqual(api.call_count, 1)


if __name__ == "__main__":
    unittest.main()
