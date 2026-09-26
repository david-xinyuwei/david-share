# Render the completed run into README.md + images/, verify check-mode, run the test suite, print token-refresh evidence.
$ErrorActionPreference = 'Stop'
$py  = if ($env:BENCHMARK_PYTHON) { $env:BENCHMARK_PYTHON } else { 'python' }
$usb = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$run = 'runs/us-matrix-9g-20260926'
Set-Location -LiteralPath $usb

Write-Output "== token refresh evidence (full.log)"
Select-String -LiteralPath "$usb\runs\us-matrix-9g-20260926.full.log" -Pattern 'token has|401|refreshed' | ForEach-Object { $_.Line.Trim() } | Select-Object -Last 12

Write-Output "`n== render"
& $py render.py $run
if ($LASTEXITCODE -ne 0) { throw "render failed" }

Write-Output "`n== check"
& $py render.py $run --check
if ($LASTEXITCODE -ne 0) { throw "check failed" }

Write-Output "`n== pytest"
& $py -m pytest tests -q -rs 2>&1 | Select-Object -Last 20
$pt = $LASTEXITCODE

Write-Output "`n== artefacts"
$readme = Get-Item -LiteralPath "$usb\README.md"
$imgs = Get-ChildItem -LiteralPath "$usb\images" -Filter *.png
"README.md $($readme.Length) bytes  images $($imgs.Count) files $([math]::Round(($imgs | Measure-Object Length -Sum).Sum/1MB)) MB"
Write-Output "PYTEST_EXIT=$pt"
