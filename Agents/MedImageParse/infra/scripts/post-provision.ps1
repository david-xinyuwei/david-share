# Post-provision script
# This script runs after infrastructure is provisioned

Write-Host "Post-provision script started..." -ForegroundColor Green

# Get the service name from azd
$serviceName = "web"

Write-Host "Deploying service: $serviceName" -ForegroundColor Cyan

# Deploy the application using azd
azd deploy $serviceName

Write-Host "Post-provision script completed!" -ForegroundColor Green
