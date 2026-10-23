param([string]$TaskName = 'StudyVault Exam Reminders')

$ErrorActionPreference = 'Stop'
$backendPath = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workspacePath = (Resolve-Path (Join-Path $backendPath '..')).Path
$pythonPath = Join-Path $workspacePath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw 'Create the project virtual environment before registering the reminder task.'
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "Task '$TaskName' already exists. Inspect or remove it before registering a replacement."
}

$action = New-ScheduledTaskAction -Execute $pythonPath -Argument '-m app.reminder_worker --once' -WorkingDirectory $backendPath
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Hidden
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Deliver due StudyVault exam reminders independently of the web server.'
Write-Output "Registered '$TaskName'. It runs every minute while this Windows user is signed in."
