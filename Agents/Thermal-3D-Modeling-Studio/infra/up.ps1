#Requires -Version 7.3
<#
.SYNOPSIS
  Create every Azure resource of the Thermal 3D Modeling Studio and install the studio on a new Ubuntu VM.

.DESCRIPTION
  1. Preflight: Azure CLI and Bicep, the signed-in account, free model quota in the region.
  2. Resource group.
  3. infra/main.bicep: an Azure AI resource with the gpt-6-astra and gpt-image deployments (Microsoft Entra sign-in only),
     a user-assigned managed identity with Cognitive Services OpenAI User on that resource, a network that lets in
     HTTPS, a public IP with a DNS name, and an Ubuntu 24.04 VM that carries the identity.
  4. infra/vm-install.sh on the VM through Run Command, so no SSH is needed: it fetches the studio from -RepoUrl at
     -RepoRef, runs studio/deploy/bootstrap_vm.sh and studio/deploy/remote_install.sh, writes the .env, builds the 15
     reference STEP solids and serves the studio behind nginx with a Let's Encrypt certificate.
  5. HTTPS health check from this machine.

  Local state goes to -StateDir (default ~/.thermal-3d-studio/<resource group>), never into the repository:
  outputs.json, a receipt of each run, the generated SSH key and the sign-in password.
  Run it again with the same resource group to update the VM to -RepoRef; the password and the solids are kept.

.EXAMPLE
  ./infra/up.ps1 -ResourceGroup rg-thermal-studio -Location eastus2
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidatePattern('^[-\w.()]{1,90}$')][string]$ResourceGroup,
  [string]$Location = 'eastus2',
  [string]$Subscription,
  [ValidateSet('Auto', 'GlobalStandard', 'DataZoneStandard')][string]$Gpt6Sku = 'Auto',
  [ValidateRange(1, 10000)][int]$Gpt6Capacity = 100,
  [switch]$SkipImageModel,
  [string]$ImageModel = 'gpt-image-2.5-sunburst',
  [string]$ImageModelVersion = '2026-09-08',
  [ValidateRange(1, 100)][int]$ImageCapacity = 2,
  [string]$VmSize,   # empty: the first 4-vCPU size from the list below that the region offers to your subscription
  [ValidatePattern('^[a-z][a-z0-9]{2,11}$')][string]$NamePrefix = 'thermal',
  [string]$SshPublicKeyPath,
  [string]$AllowSshFrom = '',
  [switch]$GrantDeployerAccess,
  [string]$PortalUsername = 'studio',
  [SecureString]$PortalPassword,
  [string]$RepoUrl = 'https://github.com/david-xinyuwei/david-share.git',
  [string]$RepoRef = 'master',
  [string]$RepoSubdir = 'Agents/Thermal-3D-Modeling-Studio',
  [switch]$SkipReferenceSolids,
  [string]$StateDir
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
Set-StrictMode -Version 3.0

if (-not $StateDir) { $StateDir = Join-Path (Join-Path $HOME '.thermal-3d-studio') $ResourceGroup }
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$utf8 = [Text.UTF8Encoding]::new($false)
$errFile = Join-Path $StateDir 'az-stderr.txt'
$started = Get-Date
$steps = [Collections.Generic.List[object]]::new()
$receipt = [ordered]@{ script = 'infra/up.ps1'; resourceGroup = $ResourceGroup; location = $Location; repoUrl = $RepoUrl; repoRef = $RepoRef
                       startedAt = $started.ToString('o'); steps = $steps }
$subArgs = @()

