[CmdletBinding()]
param(
    [string]$EnvironmentName = "meeting-agent-dev",
    [string]$Location = "eastus2",
    [string]$ModelDeploymentName = "gpt-5.4-mini"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
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

    Write-Host "Deploying Meeting Agent to $($account.name) ($($account.id)), tenant $($account.tenantId), region $Location."
    azd up --no-prompt
    if ($LASTEXITCODE -ne 0) { throw "azd up failed with exit code $LASTEXITCODE" }
    & (Join-Path $PSScriptRoot "start-ui.ps1")
}
finally {
    Pop-Location
}