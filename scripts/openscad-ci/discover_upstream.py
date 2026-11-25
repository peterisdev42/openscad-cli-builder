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


ACTIVE_STATUSES = ("queued", "in_progress", "requested", "waiting", "pending")


def active_build_runs(repository, branch):
    """List all nonterminal publishing builds, not unrelated PR or branch jobs."""
    for status in ACTIVE_STATUSES:
        page = 1
        while True:
            response = api(f"repos/{repository}/actions/workflows/openscad-cli.yml/runs"
                           f"?branch={branch}&status={status}&per_page=100&page={page}")
            runs = response["workflow_runs"]
            for run in runs:
                if (run["status"] != "completed" and run["head_branch"] == branch
                        and run["event"] in ("workflow_dispatch", "push")):
                    yield run
            if len(runs) < 100:
                break
            page += 1


def active_candidate_tags(candidates, runs):
    """Match the explicit run-name contract; legacy aliases reserve their channel."""
    aliases = {"latest-stable": "stable", "Bootstrap latest stable": "stable",
               "latest-snapshot": "snapshot"}
    titles = {run["display_title"] for run in runs}
    reserved_channels = {aliases[title] for title in titles if title in aliases}
    return {c["tag"] for c in candidates
            if c["tag"] in titles or c["channel"] in reserved_channels}


def classify_candidates(candidates, releases, runs):
    active = active_candidate_tags(candidates, runs)
    for c in candidates:
        status = candidate_status(c, releases)
        c["status"] = "building" if status == "new" and c["tag"] in active else status
    return candidates


def dispatch_missing(candidates, repository, branch):
    for c in candidates:
        if c["status"] != "new":
            print(f"Skip {c['tag']}: {c['status']}", flush=True)
            continue
        command = ["gh", "workflow", "run", "openscad-cli.yml", "--repo", repository,
                   "--ref", branch, "-f", "skip_existing=true"]
        if c["channel"] == "snapshot":
            command += ["-f", "source_tag=latest-snapshot", "-f", "expected_snapshot_tag=" + c["tag"]]
        else:
            command += ["-f", "source_tag=" + c["tag"], "-f", "expected_commit=" + c["commit"]]
        print(f"Dispatch {c['tag']} ({c['channel']})", flush=True)
        subprocess.run(command, check=True, timeout=60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch", action="store_true")
    args = parser.parse_args()
    repository = os.environ["GITHUB_REPOSITORY"]
    candidates = discover(remote_tags(), latest_stable(), snapshot_metadata())
    releases = {r["tag_name"]: r for r in release_pages(repository)}
    branch = os.environ["GITHUB_REF_NAME"]
    runs = list(active_build_runs(repository, branch))
    classify_candidates(candidates, releases, runs)
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
    dispatch_missing(candidates, repository, branch)


if __name__ == "__main__":
    main()
