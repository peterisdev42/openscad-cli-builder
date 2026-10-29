#!/usr/bin/env python3
"""Resolve the OpenSCAD website's Linux x64 development snapshot to an immutable commit."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SNAPSHOT_INDEX = "https://files.openscad.org/snapshots/.snapshots.js"
GITHUB_COMMITS = "https://api.github.com/repos/openscad/openscad/commits/"


def download(url, destination=None):
    request = Request(url, headers={"User-Agent": "openscad-cli-builder"})
    with urlopen(request, timeout=90) as response:
        if destination is None:
            return response.read()
        with open(destination, "wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)


def parse_snapshot_metadata(js):
    match = re.search(
        r"""setSnapshotFileInfo\(\s*['"]LIN64_SNAPSHOT['"]\s*,\s*['"][^'"]*['"]\s*,\s*['"][^'"]*['"]\s*,\s*['"]([^'"]+)['"]\s*\)""",
        js,
    )
    if not match:
        raise ValueError("Official snapshot metadata has no Linux x64 AppImage")
    url = match.group(1)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "files.openscad.org" or not parsed.path.startswith("/snapshots/"):
        raise ValueError("Unexpected official snapshot URL")
    basename = Path(parsed.path).name
    version_match = re.fullmatch(r"OpenSCAD-(20\d{2}\.\d{2}\.\d{2})(?:\.[A-Za-z0-9]+)?-x86_64\.AppImage", basename)
    if not version_match:
        raise ValueError(f"Unexpected snapshot filename: {basename}")
    return version_match.group(1), url, basename


def parse_checksum(data, basename):
    lines = data.splitlines()
    for line in lines:
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(\S+)", line.strip())
        if match and match.group(2) == basename:
            return match.group(1).lower()
    raise ValueError("Missing matching official SHA256 checksum")


def parse_version_info(output, expected_version):
    match = re.search(
        r"^OpenSCAD Version:\s*(\d{4}\.\d{2}\.\d{2})[^\r\n]*?\(git\s+([0-9a-fA-F]{7,40})\)",
        output,
        re.MULTILINE | re.IGNORECASE,
    )
    if not match:
        raise ValueError("Cannot determine source commit from official AppImage --info")
    if match.group(1) != expected_version:
        raise ValueError(f"Official snapshot version mismatch: expected {expected_version}, got {match.group(1)}")
    return match.group(2).lower()


def resolve_commit(short_sha):
    headers = {"User-Agent": "openscad-cli-builder", "Accept": "application/vnd.github+json"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urlopen(Request(GITHUB_COMMITS + short_sha, headers=headers), timeout=60) as response:
        result = json.load(response)
    sha = result.get("sha", "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not sha.startswith(short_sha):
        raise ValueError("GitHub returned an inconsistent source commit")
    return sha


def main():
    version, url, basename = parse_snapshot_metadata(download(SNAPSHOT_INDEX).decode("utf-8"))
    with tempfile.TemporaryDirectory(prefix="openscad-upstream-snapshot-") as folder:
        folder = Path(folder)
        appimage = folder / basename
        print(f"Downloading upstream OpenSCAD snapshot {version}: {url}", file=sys.stderr)
        expected_hash = parse_checksum(download(url + ".sha256").decode("ascii"), basename)
        download(url, appimage)
        actual_hash = hashlib.file_digest(open(appimage, "rb"), "sha256").hexdigest()
        if actual_hash != expected_hash:
            raise ValueError("Official AppImage SHA256 mismatch")
        appimage.chmod(0o755)
        subprocess.run([str(appimage), "--appimage-extract"], cwd=folder, check=True,
                       stdout=subprocess.DEVNULL)
        apprun = folder / "squashfs-root" / "AppRun"
        if not apprun.is_file():
            raise FileNotFoundError("Official AppImage has no AppRun")
        environment = os.environ.copy()
        environment["LIBGL_ALWAYS_SOFTWARE"] = "1"
        result = subprocess.run(["xvfb-run", "-a", str(apprun), "--info"], cwd=folder,
                                env=environment, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=120)
        short_sha = parse_version_info(result.stdout, version)
        full_sha = resolve_commit(short_sha)
    print(f"Resolved official OpenSCAD snapshot {version} to {full_sha}", file=sys.stderr)
    print(f"tag=openscad-{version}")
    print(f"commit={full_sha}")
    print("repo=openscad/openscad")
    print("snapshot=true")
    print(f"source_url={url}")


if __name__ == "__main__":
    main()
