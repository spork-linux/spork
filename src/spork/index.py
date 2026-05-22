from pathlib import Path
from typing import Any

from . import paths
from .bucket import list_buckets, update_bucket
from .config import load_config, now_iso, write_json
from .errors import AppNotFoundError, IndexError
from .manifest import read_app_dir
from .output import warn


def _bucket_apps(bucket: dict[str, Any], target_arch: str) -> list[dict[str, Any]]:
    bucket_path = Path(bucket["path"])
    apps = read_app_dir(bucket_path / "bucket", bucket["name"], target_arch)
    if not apps:
        warn(f"bucket {bucket['name']} 没有适用于 {target_arch} 的 bucket/*.json manifest，已跳过。")
    return apps


def update_index(no_bucket_update: bool = False) -> dict[str, Any]:
    config = load_config()
    if config.get("autoUpdateBuckets", True) and not no_bucket_update:
        update_bucket(stop_on_error=False)

    merged_by_id: dict[str, dict[str, Any]] = {}
    ordered_ids: list[str] = []
    target_arch = str(config.get("arch"))
    for bucket in list_buckets():
        apps = _bucket_apps(bucket, target_arch)
        bucket_index = {"schemaVersion": 1, "updatedAt": now_iso(), "apps": apps}
        write_json(paths.index_dir() / f"{bucket['name']}.json", bucket_index)
        for app in apps:
            app_id = app["id"]
            if app_id in merged_by_id:
                warn(f"应用 {app_id} 在多个 bucket 中重复，后添加的 bucket {bucket['name']} 优先。")
            else:
                ordered_ids.append(app_id)
            merged_by_id[app_id] = app
    merged = {
        "schemaVersion": 1,
        "updatedAt": now_iso(),
        "apps": [merged_by_id[app_id] for app_id in ordered_ids if app_id in merged_by_id],
    }
    write_json(paths.merged_index_file(), merged)
    return merged


def load_index() -> dict[str, Any]:
    if not paths.merged_index_file().exists():
        raise IndexError("本地索引不存在，请先执行：\n  spork update")
    from .config import read_json

    return read_json(paths.merged_index_file(), {"schemaVersion": 1, "apps": []})


def all_apps() -> list[dict[str, Any]]:
    return list(load_index().get("apps", []))


def find_app(app_id: str) -> dict[str, Any]:
    for app in all_apps():
        if app.get("id") == app_id:
            return app
    raise AppNotFoundError(f"未找到应用：{app_id}\n\n可以执行：\n  spork search {app_id}")


def search_apps(keyword: str) -> list[dict[str, Any]]:
    needle = keyword.lower()
    fields = ("id", "name", "package", "description")
    return [
        app
        for app in all_apps()
        if any(needle in str(app.get(field, "")).lower() for field in fields)
    ]
