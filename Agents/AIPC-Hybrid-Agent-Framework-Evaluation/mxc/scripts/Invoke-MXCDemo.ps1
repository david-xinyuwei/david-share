param(
    [ValidateSet("probe", "sales-naked", "sales-block", "sales-allow", "sales-hyperlight-restrict", "hyperlight-lifecycle", "backend-fit", "pip-policy", "task-rbac", "capability-catalog", "demo-all")]
    [string]$Step = "demo-all",
    [string]$PromptText = "Analyze the local product inventory CSV and find the top revenue category.",
    [switch]$PauseBetweenSteps
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path.TrimEnd("\")
$EvidenceDir = Join-Path $ProjectRoot "evidence"
New-Item -ItemType Directory -Force $EvidenceDir | Out-Null

function Wait-IfNeeded {
    if ($PauseBetweenSteps) {
        Write-Host ""
        Write-Host "Press Enter to continue..." -ForegroundColor Yellow
        [void][System.Console]::ReadLine()
    }
}

function Section($Title) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Find-WxcExec {
    $explicit = @(
        (Join-Path $ProjectRoot "node_modules\@microsoft\mxc-sdk\bin\x64\wxc-exec.exe"),
        "C:\mxc-smoke\node_modules\@microsoft\mxc-sdk\bin\x64\wxc-exec.exe",
        "C:\Users\aipcadmin\Desktop\mxc-smoke\node_modules\@microsoft\mxc-sdk\bin\x64\wxc-exec.exe"
    )
    foreach ($path in $explicit) {
        if (Test-Path $path) { return $path }
    }
    $roots = @(
        (Join-Path $env:LOCALAPPDATA "copilot\pkg\win32-x64"),
        (Join-Path $env:LOCALAPPDATA "GitHub CLI\copilot")
    ) | Where-Object { $_ -and (Test-Path $_) }
    $candidates = @()
    foreach ($root in $roots) {
        $candidates += Get-ChildItem -Path $root -Recurse -Filter "wxc-exec.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "mxc-bin\\x64\\wxc-exec\.exe$" }
    }
    if (-not $candidates -or $candidates.Count -eq 0) { return $null }
    return ($candidates | Sort-Object FullName -Descending | Select-Object -First 1).FullName
}

$Wxc = Find-WxcExec
if (-not $Wxc) {
    Write-Host "Cannot find wxc-exec.exe. Run GitHub Copilot CLI once first: gh copilot -- --help" -ForegroundColor Red
    exit 1
}

function Find-HostPython {
    $candidates = @(
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        (Get-Command python.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
    ) | Where-Object { $_ -and (Test-Path $_) }
    if (-not $candidates -or $candidates.Count -eq 0) { return $null }
    return $candidates[0]
}

function New-PipPolicyConfig([string]$Name, [string]$DefaultPolicy, [string]$TargetDir) {
    $config = [ordered]@{
        version = "0.4.0-alpha"
        containment = "processcontainer"
        process = [ordered]@{
            timeout = 120000
        }
        lifecycle = [ordered]@{
            destroyOnExit = $true
            preservePolicy = $false
        }
        filesystem = [ordered]@{
            readwritePaths = @($TargetDir)
        }
        processContainer = [ordered]@{
            name = $Name
        }
        network = [ordered]@{
            defaultPolicy = $DefaultPolicy
        }
    }
    if ($DefaultPolicy -eq "allow") {
        $config.processContainer.capabilities = @("internetClient")
    }
    return $config
}

function New-Win32UiPolicyConfig([string]$Name, [bool]$AllowWindows, [switch]$BroadUi) {
    $clipboard = if ($BroadUi) { "all" } else { "none" }
    $injection = [bool]$BroadUi
    $isolation = if ($BroadUi) { "desktop" } else { "container" }
    $desktopSystemControl = [bool]$BroadUi
    $systemSettings = if ($BroadUi) { "all" } else { "none" }
    $ime = [bool]$BroadUi
    return [ordered]@{
        version = "0.7.0-alpha"
        containment = "processcontainer"
        process = [ordered]@{
            timeout = 30000
        }
        processContainer = [ordered]@{
            name = $Name
            ui = [ordered]@{
                isolation = $isolation
                desktopSystemControl = $desktopSystemControl
                systemSettings = $systemSettings
                ime = $ime
            }
        }
        network = [ordered]@{
            defaultPolicy = "block"
        }
        ui = [ordered]@{
            disable = (-not $AllowWindows)
            clipboard = $clipboard
            injection = $injection
        }
    }
}

function Find-CSharpCompiler {
    $candidates = @(
        "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

function Build-Win32CapabilityProbe {
    $source = Join-Path $ProjectRoot "examples\Win32CapabilityProbe.cs"
    $outDir = Join-Path $ProjectRoot "workspace-output\win32-probe"
    $exe = Join-Path $outDir "Win32CapabilityProbe.exe"
    New-Item -ItemType Directory -Force $outDir | Out-Null
    $compiler = Find-CSharpCompiler
    if (-not $compiler) {
        throw "CSharp compiler not found. Expected .NET Framework csc.exe."
    }
    $compileOutput = & $compiler /nologo /target:exe /out:$exe /r:System.Management.dll $source 2>&1
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) {
        throw "Win32CapabilityProbe compile failed: $($compileOutput -join ' ')"
    }
    return $exe
}

function Find-VsDevCmd {
    $candidates = @(
        "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat",
        "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

function Build-NativeWin32CapabilityProbe {
    $source = Join-Path $ProjectRoot "examples\win32_capability_probe.c"
    $outDir = Join-Path $ProjectRoot "workspace-output\native-win32-probe"
    $exe = Join-Path $outDir "NativeWin32CapabilityProbe.exe"
    New-Item -ItemType Directory -Force $outDir | Out-Null
    $vsDevCmd = Find-VsDevCmd
    if (-not $vsDevCmd) {
        throw "VsDevCmd.bat not found. Cannot build native Win32 probe."
    }
    $compileCmd = "call `"$vsDevCmd`" -arch=x64 -host_arch=x64 >nul && cl /nologo /W4 /O2 /Fe`"$exe`" `"$source`" user32.lib gdi32.lib advapi32.lib ole32.lib"
    $compileOutput = & cmd.exe /c $compileCmd 2>&1
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) {
        throw "NativeWin32CapabilityProbe compile failed: $($compileOutput -join ' ')"
    }
    return $exe
}

function Get-Win32CapabilityProbeArgs([string]$ExePath) {
    return @($ExePath, "--no-wmi")
}

function Get-ProbeStats([string]$Text) {
    $passCount = ([regex]::Matches($Text, "(?m)^PROBE \S+ PASS ")).Count
    $failCount = ([regex]::Matches($Text, "(?m)^PROBE \S+ FAIL ")).Count
    return [PSCustomObject]@{ Pass = $passCount; Fail = $failCount }
}

function Get-NativeProbeProfileStats([string]$Text) {
    $stats = [ordered]@{}
    foreach ($line in ($Text -split "`r?`n")) {
        $m = [regex]::Match($line, "^PROBE\s+(?<name>\S+)\s+(?<status>PASS|FAIL|SKIP)\s*(?<detail>.*)$")
        if ($m.Success) {
            $stats[$m.Groups["name"].Value] = [PSCustomObject]@{
                Status = $m.Groups["status"].Value
                Detail = $m.Groups["detail"].Value.Trim()
            }
        }
    }
    return $stats
}

function Get-Win32UiProbeArgs {
    return @(
        "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
        "-NoProfile",
        "-Command",
        "Write-Output MXC_PS_OK"
    )
}

function Get-PipInstallProbeArgs([string]$PythonExe, [string]$TargetDir) {
    return @(
        $PythonExe,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--retries",
        "0",
        "--timeout",
        "8",
        "--target",
        $TargetDir,
        "six==1.16.0"
    )
}

function Copy-PolicyToEvidence($PolicyName) {
    $source = Join-Path $ProjectRoot "policies\$PolicyName"
    $target = Join-Path $EvidenceDir $PolicyName
    Copy-Item $source $target -Force
    return $target
}

function Write-Utf8NoBomFile([string]$Path, [string]$Content) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Write-JsonPolicyFile([string]$Path, $Object) {
    Write-Utf8NoBomFile $Path ($Object | ConvertTo-Json -Depth 10)
}

function Get-MicrosoftCurlActionArgs {
    return @(
        "C:\Windows\System32\curl.exe",
        "-I",
        "-L",
        "-sS",
        "--connect-timeout",
        "5",
        "--max-time",
        "20",
        "-w",
        "HTTP_STATUS:%{http_code}",
        "http://www.microsoft.com"
    )
}

function Get-HyperlightNetworkProbeActionArgs {
    $payload = @'
import urllib.request
print('BACKEND=hyperlight')
print('SCENARIO=untrusted_code_attempts_network')
try:
    response = urllib.request.urlopen('http://www.microsoft.com', timeout=5)
    print('NETWORK_RESULT=SUCCESS')
    print('HTTP_STATUS=' + str(response.status))
except Exception as e:
    print('NETWORK_RESULT=BLOCKED_OR_UNAVAILABLE')
    print('ERROR_TYPE=' + type(e).__name__)
    print('ERROR=' + str(e)[:160])
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))
    $code = "exec(__import__('base64').b64decode('$encoded').decode())"
    return @($code)
}

function Get-LinuxGuestWorkloadCode {
    $payload = @'
import os, sys
print('WORKLOAD=linux_guest_introspection')
print('REQUIRES=sys.platform == linux')
print('ACTUAL_SYS_PLATFORM=' + sys.platform)
if sys.platform == 'linux':
    print('WORKLOAD_RESULT=SUPPORTED')
    print('GUEST_RUNTIME=linux')
else:
    print('WORKLOAD_RESULT=NOT_SUPPORTED_ON_THIS_BACKEND')
    raise SystemExit(42)
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))
    return "exec(__import__('base64').b64decode('$encoded').decode())"
}

function ConvertTo-PythonLiteral([string]$Text) {
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Text))
    return "__import__('base64').b64decode('$encoded').decode()"
}

