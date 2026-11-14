#Requires -Version 7.3
<#
.SYNOPSIS
  Delete everything infra/up.ps1 created: the resource group, then the soft-deleted Azure AI resource.

.DESCRIPTION
  A deleted Azure AI resource stays soft-deleted for 48 hours and keeps its name and, for model deployments, its quota.
  This script purges it after the resource group is gone, checks that nothing is left, and removes the generated
  password and SSH key from the state directory (the receipts stay).

.EXAMPLE
  ./infra/down.ps1 -ResourceGroup rg-thermal-studio
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$ResourceGroup,
  [string]$Subscription,
  [string]$StateDir,
  [switch]$Yes
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
Set-StrictMode -Version 3.0
if (-not $StateDir) { $StateDir = Join-Path (Join-Path $HOME '.thermal-3d-studio') $ResourceGroup }
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$subArgs = $(if ($Subscription) { @('--subscription', $Subscription) } else { @() })
$errFile = Join-Path $StateDir 'az-stderr.txt'
$started = Get-Date
$steps = [Collections.Generic.List[object]]::new()

function Invoke-Az([string[]]$Arguments, [switch]$Json, [switch]$AllowFail) {
  $out = & az @($Arguments + $subArgs) 2>$errFile
  if ($LASTEXITCODE -ne 0) {
    if ($AllowFail) { return $null }
    throw "az $($Arguments[0..2] -join ' ') failed (exit $LASTEXITCODE): $((Get-Content -Raw -LiteralPath $errFile) -replace '\s+', ' ')"
  }
  $text = ($out -join "`n").Trim()
  if ($Json) { return $(if ($text) { $text | ConvertFrom-Json -Depth 32 } else { $null }) }
  return $text
}
function Done([string]$Name, [string]$Detail) {
  $steps.Add([ordered]@{ name = $Name; status = 'PASS'; detail = $Detail; at = (Get-Date).ToString('o') })
  Write-Host ("[{0:HH:mm:ss}] {1}: {2}" -f (Get-Date), $Name, $Detail)
}

$status = 'FAIL'
try {
  $exists = (Invoke-Az @('group', 'exists', '-n', $ResourceGroup)) -eq 'true'
  # The AI resources to purge: from the live group, else from the outputs of the last up.ps1 run.
  $ai = @()
  if ($exists) {
    $ai = @(Invoke-Az @('cognitiveservices', 'account', 'list', '-g', $ResourceGroup, '-o', 'json') -Json | Where-Object { $_ } |
            ForEach-Object { [pscustomobject]@{ name = $_.name; location = $_.location } })
  } elseif (Test-Path -LiteralPath (Join-Path $StateDir 'outputs.json')) {
    $o = Get-Content -Raw -LiteralPath (Join-Path $StateDir 'outputs.json') | ConvertFrom-Json
    $ai = @([pscustomobject]@{ name = $o.aiName; location = $o.location })
  }
  if ($exists) {
    if (-not $Yes) {
      $answer = Read-Host "Delete resource group '$ResourceGroup' and everything in it? Type its name to confirm"
      if ($answer -ne $ResourceGroup) { throw 'Not confirmed; nothing was deleted.' }
    }
    Write-Host "deleting resource group $ResourceGroup (several minutes)"
    Invoke-Az @('group', 'delete', '-n', $ResourceGroup, '--yes') | Out-Null
    Done 'resource group deleted' $ResourceGroup
  } else {
    Done 'resource group' "$ResourceGroup does not exist"
  }

  foreach ($a in $ai) {
    $deleted = @(Invoke-Az @('cognitiveservices', 'account', 'list-deleted', '-o', 'json') -Json | Where-Object { $_ -and $_.name -eq $a.name })
    if ($deleted.Count) {
      Invoke-Az @('cognitiveservices', 'account', 'purge', '-l', $a.location, '-g', $ResourceGroup, '-n', $a.name) | Out-Null
      Done 'AI resource purged' "$($a.name) ($($a.location))"
    } else {
      Done 'AI resource' "$($a.name) is not soft-deleted"
    }
  }

  $leftGroup = (Invoke-Az @('group', 'exists', '-n', $ResourceGroup)) -eq 'true'
  $aiNames = @($ai | ForEach-Object { $_.name })
  $leftAi = @(Invoke-Az @('cognitiveservices', 'account', 'list-deleted', '-o', 'json') -Json | Where-Object { $_ -and $_.name -in $aiNames } |
              ForEach-Object { $_.name })
  if ($leftGroup -or $leftAi.Count) { throw "still present: group=$leftGroup, soft-deleted AI resources=$($leftAi -join ',')" }
  Done 'nothing left' "group $ResourceGroup gone, no soft-deleted AI resource of it"

  foreach ($f in 'portal-password.txt', 'id_ed25519', 'id_ed25519.pub') {
    Remove-Item -LiteralPath (Join-Path $StateDir $f) -Force -ErrorAction SilentlyContinue
  }
  $status = 'PASS'
} finally {
  $receipt = [ordered]@{ script = 'infra/down.ps1'; resourceGroup = $ResourceGroup; startedAt = $started.ToString('o')
                         finishedAt = (Get-Date).ToString('o'); minutes = [Math]::Round(((Get-Date) - $started).TotalMinutes, 1)
                         status = $status; steps = $steps }
  $file = Join-Path $StateDir ('down-{0:yyyyMMdd-HHmmss}.json' -f $started)
  [IO.File]::WriteAllText($file, ($receipt | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
  Write-Host "receipt: $file ($status)"
}
