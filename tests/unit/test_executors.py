import os
from pathlib import Path
from types import SimpleNamespace

from minicode.tools.executors import DockerExecutor, LocalRestrictedExecutor


def test_local_executor_uses_minimal_environment_and_caps_output(tmp_path: Path):
    captured = {}

    def runner(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="A" * 20, stderr="B" * 20)

    executor = LocalRestrictedExecutor(
        env_allowlist=("PATH",),
        output_limit=25,
        runner=runner,
    )
    old_secret = os.environ.get("LLM_API_KEY")
    os.environ["LLM_API_KEY"] = "must-not-leak"
    try:
        result = executor.execute(["python", "--version"], tmp_path, 5)
    finally:
        if old_secret is None:
            os.environ.pop("LLM_API_KEY", None)
        else:
            os.environ["LLM_API_KEY"] = old_secret

    assert captured["shell"] is False
    assert captured["cwd"] == tmp_path
    assert "LLM_API_KEY" not in captured["env"]
    assert captured["env"].get("PATH") == os.environ.get("PATH")
    assert len(result.output) == 25
    assert result.truncated is True


def test_docker_executor_builds_non_root_networkless_resource_limited_command(tmp_path: Path):
    captured = {}

    def runner(argv, **kwargs):
        captured["argv"] = argv
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    executor = DockerExecutor(
        image="python:3.12-slim",
        cpus="0.5",
        memory="256m",
        pids_limit=64,
        output_limit=100,
        runner=runner,
    )

    result = executor.execute(["pytest", "-q"], tmp_path, 10)

    command = captured["argv"]
    assert command[:2] == ["docker", "run"]
    assert ["--network", "none"] == command[command.index("--network"):command.index("--network") + 2]
    assert ["--user", "65534:65534"] == command[command.index("--user"):command.index("--user") + 2]
    assert "--read-only" in command
    assert ["--cpus", "0.5"] == command[command.index("--cpus"):command.index("--cpus") + 2]
    assert ["--memory", "256m"] == command[command.index("--memory"):command.index("--memory") + 2]
    assert ["--pids-limit", "64"] == command[command.index("--pids-limit"):command.index("--pids-limit") + 2]
    assert command[-3:] == ["python:3.12-slim", "pytest", "-q"]
    assert result.output == "ok"
