import argparse
from pathlib import Path
import sys
import traceback

from . import __version__
from . import cache
from .branding import BRAND_NAME, CLI_NAME
from .bucket import add_bucket, list_buckets, remove_bucket, update_bucket
from .commands import (
    cat_command,
    config_command,
    create_command,
    depends_command,
    download_command,
    home_command,
)
from .config import ensure_initial_files, load_config
from .doctor import run_doctor
from .errors import DebupError
from .i18n import set_language, t
from .index import all_apps, find_app, search_apps, update_index
from .installer import check, install, upgrade
from .output import confirm, print_json, table
from .remover import autoremove, remove
from .self_update import update_self
from .state import list_installed


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--debug", action="store_true", help="输出 traceback")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--no-color", action="store_true", help="保留参数，当前实现不输出颜色")
    parser.add_argument("--lang", choices=["auto", "zh", "en"], help="输出语言")


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="输出 JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=CLI_NAME, description=f"{BRAND_NAME}: Scoop-style third-party Linux package manager.")
    parser.add_argument("--version", action="version", version=f"{BRAND_NAME} ({CLI_NAME}) {__version__}")
    _add_common(parser)
    sub = parser.add_subparsers(dest="command")

    bucket = sub.add_parser("bucket", help="管理 bucket")
    bucket_sub = bucket.add_subparsers(dest="bucket_command", required=True)
    bucket_add = bucket_sub.add_parser("add")
    bucket_add.add_argument("name")
    bucket_add.add_argument("source")
    bucket_add.add_argument("-y", "--yes", action="store_true")
    bucket_list = bucket_sub.add_parser("list")
    _add_json(bucket_list)
    bucket_rm = bucket_sub.add_parser("rm")
    bucket_rm.add_argument("name")
    bucket_rm.add_argument("--delete-files", action="store_true")
    bucket_update = bucket_sub.add_parser("update")
    bucket_update.add_argument("name", nargs="?")

    update = sub.add_parser("update", help="更新 Spork、自身 bucket、本地索引或应用")
    update.add_argument("app_id", nargs="?")
    update.add_argument("--no-bucket-update", action="store_true")
    update.add_argument("--no-self-update", action="store_true")
    update.add_argument("-y", "--yes", action="store_true")
    update.add_argument("--stop-on-error", action="store_true")

    list_cmd = sub.add_parser("list", help="列出已安装应用")
    list_filter = list_cmd.add_mutually_exclusive_group()
    list_filter.add_argument("--installed", action="store_true", help=f"只列出 {BRAND_NAME} 记录的已安装应用（默认行为）")
    list_filter.add_argument("--available", action="store_true", help="列出索引中的全部可用应用")
    _add_json(list_cmd)
    search = sub.add_parser("search", help="搜索应用")
    search.add_argument("keyword")
    _add_json(search)
    info = sub.add_parser("info", help="显示应用信息")
    info.add_argument("app_id")
    _add_json(info)
    status_cmd = sub.add_parser("status", help="检查可升级软件")
    _add_json(status_cmd)

    config_cmd = sub.add_parser("config", help="读写配置")
    config_sub = config_cmd.add_subparsers(dest="config_command", required=True)
    config_list = config_sub.add_parser("list")
    _add_json(config_list)
    config_get = config_sub.add_parser("get")
    config_get.add_argument("key")
    _add_json(config_get)
    config_set = config_sub.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")

    cat_cmd = sub.add_parser("cat", help="显示应用索引 JSON")
    cat_cmd.add_argument("app_id")
    download_cmd = sub.add_parser("download", help="下载应用 deb 到缓存，不安装")
    download_cmd.add_argument("app_id")

    home_cmd = sub.add_parser("home", help="显示应用主页")
    home_cmd.add_argument("app_id")
    depends_cmd = sub.add_parser("depends", help="显示包管理器依赖信息")
    depends_cmd.add_argument("app_id")
    depends_cmd.add_argument("--package")
    create_cmd = sub.add_parser("create", help="创建 fixed-url app manifest 模板")
    create_cmd.add_argument("app_id")
    create_cmd.add_argument("path")
    create_cmd.add_argument("--name")
    create_cmd.add_argument("--package")
    create_cmd.add_argument("--url")
    create_cmd.add_argument("--version")
    create_cmd.add_argument("--arch")

    install_cmd = sub.add_parser("install", help="安装应用")
    install_cmd.add_argument("app_id")
    install_cmd.add_argument("-y", "--yes", action="store_true")

    uninstall_cmd = sub.add_parser(
        "uninstall",
        help="卸载应用",
        usage="spork uninstall <app-id> [-y] [--package PACKAGE] [--purge] [--autoremove]",
    )
    uninstall_cmd.add_argument("app_id", metavar="app-id")
    uninstall_cmd.add_argument("-y", "--yes", action="store_true")
    uninstall_cmd.add_argument("--package")
    uninstall_cmd.add_argument("--purge", action="store_true", help="卸载应用并清理系统级配置（需要包管理器支持）")
    uninstall_cmd.add_argument("--autoremove", action="store_true", help="卸载完成后调用系统包管理器自动清理（需要包管理器支持）")

    cache_cmd = sub.add_parser("cache", help="管理下载缓存")
    cache_sub = cache_cmd.add_subparsers(dest="cache_command", required=True)
    cache_clean = cache_sub.add_parser("clean")
    cache_clean.add_argument("-y", "--yes", action="store_true")

    checkup_cmd = sub.add_parser("checkup", help="检查环境")
    _add_json(checkup_cmd)
    return parser


