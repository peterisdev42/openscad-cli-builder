#!/usr/bin/env python3
"""Run the unpacked x64 Windows CLI against isolated Unicode path fixtures."""

import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile

SCHEMA = 1
CUBE = (10, 20, 30)
LIBRARY_VERSIONS = ((11, 7, 3), (13, 9, 5))
DEFAULT_TIMEOUT = 90
RC0_COMMIT = "9ba0cee7c94785fac0ca8dfe040b965a12a25ed1"
BASELINE_ZIP = "8e17ce1f39a6b32ad6c710076f86037a74fda27c4110c70f613c649945c7c436"
BASELINE_EXE = "d1c8cc1b86a8b08794429892d1247221831e19f00911560496abed5b5d010a01"
PACKAGE = "openscad-cli-windows-x86_64"


@dataclass(frozen=True)
class Case:
    id: str
    source: str = "source/main.scad"
    output: str = "out/output.stl"
    library: str | None = None
    cwd: str = "cwd"
    junction: bool = False
    relocate: bool = False


CASES = (
    Case("U01"),
    Case("U02", source="项目 A/main.scad"),
    Case("U03", output="项目 B/output.stl"),
    Case("U04", source="项目 A/main.scad", output="项目 B/output.stl"),
    Case("U05", source="source/模型.scad"),
    Case("U06", source="café model/main.scad"),
    Case("U07", source="模型🧀/main.scad"),
    Case("U08", library="中文库"),
    Case("U09", library="library🧀"),
    Case("U10", source="项目 A/main.scad", library="项目 A/.scad/lib"),
    Case("U11", source="项目 A/main.scad", library="项目 A/.scad/lib", junction=True),
    Case("U12", cwd="工作目录"),
    Case("U13", relocate=True),
    Case("U14", library="ascii-library"),
    Case("U15", output="out/输出🧀.stl"),
)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stl_bounds(data):
    count = struct.unpack_from("<I", data, 80)[0] if len(data) >= 84 else 0
    if count and len(data) == 84 + 50 * count:
        vertices = [face[i:i + 3] for face in struct.iter_unpack("<12fH", data[84:])
                    for i in (3, 6, 9)]
    else:
        lines = data.decode("ascii").strip().splitlines()
        if not lines or not lines[0].startswith("solid") or not lines[-1].startswith("endsolid"):
            raise ValueError("Malformed ASCII STL")
        vertices = [tuple(map(float, line.split()[1:])) for line in lines
                    if line.lstrip().startswith("vertex ")]
        count = sum(line.lstrip().startswith("facet normal ") for line in lines)
    if count < 12 or len(vertices) != count * 3 or any(
        len(vertex) != 3 or not all(map(math.isfinite, vertex)) for vertex in vertices
    ):
        raise ValueError("Missing or invalid STL triangles")
    axes = list(zip(*vertices))
    return [min(axis) for axis in axes], [max(axis) for axis in axes]


def exit_codes(code):
    unsigned = code & 0xFFFFFFFF
    signed = unsigned if unsigned < 0x80000000 else unsigned - 0x100000000
    return {"signed": signed, "unsigned": unsigned, "hex": f"0x{unsigned:08X}", "signal": None}


def evidence(data, paths):
    # Keep original bytes losslessly. Child paths use a disposable, synthetic
    # root, and the readable view replaces absolute fixture paths.
    data = data or b""
    decoded = data.decode("utf-8", errors="backslashreplace")
    for path, token in paths:
        decoded = decoded.replace(str(path), token).replace(path.as_posix(), token)
    return {"utf8": decoded, "base64": base64.b64encode(data).decode("ascii")}