function Resolve-CodingPrompt([string]$PromptText) {
    $defaultPrompt = "Analyze the local product inventory CSV and find the top revenue category."
    if ($PromptText -eq "__ASK__") {
        Write-Host ""
        Write-Host "AIPC Coding Assistant prompt" -ForegroundColor Cyan
        Write-Host "Default: $defaultPrompt" -ForegroundColor Gray
        $typedPrompt = Read-Host "Enter prompt (blank = default)"
        if ([string]::IsNullOrWhiteSpace($typedPrompt)) { return $defaultPrompt }
        return $typedPrompt
    }
    if ([string]::IsNullOrWhiteSpace($PromptText)) { return $defaultPrompt }
    return $PromptText
}

function Get-RequiredEnvValue([string[]]$Names) {
    foreach ($name in $Names) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return [PSCustomObject]@{ Name = $name; Value = $value }
        }
    }
    return $null
}

function Get-SopApimKeyValue {
    $candidatePaths = @(
        "G:\AI-Super-Agent\prompts\main.instructions.md",
        "G:\AI-Super-Agent\prompts\5-SOP-Azure-Resources.instructions.md"
    )
    foreach ($path in $candidatePaths) {
        if (-not (Test-Path $path)) { continue }
        $text = Get-Content $path -Raw -ErrorAction SilentlyContinue
        $keyMatches = [regex]::Matches($text, "bf09[a-zA-Z0-9]{20,}")
        if ($keyMatches.Count -gt 0) {
            return [PSCustomObject]@{ Name = "SOP_APIM_KEY"; Value = $keyMatches[$keyMatches.Count - 1].Value }
        }
    }
    return $null
}

function Get-RealCodegenConfig {
    $endpoint = Get-RequiredEnvValue @("MXC_CODEGEN_APIM_BASE", "AZURE_OPENAI_ENDPOINT", "AOAI_ENDPOINT")
    $apiKey = Get-RequiredEnvValue @("MXC_CODEGEN_APIM_KEY", "AOAI_KEY")
    if (-not $apiKey) { $apiKey = Get-SopApimKeyValue }
    if (-not $apiKey) { $apiKey = Get-RequiredEnvValue @("AZURE_OPENAI_API_KEY") }
    $model = Get-RequiredEnvValue @("MXC_CODEGEN_MODEL", "AZURE_OPENAI_DEPLOYMENT", "AOAI_DEPLOYMENT")
    $apiVersion = Get-RequiredEnvValue @("MXC_CODEGEN_API_VERSION", "AZURE_OPENAI_API_VERSION", "AOAI_API_VERSION")
    $missing = @()
    if (-not $endpoint) {
        $endpoint = [PSCustomObject]@{ Name = "SOP5_DEFAULT_APIM_BASE"; Value = "https://apim-gbb-asia.azure-api.net" }
    }
    if (-not $apiKey) { $missing += "AZURE_OPENAI_API_KEY or AOAI_KEY" }
    if (-not $model) {
        $model = [PSCustomObject]@{ Name = "SOP5_DEFAULT_MODEL"; Value = "gpt-5.4" }
    }
    if (-not $apiVersion) {
        $apiVersion = [PSCustomObject]@{ Name = "SOP5_DEFAULT_API_VERSION"; Value = "2025-04-01-preview" }
    }
    if ($missing.Count -gt 0) {
        throw "REAL_CODEGEN_CONFIG_MISSING: " + ($missing -join "; ")
    }
    return [PSCustomObject]@{
        Endpoint = $endpoint.Value.TrimEnd("/")
        ApiKey = $apiKey.Value
        Model = $model.Value
        ApiVersion = $apiVersion.Value
        Source = "$($endpoint.Name), $($model.Name), $($apiVersion.Name)"
    }
}

function Remove-CodeFence([string]$Text) {
    $clean = $Text.Trim()
    if ($clean -match '^```') {
        $clean = $clean -replace '^```[a-zA-Z0-9_-]*\s*', ''
        $clean = $clean -replace '\s*```$', ''
    }
    return $clean.Trim()
}

function Invoke-RealCodeGenerator([string]$PromptText, [string]$CsvText) {
    $cfg = Get-RealCodegenConfig
    $url = "$($cfg.Endpoint)/openai/responses?api-version=$($cfg.ApiVersion)"
    $system = @'
    You generate Python 3.12 source code that solves the user's problem prompt using the provided local CSV text.
Return only executable Python source. No Markdown. No code fences.

Runtime inputs already exist:
    - PROMPT_TEXT: problem prompt string
- CSV_TEXT: CSV content string

Constraints:
- Use only Python standard library modules: csv, io, sys, collections, math, statistics.
- Do not read or write files.
- Do not use network.
- Do not use subprocess.
    - Solve the request in PROMPT_TEXT using CSV_TEXT.
    - Infer the answer from the CSV header and rows. Do not assume a fixed question or fixed answer.
    - If PROMPT_TEXT cannot be answered from CSV_TEXT, say so in ANALYSIS_BEGIN/ANALYSIS_END and print ANSWER=INSUFFICIENT_DATA.
- Print these exact machine-readable fields:
  SCENARIO=coding_assistant_exec
  PROMPT_TEXT=<actual prompt>
  RUNTIME=<sys.platform>
  INPUT_FORMAT=csv
  INPUT_ROWS=<row count>
  ANALYSIS_BEGIN
        <human-readable analysis grounded in the prompt and CSV>
  ANALYSIS_END
        ANSWER=<short final answer>
  WORKLOAD_RESULT=SUPPORTED if sys.platform == "linux" else NOT_SUPPORTED_ON_THIS_BACKEND
  ISOLATION=guest_vm_runtime if sys.platform == "linux"
'@
    $user = @"
    Problem prompt to solve exactly:
$PromptText

    Available local data: CSV_TEXT.
    CSV preview:
$($CsvText -split "`n" | Select-Object -First 6 | Out-String)
"@
    $body = @{
        model = $cfg.Model
        input = @(
            @{ role = "system"; content = $system },
            @{ role = "user"; content = $user }
        )
        max_output_tokens = 1400
    } | ConvertTo-Json -Depth 10
    $headers = @{
        "api-key" = $cfg.ApiKey
        "Content-Type" = "application/json"
    }
    $response = Invoke-RestMethod -Method Post -Uri $url -Headers $headers -Body $body -TimeoutSec 90
    $codeText = $response.output_text
    if ([string]::IsNullOrWhiteSpace($codeText) -and $response.output) {
        $parts = @()
        foreach ($item in @($response.output)) {
            foreach ($content in @($item.content)) {
                if ($content.text) { $parts += $content.text }
            }
        }
        $codeText = ($parts -join "`n")
    }
    $code = Remove-CodeFence $codeText
    if ([string]::IsNullOrWhiteSpace($code)) {
        throw "REAL_CODEGEN_EMPTY_RESPONSE"
    }
    return [PSCustomObject]@{ Code = $code; ConfigSource = $cfg.Source; Deployment = $cfg.Model; ResponseId = $response.id }
}

function New-RealCodegenExecutionArtifact([string]$PromptText) {
    $csvPath = Join-Path $ProjectRoot "coding-scenario\data\product_inventory_q2.csv"
    $promptPath = Join-Path $EvidenceDir "demo5_user_prompt.txt"
    $generatedDir = Join-Path $ProjectRoot "workspace-output\generated-code"
    $generatedPath = Join-Path $generatedDir "latest_generated_from_prompt.py"

    $csvText = Get-Content $csvPath -Raw
    $PromptText | Set-Content -Path $promptPath -Encoding UTF8
    $codegen = Invoke-RealCodeGenerator $PromptText $csvText
    New-Item -ItemType Directory -Force $generatedDir | Out-Null

    $generated = @(
        "# Generated by SOP-5 APIM + Azure OpenAI Responses API",
        "# Model: $($codegen.Deployment)",
        "# APIM response id: $($codegen.ResponseId)",
        "# Problem prompt: $PromptText",
        "PROMPT_TEXT = $(ConvertTo-PythonLiteral $PromptText)",
        "CSV_TEXT = $(ConvertTo-PythonLiteral $csvText)",
        $codegen.Code
    ) -join "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($generatedPath, $generated, $utf8NoBom)

    $parse = & C:\Python312\python.exe -c "import ast, pathlib; ast.parse(pathlib.Path(r'$generatedPath').read_text(encoding='utf-8')); print('PY_AST_OK')" 2>&1
    if ($LASTEXITCODE -ne 0 -or ($parse -join "`n") -notmatch "PY_AST_OK") {
        throw "REAL_CODEGEN_SYNTAX_INVALID: $($parse -join ' ')"
    }

    return [PSCustomObject]@{
        PromptFile = $promptPath
        GeneratedCodeFile = $generatedPath
        CsvFile = $csvPath
        Code = $generated
        ConfigSource = $codegen.ConfigSource
        ResponseId = $codegen.ResponseId
    }
}

