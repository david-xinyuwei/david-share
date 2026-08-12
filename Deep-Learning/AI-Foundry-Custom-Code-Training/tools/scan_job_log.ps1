# Filters a multi-MB distributed training log down to the lines that matter.
#
# Ray and NCCL can emit hundreds of identical transport warnings after workers die, which
# buries the single Python exception that actually caused the failure. -Dedupe collapses
# consecutive repeats (digits normalised, so per-rank and per-pid variants count as one)
# and -Exclude drops known noise families.
#
# Reads UTF-16LE because PowerShell 5.1's *> redirection writes UTF-16 and ordinary grep
# tooling silently reports zero matches on those files.
#
#   .\scan_job_log.ps1 -LogPath job.log `
#       -Pattern 'Traceback|Error|Training Progress' `
#       -Exclude 'InternalKV|dashboard|NoSuchProcess' -Dedupe
param(
    [Parameter(Mandatory = $true)][string]$LogPath,
    [Parameter(Mandatory = $true)][string]$Pattern,
    [string]$Exclude,
    [int]$Max = 60,
    [ValidateSet('head', 'tail')][string]$Mode = 'tail',
    [ValidateSet('Unicode', 'UTF8')][string]$Encoding = 'Unicode',
    [switch]$Dedupe
)

$ErrorActionPreference = 'Stop'

$textEncoding = if ($Encoding -eq 'UTF8') { [Text.Encoding]::UTF8 } else { [Text.Encoding]::Unicode }
$lines = [IO.File]::ReadAllText($LogPath, $textEncoding) -split "`r?`n"
Write-Output "TOTAL_LINES=$($lines.Count)"

$hits = New-Object System.Collections.ArrayList
$previous = ''
for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    if ($line -notmatch $Pattern) { continue }
    if ($Exclude -and $line -match $Exclude) { continue }
    if ($Dedupe) {
        $normalized = $line -replace '\d+', ''
        if ($normalized -eq $previous) { continue }
        $previous = $normalized
    }
    [void]$hits.Add("[$i] " + $line.Substring(0, [Math]::Min(200, $line.Length)))
}

Write-Output "HITS=$($hits.Count)"
if ($hits.Count -eq 0) { return }

$take = [Math]::Min($Max, $hits.Count)
if ($Mode -eq 'head') { $hits[0..($take - 1)] } else { $hits[($hits.Count - $take)..($hits.Count - 1)] }
