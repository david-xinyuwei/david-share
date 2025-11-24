# 自动化 SSH 执行脚本
param(
    [Parameter(Mandatory=$true)]
    [string]$Command
)

$password = "2"
$server = "root@a10gpuvm.canadacentral.cloudapp.azure.com"

# 使用 plink (如果有) 或 expect
$plink = Get-Command plink -ErrorAction SilentlyContinue

if ($plink) {
    echo y | plink -pw $password $server $Command
} else {
    # 使用交互式方式
    $secpasswd = ConvertTo-SecureString $password -AsPlainText -Force
    Write-Host "Executing: $Command"
    Write-Host "Password will be prompted..."
    ssh $server $Command
}