def invoke(args, cwd, env, timeout, paths):
    try:
        result = subprocess.run(args, shell=False, cwd=cwd, env=env,
                                capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {"status": "timeout", "exception": type(exc).__name__, "timed_out": True,
                "exit": None, "stdout": evidence(exc.stdout, paths), "stderr": evidence(exc.stderr, paths)}
    except OSError as exc:
        return {"status": "launch_error", "exception": type(exc).__name__, "timed_out": False,
                "winerror": getattr(exc, "winerror", None), "errno": exc.errno, "exit": None}
    return {"status": "pass" if result.returncode == 0 else "nonzero_exit", "timed_out": False,
            "exit": exit_codes(result.returncode), "stdout": evidence(result.stdout, paths),
            "stderr": evidence(result.stderr, paths)}


def check_stl(result, output, expected):
    result["output"] = {"exists": output.is_file()}
    if output.is_file():
        data = output.read_bytes()
        result["output"].update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
    if result["status"] != "pass":
        return
    if not result["output"]["exists"]:
        result["status"] = "missing_stl"
        return
    try:
        low, high = stl_bounds(data)
    except ValueError as exc:
        result.update(status="invalid_stl", exception=type(exc).__name__)
        return
    result["output"]["bounds"] = [low, high]
    if low != [0, 0, 0] or high != list(expected):
        result["status"] = "wrong_geometry"


def create_junction(target, link, root):
    import _winapi

    _winapi.CreateJunction(os.fspath(target), os.fspath(link))
    info = link.lstat()
    resolved = link.resolve(strict=True)
    is_junction = info.st_reparse_tag == stat.IO_REPARSE_TAG_MOUNT_POINT
    if not is_junction or resolved != target.resolve(strict=True):
        raise RuntimeError("Fixture is not a junction to its designated target")
    return {"is_junction": is_junction, "realpath": resolved.relative_to(root).as_posix(),
            "lstat": {"mode": info.st_mode, "file_attributes": info.st_file_attributes,
                      "reparse_tag": info.st_reparse_tag}}


def fixture_env(library):
    blocked = {"OPENSCADPATH", "OPENSCAD_FONT_PATH", "FONTCONFIG_PATH", "FONTCONFIG_FILE"}
    env = {name: value for name, value in os.environ.items() if name.upper() not in blocked}
    system = Path(env["SystemRoot"])
    env["PATH"] = os.pathsep.join(map(str, (system / "System32", system)))
    env.update(LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="softpipe")
    if library:
        env["OPENSCADPATH"] = str(library)
    return env


def run_case(case, root, binary, version, timeout):
    root.mkdir()
    model, output, cwd = root / case.source, root / case.output, root / case.cwd
    library = root / case.library if case.library else None
    result = {"id": case.id, "fixture": vars(case), "runs": []}
    for directory in (model.parent, output.parent, cwd):
        directory.mkdir(parents=True, exist_ok=True)
    if library:
        physical = root / "physical-library" if case.junction else library
        physical.mkdir(parents=True)
        if case.junction:
            library.parent.mkdir(parents=True)
            result["junction"] = create_junction(physical, library, root)
        model.write_text("include <probe_dimensions.scad>\nuse <probe_module.scad>\n"
                         "library_shape(probe_dimensions);\n", encoding="utf-8")
        (physical / "probe_module.scad").write_text(
            "module library_shape(dimensions) { cube(dimensions); }\n", encoding="utf-8")
    else:
        model.write_text("cube([10,20,30]);\n", encoding="utf-8")

    if case.relocate:
        package = root / "包 directory 🧀"
        shutil.copytree(binary.parent.parent, package)
        binary = package / "bin/openscad.exe"
    paths = [(root, "<fixture>"), (binary.parent.parent, "<package>")]
    env = fixture_env(library)
    if case.relocate:
        check = invoke([binary, "--version"], cwd, env, timeout, paths)
        check["kind"] = "version"
        output_text = check.get("stdout", {}).get("utf8", "") + check.get("stderr", {}).get("utf8", "")
        actual_version = re.search(r"OpenSCAD version (\S+)", output_text)
        if check["status"] == "pass" and (not actual_version or (
            version and actual_version.group(1) != version
        )):
            check["status"] = "wrong_version"
        result["runs"].append(check)

    for dimensions in LIBRARY_VERSIONS if library else (CUBE,):
        if library:
            x, y, z = dimensions
            (physical / "probe_dimensions.scad").write_text(
                f"probe_dimensions = [{x},{y},{z}];\n", encoding="utf-8")
            if not (library / "probe_dimensions.scad").is_file():
                raise RuntimeError("Library fixture is not visible through OPENSCADPATH")
        output.unlink(missing_ok=True)
        check = invoke([binary, "-o", output, model], cwd, env, timeout, paths)
        check.update(kind="stl", expected_dimensions=list(dimensions))
        check_stl(check, output, dimensions)
        result["runs"].append(check)
        if check["status"] != "pass":
            break
    result["status"] = next((run["status"] for run in result["runs"] if run["status"] != "pass"), "pass")
    return result


def all_pass(cases):
    return [(case["id"], case["status"]) for case in cases] == [(case.id, "pass") for case in CASES]


def runner_info():
    git = shutil.which("git")
    git_version = subprocess.check_output([git, "--version"], text=True, timeout=10).strip() if git else None
    windows = sys.getwindowsversion()
    return {"os": "Windows", "windows_build": windows.build, "platform": platform.version(),
            "architecture": platform.machine(), "python": platform.python_version(), "git": git_version,
            "msvc_tools": os.environ.get("VCToolsVersion"), "image": os.environ.get("ImageOS"),
            "image_version": os.environ.get("ImageVersion"), "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"), "workflow_sha": os.environ.get("GITHUB_SHA")}


