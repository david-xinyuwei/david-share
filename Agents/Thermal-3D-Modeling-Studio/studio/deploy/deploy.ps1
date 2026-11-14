<#
.SYNOPSIS
  Deploy the Thermal 3D Modeling Studio to an Ubuntu VM via SSH (nginx TLS front -> uvicorn on 127.0.0.1:3005, user studio).
.EXAMPLE
  .\deploy\deploy.ps1 -SshHost azureuser@<vm-fqdn> -PublicUrl https://<vm-fqdn>/            # package + upload + install/restart
  .\deploy\deploy.ps1 -SshHost azureuser@<vm-fqdn> -PublicUrl https://<vm-fqdn>/ -Pregen    # ...and (re)build missing cached examples afterwards
.NOTES
  The host is prepared once with deploy/bootstrap_vm.sh; the VM's .env (owner studio, mode 600) is provisioned separately.
#>
param(
  [Parameter(Mandatory)][string]$SshHost,     # e.g. azureuser@<vm-fqdn>
  [int]$Port = 22,
  # extra ssh/scp -o options, e.g. 'HostName=<vm-ip>','HostKeyAlias=<vm-fqdn>'
  [string[]]$SshOption = @(),
  [Parameter(Mandatory)][string]$PublicUrl,   # e.g. https://<vm-fqdn>/
  [switch]$Pregen,
  [switch]$ForcePregen
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$tar = Join-Path ([IO.Path]::GetTempPath()) 'thermal-3d-studio.tar.gz'   # $env:TEMP exists only on Windows
if (Test-Path $tar) { Remove-Item $tar -Force }

Push-Location $root
try {
  # exclude local-only artefacts; .env lives on the VM (cache/, cad_cache/, render_cache/ are shipped so presets show immediately).
  tar -czf $tar --exclude=./.git --exclude=./.env '--exclude=[Pp]assword*' --exclude=./venv --exclude=./.venv --exclude=./__pycache__ --exclude=./cad_out --exclude=./static/vendor .
  if ($LASTEXITCODE -ne 0) { throw "tar failed" }
} finally { Pop-Location }
Write-Host ">> package: $([math]::Round((Get-Item $tar).Length/1KB)) KB"

$o = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20') + @($SshOption | ForEach-Object { '-o', $_ })
scp -P $Port @o -q $tar "${SshHost}:/tmp/thermal-3d-studio.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "scp failed" }

$remote = Get-Content -Raw (Join-Path $PSScriptRoot 'remote_install.sh')
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($remote.Replace("`r`n", "`n")))
ssh -p $Port @o $SshHost "echo $b64 | base64 -d | sudo bash"
if ($LASTEXITCODE -ne 0) { throw "remote install failed" }

if ($Pregen -or $ForcePregen) {
  $flag = if ($ForcePregen) { '--force' } else { '' }
  Write-Host ">> pre-generating cached examples (this calls GPT-6 once per scenario)..."
  ssh -p $Port @o $SshHost "sudo -u studio -H bash -c 'cd /opt/thermal-3d-studio && set -a && . ./.env && set +a && venv/bin/python pregen.py $flag'"
}
Write-Host ">> done: $PublicUrl"
