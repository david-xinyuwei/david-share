<#
Snapdragon laptop regression of the round-2 C model (Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf), the exact counterpart of the
published FT-cf laptop runs in 验证结果\端侧引擎_20261027-124700\ftcf-kev-0.8b-Q8_0-cpu\: same llama.cpp b11935 ARM64 CPU
package, same server arguments, same 170 support + 159 assistant requests, one request at a time, compared per question with
C's own PyTorch rows (验证结果\第二轮微调评测_20261101-101948\runs\0.8b\r2-C-test_*\rows.json). Then the lean deployment
arguments (-c 2048 -b 512 -ub 512) once more, to confirm they change no answer on this machine either.

Run from the project root on the laptop (PowerShell 7). Default model path = README B7 location:
  .\scripts\laptop_round2c_eval.ps1
  .\scripts\laptop_round2c_eval.ps1 -Model D:\models\Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf -Bin C:\Tools\llama.cpp\b11935-cpu
Writes 验证结果\端侧引擎_骁龙第二轮C_<yyyyMMdd-HHmmss>\ (three run folders + machine.json + summary\) and prints a 6-line result.
Does not train, calibrate, call any cloud model, or change the published FT-cf results.
#>
param(
    [string] $Model = 'C:\Tools\models\contoso-kev\Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf',
    [string] $Bin = 'C:\Tools\llama.cpp\b11935-cpu',   # ARM64 CPU build used by every laptop row in the README
    [string] $OutRoot = '',                              # default: 验证结果\端侧引擎_骁龙第二轮C_<stamp>
    [switch] $SkipLean                                   # omit the -c 2048 -ub 512 run
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $expectedSha = 'c427ed7a8e797e1f6b6a838a80d4c32d8735b85dfa742f2dafba89307808ad05'   # 验证结果\第二轮微调评测_20261101-101948\gguf\0.8b-r2C\gguf.sha256
    if (-not (Test-Path -LiteralPath $Model)) { throw "model not found: $Model (pull it from FY27 first; see [RELAY]_Cloud-Local.md)" }
    $sha = (Get-FileHash -LiteralPath $Model -Algorithm SHA256).Hash.ToLower()
    if ($sha -ne $expectedSha) { throw "SHA-256 mismatch for $Model`n  have $sha`n  want $expectedSha" }
    "model OK: $Model  sha256=$($sha.Substring(0,16))…"
    if (-not (Test-Path -LiteralPath (Join-Path $Bin 'llama-server.exe'))) { throw "llama-server.exe not found under $Bin" }
    $torch = '验证结果\第二轮微调评测_20261101-101948\runs\0.8b\r2-C-'
    foreach ($w in 'support', 'assistant') { if (-not (Test-Path -LiteralPath "${torch}test_$w\rows.json")) { throw "PyTorch rows missing: ${torch}test_$w\rows.json (git pull the repository first)" } }
    if (-not $OutRoot) { $OutRoot = "验证结果\端侧引擎_骁龙第二轮C_$(Get-Date -Format 'yyyyMMdd-HHmmss')" }
    New-Item -ItemType Directory -Force -Path $OutRoot | Out-Null
    "results -> $OutRoot"

    $runs = @(
        @{ Label = 'r2c-kev-0.8b-Q8_0-cpu';      Ctx = 8192; UBatch = 2048 },
        @{ Label = 'r2c-kev-0.8b-Q8_0-cpu-run2'; Ctx = 8192; UBatch = 2048 }
    )
    if (-not $SkipLean) { $runs += @{ Label = 'r2c-kev-0.8b-Q8_0-cpu-c2048-ub512'; Ctx = 2048; UBatch = 512 } }
    foreach ($r in $runs) {
        "== $($r.Label)  $(Get-Date -Format 'HH:mm:ss') =="
        & (Join-Path $PSScriptRoot 'run_engine_eval.ps1') -Model $Model -Label $r.Label -Backend cpu -Bin $Bin -OutRoot $OutRoot `
            -Ctx $r.Ctx -UBatch $r.UBatch -TorchPrefix $torch
        if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { throw "run_engine_eval failed for $($r.Label)" }
    }

    # machine record (same shape as the x64 one)
    $cs = Get-CimInstance Win32_ComputerSystem; $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1; $os = Get-CimInstance Win32_OperatingSystem
    $machine = [ordered]@{
        captured = (Get-Date).ToString('o'); execution_plane = 'CUSTOMER_LAPTOP_WINDOWS'
        machine = "$($cs.Manufacturer) $($cs.Model); $($cpu.Name), $($cpu.NumberOfCores) cores / $($cpu.NumberOfLogicalProcessors) threads; $([math]::Round($cs.TotalPhysicalMemory/1GB)) GB RAM"
        os = "$($os.Caption) $($os.Version)"; os_architecture = $os.OSArchitecture
        engine = "llama.cpp $(Split-Path -Leaf $Bin) Windows ARM64 CPU package (same folder as the published FT-cf laptop runs)"
        model = 'Contoso-Kev-0.8B-FTcf-R2C-Q8_0.gguf (round-2 arm C: train_cf2, 4 epochs, T = 2.83)'; model_sha256 = $sha
        pytorch_reference = '验证结果/第二轮微调评测_20261101-101948/runs/0.8b/r2-C-test_support/rows.json and r2-C-test_assistant/rows.json'
        ftcf_counterpart_same_laptop = '验证结果/端侧引擎_20261027-124700/ftcf-kev-0.8b-Q8_0-cpu/ (published FT-cf, same laptop, same engine build and arguments)'
        x64_counterpart = '验证结果/端侧引擎_x64第二轮C_20261101-171344/ (same model on the AMD EPYC 7763 VM)'
        runs = @($runs | ForEach-Object { @{ directory = $_.Label; arguments = "-c $($_.Ctx) -b $($_.UBatch) -ub $($_.UBatch) --cache-ram 0" } })
        scope = 'Laptop regression of the round-2 C model against the published FT-cf on the same machine: accuracy, per-question agreement with PyTorch, latency and memory under identical arguments; plus the lean -c 2048 check. One request at a time.'
    }
    $machine | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutRoot 'machine.json') -Encoding utf8
    python scripts\summarize_engine.py --root $OutRoot --output-dir (Join-Path $OutRoot 'summary') | Out-Null

    # six-line result vs the published FT-cf laptop run
    $ft = Get-Content -LiteralPath '验证结果\端侧引擎_20261027-124700\ftcf-kev-0.8b-Q8_0-cpu\run.json' -Raw | ConvertFrom-Json
    $c1 = Get-Content -LiteralPath (Join-Path $OutRoot 'r2c-kev-0.8b-Q8_0-cpu\run.json') -Raw | ConvertFrom-Json
    ""
    "RESULT (this laptop)              FT-cf (published)        C (round 2)"
    "support accuracy                  {0,-24} {1}" -f ('{0:P1}' -f $ft.summaries.support.accuracy), ('{0:P1}' -f $c1.summaries.support.accuracy)
    "assistant accuracy                {0,-24} {1}" -f ('{0:P1}' -f $ft.summaries.assistant.accuracy), ('{0:P1}' -f $c1.summaries.assistant.accuracy)
    "support / assistant median ms     {0,-24} {1}" -f "$($ft.summaries.support.latency_ms.p50) / $($ft.summaries.assistant.latency_ms.p50)", "$($c1.summaries.support.latency_ms.p50) / $($c1.summaries.assistant.latency_ms.p50)"
    "peak working set / commit MiB     {0,-24} {1}" -f "$($ft.peak_working_set_mib) / $($ft.private_mib)", "$($c1.peak_working_set_mib) / $($c1.private_mib)"
    if (-not $SkipLean) { $lean = Get-Content -LiteralPath (Join-Path $OutRoot 'r2c-kev-0.8b-Q8_0-cpu-c2048-ub512\run.json') -Raw | ConvertFrom-Json
        "C lean -c 2048: accuracy {0:P1} / {1:P1}, peak WS {2} MiB, commit {3} MiB" -f $lean.summaries.support.accuracy, $lean.summaries.assistant.accuracy, $lean.peak_working_set_mib, $lean.private_mib }
    "__LAPTOP_R2C_DONE__ $OutRoot"
}
finally { Pop-Location }
