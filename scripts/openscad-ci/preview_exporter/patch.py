#!/usr/bin/env python3
"""Inject the optional native Preview Scene exporter into a COPY of upstream source.

This adapter is deliberately never applied by the standard CLI/WASM builders.
All anchors are checked so an upstream API change fails closed rather than
silently distributing an incomplete or incorrectly normalized Preview Scene.
"""
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent


def replace_once(path, old, new):
    content = path.read_text()
    if content.count(old) != 1:
        raise RuntimeError(f"Unsupported upstream Preview Exporter API in {path}: expected one {old!r}")
    path.write_text(content.replace(old, new, 1))


def patch_preview_exporter(source: Path):
    source = Path(source)
    header = source / "src/preview_scene_exporter.h"
    if header.exists():
        raise RuntimeError("Preview Exporter already patched")
    shutil.copyfile(HERE / "preview_scene_exporter.h", header)

    replace_once(
        source / "src/io/export.h",
        "  TERM,\n  ECHO,",
        "  TERM,\n  PREVIEW_SCENE,\n  ECHO,",
    )
    replace_once(
        source / "src/io/export.cc",
        '    add_item(*containers, {FileFormat::TERM, "term", "term", "term"});',
        '    add_item(*containers, {FileFormat::TERM, "term", "term", "term"});\n'
        '    add_item(*containers, {FileFormat::PREVIEW_SCENE, "preview-scene", "csgp", "Prepared CSG Preview Scene"});',
    )
    # The CLI uses the output suffix as an identifier when --export-format is
    # omitted. Register csgp explicitly, not just the preview-scene identifier.
    replace_once(
        source / "src/io/export.cc",
        '    containers->identifierToInfo["stl"] = containers->identifierToInfo["asciistl"];',
        '    containers->identifierToInfo["stl"] = containers->identifierToInfo["asciistl"];\n'
        '    containers->identifierToInfo["csgp"] = containers->identifierToInfo["preview-scene"];',
    )
    replace_once(
        source / "src/io/export.cc",
        "format == FileFormat::ECHO || format == FileFormat::TERM || format == FileFormat::PNG);",
        "format == FileFormat::ECHO || format == FileFormat::TERM ||\n"
        "           format == FileFormat::PREVIEW_SCENE || format == FileFormat::PNG);",
    )
    replace_once(
        source / "src/openscad.cc",
        '#include "core/CSGTreeEvaluator.h"',
        '#include "core/CSGTreeEvaluator.h"\n#include "preview_scene_exporter.h"',
    )
    replace_once(
        source / "src/openscad.cc",
        "  } else if (export_format == FileFormat::ECHO) {\n    // echo -> don't need to evaluate any geometry",
        "  } else if (export_format == FileFormat::PREVIEW_SCENE) {\n"
        "    const bool wrote = with_output(cmd.is_stdout, filename_str, [&tree, root_node](std::ostream& stream) {\n"
        "      scad_preview_exporter::exportScene(tree, *root_node, stream);\n"
        "    });\n"
        "    if (!wrote) return 1;\n"
        "  } else if (export_format == FileFormat::ECHO) {\n    // echo -> don't need to evaluate any geometry",
    )
