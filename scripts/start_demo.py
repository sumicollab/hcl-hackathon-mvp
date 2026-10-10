"""Create a local environment and run the demo app without manual PowerShell steps."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen


def stop_stale_demo_processes(root: Path) -> None:
    try:
        import psutil
    except ImportError:
        return

    root_str = str(root.resolve()).lower()
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if not cmdline:
                continue
            command = " ".join(cmdline).lower()
            cwd = (proc.info.get("cwd") or "").lower()
            if ("uvicorn" in command and "app.main:app" in command and root_str in cwd) or (
                "streamlit" in command and "ui.py" in command and root_str in cwd
            ):
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except psutil.TimeoutExpired:
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_python_executable(root: Path) -> Path:
    venv_dir = root / ".venv"
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def build_demo_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HF_HOME"] = str((root / "runtime" / "models").resolve())
    env["ADMIN_TOKEN"] = "choose-a-local-demo-token"
    env["MOCK_LLM"] = "true"
    env["API_URL"] = "http://127.0.0.1:8000"
    return env


def ensure_venv(root: Path) -> Path:
    python_executable = get_python_executable(root)
    if not python_executable.exists():
        subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)

    check_code = (
        "import importlib; "
        "mods=['fastapi','streamlit','uvicorn','chromadb','sentence_transformers']; "
        "import sys; "
        "sys.exit(0 if all(importlib.util.find_spec(m) for m in mods) else 1)"
    )
    result = subprocess.run([str(python_executable), "-c", check_code], capture_output=True, text=True)
    if result.returncode != 0:
        subprocess.run(
            [str(python_executable), "-m", "pip", "install", "-r", str(root / "requirements.txt")],
            check=True,
            cwd=root,
        )
    return python_executable


def wait_for_url(url: str, timeout_seconds: int = 45) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=3) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"{url} did not become ready within {timeout_seconds} seconds")


def run_backend(root: Path, env: dict[str, str], *, skip_seed: bool = False) -> subprocess.Popen:
    python_executable = get_python_executable(root)
    if not skip_seed:
        subprocess.run(
            [str(python_executable), "-m", "scripts.seed_demo"],
            cwd=root,
            env=env,
            check=True,
        )

    process = subprocess.Popen(
        [str(python_executable), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=root,
        env=env,
    )
    wait_for_url("http://127.0.0.1:8000/health")
    return process


def run_streamlit(root: Path, env: dict[str, str], *, open_browser: bool = True) -> subprocess.Popen:
    process = subprocess.Popen(
        [
            str(get_python_executable(root)),
            "-m",
            "streamlit",
            "run",
            "ui.py",
            "--browser.gatherUsageStats",
            "false",
            "--server.address",
            "127.0.0.1",
            "--server.port",
            "8501",
        ],
        cwd=root,
        env=env,
    )
    wait_for_url("http://127.0.0.1:8501")
    if open_browser:
        if os.name == "nt":
            os.startfile("http://127.0.0.1:8501")
        else:
            webbrowser.open("http://127.0.0.1:8501")
    return process


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the demo backend and Streamlit UI.")
    parser.add_argument("--skip-seed", action="store_true", help="Skip reseeding demo data.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    args = parser.parse_args()

    root = get_project_root()
    stop_stale_demo_processes(root)
    python_executable = ensure_venv(root)
    env = build_demo_env(root)

    print(f"Using Python: {python_executable}")
    backend = run_backend(root, env, skip_seed=args.skip_seed)
    streamlit_env = env.copy()
    streamlit_env["API_URL"] = "http://127.0.0.1:8000"
    streamlit = run_streamlit(root, streamlit_env, open_browser=not args.no_browser)

    print("Backend ready: http://127.0.0.1:8000")
    print("Streamlit ready: http://127.0.0.1:8501")

    try:
        backend.wait()
    except KeyboardInterrupt:
        backend.terminate()
        streamlit.terminate()
        print("Demo stopped.")


if __name__ == "__main__":
    main()
