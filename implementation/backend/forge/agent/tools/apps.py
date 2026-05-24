from __future__ import annotations

import subprocess


async def app_open(app_name: str) -> dict[str, str]:
    """Open an application by name."""
    subprocess.Popen(["start", app_name], shell=True)
    return {"status": "ok", "app_name": app_name}


async def app_focus(window_title: str) -> dict[str, str]:
    """Focus a window matching the provided title using PowerShell."""
    ps_script = f"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {{
    [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);
}}
"@
$p = Get-Process | Where-Object {{$_.MainWindowTitle -like '*{window_title}*'}} | Select-Object -First 1
if ($p) {{ [Win32]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Write-Output 'focused' }} else {{ Write-Output 'not_found' }}
"""
    completed = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
    return {"status": completed.stdout.strip() or "unknown", "window_title": window_title}


async def app_list_windows() -> dict[str, list[dict[str, str | int]]]:
    """List windows with non-empty titles."""
    ps_command = "Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object Id,ProcessName,MainWindowTitle | ConvertTo-Json"
    completed = subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], capture_output=True, text=True)
    return {"windows": [{"raw": completed.stdout.strip()}]}
