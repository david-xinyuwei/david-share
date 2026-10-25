param(
    [Parameter(Mandatory)][string]$Case,
    [Parameter(Mandatory)][string]$Label,
    [ValidateSet('opus55-lab', 'opus55-cache-system', 'opus55-standard', 'sonnet55-standard', 'haiku55-standard')][string]$Model = 'opus55-lab',
    [string]$ReplayResult,
    [ValidateRange(1,4096)][int]$MaxTokens = 1024,
    [string]$RunDirectory,
    [string]$MatrixPath,
    [string]$CaseId,
    [string]$GatewayUrl = $env:CLAUDE_GATEWAY_URL,
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$resultDirectory = Join-Path $root '验证结果'
$python = 'python'
$isSequenceCase = $Case -in @('five-turn','matrix')
$budgetLimit = 10.0
$priorReserve = 2.0
$sequenceAttemptLimit = 15
if (-not $ValidateOnly -and -not $GatewayUrl) { throw 'CLAUDE_GATEWAY_URL_REQUIRED' }
if ($Case -ne 'matrix') { throw 'PUBLIC_ENTRY_SUPPORTS_MATRIX_ONLY' }
$pricing = @{
    'opus55-standard' = @{input=4.0;write=5.0;read=0.20;output=20.0}
    'sonnet55-standard' = @{input=2.0;write=2.50;read=0.10;output=10.0}
    'haiku55-standard' = @{input=0.10;write=0.125;read=0.01;output=0.50}
}
function Get-LabUsageCost {
    param([System.Collections.IDictionary]$Usage, [string]$ModelName)
    foreach ($field in @('input_tokens','cache_creation_input_tokens','cache_read_input_tokens','output_tokens')) {
        if ($null -eq $Usage -or -not $Usage.Contains($field) -or $null -eq $Usage[$field]) { return $null }
    }
    $rates = $pricing[$ModelName]
    if ($null -eq $rates) { throw 'UNKNOWN_MODEL_PRICE' }
    $totalInput = $Usage.input_tokens + $Usage.cache_creation_input_tokens + $Usage.cache_read_input_tokens
    if ($ModelName -eq 'haiku55-standard' -and $totalInput -gt 100000) {
        $rates = @{input=0.50;write=0.625;read=0.05;output=2.50}
    }
    return ($Usage.input_tokens * $rates.input + $Usage.cache_creation_input_tokens * $rates.write + $Usage.cache_read_input_tokens * $rates.read + $Usage.output_tokens * $rates.output) / 1000000
}
if ($Case -eq 'matrix') {
    if (-not $MatrixPath -or -not $CaseId -or -not $RunDirectory -or $ReplayResult) { throw 'MATRIX_ARGUMENTS_REQUIRED' }
    $matrix = [IO.File]::ReadAllText($MatrixPath,[Text.Encoding]::UTF8) | ConvertFrom-Json -AsHashtable
    $selection = @($matrix.cases | Where-Object { $_.id -eq $CaseId })
    if ($selection.Count -ne 1) { throw 'MATRIX_CASE_NOT_UNIQUE' }
    $selected = $selection[0]
    $Model = $selected.model
    $MaxTokens = $matrix.baseRequest.max_tokens
    $budgetLimit = [double]$matrix.budgetUsd
    $priorReserve = [double]$matrix.priorWorkBudgetReserveUsd
    $sequenceAttemptLimit = [int]$matrix.attemptLimit
    if ($budgetLimit -ne 50 -or $sequenceAttemptLimit -ne 50 -or $matrix.questions.Count -ne 5 -or $matrix.cases.Count -ne 10) { throw 'MATRIX_APPROVAL_MISMATCH' }
    if ($Model -notin $pricing.Keys -or $MaxTokens -ne 4096 -or $selected.effort -ne 'medium') { throw 'MATRIX_MODEL_CONTRACT_MISMATCH' }
    $validModes = switch ($Model) {
        'opus55-standard' { @('adaptive') }
        'sonnet55-standard' { @('adaptive','between_tools') }
        'haiku55-standard' { @('adaptive','disabled') }
    }
    if ($selected.thinking -notin $validModes -or $selected.cache -notin @('system','conversation')) { throw 'UNSUPPORTED_MATRIX_COMBINATION' }
    $scenario = @{questions=$matrix.questions}
    $sourceHashes = @{matrix=(Get-FileHash -LiteralPath $MatrixPath -Algorithm SHA256).Hash.ToLowerInvariant()}
    $request = $matrix.baseRequest | ConvertTo-Json -Depth 50 -Compress | ConvertFrom-Json -AsHashtable
    $request.model = $Model
    $request.thinking = @{type=$selected.thinking}
    $request.output_config = @{effort=$selected.effort}
    $request.stream = $true
    $request.messages = @(@{role='user';content=$scenario.questions[0]})
    if ($selected.cache -eq 'conversation') { $request.cache_control = @{type='ephemeral'} }
    $resultDirectory = [IO.Path]::GetFullPath($RunDirectory)
    if ($ValidateOnly) {
        Write-Output (@{status='SHAPE_READY';caseId=$CaseId;model=$Model;requests=5;thinking=$request.thinking;effort=$selected.effort;cache=$selected.cache;budgetUsd=$budgetLimit;attemptLimit=$sequenceAttemptLimit;sourceHashes=$sourceHashes} | ConvertTo-Json -Depth 8)
        return
    }
    if (-not (Test-Path -LiteralPath $resultDirectory -PathType Container)) { throw 'MATRIX_RUN_MUST_BE_INITIALIZED' }
    if ($Label -ne $CaseId) { throw 'MATRIX_LABEL_MUST_MATCH_CASE' }
} elseif ($Case -eq 'five-turn') {
    if ($Model -notin $pricing.Keys -or $MaxTokens -ne 4096 -or $ReplayResult) { throw 'FIVE_TURN_CONTRACT_MISMATCH' }
    $scenarioPath = Join-Path $root 'data\claude-five-turn.json'
    $scenario = [IO.File]::ReadAllText($scenarioPath,[Text.Encoding]::UTF8) | ConvertFrom-Json -AsHashtable
    if ($scenario.questions.Count -ne 5) { throw 'EXPECTED_FIVE_QUESTIONS' }
    $sourceHashes = @{}
    $context = $scenario.context
    foreach ($relative in $scenario.sourceFiles) {
        $sourcePath = Join-Path $root $relative
        $sourceHashes[$relative] = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $context += "`n`n--- SOURCE: $relative ---`n" + [IO.File]::ReadAllText($sourcePath,[Text.Encoding]::UTF8)
    }
    $sourceHashes['data/claude-five-turn.json'] = (Get-FileHash -LiteralPath $scenarioPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $request = @{
        model=$Model;max_tokens=$MaxTokens;stream=$true
        thinking=@{type='adaptive'};output_config=@{effort='medium'}
        system=@(@{type='text';text=$context;cache_control=@{type='ephemeral'}})
        messages=@(@{role='user';content=$scenario.questions[0]})
    }
    if (-not $RunDirectory) { throw 'RUN_DIRECTORY_REQUIRED' }
    $resultDirectory = [IO.Path]::GetFullPath($RunDirectory)
    $allowedRoot = [IO.Path]::GetFullPath((Join-Path $root '验证结果')) + [IO.Path]::DirectorySeparatorChar
    if (-not $resultDirectory.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'RUN_DIRECTORY_OUTSIDE_PROJECT_RESULTS' }
    if ($ValidateOnly) {
        Write-Output (@{status='SHAPE_READY';model=$Model;requests=5;max_tokens=$MaxTokens;thinking=$request.thinking;output_config=$request.output_config;stream=$request.stream;sourceHashes=$sourceHashes;systemCharacters=$context.Length;pricing=$pricing[$Model]} | ConvertTo-Json -Depth 10)
        return
    }
    [void][IO.Directory]::CreateDirectory($resultDirectory)
} elseif ($ReplayResult) {
    $request = ([IO.File]::ReadAllText($ReplayResult,[Text.Encoding]::UTF8) | ConvertFrom-Json -AsHashtable).request
    $request.max_tokens = $MaxTokens
} else {
    $requestJson = & $python -c 'import json,sys; sys.path.insert(0,sys.argv[1]); import lab; print(json.dumps(lab.case_request(sys.argv[2])))' (Join-Path $PSScriptRoot 'aca-litellm') $Case
    if ($LASTEXITCODE -ne 0) { throw 'REQUEST_GENERATION_FAILED' }
    $request = $requestJson | ConvertFrom-Json -AsHashtable
}
$request.model = $Model
$master = $env:CLAUDE_GATEWAY_KEY
if ([string]::IsNullOrWhiteSpace($master)) { throw 'GATEWAY_SECRET_MISSING' }
$client = [Net.Http.HttpClient]::new()
$client.Timeout = [TimeSpan]::FromSeconds(120)

function Update-LabStreamContent {
    param([System.Collections.IDictionary]$Block, [System.Collections.IDictionary]$Delta)
    switch ($Delta.type) {
        'text_delta' { $Block.text += $Delta.text }
        'thinking_delta' { $Block.thinking += $Delta.thinking }
        'signature_delta' { $Block.signature += $Delta.signature }
        'input_json_delta' { $Block['_partial_json'] += $Delta.partial_json }
        'citations_delta' { $Block.citations = @($Block.citations) + @($Delta.citation) }
        default { throw ('UNSUPPORTED_CONTENT_DELTA:' + $Delta.type) }
    }
}

function Send-LabRequest {
    param([hashtable]$Payload, [string]$RecordLabel)
    if ($RecordLabel -notmatch '^[a-z0-9-]+$') { throw 'INVALID_RESULT_LABEL' }
    $path = Join-Path $resultDirectory ('ACA_HTTP_' + $RecordLabel + '.json')
    if (Test-Path -LiteralPath $path) { throw 'EXISTING_RESULT_NOT_OVERWRITTEN' }
    $attemptLimit = if ($isSequenceCase) { $sequenceAttemptLimit } else { 45 }
    if (@(Get-ChildItem -LiteralPath $resultDirectory -Filter 'ACA_HTTP_*.json' -File).Count -ge $attemptLimit) { throw 'HTTP_ATTEMPT_BUDGET_REACHED' }
    $body = $Payload | ConvertTo-Json -Depth 40 -Compress
    $bodyBytes = [Text.Encoding]::UTF8.GetByteCount($body)
    $bodyLimit = if ($isSequenceCase) { 60000 } else { 14000 }
    if ($bodyBytes -gt $bodyLimit -or $Payload.max_tokens -gt 4096) { throw 'REQUEST_COST_BOUND_EXCEEDED' }
    $maximumRequestCost = ($bodyBytes * 10 + $Payload.max_tokens * 40) / 1000000
    if ($isSequenceCase) {
        $rates = $pricing[$Payload.model]
        $maximumRequestCost = (($bodyBytes + 10000) * $rates.write + $Payload.max_tokens * $rates.output) / 1000000
        $spent = $priorReserve
        foreach ($file in Get-ChildItem -LiteralPath $resultDirectory -Filter 'ACA_HTTP_*.json' -File) {
            $prior = [IO.File]::ReadAllText($file.FullName,[Text.Encoding]::UTF8) | ConvertFrom-Json -AsHashtable
            $cost = Get-LabUsageCost -Usage $prior.response.usage -ModelName $prior.request.model
            if ($null -ne $cost) { $spent += $cost } else { $spent += $prior.maximumRequestCostUsd }
        }
    } else {
        $spent = 0.50
        foreach ($file in Get-ChildItem -LiteralPath $resultDirectory -Filter 'ACA_HTTP_*.json' -File) {
            $usage = ([IO.File]::ReadAllText($file.FullName,[Text.Encoding]::UTF8) | ConvertFrom-Json -AsHashtable).response.usage
            if ($usage) { $spent += ($usage.input_tokens * 8 + $usage.cache_creation_input_tokens * 10 + $usage.cache_read_input_tokens * 0.4 + $usage.output_tokens * 40) / 1000000 }
            else { $spent += 0.31 }
        }
    }
    if ($spent + $maximumRequestCost -gt $budgetLimit) { throw 'MODEL_COST_BUDGET_REACHED' }
    $message = [Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Post, $GatewayUrl.TrimEnd('/') + '/v1/messages')
    $message.Headers.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $master)
    $message.Headers.Add('anthropic-version', '2023-06-01')
    $message.Content = [Net.Http.StringContent]::new($body, [Text.Encoding]::UTF8, 'application/json')
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $record = [ordered]@{ label=$RecordLabel; case=$Case; captured=(Get-Date -Format o); route='WINDOWS_HTTPS_LITELLM'; request=($body | ConvertFrom-Json -AsHashtable); status='IN_PROGRESS'; maximumRequestCostUsd=$maximumRequestCost }
    if ($isSequenceCase) {
        $record.sourceHashes = $sourceHashes
        $record.pricingUsdPerMillionTokens = $pricing[$Payload.model]
        $record.pricingSource = 'https://platform.claude.com/docs/en/about-claude/pricing#claude-in-microsoft-foundry-pricing'
        $record.priorWorkBudgetReserveUsd = $priorReserve
        $record.budgetLimitUsd = $budgetLimit
    }
    if ($Case -eq 'matrix') {
        $record.matrixCaseId = $CaseId
        $record.matrixCase = $selected
    }
    $response = $null
    $cancellation = [Threading.CancellationTokenSource]::new([TimeSpan]::FromSeconds(120))
    try {
        $response = $client.SendAsync($message, [Net.Http.HttpCompletionOption]::ResponseHeadersRead, $cancellation.Token).GetAwaiter().GetResult()
        $record.responseHeadersSeconds = $watch.Elapsed.TotalSeconds
        $record.httpStatus = [int]$response.StatusCode
        $record.headers = @{}
        foreach ($header in @('request-id','apim-request-id','x-litellm-call-id','retry-after')) {
            if ($response.Headers.Contains($header)) { $record.headers[$header] = @($response.Headers.GetValues($header)) }
        }
        if ($Payload.stream -and $response.IsSuccessStatusCode) {
            $stream = $response.Content.ReadAsStream()
            $firstByte = [byte[]]::new(1)
            $firstRead = $stream.ReadAsync($firstByte, 0, 1, $cancellation.Token).GetAwaiter().GetResult()
            if ($firstRead -ne 1) { throw 'EMPTY_RESPONSE_STREAM' }
            $record.firstBodyByteSeconds = $watch.Elapsed.TotalSeconds
            $linePrefix = [Text.Encoding]::UTF8.GetString($firstByte)
            $reader = [IO.StreamReader]::new($stream)
            $events = [Collections.Generic.List[object]]::new()
            $wireLines = [Collections.Generic.List[string]]::new()
            $eventTimings = [Collections.Generic.List[object]]::new()
            $parsed = @{content=@();usage=@{}}
            $blocks = @{}
            $record.messageStopReceived = $false
            try {
                while (($line = $reader.ReadLineAsync($cancellation.Token).GetAwaiter().GetResult()) -ne $null) {
                    if ($linePrefix) { $line = $linePrefix + $line; $linePrefix = '' }
                    $wireLines.Add($line)
                    if (-not $line.StartsWith('data:')) { continue }
                    $data = $line.Substring(5).Trim()
                    if (-not $data -or $data -eq '[DONE]') { continue }
                    $event = $data | ConvertFrom-Json -AsHashtable
                    $events.Add($event)
                    if (-not $record.Contains('firstSseEventSeconds')) { $record.firstSseEventSeconds = $watch.Elapsed.TotalSeconds }
                    $eventTimings.Add(@{event=$events.Count-1;type=$event.type;index=$event.index;deltaType=$event.delta.type;elapsedSeconds=$watch.Elapsed.TotalSeconds})
                    switch ($event.type) {
                        'message_start' { $parsed = $event.message | ConvertTo-Json -Depth 50 -Compress | ConvertFrom-Json -AsHashtable }
                        'content_block_start' {
                            $blocks[[int]$event.index] = $event.content_block | ConvertTo-Json -Depth 50 -Compress | ConvertFrom-Json -AsHashtable
                            if ($event.content_block.type -eq 'thinking' -and -not $record.Contains('firstThinkingEventSeconds')) { $record.firstThinkingEventSeconds = $watch.Elapsed.TotalSeconds }
                        }
                        'content_block_delta' {
                            if ($event.delta.type -eq 'signature_delta' -and -not $record.Contains('firstSignatureSeconds')) { $record.firstSignatureSeconds = $watch.Elapsed.TotalSeconds }
                            if ($event.delta.type -eq 'text_delta') {
                                if (-not $record.Contains('firstVisibleTextSeconds') -and $event.delta.text) { $record.firstVisibleTextSeconds = $watch.Elapsed.TotalSeconds }
                            }
                            Update-LabStreamContent -Block $blocks[[int]$event.index] -Delta $event.delta
                        }
                        'content_block_stop' {
                            $block = $blocks[[int]$event.index]
                            if ($block.Contains('_partial_json')) {
                                $block.input = $block['_partial_json'] | ConvertFrom-Json -AsHashtable
                                $block.Remove('_partial_json')
                            }
                        }
                        'message_delta' {
                            foreach ($key in $event.delta.Keys) { $parsed[$key] = $event.delta[$key] }
                            foreach ($key in $event.usage.Keys) { $parsed.usage[$key] = $event.usage[$key] }
                        }
                        'message_stop' { $record.messageStopReceived = $true; $record.messageStopSeconds = $watch.Elapsed.TotalSeconds }
                        'error' { $parsed.error = $event.error }
                    }
                }
            } finally {
                $reader.Dispose()
                $parsed.content = @($blocks.Keys | Sort-Object | ForEach-Object { $blocks[$_] })
                $record.sseEvents = @($events)
                $record.sseWireLines = @($wireLines)
                $record.eventTimings = @($eventTimings)
                $record.response = $parsed
            }
        } else {
            $content = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
            try { $record.response = $content | ConvertFrom-Json -AsHashtable } catch { $record.response = @{unparsedBody=$content} }
        }
        $record.status = 'CAPTURED'
    } catch {
        $record.status = 'TRANSPORT_OR_PARSER_ERROR'
        $record.errorType = $_.Exception.GetType().FullName
        throw
    } finally {
        $watch.Stop()
        $record.elapsedSeconds = $watch.Elapsed.TotalSeconds
        if ($isSequenceCase) {
            $record.estimatedModelCostUsd = Get-LabUsageCost -Usage $record.response.usage -ModelName $Payload.model
        }
        [IO.File]::WriteAllText($path, ($record | ConvertTo-Json -Depth 50), [Text.UTF8Encoding]::new($false))
        if ($null -ne $response) { $response.Dispose() }
        $message.Dispose()
        $cancellation.Dispose()
    }
    $summary = @{label=$RecordLabel;httpStatus=$record.httpStatus;elapsedSeconds=$record.elapsedSeconds;firstVisibleTextSeconds=$record.firstVisibleTextSeconds;messageStopReceived=$record.messageStopReceived;stopReason=$record.response.stop_reason;usage=$record.response.usage;error=$record.response.error;evidence=$path}
    Write-Host ($summary | ConvertTo-Json -Depth 8 -Compress)
    return $record
}

try {
    if ($isSequenceCase) {
        for ($turn = 1; $turn -le 5; $turn++) {
            $result = Send-LabRequest -Payload $request -RecordLabel ($Label + '-turn-' + $turn)
            if ($result.httpStatus -ne 200 -or -not $result.messageStopReceived -or $result.response.stop_reason -ne 'end_turn' -or $result.response.error -or $null -eq $result.firstVisibleTextSeconds) { throw ('FIVE_TURN_INCOMPLETE:' + $turn) }
            if ($null -eq $result.estimatedModelCostUsd) { throw 'USAGE_INCOMPLETE' }
            if ($Case -eq 'matrix' -and $selected.thinking -ne 'adaptive') {
                if (@($result.response.content | Where-Object { $_.type -in @('thinking','redacted_thinking') }).Count -gt 0 -or $result.response.usage.output_tokens_details.thinking_tokens -gt 0) { throw 'REQUESTED_THINKING_OFF_NOT_EFFECTIVE' }
            }
            foreach ($block in $result.response.content) {
                if ($block.type -eq 'thinking' -and [string]::IsNullOrEmpty($block.signature)) { throw 'THINKING_SIGNATURE_MISSING' }
                if ($block.type -notin @('text','thinking','redacted_thinking')) { throw ('UNEXPECTED_CONTENT_BLOCK:' + $block.type) }
            }
            if ($turn -lt 5) {
                $request.messages += @{role='assistant';content=$result.response.content}
                $request.messages += @{role='user';content=$scenario.questions[$turn]}
            }
        }
        Write-Host ('FIVE_TURN_PASS=' + $Model)
        return
    }
    $result = Send-LabRequest -Payload $request -RecordLabel $Label
    $expectedStatus = if ($Case -eq 'thinking-invalid') { 400 } else { 200 }
    $expectedStop = if ($Case -eq 'tools') { 'tool_use' } elseif ($Case -eq 'budget-low') { 'max_tokens' } else { 'end_turn' }
    if ($result.httpStatus -ne $expectedStatus) { throw 'UNEXPECTED_HTTP_STATUS' }
    if ($expectedStatus -eq 200 -and $result.response.stop_reason -ne $expectedStop) { throw 'UNEXPECTED_STOP_REASON' }
    if ($Case -eq 'stream' -and -not $result.messageStopReceived) { throw 'SSE_INCOMPLETE' }
    if ($Case -in @('multi-turn','tools')) {
        $request.messages += @{role='assistant';content=$result.response.content}
        if ($Case -eq 'multi-turn') {
            $request.messages += @{role='user';content='Which exact function computes the hashes? Answer with its name and one sentence.'}
        } else {
            $toolResults = @()
            foreach ($call in @($result.response.content | Where-Object { $_.type -eq 'tool_use' })) {
                if ($call.name -ne 'inspect_source_file' -or $call.input.filename -ne 'trace_hook.py') { throw 'TOOL_OUT_OF_SCOPE' }
                $sourcePath = Join-Path $PSScriptRoot 'aca-litellm\trace_hook.py'
                $bytes = [IO.File]::ReadAllBytes($sourcePath)
                $facts = @{sha256=(Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant();bytes=$bytes.Length;lines=[IO.File]::ReadAllLines($sourcePath).Length}
                $toolResults += @{type='tool_result';tool_use_id=$call.id;content=($facts | ConvertTo-Json -Compress)}
            }
            $request.messages += @{role='user';content=$toolResults}
        }
        $followup = Send-LabRequest -Payload $request -RecordLabel ($Label + '-followup')
        if ($followup.httpStatus -ne 200 -or $followup.response.stop_reason -ne 'end_turn') { throw 'FOLLOWUP_INCOMPLETE' }
    }
    Write-Host ('CASE_PASS=' + $Label)
} finally {
    $client.Dispose()
    $master = $null
}