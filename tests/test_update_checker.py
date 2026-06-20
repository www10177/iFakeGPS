import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.core import update_checker
from src.utils import paths


class UpdateCheckerTests(unittest.TestCase):
    def test_reads_current_version_from_frozen_changelog_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            (bundle_root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## [Unreleased]\n\n## [1.6.2] - 2026-06-06\n",
                encoding="utf-8",
            )

            # Frozen resource resolution lives in utils.paths now.
            with mock.patch.object(paths.sys, "frozen", True, create=True):
                with mock.patch.object(paths.sys, "_MEIPASS", str(bundle_root), create=True):
                    self.assertEqual(update_checker._read_version_from_changelog(), "1.6.2")


if __name__ == "__main__":
    unittest.main()
