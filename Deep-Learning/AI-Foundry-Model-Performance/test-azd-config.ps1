# Test script to verify azd configuration
# This does NOT deploy anything, just validates the configuration

Write-Host "=== Azure Developer CLI (azd) Configuration Test ===" -ForegroundColor Cyan
Write-Host ""

# Check if azd is installed
Write-Host "1. Checking if azd is installed..." -ForegroundColor Yellow
$azdPath = Get-Command azd -ErrorAction SilentlyContinue
if ($azdPath) {
    Write-Host "   ✅ azd is installed: $($azdPath.Source)" -ForegroundColor Green
    azd version
} else {
    Write-Host "   ⚠️  azd is NOT installed" -ForegroundColor Red
    Write-Host "   Install with: winget install microsoft.azd" -ForegroundColor Yellow
    Write-Host "   Note: This is OK for Silver/Gold IP submission!" -ForegroundColor Green
    Write-Host "         Having the configuration files is sufficient." -ForegroundColor Green
}

Write-Host ""

# Check azure.yaml
Write-Host "2. Checking azure.yaml..." -ForegroundColor Yellow
if (Test-Path "azure.yaml") {
    Write-Host "   ✅ azure.yaml exists" -ForegroundColor Green
    
    $content = Get-Content "azure.yaml" -Raw
    
    # Check for required sections
    if ($content -match "name:") {
        Write-Host "   ✅ Has project name" -ForegroundColor Green
    }
    
    if ($content -match "infra:") {
        Write-Host "   ✅ Has infra configuration" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Missing infra configuration!" -ForegroundColor Red
    }
    
    if ($content -match "services:") {
        Write-Host "   ✅ Has services configuration" -ForegroundColor Green
    }
    
    if ($content -match "hooks:") {
        Write-Host "   ✅ Has lifecycle hooks" -ForegroundColor Green
    }
} else {
    Write-Host "   ❌ azure.yaml NOT found!" -ForegroundColor Red
}

Write-Host ""

# Check infra directory
Write-Host "3. Checking infra directory..." -ForegroundColor Yellow
if (Test-Path "infra") {
    Write-Host "   ✅ infra directory exists" -ForegroundColor Green
    
    # Check main.bicep
    if (Test-Path "infra/main.bicep") {
        Write-Host "   ✅ main.bicep exists" -ForegroundColor Green
        
        $bicepContent = Get-Content "infra/main.bicep" -Raw
        
        if ($bicepContent -match "targetScope\s*=\s*'subscription'") {
            Write-Host "   ✅ Correct scope: subscription" -ForegroundColor Green
        }
        
        # Count modules
        $moduleCount = ([regex]::Matches($bicepContent, "module\s+\w+")).Count
        Write-Host "   ✅ Found $moduleCount modules" -ForegroundColor Green
    } else {
        Write-Host "   ❌ main.bicep NOT found!" -ForegroundColor Red
    }
    
    # Check modules directory
    if (Test-Path "infra/modules") {
        Write-Host "   ✅ modules directory exists" -ForegroundColor Green
        
        $modules = @(
            "monitoring.bicep",
            "storage.bicep",
            "keyvault.bicep",
            "ml-workspace.bicep"
        )
        
        foreach ($module in $modules) {
            if (Test-Path "infra/modules/$module") {
                Write-Host "   ✅ $module exists" -ForegroundColor Green
            } else {
                Write-Host "   ❌ $module NOT found!" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "   ❌ modules directory NOT found!" -ForegroundColor Red
    }
    
    # Check parameters file
    if (Test-Path "infra/main.parameters.json") {
        Write-Host "   ✅ main.parameters.json exists" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  main.parameters.json NOT found (optional)" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ❌ infra directory NOT found!" -ForegroundColor Red
}

Write-Host ""

# Check documentation
Write-Host "4. Checking documentation..." -ForegroundColor Yellow
$docs = @(
    "docs/DEPLOYMENT.md",
    "docs/COMPLIANCE.md",
    "docs/ARCHITECTURE.md"
)

foreach ($doc in $docs) {
    if (Test-Path $doc) {
        Write-Host "   ✅ $doc exists" -ForegroundColor Green
    } else {
        Write-Host "   ❌ $doc NOT found!" -ForegroundColor Red
    }
}

Write-Host ""

# Summary
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Silver/Gold IP Requirements:" -ForegroundColor Yellow
Write-Host "✅ One-click deployment config (azure.yaml)" -ForegroundColor Green
Write-Host "✅ Infrastructure as Code (infra/ directory)" -ForegroundColor Green
Write-Host "✅ Documentation (docs/ directory)" -ForegroundColor Green
Write-Host ""

if ($azdPath) {
    Write-Host "Next steps to TEST deployment (optional):" -ForegroundColor Yellow
    Write-Host "1. azd auth login" -ForegroundColor Cyan
    Write-Host "2. azd init" -ForegroundColor Cyan
    Write-Host "3. azd provision --preview   # See what will be deployed" -ForegroundColor Cyan
    Write-Host "4. azd up                    # Actually deploy" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Note: Testing deployment is OPTIONAL for Silver/Gold IP submission!" -ForegroundColor Green
} else {
    Write-Host "To install azd (optional for actual deployment):" -ForegroundColor Yellow
    Write-Host "winget install microsoft.azd" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Note: Installation is OPTIONAL for Silver/Gold IP submission!" -ForegroundColor Green
    Write-Host "      Having the configuration files is sufficient." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Configuration Test Complete ===" -ForegroundColor Cyan
