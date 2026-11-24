import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from windows_unicode_probe import PACKAGE, fixture_env, invoke

with tempfile.TemporaryDirectory(prefix="scad-diagnostics-", dir=os.environ["RUNNER_TEMP"]) as tmp:
    root = Path(tmp)
    with zipfile.ZipFile("prior/dist/openscad-cli-windows-x86_64.zip") as archive:
        archive.extractall(root)
    executable = root / PACKAGE / "bin/openscad.exe"
    env = fixture_env(None)
    results = {}
    for case, model in {
        "cube": "cube([10,20,30]);",
        "mcad": "use <MCAD/boxes.scad>\nroundedBox([20,20,10],2,true);",
        "text": 'linear_extrude(1) text("CLI", size=4, font="Liberation Sans");',
        "smoke": 'use <MCAD/boxes.scad>\ndifference() { roundedBox([20,20,10],2,true); cylinder(h=30,r=4,center=true,$fn=32); }\ntranslate([0,0,5]) linear_extrude(1) text("CLI",size=4,font="Liberation Sans");',
    }.items():
        for suffix in ("ascii", "模型"):
            source = root / f"{case}-{suffix}.scad"
            source.write_text(model, encoding="utf-8")
            args = [executable, "--debug=all", "-o", root / "output.stl", source]
            result = invoke(args, root, env, 90, [(root, "<fixture>")])
            results[source.name] = result
            print(source.name, result["status"], result.get("exit"), flush=True)
    Path("input-report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    debugger = Path(os.environ["ProgramFiles(x86)"]) / "Windows Kits/10/Debuggers/x64/cdb.exe"
    if debugger.is_file():
        commands = root / "cdb.cmd"
        commands.write_text('sxe -c ".exr -1; k; gn" eh\ng\n.exr -1\nk\nq\n', encoding="ascii")
        with Path("cdb.log").open("wb") as log:
            subprocess.run([debugger, "-cf", commands, executable, "-o", root / "cdb.stl",
                            root / "mcad-模型.scad"], cwd=root, env=env, stdout=log,
                           stderr=subprocess.STDOUT, timeout=90, check=False)
