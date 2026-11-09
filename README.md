# openscad-cli-builder
Automated cross-platform builds of the OpenSCAD headless CLI.

## OpenSCAD 2026.11-RC0: CLI + Preview Exporter

The regular [OpenSCAD CLI workflow](.github/workflows/openscad-cli.yml) builds and publishes **one release** under `openscad-2026.11-RC0` with:

- All six original OpenSCAD CLI archives (macOS x64/ARM64, Windows x64, Linux x64/ARM64, Node.js/WASM) and their SHA256 checksums.
- One additional native **macOS ARM64 Preview Exporter** archive (`openscad-preview-exporter-macos-arm64.tar.gz`) and its checksum.

The Preview Exporter is built in the existing macOS ARM64 job, using the **same pinned upstream commit** and installed vcpkg dependencies but a separate copied source / CMake build tree. If any of the 14 required assets is missing or fails validation, the unified RC0 release is not published. Other OpenSCAD tags continue to produce their original 12 assets.

The old standalone Preview Exporter workflow has been retired. See [Preview Exporter](scripts/openscad-ci/preview_exporter/README.md) for usage and integration notes.