def cmd_bucket(args: argparse.Namespace) -> None:
    if args.bucket_command == "add":
        entry = add_bucket(args.name, args.source, yes=args.yes)
        print(f"已添加 bucket：{entry['name']}")
    elif args.bucket_command == "list":
        rows = list_buckets()
        if getattr(args, "json", False):
            print_json(rows)
        else:
            table(rows, [("name", "NAME"), ("type", "TYPE"), ("source", "SOURCE"), ("trusted", "TRUSTED")])
    elif args.bucket_command == "rm":
        remove_bucket(args.name, delete_files=args.delete_files)
        print(f"已删除 bucket：{args.name}")
    elif args.bucket_command == "update":
        updated = update_bucket(args.name)
        print(f"已更新 {len(updated)} 个 git bucket。")


def cmd_info(args: argparse.Namespace) -> None:
    app = find_app(args.app_id)
    if args.json:
        print_json(app)
        return
    for key in ("id", "name", "description", "package", "version", "arch", "bucket", "homepage", "url", "sha256"):
        print(f"{key}: {app.get(key) or ''}")


def cmd_cache_clean(args: argparse.Namespace) -> None:
    size = cache.downloads_size()
    print(f"即将清理下载缓存：{cache.human_size(size)}")
    if not confirm("继续吗？", yes=args.yes):
        print("已取消。")
        return
    cleaned = cache.clean_downloads()
    print(f"已清理：{cache.human_size(cleaned)}")


def dispatch(args: argparse.Namespace) -> None:
    ensure_initial_files()
    config = load_config()
    set_language(args.lang or config.get("language") or "auto")
    if args.command == "bucket":
        cmd_bucket(args)
    elif args.command == "update":
        if args.app_id:
            upgrade(None if args.app_id == "*" else args.app_id, yes=args.yes, stop_on_error=args.stop_on_error)
            return
        if not args.no_self_update:
            try:
                update_self()
            except DebupError as exc:
                if args.stop_on_error:
                    raise
                print(f"警告：{exc}", file=sys.stderr)
        merged = update_index(no_bucket_update=args.no_bucket_update)
        print(f"索引更新完成：{len(merged.get('apps', []))} 个应用。")
    elif args.command == "list":
        rows = all_apps() if args.available else list_installed()
        if args.json:
            print_json(rows)
        else:
            table(rows, [("id", "ID"), ("name", "NAME"), ("package", "PACKAGE"), ("version", "VERSION"), ("bucket", "BUCKET")])
    elif args.command == "search":
        rows = search_apps(args.keyword)
        if args.json:
            print_json(rows)
        else:
            table(rows, [("id", "ID"), ("name", "NAME"), ("package", "PACKAGE"), ("version", "VERSION"), ("bucket", "BUCKET")])
    elif args.command == "info":
        cmd_info(args)
    elif args.command == "status":
        rows = check()
        if args.json:
            print_json(rows)
        else:
            table(rows, [("id", "ID"), ("package", "PACKAGE"), ("installed", "INSTALLED"), ("latest", "LATEST"), ("bucket", "BUCKET")])
    elif args.command == "install":
        install(args.app_id, yes=args.yes)
    elif args.command == "uninstall":
        removed = remove(args.app_id, yes=args.yes, package=args.package, purge=args.purge)
        if removed and args.autoremove:
            autoremove(yes=args.yes)
    elif args.command == "cache":
        if args.cache_command == "clean":
            cmd_cache_clean(args)
    elif args.command == "checkup":
        rows = run_doctor()
        if args.json:
            print_json(rows)
        else:
            table(rows, [("item", "ITEM"), ("status", "STATUS"), ("detail", "DETAIL")])
    elif args.command == "config":
        config_command(args)
    elif args.command == "cat":
        cat_command(args.app_id)
    elif args.command == "download":
        download_command(args.app_id)
    elif args.command == "home":
        home_command(args.app_id)
    elif args.command == "depends":
        depends_command(args.app_id, package=args.package)
    elif args.command == "create":
        create_command(args.app_id, Path(args.path), args.name, args.package, args.url, args.version, args.arch)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        dispatch(args)
        return 0
    except DebupError as exc:
        print(t("error_prefix", message=exc), file=sys.stderr)
        if getattr(args, "debug", False):
            traceback.print_exc()
        return 1
    except Exception:
        if getattr(args, "debug", False):
            traceback.print_exc()
        else:
            print(t("error_prefix", message="执行失败，可使用 --debug 查看 traceback。"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