function Invoke-Az([string[]]$Arguments, [switch]$Json, [switch]$AllowFail, [switch]$NoSubscription) {
  $all = $Arguments + $(if ($NoSubscription) { @() } else { $subArgs })
  $out = & az @all 2>$errFile
  $code = $LASTEXITCODE
  if ($code -ne 0) {
    if ($AllowFail) { return $null }
    $err = (Get-Content -Raw -LiteralPath $errFile -ErrorAction SilentlyContinue) -replace '\s+', ' '
    throw "az $($Arguments[0..([Math]::Min(2, $Arguments.Count - 1))] -join ' ') failed (exit $code): $err"
  }
  $text = ($out -join "`n").Trim()
  if ($Json) { return $(if ($text) { $text | ConvertFrom-Json -Depth 64 } else { $null }) }
  return $text
}

function Step([string]$Name, [scriptblock]$Body) {
  $t = Get-Date
  Write-Host ("[{0:HH:mm:ss}] {1}" -f $t, $Name) -ForegroundColor Cyan
  try {
    $result = & $Body
    $steps.Add([ordered]@{ name = $Name; status = 'PASS'; seconds = [Math]::Round(((Get-Date) - $t).TotalSeconds, 1) })
    return $result
  } catch {
    $steps.Add([ordered]@{ name = $Name; status = 'FAIL'; seconds = [Math]::Round(((Get-Date) - $t).TotalSeconds, 1); error = "$($_.Exception.Message)" })
    throw
  }
}

function Get-FreeQuota($Usage, [string]$Name) {
  $u = @($Usage | Where-Object { $_.name.value -eq $Name }) | Select-Object -First 1
  if (-not $u) { return 0 }
  return [double]$u.limit - [double]$u.currentValue
}

function New-Password {
  $alphabet = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  -join (1..20 | ForEach-Object { $alphabet[[Security.Cryptography.RandomNumberGenerator]::GetInt32($alphabet.Length)] })
}

function Save-Secret([string]$Path, [string]$Value) {
  [IO.File]::WriteAllText($Path, $Value, $utf8)
  if (-not $IsWindows) { & chmod 600 $Path }
}

