#requires -Version 7.0
[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')]
    [string] $SubscriptionId,

    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9._()\-]{1,90}$')]
    [string] $ResourceGroup,

    [ValidateSet('centralus', 'eastus2', 'swedencentral')]
    [string] $Location = 'centralus',

    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]{3,12}$')]
    [string] $NamePrefix,

    [ValidateRange(2, 20)]
    [int] $Runs = 6,

    [ValidateRange(0.0, 1.0)]
    [double] $MinimumWarmHitRatio = 0.6,

    [string] $PythonExecutable = 'python',

    [string] $Workspace = (Join-Path ([IO.Path]::GetTempPath()) 'azure-context-cache-e2e'),

    [string] $ExistingUpstreamDirectory,

    [switch] $AllowExistingResourceGroup,

    [ValidateRange(5, 60)]
    [int] $TimeoutMinutes = 30
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$LockPath = Join-Path $ProjectRoot 'UPSTREAM_LOCK.json'
$Lock = Get-Content -LiteralPath $LockPath -Raw | ConvertFrom-Json
$Utf8NoBom = [Text.UTF8Encoding]::new($false)
$PathComparison = if ($IsWindows) {
    [StringComparison]::OrdinalIgnoreCase
} else {
    [StringComparison]::Ordinal
}

function Test-IsSameOrChildPath {
    param(
        [Parameter(Mandatory)][string] $Candidate,
        [Parameter(Mandatory)][string] $Parent
    )

    $candidatePath = [IO.Path]::GetFullPath($Candidate)
    $parentPath = [IO.Path]::GetFullPath($Parent).TrimEnd([char[]]'\/')
    $parentPrefix = $parentPath + [IO.Path]::DirectorySeparatorChar
    return $candidatePath.Equals($parentPath, $PathComparison) -or
        $candidatePath.StartsWith($parentPrefix, $PathComparison)
}

