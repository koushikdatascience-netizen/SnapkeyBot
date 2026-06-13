import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn

HOST = "127.0.0.1"
PORT = int(os.environ.get("SNAPKEY_DESKTOP_PORT", "8010"))
URL = f"http://{HOST}:{PORT}/live"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def apply_local_defaults() -> None:
    root = project_root()
    os.chdir(root)
    os.environ.setdefault("APP_ENV", "desktop")
    os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{(root / 'snapkey-desktop.db').as_posix()}")
    os.environ.setdefault("LOCAL_VOICE_ENABLED", "true")
    os.environ.setdefault("LOCAL_TTS_PROVIDER", "sapi")
    os.environ.setdefault("CONCIERGE_MODE", "false")
    os.environ.setdefault("TASK_ALWAYS_EAGER", "true")


def edge_path() -> str | None:
    found = shutil.which("msedge")
    if found:
        return found
    candidates = [
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    return str(next((path for path in candidates if path.is_file()), "")) or None


def wait_until_ready(timeout: int = 45) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise RuntimeError("Snapkey local server did not start")


def main() -> None:
    apply_local_defaults()
    config = uvicorn.Config("app.main:app", host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_until_ready()

    edge = edge_path()
    if edge:
        profile = project_root() / ".snapkey-edge-profile"
        command = [
            edge,
            f"--app={URL}",
            f"--user-data-dir={profile}",
            "--autoplay-policy=no-user-gesture-required",
            "--no-first-run",
        ]
        window = subprocess.Popen(command)
        window.wait()
    else:
        import webbrowser

        webbrowser.open(URL)
        input("Snapkey is running. Press Enter to stop it.\n")
    server.should_exit = True
    thread.join(timeout=5)


if __name__ == "__main__":
    main()
