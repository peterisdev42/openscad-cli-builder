#!/usr/bin/env python3
"""Resolve a requested source to a verified, immutable upstream commit."""
import os
import subprocess
import sys
from pathlib import Path

from upstream_versions import UPSTREAM, latest_stable, remote_tags, resolve_tag


def main():
    source = os.environ["SELECTED_SOURCE"]
    expected = os.environ.get("EXPECTED_COMMIT", "")
    expected_snapshot = os.environ.get("EXPECTED_SNAPSHOT_TAG", "")
    if source == "latest-snapshot":
        output = subprocess.check_output(
            [sys.executable, str(Path(__file__).with_name("resolve_snapshot.py"))], text=True)
        values = dict(line.split("=", 1) for line in output.splitlines())
        if expected_snapshot and values["tag"] != expected_snapshot:
            raise ValueError("Official snapshot advanced after discovery; rediscover before building")
        if expected and values["commit"] != expected:
            raise ValueError("Snapshot commit changed")
        print(output, end="")
        return
    if expected_snapshot:
        raise ValueError("Snapshot expectation requires latest-snapshot")
    if source == "latest-stable":
        source = latest_stable()
    sha = resolve_tag(source, remote_tags())
    if expected and expected != sha:
        raise ValueError("Upstream tag changed since discovery")
    print(f"tag={source}\ncommit={sha}\nrepo={UPSTREAM}\nsnapshot=false\nsource_url=")


if __name__ == "__main__":
    main()
