if (-not $env:AOAI_ENDPOINT) { $env:AOAI_ENDPOINT = [Environment]::GetEnvironmentVariable("AOAI_ENDPOINT", "Machine") }
if (-not $env:AOAI_KEY) { $env:AOAI_KEY = [Environment]::GetEnvironmentVariable("AOAI_KEY", "Machine") }
if (-not $env:AOAI_MODEL) { $env:AOAI_MODEL = [Environment]::GetEnvironmentVariable("AOAI_MODEL", "Machine") }
if (-not $env:AOAI_KEY) { throw "AOAI_KEY is not set in the process or Machine environment" }
$appDir = if ($env:AIPC_APP_DIR) { $env:AIPC_APP_DIR } else { [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop) }
$pythonExe = if ($env:PYTHON_EXE) { $env:PYTHON_EXE } else { (Get-Command python.exe).Source }
Set-Location $appDir
$log = Join-Path $appDir "sandbox_api_$PID.log"
& $pythonExe (Join-Path $appDir "sandbox_api.py") *> $log