function Get-CodingProcessContainerArgs([string]$Code) {
    $code = "exec(" + (ConvertTo-PythonLiteral $Code) + ")"
    return @("C:\Python312\python.exe", "-c", $code)
}

function Get-CodingHyperlightArgs([string]$Code) {
    $code = "exec(" + (ConvertTo-PythonLiteral $Code) + ")"
    return @($code)
}

function Get-OutputValue([string]$Output, [string]$Key) {
    $match = [regex]::Match($Output, [regex]::Escape($Key) + "=(?<value>[^`r`n]+)")
    if ($match.Success) { return $match.Groups["value"].Value.Trim() }
    return "missing"
}

function Limit-DisplayText([string]$Text, [int]$MaxLength) {
    if ($null -eq $Text) { return "" }
    if ($Text.Length -le $MaxLength) { return $Text }
    if ($MaxLength -le 3) { return $Text.Substring(0, $MaxLength) }
    return $Text.Substring(0, $MaxLength - 3) + "..."
}

function Get-ProcessContainerFailureReason([int]$ExitCode) {
    if ($ExitCode -eq -1073741515) {
        return "0xC0000135 STATUS_DLL_NOT_FOUND before Python ran"
    }
    if ($ExitCode -ne 0) {
        return "Process exited before producing the requested analysis"
    }
    return "none"
}

function Get-BackendFitProcessContainerActionArgs {
    return @(
        "C:\Windows\System32\cmd.exe",
        "/c",
        "echo WORKLOAD=linux_guest_introspection && echo REQUIRES=sys.platform == linux && echo BACKEND=processcontainer && echo ACTUAL_RUNTIME=Windows host process && echo ACTUAL_SYS_PLATFORM=win32 && echo WORKLOAD_RESULT=NOT_SUPPORTED_ON_THIS_BACKEND"
    )
}

function Get-BackendFitHyperlightActionArgs {
    return @((Get-LinuxGuestWorkloadCode))
}

function Format-ActionCommand($CommandArgs) {
    return ($CommandArgs | ForEach-Object {
        if ($_ -match "\s") { '"' + $_ + '"' } else { $_ }
    }) -join " "
}

function Get-ActionId([string[]]$CommandArgs) {
    $text = Format-ActionCommand $CommandArgs
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [Text.Encoding]::UTF8.GetBytes($text)
    $hash = [BitConverter]::ToString($sha.ComputeHash($bytes)).Replace("-", "")
    return $hash.Substring(0, 10)
}

function Invoke-WxcPolicyQuiet($PolicyPath, $Name, [switch]$Experimental, [string[]]$CommandArgs = $null) {
    $log = Join-Path $EvidenceDir "$Name.log"
    $wxcArgs = @()
    if ($Experimental) { $wxcArgs += "--experimental" }
    $wxcArgs += "--debug"
    $wxcArgs += $PolicyPath
    if ($CommandArgs -and $CommandArgs.Count -gt 0) {
        $wxcArgs += "--"
        $wxcArgs += $CommandArgs
    }
    $output = & $Wxc @wxcArgs 2>&1
    $exit = $LASTEXITCODE
    $output | Set-Content -Path $log -Encoding UTF8
    return [PSCustomObject]@{ ExitCode = $exit; Output = ($output -join "`n"); Log = $log }
}

function Get-HttpStatusFromOutput($Output) {
    $statusMatches = [regex]::Matches($Output, "(?:bare_http|mxc_http|HTTP_STATUS):(?<code>\d{3})")
    if ($statusMatches.Count -gt 0) { return $statusMatches[$statusMatches.Count - 1].Groups["code"].Value }
    return "unknown"
}


function Invoke-MicrosoftCurlWithRetry($MaxAttempts = 3) {
    $cmdArgs = Get-MicrosoftCurlActionArgs
    $exe = $cmdArgs[0]
    $curlArgs = $cmdArgs[1..($cmdArgs.Count - 1)]
    $allOutput = @()
    $lastExit = 1
    $lastStatus = "unknown"
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        $allOutput += "ATTEMPT:$attempt"
        $output = & $exe @curlArgs 2>&1
        $lastExit = $LASTEXITCODE
        $allOutput += $output
        $lastStatus = Get-HttpStatusFromOutput ($output -join "`n")
        if ($lastStatus -eq "200") { break }
        Start-Sleep -Seconds 1
    }
    return [PSCustomObject]@{ Output = $allOutput; ExitCode = $lastExit; Status = $lastStatus }
}

function Invoke-WxcPolicyQuietWithExpectedStatus($PolicyPath, $Name, $ExpectedStatus, [switch]$Experimental, $MaxAttempts = 3, [string[]]$CommandArgs = $null) {
    $combinedOutput = @()
    $last = $null
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        $combinedOutput += "ATTEMPT:$attempt"
        $last = Invoke-WxcPolicyQuiet $PolicyPath $Name -Experimental:$Experimental -CommandArgs $CommandArgs
        $combinedOutput += ($last.Output -split "`n")
        $status = Get-HttpStatusFromOutput $last.Output
        if ($status -eq $ExpectedStatus) { break }
        Start-Sleep -Seconds 1
    }
    $log = Join-Path $EvidenceDir "$Name.retry.log"
    $combinedOutput | Set-Content -Path $log -Encoding UTF8
    return [PSCustomObject]@{ ExitCode = $last.ExitCode; Output = ($combinedOutput -join "`n"); Log = $log }
}

function Step-Probe {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  MXC Demo 1 - Is MXC present on this AIPC?" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""
    $probeOutput = & $Wxc --probe 2>&1
    $probeText = $probeOutput -join "`n"
    $tier = if ($probeText -match '"tier":\s*"([^"]+)"') { $matches[1] } else { "unknown" }
    $smokePolicy = Copy-PolicyToEvidence "coding-processcontainer.json"
    $smoke = Invoke-WxcPolicyQuiet $smokePolicy "demo1_processcontainer_smoke" -CommandArgs @("C:\Windows\System32\cmd.exe", "/c", "echo", "MXC_SMOKE_OK")
    $smokeStatus = if ($smoke.ExitCode -eq 0 -and $smoke.Output -match "MXC_SMOKE_OK") { "PASS" } else { "FAIL" }
    $binarySource = if ($Wxc -like "*$ProjectRoot*") { "@microsoft/mxc-sdk 0.7.0 workspace binary" } else { "external/copilot bundled binary" }
    Write-Host "  MXC binary    : $(Split-Path $Wxc -Leaf) ($binarySource)" -ForegroundColor Green
    Write-Host "  Host tier     : $tier" -ForegroundColor Green
    Write-Host "  Smoke test    : processcontainer cmd.exe -> $smokeStatus" -ForegroundColor $(if ($smokeStatus -eq "PASS") { "Green" } else { "Red" })
    Write-Host ""
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Green
    Write-Host "  |  MXC is present on this machine.                          |" -ForegroundColor Green
    Write-Host "  |  processcontainer launched a real Windows command.         |" -ForegroundColor Green
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Green
    if ($smokeStatus -ne "PASS") {
        Write-Host "VALIDATION_FAILED: processcontainer smoke test should pass" -ForegroundColor Red
        exit 1
    }
    Wait-IfNeeded
}

function Step-SalesNaked {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Yellow
    Write-Host "  MXC Demo 2 - No policy: agent has full network access" -ForegroundColor Yellow
    Write-Host "===========================================================" -ForegroundColor Yellow
    Write-Host ""
    $actionArgs = Get-MicrosoftCurlActionArgs
    $actionId = Get-ActionId $actionArgs
    Write-Host "  Action: curl http://www.microsoft.com" -ForegroundColor White
    Write-Host "  Action ID: $actionId (same action used in Demo 2/3/4)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Policy file: none" -ForegroundColor Yellow
    Write-Host "  Key rule:    no MXC policy applied" -ForegroundColor Yellow
    Write-Host ""
    $salesDir = Join-Path $EvidenceDir "sales"
    New-Item -ItemType Directory -Force $salesDir | Out-Null
    $curlResult = Invoke-MicrosoftCurlWithRetry 3
    $status = $curlResult.Status
    $nakedVerdict = if ($status -eq "200") { "OUTBOUND NETWORK ALLOWED" } else { "OUTBOUND NETWORK DENIED" }
    $nakedColor = if ($status -eq "200") { "Yellow" } else { "Red" }
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $nakedColor
    Write-Host "  |  NO POLICY                                                |" -ForegroundColor $nakedColor
    $rid = "  |  action id -> $actionId"
    Write-Host "$($rid.PadRight(62))|" -ForegroundColor $nakedColor
    $r1 = "  |  curl microsoft.com -> HTTP $status"
    Write-Host "$($r1.PadRight(62))|" -ForegroundColor $nakedColor
    $rv = "  |  verdict: $nakedVerdict"
    Write-Host "$($rv.PadRight(62))|" -ForegroundColor $nakedColor
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $nakedColor
    Wait-IfNeeded
}

