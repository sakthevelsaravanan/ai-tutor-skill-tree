$ErrorActionPreference = 'Stop'
$repoPath = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoPath
if (Test-Path .runtime/processes.json) {
    $entries = Get-Content .runtime/processes.json -Raw | ConvertFrom-Json -AsHashtable
    foreach ($entry in $entries.Values) {
        $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
        if ($process -and $process.StartTime.ToUniversalTime().ToString('o') -eq $entry.started) {
            Stop-Process -Id $process.Id
        }
    }
}
$pgData = Join-Path $repoPath '.runtime\postgres'
& 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' -D $pgData -m fast -w stop
Write-Output 'Local application stopped. Database and vector data remain on disk.'
