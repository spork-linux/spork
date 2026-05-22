import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spork.index import update_index


class UpdateIndexTest(unittest.TestCase):
    def test_update_index_keeps_building_when_bucket_update_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bucket_path = Path(temp_dir) / "main"
            (bucket_path / "bucket").mkdir(parents=True)
            (bucket_path / "bucket" / "demo.json").write_text(
                """{
  "id": "demo",
  "name": "Demo",
  "description": "Demo app",
  "package": "demo",
  "version": "1.0.0",
  "arch": "amd64",
  "url": "https://example.com/demo.deb",
  "bucket": "main",
  "updatedAt": "2026-05-22T00:00:00Z"
}
""",
                encoding="utf-8",
            )

            with (
                patch("spork.index.load_config", return_value={"autoUpdateBuckets": True, "arch": "amd64"}),
                patch("spork.index.update_bucket") as update_bucket,
                patch("spork.index.list_buckets", return_value=[{"name": "main", "path": str(bucket_path)}]),
                patch("spork.index.paths.index_dir", return_value=Path(temp_dir) / "index"),
                patch("spork.index.paths.merged_index_file", return_value=Path(temp_dir) / "index" / "merged.json"),
            ):
                merged = update_index()

        update_bucket.assert_called_once_with(stop_on_error=False)
        self.assertEqual([app["id"] for app in merged["apps"]], ["demo"])


if __name__ == "__main__":
    unittest.main()
