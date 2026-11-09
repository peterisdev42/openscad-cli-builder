#!/usr/bin/env python3
"""Shared machine-readable release metadata and publishing channel policy."""
import re

CHANNELS = frozenset(("stable", "rc", "test", "snapshot"))
HEADER_RE = re.compile(r"\A"+re.escape("```yaml\nschemaVersion: 1\n")+r".*?\n```\n\n",re.DOTALL)


def release_channel(tag, snapshot=False):
    if not re.fullmatch(r"openscad-\d{4}\.\d{2}(?:\.\d{2})?(?:-(?:TEST|RC)\d+|-snapshot)?", tag):
        raise ValueError(f"Unsupported OpenSCAD release tag: {tag}")
    if snapshot or tag.endswith("-snapshot"):
        return "snapshot"
    if re.search(r"-RC\d+$", tag):
        return "rc"
    if re.search(r"-TEST\d+$", tag):
        return "test"
    return "stable"


def yaml_release_header(version, channel, commit, repository="openscad/openscad", snapshot_url=None):
    if channel not in CHANNELS:
        raise ValueError(f"Unsupported release channel: {channel}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Upstream commit must be the full 40-character SHA")
    if not re.fullmatch(r"[0-9A-Za-z.-]+", version):
        raise ValueError("Unexpected version string")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Unexpected upstream repository")
    lines = [
        "```yaml",
        "schemaVersion: 1",
        f'version: "{version}"',
        f"channel: {channel}",
        "upstream:",
        f"  repository: {repository}",
        f"  commit: {commit}",
    ]
    if snapshot_url:
        if channel != "snapshot" or not snapshot_url.startswith("https://files.openscad.org/snapshots/"):
            raise ValueError("Unexpected official snapshot URL")
        lines.append(f"  snapshotUrl: {snapshot_url}")
    return "\n".join((*lines, "```"))


def with_release_header(body, version, channel, commit, snapshot_url=None):
    if body is None:
        body = ""
    remainder = HEADER_RE.sub("", body, count=1)
    return yaml_release_header(version, channel, commit, snapshot_url=snapshot_url) + "\n\n" + remainder
