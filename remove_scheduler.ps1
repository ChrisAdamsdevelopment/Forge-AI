"""PowerShell script to remove the Forge-AI Windows Scheduled Task.

Unregisters the ForgeAI scheduled task. Requires administrative privileges.

Usage:
    PowerShell -ExecutionPolicy Bypass -File remove_scheduler.ps1
"""

# Requires admin privileges
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script requires administrative privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Red
    exit 1
}

$TaskName = "ForgeAI"

Write-Host "Removing Windows Scheduled Task: $TaskName" -ForegroundColor Cyan

try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    
    if (-not $task) {
        Write-Host "Task not found: $TaskName" -ForegroundColor Yellow
        Write-Host "Nothing to remove." -ForegroundColor Gray
        exit 0
    }
    
    Write-Host "Found task: $TaskName" -ForegroundColor Gray
    Write-Host "Status: $($task.State)" -ForegroundColor Gray
    
    # Unregister the task
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    
    Write-Host "✓ Task removed successfully!" -ForegroundColor Green
    Write-Host "" -ForegroundColor Gray
    Write-Host "The Forge-AI auto-start task has been removed." -ForegroundColor Gray
    Write-Host "To restore it, run: setup_scheduler.ps1" -ForegroundColor Gray
    
    exit 0
}
catch {
    Write-Host "ERROR: Failed to remove scheduled task" -ForegroundColor Red
    Write-Host "Details: $_" -ForegroundColor Red
    exit 1
}
