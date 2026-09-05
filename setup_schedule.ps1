# Windows タスクスケジューラに 1日3回の自動実行を登録する。
# 使い方: PowerShell を開き、このフォルダで  .\setup_schedule.ps1
# 解除:   .\setup_schedule.ps1 -Remove
param([switch]$Remove)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (Get-Command python).Source
$slots = @{ "morning" = "07:30"; "noon" = "12:15"; "night" = "20:30" }

foreach ($slot in $slots.Keys) {
    $name = "RakutenAffiliate_$slot"
    if ($Remove) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "削除: $name"
        continue
    }
    $action = New-ScheduledTaskAction -Execute $python -Argument "main.py run --slot $slot" -WorkingDirectory $here
    $trigger = New-ScheduledTaskTrigger -Daily -At $slots[$slot]
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
    Write-Host "登録: $name  毎日 $($slots[$slot])"
}
if (-not $Remove) {
    Write-Host ""
    Write-Host "確認: Get-ScheduledTask -TaskName 'RakutenAffiliate_*'"
    Write-Host "PCがスリープ中は実行されません。電源オプションでスリープを無効にするか、ノートPCなら蓋を閉じても動く設定にしてください。"
}
