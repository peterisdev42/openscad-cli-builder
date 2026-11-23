import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import windows_unicode_probe as probe


class WindowsUnicodeTest(unittest.TestCase):
    def test_controlled_path_variations(self):
        cases = {case.id: case for case in probe.CASES}
        self.assertEqual(cases["U02"].output, cases["U01"].output)
        self.assertEqual(cases["U03"].source, cases["U01"].source)
        self.assertFalse(cases["U02"].source.isascii())
        self.assertFalse(cases["U03"].output.isascii())
        self.assertEqual(cases["U10"].library, cases["U11"].library)
        self.assertTrue(cases["U11"].junction)
        self.assertEqual(cases["U12"].source, cases["U01"].source)
        self.assertFalse(cases["U12"].cwd.isascii())
        self.assertTrue(cases["U13"].relocate)

    def test_windows_environment_uses_uppercase_copied_keys(self):
        with patch.dict(probe.os.environ, {"SYSTEMROOT": "windows", "OpEnScAdPaTh": "ambient"}, clear=True):
            environment = probe.fixture_env(None)
        self.assertNotIn("OPENSCADPATH", environment)
        self.assertEqual(environment["PATH"].split(probe.os.pathsep)[0], str(Path("windows/System32")))

    def test_unsigned_windows_status_is_preserved(self):
        self.assertEqual(probe.exit_codes(3221226505),
                         {"signed": -1073740791, "unsigned": 3221226505,
                          "hex": "0xC0000409", "signal": None})

    def test_timeout_keeps_original_bytes_and_avoids_shell(self):
        command = ["openscad.exe", "模型🧀.scad"]
        with patch.object(probe.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired(command, 1, stderr=b"\xff")) as run:
            result = probe.invoke(command, Path("cwd"), {}, 1, [])
        run.assert_called_once_with(command, shell=False, cwd=Path("cwd"), env={},
                                    capture_output=True, timeout=1)
        self.assertEqual(result["status"], "timeout")
        self.assertIsNone(result["exit"])
        self.assertEqual(result["stderr"]["base64"], "/w==")

    def test_launch_error_fails(self):
        with patch.object(probe.subprocess, "run", side_effect=FileNotFoundError(2, "missing")):
            result = probe.invoke(["openscad.exe"], Path("cwd"), {}, 1, [])
        self.assertEqual(result["status"], "launch_error")
        self.assertEqual(result["exception"], "FileNotFoundError")

    def test_stl_evidence_detects_missing_empty_and_wrong_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output.stl"
            result = {"status": "pass"}
            probe.check_stl(result, output, probe.CUBE)
            self.assertEqual(result["status"], "missing_stl")
            output.touch()
            result = {"status": "pass"}
            probe.check_stl(result, output, probe.CUBE)
            self.assertEqual(result["status"], "invalid_stl")

            face = struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 10, 0, 30, 10, 20, 0, 0)
            output.write_bytes(bytes(80) + struct.pack("<I", 12) + face * 12)
            result = {"status": "pass"}
            probe.check_stl(result, output, (11, 20, 30))
            self.assertEqual(result["status"], "wrong_geometry")
            result = {"status": "pass"}
            probe.check_stl(result, output, probe.CUBE)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["output"]["bounds"], [[0, 0, 0], [10, 20, 30]])
            self.assertEqual(len(result["output"]["sha256"]), 64)

    def test_missing_case_and_failed_output_gate(self):
        results = [{"id": case.id, "status": "pass"} for case in probe.CASES]
        self.assertTrue(probe.all_pass(results))
        self.assertFalse(probe.all_pass(results[:-1]))
        results[2]["status"] = "wrong_geometry"
        self.assertFalse(probe.all_pass(results))

    def test_non_windows_writes_not_run_report_and_fails(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(probe.sys, "platform", "darwin"):
            output = Path(directory) / "report.json"
            self.assertFalse(probe.run_probe(Path("openscad.exe"), output))
            report = json.loads(output.read_text())
        self.assertEqual(report["status"], "not-run")
        self.assertEqual(report["cases"], [])