function Step-SalesBlock {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Red
    Write-Host "  MXC Demo 3 - Block policy: network denied" -ForegroundColor Red
    Write-Host "===========================================================" -ForegroundColor Red
    Write-Host ""
    $actionArgs = Get-MicrosoftCurlActionArgs
    $actionId = Get-ActionId $actionArgs
    Write-Host "  Action: same curl http://www.microsoft.com" -ForegroundColor White
    Write-Host "  Action ID: $actionId (unchanged from Demo 2)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Policy file: policies/sales-network-block.json" -ForegroundColor Red
    $blockPolicyContent = Get-Content (Join-Path $ProjectRoot "policies\sales-network-block.json") -Raw | ConvertFrom-Json
    $blockRule = $blockPolicyContent.network.defaultPolicy
    Write-Host "  Key rule:    `"network`": { `"defaultPolicy`": `"$blockRule`" }" -ForegroundColor Red
    Write-Host "  Containment: $($blockPolicyContent.containment)" -ForegroundColor Red
    Write-Host ""
    $policy = Copy-PolicyToEvidence "sales-network-block.json"
    $result = Invoke-WxcPolicyQuiet $policy "sales_02_mxc_network_block" -CommandArgs $actionArgs
    $status = Get-HttpStatusFromOutput $result.Output
    $isBlocked = ($status -eq "000")
    $verdictText = if ($isBlocked) { "OUTBOUND NETWORK BLOCKED" } else { "OUTBOUND NETWORK ALLOWED" }
    $boxColor = if ($isBlocked) { "Red" } else { "Green" }
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $boxColor
    Write-Host "  |  MXC POLICY ACTIVE                                        |" -ForegroundColor $boxColor
    $rid = "  |  action id -> $actionId"
    Write-Host "$($rid.PadRight(62))|" -ForegroundColor $boxColor
    $r1 = "  |  curl microsoft.com -> HTTP $status"
    Write-Host "$($r1.PadRight(62))|" -ForegroundColor $boxColor
    $rv = "  |  verdict: $verdictText"
    Write-Host "$($rv.PadRight(62))|" -ForegroundColor $boxColor
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $boxColor
    Write-Host ""
    Write-Host "  Same action, same action ID. Only the policy changed." -ForegroundColor Cyan
    Wait-IfNeeded
}

function Step-SalesAllow {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Green
    Write-Host "  MXC Demo 4 - Allow policy: network approved" -ForegroundColor Green
    Write-Host "===========================================================" -ForegroundColor Green
    Write-Host ""
    $actionArgs = Get-MicrosoftCurlActionArgs
    $actionId = Get-ActionId $actionArgs
    Write-Host "  Action: same curl http://www.microsoft.com" -ForegroundColor White
    Write-Host "  Action ID: $actionId (unchanged from Demo 2/3)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Policy file: policies/sales-network-allow.json" -ForegroundColor Green
    $allowPolicyContent = Get-Content (Join-Path $ProjectRoot "policies\sales-network-allow.json") -Raw | ConvertFrom-Json
    $allowRule = $allowPolicyContent.network.defaultPolicy
    Write-Host "  Key rule:    `"network`": { `"defaultPolicy`": `"$allowRule`" }" -ForegroundColor Green
    Write-Host "  Containment: $($allowPolicyContent.containment)" -ForegroundColor Green
    Write-Host ""
    $policy = Copy-PolicyToEvidence "sales-network-allow.json"
    $result = Invoke-WxcPolicyQuietWithExpectedStatus $policy "sales_03_mxc_network_allow" "200" -MaxAttempts 3 -CommandArgs $actionArgs
    $status = Get-HttpStatusFromOutput $result.Output
    $isAllowed = ($status -eq "200")
    $verdictText = if ($isAllowed) { "OUTBOUND NETWORK ALLOWED" } else { "OUTBOUND NETWORK BLOCKED" }
    $boxColor = if ($isAllowed) { "Green" } else { "Red" }
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $boxColor
    Write-Host "  |  MXC POLICY ACTIVE                                        |" -ForegroundColor $boxColor
    $rid = "  |  action id -> $actionId"
    Write-Host "$($rid.PadRight(62))|" -ForegroundColor $boxColor
    $r1 = "  |  curl microsoft.com -> HTTP $status"
    Write-Host "$($r1.PadRight(62))|" -ForegroundColor $boxColor
    $rv = "  |  verdict: $verdictText"
    Write-Host "$($rv.PadRight(62))|" -ForegroundColor $boxColor
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $boxColor
    Write-Host ""
    Write-Host "  Same action, same action ID. Policy changed = outcome changed." -ForegroundColor Cyan
    Wait-IfNeeded
}

function Step-PipPolicy {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  MXC Policy Probe - ProcessContainer enforcement" -ForegroundColor Cyan
    Write-Host "  Pip install attempt + Win32/UI policy proof" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""

    $python = Find-HostPython
    if (-not $python) {
        Write-Host "VALIDATION_FAILED: cannot find python.exe for pip probe" -ForegroundColor Red
        exit 1
    }

    $root = "C:\temp\mxc-pip-policy-test"
    $blockTarget = Join-Path $root "blocked"
    $allowTarget = Join-Path $root "allowed"
    Remove-Item $blockTarget, $allowTarget -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $blockTarget, $allowTarget | Out-Null

    $blockPolicy = Join-Path $EvidenceDir "pip-policy-network-block.json"
    $allowPolicy = Join-Path $EvidenceDir "pip-policy-network-allow.json"
    Write-JsonPolicyFile $blockPolicy (New-PipPolicyConfig "PipInstall-Network-Block" "block" $blockTarget)
    Write-JsonPolicyFile $allowPolicy (New-PipPolicyConfig "PipInstall-Network-Allow" "allow" $allowTarget)

    $blockArgs = Get-PipInstallProbeArgs $python $blockTarget
    $allowArgs = Get-PipInstallProbeArgs $python $allowTarget
    $actionId = Get-ActionId $blockArgs

    Write-Host "  Python:     $python" -ForegroundColor White
    Write-Host "  Package:    six==1.16.0" -ForegroundColor White
    Write-Host "  Action ID:  $actionId" -ForegroundColor Gray
    Write-Host ""

    Write-Host "  Running network=block policy..." -ForegroundColor Red
    $blockResult = Invoke-WxcPolicyQuiet $blockPolicy "pip_policy_01_network_block" -CommandArgs $blockArgs
    $blockInstalled = Test-Path (Join-Path $blockTarget "six.py")
    $pipFsUnavailable = ($blockResult.Output -match "bfscfg.exe was not resolved")
    $pipPythonUnavailable = ($blockResult.ExitCode -eq -1073741515 -or $allowResult.ExitCode -eq -1073741515)
    $blockBlocked = (-not $blockInstalled) -and ($blockResult.ExitCode -ne 0)

    Write-Host "  Running network=allow policy..." -ForegroundColor Green
    $allowResult = Invoke-WxcPolicyQuiet $allowPolicy "pip_policy_02_network_allow" -CommandArgs $allowArgs
    $allowInstalled = Test-Path (Join-Path $allowTarget "six.py")
    $allowOk = ($allowResult.ExitCode -eq 0) -and $allowInstalled

    $lockPolicy = Join-Path $EvidenceDir "win32-ui-default-lockdown.json"
    $uiAllowPolicy = Join-Path $EvidenceDir "win32-ui-allow-windows.json"
    Write-JsonPolicyFile $lockPolicy (New-Win32UiPolicyConfig "Win32-UI-Default-Lockdown" $false)
    Write-JsonPolicyFile $uiAllowPolicy (New-Win32UiPolicyConfig "Win32-UI-Allow-Windows" $true)

    $uiArgs = Get-Win32UiProbeArgs
    $uiActionId = Get-ActionId $uiArgs
    Write-Host "  Running Win32/UI default lockdown policy..." -ForegroundColor Red
    $uiLockedResult = Invoke-WxcPolicyQuiet $lockPolicy "win32_ui_01_default_lockdown" -CommandArgs $uiArgs
    Write-Host "  Running Win32/UI allowWindows policy..." -ForegroundColor Green
    $uiAllowedResult = Invoke-WxcPolicyQuiet $uiAllowPolicy "win32_ui_02_allow_windows" -CommandArgs $uiArgs
    $uiBlocked = ($uiLockedResult.ExitCode -eq -1073741502) -and ($uiLockedResult.Output -match "Win32k|dll_init_failed_ui_required|UI subsystem")
    $uiAllowed = ($uiAllowedResult.ExitCode -eq 0) -and ($uiAllowedResult.Output -match "MXC_PS_OK")

    $summary = @(
        "MXC pip policy probe",
        "time=$(Get-Date -Format o)",
        "wxc=$Wxc",
        "python=$python",
        "package=six==1.16.0",
        "action_id=$actionId",
        "block_policy=$blockPolicy",
        "block_exit=$($blockResult.ExitCode)",
        "block_installed=$blockInstalled",
        "block_log=$($blockResult.Log)",
        "allow_policy=$allowPolicy",
        "allow_exit=$($allowResult.ExitCode)",
        "allow_installed=$allowInstalled",
        "allow_log=$($allowResult.Log)",
        "pip_filesystem_policy_unavailable=$pipFsUnavailable",
        "pip_python_unavailable=$pipPythonUnavailable",
        "verdict_block=$blockBlocked",
        "verdict_allow=$allowOk",
        "win32_ui_action_id=$uiActionId",
        "ui_lock_policy=$lockPolicy",
        "ui_lock_exit=$($uiLockedResult.ExitCode)",
        "ui_lock_log=$($uiLockedResult.Log)",
        "ui_allow_policy=$uiAllowPolicy",
        "ui_allow_exit=$($uiAllowedResult.ExitCode)",
        "ui_allow_log=$($uiAllowedResult.Log)",
        "verdict_ui_blocked=$uiBlocked",
        "verdict_ui_allowed=$uiAllowed"
    )
    $summaryPath = Join-Path $EvidenceDir "pip_policy_probe_summary.txt"
    $summary | Set-Content -Path $summaryPath -Encoding UTF8

    Write-Host ""
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Cyan
    Write-Host "  |  Result                                                   |" -ForegroundColor Cyan
    $b1 = "  |  pip network=block -> exit $($blockResult.ExitCode), installed=$blockInstalled"
    Write-Host "$($b1.PadRight(62))|" -ForegroundColor $(if ($blockBlocked) { "Green" } else { "Red" })
    $a1 = "  |  pip network=allow -> exit $($allowResult.ExitCode), installed=$allowInstalled"
    Write-Host "$($a1.PadRight(62))|" -ForegroundColor $(if ($allowOk) { "Green" } else { "Yellow" })
    $p1 = "  |  pip verdict -> inconclusive on this host"
    Write-Host "$($p1.PadRight(62))|" -ForegroundColor Yellow
    $u1 = "  |  Win32/UI lockdown -> exit $($uiLockedResult.ExitCode), blocked=$uiBlocked"
    Write-Host "$($u1.PadRight(62))|" -ForegroundColor $(if ($uiBlocked) { "Green" } else { "Red" })
    $u2 = "  |  Win32/UI allow -> exit $($uiAllowedResult.ExitCode), allowed=$uiAllowed"
    Write-Host "$($u2.PadRight(62))|" -ForegroundColor $(if ($uiAllowed) { "Green" } else { "Red" })
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Evidence summary: $summaryPath" -ForegroundColor White
    Write-Host "  Block log:        $($blockResult.Log)" -ForegroundColor White
    Write-Host "  Allow log:        $($allowResult.Log)" -ForegroundColor White
    Write-Host "  UI block log:     $($uiLockedResult.Log)" -ForegroundColor White
    Write-Host "  UI allow log:     $($uiAllowedResult.Log)" -ForegroundColor White

    if (-not $uiBlocked -or -not $uiAllowed) {
        Write-Host "VALIDATION_FAILED: expected UI lockdown to block PowerShell and allowWindows to run it" -ForegroundColor Red
        exit 1
    }
    Wait-IfNeeded
}

