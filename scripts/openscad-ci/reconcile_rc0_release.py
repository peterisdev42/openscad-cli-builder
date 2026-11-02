#!/usr/bin/env python3
"""Repair only the published RC0 Release description; never rebuild or edit assets.

The standard release.py remains the single source of truth for future releases.
This script is intentionally pinned to the already-verified 14-asset RC0 Release.
"""
import argparse
import json
import os
import subprocess

from release import PREVIEW_EXPORTER_ASSET, RELEASE_TAG, SOURCE_COMMIT, SOURCE_TAG
from release import release_assets, release_notes
from release_metadata import yaml_release_header

REPOSITORY = "peterisdev42/openscad-cli-builder"
EXPECTED_TAG = "openscad-2026.11-RC0"
EXPECTED_COMMIT = "9ba0cee7c94785fac0ca8dfe040b965a12a25ed1"
OLD_ROW = "| macOS (Preview Exporter) | Apple Silicon (ARM64) |"
NEW_ROW = "| macOS | Apple Silicon |"
OLD_NOTE = (
    "Additional macOS ARM64 Preview Exporter: "
    "run `bin/openscad-preview-exporter -o model.csgp model.scad` "
    "to produce Prepared CSG Scene schema v1 using the official "
    "OpenSCAD geometry and CSG normalizer. "
    "This is a separate archive in this same OpenSCAD release, "
    "not a second Release/Tag."
)


def target(release: dict) -> str:
    if SOURCE_TAG != EXPECTED_TAG or RELEASE_TAG != EXPECTED_TAG or SOURCE_COMMIT != EXPECTED_COMMIT:
        raise RuntimeError("Release generator not pinned to official OpenSCAD 2026.11-RC0")
    if (release.get("tag_name") != EXPECTED_TAG
            or release.get("draft") is not False
            or release.get("prerelease") is not True):
        raise RuntimeError("Refusing to modify another Release or unexpected release state")
    assets = release.get("assets")
    expected = set(release_assets())
    if not isinstance(assets, list) or len(assets) != 14 or expected != {a.get("name") for a in assets}:
        raise RuntimeError("Expected all 14 original assets, refusing to update release")
    if not all(isinstance(a.get("id"), int) and a.get("size", 0) > 0 for a in assets):
        raise RuntimeError("Invalid Release asset ID or size")
    body = release.get("body")
    header = yaml_release_header("2026.11-RC0", "rc", EXPECTED_COMMIT)
    if not isinstance(body, str) or not body.startswith(header + "\n\n"):
        raise RuntimeError("Release YAML upstream provenance mismatch")
    canonical = release_notes(REPOSITORY)
    if body == canonical:
        return body
    if body.count(OLD_ROW) != 1 or body.count(OLD_NOTE) != 1:
        raise RuntimeError("Existing Release description differs from audited source")
    old_archive = PREVIEW_EXPORTER_ASSET
    download_row = next(line for line in canonical.splitlines()
                        if f"[{old_archive}]" in line)
    new_note_marker = "Preview Exporter (macOS Apple Silicon only):"
    if canonical.count(new_note_marker) != 1:
        raise RuntimeError("Release note generator failed to produce new description")
    new_note = new_note_marker + canonical.split(new_note_marker, 1)[1]
    original_row = next(line for line in body.splitlines() if OLD_ROW in line)
    corrected = body.replace(original_row, download_row, 1).replace(OLD_NOTE, new_note, 1)
    if corrected != canonical:
        raise RuntimeError("Refusing to overwrite unexpected differences in release description")
    return corrected


def gh_api(path: str, payload: dict | None = None) -> dict:
    command = ["gh", "api", f"repos/{REPOSITORY}/{path}"]
    if payload is not None:
        command.extend(["--method", "PATCH", "--input", "-"])
    result = subprocess.run(command, text=True, capture_output=True, check=True,
                            input=json.dumps(payload) if payload is not None else None)
    return json.loads(result.stdout)


def run(apply: bool) -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise RuntimeError("RC0 metadata repair must run on the expected repository's main branch")
    before = gh_api("releases/tags/" + EXPECTED_TAG)
    expected = target(before)
    if expected == before["body"]:
        print("Release description already correct; no changes needed")
        return
    if not apply:
        print("Would update OS/Architectures labels and Preview Exporter note only")
        return
    gh_api("releases/" + str(before["id"]), {"body": expected})
    after = gh_api("releases/tags/" + EXPECTED_TAG)
    if after.get("body") != expected:
        raise RuntimeError("Published Release description does not match generated notes")
    for field in ("id", "tag_name", "name", "draft", "prerelease", "target_commitish"):
        if before.get(field) != after.get(field):
            raise RuntimeError("Release identity changed unexpectedly: " + field)
    prior = {(a["id"], a["name"], a["size"]) for a in before["assets"]}
    actual = {(a["id"], a["name"], a["size"]) for a in after["assets"]}
    if actual != prior:
        raise RuntimeError("Release assets changed during metadata-only repair")
    print("Updated RC0 Release description; verified all 14 original assets unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run(apply=args.apply)
