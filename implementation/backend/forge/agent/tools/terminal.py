from __future__ import annotations

import subprocess
from typing import Sequence


def _shell_command(shell: str, command: str) -> Sequence[str]:
    shell_name = shell.lower()
    if shell_name == "powershell":
        return ["powershell", "-NoProfile", "-Command", command]
    if shell_name == "cmd":
        return ["cmd", "/c", command]
    if shell_name == "wsl":
        return ["wsl", "bash", "-lc", command]
    if shell_name == "bash":
        return ["bash", "-lc", command]
    if shell_name == "gitbash":
        return ["C:\\Program Files\\Git\\bin\\bash.exe", "-lc", command]
    raise ValueError(f"Unsupported shell: {shell}")


async def terminal_execute(
    command: str, shell: str = "powershell", working_dir: str | None = None
) -> dict[str, str | int]:
    """Execute a terminal command with a 120-second timeout."""
    cmd = _shell_command(shell, command)
    completed = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120, cwd=working_dir
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
