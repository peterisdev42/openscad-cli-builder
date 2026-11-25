# openscad-cli-builder
Automated cross-platform builds of the OpenSCAD headless CLI.

## OpenSCAD 2026.11-RC0: CLI + Preview Exporter

The regular [OpenSCAD CLI workflow](.github/workflows/openscad-cli.yml) builds and publishes **one release** under `openscad-2026.11-RC0` with:

- All six original OpenSCAD CLI archives (macOS x64/ARM64, Windows x64, Linux x64/ARM64, Node.js/WASM) and their SHA256 checksums.
- One additional native **macOS ARM64 Preview Exporter** archive (`openscad-preview-exporter-macos-arm64.tar.gz`) and its checksum.

The Preview Exporter is built in the existing macOS ARM64 job, using the **same pinned upstream commit** and installed vcpkg dependencies but a separate copied source / CMake build tree. If any of the 14 required assets is missing or fails validation, the unified RC0 release is not published. Other OpenSCAD tags continue to produce their original 12 assets.

The old standalone Preview Exporter workflow has been retired. See [Preview Exporter](scripts/openscad-ci/preview_exporter/README.md) for usage and integration notes.

## Upstream discovery

The submodule and build checkouts use `openscad/openscad`. Manual builds
accept an official tag, `latest-stable`, or
`latest-snapshot`. All build jobs consume the resolved immutable commit.

Run **Discover Upstream OpenSCAD** manually with `dispatch_builds` unchecked
to inspect the latest stable (GitHub Releases), RC and TEST (official Git
tags), and Snapshot (official website metadata) together. Check
`dispatch_builds` to request all missing latest-channel releases. Existing
release metadata is compared before dispatch; conflicts require manual review.
Active or queued builds suppress only their own version; other channels can
build concurrently. Historical versions are not backfilled.
A snapshot that advances between discovery and resolution fails safely.
Source resource layout and patch compatibility are checked before native builds.
Newer upstream versions without bundled MCAD use an empty libraries directory
and a local smoke-test fixture. Older versions retain bundled MCAD testing.
Vcpkg downloads are cached; install is retried up to three times with the
original archive hashes unchanged. Orphaned release records are detected by
an additional direct tag lookup and require manual review.

After successful manual discovery and end-to-end dispatched builds, uncomment
the schedule in `.github/workflows/discover-upstream.yml` to run daily at
00:00 UTC. Schedule runs automatically dispatch missing releases. No external
PAT or service is required.
