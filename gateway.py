"""Find, launch and probe IB Gateway (Windows)."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

WIN = sys.platform == "win32"


def find_gateway() -> str | None:
    """Latest ibgateway.exe under the standard install dirs (C:\\Jts\\ibgateway\\<version>)."""
    roots = [Path((os.getenv("SystemDrive") or "C:") + "\\") / "Jts" / "ibgateway",
             Path.home() / "Jts" / "ibgateway"]
    found = [(int(exe.parent.name) if exe.parent.name.isdigit() else 0, exe)
             for root in roots for exe in root.glob("*/ibgateway.exe")]
    return str(max(found)[1]) if found else None


def is_running() -> bool:
    if not WIN:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ibgateway.exe", "/NH"], capture_output=True,
                             text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW).stdout
    except Exception:
        return False
    return "ibgateway.exe" in out.lower()


def launch(path: str = "") -> str:
    exe = path.strip().strip('"') or find_gateway()
    if not exe or not Path(exe).is_file():
        raise FileNotFoundError("IB Gateway not found - set its path in Settings.")
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if WIN else 0
    subprocess.Popen([exe], cwd=str(Path(exe).parent), creationflags=flags, close_fds=True)
    return exe


def port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """The Gateway only opens its API port once you are logged in."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
