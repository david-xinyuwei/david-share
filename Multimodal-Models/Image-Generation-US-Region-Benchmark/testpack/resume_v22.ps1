# One-shot: syntax-check the revised runner, dry-run it, re-freeze the run onto it, then resume the formal matrix.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = if ($env:BENCHMARK_PYTHON) { $env:BENCHMARK_PYTHON } else { 'python' }
$run = Join-Path $here 'runs\us-matrix-9g-20260926'
& $py -c "import ast,hashlib,pathlib,sys; p=pathlib.Path(sys.argv[1]); b=p.read_bytes(); ast.parse(b); print('SYNTAX_OK', hashlib.sha256(b).hexdigest())" (Join-Path $here 'source\benchmark_5way_v2.py')
if ($LASTEXITCODE) { exit 1 }
& $py (Join-Path $here 'refreeze_runner.py') $run 'v2.2: bearer token refreshed from JWT exp and on HTTP 401; resume re-runs failed samples. Payloads, pacing, prompts, latency definition unchanged.'
if ($LASTEXITCODE) { exit 1 }
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'run_from_surface2.ps1') -Mode dry -Tag us-matrix-9g-20260926
if ($LASTEXITCODE) { exit 1 }
"DRY_OK; starting full resume $(Get-Date -Format s)"
& 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here 'run_from_surface2.ps1') -Mode full -Tag us-matrix-9g-20260926
exit $LASTEXITCODE
