# One-shot: move the tester pack under the repo, drop the local test junction, verify the tree.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$parent = Split-Path -Parent $root
$pack = Join-Path $parent 'andre-us-testpack'
$dest = Join-Path $root 'testpack'

if ((Test-Path -LiteralPath $pack) -and -not (Test-Path -LiteralPath $dest)) {
  Move-Item -LiteralPath $pack -Destination $dest
}
# The fabric run was only a junction used to prove render.py on real data; the repo ships no run until Andre's arrives.
$junction = Join-Path $root 'runs\fabric-language-20260921-mai'
if (Test-Path -LiteralPath $junction) {
  $item = Get-Item -LiteralPath $junction -Force
  if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { $item.Delete() } else { Write-Output "NOT_A_JUNCTION_LEFT_ALONE $junction" }
}
Remove-Item -LiteralPath (Join-Path $root 'README.md') -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $root 'images') -Recurse -Force -ErrorAction SilentlyContinue

Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { $_.FullName -notmatch '__pycache__|\\runs\\' } |
  ForEach-Object { '{0,8}  {1}' -f $_.Length, $_.FullName.Substring($root.Length + 1) }
