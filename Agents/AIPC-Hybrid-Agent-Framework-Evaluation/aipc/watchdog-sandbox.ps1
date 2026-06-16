# SandboxAPI Watchdog - check 8507 every 30s, restart if down
# Deploy to AIPC as schtask: runs every 1 minute, checks health, restarts if needed

$port = 8507
$taskName = "SandboxAPI"
$appDir = if ($env:AIPC_APP_DIR) { $env:AIPC_APP_DIR } else { [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop) }
$logFile = Join-Path $appDir "watchdog.log"

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $logFile -Value "$ts $msg"
}

try {
    $response = Invoke-WebRequest -Uri "http://localhost:$port/api/sandbox/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        # Healthy, do nothing
        exit 0
    }
} catch {
    # Not responding - restart
    Write-Log "8507 DOWN - restarting SandboxAPI..."
    
    # Kill any lingering python on 8507
    $proc = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($proc) {
        Stop-Process -Id $proc.OwningProcess -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    
    # Trigger the main schtask
    schtasks /Run /TN $taskName 2>&1 | Out-Null
    Write-Log "SandboxAPI schtask triggered"
}
