[CmdletBinding()]
param(
    [int]$BackendPort = 18089,
    [int]$UiPort = 4173
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if ($env:OS -ne "Windows_NT") {
    throw "start-ui.ps1 must run in Windows PowerShell. WSL is not supported for the Outlook handoff."
}
foreach ($commandName in @("node.exe", "npm.cmd", "py.exe", "olk.exe")) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required Windows command is unavailable: $commandName"
    }
}
$nodeVersion = [Version]((node --version).TrimStart("v"))
if ($nodeVersion -lt [Version]"22.0.0") {
    throw "Node.js 22 or newer is required; found $nodeVersion."
}

$azureOpenAIEndpoint = $env:AZURE_OPENAI_ENDPOINT
$azureOpenAIDeployment = $env:AZURE_OPENAI_DEPLOYMENT
if (-not $azureOpenAIEndpoint -or -not $azureOpenAIDeployment) {
    throw "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT are required."
}
if (-not $env:AZURE_OPENAI_API_KEY) {
    throw "AZURE_OPENAI_API_KEY is required."
}
$parsedEndpoint = $null
if (-not [Uri]::TryCreate($azureOpenAIEndpoint, [UriKind]::Absolute, [ref]$parsedEndpoint) -or
    $parsedEndpoint.Scheme -ne "https") {
    throw "AZURE_OPENAI_ENDPOINT must be an absolute HTTPS URL."
}

