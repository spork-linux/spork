import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spork.package_managers.apt import AptPackageManager


class AptPackageManagerTest(unittest.TestCase):
    def test_install_file_uses_accessible_temporary_deb_and_removes_it(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            source_path = Path(source_dir) / "demo.deb"
            source_path.write_bytes(b"deb")

            seen_paths: list[Path] = []

            def fake_run_command(args: list[str], failure_message: str) -> None:
                deb_path = Path(args[-1])
                seen_paths.append(deb_path)
                self.assertTrue(deb_path.exists())
                self.assertEqual(deb_path.name, source_path.name)
                self.assertEqual(deb_path.parent.stat().st_mode & 0o777, 0o755)
                self.assertEqual(deb_path.stat().st_mode & 0o777, 0o644)

            manager = AptPackageManager()
            with patch("spork.package_managers.apt.run_command", side_effect=fake_run_command):
                manager.install_file(source_path)

        self.assertEqual(len(seen_paths), 2)
        self.assertEqual(seen_paths[0], seen_paths[1])
        self.assertFalse(seen_paths[0].exists())
        self.assertFalse(seen_paths[0].parent.exists())


if __name__ == "__main__":
    unittest.main()
