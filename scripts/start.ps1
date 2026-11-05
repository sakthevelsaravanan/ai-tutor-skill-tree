$ErrorActionPreference = 'Stop'
$repoPath = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repoPath
$logPath = Join-Path $repoPath '.runtime\logs'
New-Item -ItemType Directory -Force -Path $logPath | Out-Null
$pgCtl = 'C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe'
$pgData = Join-Path $repoPath '.runtime\postgres'
if (-not (Test-Path -LiteralPath (Join-Path $pgData 'PG_VERSION'))) {
    throw 'Initialize PostgreSQL first using the steps in README.md.'
}
& $pgCtl -D $pgData status *> $null
if ($LASTEXITCODE -ne 0) {
    $pgLog = Join-Path $logPath 'postgres.log'
    $pgArgs = @('-D', ('"' + $pgData + '"'), '-l', ('"' + $pgLog + '"'), '-o', '"-p 5433 -h 127.0.0.1"', '-w', 'start')
    $pgStart = Start-Process -FilePath $pgCtl -ArgumentList $pgArgs -WindowStyle Hidden -Wait -PassThru
    if ($pgStart.ExitCode -ne 0) { throw 'PostgreSQL did not start; inspect .runtime/logs/postgres.log.' }
}
$processes = @{}
if (Test-Path .runtime/processes.json) {
    try {
        $jsonObj = Get-Content .runtime/processes.json -Raw | ConvertFrom-Json
        foreach ($prop in $jsonObj.PSObject.Properties) {
            $processes[$prop.Name] = $prop.Value
        }
    } catch {}
}
foreach ($service in @('backend','frontend')) {
    $port = if ($service -eq 'backend') { 8000 } else { 3000 }
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if ($listener) {
        $healthUrl = if ($service -eq 'backend') { 'http://127.0.0.1:8000/health' } else { 'http://127.0.0.1:3000/api/health' }
        try { $health = Invoke-RestMethod $healthUrl -TimeoutSec 5 } catch { throw "Port $port is already occupied by another service." }
        if ($health.database -ne 'PostgreSQL' -or $health.database_name -ne 'ai_tutor_db') { throw "Unexpected service on port $port." }
        continue
    }
    if ($service -eq 'backend') {
        $executable = (Get-Command python).Source
        $arguments = @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000')
        $workingPath = $repoPath
    } else {
        $buildDir = '.next'
        if (Test-Path .runtime/frontend-build-dir) { $buildDir = (Get-Content .runtime/frontend-build-dir -Raw).Trim() }
        if ($buildDir -notmatch '^\.next(?:-[a-z0-9-]+)?$') { throw 'Invalid frontend build directory.' }
        $env:NEXT_DIST_DIR = $buildDir
        if (-not (Test-Path (Join-Path "frontend/$buildDir" 'BUILD_ID'))) { throw 'Run npm run build in frontend first.' }
        $executable = (Get-Command node).Source
        $arguments = @('node_modules/next/dist/bin/next','start','-p','3000','-H','127.0.0.1')
        $workingPath = Join-Path $repoPath 'frontend'
    }
    $process = Start-Process -FilePath $executable -ArgumentList $arguments -WorkingDirectory $workingPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logPath "$service.out.log") -RedirectStandardError (Join-Path $logPath "$service.err.log")
    $processes[$service] = @{ id=$process.Id; started=$process.StartTime.ToUniversalTime().ToString('o') }
    $processes | ConvertTo-Json | Set-Content .runtime/processes.json
}
Write-Output 'Starting AI Tutor at http://localhost:3000. Credentials: LOCAL_ACCESS.md. Logs: .runtime/logs.'
