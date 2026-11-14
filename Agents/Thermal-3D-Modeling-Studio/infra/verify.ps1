#Requires -Version 7.3
<#
.SYNOPSIS
  Check a studio deployed by infra/up.ps1 from the outside, through its public HTTPS address.

.DESCRIPTION
  Always (no model tokens except one 64-token reply):
    healthz over HTTPS, HTTP redirected to HTTPS, a wrong password rejected, sign-in, the 15 scenarios, the
    pre-generated STEP solid of every scenario in Chinese and English, and one GPT-6 round trip through the
    VM's managed identity (/api/connection/test).
  With -Full (a few thousand tokens and one low-quality image):
    Generate STEP live: GPT-6 writes a CadQuery script and OpenCascade on the VM builds it; the STEP is downloaded.
    One gpt-image concept picture, when an image model is deployed.

  Reads outputs.json and portal-password.txt from the state directory of up.ps1 and writes verify-<time>.json there.
  Exit code 0 when every check passes, 1 otherwise.

.EXAMPLE
  ./infra/verify.ps1 -ResourceGroup rg-thermal-studio -Full
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$ResourceGroup,
  [string]$StateDir,
  [switch]$Full,
  [SecureString]$PortalPassword
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
if (-not $StateDir) { $StateDir = Join-Path (Join-Path $HOME '.thermal-3d-studio') $ResourceGroup }
$outputsFile = Join-Path $StateDir 'outputs.json'
if (-not (Test-Path -LiteralPath $outputsFile)) { throw "No ${outputsFile}: run infra/up.ps1 -ResourceGroup $ResourceGroup first." }
$o = Get-Content -Raw -LiteralPath $outputsFile | ConvertFrom-Json
$password = if ($PortalPassword) { ConvertFrom-SecureString -SecureString $PortalPassword -AsPlainText }
            else { (Get-Content -Raw -LiteralPath (Join-Path $StateDir 'portal-password.txt')).Trim() }
$base = "https://$($o.fqdn)"
$utf8 = [Text.UTF8Encoding]::new($false)
$started = Get-Date
$checks = [Collections.Generic.List[object]]::new()

function Check([string]$Name, [scriptblock]$Body) {
  $t = Get-Date
  try {
    $detail = & $Body
    $checks.Add([ordered]@{ name = $Name; status = 'PASS'; seconds = [Math]::Round(((Get-Date) - $t).TotalSeconds, 1); detail = $detail })
    Write-Host ("PASS  {0,-34} {1}" -f $Name, ($detail | ConvertTo-Json -Compress -Depth 4)) -ForegroundColor Green
  } catch {
    $checks.Add([ordered]@{ name = $Name; status = 'FAIL'; seconds = [Math]::Round(((Get-Date) - $t).TotalSeconds, 1); detail = "$($_.Exception.Message)" })
    Write-Host ("FAIL  {0,-34} {1}" -f $Name, $_.Exception.Message) -ForegroundColor Red
  }
}

function Get-Field($Object, [string]$Name) {
  # Set-StrictMode throws on a missing property; optional fields of an answer are read through this.
  if ($null -ne $Object -and $Object.PSObject.Properties[$Name]) { return $Object.$Name }
  return $null
}

function Read-Sse($Response) {
  # The studio streams Server-Sent Events; the stream ends after a `done` or `error` event.
  $text = [Text.Encoding]::UTF8.GetString($Response.RawContentStream.ToArray())
  $events = foreach ($block in ($text -split "`n`n")) {
    $name = ($block -split "`n" | Where-Object { $_ -like 'event: *' } | Select-Object -First 1)
    $data = ($block -split "`n" | Where-Object { $_ -like 'data: *' } | Select-Object -First 1)
    if ($name -and $data) { [pscustomobject]@{ event = $name.Substring(7); data = ($data.Substring(6) | ConvertFrom-Json -Depth 32) } }
  }
  $last = @($events | Where-Object { $_.event -in 'done', 'error' }) | Select-Object -Last 1
  if (-not $last) { throw "the stream ended without a done or error event ($(@($events).Count) events)" }
  if ($last.event -eq 'error') { throw "error event: $(Get-Field $last.data 'message')" }
  return $last.data
}

