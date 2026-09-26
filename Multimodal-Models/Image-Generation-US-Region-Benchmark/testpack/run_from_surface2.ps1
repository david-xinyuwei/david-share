# Windows launcher for the US matrix (Entra bearer auth via the Azure CLI).
# Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File run_from_surface2.ps1 -Mode dry|smoke|full [-Tag us-matrix-YYYYMMDD]
# Optional environment before calling: BENCHMARK_PYTHON (interpreter), AZ_CLI (az.cmd path), AZURE_CONFIG_DIR (an
# isolated az profile, if you keep one), BENCHMARK_CLIENT_LOCATION (free-text label recorded in the run).
# While -Mode full runs, the process holds ES_SYSTEM_REQUIRED|ES_CONTINUOUS so the laptop does not sleep; the
# hold is released when the run ends (normally or by Ctrl+C). The display may still turn off.
param([ValidateSet('dry','smoke','full')][string]$Mode = 'dry', [string]$Tag = "us-matrix-$(Get-Date -Format yyyyMMdd)")
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py   = if ($env:BENCHMARK_PYTHON) { $env:BENCHMARK_PYTHON } elseif (Test-Path -LiteralPath (Join-Path $here '.venv\Scripts\python.exe')) { Join-Path $here '.venv\Scripts\python.exe' } else { 'python' }
if (-not $env:AZ_CLI) { $env:AZ_CLI = (Get-Command az.cmd -ErrorAction SilentlyContinue).Source; if (-not $env:AZ_CLI) { $env:AZ_CLI = 'az' } }
$env:RUN_TAG = $Tag
if (-not $env:BENCHMARK_CLIENT_LOCATION) { $env:BENCHMARK_CLIENT_LOCATION = "$env:COMPUTERNAME; resources East US (MAI) / East US 2 (GPT); Entra bearer auth" }
$env:PYTHONIOENCODING = 'utf-8'
[string[]]$runnerArgs = @()
if ($Mode -eq 'dry')   { $runnerArgs = @('--dry-run') }
if ($Mode -eq 'smoke') { $runnerArgs = @('--smoke') }
$log = Join-Path $here "runs\$Tag.$Mode.log"
New-Item -ItemType Directory -Force -Path (Join-Path $here 'runs') | Out-Null

$sleepBlocked = $false
if ($Mode -eq 'full') {
    Add-Type -Namespace Win32 -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
    # ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001). PowerShell 5.1 parses 0x80000001 as a
    # negative Int32, so build the value from the two flags instead of a single literal.
    $esFlags = [uint32]2147483648 + [uint32]1
    $sleepBlocked = ([Win32.Power]::SetThreadExecutionState($esFlags) -ne 0)
}
"MODE=$Mode TAG=$Tag START=$(Get-Date -Format s) PID=$PID SLEEP_BLOCKED=$sleepBlocked" | Tee-Object -FilePath $log
$code = 1
try {
    $allArgs = @('-u', (Join-Path $here 'run_us_matrix.py')) + $runnerArgs
    & $py $allArgs 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath $log -Append
    $code = $LASTEXITCODE
} finally {
    if ($sleepBlocked) { [void][Win32.Power]::SetThreadExecutionState([uint32]2147483648) }
    "EXIT=$code END=$(Get-Date -Format s)" | Tee-Object -FilePath $log -Append
}
exit $code