function Get-FileSha256 {
    param([Parameter(Mandatory)][string] $Path)

    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Invoke-BoundedProcess {
    param(
        [Parameter(Mandatory)][string] $Operation,
        [Parameter(Mandatory)][string] $FilePath,
        [Parameter(Mandatory)][AllowEmptyString()][AllowEmptyCollection()][string[]] $Arguments,
        [Parameter(Mandatory)][string] $WorkingDirectory,
        [Parameter(Mandatory)][int] $TimeoutSeconds,
        [Parameter(Mandatory)][string] $StdoutPath,
        [Parameter(Mandatory)][string] $StderrPath,
        [hashtable] $Environment = @{}
    )

    $processInfo = [Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $FilePath
    $processInfo.WorkingDirectory = $WorkingDirectory
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true
    foreach ($argument in $Arguments) {
        [void]$processInfo.ArgumentList.Add($argument)
    }
    foreach ($entry in $Environment.GetEnumerator()) {
        $processInfo.Environment[$entry.Key] = [string]$entry.Value
    }

    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $processInfo
    $startedAt = [DateTimeOffset]::UtcNow
    $timedOut = $false
    try {
        if (-not $process.Start()) {
            throw "Unable to start $Operation."
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $timedOut = -not $process.WaitForExit($TimeoutSeconds * 1000)
        if ($timedOut) {
            $process.Kill($true)
            $process.WaitForExit()
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $endedAt = [DateTimeOffset]::UtcNow
        [IO.File]::WriteAllText($StdoutPath, $stdout, $Utf8NoBom)
        [IO.File]::WriteAllText($StderrPath, $stderr, $Utf8NoBom)

        if ($timedOut) {
            $timeoutRecord = [ordered]@{
                schemaVersion = 1
                operation = $Operation
                startedAt = $startedAt.ToString('o')
                endedAt = $endedAt.ToString('o')
                timeoutSeconds = $TimeoutSeconds
                processTerminated = $process.HasExited
                stdout = [IO.Path]::GetFileName($StdoutPath)
                stderr = [IO.Path]::GetFileName($StderrPath)
            }
            $timeoutPath = Join-Path (Split-Path -Parent $StdoutPath) "$Operation.timeout.json"
            [IO.File]::WriteAllText(
                $timeoutPath,
                ($timeoutRecord | ConvertTo-Json -Depth 4),
                $Utf8NoBom
            )
            throw "$Operation exceeded $TimeoutSeconds seconds. Partial evidence: $timeoutPath"
        }
        if ($process.ExitCode -ne 0) {
            throw "$Operation failed with exit code $($process.ExitCode). Evidence: $StderrPath"
        }
        return [pscustomobject]@{
            Operation = $Operation
            ExitCode = $process.ExitCode
            StartedAt = $startedAt
            EndedAt = $endedAt
            Stdout = $stdout
            Stderr = $stderr
        }
    } finally {
        $process.Dispose()
    }
}

function Get-AzJson {
    param([Parameter(Mandatory)][string[]] $Arguments)

    $lines = & az @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "az exited with $LASTEXITCODE"
    }
    return (($lines -join [Environment]::NewLine) | ConvertFrom-Json)
}

if (-not $IsWindows) {
    throw 'The pinned official Quickstart currently requires PowerShell 7 on Windows.'
}
if ([string]::IsNullOrWhiteSpace($env:AZURE_CONFIG_DIR)) {
    throw 'Set an isolated AZURE_CONFIG_DIR before running this validation.'
}

foreach ($command in ('az', 'git', 'pwsh', $PythonExecutable)) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $command"
    }
}

$PythonPath = (Get-Command $PythonExecutable).Source
$GitPath = (Get-Command git).Source
$PwshPath = (Get-Command pwsh).Source
$WorkspaceRoot = [IO.Path]::GetFullPath($Workspace)
if (Test-IsSameOrChildPath -Candidate $WorkspaceRoot -Parent $ProjectRoot) {
    throw 'Workspace must be outside the public source tree.'
}
if ($ExistingUpstreamDirectory) {
    $ExistingUpstreamDirectory = [IO.Path]::GetFullPath($ExistingUpstreamDirectory)
    if (Test-IsSameOrChildPath -Candidate $ExistingUpstreamDirectory -Parent $ProjectRoot) {
        throw 'ExistingUpstreamDirectory must be outside the public source tree.'
    }
}

$Account = Get-AzJson @('account', 'show', '--only-show-errors', '-o', 'json')
if ($Account.id -ne $SubscriptionId -or $Account.state -ne 'Enabled') {
    throw 'The active Azure CLI subscription does not match the requested enabled subscription.'
}

$ResourceProvider = Get-AzJson @(
    'provider', 'show', '--namespace', 'Microsoft.Resources', '--subscription', $SubscriptionId,
    '--only-show-errors', '-o', 'json'
)
if ($ResourceProvider.registrationState -ne 'Registered') {
    throw 'Microsoft.Resources live read did not return Registered.'
}

foreach ($provider in ('Microsoft.Storage', 'Microsoft.CognitiveServices')) {
    $state = Get-AzJson @(
        'provider', 'show', '--namespace', $provider, '--subscription', $SubscriptionId,
        '--only-show-errors', '-o', 'json'
    )
    if ($state.registrationState -ne 'Registered') {
        throw "$provider must be Registered before this runner starts."
    }
}

$Feature = Get-AzJson @(
    'feature', 'show', '--namespace', 'Microsoft.CognitiveServices',
    '--name', 'OpenAI.ContextCacheAllowed', '--subscription', $SubscriptionId,
    '--only-show-errors', '-o', 'json'
)
if ($Feature.properties.state -ne 'Registered') {
    throw 'OpenAI.ContextCacheAllowed is not Registered. Complete preview onboarding first.'
}

$ResourceGroupExists = Get-AzJson @(
    'group', 'exists', '--name', $ResourceGroup, '--subscription', $SubscriptionId,
    '--only-show-errors', '-o', 'json'
)
if ($ResourceGroupExists -and -not $AllowExistingResourceGroup) {
    throw 'The resource group already exists. Pass -AllowExistingResourceGroup only after reviewing ownership and collision risk.'
}

if (-not $PSCmdlet.ShouldProcess(
        "$SubscriptionId/$ResourceGroup",
        'verify pinned upstream, deploy Azure resources, and send live Responses API requests'
    )) {
    return
}

[IO.Directory]::CreateDirectory($WorkspaceRoot) | Out-Null
$RunId = "run-{0}-{1}" -f (
    (Get-Date -AsUTC -Format 'yyyyMMdd-HHmmss'),
    ([guid]::NewGuid().ToString('N').Substring(0, 8))
)
$RunDirectory = Join-Path $WorkspaceRoot $RunId
$EvidenceDirectory = Join-Path $RunDirectory 'evidence'
[IO.Directory]::CreateDirectory($EvidenceDirectory) | Out-Null
$ProcessTimeoutSeconds = $TimeoutMinutes * 60

if ($ExistingUpstreamDirectory) {
    $UpstreamDirectory = $ExistingUpstreamDirectory
    $UpstreamMode = 'explicit-existing-clean-checkout'
    if (-not (Test-Path -LiteralPath (Join-Path $UpstreamDirectory '.git'))) {
        throw 'ExistingUpstreamDirectory is not a Git checkout.'
    }
} else {
    $UpstreamDirectory = Join-Path $RunDirectory 'upstream'
    $UpstreamMode = 'fresh-official-clone'
    $EmptyHooks = Join-Path $RunDirectory 'empty-hooks'
    [IO.Directory]::CreateDirectory($EmptyHooks) | Out-Null
    [void](Invoke-BoundedProcess `
        -Operation 'git-clone' `
        -FilePath $GitPath `
        -Arguments @(
            'clone', '--filter=blob:none', '--no-tags', '--no-checkout',
            '--config', "core.hooksPath=$EmptyHooks", $Lock.repository, $UpstreamDirectory
        ) `
        -WorkingDirectory $RunDirectory `
        -TimeoutSeconds $ProcessTimeoutSeconds `
        -StdoutPath (Join-Path $EvidenceDirectory 'git-clone.stdout.log') `
        -StderrPath (Join-Path $EvidenceDirectory 'git-clone.stderr.log')
    )
    [void](Invoke-BoundedProcess `
        -Operation 'git-checkout' `
        -FilePath $GitPath `
        -Arguments @(
            '-c', "core.hooksPath=$EmptyHooks", '-C', $UpstreamDirectory,
            'checkout', '--detach', $Lock.commit
        ) `
        -WorkingDirectory $RunDirectory `
        -TimeoutSeconds $ProcessTimeoutSeconds `
        -StdoutPath (Join-Path $EvidenceDirectory 'git-checkout.stdout.log') `
        -StderrPath (Join-Path $EvidenceDirectory 'git-checkout.stderr.log')
    )
}

[void](Invoke-BoundedProcess `
    -Operation 'verify-upstream' `
    -FilePath $PythonPath `
    -Arguments @(
        (Join-Path $PSScriptRoot 'verify_upstream.py'),
        '--upstream-dir', $UpstreamDirectory,
        '--lock', $LockPath
    ) `
    -WorkingDirectory $ProjectRoot `
    -TimeoutSeconds 120 `
    -StdoutPath (Join-Path $EvidenceDirectory 'verify-upstream.stdout.log') `
    -StderrPath (Join-Path $EvidenceDirectory 'verify-upstream.stderr.log')
)

$VenvDirectory = Join-Path $RunDirectory 'python-env'
$VenvPython = Join-Path $VenvDirectory 'Scripts/python.exe'
[void](Invoke-BoundedProcess `
    -Operation 'python-venv' `
    -FilePath $PythonPath `
    -Arguments @('-m', 'venv', $VenvDirectory) `
    -WorkingDirectory $RunDirectory `
    -TimeoutSeconds $ProcessTimeoutSeconds `
    -StdoutPath (Join-Path $EvidenceDirectory 'python-venv.stdout.log') `
    -StderrPath (Join-Path $EvidenceDirectory 'python-venv.stderr.log')
)
[void](Invoke-BoundedProcess `
    -Operation 'pip-install' `
    -FilePath $VenvPython `
    -Arguments @(
        '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input',
        '--timeout', '60', '--retries', '2',
        '-r', (Join-Path $UpstreamDirectory 'demo/requirements.txt')
    ) `
    -WorkingDirectory $RunDirectory `
    -TimeoutSeconds $ProcessTimeoutSeconds `
    -StdoutPath (Join-Path $EvidenceDirectory 'pip-install.stdout.log') `
    -StderrPath (Join-Path $EvidenceDirectory 'pip-install.stderr.log')
)
[void](Invoke-BoundedProcess `
    -Operation 'pip-check' `
    -FilePath $VenvPython `
    -Arguments @('-m', 'pip', 'check') `
    -WorkingDirectory $RunDirectory `
    -TimeoutSeconds 120 `
    -StdoutPath (Join-Path $EvidenceDirectory 'pip-check.stdout.log') `
    -StderrPath (Join-Path $EvidenceDirectory 'pip-check.stderr.log')
)

$StdoutPath = Join-Path $EvidenceDirectory 'official-quickstart.stdout.log'
$StderrPath = Join-Path $EvidenceDirectory 'official-quickstart.stderr.log'
$QuickstartPath = Join-Path $UpstreamDirectory 'scripts/quickstart.ps1'
$QuickstartEnvironment = @{
    AZURE_CONFIG_DIR = $env:AZURE_CONFIG_DIR
    PYTHONIOENCODING = 'utf-8'
    PATH = "{0}{1}{2}" -f (
        [IO.Path]::GetDirectoryName($VenvPython),
        [IO.Path]::PathSeparator,
        $env:PATH
    )
}
$QuickstartResult = Invoke-BoundedProcess `
    -Operation 'official-quickstart' `
    -FilePath $PwshPath `
    -Arguments @(
        '-NoProfile', '-File', $QuickstartPath,
        '-SubscriptionId', $SubscriptionId,
        '-ResourceGroup', $ResourceGroup,
        '-Location', $Location,
        '-NamePrefix', $NamePrefix,
        '-ExistingAoaiAccountName', '',
        '-Runs', $Runs.ToString(),
        '-SkipPython'
    ) `
    -WorkingDirectory $UpstreamDirectory `
    -TimeoutSeconds $ProcessTimeoutSeconds `
    -StdoutPath $StdoutPath `
    -StderrPath $StderrPath `
    -Environment $QuickstartEnvironment

if ($QuickstartResult.Stdout -match 'Demo exited with code\s+[1-9]\d*') {
    throw "The official Quickstart reported a failed demo. Evidence: $StdoutPath"
}

$SummaryPath = Join-Path $EvidenceDirectory 'demo-summary.json'
[void](Invoke-BoundedProcess `
    -Operation 'parse-demo' `
    -FilePath $VenvPython `
    -Arguments @(
        (Join-Path $PSScriptRoot 'parse_demo_output.py'),
        $StdoutPath,
        '--stderr', $StderrPath,
        '--output', $SummaryPath,
        '--expected-runs', $Runs.ToString(),
        '--min-warm-hit-ratio', $MinimumWarmHitRatio.ToString(
            [Globalization.CultureInfo]::InvariantCulture
        )
    ) `
    -WorkingDirectory $ProjectRoot `
    -TimeoutSeconds 120 `
    -StdoutPath (Join-Path $EvidenceDirectory 'parse-demo.stdout.log') `
    -StderrPath (Join-Path $EvidenceDirectory 'parse-demo.stderr.log')
)

$DeploymentMatch = [regex]::Match(
    $QuickstartResult.Stdout,
    "Deployment '([^']+)' Succeeded"
)
if (-not $DeploymentMatch.Success) {
    throw 'The Quickstart output did not identify the successful ARM deployment.'
}
$DeploymentName = $DeploymentMatch.Groups[1].Value
$ArmSummaryLines = & az deployment group show `
    --resource-group $ResourceGroup `
    --name $DeploymentName `
    --subscription $SubscriptionId `
    --query '{name:name,state:properties.provisioningState,correlationId:properties.correlationId,modelName:properties.outputs.modelName.value,modelVersion:properties.outputs.modelVersion.value,aoaiDeploymentName:properties.outputs.aoaiDeploymentName.value,contextCacheAccountName:properties.outputs.contextCacheAccountName.value}' `
    --only-show-errors -o json
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to read the completed ARM deployment.'
}
$ArmSummaryPath = Join-Path $EvidenceDirectory 'arm-summary.json'
[IO.File]::WriteAllText(
    $ArmSummaryPath,
    ($ArmSummaryLines -join [Environment]::NewLine),
    $Utf8NoBom
)

$RunContract = [ordered]@{
    schemaVersion = 1
    runId = $RunId
    upstreamRepository = $Lock.repository
    upstreamCommit = $Lock.commit
    upstreamMode = $UpstreamMode
    startedAt = $QuickstartResult.StartedAt.ToString('o')
    endedAt = $QuickstartResult.EndedAt.ToString('o')
    quickstartExitCode = $QuickstartResult.ExitCode
    runs = $Runs
    minimumWarmHitRatio = $MinimumWarmHitRatio
    resourceGroup = $ResourceGroup
    location = $Location
    deploymentName = $DeploymentName
    authentication = 'Azure CLI user credential through isolated AZURE_CONFIG_DIR'
}
$RunContractPath = Join-Path $EvidenceDirectory 'run-contract.json'
[IO.File]::WriteAllText(
    $RunContractPath,
    ($RunContract | ConvertTo-Json -Depth 4),
    $Utf8NoBom
)

$ManifestInputs = [ordered]@{
    upstreamLock = [ordered]@{
        sha256 = Get-FileSha256 $LockPath
        upstreamQuickstartGitBlobContentSha256 = $Lock.files.'scripts/quickstart.ps1'
    }
    publicRunner = [ordered]@{ sha256 = Get-FileSha256 $PSCommandPath }
    publicParser = [ordered]@{
        sha256 = Get-FileSha256 (Join-Path $PSScriptRoot 'parse_demo_output.py')
    }
    publicVerifier = [ordered]@{
        sha256 = Get-FileSha256 (Join-Path $PSScriptRoot 'verify_upstream.py')
    }
}
$Artifacts = @(
    Get-ChildItem -LiteralPath $EvidenceDirectory -File |
        Sort-Object Name |
        ForEach-Object {
            [ordered]@{
                path = $_.Name
                bytes = $_.Length
                sha256 = Get-FileSha256 $_.FullName
            }
        }
)
$Manifest = [ordered]@{
    schemaVersion = 1
    generatedAt = [DateTimeOffset]::UtcNow.ToString('o')
    runId = $RunId
    inputs = $ManifestInputs
    artifacts = $Artifacts
}
$ManifestPath = Join-Path $EvidenceDirectory 'manifest.json'
[IO.File]::WriteAllText(
    $ManifestPath,
    ($Manifest | ConvertTo-Json -Depth 8),
    $Utf8NoBom
)

Write-Host "OFFICIAL_E2E_PASS evidence=$EvidenceDirectory" -ForegroundColor Green