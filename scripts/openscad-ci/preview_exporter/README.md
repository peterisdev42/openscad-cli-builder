# OpenSCAD Preview Scene Exporter — macOS ARM64

This experimental exporter is built in the same Builder as the normal OpenSCAD CLI, but through an **independent workflow and release**. It is pinned to the official OpenSCAD tag **openscad-2026.11-RC0**, commit **9ba0cee7c94785fac0ca8dfe040b965a12a25ed1**. The canonical OpenSCAD source checkout is not modified.

## What is reused

The exporter calls official OpenSCAD C++ GeometryEvaluator, CSGTreeEvaluator, CSGTreeNormalizer and CSGProducts. It returns prepared local operand meshes and normalized Boolean products, **not** a final Boolean mesh and **not** an OpenGL/PNG frame.

- OpenSCAD performs the original SCAD parsing, instantiation, local geometry generation, transformations, normalization and CSG Product assembly.
- The adapter adds a preview-scene export format with suffix .csgp.
- Three.js needs to implement and verify its own compatible GPU CSG image-space operation, including depth, clipping, highlights and orientation.
- The format is JSON v1 for inspecting/validating the result; a later ABI-independent binary encoding can reuse the same semantics.

## Usage

After extracting the macOS ARM64 archive:

    ./openscad-preview-exporter-macos-arm64/bin/openscad-preview-exporter -o model.csgp model.scad

Or explicitly select the format:

    ./openscad-preview-exporter-macos-arm64/bin/openscad-preview-exporter --export-format=preview-scene -o model.csgp model.scad

The output contains:
- meshes: arrays of positions and triangle indices for shared PolySets.
- instances: mesh references, row-major transform matrices, RGBA colors and convexity.
- products, highlights, backgrounds: OpenSCAD-normalized products listing intersection and subtraction instance references and propagated flags.
- schemaVersion = 1; source metadata identifying the upstream OpenSCAD preparation stage.

## Build and publication

The independent workflow is .github/workflows/preview-exporter.yml. PR builds upload an artifact with a 14-day retention period. Manual dispatch on the default branch can publish a separate prerelease tagged preview-exporter-openscad-2026.11-RC0. The original CLI workflow and six-platform release assets do not depend on this exporter.

Local build on a provisioned Apple Silicon macOS host:

    export TARGET=macos-arm64 TRIPLET=arm64-osx
    export OPENSCAD_TAG=openscad-2026.11-RC0
    export OPENSCAD_COMMIT=9ba0cee7c94785fac0ca8dfe040b965a12a25ed1
    export SCAD_PREVIEW_EXPORTER=1
    python3 scripts/openscad-ci/build.py
    python3 scripts/openscad-ci/preview_exporter/verify_release.py dist

The build script tests a relocated binary against version, STL/PNG, Manifold/CGAL, and a real difference() model. For that model it checks that official Boolean subtractions, meshes and transforms survived export.

## Limitations

- The only audited version is RC0 and only native macOS ARM64 is available. Upstream C++ API changes fail closed.
- Every PolySet face must already be triangular; no unsafe fan triangulation is performed.
- Nonfinite geometry, empty referenced PolySets and broken source references are errors.
- The exporter follows OpenSCAD F5 / $preview semantics, not F6.
- Face-level color/material variations, unusual modifiers and degenerate geometry still require parity testing before IDE integration.
- This is **not yet connected to SCAD AI IDE** and does not assert identical frames to official OpenCSG.
- Upstream COPYING, dependency licenses and source-provenance metadata remain in the release.
