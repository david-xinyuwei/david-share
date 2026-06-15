param(
  [Parameter(Mandatory = $true)]
  [string]$Pptx,

  [Parameter(Mandatory = $true)]
  [string]$OutDir
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $OutDir)) {
  New-Item -ItemType Directory -Path $OutDir | Out-Null
}

Get-ChildItem $OutDir -Filter "slide-*.png" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $OutDir -Filter "Slide*.PNG" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem $OutDir -Filter "*.PNG" -ErrorAction SilentlyContinue | Remove-Item -Force

$app = New-Object -ComObject PowerPoint.Application
$pres = $null

try {
  $pres = $app.Presentations.Open($Pptx, $true, $false, $false)
  $pres.Export($OutDir, "PNG", 1600, 900)
}
finally {
  if ($null -ne $pres) {
    $pres.Close()
  }
  $app.Quit()
}

foreach ($file in Get-ChildItem $OutDir -Filter "*.PNG") {
  if ($file.BaseName -match "(\d+)$") {
    $target = Join-Path $OutDir ("slide-{0:D2}.png" -f [int]$Matches[1])
    Rename-Item -LiteralPath $file.FullName -NewName $target -Force
  }
}
