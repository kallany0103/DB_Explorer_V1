"""WSL Linux distribution and PostgreSQL client discovery utilities."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

# Ignored non-user or internal WSL utility distros
IGNORED_DISTROS: set[str] = {
    "docker-desktop",
    "docker-desktop-data",
}


def is_wsl_available() -> bool:
    """Return True if WSL executable exists and is runnable on the system."""
    return shutil.which("wsl") is not None or shutil.which("wsl.exe") is not None


def get_wsl_distributions() -> list[dict[str, Any]]:
    """Return list of installed WSL distributions.

    Returns:
        List of dicts:
            - name: Distribution name (e.g. 'Ubuntu-22.04')
            - is_default: True if marked as default with '*'
            - state: 'Running' or 'Stopped'
            - version: WSL version (1 or 2)
    """
    if not is_wsl_available():
        return []

    try:
        # Run wsl -l -v with timeout
        raw = subprocess.check_output(
            ["wsl.exe", "-l", "-v"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        text = raw.decode("utf-16le", errors="replace")
    except Exception:
        return []

    distros: list[dict[str, Any]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) <= 1:
        return []

    for line in lines[1:]:  # Skip header (NAME STATE VERSION)
        is_default = line.startswith("*")
        cleaned = line.lstrip("*").strip()
        parts = cleaned.split()
        if not parts:
            continue

        name = parts[0]
        if name.lower() in IGNORED_DISTROS:
            continue

        state = parts[1] if len(parts) > 1 else "Unknown"
        version_val = 2
        if len(parts) > 2 and parts[2].isdigit():
            version_val = int(parts[2])

        distros.append({
            "name": name,
            "is_default": is_default,
            "state": state,
            "version": version_val,
        })

    return distros


def get_linux_package_manager_info(distro_id: str) -> tuple[str, str]:
    """Map a Linux distro ID (from /etc/os-release) to its package manager and install command."""
    d = (distro_id or "").strip().lower().strip('"')

    if d in ("ubuntu", "debian", "kali", "pop", "linuxmint", "raspbian", "neon", "zorin"):
        return ("apt", "sudo apt update && sudo apt install -y postgresql-client")

    if d in ("ol", "rhel", "fedora", "centos", "rocky", "almalinux"):
        return ("dnf", "sudo dnf install -y postgresql")

    if d in ("arch", "manjaro", "endeavouros"):
        return ("pacman", "sudo pacman -S --noconfirm postgresql-libs")

    if d in ("alpine",):
        return ("apk", "apk add postgresql-client")

    if d in ("opensuse", "opensuse-leap", "opensuse-tumbleweed", "sles"):
        return ("zypper", "sudo zypper install -y postgresql")

    return ("apt/dnf", "sudo apt install postgresql-client  OR  sudo dnf install postgresql")


def check_wsl_postgres(distro: str | None = None) -> dict[str, Any]:
    """Inspect a WSL distribution to verify whether psql and pg_dump are available.

    Returns:
        dict with keys:
            - available: bool (True if psql was found)
            - distro: str (distro name tested)
            - path: str (Linux path to psql, e.g. '/usr/bin/psql')
            - version: str (e.g. 'psql (PostgreSQL) 16.12')
            - distro_id: str (e.g. 'ubuntu', 'ol')
            - distro_name: str (e.g. 'Ubuntu 22.04.5 LTS')
            - install_cmd: str (suggested installation command if missing)
            - error: str | None
    """
    result: dict[str, Any] = {
        "available": False,
        "distro": distro or "",
        "path": "",
        "version": "",
        "distro_id": "",
        "distro_name": "",
        "install_cmd": "",
        "error": None,
    }

    if not is_wsl_available():
        result["error"] = "WSL is not installed or enabled on this system."
        return result

    wsl_args = ["wsl.exe"]
    if distro:
        wsl_args.extend(["-d", distro])

    # 1. Detect OS distribution details from /etc/os-release
    distro_id = "ubuntu"
    distro_name = ""
    try:
        os_rel_out = subprocess.check_output(
            wsl_args + ["--", "cat", "/etc/os-release"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode("utf-8", errors="replace")

        for line in os_rel_out.splitlines():
            line = line.strip()
            if line.startswith("ID="):
                distro_id = line.split("=", 1)[1].strip().strip('"').lower()
            elif line.startswith("PRETTY_NAME="):
                distro_name = line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass

    result["distro_id"] = distro_id
    result["distro_name"] = distro_name
    _, install_cmd = get_linux_package_manager_info(distro_id)
    result["install_cmd"] = install_cmd

    # 2. Check for psql binary
    try:
        psql_path_out = subprocess.check_output(
            wsl_args + ["--", "which", "psql"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode("utf-8", errors="replace").strip()
    except subprocess.CalledProcessError:
        psql_path_out = ""
    except Exception as e:
        result["error"] = str(e)
        return result

    if not psql_path_out:
        result["available"] = False
        return result

    # 3. Check psql version
    try:
        ver_out = subprocess.check_output(
            wsl_args + ["--", "psql", "--version"],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode("utf-8", errors="replace").strip()
    except Exception:
        ver_out = "psql (PostgreSQL)"

    result["available"] = True
    result["path"] = psql_path_out
    result["version"] = ver_out.split("\n")[0].strip()
    return result


def find_best_wsl_postgres_distro() -> tuple[str | None, dict[str, Any]]:
    """Scan available WSL distributions and return the one that has PostgreSQL installed.

    If multiple have PostgreSQL, prefers the default distribution.
    If none have PostgreSQL, returns the default distribution with its check info.
    """
    distros = get_wsl_distributions()
    if not distros:
        return None, {"available": False, "error": "No WSL distributions found"}

    default_distro = next((d["name"] for d in distros if d.get("is_default")), distros[0]["name"])

    # First check default distro
    default_info = check_wsl_postgres(default_distro)
    if default_info["available"]:
        return default_distro, default_info

    # Otherwise scan other distros to see if one has psql installed
    for d in distros:
        d_name = d["name"]
        if d_name == default_distro:
            continue
        info = check_wsl_postgres(d_name)
        if info["available"]:
            return d_name, info

    return default_distro, default_info
