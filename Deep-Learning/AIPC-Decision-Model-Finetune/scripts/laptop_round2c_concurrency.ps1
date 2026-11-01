<#
Snapdragon laptop concurrency sweep for the delivered round-2 C model, the laptop counterpart of the x86-64 sweep in
验证结果\端侧引擎_x64并发_20261031-013937\: the client keeps 1 / 2 / 4 / 8 requests in flight against the default 4 server
slots, then 8 in flight against 8 slots (-np 8). Every tier scores the same 170 support + 159 assistant requests and is
compared per question with C's PyTorch rows, so the answer-agreement column shows whether concurrency changes answers.

Run from the project root on the laptop (PowerShell 7), after laptop_round2c_eval.ps1 has passed:
  .\scripts\laptop_round2c_concurrency.ps1
  .\scripts\laptop_round2c_concurrency.ps1 -Model D:\models\Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf -Bin C:\Tools\llama.cpp\b11935-cpu
Writes 验证结果\端侧引擎_骁龙并发第二轮C_<yyyyMMdd-HHmmss>\ (five run folders + machine.json + summary\). About 5 x 6 minutes.
Plug in, close other CPU-heavy programs, do not use the laptop during the run. Does not train, calibrate or call any cloud model.
#>
param(
    [string] $Model = 'C:\Tools\models\contoso-kev\Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf',
    [string] $Bin = 'C:\Tools\llama.cpp\b11935-cpu',
    [string] $OutRoot = '',
    [int[]] $Concurrency = @(1, 2, 4, 8),
    [switch] $SkipNp8
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $expectedSha = 'c427ed7a8e797e1f6b6a838a80d4c32d8735b85dfa742f2dafba89307808ad05'
    if (-not (Test-Path -LiteralPath $Model)) { throw "model not found: $Model" }
    $sha = (Get-FileHash -LiteralPath $Model -Algorithm SHA256).Hash.ToLower()
    if ($sha -ne $expectedSha) { throw "SHA-256 mismatch for $Model`n  have $sha`n  want $expectedSha" }
    if (-not (Test-Path -LiteralPath (Join-Path $Bin 'llama-server.exe'))) { throw "llama-server.exe not found under $Bin" }
    $torch = '验证结果\第二轮微调评测_20261101-101948\runs\0.8b\r2-C-'
    foreach ($w in 'support', 'assistant') { if (-not (Test-Path -LiteralPath "${torch}test_$w\rows.json")) { throw "PyTorch rows missing: ${torch}test_$w\rows.json (git pull first)" } }
    if (-not $OutRoot) { $OutRoot = "验证结果\端侧引擎_骁龙并发第二轮C_$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
    New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
    "model OK ($($sha.Substring(0,16))…); results -> $OutRoot"

    $tiers = @($Concurrency | ForEach-Object { @{ Label = "r2c-kev-0.8b-Q8_0-cpu-c$_"; Conc = $_; Np = 0 } })
    if (-not $SkipNp8) { $tiers += @{ Label = 'r2c-kev-0.8b-Q8_0-cpu-c8np8'; Conc = 8; Np = 8 } }
    foreach ($t in $tiers) {
        "== $($t.Label)  concurrency=$($t.Conc) np=$($t.Np)  $(Get-Date -Format 'HH:mm:ss') =="
        & (Join-Path $PSScriptRoot 'run_engine_eval.ps1') -Model $Model -Label $t.Label -Backend cpu -Bin $Bin -OutRoot $OutRoot `
            -TorchPrefix $torch -Concurrency $t.Conc -Parallel $t.Np
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { throw "run_engine_eval failed for $($t.Label)" }
    }

    $cs = Get-CimInstance Win32_ComputerSystem; $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1; $os = Get-CimInstance Win32_OperatingSystem
    [ordered]@{
        captured = (Get-Date).ToString('o'); execution_plane = 'CUSTOMER_LAPTOP_WINDOWS'
        machine = "$($cs.Manufacturer) $($cs.Model); $($cpu.Name), $($cpu.NumberOfCores) cores / $($cpu.NumberOfLogicalProcessors) threads; $([math]::Round($cs.TotalPhysicalMemory/1GB)) GB RAM"
        os = "$($os.Caption) $($os.Version)"; os_architecture = $os.OSArchitecture
        engine = "llama.cpp $(Split-Path -Leaf $Bin) Windows ARM64 CPU package"
        model = 'Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf (round-2 arm C, T = 2.83)'; model_sha256 = $sha
        pytorch_reference = '验证结果/第二轮微调评测_20261101-101948/runs/0.8b/r2-C-test_{support,assistant}/rows.json'
        x64_counterpart = '验证结果/端侧引擎_x64并发_20261031-013937/ (published FT-cf, same tiers, AMD EPYC 7763 VM)'
        sequential_counterpart = 'laptop_round2c_eval.ps1 output (same model, concurrency 1, default and lean arguments)'
        runs = @($tiers | ForEach-Object { @{ directory = $_.Label; client_concurrency = $_.Conc; server_slots = $(if ($_.Np) { $_.Np } else { 'default (4)' }) } })
        scope = 'Concurrency sweep on the laptop: throughput (requests per second), latency distribution, peak memory and per-question agreement with PyTorch as the client keeps more requests in flight. One run per tier.'
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutRoot 'machine.json') -Encoding utf8
    python scripts\summarize_engine.py --root $OutRoot --output-dir (Join-Path $OutRoot 'summary') | Out-Null

    ""
    "tier        in-flight  slots  support p50/p90 ms   req/s   peak WS MiB  support acc"
    foreach ($t in $tiers) {
        $r = Get-Content -LiteralPath (Join-Path $OutRoot "$($t.Label)\run.json") -Raw | ConvertFrom-Json
        $s = $r.summaries.support
        "{0,-11} {1,9} {2,6} {3,8} / {4,-9} {5,5}  {6,11}  {7:P1}" -f $t.Label.Substring(21), $t.Conc, $(if ($t.Np) { $t.Np } else { 4 }), $s.latency_ms.p50, $s.latency_ms.p90, $s.requests_per_second, $r.peak_working_set_mib, $s.accuracy
    }
    "__LAPTOP_R2C_CONCURRENCY_DONE__ $OutRoot"
}
finally { Pop-Location }