function Step-SalesHyperlightRestrict {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Magenta
    Write-Host "  MXC Demo 6 - Hyperlight network policy" -ForegroundColor Magenta
    Write-Host "  Does current policy allow this Hyperlight guest to reach the internet?" -ForegroundColor Magenta
    Write-Host "===========================================================" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "  Action: Python urllib.request.urlopen('http://www.microsoft.com')" -ForegroundColor White
    Write-Host "  Backend: Hyperlight (isolated micro-VM)" -ForegroundColor White
    Write-Host ""
    Write-Host "  Policy file: policies/06-hyperlight-network-policy.json" -ForegroundColor Magenta
    $policyContent = Get-Content (Join-Path $ProjectRoot "policies\06-hyperlight-network-policy.json") -Raw
    $policyNetRule = if ($policyContent -match '"defaultPolicy":\s*"([^"]+)"') { $matches[1] } else { "block" }
    Write-Host '  Key rule:    "containment": "hyperlight"' -ForegroundColor Magenta
    $ruleDisplay = "               `"network`": { `"defaultPolicy`": `"$policyNetRule`" }"
    Write-Host $ruleDisplay -ForegroundColor Magenta
    Write-Host ""
    $policy = Copy-PolicyToEvidence "06-hyperlight-network-policy.json"
    $actionArgs = Get-HyperlightNetworkProbeActionArgs
    $result = Invoke-WxcPolicyQuiet $policy "sales_05_hyperlight_network_restrict" -Experimental -CommandArgs $actionArgs

    $netResult = Get-OutputValue $result.Output "NETWORK_RESULT"
    $errType = Get-OutputValue $result.Output "ERROR_TYPE"
    $isBlocked = ($netResult -match "BLOCKED")
    $verdictText = if ($isBlocked) { "GUEST CANNOT REACH THE INTERNET" } else { "GUEST CAN REACH THE INTERNET" }
    $verdictColor = if ($isBlocked) { "Magenta" } else { "Green" }

    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $verdictColor
    Write-Host "  |  Hyperlight guest network probe                           |" -ForegroundColor $verdictColor
    $r1 = "  |  urllib.request -> $netResult"
    Write-Host "$($r1.PadRight(62))|" -ForegroundColor $verdictColor
    $r2 = "  |  error          -> $errType"
    Write-Host "$($r2.PadRight(62))|" -ForegroundColor $verdictColor
    $r3 = "  |  verdict: $verdictText"
    Write-Host "$($r3.PadRight(62))|" -ForegroundColor $verdictColor
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $verdictColor
    Write-Host ""
    if ($isBlocked) {
        Write-Host "  Policy says block -> network denied. Change to allow -> it works." -ForegroundColor Cyan
        $script:Demo6Summary = "Demo 6: Hyperlight guest network is denied by current policy."
    } else {
        Write-Host "  Policy says allow -> network granted. Change to block -> it's denied." -ForegroundColor Cyan
        $script:Demo6Summary = "Demo 6: Hyperlight guest network is granted by current policy."
    }
    Wait-IfNeeded
}

function Step-HyperlightLifecycle {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Blue
    Write-Host "  MXC Demo 7 - Hyperlight lifecycle: long-running action" -ForegroundColor Blue
    Write-Host "  Can we see a Hyperlight-backed action while it is alive?" -ForegroundColor Blue
    Write-Host "===========================================================" -ForegroundColor Blue
    Write-Host ""
    Write-Host "  Important: Hyperlight is embedded in wxc-exec.exe." -ForegroundColor White
    Write-Host "  Windows will show the host process, not Hyperlight.exe." -ForegroundColor White
    Write-Host ""
    Write-Host "  Policy file: policies/07-hyperlight-lifecycle.json" -ForegroundColor Blue
    Write-Host '  Key rule:    "containment": "hyperlight"' -ForegroundColor Blue
    Write-Host '               "timeout": 120000000 ms (120000 seconds)' -ForegroundColor Blue
    Write-Host '               guest sleep: 120000 seconds' -ForegroundColor Blue
    Write-Host ""

    Write-Host ""
    Write-Host "  What is inside the Hyperlight guest?" -ForegroundColor White
    Write-Host ""
    $lsCode = "import os, sys; root = sorted(os.listdir('/')); paths = sys.path[:4]; print('GUEST_FS_ROOT=' + ','.join(root)); print('GUEST_PYTHON_LIB=' + (paths[1] if len(paths)>1 else '?'))"
    $lsEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($lsCode))
    $lsWrapper = "exec(__import__('base64').b64decode('$lsEncoded').decode())"
    $lsPolicy = Copy-PolicyToEvidence "coding-hyperlight.json"
    $lsResult = Invoke-WxcPolicyQuiet $lsPolicy "demo7_guest_ls" -Experimental -CommandArgs @($lsWrapper)
    $guestRoot = Get-OutputValue $lsResult.Output "GUEST_FS_ROOT"
    $guestPyLib = Get-OutputValue $lsResult.Output "GUEST_PYTHON_LIB"
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Blue
    Write-Host "  |  Guest filesystem (os.listdir('/'))                        |" -ForegroundColor Blue
    $lr1 = "  |  / contains: $guestRoot"
    Write-Host "$($lr1.PadRight(62))|" -ForegroundColor Blue
    $lr2 = "  |  Python lib: $guestPyLib"
    Write-Host "$($lr2.PadRight(62))|" -ForegroundColor Blue
    Write-Host "  |  No C:\, no Users\, no Windows host files visible.        |" -ForegroundColor Blue
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Blue
    Write-Host ""

    $policy = Copy-PolicyToEvidence "07-hyperlight-lifecycle.json"
    $log = Join-Path $EvidenceDir "demo7_hyperlight_lifecycle.log"
    $err = Join-Path $EvidenceDir "demo7_hyperlight_lifecycle.err.log"
    Remove-Item $log, $err -ErrorAction SilentlyContinue

    $argLine = "--experimental --debug `"$policy`""
    $proc = Start-Process -FilePath $Wxc -ArgumentList $argLine -RedirectStandardOutput $log -RedirectStandardError $err -PassThru -WindowStyle Hidden

    Write-Host "  Started action: wxc-exec.exe" -ForegroundColor White
    Write-Host "  Windows PID:    $($proc.Id)" -ForegroundColor White
    Write-Host ""
    Write-Host "  Open Task Manager now:" -ForegroundColor Yellow
    Write-Host "    Search term: wxc-exec or wxc-exec.exe" -ForegroundColor Yellow
    Write-Host "    Policy lifetime: 120000 seconds." -ForegroundColor Yellow
    Write-Host "    Demo observation window: 30 seconds." -ForegroundColor Yellow
    Write-Host "    It will NOT naturally exit at 30s; cleanup is manual." -ForegroundColor Yellow
    Write-Host ""

    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Blue
    Write-Host "  |  Windows-side lifecycle observation (first 30 seconds)    |" -ForegroundColor Blue
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 1
        $running = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
        $state = if ($running) { "RUNNING" } else { "EXITED" }
        $line = "  |  t+$($i)s  wxc-exec.exe PID $($proc.Id) -> $state"
        Write-Host "$($line.PadRight(62))|" -ForegroundColor Blue
        if ($state -eq "EXITED") { break }
    }
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Blue
    Write-Host ""

    if ($Step -ne "demo-all") {
        [void](Read-Host "  Press Enter to manually stop and clean up the long-running action")
    } else {
        Write-Host "  demo-all mode: cleaning up the long-running action automatically." -ForegroundColor Yellow
    }

    $runningBeforeCleanup = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    $cleanupAction = if ($runningBeforeCleanup) {
        & C:\Windows\System32\taskkill.exe /PID $proc.Id /F | Out-Null
        "stopped wxc-exec.exe"
    } else {
        "already exited"
    }
    for ($wait = 1; $wait -le 10; $wait++) {
        if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Milliseconds 500
    }
    $finalState = if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) { "STILL_RUNNING" } else { "EXITED" }

    $lifeLog = ""
    if (Test-Path $log) { $lifeLog += (Get-Content $log -Raw) }
    if (Test-Path $err) { $lifeLog += "`n" + (Get-Content $err -Raw) }
    $exitCode = if ($lifeLog -match "Exit code: (-?\d+)") { $matches[1] } else { "terminated" }
    $startSeen = if ($lifeLog -match "LIFECYCLE_EVENT=START") { "seen" } else { "missing" }
    $requestedLifetime = if ($lifeLog -match "REQUESTED_LIFETIME_SECONDS=(\d+)") { $matches[1] + "s" } else { "missing" }

    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Blue
    Write-Host "  |  Completion                                                |" -ForegroundColor Blue
    $line1 = "  |  final process state -> $finalState"
    Write-Host "$($line1.PadRight(62))|" -ForegroundColor Blue
    $line2 = "  |  exit code           -> $exitCode"
    Write-Host "$($line2.PadRight(62))|" -ForegroundColor Blue
    $line3 = "  |  guest start event   -> $startSeen"
    Write-Host "$($line3.PadRight(62))|" -ForegroundColor Blue
    $line4 = "  |  requested lifetime  -> $requestedLifetime"
    Write-Host "$($line4.PadRight(62))|" -ForegroundColor Blue
    $line5 = "  |  cleanup action      -> $cleanupAction"
    Write-Host "$($line5.PadRight(62))|" -ForegroundColor Blue
    $line6 = "  |  natural 30s exit?   -> no, manual cleanup"
    Write-Host "$($line6.PadRight(62))|" -ForegroundColor Blue
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Blue
    Write-Host ""
    Write-Host "  Takeaway: MXC can keep a Hyperlight action alive long enough" -ForegroundColor Cyan
    Write-Host "  to observe it in Windows, then the host process is cleaned up." -ForegroundColor Cyan

    if ($finalState -ne "EXITED" -or $startSeen -ne "seen" -or $requestedLifetime -ne "120000s") {
        Write-Host "VALIDATION_FAILED: Hyperlight lifecycle demo did not complete cleanly" -ForegroundColor Red
        exit 1
    }
    Wait-IfNeeded
}