Push-Location (Join-Path $root "ui")
$backendProcess = $null
try {
    $virtualEnvironment = Join-Path $root ".venv"
    $backendPython = Join-Path $virtualEnvironment "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $backendPython -PathType Leaf)) {
        py -3.12 -m venv $virtualEnvironment
        if ($LASTEXITCODE -ne 0) { throw "Unable to create the local Python environment." }
    }
    & $backendPython -c "import azure.ai.agentserver.invocations, openai, pptx, PIL"
    if ($LASTEXITCODE -ne 0) {
        & $backendPython -m pip install --disable-pip-version-check -r (Join-Path $root "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "Unable to install the local Python dependencies." }
    }

    $backendListener = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue
    if ($backendListener) { throw "Backend port $BackendPort is already in use." }
    $runtimeDirectory = Join-Path $root "runtime\windows-aoai"
    $sessionDirectory = Join-Path $runtimeDirectory "session"
    New-Item -ItemType Directory -Path $sessionDirectory -Force | Out-Null
    $env:PORT = [string]$BackendPort
    $env:OTEL_SDK_DISABLED = "true"
    $env:MEETING_AGENT_ANALYZER = "azure"
    $env:MEETING_AGENT_SESSION_HOME = $sessionDirectory
    $backendProcess = Start-Process `
        -FilePath $backendPython `
        -ArgumentList "main.py" `
        -WorkingDirectory $root `
        -RedirectStandardOutput (Join-Path $runtimeDirectory "backend.stdout.log") `
        -RedirectStandardError (Join-Path $runtimeDirectory "backend.stderr.log") `
        -PassThru `
        -NoNewWindow
    Remove-Item Env:AZURE_OPENAI_API_KEY -ErrorAction SilentlyContinue

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
        throw "The local AOAI backend did not become ready. $details"
    }

    Write-Host "Starting Meeting Agent with Azure OpenAI Responses API ($azureOpenAIDeployment, key authentication)."
    $env:PORT = [string]$UiPort
    $env:MEETING_AGENT_LOCAL_AGENT_URL = "http://127.0.0.1:$BackendPort"
    $env:MEETING_AGENT_LOCAL_SESSION_HOME = $sessionDirectory
    $env:MEETING_AGENT_RUNTIME_MODE = "aoai"
    $env:MEETING_AGENT_NAME = "meeting-agent"
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm build failed with exit code $LASTEXITCODE" }
    npm start
    if ($LASTEXITCODE -ne 0) { throw "Meeting Agent UI exited with code $LASTEXITCODE" }
}
finally {
    Remove-Item Env:AZURE_OPENAI_API_KEY -ErrorAction SilentlyContinue
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Pop-Location
}
[CmdletBinding()]
param(
    [string]$EnvironmentName = "meeting-agent-dev",
    [string]$AzureConfigDir,
    [int]$BackendPort = 18089,
    [int]$UiPort = 4173
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$authenticationMode = if ($env:AZURE_OPENAI_AUTH_MODE) {
    $env:AZURE_OPENAI_AUTH_MODE.Trim().ToLowerInvariant()
}
else {
    "entra"
}

if ($env:OS -ne "Windows_NT") {
    throw "start-ui.ps1 must run in Windows PowerShell. WSL is not supported for the Outlook handoff."
}
if ($authenticationMode -notin @("entra", "key")) {
    throw "AZURE_OPENAI_AUTH_MODE must be entra or key."
}

$requiredCommands = @("node.exe", "npm.cmd", "py.exe", "olk.exe")
if ($authenticationMode -eq "entra") {
    $requiredCommands += @("az.cmd", "azd.exe")
}
foreach ($commandName in $requiredCommands) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required Windows command is unavailable: $commandName"
    }
}
$nodeVersion = [Version]((node --version).TrimStart("v"))
if ($nodeVersion -lt [Version]"22.0.0") {
    throw "Node.js 22 or newer is required; found $nodeVersion."
}

Push-Location (Join-Path $root "ui")
$backendProcess = $null
try {
    if ($authenticationMode -eq "key") {
        $azureOpenAIEndpoint = $env:AZURE_OPENAI_ENDPOINT
        $azureOpenAIDeployment = $env:AZURE_OPENAI_DEPLOYMENT
        if (-not $azureOpenAIEndpoint -or -not $azureOpenAIDeployment) {
            throw "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT are required for key authentication."
        }
        if (-not $env:AZURE_OPENAI_API_KEY) {
            throw "AZURE_OPENAI_API_KEY is required for key authentication."
        }
        $parsedEndpoint = $null
        if (-not [Uri]::TryCreate($azureOpenAIEndpoint, [UriKind]::Absolute, [ref]$parsedEndpoint) -or
            $parsedEndpoint.Scheme -ne "https") {
            throw "AZURE_OPENAI_ENDPOINT must be an absolute HTTPS URL."
        }
        Write-Host "Starting Windows Meeting Agent UI with Azure OpenAI Responses API ($azureOpenAIDeployment, key authentication)."
    }
    else {
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
            azd config set auth.useAzCliAuth true
            if ($LASTEXITCODE -ne 0) { throw "Unable to configure azd Azure CLI authentication." }
            azd env select $EnvironmentName --no-prompt
            if ($LASTEXITCODE -ne 0) { throw "Unable to select azd environment '$EnvironmentName'." }
            $deployment = azd env get-values --output json --no-prompt | ConvertFrom-Json
            if ($LASTEXITCODE -ne 0) { throw "Unable to read azd environment '$EnvironmentName'." }
            $account = az account show --only-show-errors --output json | ConvertFrom-Json
            if ($LASTEXITCODE -ne 0) { throw "Azure CLI is not signed in within $env:AZURE_CONFIG_DIR." }
            if ($account.state -ne "Enabled") { throw "Azure subscription '$($account.name)' is not enabled." }
            if ($account.id -ne $deployment.AZURE_SUBSCRIPTION_ID) {
                throw "Azure CLI subscription does not match the deployed azd environment."
            }
            if ($account.tenantId -ne $deployment.AZURE_TENANT_ID) {
                throw "Azure CLI tenant does not match the deployed azd environment."
            }
            if (-not $deployment.AZURE_OPENAI_ENDPOINT -or -not $deployment.AZURE_AI_MODEL_DEPLOYMENT_NAME) {
                throw "The selected azd environment does not contain an Azure OpenAI endpoint and model deployment."
            }
            $azureOpenAIEndpoint = $deployment.AZURE_OPENAI_ENDPOINT
            $azureOpenAIDeployment = $deployment.AZURE_AI_MODEL_DEPLOYMENT_NAME
            Write-Host "Starting Windows Meeting Agent UI with Azure OpenAI Responses API ($azureOpenAIDeployment, Entra authentication)."
        }
        finally {
            Pop-Location
        }
    }

    $virtualEnvironment = Join-Path $root ".venv"
    $backendPython = Join-Path $virtualEnvironment "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $backendPython -PathType Leaf)) {
        py -3.12 -m venv $virtualEnvironment
        if ($LASTEXITCODE -ne 0) { throw "Unable to create the local Python environment." }
    }
    & $backendPython -c "import azure.ai.agentserver.invocations, openai, pptx, PIL"
    if ($LASTEXITCODE -ne 0) {
        & $backendPython -m pip install --disable-pip-version-check -r (Join-Path $root "requirements.txt")
        if ($LASTEXITCODE -ne 0) { throw "Unable to install the local Python dependencies." }
    }

    $backendListener = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue
    if ($backendListener) { throw "Backend port $BackendPort is already in use." }
    $runtimeDirectory = Join-Path $root "runtime\windows-aoai"
    $sessionDirectory = Join-Path $runtimeDirectory "session"
    New-Item -ItemType Directory -Path $sessionDirectory -Force | Out-Null
    $env:PORT = [string]$BackendPort
    $env:OTEL_SDK_DISABLED = "true"
    $env:MEETING_AGENT_ANALYZER = "azure"
    $env:MEETING_AGENT_SESSION_HOME = $sessionDirectory
    $env:AZURE_OPENAI_AUTH_MODE = $authenticationMode
    $env:AZURE_OPENAI_ENDPOINT = $azureOpenAIEndpoint
    $env:AZURE_OPENAI_DEPLOYMENT = $azureOpenAIDeployment
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
        throw "The local AOAI backend did not become ready. $details"
    }
    if ($authenticationMode -eq "key") {
        Remove-Item Env:AZURE_OPENAI_API_KEY -ErrorAction SilentlyContinue
    }

    $env:PORT = [string]$UiPort
    $env:MEETING_AGENT_LOCAL_AGENT_URL = "http://127.0.0.1:$BackendPort"
    $env:MEETING_AGENT_LOCAL_SESSION_HOME = $sessionDirectory
    $env:MEETING_AGENT_RUNTIME_MODE = "aoai"
    $env:MEETING_AGENT_AOAI_AUTH_MODE = $authenticationMode
    $env:MEETING_AGENT_NAME = "meeting-agent"
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