import unittest
from unittest.mock import patch

from discover_upstream import (active_build_runs, active_candidate_tags, candidate_status,
                               classify_candidates, dispatch_missing)
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


    def test_version_specific_active_builds_do_not_block_other_channels(self):
        sha = "a" * 40
        candidates = discover({"openscad-2027.01": sha, "openscad-2027.02-RC1": sha,
                               "openscad-2027.02-TEST1": sha},
                              "openscad-2027.01", ("2027.02.01", "https://example.com/file", "file"))
        runs = [{"display_title": "Bootstrap latest stable"},
                {"display_title": "openscad-2027.02-TEST1"},
                {"display_title": "openscad-2027.01-RC1"}]
        result = classify_candidates(candidates, {}, runs)
        self.assertEqual([c["status"] for c in result], ["building", "new", "building", "new"])
        with patch("discover_upstream.subprocess.run") as run:
            dispatch_missing(result, "example/builder", "main")
        self.assertEqual(run.call_count, 2)
        commands = [c.args[0] for c in run.call_args_list]
        self.assertIn("source_tag=openscad-2027.02-RC1", commands[0])
        self.assertIn("expected_snapshot_tag=openscad-2027.02.01", commands[1])

    def test_active_snapshot_alias_only_reserves_snapshot_channel(self):
        candidates = [{"tag": "openscad-2027.01", "channel": "stable"},
                      {"tag": "openscad-2027.02.01", "channel": "snapshot"}]
        self.assertEqual(active_candidate_tags(candidates, [{"display_title": "latest-snapshot"}]),
                         {"openscad-2027.02.01"})
        self.assertEqual(active_candidate_tags(candidates, [{"display_title": "openscad-2027.01.31"}]),
                         set())

    def test_active_runs_ignore_pr_branch_and_completed(self):
        def run(event="workflow_dispatch", branch="main", status="queued"):
            return {"display_title": "openscad-2027.01", "event": event,
                    "head_branch": branch, "status": status}
        with patch("discover_upstream.api", side_effect=[
                {"workflow_runs": [run(), run("pull_request"), run(branch="dev"),
                                   run(status="completed")]},
                *[{"workflow_runs": []} for _ in range(4)]]) as api:
            self.assertEqual(list(active_build_runs("example/builder", "main")), [run()])
            self.assertEqual(api.call_count, 5)

    def test_existing_release_takes_precedence_over_active(self):
        sha = "a" * 40
        c = {"tag": "openscad-2027.01", "channel": "stable", "commit": sha}
        runs = [{"display_title": c["tag"]}]
        for commit, expected in ((sha, "published"), ("b" * 40, "conflict")):
            result = classify_candidates([c.copy()], {c["tag"]: {"body": "  commit: " + commit}}, runs)
            self.assertEqual(result[0]["status"], expected)


if __name__ == "__main__":
    unittest.main()
