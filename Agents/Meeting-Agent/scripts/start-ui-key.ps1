[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Endpoint,
    [string]$Deployment = "gpt-5.4",
    [int]$BackendPort = 18089,
    [int]$UiPort = 4173
)

$ErrorActionPreference = "Stop"
$previous = @{}
$environmentNames = @(
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_KEY"
)
foreach ($name in $environmentNames) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

$secureKey = Read-Host "Azure OpenAI API key" -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
}
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "Azure OpenAI API key cannot be empty."
}

try {
    $env:AZURE_OPENAI_ENDPOINT = $Endpoint
    $env:AZURE_OPENAI_DEPLOYMENT = $Deployment
    $env:AZURE_OPENAI_API_KEY = $apiKey
    $apiKey = $null
    & (Join-Path $PSScriptRoot "start-ui.ps1") `
        -BackendPort $BackendPort `
        -UiPort $UiPort
}
finally {
    $apiKey = $null
    foreach ($name in $environmentNames) {
        $value = $previous[$name]
        if ($null -eq $value) {
            Remove-Item "Env:$name" -ErrorAction SilentlyContinue
        }
        else {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}