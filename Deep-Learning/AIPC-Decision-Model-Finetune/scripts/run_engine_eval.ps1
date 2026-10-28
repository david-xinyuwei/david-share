<#
On-device engine run: start llama-server (b11935, CPU or Adreno OpenCL build) with one GGUF, score the Contoso test
sets through /v1/systemone, record process memory, compare per question with the PyTorch rows, stop the server.
Default server flags match the first released-model runs (-c 8192 -b 2048 -ub 2048 --cache-ram 0); -Ctx/-UBatch change them.

  .\scripts\run_engine_eval.ps1 -Model C:\Tools\models\contoso-kev\Contoso-Kev-0.8B-FT-Q8_0.gguf -Label ft-kev-0.8b-Q8_0-cpu `
      -TorchPrefix 验证结果\微调评测_X\runs\0.8b\ft-
  .\scripts\run_engine_eval.ps1 -Model ggml-org/Kev-0.8B-GGUF:Q8_0 -Label released-kev-0.8b-Q8_0-opencl -Backend opencl `
      -TorchPrefix 验证结果\端侧引擎_20261027-124700\pytorch-b0-0.8b\

-TorchPrefix + "<workload>\rows.json" (released runs) or + "test_<workload>\rows.json" (kev run folders) must exist for parity.
#>
param(
    [Parameter(Mandatory)] [string] $Model,
    [Parameter(Mandatory)] [string] $Label,
    [ValidateSet('cpu', 'opencl')] [string] $Backend = 'cpu',
    [string] $TorchPrefix = '',
    [string[]] $Workloads = @('support', 'assistant'),
    [int] $Port = 8080,
    [int] $Ctx = 8192,      # -c; the lean deployment check uses 2048 (inputs are ~500 tokens)
    [int] $UBatch = 2048,   # -b and -ub; the lean deployment check uses 512
    [string] $DataPrefix = 'test_'  # 'policy_test_' scores the prompt-only variant (policy text in every question)
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$bin = if ($Backend -eq 'cpu') { 'C:\Tools\llama.cpp\b11935-cpu' } else { 'C:\Tools\llama.cpp\b11935-opencl-adreno' }
$out = Join-Path $root "验证结果\端侧引擎_20261027-124700\$Label"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$log = Join-Path $env:TEMP "llama-server-$Label.log"

$argList = @()
if (Test-Path -LiteralPath $Model) { $argList += @('-m', ('"{0}"' -f (Resolve-Path -LiteralPath $Model).Path)) } else { $argList += @('-hf', $Model) }
$argList += @('--host', '127.0.0.1', '--port', "$Port", '-c', "$Ctx", '-b', "$UBatch", '-ub', "$UBatch", '--cache-ram', '0')
if ($Backend -eq 'opencl') { $argList += @('-ngl', '99') }
$portDeadline = (Get-Date).AddSeconds(60)  # the previous run's server may still be releasing the port
while (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    if ((Get-Date) -gt $portDeadline) { throw "port $Port is still in use after 60 s" }
    Start-Sleep -Milliseconds 500
}

$server = Start-Process -FilePath (Join-Path $bin 'llama-server.exe') -ArgumentList $argList -PassThru -WindowStyle Hidden `
    -RedirectStandardError $log -RedirectStandardOutput "$log.out"
$result = [ordered]@{ label = $Label; model = $Model; backend = $Backend; build = (Split-Path -Leaf $bin); server_args = ($argList -join ' '); data_prefix = $DataPrefix }
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $ready = $false
    while (-not $ready -and $sw.Elapsed.TotalSeconds -lt 900) {
        if ($server.HasExited) { throw "llama-server exited with code $($server.ExitCode); see $log" }
        try { $ready = (Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3).StatusCode -eq 200 } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw "llama-server not healthy after 900 s; see $log" }
    $result.load_seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    $result.server_log_facts = @(Select-String -LiteralPath $log -Pattern 'decision model type|ggml_opencl: device|offloaded|CPU_REPACK model buffer|OpenCL model buffer|CPU model buffer|KV buffer size|compute buffer size|file type|model size' | ForEach-Object { $_.Line.Trim() })

    foreach ($w in $Workloads) {
        $data = Join-Path $root "data\contoso\final\$DataPrefix$w.jsonl"
        python (Join-Path $root 'scripts\systemone_client.py') --url "http://127.0.0.1:$Port/v1/systemone" --data $data --out (Join-Path $out $w)
        if ($LASTEXITCODE -ne 0) { throw "client failed for $w" }
        if ($TorchPrefix) {
            $torch = @("$TorchPrefix$w\rows.json", "${TorchPrefix}test_$w\rows.json") | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
            if ($torch) {
                python (Join-Path $root 'scripts\parity.py') --torch $torch --engine (Join-Path $out "$w\rows.jsonl") --out (Join-Path $out "$w\parity_vs_pytorch.json")
            } else { Write-Warning "no PyTorch rows for $w under $TorchPrefix" }
        }
    }

    $server.Refresh()
    $proc = Get-Process -Id $server.Id
    $result.peak_working_set_mib = [int]($proc.PeakWorkingSet64 / 1MB)
    $result.working_set_mib = [int]($proc.WorkingSet64 / 1MB)
    $result.private_mib = [int]($proc.PrivateMemorySize64 / 1MB)
    $result.cpu_seconds = [int]$proc.TotalProcessorTime.TotalSeconds
    if ($Backend -eq 'opencl') {
        $gpu = Get-Counter -Counter '\GPU Process Memory(*)\Shared Usage', '\GPU Process Memory(*)\Dedicated Usage' -ErrorAction SilentlyContinue
        $mine = $gpu.CounterSamples | Where-Object { $_.InstanceName -like "pid_$($server.Id)_*" }
        $result.gpu_shared_mib = [int](($mine | Where-Object { $_.Path -like '*shared usage' } | Measure-Object CookedValue -Sum).Sum / 1MB)
        $result.gpu_dedicated_mib = [int](($mine | Where-Object { $_.Path -like '*dedicated usage' } | Measure-Object CookedValue -Sum).Sum / 1MB)
    }
    if (Test-Path -LiteralPath $Model) {
        $result.gguf_mib = [math]::Round((Get-Item -LiteralPath $Model).Length / 1MB, 1)
        $result.gguf_sha256 = (Get-FileHash -LiteralPath $Model -Algorithm SHA256).Hash.ToLower()
    }
    $result.captured = (Get-Date).ToString('o')
    $result.summaries = @{}
    foreach ($w in $Workloads) { $result.summaries[$w] = Get-Content -LiteralPath (Join-Path $out "$w\summary.json") -Raw | ConvertFrom-Json }
}
finally {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force; $null = $server.WaitForExit(30000) }
    Copy-Item -LiteralPath $log -Destination (Join-Path $out 'server.log') -Force -ErrorAction SilentlyContinue
}
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $out 'run.json') -Encoding utf8
[pscustomobject]$result | Select-Object label, backend, load_seconds, peak_working_set_mib, private_mib, gpu_shared_mib | Format-List
foreach ($w in $Workloads) { "{0}: acc={1} p50={2} ms p90={3} ms" -f $w, $result.summaries[$w].accuracy, $result.summaries[$w].latency_ms.p50, $result.summaries[$w].latency_ms.p90 }
Write-Output "__ENGINE_EVAL_DONE__ $Label"
