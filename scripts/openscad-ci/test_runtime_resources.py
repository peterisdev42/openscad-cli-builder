import tempfile
import unittest
from pathlib import Path

from runtime_resources import check_source_resources, copy_runtime_resources, resource_names, smoke_library


class RuntimeResourcesTests(unittest.TestCase):
    def make_source(self, root, modern, libraries=True):
        source = root / "source"
        source.mkdir()
        for name in resource_names(modern):
            if name != "libraries" or libraries:
                (source / name).mkdir()
        (source / "locale").mkdir()
        for name in ("CMakeLists.txt", "COPYING", "locale/LINGUAS"):
            (source / name).touch()
        if libraries:
            (source / "libraries/MCAD").mkdir()
            (source / "libraries/MCAD/boxes.scad").write_text("test")
        return source

    def test_old_and_new_layout_for_native_and_wasm(self):
        for modern, libraries in ((False, True), (True, True), (True, False)):
            for wasm in (False, True):
                with self.subTest(modern=modern, libraries=libraries, wasm=wasm), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    source = self.make_source(root, modern, libraries)
                    resources = root / "resources"
                    copy_runtime_resources(source, resources, modern, wasm)
                    self.assertTrue((resources / "libraries").is_dir())
                    self.assertEqual((resources / "libraries/MCAD/boxes.scad").is_file(), libraries)
                    model = root / "model"
                    model.mkdir()
                    expected = "MCAD/boxes.scad" if libraries else "smoke-library.scad"
                    self.assertEqual(smoke_library(resources, model), expected)
                    self.assertEqual((model / "smoke-library.scad").is_file(), not libraries)

    def test_required_resources_not_silently_skipped(self):
        for modern, missing in ((False, "libraries"), (True, "fonts"), (True, "templates")):
            with self.subTest(modern=modern, missing=missing), tempfile.TemporaryDirectory() as tmp:
                source = self.make_source(Path(tmp), modern, missing != "libraries")
                if missing != "libraries":
                    (source / missing).rmdir()
                with self.assertRaisesRegex(FileNotFoundError, missing):
                    check_source_resources(source, modern)
