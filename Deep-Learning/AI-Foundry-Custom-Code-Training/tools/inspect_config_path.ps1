# Reconstructs the real dotted path of a key in verl's pprint'd runtime config dump.
#
# verl's error messages sometimes name a shorter path than the one the config actually
# uses, and Hydra will happily create the wrong key when you pass it with a leading '+'.
# Reading the path out of the dump removes the guesswork.
#
# Reads UTF-16LE because PowerShell 5.1's *> redirection writes UTF-16 and ordinary grep
# tooling silently reports zero matches on those files.
#
#   .\inspect_config_path.ps1 -LogPath job.log -Pattern 'update_weights_bucket_megabytes'
#   .\inspect_config_path.ps1 -LogPath job.log -LineNumbers '1055,1161'
param(
    [Parameter(Mandatory = $true)][string]$LogPath,
    # Comma-separated; powershell.exe -File hands every argument over as one string.
    [string]$LineNumbers,
    [string]$Pattern,
    [int]$From = 0,
    [int]$To = 0,
    [ValidateSet('Unicode', 'UTF8')][string]$Encoding = 'Unicode'
)

$ErrorActionPreference = 'Stop'

$textEncoding = if ($Encoding -eq 'UTF8') { [Text.Encoding]::UTF8 } else { [Text.Encoding]::Unicode }
$lines = [IO.File]::ReadAllText($LogPath, $textEncoding) -split "`r?`n"

function Get-Indent([int]$n) {
    $raw = $lines[$n]
    return $raw.Length - ($raw -replace '^\s+', '').Length
}

function Get-Text([int]$n) {
    $trimmed = $lines[$n] -replace '^\s+', ''
    return $trimmed.Substring(0, [Math]::Min(90, $trimmed.Length))
}

$openKey = "^\s*'([^']+)':\s*\{"

if ($Pattern) {
    if ($To -le 0) { $To = $lines.Count - 1 }
    $targets = @()
    for ($i = $From; $i -le $To; $i++) {
        if ($lines[$i] -match $Pattern) { $targets += $i }
    }
    Write-Output "MATCHES=$($targets.Count)"
}
elseif ($LineNumbers) {
    $targets = $LineNumbers.Split(',') | ForEach-Object { [int]$_.Trim() }
}
else {
    throw 'Supply either -Pattern or -LineNumbers.'
}

foreach ($target in $targets) {
    Write-Output "===== line $target ====="
    $currentIndent = Get-Indent $target
    $names = New-Object System.Collections.ArrayList

    # Walk backwards; each enclosing "'key': {" at a smaller indent is one level up.
    for ($i = $target - 1; $i -ge 0 -and $currentIndent -gt 0; $i--) {
        $indent = Get-Indent $i
        if ($indent -lt $currentIndent -and $lines[$i] -match $openKey) {
            [void]$names.Add($Matches[1])
            $currentIndent = $indent
        }
    }

    $names.Reverse()
    $leaf = ($lines[$target] -replace '^\s+', '') -replace "^'([^']+)'.*", '$1'
    Write-Output ("  PATH -> " + (($names + @($leaf)) -join '.'))
    Write-Output ("  VALUE  " + (Get-Text $target))
}
