# Azure Deployment Prerequisites Check Script
# This script verifies all prerequisites for Azure deployment

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Azure Deployment Prerequisites Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allChecksPassed = $true

# Check 1: Azure CLI
Write-Host "1. Checking Azure CLI..." -ForegroundColor Yellow
try {
    $azVersion = az --version 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [PASS] Azure CLI installed" -ForegroundColor Green
        $versionLine = ($azVersion -split "`n")[0]
        Write-Host "   Version: $versionLine" -ForegroundColor Gray
    } else {
        throw "Azure CLI not found"
    }
} catch {
    Write-Host "   [FAIL] Azure CLI NOT installed" -ForegroundColor Red
    Write-Host "   Install with: winget install -e --id Microsoft.AzureCLI" -ForegroundColor Yellow
    Write-Host "   Or visit: https://aka.ms/installazurecliwindows" -ForegroundColor Yellow
    $allChecksPassed = $false
}

# Check 2: Azure Login Status
Write-Host ""
Write-Host "2. Checking Azure login status..." -ForegroundColor Yellow
try {
    $accountJson = az account show 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        $account = $accountJson | ConvertFrom-Json
        Write-Host "   [PASS] Logged in to Azure" -ForegroundColor Green
        Write-Host "   Subscription: $($account.name)" -ForegroundColor Gray
        Write-Host "   User: $($account.user.name)" -ForegroundColor Gray
    } else {
        throw "Not logged in"
    }
} catch {
    Write-Host "   [FAIL] NOT logged in to Azure" -ForegroundColor Red
    Write-Host "   Run: az login" -ForegroundColor Yellow
    $allChecksPassed = $false
}

# Check 3: Permissions (if logged in)
if ($allChecksPassed) {
    Write-Host ""
    Write-Host "3. Checking Azure permissions..." -ForegroundColor Yellow
    $testRG = "test-permissions-check-$(Get-Random -Minimum 1000 -Maximum 9999)"
    try {
        $createResult = az group create --name $testRG --location eastus 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   [PASS] Has required permissions" -ForegroundColor Green
            Write-Host "   Can create resource groups" -ForegroundColor Gray
            
            # Cleanup test resource
            Write-Host "   Cleaning up test resource..." -ForegroundColor Gray
            az group delete --name $testRG --yes --no-wait 2>&1 | Out-Null
        } else {
            throw "Permission denied"
        }
    } catch {
        Write-Host "   [FAIL] Insufficient permissions" -ForegroundColor Red
        Write-Host "   Contact your Azure administrator for 'Contributor' role" -ForegroundColor Yellow
        $allChecksPassed = $false
    }
}

# Check 4: Local Environment
Write-Host ""
Write-Host "4. Checking local environment..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    Write-Host "   [PASS] requirements.txt found" -ForegroundColor Green
} else {
    Write-Host "   [WARN] requirements.txt not found" -ForegroundColor Yellow
}

if (Test-Path "src\web_estimator.py") {
    Write-Host "   [PASS] src\web_estimator.py found" -ForegroundColor Green
} else {
    Write-Host "   [FAIL] src\web_estimator.py not found" -ForegroundColor Red
    $allChecksPassed = $false
}

if (Test-Path "startup.sh") {
    Write-Host "   [PASS] startup.sh found" -ForegroundColor Green
} else {
    Write-Host "   [WARN] startup.sh not found (will be created during deployment)" -ForegroundColor Yellow
}

# Final Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($allChecksPassed) {
    Write-Host "  SUCCESS: All prerequisites met!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "You are ready to deploy to Azure!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "  1. Review configuration in scripts\deploy-azure.ps1" -ForegroundColor Gray
    Write-Host "  2. Run deployment:" -ForegroundColor Gray
    Write-Host "     .\scripts\deploy-azure.ps1" -ForegroundColor Yellow
    Write-Host ""
    exit 0
} else {
    Write-Host "  FAILED: Prerequisites not met" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please fix the issues above and run this check again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "For detailed help, see:" -ForegroundColor White
    Write-Host "  AZURE_PREREQUISITES.md" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}
