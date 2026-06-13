from pathlib import Path

from minicode.config import discover_env_file, resolve_db_url


def test_env_discovery_falls_back_to_project_root(tmp_path: Path):
    cwd = tmp_path / "other"
    project = tmp_path / "harness"
    cwd.mkdir()
    project.mkdir()
    (project / ".env").write_text("LLM_MODEL=test\n", encoding="utf-8")

    assert discover_env_file(cwd=cwd, project_root=project, home=tmp_path) == project / ".env"


def test_env_discovery_prefers_workspace_then_user_config(tmp_path: Path):
    cwd = tmp_path / "workspace"
    project = tmp_path / "harness"
    home = tmp_path / "home"
    cwd.mkdir()
    project.mkdir()
    (home / ".minicode").mkdir(parents=True)
    (project / ".env").write_text("", encoding="utf-8")
    (home / ".minicode" / ".env").write_text("", encoding="utf-8")
    assert discover_env_file(cwd=cwd, project_root=project, home=home) == home / ".minicode" / ".env"

    (cwd / ".env").write_text("", encoding="utf-8")
    assert discover_env_file(cwd=cwd, project_root=project, home=home) == cwd / ".env"


def test_relative_sqlite_url_is_anchored_to_env_directory(tmp_path: Path):
    result = resolve_db_url("sqlite:///minicode.db", tmp_path)
    assert result == f"sqlite:///{(tmp_path / 'minicode.db').resolve().as_posix()}"
