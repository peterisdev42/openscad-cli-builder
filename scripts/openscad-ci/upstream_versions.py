#!/usr/bin/env python3
"""Discover and resolve OpenSCAD upstream versions without trusting event input."""
import json
import os
import re
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from resolve_snapshot import SNAPSHOT_INDEX, download, parse_snapshot_metadata
from release_metadata import release_channel

UPSTREAM = "openscad/openscad"
TAG_RE = re.compile(r"openscad-(\d{4})\.(\d{2})(?:\.(\d{2}))?(?:-(RC|TEST)(\d+))?")
SHA_RE = re.compile(r"[0-9a-f]{40}")
PINNED = {
    "openscad-2021.01": "41f58fe57c03457a3a8b4dc541ef5654ec3e8c78",
    "openscad-2026.10-TEST4": "5a864f17b6b022904004704f64e6168d2cfb8435",
    "openscad-2026.11-RC0": "9ba0cee7c94785fac0ca8dfe040b965a12a25ed1",
}


def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "openscad-cli-builder"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urlopen(Request("https://api.github.com/" + path, headers=headers), timeout=60) as response:
        return json.load(response)


def release_by_tag(repository, tag):
    """Only a real 404 means absent; fail closed on transport/auth failures."""
    if not TAG_RE.fullmatch(tag):
        raise ValueError("Unsupported release lookup tag: " + tag)
    try:
        return api(f"repos/{repository}/releases/tags/{tag}")
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def parse_remote_tags(output):
    tags, peeled = {}, {}
    for line in output.splitlines():
        sha, ref = line.split("\t")
        if not ref.startswith("refs/tags/") or not SHA_RE.fullmatch(sha):
            continue
        tag = ref[len("refs/tags/"):]
        target = peeled if tag.endswith("^{}") else tags
        tag = tag.removesuffix("^{}")
        if TAG_RE.fullmatch(tag):
            target[tag] = sha
    return {tag: peeled.get(tag, sha) for tag, sha in tags.items()}


def remote_tags():
    return parse_remote_tags(subprocess.check_output(
        ["git", "ls-remote", "--tags", "https://github.com/" + UPSTREAM + ".git"],
        text=True, timeout=90))


def tag_key(tag):
    m = TAG_RE.fullmatch(tag)
    if not m:
        raise ValueError("Unsupported upstream tag: " + tag)
    return tuple(int(m.group(i) or 0) for i in (1, 2, 3, 5))


def latest_stable():
    result = api("repos/" + UPSTREAM + "/releases/latest")
    tag = result["tag_name"]
    if result.get("draft") or result.get("prerelease") or not TAG_RE.fullmatch(tag) or release_channel(tag) != "stable":
        raise ValueError("Invalid stable release")
    return tag


def resolve_tag(tag, tags):
    if not TAG_RE.fullmatch(tag) or tag not in tags:
        raise ValueError("Unknown or unsupported upstream tag: " + tag)
    sha = tags[tag]
    if not SHA_RE.fullmatch(sha) or (tag in PINNED and PINNED[tag] != sha):
        raise ValueError("Invalid or changed upstream commit for " + tag)
    return sha


def discover(tags, stable, snapshot):
    candidates = [{"channel": "stable", "tag": stable, "commit": resolve_tag(stable, tags)}]
    for channel in ("rc", "test"):
        matches = [tag for tag in tags if release_channel(tag) == channel]
        if matches:
            tag = max(matches, key=tag_key)
            candidates.append({"channel": channel, "tag": tag, "commit": resolve_tag(tag, tags)})
    version, url, _ = snapshot
    candidates.append({"channel": "snapshot", "tag": "openscad-" + version, "url": url})
    return candidates


def snapshot_metadata():
    return parse_snapshot_metadata(download(SNAPSHOT_INDEX).decode("utf-8"))