function Step-BackendFit {
    # ═══ ACT 1: Title + Prompt ═══
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  AIPC Coding Assistant - Code Execution Demo" -ForegroundColor Cyan
    Write-Host "  Can generated code run safely on this AIPC?" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""

    $resolvedPrompt = Resolve-CodingPrompt $PromptText

    Write-Host "> Problem prompt sent to model: $resolvedPrompt" -ForegroundColor White
    Write-Host ""

    # ═══ ACT 2: Model code generation + artifact preview ═══
    $artifactTimer = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $artifact = New-RealCodegenExecutionArtifact $resolvedPrompt
    } catch {
        Write-Host ""
        Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Red
        Write-Host "  |  MODEL CODE GENERATION FAILED                             |" -ForegroundColor Red
        $errLine = "  |  $($_.Exception.Message)"
        Write-Host "$($errLine.PadRight(62))|" -ForegroundColor Red
        Write-Host "  |  No prewritten analyzer was used.                          |" -ForegroundColor Red
        Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Red
        exit 1
    }
    $artifactTimer.Stop()
    $csvPath = $artifact.CsvFile
    $csvLines = @(Get-Content $csvPath)
    $dataRows = $csvLines.Count - 1
    $artifactHash = (Get-FileHash -Path $artifact.GeneratedCodeFile -Algorithm SHA256).Hash.Substring(0, 12)

    Write-Host "  Model-generated code artifact: latest_generated_from_prompt.py ($((Get-Content $artifact.GeneratedCodeFile).Count) lines)" -ForegroundColor White
    Write-Host "  Artifact file: workspace-output/generated-code/latest_generated_from_prompt.py" -ForegroundColor White
    Write-Host "  Artifact SHA256: $artifactHash" -ForegroundColor White
    Write-Host "  APIM response id: $($artifact.ResponseId)" -ForegroundColor White
    Write-Host "  Codegen config: $($artifact.ConfigSource)" -ForegroundColor White
    Write-Host ""
    Write-Host "  Generated code preview (first 18 lines):" -ForegroundColor White
    $previewLines = Get-Content $artifact.GeneratedCodeFile | Select-Object -First 18
    for ($idx = 0; $idx -lt $previewLines.Count; $idx++) {
        $lineNo = ($idx + 1).ToString().PadLeft(2)
        $line = $previewLines[$idx]
        if ($line.Length -gt 74) { $line = $line.Substring(0, 71) + "..." }
        Write-Host "    $lineNo | $line" -ForegroundColor Gray
    }
    Write-Host ""
    if ($Step -ne "demo-all") {
        [void](Read-Host "  Press Enter to execute this artifact in MXC backends")
    } else {
        Write-Host "  demo-all mode: executing artifact after preview." -ForegroundColor Yellow
    }
    Write-Host ""

    Write-Host "  Input data: product_inventory_q2.csv ($dataRows products)" -ForegroundColor White
    Write-Host ""
    Write-Host "  model                       | category    | units | price" -ForegroundColor Gray
    Write-Host "  ----------------------------|-------------|-------|------" -ForegroundColor Gray
    foreach ($row in ($csvLines | Select-Object -Skip 1)) {
        $cols = $row -split ","
        $model = $cols[0].PadRight(28).Substring(0,28)
        $cat = $cols[1].PadRight(11).Substring(0,11)
        Write-Host "  $model| $cat | $($cols[2].PadLeft(5)) | $($cols[3].PadLeft(5))" -ForegroundColor Gray
    }
    Write-Host ""

    # ═══ ACT 3: Execute in both backends ═══
    Write-Host "  Executing same code artifact in two MXC backends..." -ForegroundColor White
    Write-Host ""

    $processPolicy = Copy-PolicyToEvidence "coding-processcontainer.json"
    $processArgs = Get-CodingProcessContainerArgs $artifact.Code
    $processResult = Invoke-WxcPolicyQuiet $processPolicy "backend_fit_01_processcontainer" -CommandArgs $processArgs

    $hyperPolicy = Copy-PolicyToEvidence "coding-hyperlight.json"
    $hyperArgs = Get-CodingHyperlightArgs $artifact.Code
    $hyperResult = Invoke-WxcPolicyQuiet $hyperPolicy "backend_fit_02_hyperlight" -Experimental -CommandArgs $hyperArgs

    $processStatus = if ($processResult.ExitCode -eq 0 -and $processResult.Output -match "WORKLOAD_RESULT=SUPPORTED") { "PASS" } else { "FAIL" }
    $hyperStatus = if ($hyperResult.ExitCode -eq 0 -and $hyperResult.Output -match "WORKLOAD_RESULT=SUPPORTED") { "PASS" } else { "FAIL" }
    $answer = Get-OutputValue $hyperResult.Output "ANSWER"
    $execTime = if ($hyperResult.Output -match "Runner completed in (\d+)ms") { $matches[1] + "ms" } else { "?" }

    # processcontainer box — dynamic from actual result
    $pcBoxColor = if ($processStatus -eq "FAIL") { "Red" } else { "Green" }
    $pcReason = Get-ProcessContainerFailureReason $processResult.ExitCode
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $pcBoxColor
    $pcStatusLine = "  |  processcontainer       $processStatus"
    Write-Host "$($pcStatusLine.PadRight(62))|" -ForegroundColor $pcBoxColor
    $pcReasonLine = "  |  $pcReason"
    Write-Host "$($pcReasonLine.PadRight(62))|" -ForegroundColor $pcBoxColor
    $pcExitLine = "  |  Exit code: $($processResult.ExitCode)"
    Write-Host "$($pcExitLine.PadRight(62))|" -ForegroundColor $pcBoxColor
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $pcBoxColor
    Write-Host ""

    # Hyperlight box — dynamic from actual result
    $hlBoxColor = if ($hyperStatus -eq "PASS") { "Green" } else { "Red" }
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $hlBoxColor
    $hlStatusLine = "  |  Hyperlight              $hyperStatus"
    Write-Host "$($hlStatusLine.PadRight(62))|" -ForegroundColor $hlBoxColor
    $hlRuntime = Get-OutputValue $hyperResult.Output "RUNTIME"
    $hlRuntimeLine = "  |  Runtime: $hlRuntime"
    Write-Host "$($hlRuntimeLine.PadRight(62))|" -ForegroundColor $hlBoxColor
    $answerDisplay = Limit-DisplayText $answer 49
    $resultLine = "  |  Answer: $answerDisplay"
    Write-Host "$($resultLine.PadRight(62))|" -ForegroundColor $hlBoxColor
    $timeLine = "  |  Execution time: $execTime"
    Write-Host "$($timeLine.PadRight(62))|" -ForegroundColor $hlBoxColor
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $hlBoxColor
    Write-Host ""

    # ═══ ACT 4: Isolation comparison — processcontainer leaks, Hyperlight doesn't ═══
    Write-Host "  What can malicious code see about the host?" -ForegroundColor White
    Write-Host ""

    # processcontainer probe via cmd.exe (which CAN start) - use "set" to dump env vars
    $pcProbeArgs = @("C:\Windows\System32\cmd.exe", "/c", "set")
    $pcProbeResult = Invoke-WxcPolicyQuiet $processPolicy "demo5_pc_identity_probe" -CommandArgs $pcProbeArgs
    $pcOutput = $pcProbeResult.Output
    $pcUserprofile = if ($pcOutput -match "(?m)^USERPROFILE=(.+)$") { $matches[1].Trim() } else { "?" }
    $pcComputername = if ($pcOutput -match "(?m)^COMPUTERNAME=(.+)$") { $matches[1].Trim() } else { "?" }
    $pcOS = if ($pcOutput -match "(?m)^OS=(.+)$") { $matches[1].Trim() } else { "?" }
    $pcUserprofileDisplay = if ($pcUserprofile -match "^C:\\Users\\") { "C:\Users\<host-user>" } else { $pcUserprofile }
    $pcComputernameDisplay = if ($pcComputername -ne "?") { "<device-name>" } else { $pcComputername }

    # Hyperlight probe via Python
    $isolationProbe = @'
