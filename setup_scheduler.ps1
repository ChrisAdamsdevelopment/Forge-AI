"""PowerShell script to create Windows Scheduled Task for Forge-AI auto-start.

Creates a task that launches Forge-AI when the user logs in with auto-restart
on failure. Requires administrative privileges.

Usage:
    PowerShell -ExecutionPolicy Bypass -File setup_scheduler.ps1
"""

# Requires admin privileges
if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script requires administrative privileges." -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Red
    exit 1
}

# Configuration
$TaskName = "ForgeAI"
$TaskDescription = "Forge-AI MCP Agent Platform - Auto-start on user logon"
$RepoRoot = (Get-Item $PSScriptRoot).FullName
$StartScript = Join-Path $RepoRoot "start_agent.bat"
$LogDir = Join-Path $env:USERPROFILE ".forge" "logs" "scheduler"

# Create log directory
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    Write-Host "Created log directory: $LogDir" -ForegroundColor Green
}

# Verify start_agent.bat exists
if (-not (Test-Path $StartScript)) {
    Write-Host "ERROR: start_agent.bat not found at: $StartScript" -ForegroundColor Red
    exit 1
}

Write-Host "Setting up Windows Scheduled Task: $TaskName" -ForegroundColor Cyan
Write-Host "Start script: $StartScript" -ForegroundColor Gray
Write-Host "Repo root: $RepoRoot" -ForegroundColor Gray

# Remove existing task if present
try {
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "Removing existing task: $TaskName..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}
catch {
    Write-Host "Note: No existing task to remove." -ForegroundColor Gray
}

# Create task trigger (run at user logon)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Create task action (run batch file)
$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$StartScript`"" `
    -WorkingDirectory $RepoRoot

# Create task settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)  # Unlimited

# Configure restart on failure: restart every 5 minutes, max 3 restarts
$settings.RestartCount = 3
$settings.RestartInterval = [TimeSpan]::FromMinutes(5)

# Create the principal with highest privileges
$principal = New-ScheduledTaskPrincipal `
    -UserID "$env:USERDOMAIN\$env:USERNAME" `
    -RunLevel Highest `
    -LogonType Interactive

# Register the task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Trigger $trigger `
        -Action $action `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null
    
    Write-Host "✓ Task created successfully!" -ForegroundColor Green
    Write-Host "" -ForegroundColor Gray
    Write-Host "Task Details:" -ForegroundColor Cyan
    Write-Host "  Name:           $TaskName" -ForegroundColor Gray
    Write-Host "  Trigger:        At user logon" -ForegroundColor Gray
    Write-Host "  Action:         Run $StartScript" -ForegroundColor Gray
    Write-Host "  Privileges:     Highest" -ForegroundColor Gray
    Write-Host "  On Failure:     Restart every 5 minutes (max 3 restarts)" -ForegroundColor Gray
    Write-Host "  Time Limit:     Unlimited" -ForegroundColor Gray
    Write-Host "" -ForegroundColor Gray
}
catch {
    Write-Host "ERROR: Failed to create scheduled task" -ForegroundColor Red
    Write-Host "Details: $_" -ForegroundColor Red
    exit 1
}

# Verify task creation
try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "Verification:" -ForegroundColor Cyan
        Write-Host "  Task found in Task Scheduler" -ForegroundColor Green
        Write-Host "  Status: $($task.State)" -ForegroundColor Gray
        Write-Host "" -ForegroundColor Gray
        Write-Host "The task will run automatically when you log in." -ForegroundColor Green
        Write-Host "To remove the task later, run: remove_scheduler.ps1" -ForegroundColor Gray
    }
    else {
        Write-Host "WARNING: Task may not have been created properly." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "WARNING: Could not verify task creation: $_" -ForegroundColor Yellow
}

exit 0
