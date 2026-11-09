# OpenSCAD Preview Scene Exporter — macOS ARM64

The experimental Preview Exporter is an **extra archive in the same complete OpenSCAD CLI Release** for `openscad-2026.11-RC0`. Its upstream source is the official commit `9ba0cee7c94785fac0ca8dfe040b965a12a25ed1`. The canonical OpenSCAD checkout remains untouched.

## Reused OpenSCAD CPU code

The exporter calls official GeometryEvaluator, CSGTreeEvaluator, CSGTreeNormalizer, CSGProducts, and PolySetUtils tessellation. It exports source local operand geometry and normalized Boolean products, not a final F6 mesh or an OpenGL frame. WebGPU/WebGL2 still requires its own Boolean visibility rendering implementation.

The versioned `.csgp` format is JSON for initial validation. It includes shared triangle meshes, instance transforms (row-major), colors, convexity, and products/highlights/backgrounds with intersections and subtractions.

## Usage

Download the **Preview Exporter macOS ARM64** asset from the same [OpenSCAD 2026.11-RC0 CLI Release](https://github.com/peterisdev42/openscad-cli-builder/releases/tag/openscad-2026.11-RC0). After extracting:

    ./openscad-preview-exporter-macos-arm64/bin/openscad-preview-exporter -o model.csgp model.scad

Or:

    ./openscad-preview-exporter-macos-arm64/bin/openscad-preview-exporter --export-format=preview-scene -o model.csgp model.scad

## Unified build and release

`.github/workflows/openscad-cli.yml` selects `openscad-2026.11-RC0`, builds six normal CLI targets and compiles the Preview Exporter inside the same macOS ARM64 job. The separate CMake build directories prevent patches from altering normal CLI binaries. The pinned vcpkg dependency install is reused.

The single Release has 14 mandatory assets: six CLI archives, their six checksums, one Exporter archive and its checksum. The existing canonical YAML Release header identifies the upstream tag, version, channel and commit. Release publishing fails closed if the exporter package or any other required asset is absent or invalid.

Standalone Preview Exporter release publishing and one-time metadata repair scripts have been retired. The unified CLI workflow is the only supported publisher; the exporter build and package verification remain enabled.

## Local build

On Apple Silicon with the normal build prerequisites and checked-out official RC0 source:

    export TARGET=macos-arm64 TRIPLET=arm64-osx
    export OPENSCAD_TAG=openscad-2026.11-RC0
    export OPENSCAD_COMMIT=9ba0cee7c94785fac0ca8dfe040b965a12a25ed1
    python3 scripts/openscad-ci/build.py

Then build the additional package using the already installed vcpkg dependencies:

    export SCAD_PREVIEW_EXPORTER=1 SCAD_REUSE_VCPKG=1
    python3 scripts/openscad-ci/build.py
    python3 scripts/openscad-ci/preview_exporter/verify_release.py dist

## Limitations

- The only audited version is RC0; Preview Exporter is native macOS ARM64 only.
- OpenSCAD's own PolySetUtils triangulates polygonal faces (including cube quads).
- Nonfinite geometry, invalid triangle indices and missing source operands are errors.
- The exporter implements OpenSCAD F5 preparation semantics; Three.js GPU rendering parity still needs validation.
- Face-level color/material details, complex modifiers and degeneracies need broader parity testing before IDE integration.
- Upstream COPYING, dependency licenses and source provenance remain included in the archive.
