[CmdletBinding()]
param(
    [string]$ManagedAgentEndpoint = $env:MANAGED_AGENT_ENDPOINT,
    [string]$ManagedAgentName = $env:MANAGED_AGENT_NAME,
    [string]$ManagedAgentVersion = $env:MANAGED_AGENT_VERSION,
    [string]$ManagedAgentModel = $env:MANAGED_AGENT_MODEL,
    [Nullable[bool]]$RequireDeckPlan = $null,
    [string]$AzureConfigDir = $env:AZURE_CONFIG_DIR,
    [int]$BackendPort = 18089,
    [int]$UiPort = 4173
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$runtimeManifestPath = Join-Path $root ".azure\managed-runtime.json"
if (Test-Path -LiteralPath $runtimeManifestPath -PathType Leaf) {
    $runtimeManifest = Get-Content -LiteralPath $runtimeManifestPath -Raw | ConvertFrom-Json
    if (-not $ManagedAgentEndpoint) { $ManagedAgentEndpoint = $runtimeManifest.managed_agent_endpoint }
    if (-not $ManagedAgentName) { $ManagedAgentName = $runtimeManifest.managed_agent_name }
    if (-not $ManagedAgentVersion) { $ManagedAgentVersion = $runtimeManifest.managed_agent_version }
    if (-not $ManagedAgentModel) { $ManagedAgentModel = $runtimeManifest.managed_agent_model }
    if ($null -eq $RequireDeckPlan -and $null -ne $runtimeManifest.managed_agent_requires_deck_plan) {
        $RequireDeckPlan = [bool]$runtimeManifest.managed_agent_requires_deck_plan
    }
}
if ($null -eq $RequireDeckPlan) { $RequireDeckPlan = $true }
if (-not $ManagedAgentModel) { $ManagedAgentModel = "Kimi-K2.7-Code" }

if ($env:OS -ne "Windows_NT") {
    throw "start-ui.ps1 must run in Windows PowerShell. WSL cannot open the New Outlook draft."
}
foreach ($commandName in @("node.exe", "npm.cmd", "py.exe", "olk.exe", "az.cmd")) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required Windows command is unavailable: $commandName"
    }
}
$nodeVersion = [Version]((node --version).TrimStart("v"))
if ($nodeVersion -lt [Version]"22.0.0") {
    throw "Node.js 22 or newer is required; found $nodeVersion."
}
if (-not $ManagedAgentEndpoint -or -not $ManagedAgentName -or -not $ManagedAgentVersion) {
    throw "ManagedAgentEndpoint, ManagedAgentName, and ManagedAgentVersion are required."
}
$parsedEndpoint = $null
if (-not [Uri]::TryCreate($ManagedAgentEndpoint, [UriKind]::Absolute, [ref]$parsedEndpoint) -or
    $parsedEndpoint.Scheme -ne "https" -or
    -not $parsedEndpoint.Host.EndsWith(".services.ai.azure.com") -or
    -not $parsedEndpoint.IsDefaultPort -or
    $parsedEndpoint.UserInfo -or
    -not $parsedEndpoint.AbsolutePath.EndsWith("/openai/v1/responses")) {
    throw "ManagedAgentEndpoint must be an HTTPS Azure Foundry /openai/v1/responses endpoint without userinfo or a custom port."
}
if (-not $AzureConfigDir) {
    throw "AzureConfigDir is required. Use an isolated, signed-in Azure CLI profile."
}
$AzureConfigDir = [Environment]::ExpandEnvironmentVariables($AzureConfigDir)
if (-not (Test-Path -LiteralPath $AzureConfigDir -PathType Container)) {
    throw "AzureConfigDir does not exist: $AzureConfigDir"
}
$env:AZURE_CONFIG_DIR = (Resolve-Path -LiteralPath $AzureConfigDir).Path
$account = az account show --only-show-errors --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $account.state -ne "Enabled") {
    throw "Azure CLI is not signed in to an enabled subscription within $env:AZURE_CONFIG_DIR."
}
az account get-access-token --scope https://ai.azure.com/.default --only-show-errors --output none
if ($LASTEXITCODE -ne 0) {
    throw "The Azure CLI profile cannot acquire a Foundry data-plane token."
}

