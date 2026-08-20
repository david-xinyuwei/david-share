#requires -Version 7.0
[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')]
    [string] $SubscriptionId,

    [Parameter(Mandatory)]
    [ValidatePattern('^[\p{L}\p{Nd}_().-]{1,90}(?<!\.)$')]
    [string] $ResourceGroup,

    [ValidateSet('centralus', 'swedencentral')]
    [string] $Location = 'centralus',

    [Parameter(Mandatory)]
    [ValidatePattern('^[a-z0-9]{3,12}$')]
    [string] $NamePrefix,

    [ValidateRange(2, 20)]
    [int] $Runs = 6,

    [ValidateScript({ $_ -gt 0.0 -and $_ -le 1.0 })]
    [double] $MinimumWarmHitRatio = 0.6,

    [string] $PythonExecutable = 'python',

    [string] $Workspace = (Join-Path ([IO.Path]::GetTempPath()) 'azure-context-cache-e2e'),

    [string] $ExistingUpstreamDirectory,

    [ValidateRange(1, 300)]
    [int] $AzureReadTimeoutSeconds = 120,

    [ValidateRange(5, 60)]
    [int] $TimeoutMinutes = 30
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$LockPath = Join-Path $ProjectRoot 'UPSTREAM_LOCK.json'
$PythonLockPath = Join-Path $ProjectRoot 'requirements-live-win-py311.lock'
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

function Get-NonReparseFullPath {
    param(
        [Parameter(Mandatory)][string] $Path,
        [Parameter(Mandatory)][string] $Label
    )

    $fullPath = [IO.Path]::GetFullPath($Path)
    $probe = $fullPath
    while (-not (Test-Path -LiteralPath $probe)) {
        $parent = [IO.Path]::GetDirectoryName($probe)
        if ([string]::IsNullOrEmpty($parent) -or $parent -eq $probe) {
            break
        }
        $probe = $parent
    }
    while (-not [string]::IsNullOrEmpty($probe)) {
        $item = Get-Item -LiteralPath $probe -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "$Label cannot traverse a reparse point: $($item.FullName)"
        }
        $parent = [IO.Directory]::GetParent($probe)
        if ($null -eq $parent) {
            break
        }
        $probe = $parent.FullName
    }
    return $fullPath
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
            if (-not $process.WaitForExit(5000)) {
                throw "$Operation exceeded $TimeoutSeconds seconds and did not terminate within 5 seconds."
            }
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
    param(
        [Parameter(Mandatory)][string[]] $Arguments,
        [string] $Operation = 'az-read'
    )

    $safeOperation = $Operation -replace '[^A-Za-z0-9-]', '-'
    $temporaryPrefix = Join-Path (
        [IO.Path]::GetTempPath()
    ) "azure-context-cache-$safeOperation-$([guid]::NewGuid().ToString('N'))"
    $temporaryStdout = "$temporaryPrefix.stdout.log"
    $temporaryStderr = "$temporaryPrefix.stderr.log"
    $succeeded = $false
    try {
        $result = Invoke-BoundedProcess `
            -Operation $safeOperation `
            -FilePath $AzPath `
            -Arguments $Arguments `
            -WorkingDirectory $ProjectRoot `
            -TimeoutSeconds $AzureReadTimeoutSeconds `
            -StdoutPath $temporaryStdout `
            -StderrPath $temporaryStderr
        if ([string]::IsNullOrWhiteSpace($result.Stdout)) {
            throw "$Operation returned empty JSON."
        }
        $parsed = $result.Stdout | ConvertFrom-Json -NoEnumerate
        if ($null -eq $parsed) {
            throw "$Operation returned JSON null."
        }
        $succeeded = $true
        return $parsed
    } finally {
        if ($succeeded) {
            foreach ($temporaryPath in ($temporaryStdout, $temporaryStderr)) {
                if ([IO.File]::Exists($temporaryPath)) {
                    [IO.File]::Delete($temporaryPath)
                }
            }
        }
    }
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

$AzPath = (Get-Command az).Source
$PythonPath = (Get-Command $PythonExecutable).Source
$GitPath = (Get-Command git).Source
$PwshPath = (Get-Command pwsh).Source
$RuntimeProbeDirectory = Join-Path (
    [IO.Path]::GetTempPath()
) "azure-context-cache-python-$([guid]::NewGuid().ToString('N'))"
[IO.Directory]::CreateDirectory($RuntimeProbeDirectory) | Out-Null
try {
    $RuntimeProbe = Invoke-BoundedProcess `
        -Operation 'python-runtime' `
        -FilePath $PythonPath `
        -Arguments @(
            '-c',
            'import json, platform, struct, sys; print(json.dumps({"major": sys.version_info.major, "minor": sys.version_info.minor, "bits": struct.calcsize("P") * 8, "machine": platform.machine()}))'
        ) `
        -WorkingDirectory $RuntimeProbeDirectory `
        -TimeoutSeconds 30 `
        -StdoutPath (Join-Path $RuntimeProbeDirectory 'stdout.log') `
        -StderrPath (Join-Path $RuntimeProbeDirectory 'stderr.log')
    $RuntimeInfo = $RuntimeProbe.Stdout | ConvertFrom-Json
} finally {
    if ([IO.Directory]::Exists($RuntimeProbeDirectory)) {
        [IO.Directory]::Delete($RuntimeProbeDirectory, $true)
    }
}
if ($RuntimeInfo.major -ne 3 -or $RuntimeInfo.minor -ne 11 -or
    $RuntimeInfo.bits -ne 64 -or $RuntimeInfo.machine -notin @('AMD64', 'x86_64')) {
    throw 'The live runner requires 64-bit CPython 3.11 on AMD64 Windows.'
}
$AzureConfigRoot = Get-NonReparseFullPath `
    -Path $env:AZURE_CONFIG_DIR `
    -Label 'AZURE_CONFIG_DIR'
if (-not (Test-Path -LiteralPath $AzureConfigRoot -PathType Container)) {
    throw 'AZURE_CONFIG_DIR must identify an existing dedicated directory.'
}
$DefaultAzureConfigRoot = [IO.Path]::GetFullPath((Join-Path $HOME '.azure'))
if ($AzureConfigRoot.Equals($DefaultAzureConfigRoot, $PathComparison)) {
    throw 'AZURE_CONFIG_DIR must not use the default shared Azure CLI profile.'
}
if (Test-IsSameOrChildPath -Candidate $AzureConfigRoot -Parent $ProjectRoot) {
    throw 'AZURE_CONFIG_DIR must be outside the public source tree.'
}

$WorkspaceRoot = Get-NonReparseFullPath -Path $Workspace -Label 'Workspace'
if (Test-IsSameOrChildPath -Candidate $WorkspaceRoot -Parent $ProjectRoot) {
    throw 'Workspace must be outside the public source tree.'
}
if ((Test-IsSameOrChildPath -Candidate $AzureConfigRoot -Parent $WorkspaceRoot) -or
    (Test-IsSameOrChildPath -Candidate $WorkspaceRoot -Parent $AzureConfigRoot)) {
    throw 'Workspace and AZURE_CONFIG_DIR must be separate directory trees.'
}
if ($ExistingUpstreamDirectory) {
    $ExistingUpstreamDirectory = [IO.Path]::GetFullPath($ExistingUpstreamDirectory)
    if (Test-IsSameOrChildPath -Candidate $ExistingUpstreamDirectory -Parent $ProjectRoot) {
        throw 'ExistingUpstreamDirectory must be outside the public source tree.'
    }
}

$LeasePath = Join-Path $AzureConfigRoot 'azure-context-cache-e2e.lock'
try {
    $RunLease = [IO.File]::Open(
        $LeasePath,
        [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
} catch {
    throw 'Another validation run is already using this AZURE_CONFIG_DIR.'
}

try {
$Account = Get-AzJson `
    -Operation 'az-account-show' `
    -Arguments @('account', 'show', '--only-show-errors', '-o', 'json')
if ($Account.id -ne $SubscriptionId -or $Account.state -ne 'Enabled') {
    throw 'The active Azure CLI subscription does not match the requested enabled subscription.'
}

$ResourceProvider = Get-AzJson `
    -Operation 'az-provider-microsoft-resources' `
    -Arguments @(
        'provider', 'show', '--namespace', 'Microsoft.Resources',
        '--subscription', $SubscriptionId, '--only-show-errors', '-o', 'json'
    )
if ($ResourceProvider.registrationState -ne 'Registered') {
    throw 'Microsoft.Resources live read did not return Registered.'
}

foreach ($provider in ('Microsoft.Storage', 'Microsoft.CognitiveServices')) {
    $state = Get-AzJson `
        -Operation "az-provider-$($provider -replace '[^A-Za-z0-9]', '-')" `
        -Arguments @(
            'provider', 'show', '--namespace', $provider,
            '--subscription', $SubscriptionId, '--only-show-errors', '-o', 'json'
        )
    if ($state.registrationState -ne 'Registered') {
        throw "$provider must be Registered before this runner starts."
    }
}

$Feature = Get-AzJson `
    -Operation 'az-feature-context-cache' `
    -Arguments @(
        'feature', 'show', '--namespace', 'Microsoft.CognitiveServices',
        '--name', 'OpenAI.ContextCacheAllowed', '--subscription', $SubscriptionId,
        '--only-show-errors', '-o', 'json'
    )
if ($Feature.properties.state -ne 'Registered') {
    throw 'OpenAI.ContextCacheAllowed is not Registered. Complete preview onboarding first.'
}

$ResourceGroupExists = Get-AzJson `
    -Operation 'az-resource-group-exists' `
    -Arguments @(
        'group', 'exists', '--name', $ResourceGroup, '--subscription', $SubscriptionId,
        '--only-show-errors', '-o', 'json'
    )
if ($ResourceGroupExists) {
    throw 'The resource group already exists. Use a new unique resource group for each validation run.'
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
    $UpstreamSourceDirectory = $ExistingUpstreamDirectory
    $UpstreamMode = 'explicit-existing-object-source'
    if (-not (Test-Path -LiteralPath (Join-Path $UpstreamSourceDirectory '.git'))) {
        throw 'ExistingUpstreamDirectory is not a Git checkout.'
    }
} else {
    $UpstreamSourceDirectory = Join-Path $RunDirectory 'upstream-source'
    $UpstreamMode = 'fresh-official-clone-object-source'
    $EmptyHooks = Join-Path $RunDirectory 'empty-hooks'
    [IO.Directory]::CreateDirectory($EmptyHooks) | Out-Null
    [void](Invoke-BoundedProcess `
        -Operation 'git-clone' `
        -FilePath $GitPath `
        -Arguments @(
            'clone', '--filter=blob:none', '--no-tags', '--no-checkout',
            '--config', "core.hooksPath=$EmptyHooks", $Lock.repository, $UpstreamSourceDirectory
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
            '-c', "core.hooksPath=$EmptyHooks", '-C', $UpstreamSourceDirectory,
            'checkout', '--detach', $Lock.commit
        ) `
        -WorkingDirectory $RunDirectory `
        -TimeoutSeconds $ProcessTimeoutSeconds `
        -StdoutPath (Join-Path $EvidenceDirectory 'git-checkout.stdout.log') `
        -StderrPath (Join-Path $EvidenceDirectory 'git-checkout.stderr.log')
    )
}

$UpstreamDirectory = Join-Path $RunDirectory 'verified-upstream'
[void](Invoke-BoundedProcess `
    -Operation 'verify-upstream' `
    -FilePath $PythonPath `
    -Arguments @(
        (Join-Path $PSScriptRoot 'verify_upstream.py'),
        '--upstream-dir', $UpstreamSourceDirectory,
        '--lock', $LockPath,
        '--output', $UpstreamDirectory,
        '--git-executable', $GitPath
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
        '--timeout', '60', '--retries', '2', '--require-hashes', '--only-binary=:all:',
        '-r', $PythonLockPath
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
    PATH = "{0}{1}{2}{1}{3}" -f (
        [IO.Path]::GetDirectoryName($VenvPython),
        [IO.Path]::PathSeparator,
        [IO.Path]::GetDirectoryName($AzPath),
        $env:PATH
    )
}
$ResourceGroupExistsBeforeDeploy = Get-AzJson `
    -Operation 'az-resource-group-recheck' `
    -Arguments @(
        'group', 'exists', '--name', $ResourceGroup, '--subscription', $SubscriptionId,
        '--only-show-errors', '-o', 'json'
    )
if ($ResourceGroupExistsBeforeDeploy) {
    throw 'The resource group was created after preflight. Use a new unique resource group.'
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
$ArmDeployment = Get-AzJson `
    -Operation 'az-arm-deployment-summary' `
    -Arguments @(
        'deployment', 'group', 'show', '--resource-group', $ResourceGroup,
        '--name', $DeploymentName, '--subscription', $SubscriptionId,
        '--query', '{name:name,state:properties.provisioningState,correlationId:properties.correlationId,azureOpenAIAccountName:properties.outputs.azureOpenAIAccountName.value,aoaiDeploymentName:properties.outputs.aoaiDeploymentName.value,contextCacheAccountName:properties.outputs.contextCacheAccountName.value,contextCacheContainerId:properties.outputs.contextCacheContainerId.value,modelName:properties.outputs.modelName.value,modelVersion:properties.outputs.modelVersion.value}',
        '--only-show-errors', '-o', 'json'
    )
$ResourceRoot = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup"
$AoaiDeploymentId = "$ResourceRoot/providers/Microsoft.CognitiveServices/accounts/$NamePrefix-aoai/deployments/context-cache-deployment"
$CacheContainerId = "$ResourceRoot/providers/Microsoft.Storage/contextCaches/$NamePrefix-cache/contextCacheContainers/default-container"
$AoaiDeployment = Get-AzJson `
    -Operation 'az-aoai-deployment-binding' `
    -Arguments @(
        'resource', 'show', '--ids', $AoaiDeploymentId,
        '--api-version', '2026-03-15-preview', '--only-show-errors', '-o', 'json'
    )
$CacheContainer = Get-AzJson `
    -Operation 'az-context-cache-container' `
    -Arguments @(
        'resource', 'show', '--ids', $CacheContainerId,
        '--api-version', '2026-01-01-preview', '--only-show-errors', '-o', 'json'
    )
$ArmRawPath = Join-Path $EvidenceDirectory 'arm-summary.raw.json'
[IO.File]::WriteAllText(
    $ArmRawPath,
    ([ordered]@{
        deployment = $ArmDeployment
        aoaiDeployment = $AoaiDeployment
        cacheContainer = $CacheContainer
    } | ConvertTo-Json -Depth 20),
    $Utf8NoBom
)
$ArmSummaryPath = Join-Path $EvidenceDirectory 'arm-summary.json'
[void](Invoke-BoundedProcess `
    -Operation 'validate-arm-binding' `
    -FilePath $VenvPython `
    -Arguments @(
        (Join-Path $PSScriptRoot 'validate_arm_summary.py'),
        $ArmRawPath,
        '--output', $ArmSummaryPath,
        '--subscription-id', $SubscriptionId,
        '--resource-group', $ResourceGroup,
        '--name-prefix', $NamePrefix
    ) `
    -WorkingDirectory $ProjectRoot `
    -TimeoutSeconds 120 `
    -StdoutPath (Join-Path $EvidenceDirectory 'validate-arm-binding.stdout.log') `
    -StderrPath (Join-Path $EvidenceDirectory 'validate-arm-binding.stderr.log')
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
        upstreamRequirementsGitBlobContentSha256 = $Lock.files.'demo/requirements.txt'
    }
    pythonArtifactLock = [ordered]@{
        sha256 = Get-FileSha256 $PythonLockPath
        runtime = 'CPython 3.11 AMD64 Windows'
    }
    publicRunner = [ordered]@{ sha256 = Get-FileSha256 $PSCommandPath }
    publicParser = [ordered]@{
        sha256 = Get-FileSha256 (Join-Path $PSScriptRoot 'parse_demo_output.py')
    }
    publicArmValidator = [ordered]@{
        sha256 = Get-FileSha256 (Join-Path $PSScriptRoot 'validate_arm_summary.py')
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
} finally {
    $RunLease.Dispose()
}