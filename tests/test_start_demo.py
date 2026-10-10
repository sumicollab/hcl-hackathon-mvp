from pathlib import Path

from scripts.start_demo import build_demo_env, get_python_executable


def test_build_demo_env_sets_required_values():
    env = build_demo_env(Path("."))
    hf_home = Path(env["HF_HOME"])

    assert env["MOCK_LLM"] == "true"
    assert env["ADMIN_TOKEN"] == "choose-a-local-demo-token"
    assert "HF_HOME" in env
    assert hf_home.parts[-2:] == ("runtime", "models")


def test_get_python_executable_uses_venv_python():
    exe = get_python_executable(Path("."))

    assert "python" in exe.name.lower()
