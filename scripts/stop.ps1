$ErrorActionPreference = 'Stop'
$repoPath = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoPath
if (Test-Path .runtime/processes.json) {
    try {
        $jsonObj = Get-Content .runtime/processes.json -Raw | ConvertFrom-Json
        foreach ($prop in $jsonObj.PSObject.Properties) {
            $entry = $prop.Value
            $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
            if ($process -and $process.StartTime.ToUniversalTime().ToString('o') -eq $entry.started) {
                Stop-Process -Id $process.Id -Force
            }
        }
    } catch {}
}
$pgData = Join-Path $repoPath '.runtime\postgres'
$localPgCtl = Join-Path $repoPath '.runtime\pgsql\bin\pg_ctl.exe'
$pgCtl = if (Test-Path $localPgCtl) { $localPgCtl } else { 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe' }
& $pgCtl -D $pgData -m fast -w stop
Write-Output 'Local application stopped. Database and vector data remain on disk.'
