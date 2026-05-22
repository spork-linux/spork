import unittest
from pathlib import Path
from unittest.mock import call, patch

from spork.bucket import update_bucket
from spork.errors import BucketError


class UpdateBucketTest(unittest.TestCase):
    def test_update_bucket_can_continue_after_git_pull_failure(self) -> None:
        buckets = [
            {"name": "broken", "type": "git", "path": "/tmp/broken"},
            {"name": "ok", "type": "git", "path": "/tmp/ok"},
        ]

        with (
            patch("spork.bucket.list_buckets", return_value=buckets),
            patch("spork.bucket._run_git", side_effect=[BucketError("failed"), None]) as run_git,
        ):
            updated = update_bucket(stop_on_error=False)

        self.assertEqual(updated, ["ok"])
        run_git.assert_has_calls(
            [
                call(["pull", "--ff-only"], cwd=Path("/tmp/broken")),
                call(["pull", "--ff-only"], cwd=Path("/tmp/ok")),
            ]
        )

    def test_update_bucket_defaults_to_stop_on_git_pull_failure(self) -> None:
        buckets = [{"name": "broken", "type": "git", "path": "/tmp/broken"}]

        with (
            patch("spork.bucket.list_buckets", return_value=buckets),
            patch("spork.bucket._run_git", side_effect=BucketError("failed")),
        ):
            with self.assertRaises(BucketError):
                update_bucket()


if __name__ == "__main__":
    unittest.main()