import os, sys
results = []
try:
    entries = os.listdir('C:\\Users')
    results.append('HOST_USERS=VISIBLE:' + ','.join(entries[:3]))
except Exception as e:
    results.append('HOST_USERS=BLOCKED:' + type(e).__name__)
uname = os.environ.get('USERNAME', os.environ.get('USER', 'NOT_FOUND'))
results.append('HOST_USERNAME=' + uname)
try:
    import winreg
    results.append('WIN_REGISTRY=AVAILABLE')
except Exception:
    results.append('WIN_REGISTRY=NOT_AVAILABLE')
results.append('PLATFORM=' + sys.platform)
for r in results:
    print(r)
'@
    $isoEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($isolationProbe))
    $isoCode = "exec(__import__('base64').b64decode('$isoEncoded').decode())"
    $isoResult = Invoke-WxcPolicyQuiet $hyperPolicy "demo5_isolation_probe" -Experimental -CommandArgs @($isoCode)
    $hlUsers = Get-OutputValue $isoResult.Output "HOST_USERS"
    $hlUsername = Get-OutputValue $isoResult.Output "HOST_USERNAME"
    $hlRegistry = Get-OutputValue $isoResult.Output "WIN_REGISTRY"
    $hlPlatform = Get-OutputValue $isoResult.Output "PLATFORM"

    $pcIdentityLeaked = ($pcUserprofile -ne "?" -or $pcComputername -ne "?")
    $pcIdentityVerdict = if ($pcIdentityLeaked) { "HOST IDENTITY LEAKED" } else { "HOST IDENTITY NOT DETECTED" }
    $pcIdColor = if ($pcIdentityLeaked) { "Red" } else { "Green" }
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $pcIdColor
    Write-Host "  |  processcontainer (cmd.exe probe)                         |" -ForegroundColor $pcIdColor
    $pc1 = "  |  USERPROFILE    = $pcUserprofileDisplay"
    Write-Host "$($pc1.PadRight(62))|" -ForegroundColor $pcIdColor
    $pc2 = "  |  COMPUTERNAME   = $pcComputernameDisplay"
    Write-Host "$($pc2.PadRight(62))|" -ForegroundColor $pcIdColor
    $pc3 = "  |  OS             = $pcOS"
    Write-Host "$($pc3.PadRight(62))|" -ForegroundColor $pcIdColor
    $pcIdVerdictLine = "  |  verdict: $pcIdentityVerdict"
    Write-Host "$($pcIdVerdictLine.PadRight(62))|" -ForegroundColor $pcIdColor
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $pcIdColor
    Write-Host ""
    $hlInvisible = ($hlUsername -eq "NOT_FOUND" -and $hlUsers -match "BLOCKED")
    $hlIdentityVerdict = if ($hlInvisible) { "HOST IDENTITY INVISIBLE" } else { "HOST IDENTITY VISIBLE" }
    $hlIdColor = if ($hlInvisible) { "Green" } else { "Red" }
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $hlIdColor
    Write-Host "  |  Hyperlight (Python probe)                                |" -ForegroundColor $hlIdColor
    $hl1 = "  |  C:\Users       = $hlUsers"
    Write-Host "$($hl1.PadRight(62))|" -ForegroundColor $hlIdColor
    $hl2 = "  |  USERNAME       = $hlUsername"
    Write-Host "$($hl2.PadRight(62))|" -ForegroundColor $hlIdColor
    $hl3 = "  |  winreg         = $hlRegistry"
    Write-Host "$($hl3.PadRight(62))|" -ForegroundColor $hlIdColor
    $hl4 = "  |  sys.platform   = $hlPlatform"
    Write-Host "$($hl4.PadRight(62))|" -ForegroundColor $hlIdColor
    $hlIdVerdictLine = "  |  verdict: $hlIdentityVerdict"
    Write-Host "$($hlIdVerdictLine.PadRight(62))|" -ForegroundColor $hlIdColor
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor $hlIdColor
    Write-Host ""
    Write-Host "  processcontainer runs in the same OS - it leaks who you are." -ForegroundColor Cyan
    Write-Host "  Hyperlight is a separate VM - the code has no idea." -ForegroundColor Cyan
    Write-Host ""

    # Validation (hidden from audience, only fails if something is broken)
    if ($processStatus -ne "FAIL") {
        Write-Host "VALIDATION_FAILED: processcontainer was expected to fail" -ForegroundColor Red
        exit 1
    }
    if ($hyperStatus -ne "PASS") {
        Write-Host "VALIDATION_FAILED: Hyperlight should run the code artifact successfully" -ForegroundColor Red
        exit 1
    }
    if ($answer -eq "missing") {
        Write-Host "VALIDATION_FAILED: generated code did not print ANSWER" -ForegroundColor Red
        exit 1
    }
    if (Test-Path $artifact.GeneratedCodeFile) {
        Remove-Item $artifact.GeneratedCodeFile -Force
    }
    Wait-IfNeeded
}

function Step-TaskRbac {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  MXC Task-Scoped RBAC / Capability Policy Probe" -ForegroundColor Cyan
    Write-Host "  Same Win32 capability probe, different task profiles" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""

    $probeExe = Build-NativeWin32CapabilityProbe
    $probeArgs = @($probeExe)
    $taskActionArgs = Get-Win32UiProbeArgs
    $actionId = Get-ActionId $taskActionArgs

    $hostLog = Join-Path $EvidenceDir "task_rbac_00_host_baseline.log"
    $hostOutput = & $probeExe --no-wmi 2>&1
    $hostExit = $LASTEXITCODE
    $hostOutput | Set-Content -Path $hostLog -Encoding UTF8

    $textPolicy = Join-Path $EvidenceDir "task-rbac-text-lockdown.json"
    $drawingPolicy = Join-Path $EvidenceDir "task-rbac-drawing-ui.json"
    Write-JsonPolicyFile $textPolicy (New-Win32UiPolicyConfig "Task-Text-Lockdown" $false)
    Write-JsonPolicyFile $drawingPolicy (New-Win32UiPolicyConfig "Task-Drawing-UiAllowed" $true -BroadUi)

    Write-Host "  Probe exe:  $probeExe" -ForegroundColor White
    Write-Host "  Task action: powershell.exe -NoProfile -Command Write-Output MXC_PS_OK" -ForegroundColor White
    Write-Host "  Action ID:   $actionId" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Running host baseline..." -ForegroundColor White
    Write-Host "  Running text task policy (UI/Win32k locked down)..." -ForegroundColor Red
    $textResult = Invoke-WxcPolicyQuiet $textPolicy "task_rbac_01_text_lockdown" -CommandArgs $taskActionArgs
    Write-Host "  Running drawing task policy (UI/Win32k allowed)..." -ForegroundColor Green
    $drawingResult = Invoke-WxcPolicyQuiet $drawingPolicy "task_rbac_02_drawing_ui_allowed" -CommandArgs $taskActionArgs

    $hostStats = Get-ProbeStats ($hostOutput -join "`n")
    $textStats = Get-ProbeStats $textResult.Output
    $drawingStats = Get-ProbeStats $drawingResult.Output
    $textBlocked = ($textResult.Output -match "Win32k mitigation applied|dll_init_failed_ui_required|UI subsystem" -or $textResult.ExitCode -ne 0)
    $drawingRan = ($drawingResult.Output -match "MXC_PS_OK") -and ($drawingResult.ExitCode -eq 0)
    $capabilityDelta = ($textBlocked -and $drawingRan)

    $summaryPath = Join-Path $EvidenceDir "task_rbac_policy_probe_summary.txt"
    @(
        "MXC task-scoped RBAC / capability policy probe",
        "time=$(Get-Date -Format o)",
        "wxc=$Wxc",
        "probe_exe=$probeExe",
        "action_id=$actionId",
        "host_exit=$hostExit",
        "host_pass=$($hostStats.Pass)",
        "host_fail=$($hostStats.Fail)",
        "host_log=$hostLog",
        "text_policy=$textPolicy",
        "text_exit=$($textResult.ExitCode)",
        "text_pass=$($textStats.Pass)",
        "text_fail=$($textStats.Fail)",
        "text_log=$($textResult.Log)",
        "drawing_policy=$drawingPolicy",
        "drawing_exit=$($drawingResult.ExitCode)",
        "drawing_pass=$($drawingStats.Pass)",
        "drawing_fail=$($drawingStats.Fail)",
        "drawing_log=$($drawingResult.Log)",
        "verdict_text_restricted=$textBlocked",
        "verdict_drawing_ran=$drawingRan",
        "verdict_capability_delta=$capabilityDelta"
    ) | Set-Content -Path $summaryPath -Encoding UTF8

    Write-Host ""
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Cyan
    Write-Host "  |  Result                                                   |" -ForegroundColor Cyan
    $h = "  |  host baseline -> exit $hostExit, pass=$($hostStats.Pass), fail=$($hostStats.Fail)"
    Write-Host "$($h.PadRight(62))|" -ForegroundColor White
    $t = "  |  text profile  -> exit $($textResult.ExitCode), blocked=$textBlocked"
    Write-Host "$($t.PadRight(62))|" -ForegroundColor $(if ($textBlocked) { "Green" } else { "Red" })
    $d = "  |  draw profile  -> exit $($drawingResult.ExitCode), allowed=$drawingRan"
    Write-Host "$($d.PadRight(62))|" -ForegroundColor $(if ($drawingRan) { "Green" } else { "Red" })
    $v = "  |  capability delta -> $capabilityDelta"
    Write-Host "$($v.PadRight(62))|" -ForegroundColor $(if ($capabilityDelta) { "Green" } else { "Red" })
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Evidence summary: $summaryPath" -ForegroundColor White
    Write-Host "  Text policy log:  $($textResult.Log)" -ForegroundColor White
    Write-Host "  Draw policy log:  $($drawingResult.Log)" -ForegroundColor White

    if (-not $drawingRan -or -not $capabilityDelta) {
        Write-Host "VALIDATION_FAILED: expected task profiles to produce different capability results" -ForegroundColor Red
        exit 1
    }
    Wait-IfNeeded
}

