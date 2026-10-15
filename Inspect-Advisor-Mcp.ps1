param(
 [string]$GameRoot='C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV',
 [string]$UserRoot="$HOME\Documents\Paradox Interactive\Hearts of Iron IV",
 [string]$Python='python',
 [ValidateSet('GER','ITA')][string]$Country='GER',
 [ValidateRange(1,600)][int]$Seconds=180
)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$r=$PSScriptRoot;$env:PYTHONPATH="$r;$r\native-research-focus";$session=$null;$task=$null;$owned=$null
function Run-Python([string[]]$Arguments){
 $prior=$ErrorActionPreference;$ErrorActionPreference='Continue'
 try{$out=& $Python @Arguments 2>&1 | ForEach-Object { $_.ToString() };$stepExit=$LASTEXITCODE}
 finally{$ErrorActionPreference=$prior}
 if($stepExit -ne 0){throw "Python step failed: $($Arguments[0]); retained session: $session; details: $($out -join [Environment]::NewLine)"}
 return $out
}
function Wait-Ready([scriptblock]$Check,[int]$Limit,[string]$Name){
 $until=(Get-Date).AddSeconds($Limit)
 while(-not (& $Check)){
  if((Get-Date) -ge $until){throw "$Name not ready; retain the session and request IDs"}
  if($owned -and -not (Get-Process -Id $owned.Id -ErrorAction SilentlyContinue)){throw 'Owned game exited'}
  Start-Sleep -Seconds 1
 }
}
Add-Type -AssemblyName System.Windows.Forms
if([System.Windows.Forms.SystemInformation]::PowerStatus.PowerLineStatus -ne 'Online'){throw 'Connect AC power before starting the MVP'}
if(@(Get-Process hoi4 -ErrorAction SilentlyContinue).Count){throw 'Close the existing game before starting the temporary MVP campaign'}
Run-Python @('-c','import mcp; import sys; assert sys.version_info >= (3,10)') | Out-Null
try{
 Write-Host "Preparing protected $Country campaign..."
 $newRoot=Join-Path "$r\sessions" ('queued-capacity-20261013-'+[guid]::NewGuid().ToString('N').Substring(0,8))
 $session=Join-Path $newRoot 'session.json'
 $prepared=Run-Python @("$r\native-research-focus\prepare_queued_capacity_session.py",'--game-root',$GameRoot,'--user-root',$UserRoot,'--session-root',$newRoot,'--country',$Country) | ConvertFrom-Json
 $session=Join-Path $prepared.root 'session.json';$config=Get-Content $session -Raw | ConvertFrom-Json
 $exe=Join-Path $GameRoot 'hoi4.exe';$launchTime=Get-Date
 $task='HOI4-MCP-MVP-'+$prepared.session_id.Substring(0,8)
 $action=New-ScheduledTaskAction -Execute $exe -WorkingDirectory $GameRoot -Argument "-debug -start_tag=$Country -start_speed=1 -autosave=NEVER -windowed"
 $principal=New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive
 $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero)
 Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Settings $settings | Out-Null
 $task | Set-Content (Join-Path $prepared.root 'launch-task.txt')
 Start-ScheduledTask -TaskName $task
 Wait-Ready { @(Get-Process hoi4 -ErrorAction SilentlyContinue).Count -eq 1 } 30 'Game process'
 Wait-Ready { $candidate=Get-Process hoi4 -ErrorAction SilentlyContinue;@($candidate).Count -eq 1 -and $candidate.Path } 30 'Readable game process identity'
 $process=Get-Process hoi4
 $owned=[pscustomobject]@{Id=$process.Id;Path=$process.Path;StartTime=$process.StartTime}
 if($owned.Path -ne $exe -or $owned.StartTime -lt $launchTime.AddSeconds(-1)){throw ('Game process ownership mismatch: '+(@{owned=$owned;expectedPath=$exe;launchTime=$launchTime}|ConvertTo-Json -Compress))}
 Write-Host "Session: $session"
 $marker='CODEX_COMMAND_SESSION|'+$prepared.session_id+'|READY|country='+$Country
 Wait-Ready { (Test-Path $config.log_path) -and (Select-String -Path $config.log_path -SimpleMatch $marker -Quiet) } 240 'Game-side startup'
 Run-Python @("$r\bind_session.py",'--session-file',$session,'--pid',[string]$owned.Id) | Write-Host
 Write-Host 'Starting native command and observation backends...'
 Run-Python @("$r\native-research-focus\install_native_session.py",'--session-file',$session) | Write-Host
 $native=Join-Path $prepared.root 'native'
 Wait-Ready { Test-Path "$native\native-observation.json" } 60 'Native daily callback'
 Run-Python @("$r\native-research-focus\install_peacetime_reader.py",'--session-file',$session) | Write-Host
 Run-Python @("$r\native-research-focus\install_time_reader.py",'--session-file',$session) | Write-Host
 Wait-Ready { Test-Path "$native\time-status.json" } 30 'Native frame callback'
 Write-Host 'Pausing and reading the advisor state through MCP...'
 Run-Python @("$r\native-research-focus\prepare_advisor_snapshot.py",'--session-file',$session) | Write-Host
 $prepared.root | Set-Content (Join-Path $r 'active-advisor-session.txt')
 $hold=Join-Path $native 'hold-open.flag';'Paused, disarmed protected campaign' | Set-Content $hold
 Write-Host "Keeping the paused campaign open on AC power: $session"
 while(Test-Path $hold){
  if([System.Windows.Forms.SystemInformation]::PowerStatus.PowerLineStatus -ne 'Online'){break}
  if(-not (Get-Process -Id $owned.Id -ErrorAction SilentlyContinue)){break}
  Start-Sleep -Seconds 2
 }

}
finally{
 if($session -and (Test-Path (Join-Path (Split-Path $session) 'recovery\manifest.json'))){
  Write-Host 'Closing the owned campaign and restoring the original profile...'
  # Covers startup failure before the READY-only bind; never terminate a reused PID.
  if($owned -and -not ((Get-Content $session -Raw | ConvertFrom-Json).process_identity)){
   $current=Get-Process -Id $owned.Id -ErrorAction SilentlyContinue
   if($current -and $current.StartTime -eq $owned.StartTime -and $current.Path -eq $exe){Stop-Process -Id $owned.Id -Force;Wait-Process -Id $owned.Id -ErrorAction SilentlyContinue}
  }
  Run-Python @("$r\native-research-focus\restore_queued_capacity_session.py",$session) | Write-Host
  if($task){Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue}
 }
}
if($testFailure){throw $testFailure}
Write-Host 'MVP demo finished. Reports and request IDs remain in the session directory.'
