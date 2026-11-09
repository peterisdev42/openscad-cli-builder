"""RC0 release metadata consistency, idempotence, and unchanged-asset gates."""
import copy
import os
import unittest
from unittest.mock import patch

import release
from reconcile_rc0_release import OLD_NOTE, OLD_ROW, REPOSITORY, run, target


def original_release():
    body = release.release_notes(REPOSITORY)
    new_row = next(line for line in body.splitlines()
                   if "[openscad-preview-exporter-macos-arm64.tar.gz]" in line)
    prior_row = new_row.replace("| macOS | Apple Silicon |",
                                "| macOS (Preview Exporter) | Apple Silicon (ARM64) |")
    new_marker = "Preview Exporter (macOS Apple Silicon only):"
    current_note = new_marker + body.split(new_marker, 1)[1]
    previous = body.replace(new_row, prior_row, 1).replace(current_note, OLD_NOTE, 1)
    return {
        "id": 1234, "tag_name": "openscad-2026.11-RC0", "draft": False,
        "prerelease": True, "name": "2026.10.31-RC0",
        "target_commitish": "main",
        "body": previous,
        "assets": [{"id": 100 + i, "size": 1000,
                    "name": name}
                   for i, name in enumerate(release.release_assets())],
    }


class ReleaseDescriptionTests(unittest.TestCase):
    def test_new_body_uses_consistent_labels_and_standard_yaml_header(self):
        body = release.release_notes(REPOSITORY)
        self.assertTrue(body.startswith("```yaml\nschemaVersion: 1\n"))
        self.assertEqual(body.count("| macOS | Apple Silicon |"), 2)
        self.assertNotIn(OLD_ROW, body)
        self.assertIn("alongside the six standard CLI packages", body)
        self.assertIn("bin/openscad-preview-exporter -o model.csgp model.scad", body)
        self.assertEqual(len(release.release_assets()), 14)

    def test_migrates_only_expected_old_body_and_is_idempotent(self):
        old = original_release()
        new_body = target(old)
        self.assertEqual(new_body, release.release_notes(REPOSITORY))
        self.assertEqual(target({**old, "body": new_body}), new_body)

    def test_rejects_missing_asset_wrong_release_or_unknown_description(self):
        old = original_release()
        for key, val in (
            ("tag_name", "preview-exporter-openscad-2026.11-RC0"),
            ("draft", True),
            ("assets", old["assets"][:-1]),
            ("body", "unrelated user-authored content"),
        ):
            altered = copy.deepcopy(old)
            altered[key] = val
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                target(altered)

    def test_gh_patch_changes_body_only_and_checks_all_assets(self):
        state = original_release()
        patches = []

        def fake_api(path, payload=None):
            if payload is not None:
                self.assertEqual(set(payload), {"body"})
                patches.append(payload)
                state.update(payload)
            return copy.deepcopy(state)

        with patch.dict(os.environ, {"GITHUB_REPOSITORY": REPOSITORY,
                                     "GITHUB_REF": "refs/heads/main"}), \
             patch("reconcile_rc0_release.gh_api", side_effect=fake_api):
            run(apply=False)
            run(apply=True)
            run(apply=True)
        self.assertEqual(len(patches), 1)
        self.assertEqual(state["body"], release.release_notes(REPOSITORY))


if __name__ == "__main__":
    unittest.main()
