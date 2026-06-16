import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


# 默认只把这些环境变量传给子进程。
DEFAULT_ENV_ALLOWLIST = ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP")


@dataclass(frozen=True)
class CommandExecution:
    returncode: int
    output: str
    truncated: bool = False


class LocalRestrictedExecutor:
    # 本地执行器有安全限制，但不是完整的操作系统级沙箱。
    def __init__(self, env_allowlist=DEFAULT_ENV_ALLOWLIST, output_limit=30_000, runner=None):
        self.env_allowlist = tuple(env_allowlist)
        self.output_limit = output_limit
        self.runner = runner or subprocess.run

    def execute(self, argv: list[str], workspace: Path, timeout_seconds: int) -> CommandExecution:
        # shell=False 是安全模型的一部分；调用执行器前 argv 已经由 PermissionGuard 检查。
        environment = {key: os.environ[key] for key in self.env_allowlist if key in os.environ}
        completed = self.runner(
            argv,
            cwd=workspace,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=environment,
        )
        return _execution(completed, self.output_limit)


class DockerExecutor:
    # 可选的更强命令隔离；Docker 失败时不会静默降级成本地执行。
    def __init__(
        self,
        image: str,
        cpus: str = "1.0",
        memory: str = "512m",
        pids_limit: int = 128,
        output_limit: int = 30_000,
        runner=None,
    ):
        self.image = image
        self.cpus = cpus
        self.memory = memory
        self.pids_limit = pids_limit
        self.output_limit = output_limit
        self.runner = runner or subprocess.run

    def execute(self, argv: list[str], workspace: Path, timeout_seconds: int) -> CommandExecution:
        root = workspace.resolve()
        command = [
            "docker", "run", "--rm",
            "--network", "none",
            "--user", "65534:65534",
            "--read-only",
            "--cpus", self.cpus,
            "--memory", self.memory,
            "--pids-limit", str(self.pids_limit),
            "--volume", f"{root}:/workspace",
            "--workdir", "/workspace",
            self.image,
            *argv,
        ]
        environment = {key: os.environ[key] for key in DEFAULT_ENV_ALLOWLIST if key in os.environ}
        completed = self.runner(
            command,
            cwd=root,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=environment,
        )
        return _execution(completed, self.output_limit)


def create_command_executor(mode="local", **options):
    # Settings.COMMAND_EXECUTOR 使用的执行器配置开关。
    if mode == "local":
        return LocalRestrictedExecutor(
            env_allowlist=options.get("env_allowlist", DEFAULT_ENV_ALLOWLIST),
            output_limit=options.get("output_limit", 30_000),
        )
    if mode == "docker":
        return DockerExecutor(
            image=options.get("image", "python:3.12-slim"),
            cpus=options.get("cpus", "1.0"),
            memory=options.get("memory", "512m"),
            pids_limit=options.get("pids_limit", 128),
            output_limit=options.get("output_limit", 30_000),
        )
    raise ValueError(f"Unknown command executor: {mode}")


def _execution(completed, output_limit: int) -> CommandExecution:
    combined = (completed.stdout or "") + (completed.stderr or "")
    return CommandExecution(completed.returncode, combined[:output_limit], len(combined) > output_limit)