$status = 'FAIL'
try {
  # 1 ------------------------------------------------------------------------------------------------ preflight
  $plan = Step '1/5 preflight: Azure CLI, sign-in, model quota' {
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) { throw 'Azure CLI not found: https://learn.microsoft.com/cli/azure/install-azure-cli' }
    $receipt.azureCli = (Invoke-Az @('version', '-o', 'json') -Json -NoSubscription).'azure-cli'
    & az bicep version *> $null
    if ($LASTEXITCODE -ne 0) { Invoke-Az @('bicep', 'install') -NoSubscription | Out-Null }
    $script:subArgs = $(if ($Subscription) { @('--subscription', $Subscription) } else { @() })
    $account = Invoke-Az @('account', 'show', '-o', 'json') -Json -AllowFail
    if (-not $account) { throw 'Not signed in to Azure: run az login (and az account set --subscription <id>) first.' }
    $receipt.subscriptionId = $account.id
    Write-Host "   subscription $($account.name) ($($account.id))"

    # A missing resource group gives $null here, which a pipeline still passes on as one item: hence the $_ -and guards.
    $existingAi = @(Invoke-Az @('cognitiveservices', 'account', 'list', '-g', $ResourceGroup, '-o', 'json') -Json -AllowFail |
                    Where-Object { $_ -and $_.kind -eq 'AIServices' }) | Select-Object -First 1
    $existingDeployments = @()
    if ($existingAi) {
      $existingDeployments = @(Invoke-Az @('cognitiveservices', 'account', 'deployment', 'list', '-g', $ResourceGroup, '-n', $existingAi.name, '-o', 'json') -Json)
    }
    $gpt6 = @($existingDeployments | Where-Object { $_ -and $_.name -eq 'gpt-6-astra' }) | Select-Object -First 1
    $wanted = @(@{ name = 'gpt-6-astra'; version = '2026-09-03' })
    if (-not $SkipImageModel) { $wanted += @{ name = $ImageModel; version = $ImageModelVersion } }
    $catalog = @(Invoke-Az @('cognitiveservices', 'model', 'list', '-l', $Location, '-o', 'json') -Json | Where-Object { $_ -and $_.kind -eq 'AIServices' })
    foreach ($w in $wanted) {
      if (-not ($catalog | Where-Object { $_.model.name -eq $w.name -and $_.model.version -eq $w.version })) {
        throw "Model $($w.name) version $($w.version) is not offered in $Location. Pick another -Location$(if ($w.name -ne 'gpt-6-astra') { ', -ImageModel/-ImageModelVersion or -SkipImageModel' })."
      }
    }
    Write-Host "   models offered in ${Location}: $(($wanted | ForEach-Object { "$($_.name) $($_.version)" }) -join ', ')"
    $usage = $null
    if ($gpt6) {
      $sku = $gpt6.sku.name
      Write-Host "   gpt-6-astra already deployed ($sku, $($gpt6.sku.capacity)K tokens/min): kept"
    } else {
      $usage = Invoke-Az @('cognitiveservices', 'usage', 'list', '-l', $Location, '-o', 'json') -Json
      $candidates = if ($Gpt6Sku -eq 'Auto') { @('GlobalStandard', 'DataZoneStandard') } else { @($Gpt6Sku) }
      $sku = $null
      foreach ($c in $candidates) {
        $free = Get-FreeQuota $usage "OpenAI.$c.gpt-6-astra"
        Write-Host "   gpt-6-astra $c in ${Location}: $free K tokens/min free, $Gpt6Capacity needed"
        if ($free -ge $Gpt6Capacity) { $sku = $c; break }
      }
      if (-not $sku) { throw "No free gpt-6-astra quota for $Gpt6Capacity K tokens/min in $Location ($($candidates -join ', ')). Lower -Gpt6Capacity, pick another -Location or request quota." }
    }
    if (-not $SkipImageModel -and -not ($existingDeployments | Where-Object { $_ -and $_.name -eq $ImageModel })) {
      if (-not $usage) { $usage = Invoke-Az @('cognitiveservices', 'usage', 'list', '-l', $Location, '-o', 'json') -Json }
      $free = Get-FreeQuota $usage "OpenAI.GlobalStandard.$ImageModel"
      Write-Host "   $ImageModel GlobalStandard in ${Location}: $free free, $ImageCapacity needed"
      if ($free -lt $ImageCapacity) { throw "No free $ImageModel quota in $Location. Use -SkipImageModel (Tracks C and D off) or a lower -ImageCapacity." }
    }
    $vm = @(Invoke-Az @('vm', 'list', '-g', $ResourceGroup, '-o', 'json') -Json -AllowFail | Where-Object { $_ }) | Select-Object -First 1
    if ($vm) {
      $size = $vm.hardwareProfile.vmSize   # an existing VM keeps its size and disk controller
      $controller = $(if ($vm.storageProfile.PSObject.Properties['diskControllerType'] -and $vm.storageProfile.diskControllerType) {
                        $vm.storageProfile.diskControllerType } else { 'SCSI' })
      Write-Host "   VM $($vm.name) already exists ($size): kept"
    } else {
      Write-Host "   VM sizes offered to this subscription in $Location (about a minute)"
      $skus = @(Invoke-Az @('vm', 'list-skus', '-l', $Location, '--resource-type', 'virtualMachines', '-o', 'json') -Json | Where-Object { $_ })
      $candidates = $(if ($VmSize) { @($VmSize) } else {
        @('Standard_D4as_v5', 'Standard_D4s_v5', 'Standard_D4ads_v5', 'Standard_D4ds_v5', 'Standard_D4as_v6', 'Standard_D4ads_v6',
          'Standard_D4s_v6', 'Standard_D4as_v4', 'Standard_D4s_v4') })
      $size, $controller = $null, 'SCSI'
      foreach ($c in $candidates) {
        # list-skus leaves out sizes the subscription cannot use in the region; a zone restriction does not matter (no zone is set)
        $s = @($skus | Where-Object { $_.name -eq $c }) | Select-Object -First 1
        if (-not $s -or @($s.restrictions | Where-Object { $_ -and $_.type -eq 'Location' }).Count) { continue }
        $types = @($s.capabilities | Where-Object { $_ -and $_.name -eq 'DiskControllerTypes' } | ForEach-Object { $_.value })
        $controller = $(if ($types -and $types[0] -notmatch 'SCSI') { 'NVMe' } else { 'SCSI' })   # the v6 sizes take NVMe only
        $size = $c
        break
      }
      if (-not $size) { throw "None of these VM sizes is offered to this subscription in ${Location}: $($candidates -join ', '). Pass -VmSize with a 4-vCPU x64 size from 'az vm list-skus -l $Location -o table', or pick another -Location." }
      Write-Host "   VM size $size, disk controller $controller"
    }
    [pscustomobject]@{ Sku = $sku; Vm = $vm; VmSize = $size; DiskController = $controller }
  }
  $receipt.gpt6Sku = $plan.Sku
  $receipt.vmSize = $plan.VmSize

  # 2 ------------------------------------------------------------------------------------------------ resource group
  Step "2/5 resource group $ResourceGroup" {
    if ((Invoke-Az @('group', 'exists', '-n', $ResourceGroup)) -eq 'true') {
      Write-Host "   exists in $((Invoke-Az @('group', 'show', '-n', $ResourceGroup, '-o', 'json') -Json).location): kept; the resources go to $Location"
    } else {
      Invoke-Az @('group', 'create', '-n', $ResourceGroup, '-l', $Location, '--tags', 'app=thermal-3d-studio', '-o', 'none') | Out-Null
      Write-Host "   created in $Location"
    }
  }

  # 3 ------------------------------------------------------------------------------------------------ Azure resources
  $out = Step '3/5 Azure resources (infra/main.bicep): AI resource and models, identity and role, network, VM' {
    if ($SshPublicKeyPath) {
      $publicKey = (Get-Content -Raw -LiteralPath $SshPublicKeyPath).Trim()
    } elseif ($plan.Vm) {
      $publicKey = $plan.Vm.osProfile.linuxConfiguration.ssh.publicKeys[0].keyData.Trim()   # the key of a VM cannot change
    } else {
      $keyFile = Join-Path $StateDir 'id_ed25519'
      if (-not (Test-Path -LiteralPath "$keyFile.pub")) {
        if (-not (Get-Command ssh-keygen -ErrorAction SilentlyContinue)) { throw 'ssh-keygen not found: install the OpenSSH client or pass -SshPublicKeyPath' }
        & ssh-keygen -q -t ed25519 -N '' -C 'thermal-3d-studio' -f $keyFile
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath "$keyFile.pub")) { throw 'ssh-keygen failed' }
      }
      $publicKey = (Get-Content -Raw -LiteralPath "$keyFile.pub").Trim()
    }
    $principalId, $principalType = '', 'User'
    if ($GrantDeployerAccess) {
      $token = Invoke-Az @('account', 'get-access-token', '--resource', 'https://management.azure.com/', '--query', 'accessToken', '-o', 'tsv')
      $part = $token.Split('.')[1].Replace('-', '+').Replace('_', '/')
      $claims = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($part + ('=' * ((4 - $part.Length % 4) % 4)))) | ConvertFrom-Json
      $principalId = $claims.oid
      if ($claims.PSObject.Properties['idtyp'] -and $claims.idtyp -eq 'app') { $principalType = 'ServicePrincipal' }
      Write-Host "   model access also for the signed-in $principalType $principalId"
    }
    $parameters = [ordered]@{
      '$schema'      = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'
      contentVersion = '1.0.0.0'
      parameters     = [ordered]@{
        location              = @{ value = $Location }
        namePrefix            = @{ value = $NamePrefix }
        gpt6Sku               = @{ value = $plan.Sku }
        gpt6Capacity          = @{ value = $Gpt6Capacity }
        deployImageModel      = @{ value = -not $SkipImageModel.IsPresent }
        imageModelName        = @{ value = $ImageModel }
        imageModelVersion     = @{ value = $ImageModelVersion }
        imageCapacity         = @{ value = $ImageCapacity }
        vmSize                = @{ value = $plan.VmSize }
        diskControllerType    = @{ value = $plan.DiskController }
        adminPublicKey        = @{ value = $publicKey }
        allowSshFrom          = @{ value = $AllowSshFrom }
        deployerPrincipalId   = @{ value = $principalId }
        deployerPrincipalType = @{ value = $principalType }
      }
    }
    $paramFile = Join-Path $StateDir 'parameters.json'
    [IO.File]::WriteAllText($paramFile, ($parameters | ConvertTo-Json -Depth 8), $utf8)
    $o = Invoke-Az @('deployment', 'group', 'create', '-g', $ResourceGroup, '-n', 'thermal-3d-studio', '-f', (Join-Path $PSScriptRoot 'main.bicep'),
                     '-p', "@$paramFile", '--query', 'properties.outputs', '-o', 'json') -Json
    $values = [ordered]@{}
    foreach ($p in $o.PSObject.Properties) { $values[$p.Name] = $p.Value.value }
    Write-Host "   $($values.vmName) at $($values.fqdn); models on $($values.aiEndpoint): $($values.gpt6Deployment) ($($values.gpt6Sku))$(if ($values.imageDeployment) { ', ' + $values.imageDeployment })"
    $values
  }

  # 4 ------------------------------------------------------------------------------------------------ install on the VM
  $install = Step '4/5 install on the VM through Run Command (infra/vm-install.sh): the longest step, silent until it ends' {
    $pwFile = Join-Path $StateDir 'portal-password.txt'
    if ($PortalPassword) {
      $password = ConvertFrom-SecureString -SecureString $PortalPassword -AsPlainText
      if ($password -notmatch '^[A-Za-z0-9._~@%+=,-]{12,128}$') { throw 'The password needs 12-128 characters from A-Z a-z 0-9 . _ ~ @ % + = , -' }
      Save-Secret $pwFile $password
    } elseif (Test-Path -LiteralPath $pwFile) {
      $password = (Get-Content -Raw -LiteralPath $pwFile).Trim()
    } elseif ($plan.Vm) {
      $password = ''   # keep the password that is already on the VM
      Write-Host '   no local password file: the password on the VM is kept'
    } else {
      $password = New-Password
      Save-Secret $pwFile $password
    }
    $config = [ordered]@{
      fqdn = $out.fqdn; aiEndpoint = $out.aiEndpoint; gpt6Deployment = $out.gpt6Deployment; imageDeployment = $out.imageDeployment
      identityClientId = $out.identityClientId; portalUsername = $PortalUsername; portalPassword = $password
      repoUrl = $RepoUrl; repoRef = $RepoRef; repoSubdir = $RepoSubdir; buildSolids = -not $SkipReferenceSolids.IsPresent
    }
    $b64 = [Convert]::ToBase64String($utf8.GetBytes(($config | ConvertTo-Json -Compress)))
    $installer = (Get-Content -Raw -LiteralPath (Join-Path $PSScriptRoot 'vm-install.sh')).Replace("`r`n", "`n")
    $wrapper = "#!/bin/bash`nexport THERMAL_CONFIG_B64='$b64'`ncat > /tmp/thermal-vm-install.sh <<'THERMAL_INSTALLER_EOF'`n$installer`nTHERMAL_INSTALLER_EOF`nexec bash /tmp/thermal-vm-install.sh`n"
    $scriptFile = Join-Path $StateDir 'run-command.sh'   # holds the password: deleted right after the call
    [IO.File]::WriteAllText($scriptFile, $wrapper, $utf8)
    try {
      $r = Invoke-Az @('vm', 'run-command', 'invoke', '-g', $ResourceGroup, '-n', $out.vmName, '--command-id', 'RunShellScript',
                       '--scripts', "@$scriptFile", '-o', 'json') -Json
    } finally {
      Remove-Item -LiteralPath $scriptFile -Force -ErrorAction SilentlyContinue
    }
    $message = [string]$r.value[0].message
    $stdout = ($message -split '\[stderr\]')[0] -replace '^[\s\S]*?\[stdout\]\s*', ''
    $stdout.Trim().Split("`n") | ForEach-Object { Write-Host "   $_" }
    $line = ($stdout -split "`n" | Where-Object { $_ -match 'THERMAL_INSTALL=' } | Select-Object -Last 1)
    if (-not $line -or $line -notmatch 'THERMAL_INSTALL=PASS') { throw "the install on the VM did not finish: $line (log on the VM: /var/log/thermal-install.log)" }
    $fields = @{}
    foreach ($m in [regex]::Matches($line, '(\w+)=(\S+)')) { $fields[$m.Groups[1].Value] = $m.Groups[2].Value }
    $fields
  }
  $receipt.installedCommit = $install['commit']
  $receipt.referenceSolids = @{ zh = $install['solids_zh']; en = $install['solids_en'] }
  $receipt.noEdgeBreak = $install['no_edge_break']   # solids built without the edge break after OCCT crashed in it

  # 5 ------------------------------------------------------------------------------------------------ check from here
  Step "5/5 HTTPS check from this machine: https://$($out.fqdn)/healthz" {
    $health = $null
    for ($i = 1; $i -le 24 -and -not $health; $i++) {
      try { $health = Invoke-RestMethod -Uri "https://$($out.fqdn)/healthz" -TimeoutSec 15 } catch { Start-Sleep -Seconds 5 }
    }
    if (-not $health -or -not $health.ok) { throw "https://$($out.fqdn)/healthz did not answer ok" }
    Write-Host "   $($health | ConvertTo-Json -Compress)"
  }

  $outputs = [ordered]@{}
  foreach ($k in $out.Keys) { $outputs[$k] = $out[$k] }
  $outputs.url = "https://$($out.fqdn)/"
  $outputs.resourceGroup = $ResourceGroup
  $outputs.subscriptionId = $receipt.subscriptionId
  $outputs.portalUsername = $PortalUsername
  $outputs.passwordFile = Join-Path $StateDir 'portal-password.txt'
  $outputs.installedCommit = $install['commit']
  $outputs.repoUrl = $RepoUrl
  $outputs.repoRef = $RepoRef
  [IO.File]::WriteAllText((Join-Path $StateDir 'outputs.json'), ($outputs | ConvertTo-Json -Depth 5), $utf8)
  $status = 'PASS'

  Write-Host ''
  Write-Host 'Thermal 3D Modeling Studio is running' -ForegroundColor Green
  Write-Host "  Open      $($outputs.url)"
  Write-Host "  Sign in   user $PortalUsername; password in $($outputs.passwordFile)"
  Write-Host "  Check     ./infra/verify.ps1 -ResourceGroup $ResourceGroup"
  Write-Host "  Remove    ./infra/down.ps1 -ResourceGroup $ResourceGroup"
  Write-Host '  The VM bills while it runs; the model deployments bill per token.'
} finally {
  $receipt.status = $status
  $receipt.finishedAt = (Get-Date).ToString('o')
  $receipt.minutes = [Math]::Round(((Get-Date) - $started).TotalMinutes, 1)
  $receiptFile = Join-Path $StateDir ('up-{0:yyyyMMdd-HHmmss}.json' -f $started)
  [IO.File]::WriteAllText($receiptFile, ($receipt | ConvertTo-Json -Depth 6), $utf8)
  Write-Host "receipt: $receiptFile ($status)"
}
