param(
    [string]$GatewayUrl = $env:CLAUDE_GATEWAY_URL,
    [ValidateRange(1,120)][int]$TimeoutSeconds = 15
)

$ErrorActionPreference = 'Stop'
$uri = $null
if (-not [Uri]::TryCreate($GatewayUrl, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
    throw 'HTTPS_GATEWAY_URL_REQUIRED'
}
if ([string]::IsNullOrWhiteSpace($env:CLAUDE_GATEWAY_KEY)) { throw 'GATEWAY_SECRET_REQUIRED' }
$expected = @('opus55-standard','sonnet55-standard','haiku55-standard')
$headers = @{Authorization='Bearer '+$env:CLAUDE_GATEWAY_KEY}
try {
    $result = Invoke-RestMethod -Method Get -Uri ($GatewayUrl.TrimEnd('/') + '/v1/models') -Headers $headers -TimeoutSec $TimeoutSeconds -MaximumRedirection 0
    $actual = @($result.data | ForEach-Object { $_.id })
    if (@($expected | Where-Object { $_ -notin $actual }).Count -gt 0) { throw 'EXPECTED_MODEL_ALIASES_MISSING' }
    [ordered]@{status='METADATA_READY';modelAliases=$expected;modelInvocation='NOT_RUN'} | ConvertTo-Json
} finally {
    $headers.Clear()
}