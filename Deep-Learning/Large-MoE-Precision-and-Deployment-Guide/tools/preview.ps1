param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
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
main { max-width: 1216px; margin: auto; padding: 32px 24px 80px; overflow-wrap: anywhere; }
h1 { font-size: 30px; line-height: 1.35; border-bottom: 1px solid #d1d9e0; padding-bottom: 16px; }
h2 { font-size: 24px; border-bottom: 1px solid #d1d9e0; padding-bottom: 8px; margin-top: 36px; }
h3 { font-size: 20px; margin-top: 28px; }
a { color: #0969da; text-decoration: none; } a:hover { text-decoration: underline; }
img { max-width: 100%; height: auto; }
pre { padding: 16px; background: #f6f8fa; overflow-x: auto; border-radius: 4px; }
code { font: 0.9em/1.6 Consolas, monospace; background: #eff1f3; }
pre code { background: transparent; }
.table-wrap { overflow-x: auto; border: 1px solid #d1d9e0; margin: 18px 0; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 10px 12px; border: 1px solid #d1d9e0; min-width: 150px; vertical-align: top; }
th { background: #eef3f6; text-align: left; }
tr:nth-child(even) td { background: #f6f8fa; }
.table-wrap.wide table { width: 2040px; table-layout: fixed; }
.table-wrap.wide th:first-child, .table-wrap.wide td:first-child { position: sticky; left: 0; background: #edf4f8; width: 200px; }
.diagram-wrap { overflow-x: auto; margin: 18px 0; border: 1px solid #d1d9e0; }
.mermaid { min-width: 960px; padding: 12px; }
.katex-display { overflow-x: auto; overflow-y: hidden; padding: 8px 0; }
.render-error { color: #a40e26; padding: 12px; border: 1px solid #a40e26; }
@media (max-width: 600px) { main { padding: 16px 12px 48px; } h1 { font-size: 25px; } h2 { font-size: 22px; } }
</style>
</head>
<body><main>__BODY__</main>
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
  wrapper.className = 'table-wrap' + (table.rows[0]?.cells.length === 10 ? ' wide' : '');
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
    mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'neutral', flowchart: { htmlLabels: false }, themeVariables: { fontFamily: 'Segoe UI, Microsoft YaHei, sans-serif' } });
    await mermaid.run();
    if (document.querySelectorAll('.mermaid svg').length !== blocks.length) throw new Error('Mermaid diagram was not rendered.');
  }
  const { default: renderMathInElement } = await import('https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.mjs');
  renderMathInElement(document.querySelector('main'), { delimiters: [{left: '$$', right: '$$', display: true}, {left: '\\[', right: '\\]', display: true}], throwOnError: true });
  document.body.dataset.renderStatus = 'complete';
} catch (error) {
  document.body.dataset.renderStatus = 'failed';
  const warning = document.createElement('p'); warning.className = 'render-error'; warning.textContent = 'Preview rendering failed: ' + error.message;
  document.querySelector('main').prepend(warning);
}
</script>
</body></html>
'@

$records = foreach ($name in @('README.md', 'README_CN.md', 'VALIDATION.md', 'VALIDATION_CN.md')) {
    $source = Join-Path $projectRoot $name
    $markdown = Get-Content -LiteralPath $source -Raw -Encoding utf8
    $body = (ConvertFrom-Markdown -InputObject $markdown).Html
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
$receipt = [ordered]@{ GeneratedUtc = [DateTime]::UtcNow.ToString('o'); Renderer = 'PowerShell ConvertFrom-Markdown'; Documents = @($records) }
$receipt | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $outputRoot 'render-receipt.json') -Encoding utf8
$receipt | ConvertTo-Json -Depth 4