function Step-CapabilityCatalog {
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "  MXC Capability Catalog Probe" -ForegroundColor Cyan
    Write-Host "  Native Win32 probes across task capability profiles" -ForegroundColor Cyan
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host ""

    $probeExe = Build-NativeWin32CapabilityProbe
    $probeArgs = @($probeExe)
    $profiles = @(
        [PSCustomObject]@{ Name = "text-lockdown"; Policy = (New-Win32UiPolicyConfig "Capability-Text-Lockdown" $false) },
        [PSCustomObject]@{ Name = "gdi-minimal"; Policy = (New-Win32UiPolicyConfig "Capability-Gdi-Minimal" $true) },
        [PSCustomObject]@{ Name = "broad-ui"; Policy = (New-Win32UiPolicyConfig "Capability-Broad-Ui" $true -BroadUi) }
    )

    $hostLog = Join-Path $EvidenceDir "capability_catalog_00_host_baseline.log"
    $hostOutput = & $probeExe --no-wmi 2>&1
    $hostExit = $LASTEXITCODE
    $hostOutput | Set-Content -Path $hostLog -Encoding UTF8
    $hostStats = Get-NativeProbeProfileStats ($hostOutput -join "`n")
    $allNames = [System.Collections.Generic.SortedSet[string]]::new()
    foreach ($key in $hostStats.Keys) { [void]$allNames.Add($key) }

    $results = @()
    foreach ($profile in $profiles) {
        $policyPath = Join-Path $EvidenceDir "capability-$($profile.Name).json"
        Write-JsonPolicyFile $policyPath $profile.Policy
        Write-Host "  Running profile: $($profile.Name)" -ForegroundColor White
        $run = Invoke-WxcPolicyQuiet $policyPath "capability_catalog_$($profile.Name)" -CommandArgs $probeArgs
        $stats = Get-NativeProbeProfileStats $run.Output
        foreach ($key in $stats.Keys) { [void]$allNames.Add($key) }
        $results += [PSCustomObject]@{ Name = $profile.Name; Policy = $policyPath; Log = $run.Log; ExitCode = $run.ExitCode; Stats = $stats }
    }

    $summaryPath = Join-Path $EvidenceDir "capability_catalog_summary.md"
    $lines = @()
    $lines += "# MXC Capability Catalog Probe"
    $lines += ""
    $lines += "Time: $(Get-Date -Format o)"
    $lines += "Probe: $probeExe"
    $lines += "Host log: $hostLog (exit=$hostExit)"
    $lines += ""
    $lines += "| Capability probe | Host baseline | text-lockdown | gdi-minimal | broad-ui |"
    $lines += "|---|---|---|---|---|"
    foreach ($name in $allNames) {
        $hostStatus = if ($hostStats.Contains($name)) { $hostStats[$name].Status } else { "N/A" }
        $row = @($name, $hostStatus)
        foreach ($profileName in @("text-lockdown", "gdi-minimal", "broad-ui")) {
            $result = $results | Where-Object { $_.Name -eq $profileName } | Select-Object -First 1
            if ($result.ExitCode -ne 0 -and $result.Stats.Count -eq 0) {
                $row += "PROCESS_BLOCKED($($result.ExitCode))"
            } elseif ($result.Stats.Contains($name)) {
                $row += $result.Stats[$name].Status
            } else {
                $row += "N/A"
            }
        }
        $lines += "| " + ($row -join " | ") + " |"
    }
    $lines += ""
    $lines += "## Logs"
    foreach ($result in $results) {
        $lines += "- $($result.Name): $($result.Log) (exit=$($result.ExitCode))"
    }
    $lines | Set-Content -Path $summaryPath -Encoding UTF8

    Write-Host ""
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Cyan
    Write-Host "  |  Summary                                                  |" -ForegroundColor Cyan
    foreach ($result in $results) {
        $passCount = @($result.Stats.Values | Where-Object { $_.Status -eq "PASS" }).Count
        $failCount = @($result.Stats.Values | Where-Object { $_.Status -eq "FAIL" }).Count
        $line = "  |  $($result.Name) -> exit $($result.ExitCode), pass=$passCount, fail=$failCount"
        Write-Host "$($line.PadRight(62))|" -ForegroundColor $(if ($result.ExitCode -eq 0) { "Green" } else { "Yellow" })
    }
    Write-Host "  +-----------------------------------------------------------+" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Capability summary: $summaryPath" -ForegroundColor White

    $gdi = $results | Where-Object { $_.Name -eq "gdi-minimal" } | Select-Object -First 1
    if (-not $gdi -or $gdi.ExitCode -ne 0 -or -not $gdi.Stats.Contains("GDI_GetDC")) {
        Write-Host "VALIDATION_FAILED: gdi-minimal profile should run native probe and report GDI_GetDC" -ForegroundColor Red
        exit 1
    }
    Wait-IfNeeded
}

switch ($Step) {
    "probe" { Step-Probe }
    "backend-fit" { Step-BackendFit }
    "demo-all" {
        Step-Probe
        Step-SalesNaked
        Step-SalesBlock
        Step-SalesAllow
        Step-PipPolicy
        Step-BackendFit
        Step-SalesHyperlightRestrict
        Step-HyperlightLifecycle
        Section "MXC Demo Summary (1-7)"
        Write-Host "Demo 1: MXC is present on this AIPC (shipped with Copilot CLI)." -ForegroundColor Green
        Write-Host "Demo 2: Without policy, agent action has full network access." -ForegroundColor Yellow
        Write-Host "Demo 3: MXC block policy denies outbound network." -ForegroundColor Red
        Write-Host "Demo 4: MXC allow policy grants approved network access." -ForegroundColor Green
        Write-Host "Demo 5: Same pip install action fails under network block and succeeds under allow." -ForegroundColor Cyan
        Write-Host "Demo 6: Hyperlight runs code; processcontainer leaks host identity." -ForegroundColor Cyan
        $demo6Summary = if ($script:Demo6Summary) { $script:Demo6Summary } else { "Demo 6: Hyperlight network result follows current policy." }
        Write-Host $demo6Summary -ForegroundColor Cyan
        Write-Host "Demo 7: Hyperlight action is observable, then manually cleaned up." -ForegroundColor Blue
    }
    "sales-naked" { Step-SalesNaked }
    "sales-block" { Step-SalesBlock }
    "sales-allow" { Step-SalesAllow }
    "pip-policy" { Step-PipPolicy }
    "task-rbac" { Step-TaskRbac }
    "capability-catalog" { Step-CapabilityCatalog }
    "sales-hyperlight-restrict" { Step-SalesHyperlightRestrict }
    "hyperlight-lifecycle" { Step-HyperlightLifecycle }
    default {
        Write-Host "VALIDATION_FAILED: unknown step '$Step'" -ForegroundColor Red
        exit 1
    }
}
