#!/usr/bin/env python3
"""Publish the pinned macOS ARM64 Exporter only after remote asset round-trip.

This is deliberately independent of normal OpenSCAD CLI releases.
Published tags/assets are immutable: rerunning will not clobber an existing release.
An interrupted *draft* may be resumed safely.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from verify_release import ARCHIVE, RELEASE_TAG, SOURCE_COMMIT, SOURCE_TAG, verify

TITLE = "OpenSCAD Preview Exporter 2026.11-RC0 · macOS ARM64"
NOTES = (
    f"Preview Scene schema v1; official source openscad/openscad@{SOURCE_COMMIT} "
    f"({SOURCE_TAG}). Only macOS ARM64. "
    "Independent of the OpenSCAD CLI/WASM releases."
)


def gh(*args, check=True):
    return subprocess.run(["gh", *args], check=check, text=True, capture_output=True)


def release_snapshot():
    result = gh("release", "view", RELEASE_TAG, "--json", "isDraft,body", check=False)
    if result.returncode != 0:
        # Do not confuse authentication/network failure with a missing release.
        # The only safe missing-release case is that GitHub returned 404.
        # The CLI's message can vary; resolve existence through the REST API.
        response = gh("api", "-i", f"repos/{os.environ['GITHUB_REPOSITORY']}/releases/tags/{RELEASE_TAG}", check=False)
        combined = response.stdout + "\n" + response.stderr
        if "404 Not Found" not in combined and '"status": "404"' not in combined:
            raise RuntimeError(f"Unable to inspect existing release: {combined[-1000:]}")
        return None
    return json.loads(result.stdout)


def publish(directory: Path):
    directory = Path(directory)
    local_hash = verify(directory)
    builder_sha = os.environ["GITHUB_SHA"]
    if len(builder_sha) != 40:
        raise RuntimeError("Missing immutable builder commit SHA")
    existing = release_snapshot()
    if existing:
        if not existing["isDraft"]:
            raise RuntimeError("Release is already published: refusing to overwrite or silently replace assets")
        if SOURCE_COMMIT not in existing.get("body", ""):
            raise RuntimeError("Existing draft does not match pinned upstream; refusing to clobber")
    else:
        # Prevent attaching to a tag created by another release/build.
        ref = gh("api", "-i", f"repos/{os.environ['GITHUB_REPOSITORY']}/git/ref/tags/{RELEASE_TAG}", check=False)
        combined = ref.stdout + "\n" + ref.stderr
        if ref.returncode == 0:
            raise RuntimeError("Release tag already exists without a matching draft; refusing to reuse it")
        if "404 Not Found" not in combined and '"status": "404"' not in combined:
            raise RuntimeError(f"Unable to verify tag availability: {combined[-1000:]}")
        gh("release", "create", RELEASE_TAG,
           "--draft", "--prerelease", "--latest=false",
           "--target", builder_sha,
           "--title", TITLE, "--notes", NOTES)
    gh("release", "upload", RELEASE_TAG,
       str(directory / ARCHIVE), str(directory / (ARCHIVE + ".sha256")), "--clobber")
    # Validate bytes actually served by GitHub, not merely the input files.
    with tempfile.TemporaryDirectory(prefix="preview-exporter-release-verify-") as tmp:
        gh("release", "download", RELEASE_TAG, "--pattern", ARCHIVE + "*", "--dir", tmp)
        remote_hash = verify(Path(tmp))
        if remote_hash != local_hash:
            raise RuntimeError("Downloaded release archive differs from the verified local archive")
    # Only now make the release public. A failure above leaves a retriable draft.
    gh("release", "edit", RELEASE_TAG,
       "--draft=false", "--prerelease", "--latest=false",
       "--title", TITLE, "--notes", NOTES)
    print(f"Published verified {RELEASE_TAG}: {local_hash}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: publish.py <dist-dir>")
    publish(Path(sys.argv[1]))