$session = $null
Check 'healthz over HTTPS' {
  $h = Invoke-RestMethod -Uri "$base/healthz" -TimeoutSec 30
  if (-not $h.ok -or $h.deployment -ne $o.gpt6Deployment) { throw "unexpected answer: $($h | ConvertTo-Json -Compress)" }
  [ordered]@{ deployment = $h.deployment; uptime_s = $h.uptime_s }
}
Check 'HTTP redirects to HTTPS' {
  # Invoke-WebRequest -MaximumRedirection 0 throws on a 3xx under ErrorAction Stop; HttpClient reports it as it is.
  $handler = [Net.Http.HttpClientHandler]::new()
  $handler.AllowAutoRedirect = $false
  $client = [Net.Http.HttpClient]::new($handler)
  $client.Timeout = [TimeSpan]::FromSeconds(30)
  try {
    $r = $client.GetAsync("http://$($o.fqdn)/").GetAwaiter().GetResult()
    $status = [int]$r.StatusCode
    $location = [string]$r.Headers.Location
  } finally { $client.Dispose() }
  if ($status -ne 308 -or -not $location.StartsWith("https://$($o.fqdn)/")) { throw "status $status, Location $location" }
  [ordered]@{ status = $status; location = $location }
}
Check 'wrong password is rejected' {
  $body = @{ username = $o.portalUsername; password = 'not-the-password' } | ConvertTo-Json
  $r = Invoke-WebRequest -Uri "$base/api/login" -Method Post -ContentType 'application/json' -Body $body -SkipHttpErrorCheck -TimeoutSec 30
  if ($r.StatusCode -ne 401) { throw "status $($r.StatusCode)" }
  [ordered]@{ status = $r.StatusCode }
}
Check 'sign in' {
  $body = @{ username = $o.portalUsername; password = $password } | ConvertTo-Json
  $r = Invoke-RestMethod -Uri "$base/api/login" -Method Post -ContentType 'application/json' -Body $body -SessionVariable s -TimeoutSec 30
  if (-not $r.ok) { throw 'sign-in did not return ok' }
  $script:session = $s
  [ordered]@{ user = $r.user; role = $r.role }
}
$ids = @()
Check '15 scenarios' {
  $r = Invoke-RestMethod -Uri "$base/api/scenarios" -WebSession $session -TimeoutSec 30
  $script:ids = @($r.scenarios | ForEach-Object { $_.id })
  if ($ids.Count -ne 15) { throw "$($ids.Count) scenarios" }
  [ordered]@{ scenarios = $ids.Count }
}
foreach ($lang in 'zh', 'en') {
  Check "pre-generated STEP solids ($lang)" {
    $found = 0
    $missing = foreach ($id in $ids) {
      $r = Invoke-WebRequest -Uri "$base/api/cad/cache/${id}?lang=$lang" -WebSession $session -SkipHttpErrorCheck -TimeoutSec 60
      $ok = $r.StatusCode -eq 200
      if ($ok -and $lang -eq 'en') { $ok = ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json).files.step -like '*lang=en*' }
      if ($ok) { $found++ } else { $id }
    }
    if ($found -ne $ids.Count) { throw "missing: $($missing -join ', ')" }
    [ordered]@{ solids = $found }
  }
}
Check 'GPT-6 round trip (managed identity)' {
  $r = Invoke-RestMethod -Uri "$base/api/connection/test?lang=en" -Method Post -WebSession $session -TimeoutSec 120
  if (-not $r.ok) { throw "$(Get-Field $r 'error')" }
  [ordered]@{ deployment = $r.deployment; actual_model = (Get-Field $r 'actual_model'); latency_s = $r.latency_s }
}

