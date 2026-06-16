$appDir = if ($env:AIPC_APP_DIR) { $env:AIPC_APP_DIR } else { [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop) }
$pythonExe = if ($env:PYTHON_EXE) { $env:PYTHON_EXE } else { (Get-Command python.exe).Source }
$nssm = if ($env:NSSM_EXE) { $env:NSSM_EXE } else { Join-Path $appDir "nssm.exe" }
$screenshotPath = if ($env:AIPC_SCREENSHOT_PATH) { $env:AIPC_SCREENSHOT_PATH } else { Join-Path $appDir "last_screenshot.png" }

# Remove old service if exists
& $nssm stop SandboxAPI 2>&1 | Out-Null
& $nssm remove SandboxAPI confirm 2>&1 | Out-Null
Start-Sleep 2

# Read Machine env vars
$ep = [Environment]::GetEnvironmentVariable("AOAI_ENDPOINT","Machine")
$key = [Environment]::GetEnvironmentVariable("AOAI_KEY","Machine")
$model = [Environment]::GetEnvironmentVariable("AOAI_MODEL","Machine")

# Install service
& $nssm install SandboxAPI $pythonExe (Join-Path $appDir "sandbox_api.py")
& $nssm set SandboxAPI AppDirectory $appDir
& $nssm set SandboxAPI AppRestartDelay 3000
& $nssm set SandboxAPI AppEnvironmentExtra "AOAI_ENDPOINT=$ep" "AOAI_KEY=$key" "AOAI_MODEL=$model" "AIPC_APP_DIR=$appDir" "AIPC_HOST_DATA_DIR=$appDir" "AIPC_RUNTIME_DIR=$appDir" "AIPC_SCREENSHOT_PATH=$screenshotPath"
& $nssm set SandboxAPI AppStdout (Join-Path $appDir "sandbox_service.log")
& $nssm set SandboxAPI AppStderr (Join-Path $appDir "sandbox_service.log")
& $nssm set SandboxAPI AppStdoutCreationDisposition 4
& $nssm set SandboxAPI AppStderrCreationDisposition 4
# Password: read from env var or prompt interactively (never hardcode)
if ($env:NSSM_SERVICE_PASSWORD) {
	$pw = $env:NSSM_SERVICE_PASSWORD
} else {
	$secure = Read-Host "Enter aipcadmin password" -AsSecureString
	$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
	try { $pw = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) }
	finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}
& $nssm set SandboxAPI ObjectName ".\aipcadmin" $pw

# Create/update interactive screenshot helper. This must run as the logged-in desktop user.
$captureScript = Join-Path $appDir "capture_screenshot.ps1"
schtasks.exe /Create /F /TN ScreenshotHelper /SC ONCE /ST 23:59 /RL HIGHEST /IT /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$captureScript`" -OutputPath `"$screenshotPath`"" | Out-Null

& $nssm start SandboxAPI
Start-Sleep 3
Write-Output "=== Service status ==="
& $nssm status SandboxAPI
