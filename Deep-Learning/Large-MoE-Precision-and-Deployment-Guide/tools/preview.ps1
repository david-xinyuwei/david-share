param(
    [Parameter(Mandatory = $true)]
  [string]$OutputDirectory,
    [switch]$ExportDiagrams,
    [switch]$GitHubMarkdown,
    # GitHub repository used as the `context` of the Markdown API call (-GitHubMarkdown). Only affects
    # how #123 / @user references resolve; override when rendering from a fork.
    [string]$GitHubContext = 'david-xinyuwei/david-share',
    [string]$PythonExecutable = 'python'
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
.table-wrap { max-width: 100%; overflow-x: auto; overscroll-behavior-x: contain; margin: 18px 0; }
table { width: 100%; table-layout: auto; border-collapse: collapse; font-size: 14px; line-height: 1.5; }
th, td { padding: 7px 10px; border: 1px solid #d1d9e0; vertical-align: top; overflow-wrap: normal; word-break: normal; }
td code, th code { font-size: 0.9em; white-space: normal; overflow-wrap: anywhere; }
th { background: #eef3f6; text-align: left; }
tr:nth-child(even) td { background: #f6f8fa; }
.precision th:first-child { width: 20%; }
.budget th:nth-child(1) { width: 20%; }
.budget th:nth-child(2) { width: 16%; }
.budget th:nth-child(3), .budget th:nth-child(4), .budget th:nth-child(5) { width: 10%; }
.budget th:nth-child(6) { width: 34%; }
.performance th { min-width: 6em; }
.performance th:nth-child(1) { width: 19%; }
.performance th:nth-child(2) { width: 9%; }
.performance th:nth-child(3) { width: 14%; }
.performance th:nth-child(4) { width: 16%; }
.performance th:nth-child(5) { width: 22%; }
.performance th:nth-child(6), .performance th:nth-child(7) { width: 10%; }
.wide-comparison th { min-width: 6em; }
.reading-map th:first-child { width: 34%; }
.diagram-wrap { overflow-x: auto; margin: 18px 0; border: 1px solid #d1d9e0; }
.mermaid { min-width: 960px; padding: 12px; }
.katex-display { position: relative; overflow-x: auto; overflow-y: hidden; padding: 8px 0; } /* relative: keep KaTeX's absolutely positioned MathML copy inside the scroll box, otherwise it widens the page at 390 px */
.render-error { color: #a40e26; padding: 12px; border: 1px solid #a40e26; }
@media (max-width: 600px) { main { padding: 16px 16px 48px; } h1 { font-size: 25px; } h2 { font-size: 22px; } }
</style>
</head>
<body><main>__BODY__</main>
<script id="diagram-export" type="application/json">[]</script>
<script type="module">
const sourceUri = __SOURCE_URI__;
for (const heading of document.querySelectorAll('h1,h2,h3,h4')) {
  const slug = heading.textContent.toLowerCase().replace(/[^\p{L}\p{N}_\- ]/gu, '').trim().replace(/ /g, '-');
  if (slug && !document.getElementById(slug)) {
    const anchor = document.createElement('a'); anchor.id = slug; heading.before(anchor);
  }
}
for (const link of document.querySelectorAll('a[href]')) {
  const href = link.getAttribute('href');
  if (/^(README(?:_CN)?|VALIDATION(?:_CN)?)\.md(?:#.*)?$/.test(href)) {
    link.setAttribute('href', href.replace('.md', '.html'));
  } else if (href && !href.startsWith('#') && !/^[a-z][a-z0-9+.-]*:/i.test(href)) {
    link.setAttribute('href', new URL(href, sourceUri).href);
  }
}
for (const table of document.querySelectorAll('table')) {
  const wrapper = document.createElement('div');
  const firstHeader = table.rows[0]?.cells[0]?.textContent.trim() ?? '';
  const headers = table.rows[0]?.textContent ?? '';
  wrapper.className = 'table-wrap';
  if (/^(组件|Part)$/.test(firstHeader)) wrapper.classList.add('precision');
  if (/MXFP4/.test(firstHeader)) wrapper.classList.add('performance');
  if (table.rows[0].cells.length >= 8) wrapper.classList.add('wide-comparison');
  if (/HBM/.test(headers) && table.rows[0].cells.length === 6) wrapper.classList.add('budget');
  if (/^(想要|You want|阅读目的|Reader task)/.test(firstHeader)) wrapper.classList.add('reading-map');
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
  & $PythonExecutable (Join-Path $projectRoot 'tools/build_layout_figure.py') --topology-only
  if ($LASTEXITCODE -ne 0) { throw 'MI300X topology generation failed.' }
  foreach ($language in @('en', 'zh')) {
    Copy-Item -LiteralPath (Join-Path $projectRoot "images/mi300x-test-topology-$language.svg") -Destination $imageRoot
  }
  Copy-Item -LiteralPath (Join-Path $projectRoot 'data/visual-evidence.json') -Destination $dataRoot
  Write-Output 'STATIC_DIAGRAM_EXPORT_PASS count=2'
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
    $sourceUriJson = ([Uri]$source).AbsoluteUri | ConvertTo-Json -Compress
    $html = $template.Replace('__LANG__', $language).Replace('__TITLE__', $name).Replace('__BODY__', $body).Replace('__SOURCE_URI__', $sourceUriJson)
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