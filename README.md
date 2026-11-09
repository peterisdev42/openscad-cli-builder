# openscad-cli-builder
Automated cross-platform builds of the OpenSCAD headless CLI.


## Experimental Preview Scene Exporter

The Builder additionally contains an **independent macOS ARM64** Preview Exporter job for the official OpenSCAD `openscad-2026.11-RC0` tag. It exports official CSGTreeEvaluator / CSGTreeNormalizer / CSGProducts data as a versioned `.csgp` Preview Scene, without affecting regular CLI/WASM package gates or releases.

Details, supported architecture and known limitations: [Preview Exporter](scripts/openscad-ci/preview_exporter/README.md).
