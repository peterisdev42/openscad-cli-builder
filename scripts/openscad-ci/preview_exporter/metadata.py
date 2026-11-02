"""Release description shared by Preview Exporter publishing and metadata repair.

Use the Builder's existing schemaVersion 1 YAML header rather than an exporter-only
format. This is a separate artifact, so its tag and asset names remain independent
from the ordinary OpenSCAD CLI release.
"""
import sys
from pathlib import Path

# This module is invoked both from the preview_exporter package (tests) and
# directly by publish.py in a GitHub Actions checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from release_metadata import release_channel, with_release_header
from preview_exporter.verify_release import ARCHIVE, RELEASE_TAG, SOURCE_COMMIT, SOURCE_TAG

REPOSITORY = "peterisdev42/openscad-cli-builder"
VERSION = SOURCE_TAG.removeprefix("openscad-")
CHANNEL = release_channel(SOURCE_TAG)
DOWNLOAD = f"https://github.com/{REPOSITORY}/releases/download/{RELEASE_TAG}/{ARCHIVE}"
BASE_NOTES = (
    f"Preview Scene schema v1; official source openscad/openscad@{SOURCE_COMMIT} "
    f"({SOURCE_TAG}). Only macOS ARM64. "
    "Independent of the OpenSCAD CLI/WASM releases."
)
TABLE_HEADING = "| OS | Architecture | Download URL | SHA256 |"
DOWNLOAD_TABLE = "\n".join((
    TABLE_HEADING,
    "| :---: | :---: | :---: | :---: |",
    f"| macOS | Apple Silicon (ARM64) | [{ARCHIVE}]({DOWNLOAD}) | "
    f"[{ARCHIVE}.sha256]({DOWNLOAD}.sha256) |",
))


def release_notes(body: str | None = None) -> str:
    """Add the canonical fenced YAML header, preserving existing description.

    Repeated invocations are idempotent: never duplicate the header or asset
    table, including when repairing an already published release.
    """
    description = BASE_NOTES if body is None else body
    description = with_release_header(description, VERSION, CHANNEL, SOURCE_COMMIT)
    if TABLE_HEADING not in description:
        description = description.rstrip() + "\n\n" + DOWNLOAD_TABLE + "\n"
    return description
