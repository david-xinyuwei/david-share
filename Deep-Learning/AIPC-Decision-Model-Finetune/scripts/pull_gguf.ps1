<#
Pull the quantized fine-tuned GGUFs of one size from the VM to a local, non-synced model folder over parallel streams
(scripts/fetch_parallel.ps1) and verify SHA-256 against the gguf.sha256 written on the VM.
BF16 stays on the VM (only used as the quantization source).
  .\scripts\pull_gguf.ps1 -Size 0.8b [-Only Q8_0]
#>
param(
    [Parameter(Mandatory)] [ValidateSet('0.8b', '4b', '0.8b-cf', '4b-cf')] [string] $Size,
    [string[]] $Only = @('Q8_0', 'Q4_K_M'),
    [string] $Dest = 'C:\Tools\models\contoso-kev',
    [string] $SshTarget = $env:AIPC_SSH_TARGET,
    [int] $SshPort = $(if ($env:AIPC_SSH_PORT) { [int]$env:AIPC_SSH_PORT } else { 22 })
)
$ErrorActionPreference = 'Stop'
if (-not $SshTarget) { throw 'pass -SshTarget user@host or set $env:AIPC_SSH_TARGET' }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$remote = "/mnt/aipc/gguf/$Size"
$lines = ssh -n -o BatchMode=yes -o ConnectTimeout=30 -p $SshPort $SshTarget "cat $remote/gguf.sha256"
if ($LASTEXITCODE -ne 0 -or -not $lines) { throw "no gguf.sha256 for $Size on the VM yet" }
$bad = 0
foreach ($line in $lines) {
    $hash, $name = $line -split '\s+', 2
    $name = $name.TrimStart('*') -replace '^\./', ''
    if (-not ($Only | Where-Object { $name -like "*-$_.gguf" })) { continue }
    $local = Join-Path $Dest $name
    if (-not (Test-Path -LiteralPath $local) -or (Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash.ToLower() -ne $hash) {
        & (Join-Path $PSScriptRoot 'fetch_parallel.ps1') -RemotePath "$remote/$name" -LocalPath $local -SshTarget $SshTarget -SshPort $SshPort
    }
    $ok = (Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash.ToLower() -eq $hash
    if (-not $ok) { $bad++ }
    "{0}  sha256 {1}  {2}" -f $name, $hash.Substring(0, 16), $(if ($ok) { 'OK' } else { 'MISMATCH' })
}
if ($bad) { throw "$bad GGUF file(s) failed the SHA-256 check" }
Write-Output "__PULL_GGUF_DONE__ $Size"
