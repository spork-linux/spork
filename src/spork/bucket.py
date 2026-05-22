import shutil
import subprocess
from pathlib import Path
from typing import Any

from . import paths
from .config import load_buckets, load_trusted_buckets, now_iso, save_buckets, save_trusted_buckets
from .errors import BucketError
from .output import warn


def _is_git_source(source: str) -> bool:
    return source.endswith(".git") or "://" in source or source.startswith("git@")


def _run_git(args: list[str], cwd: Path | None = None) -> None:
    try:
        subprocess.run(["git", *args], cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise BucketError("git 不可用，请先安装 git。") from exc
    except subprocess.CalledProcessError as exc:
        raise BucketError("git 命令执行失败。") from exc


def _find_bucket(data: dict[str, Any], name: str) -> dict[str, Any] | None:
    for bucket in data.get("buckets", []):
        if bucket.get("name") == name:
            return bucket
    return None


def _validate_bucket_path(path: Path) -> None:
    if not (path / "bucket.json").exists():
        raise BucketError(f"bucket.json 不存在：{path}")


def _record_trust(name: str, source: str) -> None:
    trusted = load_trusted_buckets()
    entries = trusted.setdefault("trusted", [])
    entries[:] = [entry for entry in entries if entry.get("name") != name]
    entries.append({"name": name, "source": source, "trustedAt": now_iso()})
    save_trusted_buckets(trusted)


def add_bucket(name: str, source: str, yes: bool = False) -> dict[str, Any]:
    data = load_buckets()
    if _find_bucket(data, name):
        raise BucketError(f"bucket 已存在：{name}")

    if _is_git_source(source):
        target = paths.buckets_dir() / name
        if target.exists():
            raise BucketError(f"bucket 目录已存在：{target}")
        _run_git(["clone", source, str(target)])
        bucket_type = "git"
        bucket_path = target
    else:
        bucket_path = Path(source).expanduser().resolve()
        if not bucket_path.exists():
            raise BucketError(f"本地 bucket 不存在：{bucket_path}")
        bucket_type = "local"

    _validate_bucket_path(bucket_path)

    entry = {
        "name": name,
        "type": bucket_type,
        "source": source,
        "path": str(bucket_path),
        "trusted": True,
        "addedAt": now_iso(),
    }
    data.setdefault("buckets", []).append(entry)
    save_buckets(data)
    _record_trust(name, source)
    return entry


def list_buckets() -> list[dict[str, Any]]:
    return list(load_buckets().get("buckets", []))


def remove_bucket(name: str, delete_files: bool = False) -> None:
    data = load_buckets()
    bucket = _find_bucket(data, name)
    if not bucket:
        raise BucketError(f"未找到 bucket：{name}")
    data["buckets"] = [entry for entry in data.get("buckets", []) if entry.get("name") != name]
    save_buckets(data)

    trusted = load_trusted_buckets()
    trusted["trusted"] = [entry for entry in trusted.get("trusted", []) if entry.get("name") != name]
    save_trusted_buckets(trusted)

    if delete_files and bucket.get("type") == "git":
        shutil.rmtree(Path(bucket["path"]), ignore_errors=True)


def update_bucket(name: str | None = None, stop_on_error: bool = True) -> list[str]:
    buckets = list_buckets()
    if name:
        buckets = [bucket for bucket in buckets if bucket.get("name") == name]
        if not buckets:
            raise BucketError(f"未找到 bucket：{name}")
    updated: list[str] = []
    for bucket in buckets:
        if bucket.get("type") == "git":
            try:
                _run_git(["pull", "--ff-only"], cwd=Path(bucket["path"]))
            except BucketError:
                if stop_on_error:
                    raise
                warn(f"bucket {bucket['name']} 更新失败，继续使用本地已有内容。")
                continue
            updated.append(bucket["name"])
    return updated