def run_probe(executable, output, archive=None, baseline=False, timeout=DEFAULT_TIMEOUT):
    report = {"schema": SCHEMA, "status": "not-run", "cases": []}
    try:
        if sys.platform != "win32" or platform.machine().upper() not in {"AMD64", "X86_64"}:
            report["reason"] = "Native Windows x64 is required"
            return False
        report["runner"] = runner_info()
        # A default TEMP containing a user's name is unsuitable for the ASCII control,
        # and raw child streams must not expose home directory names.
        base = Path(os.environ.get("RUNNER_TEMP") or
                    (Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Documents"))
        if not base.is_absolute() or not str(base.resolve()).isascii() or not base.is_dir():
            raise RuntimeError("An existing ASCII RUNNER_TEMP directory is required")
        with tempfile.TemporaryDirectory(prefix="scad-unicode-", dir=base) as directory:
            root = Path(directory).resolve()
            sentinel = root / "writable"
            sentinel.write_bytes(b"ok")
            if sentinel.read_bytes() != b"ok":
                raise RuntimeError("Cannot verify the ASCII fixture root")
            if archive:
                report["zip_sha256"] = sha256(archive)
                if baseline and report["zip_sha256"] != BASELINE_ZIP:
                    raise RuntimeError("Published RC0 ZIP checksum mismatch")
                with zipfile.ZipFile(archive) as stream:
                    stream.extractall(root / "archive")
                executable = root / "archive" / PACKAGE / "bin/openscad.exe"
            else:
                package = root / "package"
                shutil.copytree(executable.parent.parent, package)
                executable = package / "bin" / executable.name
            report["exe_sha256"] = sha256(executable)
            if baseline and report["exe_sha256"] != BASELINE_EXE:
                raise RuntimeError("Published RC0 EXE checksum mismatch")
            info = json.loads((executable.parent.parent / "build-info.json").read_text(encoding="utf-8"))
            report["build_info"] = info
            if baseline and (info["commit"] != RC0_COMMIT or info["tag"] != "openscad-2026.11-RC0"):
                raise RuntimeError("Published RC0 build provenance mismatch")
            for case in CASES:
                try:
                    result = run_case(case, root / case.id, executable, info["tag"].removeprefix("openscad-"), timeout)
                except (OSError, RuntimeError, ValueError) as exc:
                    result = {"id": case.id, "fixture": vars(case), "status": "fixture_error",
                              "exception": type(exc).__name__, "errno": getattr(exc, "errno", None),
                              "winerror": getattr(exc, "winerror", None)}
                report["cases"].append(result)
        report["status"] = "pass" if all_pass(report["cases"]) else "fail"
        return report["status"] == "pass"
    except Exception as exc:
        report["exception"] = type(exc).__name__
        if isinstance(exc, RuntimeError):
            report["reason"] = str(exc)
        return False
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--executable", type=Path)
    source.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true", help="Require the original public RC0 hashes")
    args = parser.parse_args()
    if args.baseline and not args.archive:
        parser.error("--baseline requires --archive")
    if args.executable and (not args.executable.is_absolute() or args.executable.name.lower() != "openscad.exe"):
        parser.error("--executable must be an absolute path to the unpacked bin/openscad.exe")
    return 0 if run_probe(args.executable, args.output, args.archive, args.baseline) else 1


if __name__ == "__main__":
    sys.exit(main())