$backendProcess = $null
Push-Location (Join-Path $root "ui")
try {
    $virtualEnvironment = Join-Path $root ".venv-win"
    $backendPython = Join-Path $virtualEnvironment "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $backendPython -PathType Leaf)) {
        py -3.12 -m venv $virtualEnvironment
        if ($LASTEXITCODE -ne 0) { throw "Unable to create the local Python environment." }
    }
    & $backendPython -c "import azure.ai.agentserver.invocations, azure.identity, httpx, pptx, PIL"
    if ($LASTEXITCODE -ne 0) {
        & $backendPython -m pip install --disable-pip-version-check -r (Join-Path $root "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "Unable to install the local Python dependencies." }
    }

    if (Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue) {
        throw "Backend port $BackendPort is already in use."
    }
    $runtimeDirectory = Join-Path $env:LOCALAPPDATA "ManagedMeetingAgent\runtime"
    $sessionDirectory = Join-Path $runtimeDirectory "session"
    New-Item -ItemType Directory -Path $sessionDirectory -Force | Out-Null

    $env:PORT = [string]$BackendPort
    $env:OTEL_SDK_DISABLED = "true"
    $env:OTEL_EXPERIMENTAL_RESOURCE_DETECTORS = "service_instance,otel"
    $env:MEETING_AGENT_ANALYZER = "managed"
    $env:MANAGED_AGENT_CREDENTIAL = "azure-cli"
    $env:MEETING_AGENT_SESSION_HOME = $sessionDirectory
    $env:MANAGED_AGENT_ENDPOINT = $ManagedAgentEndpoint
    $env:MANAGED_AGENT_NAME = $ManagedAgentName
    $env:MANAGED_AGENT_VERSION = $ManagedAgentVersion
    $env:MANAGED_AGENT_REQUIRE_DECK_PLAN = $RequireDeckPlan.ToString().ToLowerInvariant()
    $backendProcess = Start-Process `
        -FilePath $backendPython `
        -ArgumentList "main.py" `
        -WorkingDirectory $root `
        -RedirectStandardOutput (Join-Path $runtimeDirectory "backend.stdout.log") `
        -RedirectStandardError (Join-Path $runtimeDirectory "backend.stderr.log") `
        -PassThru `
        -NoNewWindow

    $backendReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($backendProcess.HasExited) { break }
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$BackendPort/readiness" -TimeoutSec 2
            if ($health.status -eq "healthy") {
                $backendReady = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $backendReady) {
        $errorLog = Join-Path $runtimeDirectory "backend.stderr.log"
        $details = if (Test-Path $errorLog) { (Get-Content $errorLog -Tail 20) -join "`n" } else { "" }
        throw "The local Managed Agent backend did not become ready. $details"
    }

    Write-Host "Starting Meeting Agent UI with Foundry Managed Agent $ManagedAgentName v$ManagedAgentVersion and $ManagedAgentModel (Entra authentication)."
    $env:PORT = [string]$UiPort
    $env:MEETING_AGENT_LOCAL_AGENT_URL = "http://127.0.0.1:$BackendPort"
    $env:MEETING_AGENT_LOCAL_SESSION_HOME = $sessionDirectory
    $env:MEETING_AGENT_RUNTIME_MODE = "managed"
    $env:MEETING_AGENT_RUNTIME_ATTESTATION = "live-managed"
    $env:MEETING_AGENT_NAME = $ManagedAgentName
    $env:MANAGED_AGENT_MODEL = $ManagedAgentModel
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm build failed with exit code $LASTEXITCODE" }
    npm start
    if ($LASTEXITCODE -ne 0) { throw "Meeting Agent UI exited with code $LASTEXITCODE" }
}
finally {
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Pop-Location
}
