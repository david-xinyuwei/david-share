<#
Download one large file from the VM over several parallel scp streams. A single scp stream to Spain Central gave
~0.3-0.9 MiB/s from this laptop; 13 parallel streams gave 10.9 MiB/s (2026-10-27). More than ~10 concurrent SSH
connections get dropped by sshd (MaxStartups), so the default is 8 streams with per-chunk retries.
The VM splits the file into chunks under /mnt/aipc/xfer/<name>/, the laptop fetches them in parallel, joins them in
order, checks SHA-256 against the VM's hash of the original file, and both sides delete the chunks.
  .\scripts\fetch_parallel.ps1 -RemotePath /mnt/aipc/gguf/0.8b/Contoso-Kev-0.8B-FT-Q8_0.gguf -LocalPath C:\Tools\models\contoso-kev\Contoso-Kev-0.8B-FT-Q8_0.gguf
#>
param(
    [Parameter(Mandatory)] [string] $RemotePath,
    [Parameter(Mandatory)] [string] $LocalPath,
    [int] $Streams = 8,
    [int] $ChunkMB = 64,
    [string] $SshTarget = $env:AIPC_SSH_TARGET,
    [int] $SshPort = $(if ($env:AIPC_SSH_PORT) { [int]$env:AIPC_SSH_PORT } else { 22 })
)
$ErrorActionPreference = 'Stop'
if (-not $SshTarget) { throw 'pass -SshTarget user@host or set $env:AIPC_SSH_TARGET' }
$name = Split-Path -Leaf $RemotePath
$remoteDir = "/mnt/aipc/xfer/$name"
# -n: without it Windows OpenSSH waits for console input after the remote command has finished
$info = ssh -n -o BatchMode=yes -o ConnectTimeout=30 -p $SshPort $SshTarget "set -e; rm -rf '$remoteDir'; mkdir -p '$remoteDir'; cd '$remoteDir'; split -b ${ChunkMB}M -d -a 4 '$RemotePath' chunk.; sha256sum '$RemotePath' | cut -c1-64; ls chunk.* | wc -l; stat -c %s '$RemotePath'"
if ($LASTEXITCODE -ne 0) { throw "remote split failed: $info" }
$remoteHash, $count, $size = $info
$count = [int]$count
$localDir = "$LocalPath.chunks"
New-Item -ItemType Directory -Force -Path $localDir | Out-Null
$sw = [Diagnostics.Stopwatch]::StartNew()
$failed = 0..($count - 1) | ForEach-Object -ThrottleLimit $Streams -Parallel {
    $n = 'chunk.{0:D4}' -f $_
    $dst = Join-Path $using:localDir $n
    $ok = $false
    for ($attempt = 1; $attempt -le 4 -and -not $ok; $attempt++) {
        scp -q -o BatchMode=yes -o ConnectTimeout=30 -P $using:SshPort "$($using:SshTarget):$($using:remoteDir)/$n" $dst 2>$null
        $ok = ($LASTEXITCODE -eq 0) -and (Test-Path -LiteralPath $dst)
        if (-not $ok) { Start-Sleep -Seconds (2 * $attempt) }
    }
    if (-not $ok) { $n }
}
if ($failed) { throw "chunks failed after retries: $($failed -join ', ')" }
$out = [IO.File]::Create("$LocalPath.part")
try {
    foreach ($i in 0..($count - 1)) {
        $in = [IO.File]::OpenRead((Join-Path $localDir ('chunk.{0:D4}' -f $i)))
        try { $in.CopyTo($out) } finally { $in.Dispose() }
    }
} finally { $out.Dispose() }
$localHash = (Get-FileHash -LiteralPath "$LocalPath.part" -Algorithm SHA256).Hash.ToLower()
if ($localHash -ne $remoteHash) { throw "SHA-256 mismatch for ${name}: local $localHash remote $remoteHash" }
Move-Item -LiteralPath "$LocalPath.part" -Destination $LocalPath -Force
Remove-Item -LiteralPath $localDir -Recurse -Force
ssh -n -o BatchMode=yes -o ConnectTimeout=30 -p $SshPort $SshTarget "rm -rf '$remoteDir'" | Out-Null
$mib = [int64]$size / 1MB
"{0}: {1:N1} MiB in {2:N0} s ({3:N1} MiB/s, {4} chunks, {5} streams), sha256 {6} OK" -f $name, $mib, $sw.Elapsed.TotalSeconds, ($mib / $sw.Elapsed.TotalSeconds), $count, $Streams, $localHash.Substring(0, 16)
