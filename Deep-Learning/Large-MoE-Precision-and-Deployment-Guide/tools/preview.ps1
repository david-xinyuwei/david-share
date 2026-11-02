param(
    [Parameter(Mandatory = $true)]
  [string]$OutputDirectory,
    [switch]$ExportDiagrams,
    [switch]$GitHubMarkdown,
    # GitHub repository used as the `context` of the Markdown API call (-GitHubMarkdown). Only affects
    # how #123 / @user references resolve; override when rendering from a fork.
    [string]$GitHubContext = 'david-xinyuwei/david-share'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
[System.IO.Directory]::CreateDirectory($outputRoot) | Out-Null
$imageRoot = Join-Path $outputRoot 'images'
[System.IO.Directory]::CreateDirectory($imageRoot) | Out-Null
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'images') -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $imageRoot $_.Name)
}
$dataRoot = Join-Path $outputRoot 'data'
[System.IO.Directory]::CreateDirectory($dataRoot) | Out-Null
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'data') -File | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $dataRoot $_.Name)
}

$template = @'
<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<style>
body { margin: 0; color: #1f2328; background: #ffffff; font: 16px/1.65 "Segoe UI", "Microsoft YaHei", sans-serif; }
main { box-sizing: border-box; max-width: 1092px; margin: auto; padding: 32px 40px 80px; overflow-wrap: break-word; }
h1 { font-size: 30px; line-height: 1.35; border-bottom: 1px solid #d1d9e0; padding-bottom: 16px; }
h2 { font-size: 24px; border-bottom: 1px solid #d1d9e0; padding-bottom: 8px; margin-top: 36px; }
h3 { font-size: 20px; margin-top: 28px; }
a { color: #0969da; text-decoration: none; } a:hover { text-decoration: underline; }
img { max-width: 100%; height: auto; }
pre { padding: 16px; background: #f6f8fa; overflow-x: auto; border-radius: 4px; }
code { font: 0.9em/1.6 Consolas, monospace; background: #eff1f3; }
pre code { background: transparent; }
.table-wrap { overflow-x: auto; margin: 18px 0; }
table { display: block; width: max-content; max-width: 100%; overflow-x: auto; border-collapse: collapse; font-size: 16px; }
th, td { padding: 6px 13px; border: 1px solid #d1d9e0; vertical-align: top; overflow-wrap: break-word; word-break: normal; }
th { background: #eef3f6; text-align: left; }
tr:nth-child(even) td { background: #f6f8fa; }
.diagram-wrap { overflow-x: auto; margin: 18px 0; border: 1px solid #d1d9e0; }
.mermaid { min-width: 960px; padding: 12px; }
.katex-display { position: relative; overflow-x: auto; overflow-y: hidden; padding: 8px 0; } /* relative: keep KaTeX's absolutely positioned MathML copy inside the scroll box, otherwise it widens the page at 390 px */
.render-error { color: #a40e26; padding: 12px; border: 1px solid #a40e26; }
@media (max-width: 600px) { main { padding: 16px 32px 48px; } h1 { font-size: 25px; } h2 { font-size: 22px; } }
</style>
</head>
<body><main>__BODY__</main>
<script id="diagram-export" type="application/json">[]</script>
<script type="module">
for (const heading of document.querySelectorAll('h1,h2,h3,h4')) {
  const slug = heading.textContent.toLowerCase().replace(/[^\p{L}\p{N}_\- ]/gu, '').trim().replace(/ /g, '-');
  if (slug && !document.getElementById(slug)) {
    const anchor = document.createElement('a'); anchor.id = slug; heading.before(anchor);
  }
}
for (const link of document.querySelectorAll('a[href]')) {
  const href = link.getAttribute('href');
  if (/^(README(?:_CN)?|VALIDATION(?:_CN)?)\.md(?:#.*)?$/.test(href)) link.setAttribute('href', href.replace('.md', '.html'));
}
for (const table of document.querySelectorAll('table')) {
  const wrapper = document.createElement('div');
  wrapper.className = 'table-wrap' + (/^(组件|Part)$/.test(table.rows[0]?.cells[0]?.textContent.trim() ?? '') ? ' precision' : '');
  table.replaceWith(wrapper); wrapper.append(table);
}
try {
  const blocks = document.querySelectorAll('pre.mermaid, pre code.language-mermaid');
  for (const block of blocks) {
    const wrapper = document.createElement('div'); wrapper.className = 'diagram-wrap';
    const diagram = document.createElement('div'); diagram.className = 'mermaid'; diagram.textContent = block.textContent;
    wrapper.append(diagram); (block.matches('pre') ? block : block.parentElement).replaceWith(wrapper);
  }
  if (blocks.length) {
    const { default: mermaid } = await import('https://cdn.jsdelivr.net/npm/mermaid@11.12.0/dist/mermaid.esm.min.mjs');
    mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral', htmlLabels: false, deterministicIds: true, deterministicIDSeed: 'moe-docs', flowchart: { htmlLabels: false }, themeVariables: { fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif' } });
    await document.fonts.ready;
    const exported = [];
    for (const [index, diagram] of [...document.querySelectorAll('.mermaid')].entries()) {
      const { svg } = await mermaid.render(`moe-diagram-${index}`, diagram.textContent);
      diagram.innerHTML = svg;
      exported.push(new XMLSerializer().serializeToString(diagram.querySelector('svg')));
    }
    document.getElementById('diagram-export').textContent = JSON.stringify(exported);
    if (document.querySelectorAll('.mermaid svg').length !== blocks.length) throw new Error('Mermaid diagram was not rendered.');
  }
  if (document.body.dataset.exportOnly !== 'true') {
    const { default: renderMathInElement } = await import('https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.mjs');
    // GitHub renders $$...$$ blocks only. The JS string '\[' is just '[' and turned every [T2]/[M1] citation
    // into display math in the local preview (observed 2026-11-02); match the literal "\[" so citations stay text.
    renderMathInElement(document.querySelector('main'), { delimiters: [{left: '$$', right: '$$', display: true}, {left: '\\[', right: '\\]', display: true}], throwOnError: true });
  }
  document.body.dataset.renderStatus = 'complete';
} catch (error) {
  document.body.dataset.renderStatus = 'failed';
  const warning = document.createElement('p'); warning.className = 'render-error'; warning.textContent = 'Preview rendering failed: ' + error.message;
  document.querySelector('main').prepend(warning);
}
</script>
</body></html>
'@

if ($ExportDiagrams) {
  $sources = @()
  foreach ($language in @('en', 'zh')) {
    $document = if ($language -eq 'zh') { 'README_CN.md' } else { 'README.md' }
    $markdown = [IO.File]::ReadAllText((Join-Path $projectRoot $document), [Text.Encoding]::UTF8)
    $blocks = [regex]::Matches($markdown, '(?ms)^```mermaid\r?\n(?<source>.*?)^```[ \t]*\r?$')
    $names = @("nvfp4-execution-$language", "mi300x-test-topology-$language")
    for ($index = 0; $index -lt $names.Count; $index++) {
      $sourcePath = Join-Path $projectRoot "images/$($names[$index]).mmd"
      if (-not (Test-Path -LiteralPath $sourcePath)) {
        if ($blocks.Count -ne 2) { throw "Expected two source diagrams in $document" }
        [IO.File]::WriteAllText($sourcePath, $blocks[$index].Groups['source'].Value.TrimEnd() + "`n", [Text.UTF8Encoding]::new($false))
      }
      $sources += [ordered]@{
        Name = $names[$index]
        Language = $language
        Kind = $index
        Path = $sourcePath
        Text = [IO.File]::ReadAllText($sourcePath, [Text.Encoding]::UTF8)
      }
    }
  }
  $body = ($sources | ForEach-Object { '<pre class="mermaid">' + [Net.WebUtility]::HtmlEncode($_.Text) + '</pre>' }) -join "`n"
  $exportPage = Join-Path $outputRoot 'diagram-export.html'
  $html = $template.Replace('__LANG__', 'en').Replace('__TITLE__', 'Static diagram export').Replace('__BODY__', $body).Replace('<body>', '<body data-export-only="true">')
  [IO.File]::WriteAllText($exportPage, $html, [Text.UTF8Encoding]::new($false))
  $edge = @('C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', 'C:\Program Files\Microsoft\Edge\Application\msedge.exe') | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
  if (-not $edge) { throw 'Microsoft Edge is required to export static diagrams.' }
  $start = [Diagnostics.ProcessStartInfo]::new($edge)
  $start.UseShellExecute = $false
  $start.RedirectStandardOutput = $true
  $start.RedirectStandardError = $true
  $start.StandardOutputEncoding = [Text.Encoding]::UTF8
  $start.StandardErrorEncoding = [Text.Encoding]::UTF8
  foreach ($argument in @('--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--dump-dom', '--virtual-time-budget=10000', ([Uri]$exportPage).AbsoluteUri)) {
    $start.ArgumentList.Add($argument)
  }
  $process = [Diagnostics.Process]::Start($start)
  $stdout = $process.StandardOutput.ReadToEndAsync()
  $stderr = $process.StandardError.ReadToEndAsync()
  if (-not $process.WaitForExit(60000)) {
    $process.Kill($true)
    throw 'Static diagram export exceeded 60 seconds.'
  }
  $rendered = $stdout.GetAwaiter().GetResult()
  [IO.File]::WriteAllText((Join-Path $outputRoot 'diagram-export.stderr.log'), $stderr.GetAwaiter().GetResult(), [Text.UTF8Encoding]::new($false))
  if ($process.ExitCode -ne 0 -or $rendered -notmatch 'data-render-status="complete"') { throw 'Static diagram rendering did not complete; inspect diagram-export.stderr.log.' }
  $match = [regex]::Match($rendered, '<script id="diagram-export" type="application/json">(?<json>.*?)</script>', [Text.RegularExpressions.RegexOptions]::Singleline)
  if (-not $match.Success) { throw 'The renderer did not return diagram data.' }
  $svgs = @($match.Groups['json'].Value | ConvertFrom-Json)
  if ($svgs.Count -ne $sources.Count) { throw 'The renderer returned an incomplete diagram set.' }
  $ledgerPath = Join-Path $projectRoot 'data/visual-evidence.json'
  $ledger = [IO.File]::ReadAllText($ledgerPath, [Text.Encoding]::UTF8) | ConvertFrom-Json -AsHashtable
  $entries = @()
  for ($index = 0; $index -lt $sources.Count; $index++) {
    $source = $sources[$index]
    $asset = "images/$($source.Name).svg"
    $assetPath = Join-Path $projectRoot $asset
    $svg = [xml]::new()
    $svg.LoadXml($svgs[$index])
    $viewBox = $svg.DocumentElement.GetAttribute('viewBox').Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
    if ($viewBox.Count -ne 4 -or $svg.DocumentElement.LocalName -ne 'svg') { throw "Invalid rendered SVG: $asset" }
    if ($svg.SelectNodes('//*[local-name()="foreignObject"]').Count) { throw "HTML labels are not portable SVG: $asset" }
    [IO.File]::WriteAllText($assetPath, $svgs[$index] + "`n", [Text.UTF8Encoding]::new($false))
    $original = $ledger.visuals | Where-Object { $_.source_class -eq $(if ($source.Kind -eq 0) { 'original_cross_source_explanation' } else { 'original_test_topology' }) } | Select-Object -First 1
    if (-not $original) { throw 'The original diagram provenance is missing.' }
    $entry = [ordered]@{}
    foreach ($key in $original.Keys) { $entry[$key] = $original[$key] }
    $entry.asset = $asset
    $entry.language = $source.Language
    $entry.generator = 'tools/preview.ps1 -ExportDiagrams'
    $entry.source_asset = "images/$($source.Name).mmd"
    $entry.source_sha256 = (Get-FileHash -LiteralPath $source.Path -Algorithm SHA256).Hash.ToLowerInvariant()
    $entry.sha256 = (Get-FileHash -LiteralPath $assetPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $entry.width = [Math]::Ceiling([double]::Parse($viewBox[2], [Globalization.CultureInfo]::InvariantCulture))
    $entry.height = [Math]::Ceiling([double]::Parse($viewBox[3], [Globalization.CultureInfo]::InvariantCulture))
    $entries += $entry
    Copy-Item -LiteralPath $assetPath, $source.Path -Destination $imageRoot
  }
  $ledger.visuals = @($ledger.visuals | Where-Object { $_.source_class -notin @('original_cross_source_explanation', 'original_test_topology') }) + $entries
  [IO.File]::WriteAllText($ledgerPath, ($ledger | ConvertTo-Json -Depth 20) + "`n", [Text.UTF8Encoding]::new($false))
  Copy-Item -LiteralPath $ledgerPath -Destination $dataRoot
  Write-Output "STATIC_DIAGRAM_EXPORT_PASS count=$($svgs.Count)"
}

$records = foreach ($name in @('README.md', 'README_CN.md', 'VALIDATION.md', 'VALIDATION_CN.md')) {
    $source = Join-Path $projectRoot $name
    $markdown = Get-Content -LiteralPath $source -Raw -Encoding utf8
  if ($GitHubMarkdown) {
    $request = @{ text = $markdown; mode = 'gfm'; context = $GitHubContext } | ConvertTo-Json -Compress
    $body = Invoke-RestMethod -Method Post -Uri 'https://api.github.com/markdown' -Headers @{ Accept = 'text/html'; 'User-Agent' = 'MoE-document-preview' } -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($request)) -TimeoutSec 30
  } else {
    $body = (ConvertFrom-Markdown -InputObject $markdown).Html
  }
    $language = if ($name.Contains('_CN')) { 'zh-CN' } else { 'en' }
    $html = $template.Replace('__LANG__', $language).Replace('__TITLE__', $name).Replace('__BODY__', $body)
    $destination = Join-Path $outputRoot ($name.Replace('.md', '.html'))
    [System.IO.File]::WriteAllText($destination, $html, [System.Text.UTF8Encoding]::new($false))
    [ordered]@{
        Source = $name
        SourceSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash
        Output = $destination
        OutputSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash
    }
}
$renderer = if ($GitHubMarkdown) { 'GitHub Markdown API (gfm)' } else { 'PowerShell ConvertFrom-Markdown' }
$receipt = [ordered]@{ GeneratedUtc = [DateTime]::UtcNow.ToString('o'); Renderer = $renderer; Documents = @($records) }
$receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $outputRoot 'render-receipt.json') -Encoding utf8
$receipt | ConvertTo-Json -Depth 4