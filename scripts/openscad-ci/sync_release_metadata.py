#!/usr/bin/env python3
"""One-time, metadata-only reconciliation of previously published OpenSCAD CLI releases.

Changes release descriptions, prerelease status, and the Latest pointer.
Never rebuilds, downloads, uploads, deletes, or renames release assets.
"""
import argparse
import json
import os
import subprocess

from release_metadata import release_channel, with_release_header

RELEASES = {
    "openscad-2021.01": {
        "commit": "41f58fe57c03457a3a8b4dc541ef5654ec3e8c78",
        "channel": "stable",
    },
    "openscad-2026.10-TEST4": {
        "commit": "5a864f17b6b022904004704f64e6168d2cfb8435",
        "channel": "test",
    },
    "openscad-2026.10.27": {
        "commit": "362da9e62fe71f6160a16ec96946db6cec3f77ee",
        "channel": "snapshot",
        "snapshot_url": "https://files.openscad.org/snapshots/OpenSCAD-2026.10.27-x86_64.AppImage",
    },
}
ASSET_NAMES = {
    f"openscad-cli-{platform}.{extension}{suffix}"
    for platform, extension in (
        ("macos-arm64", "tar.gz"),
        ("macos-x86_64", "tar.gz"),
        ("windows-x86_64", "zip"),
        ("linux-x86_64", "tar.gz"),
        ("linux-arm64", "tar.gz"),
        ("wasm", "tar.gz"),
    )
    for suffix in ("", ".sha256")
}


def gh_api(repository, path, payload=None):
    command = ["gh", "api", f"repos/{repository}/{path}"]
    if payload is not None:
        command += ["--method", "PATCH", "--input", "-"]
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            stdout=subprocess.PIPE, text=True, check=True)
    return json.loads(result.stdout)


def target(release):
    tag = release["tag_name"]
    config = RELEASES[tag]
    if release.get("draft"):
        raise RuntimeError(f"Cannot migrate a draft release: {tag}")
    names = {asset["name"] for asset in release["assets"]}
    if names != ASSET_NAMES or len(release["assets"]) != len(ASSET_NAMES):
        raise RuntimeError(f"Asset list mismatch, refusing to edit: {tag}")
    version = tag.removeprefix("openscad-")
    channel = config["channel"]
    if tag != "openscad-2026.10.27" and release_channel(tag) != channel:
        raise RuntimeError(f"Channel mismatch: {tag}")
    body = with_release_header(release["body"], version, channel,
                               config["commit"], config.get("snapshot_url"))
    return {
        "body": body,
        "prerelease": channel != "stable",
        "make_latest": "true" if channel == "stable" else "false",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually update GitHub releases")
    args = parser.parse_args()
    repository = os.environ["GITHUB_REPOSITORY"]
    if repository != "peterisdev42/openscad-cli-builder":
        raise RuntimeError("This migration is scoped to peterisdev42/openscad-cli-builder")
    releases = gh_api(repository, "releases?per_page=100")
    found = {r["tag_name"]: r for r in releases if r["tag_name"] in RELEASES}
    if set(found) != set(RELEASES):
        raise RuntimeError(f"Missing expected releases: {set(RELEASES) - set(found)}")
    updates = {tag: target(found[tag]) for tag in RELEASES}
    order = ("openscad-2026.10.27", "openscad-2026.10-TEST4", "openscad-2021.01")
    for tag in order:
        release = found[tag]
        payload = updates[tag]
        print(f"{'Updating' if args.apply else 'Would update'} {tag} "
              f"(prerelease={payload['prerelease']}, latest={payload['make_latest']}); "
              f"assets preserved={len(release['assets'])}", flush=True)
        if args.apply:
            actual = gh_api(repository, f"releases/{release['id']}", payload)
            if (actual["tag_name"] != tag or actual["body"] != payload["body"]
                    or actual["prerelease"] != payload["prerelease"]
                    or {asset["name"] for asset in actual["assets"]} != ASSET_NAMES):
                raise RuntimeError(f"Release verification failed: {tag}")
    if args.apply:
        latest = gh_api(repository, "releases/latest")
        if latest["tag_name"] != "openscad-2021.01":
            raise RuntimeError(f"Latest points to {latest['tag_name']}, not stable")
        print("All release metadata verified; latest is openscad-2021.01", flush=True)


if __name__ == "__main__":
    main()
