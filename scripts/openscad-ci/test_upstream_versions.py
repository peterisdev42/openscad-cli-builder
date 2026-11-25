import unittest

from discover_upstream import candidate_status
from upstream_versions import discover, parse_remote_tags, resolve_tag


class UpstreamTests(unittest.TestCase):
    def test_peel_annotated_and_ignore_unrelated_tags(self):
        a, b = "a" * 40, "b" * 40
        text = f"{a}\trefs/tags/openscad-2027.01\n{b}\trefs/tags/openscad-2027.01^{{}}\n{a}\trefs/tags/unrelated"
        self.assertEqual(parse_remote_tags(text), {"openscad-2027.01": b})

    def test_discover_all_channels_and_numeric_suffix(self):
        sha = "a" * 40
        tags = {tag: sha for tag in ("openscad-2027.01", "openscad-2027.02-RC2",
                "openscad-2027.02-RC10", "openscad-2027.03-TEST1")}
        snapshot = ("2027.03.01", "https://files.openscad.org/snapshots/file", "file")
        result = discover(tags, "openscad-2027.01", snapshot)
        self.assertEqual([c["tag"] for c in result], ["openscad-2027.01",
            "openscad-2027.02-RC10", "openscad-2027.03-TEST1", "openscad-2027.03.01"])

    def test_pinned_tag_cannot_move(self):
        with self.assertRaises(ValueError):
            resolve_tag("openscad-2021.01", {"openscad-2021.01": "a" * 40})

    def test_existing_release_guard(self):
        sha = "a" * 40
        c = {"tag": "openscad-2027.01", "channel": "stable", "commit": sha}
        self.assertEqual(candidate_status(c, {}), "new")
        self.assertEqual(candidate_status(c, {c["tag"]: {"body": "  commit: " + sha}}), "published")
        self.assertEqual(candidate_status(c, {c["tag"]: {"body": "  commit: " + "b" * 40}}), "conflict")

    def test_snapshot_guard(self):
        c = {"tag": "openscad-2027.01.01", "channel": "snapshot", "url": "https://files.openscad.org/snapshots/file"}
        self.assertEqual(candidate_status(c, {c["tag"]: {"body": "  snapshotUrl: " + c["url"]}}), "published")
        self.assertEqual(candidate_status(c, {c["tag"]: {"body": "no metadata"}}), "conflict")


if __name__ == "__main__":
    unittest.main()
