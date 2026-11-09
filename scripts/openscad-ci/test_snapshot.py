import unittest

from resolve_snapshot import parse_checksum, parse_snapshot_metadata, parse_version_info


class SnapshotResolutionTests(unittest.TestCase):
    def test_upstream_metadata(self):
        js = ("setSnapshotFileInfo('LIN64_SNAPSHOT', 'OpenSCAD-2026.10.29', "
              "'86 MB', 'https://files.openscad.org/snapshots/"
              "OpenSCAD-2026.10.29.ai12345-x86_64.AppImage');")
        self.assertEqual(parse_snapshot_metadata(js), (
            "2026.10.29",
            "https://files.openscad.org/snapshots/OpenSCAD-2026.10.29.ai12345-x86_64.AppImage",
            "OpenSCAD-2026.10.29.ai12345-x86_64.AppImage",
        ))

    def test_reject_incorrect_origin_and_format(self):
        for url in ("https://evil.example/snapshots/OpenSCAD-2026.10.29-x86_64.AppImage",
                    "https://files.openscad.org/snapshots/OpenSCAD-2026.10.29.exe"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                parse_snapshot_metadata(
                    "setSnapshotFileInfo('LIN64_SNAPSHOT','name','100 MB','" + url + "');")

    def test_checksum_requires_matching_filename(self):
        basename = "OpenSCAD-2026.10.29-x86_64.AppImage"
        checksum = "a" * 64
        self.assertEqual(parse_checksum((checksum + "  " + basename).encode().decode(), basename), checksum)
        with self.assertRaises(ValueError):
            parse_checksum(checksum + "  other.AppImage", basename)

    def test_version_info_requires_git_revision_and_matching_date(self):
        output = "OpenSCAD Version: 2026.10.29 (git abC123d)\nSystem information: Linux\n"
        self.assertEqual(parse_version_info(output, "2026.10.29"), "abc123d")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            parse_version_info(output, "2026.10.28")
        with self.assertRaisesRegex(ValueError, "Cannot determine"):
            parse_version_info("OpenSCAD Version: 2026.10.29\n", "2026.10.29")


if __name__ == "__main__":
    unittest.main()
