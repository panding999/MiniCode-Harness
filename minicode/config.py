from dataclasses import dataclass
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def discover_env_file(cwd: Path | None = None, project_root: Path | None = None, home: Path | None = None) -> Path | None:
    explicit = os.getenv("MINICODE_ENV_FILE")
    candidates = [
        Path(explicit).expanduser() if explicit else None,
        (cwd or Path.cwd()) / ".env",
        (home or Path.home()) / ".minicode" / ".env",
        (project_root or PROJECT_ROOT) / ".env",
    ]
    return next((path.resolve() for path in candidates if path and path.exists()), None)


def resolve_db_url(value: str, base_dir: Path) -> str:
    prefix = "sqlite:///"
    if not value.startswith(prefix):
        return value
    database = value[len(prefix):]
    if database == ":memory:" or Path(database).is_absolute():
        return value
    return f"{prefix}{(base_dir / database).resolve().as_posix()}"


def load_env_file(path: Path | None = None) -> Path | None:
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
    db_url: str = os.getenv("MINICODE_DB_URL", "sqlite:///minicode.db")
    max_steps: int = int(os.getenv("MAX_STEPS", "8"))
    repeat_limit: int = 3
    message_threshold: int = 30
    keep_messages: int = 12
