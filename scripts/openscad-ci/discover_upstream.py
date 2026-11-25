#!/usr/bin/env python3
"""Report latest Stable, RC, TEST and Snapshot; optionally dispatch missing builds."""
import argparse
import json
import os
import re
import subprocess

from upstream_versions import api, discover, latest_stable, remote_tags, snapshot_metadata


def release_pages(repository):
    page = 1
    while True:
        releases = api(f"repos/{repository}/releases?per_page=100&page={page}")
        yield from releases
        if len(releases) < 100:
            break
        page += 1


def candidate_status(candidate, releases):
    current = releases.get(candidate["tag"])
    if current is None:
        return "new"
    if current.get("draft"):
        return "conflict"
    body = current.get("body") or ""
    header = body.split("\n" + chr(96) * 3, 1)[0]
    if candidate["channel"] == "snapshot":
        match = re.search(r"^  snapshotUrl: (.+)$", header, re.M)
        return "published" if match and match.group(1) == candidate["url"] else "conflict"
    match = re.search(r"^  commit: ([0-9a-f]{40})$", header, re.M)
    return "published" if match and match.group(1) == candidate["commit"] else "conflict"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch", action="store_true")
    args = parser.parse_args()
    repository = os.environ["GITHUB_REPOSITORY"]
    candidates = discover(remote_tags(), latest_stable(), snapshot_metadata())
    releases = {r["tag_name"]: r for r in release_pages(repository)}
    for candidate in candidates:
        candidate["status"] = candidate_status(candidate, releases)
    print(json.dumps(candidates, indent=2))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write("## Upstream versions\n\n| Channel | Tag | Status |\n|---|---|---|\n")
            for c in candidates:
                summary.write(f"| {c['channel']} | {c['tag']} | {c['status']} |\n")
    if any(c["status"] == "conflict" for c in candidates):
        raise RuntimeError("Existing release differs from upstream; review manually")
    if not args.dispatch:
        return
    # Avoid overlapping discovery with any pending or running CLI build.
    runs = api(f"repos/{repository}/actions/workflows/openscad-cli.yml/runs?per_page=100")
    if any(r["status"] != "completed" for r in runs["workflow_runs"]):
        print("CLI build already active; retry discovery later")
        return
    for c in candidates:
        if c["status"] != "new":
            continue
        command = ["gh", "workflow", "run", "openscad-cli.yml", "--repo", repository,
                   "--ref", os.environ["GITHUB_REF_NAME"], "-f", "skip_existing=true"]
        if c["channel"] == "snapshot":
            command += ["-f", "source_tag=latest-snapshot", "-f", "expected_snapshot_tag=" + c["tag"]]
        else:
            command += ["-f", "source_tag=" + c["tag"], "-f", "expected_commit=" + c["commit"]]
        subprocess.run(command, check=True, timeout=60)


if __name__ == "__main__":
    main()