if ($Full) {
  Check 'Generate STEP live (GPT-6 + OCCT)' {
    $body = @{ scenario_id = 'coldplate'; lang = 'en'; reasoning_effort = 'none'
               prompt = 'An aluminium battery cold plate, 320 x 180 x 12 mm, with six S-shaped coolant channels and two fittings.' } | ConvertTo-Json
    $r = Invoke-WebRequest -Uri "$base/api/cad" -Method Post -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 1200
    $d = Read-Sse $r
    $step = Invoke-WebRequest -Uri "$base$($d.files.step)" -WebSession $session -TimeoutSec 120
    $bytes = $step.RawContentStream.ToArray()
    $head = [Text.Encoding]::ASCII.GetString($bytes, 0, [Math]::Min(12, $bytes.Length))
    if ($head -ne 'ISO-10303-21') { throw "the STEP file starts with '$head'" }
    $file = Join-Path $StateDir 'verify-live.step'
    [IO.File]::WriteAllBytes($file, $bytes)
    $mass = @($d.metrics | Where-Object { $_ -and (Get-Field $_ 'unit') -eq 'kg' } | ForEach-Object { $_.value }) | Select-Object -First 1
    $usage = Get-Field $d 'usage'
    [ordered]@{ attempts = $d.attempts; latency_s = $d.latency_s; occt_s = (Get-Field $d.raw 'elapsed_s'); solids = (Get-Field $d.raw 'solids')
                faces = (Get-Field $d.raw 'faces'); mass_kg = $mass; step_bytes = $bytes.Length; reasoning_effort = (Get-Field $d 'reasoning_effort')
                prompt_tokens = (Get-Field $usage 'prompt_tokens'); completion_tokens = (Get-Field $usage 'completion_tokens')
                reasoning_tokens = (Get-Field (Get-Field $usage 'completion_tokens_details') 'reasoning_tokens'); saved = $file }
  }
  if ($o.imageDeployment) {
    Check 'concept image (gpt-image)' {
      $body = @{ prompt = 'Product photo of an aluminium liquid cold plate for an EV battery pack, studio lighting'; provider = 'gpt-image'
                 size = '1024x1024'; quality = 'low'; lang = 'en' } | ConvertTo-Json
      $r = Invoke-WebRequest -Uri "$base/api/concept" -Method Post -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 600
      $d = Read-Sse $r
      $png = [Convert]::FromBase64String(($d.image -replace '^data:image/png;base64,', ''))
      if ($png.Length -lt 8 -or $png[1] -ne 0x50 -or $png[2] -ne 0x4E -or $png[3] -ne 0x47) { throw 'the image is not a PNG' }
      $file = Join-Path $StateDir 'verify-concept.png'
      [IO.File]::WriteAllBytes($file, $png)
      [ordered]@{ png_bytes = $png.Length; latency_s = (Get-Field $d 'latency_s'); model = (Get-Field $d 'model'); saved = $file }
    }
  }
}

$failed = @($checks | Where-Object { $_.status -ne 'PASS' })
$report = [ordered]@{ script = 'infra/verify.ps1'; resourceGroup = $ResourceGroup; url = "$base/"; full = $Full.IsPresent
                      startedAt = $started.ToString('o'); finishedAt = (Get-Date).ToString('o')
                      status = $(if ($failed.Count) { 'FAIL' } else { 'PASS' }); checks = $checks }
$reportFile = Join-Path $StateDir ('verify-{0:yyyyMMdd-HHmmss}.json' -f $started)
[IO.File]::WriteAllText($reportFile, ($report | ConvertTo-Json -Depth 8), $utf8)
Write-Host ''
Write-Host "$($checks.Count - $failed.Count) of $($checks.Count) checks passed; report: $reportFile"
exit $(if ($failed.Count) { 1 } else { 0 })
