# Parameters
param(
    [string]$EnvironmentName = "dev",
    [string]$Location = "eastus"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Azure Developer CLI Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if azd is installed
Write-Host "Checking Azure Developer CLI..." -ForegroundColor Yellow
if (!(Get-Command azd -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Azure Developer CLI (azd) not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install it with:" -ForegroundColor Yellow
    Write-Host "  winget install microsoft.azd" -ForegroundColor White
    Write-Host ""
    Write-Host "Or visit: https://aka.ms/install-azd" -ForegroundColor Cyan
    exit 1
}
Write-Host "✓ Azure Developer CLI found" -ForegroundColor Green
Write-Host ""

# Initialize environment
Write-Host "Initializing Azure Developer CLI environment..." -ForegroundColor Yellow
azd env new $EnvironmentName

# Set location
Write-Host "Setting location to $Location..." -ForegroundColor Yellow
azd env set AZURE_LOCATION $Location

# Deploy
Write-Host ""
Write-Host "Starting deployment..." -ForegroundColor Yellow
Write-Host "This will:" -ForegroundColor Cyan
Write-Host "  1. Provision Azure resources (App Service, Application Insights)" -ForegroundColor Gray
Write-Host "  2. Build and package your application" -ForegroundColor Gray
Write-Host "  3. Deploy to Azure Web App" -ForegroundColor Gray
Write-Host "  4. Configure HTTPS and monitoring" -ForegroundColor Gray
Write-Host ""

azd up

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "View your app:" -ForegroundColor Cyan
azd env get-values | Select-String "WEB_URI"
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Cyan
Write-Host "  azd monitor        - View application logs and metrics" -ForegroundColor Gray
Write-Host "  azd deploy         - Deploy code changes" -ForegroundColor Gray
Write-Host "  azd down           - Delete all Azure resources" -ForegroundColor Gray
Write-Host ""
