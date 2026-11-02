# Register a Windows scheduled task "YouBikeCollect" that runs
# scripts/collect_local.py every 10 minutes (current user, no admin needed).
# Remove it with:  Unregister-ScheduledTask -TaskName YouBikeCollect -Confirm:$false

$repo = Split-Path $PSScriptRoot -Parent
$script = Join-Path $PSScriptRoot 'collect_local.py'
$pyw = Join-Path (Split-Path (Get-Command python).Source -Parent) 'pythonw.exe'

$now = Get-Date
$start = $now.Date.AddHours($now.Hour).AddMinutes([math]::Ceiling(($now.Minute + 1) / 10) * 10)

$action = New-ScheduledTaskAction -Execute $pyw -Argument "`"$script`"" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Minutes 10)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName 'YouBikeCollect' -Action $action -Trigger $trigger -Settings $settings `
    -Description 'YouBike snapshot every 10 min -> data branch' -Force | Out-Null

Get-ScheduledTask -TaskName 'YouBikeCollect' | Get-ScheduledTaskInfo |
    Select-Object NextRunTime, LastRunTime, LastTaskResult
