import shutil
import subprocess
import tempfile
from pathlib import Path

from .common import PackageManager, capture_command, run_command


class AptPackageManager(PackageManager):
    def __init__(self, command: str = "apt") -> None:
        super().__init__(command, "dpkg-query", command, "apt-cache")

    def required_commands(self) -> list[str]:
        return [self.install_command, "sudo", "dpkg-query", "dpkg-deb", "dpkg", "apt-cache"]

    def install_plan(self, path: Path) -> list[str]:
        return [
            f"{self.install_command} install --simulate {path}",
            f"sudo {self.install_command} install {path}",
        ]

    def preinstall_file(self, path: Path) -> None:
        print("执行预安装检查：", flush=True)
        print(f"  {self.install_command} install --simulate {path}", flush=True)
        run_command(
            [self.install_command, "install", "--simulate", str(path)],
            "预安装检查失败，已拒绝安装。请检查上方 apt 输出。",
        )

    def install_file(self, path: Path) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="spork-apt-", dir="/tmp"))
        try:
            temp_dir.chmod(0o755)
            temp_path = temp_dir / path.name
            shutil.copy2(path, temp_path)
            temp_path.chmod(0o644)

            self.preinstall_file(temp_path)
            run_command(["sudo", self.install_command, "install", str(temp_path)], "apt 安装失败，请检查上方 apt 输出。")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def remove_plan(self, package: str, purge: bool = False) -> str:
        op = "purge" if purge else "remove"
        return f"sudo {self.install_command} {op} {package}"

    def purge_package(self, package: str) -> None:
        run_command(["sudo", self.install_command, "purge", package], "apt purge 失败，请检查上方 apt 输出。")

    def installed_version(self, package: str) -> str | None:
        result = capture_command(["dpkg-query", "-W", "-f=${Version}", package])
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def compare_versions(self, left: str, op: str, right: str) -> bool:
        result = subprocess.run(["dpkg", "--compare-versions", left, op, right])
        return result.returncode == 0

    def depends(self, package: str) -> None:
        run_command(["apt-cache", "depends", package], "apt-cache depends 执行失败。")
