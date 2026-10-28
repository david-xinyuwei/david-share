<#
Recompute parity.py for every engine run under 验证结果\端侧引擎_20261027-124700 against the matching PyTorch rows
(the run label says which model and test-set variant it served). Used after parity.py started storing 6 decimals.
  .\scripts\refresh_parity.ps1
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$E = Join-Path $root '验证结果\端侧引擎_20261027-124700'
foreach ($d in Get-ChildItem -LiteralPath $E -Directory | Where-Object { $_.Name -notlike 'pytorch-*' }) {
    $kind, $null, $size, $null, $null, $variant = $d.Name -split '-', 6
    $ref = switch ($kind) {
        'released' { if ($variant -eq 'policy') { "pytorch-b0policy-$size" } else { "pytorch-b0-$size" } }
        'ft' { "pytorch-ft-$size" }
        'ftcf' { "pytorch-ftcf-$size" }
    }
    foreach ($w in 'support', 'assistant') {
        $torch = Join-Path $E "$ref\$w\rows.json"
        $engine = Join-Path $d.FullName "$w\rows.jsonl"
        $done = Join-Path $d.FullName "$w\summary.json"  # written by systemone_client.py only after the last record
        if (-not (Test-Path -LiteralPath $torch) -or -not (Test-Path -LiteralPath $done)) { "skip $($d.Name) $w"; continue }
        $existing = Get-ChildItem -LiteralPath (Join-Path $d.FullName $w) -Filter 'parity_vs_pytorch*.json' | Select-Object -First 1
        $out = if ($existing) { $existing.FullName } else { Join-Path $d.FullName "$w\parity_vs_pytorch.json" }
        python (Join-Path $root 'scripts\parity.py') --torch $torch --engine $engine --out $out > $null
        if ($LASTEXITCODE -ne 0) { throw "parity failed for $($d.Name) $w" }
        $p = Get-Content -LiteralPath $out -Raw | ConvertFrom-Json
        "{0} {1} vs {2}: agree {3}/{4}" -f $d.Name, $w, $ref, $p.by_type.all.agree_count, $p.by_type.all.n
    }
}
