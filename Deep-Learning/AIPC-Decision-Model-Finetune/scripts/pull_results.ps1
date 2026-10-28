<#
Pack the VM results (scripts/remote_pack_results.sh), copy the archive into 验证结果\微调评测_<UTC ts>\, verify SHA-256,
extract it there and run summarize_results.py on the extracted runs.
  .\scripts\pull_results.ps1                       # final evidence, inside the project
  .\scripts\pull_results.ps1 -OutRoot $env:TEMP    # interim look while jobs are still running (not evidence)
#>
param(
    [string] $SshTarget = $env:AIPC_SSH_TARGET,
    [int] $SshPort = $(if ($env:AIPC_SSH_PORT) { [int]$env:AIPC_SSH_PORT } else { 22 }),
    [string] $RemoteMeta = $(if ($env:AIPC_REMOTE_META) { $env:AIPC_REMOTE_META } else { '~/remote-workspaces/aipc-decision' }),
    [string] $OutRoot = ''
)
$ErrorActionPreference = 'Stop'
if (-not $SshTarget) { throw 'pass -SshTarget user@host or set $env:AIPC_SSH_TARGET' }
$root = Split-Path -Parent $PSScriptRoot
$base = if ($OutRoot) { $OutRoot } else { Join-Path $root '验证结果' }
$pack = ssh -n -o BatchMode=yes -o ConnectTimeout=30 -p $SshPort $SshTarget "bash $RemoteMeta/scripts/remote_pack_results.sh"
if ($LASTEXITCODE -ne 0) { throw "remote pack failed: $pack" }
$pack | Select-Object -Last 3
$hashLine = $pack | Where-Object { $_ -match '^[0-9a-f]{64}\s+/mnt/aipc/results-.*\.tgz$' } | Select-Object -Last 1
if (-not $hashLine) { throw 'no archive hash in the pack output' }
$remoteHash, $remotePath = $hashLine -split '\s+', 2
$name = Split-Path -Leaf $remotePath
$ts = $name -replace '^results-(\d{8}-\d{6})\.tgz$', '$1'
$dest = Join-Path $base "微调评测_$ts"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$local = Join-Path $dest $name
& (Join-Path $PSScriptRoot 'fetch_parallel.ps1') -RemotePath $remotePath -LocalPath $local -ChunkMB 16 -SshTarget $SshTarget -SshPort $SshPort
$localHash = (Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash.ToLower()
"$localHash  $name" | Set-Content -LiteralPath (Join-Path $dest 'archive.sha256') -Encoding ascii
if ($localHash -ne $remoteHash) { throw "SHA-256 mismatch: local $localHash remote $remoteHash" }
"archive {0:N1} MiB, sha256 OK {1}" -f ((Get-Item -LiteralPath $local).Length / 1MB), $localHash.Substring(0, 16)
tar -xzf $local -C $dest
if ($LASTEXITCODE -ne 0) { throw 'extract failed' }
python (Join-Path $root 'scripts\summarize_results.py') --runs (Join-Path $dest 'runs') --data (Join-Path $root 'data\contoso\final') --out (Join-Path $dest 'summary') > $null
if ($LASTEXITCODE -ne 0) { throw 'summarize failed' }
Write-Output "__PULL_RESULTS_DONE__ $dest"
