$ErrorActionPreference = 'Continue'
$p = 'G:\github\david-share\Agents\Hyperlight-MXC-Sandbox-Landscape\mxc-windows-smoke'
Set-Location -LiteralPath $p
$exe = '.\node_modules\@microsoft\mxc-sdk\bin\x64\wxc-exec.exe'
if (!(Test-Path $exe)) { npm install --no-audit --no-fund | Out-Null }

function Invoke-MxcConfig($name, $config) {
    $json = $config | ConvertTo-Json -Depth 12 -Compress
    $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json))
    Write-Host "=== $name ==="
    & $exe --config-base64 $b64 2>&1 | Tee-Object -FilePath "retest-python-node-$name.log"
    Write-Host "EXIT:$LASTEXITCODE"
}

function New-BaseConfig($id, $cmd) {
    return @{
        version = '0.4.0-alpha'
        containment = 'processcontainer'
        containerId = $id
        process = @{
            commandLine = $cmd
            timeout = 30000
        }
        network = @{ defaultPolicy = 'block' }
        processContainer = @{
            name = $id
            leastPrivilege = $false
            capabilities = @()
            ui = @{
                isolation = 'container'
                desktopSystemControl = $false
                systemSettings = 'none'
                ime = $false
            }
        }
    }
}

Invoke-MxcConfig 'py-relative' (New-BaseConfig 'py-relative' "python -c \"print('PY_RELATIVE_OK')\"")
Invoke-MxcConfig 'py-absolute' (New-BaseConfig 'py-absolute' "C:\Python312\python.exe -c \"print('PY_ABSOLUTE_OK')\"")
Invoke-MxcConfig 'node-relative' (New-BaseConfig 'node-relative' "node -e \"console.log('NODE_RELATIVE_OK')\"")
Invoke-MxcConfig 'node-absolute' (New-BaseConfig 'node-absolute' "\"C:\Program Files\nodejs\node.exe\" -e \"console.log('NODE_ABSOLUTE_OK')\"")
