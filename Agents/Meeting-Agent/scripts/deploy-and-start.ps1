[CmdletBinding()]
param(
    [string]$EnvironmentName = "meeting-agent-dev",
    [string]$Location = "eastus2",
    [string]$ModelDeploymentName = "gpt-5.4",
    [string]$AzureConfigDir
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if ($env:OS -ne "Windows_NT") {
    throw "deploy-and-start.ps1 must run in Windows PowerShell."
}
if (-not $AzureConfigDir) { $AzureConfigDir = $env:AZURE_CONFIG_DIR }
if (-not $AzureConfigDir) {
    $AzureConfigDir = [Environment]::GetEnvironmentVariable(
        "MEETING_AGENT_AZURE_CONFIG_DIR",
        "User"
    )
}
if (-not $AzureConfigDir) {
    throw "AzureConfigDir is required. Pass -AzureConfigDir or set MEETING_AGENT_AZURE_CONFIG_DIR."
}
$AzureConfigDir = [Environment]::ExpandEnvironmentVariables($AzureConfigDir)
if (-not (Test-Path -LiteralPath $AzureConfigDir -PathType Container)) {
    throw "AzureConfigDir does not exist: $AzureConfigDir"
}
$env:AZURE_CONFIG_DIR = (Resolve-Path -LiteralPath $AzureConfigDir).Path

foreach ($commandName in @("node.exe", "npm.cmd", "az.cmd", "azd.exe", "olk.exe")) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required Windows command is unavailable: $commandName"
    }
}
$nodeVersion = [Version]((node --version).TrimStart("v"))
if ($nodeVersion -lt [Version]"22.0.0") {
    throw "Node.js 22 or newer is required; found $nodeVersion."
}
$azdVersionOutput = azd version
if ($LASTEXITCODE -ne 0 -or $azdVersionOutput -notmatch "azd version ([0-9.]+)") {
    throw "Unable to determine the Windows azd version."
}
$azdVersion = [Version]$Matches[1]
if ($azdVersion -lt [Version]"1.27.0") {
    throw "Azure Developer CLI 1.27 or newer is required; found $azdVersion."
}

Push-Location $root
try {
    if (-not $PSBoundParameters.ContainsKey("EnvironmentName") -and $env:AZURE_ENV_NAME) {
        $EnvironmentName = $env:AZURE_ENV_NAME
    }
    if (-not $PSBoundParameters.ContainsKey("Location") -and $env:AZURE_LOCATION) {
        $Location = $env:AZURE_LOCATION
    }
    if (-not $PSBoundParameters.ContainsKey("ModelDeploymentName") -and $env:AZURE_AI_MODEL_DEPLOYMENT_NAME) {
        $ModelDeploymentName = $env:AZURE_AI_MODEL_DEPLOYMENT_NAME
    }

    $accountJson = az account show --only-show-errors --output json
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI is not signed in." }
    $account = $accountJson | ConvertFrom-Json
    if (-not $account.id -or -not $account.tenantId) {
        throw "Azure CLI did not return a tenant and subscription."
    }
    if ($account.state -ne "Enabled") {
        throw "Azure subscription '$($account.name)' is not enabled."
    }

    azd config set auth.useAzCliAuth true
    if ($LASTEXITCODE -ne 0) { throw "Unable to configure azd Azure CLI authentication." }
    $null = azd env select $EnvironmentName --no-prompt 2>$null
    if ($LASTEXITCODE -ne 0) {
        azd env new $EnvironmentName `
            --subscription $account.id `
            --location $Location `
            --no-prompt
        if ($LASTEXITCODE -ne 0) { throw "Unable to create azd environment '$EnvironmentName'." }
    }
    azd env set AZURE_SUBSCRIPTION_ID $account.id
    if ($LASTEXITCODE -ne 0) { throw "Unable to set the azd subscription." }
    azd env set AZURE_TENANT_ID $account.tenantId
    if ($LASTEXITCODE -ne 0) { throw "Unable to set the azd tenant." }
    azd env set AZURE_LOCATION $Location
    if ($LASTEXITCODE -ne 0) { throw "Unable to set the azd region." }
    azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME $ModelDeploymentName
    if ($LASTEXITCODE -ne 0) { throw "Unable to set the model deployment name." }

    Write-Host "Provisioning the Azure OpenAI model in $($account.name) ($($account.id)), tenant $($account.tenantId), region $Location."
    azd provision --no-prompt
    if ($LASTEXITCODE -ne 0) { throw "azd provision failed with exit code $LASTEXITCODE" }
    & (Join-Path $PSScriptRoot "start-ui.ps1") `
        -EnvironmentName $EnvironmentName `
        -AzureConfigDir $env:AZURE_CONFIG_DIR
}
finally {
    Pop-Location
}