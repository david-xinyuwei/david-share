param(
    [string]$MatrixPath = (Join-Path $PSScriptRoot '..\data\matrix.json'),
    [Parameter(Mandatory)][string]$RunDirectory,
    [string[]]$CaseIds,
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$MatrixPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($MatrixPath)
$RunDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($RunDirectory)
$runner = Join-Path $PSScriptRoot 'invoke_case.ps1'
$matrix = [IO.File]::ReadAllText($MatrixPath,[Text.Encoding]::UTF8) | ConvertFrom-Json -AsHashtable
$cases = if ($CaseIds) { @($matrix.cases | Where-Object { $_.id -in $CaseIds }) } else { @($matrix.cases) }
if ($CaseIds -and $cases.Count -ne $CaseIds.Count) { throw 'UNKNOWN_OR_DUPLICATE_CASE' }
if ($ValidateOnly) {
    foreach ($case in $cases) {
        & $runner -Case matrix -CaseId $case.id -Label $case.id -MatrixPath $MatrixPath -RunDirectory $RunDirectory -ValidateOnly
    }
    return
}
if ([string]::IsNullOrWhiteSpace($env:CLAUDE_GATEWAY_URL) -or [string]::IsNullOrWhiteSpace($env:CLAUDE_GATEWAY_KEY)) { throw 'GATEWAY_ENVIRONMENT_REQUIRED' }
if (Test-Path -LiteralPath $RunDirectory) { throw 'USE_A_NEW_RUN_DIRECTORY' }
[void][IO.Directory]::CreateDirectory($RunDirectory)
[void][IO.Directory]::CreateDirectory((Join-Path $RunDirectory 'source\scripts'))
Copy-Item -LiteralPath $MatrixPath -Destination (Join-Path $RunDirectory 'matrix.json')
Copy-Item -LiteralPath $runner -Destination (Join-Path $RunDirectory 'source\scripts\invoke_case.ps1')
$frozen = Join-Path $RunDirectory 'source\scripts\invoke_case.ps1'
$state = [ordered]@{
    started=(Get-Date -Format o);status='IN_PROGRESS';budgetUsd=$matrix.budgetUsd
    runnerSha256=(Get-FileHash -LiteralPath $frozen).Hash.ToLowerInvariant()
    matrixSha256=(Get-FileHash -LiteralPath (Join-Path $RunDirectory 'matrix.json')).Hash.ToLowerInvariant()
    selectedCases=@($cases.id);completedCases=@();failedCases=@()
}
$statePath = Join-Path $RunDirectory 'run.json'
try {
    foreach ($case in $cases) {
        $state.activeCase = $case.id
        [IO.File]::WriteAllText($statePath,($state|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
        & $frozen -Case matrix -CaseId $case.id -Label $case.id -MatrixPath (Join-Path $RunDirectory 'matrix.json') -RunDirectory $RunDirectory
        $state.completedCases += @($case.id)
    }
    $state.status = 'EXECUTED_PENDING_PROVIDER_TRACE_AUDIT'
} catch {
    $state.status = 'FAILED'
    $state.failedCases += @(@{id=$state.activeCase;error=$_.Exception.Message})
    throw
} finally {
    $state.updated = Get-Date -Format o
    [IO.File]::WriteAllText($statePath,($state|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
}