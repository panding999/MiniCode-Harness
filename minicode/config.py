from dataclasses import dataclass
import os
from pathlib import Path


# 配置采用环境变量优先，这样安装后的 CLI 可以从任意 Workspace 启动。
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def discover_env_file(cwd: Path | None = None, project_root: Path | None = None, home: Path | None = None) -> Path | None:
    # 查找顺序：显式指定、当前 Workspace、用户级配置、开发时的 MiniCode 项目根目录。
    explicit = os.getenv("MINICODE_ENV_FILE")
    candidates = [
        Path(explicit).expanduser() if explicit else None,
        (cwd or Path.cwd()) / ".env",
        (home or Path.home()) / ".minicode" / ".env",
        (project_root or PROJECT_ROOT) / ".env",
    ]
    return next((path.resolve() for path in candidates if path and path.exists()), None)


def resolve_db_url(value: str, base_dir: Path) -> str:
    # 相对 sqlite 路径锚定到 .env 所在目录，而不是进程当前目录。
    prefix = "sqlite:///"
    if not value.startswith(prefix):
        return value
    database = value[len(prefix):]
    if database == ":memory:" or Path(database).is_absolute():
        return value
    return f"{prefix}{(base_dir / database).resolve().as_posix()}"


def load_env_file(path: Path | None = None) -> Path | None:
    # setdefault 保证外部已经设置的环境变量优先级更高。
    env_path = path.resolve() if path else discover_env_file()
    if env_path is None:
        return None
    if not env_path.exists():
        return None
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
    if "MINICODE_DB_URL" in os.environ:
        os.environ["MINICODE_DB_URL"] = resolve_db_url(os.environ["MINICODE_DB_URL"], env_path.parent)
    return env_path


load_env_file()


@dataclass(frozen=True)
class Settings:
    # 上下文压缩默认值：超过 12000 字符压缩旧消息，保留最近 12 条消息和最近 5 条完整工具输出。
    db_url: str = os.getenv("MINICODE_DB_URL", "sqlite:///minicode.db")
    max_steps: int = int(os.getenv("MAX_STEPS", "8"))
    repeat_limit: int = 3
    context_char_limit: int = int(os.getenv("CONTEXT_CHAR_LIMIT", "12000"))
    context_keep_messages: int = int(os.getenv("CONTEXT_KEEP_MESSAGES", "12"))
    context_full_tool_results: int = int(os.getenv("CONTEXT_FULL_TOOL_RESULTS", "5"))
    command_executor: str = os.getenv("COMMAND_EXECUTOR", "local")
    command_env_allowlist: tuple[str, ...] = tuple(
        item.strip() for item in os.getenv(
            "COMMAND_ENV_ALLOWLIST",
            "PATH,PATHEXT,SYSTEMROOT,WINDIR,COMSPEC,TEMP,TMP",
        ).split(",") if item.strip()
    )
    command_output_limit: int = int(os.getenv("COMMAND_OUTPUT_LIMIT", "30000"))
    docker_image: str = os.getenv("DOCKER_IMAGE", "python:3.12-slim")
    docker_cpus: str = os.getenv("DOCKER_CPUS", "1.0")
    docker_memory: str = os.getenv("DOCKER_MEMORY", "512m")
    docker_pids_limit: int = int(os.getenv("DOCKER_PIDS_LIMIT", "128"))
