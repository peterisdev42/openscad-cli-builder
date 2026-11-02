#!/usr/bin/env python3
"""Repair ONLY the body of the published RC0 Preview Exporter release.

No builds, asset upload/download/replacement, tag changes, or Latest changes.
The existing release is protected by exact tag/source/asset assertions.
"""
import argparse
import json
import os
import subprocess

from preview_exporter.metadata import REPOSITORY, release_notes
from preview_exporter.verify_release import ARCHIVE, RELEASE_TAG, SOURCE_COMMIT

EXPECTED_ASSETS = {ARCHIVE, ARCHIVE + ".sha256"}


def target(release: dict) -> str:
    if release.get("tag_name") != RELEASE_TAG:
        raise RuntimeError("Wrong Preview Exporter release tag; refusing to modify")
    if release.get("draft") is not False or release.get("prerelease") is not True:
        raise RuntimeError("Unexpected release status; refusing to modify")
    assets = release.get("assets")
    if not isinstance(assets, list) or len(assets) != 2 or {a.get("name") for a in assets} != EXPECTED_ASSETS:
        raise RuntimeError("Release asset list changed; refusing to modify")
    if any(not isinstance(a.get("id"), int) or a.get("size", 0) <= 0 for a in assets):
        raise RuntimeError("Release asset IDs/sizes invalid")
    body = release.get("body")
    if not isinstance(body, str) or SOURCE_COMMIT not in body:
        raise RuntimeError("Release does not identify expected upstream commit")
    return release_notes(body)


def gh_api(path: str, payload: dict | None = None) -> dict:
    command = ["gh", "api", f"repos/{REPOSITORY}/{path}"]
    if payload is not None:
        command.extend(["--method", "PATCH", "--input", "-"])
    result = subprocess.run(
        command, input=json.dumps(payload) if payload is not None else None,
        text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout)


def run(apply: bool) -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise RuntimeError("Refusing to modify a different repository")
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("Repair must run from the default branch")
    before = gh_api(f"releases/tags/{RELEASE_TAG}")
    expected_body = target(before)
    if before["body"] == expected_body:
        print("Preview Exporter Release YAML header already correct; no update needed")
        return
    if not apply:
        print("Would repair Preview Exporter Release body only; leaving tags/assets unchanged")
        return

    # Only the description is patched; never touch tag, prerelease, Latest,
    # target commitish, assets, or release title.
    updated = gh_api(f"releases/{before['id']}", {"body": expected_body})
    after = gh_api(f"releases/tags/{RELEASE_TAG}")
    if updated.get("body") != expected_body or after.get("body") != expected_body:
        raise RuntimeError("Release body post-update verification failed")
    for key in ("tag_name", "draft", "prerelease", "name", "target_commitish"):
        if after.get(key) != before.get(key):
            raise RuntimeError(f"Unexpected Release field changed: {key}")
    original_assets = {(a["id"], a["name"], a["size"]) for a in before["assets"]}
    current_assets = {(a["id"], a["name"], a["size"]) for a in after["assets"]}
    if original_assets != current_assets:
        raise RuntimeError("Release assets changed unexpectedly during metadata repair")
    print(f"Updated and verified YAML header of {RELEASE_TAG}; preserved two original assets")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Patch the published body after validation")
    args = parser.parse_args()
    run(apply=args.apply)
