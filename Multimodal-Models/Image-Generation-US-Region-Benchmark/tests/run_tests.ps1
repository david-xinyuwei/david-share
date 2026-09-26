# Runs the suite and writes the transcript beside this script; exit code is pytest's.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$py = if ($env:BENCHMARK_PYTHON) { $env:BENCHMARK_PYTHON } else { 'python' }
Set-Location -LiteralPath $root
& $py -m pip install --quiet --disable-pip-version-check -r requirements.txt 2>&1 | Out-Null
& $py -m pytest tests -q -p no:cacheprovider 2>&1 | Tee-Object -FilePath (Join-Path $PSScriptRoot 'last-run.txt')
exit $LASTEXITCODE
