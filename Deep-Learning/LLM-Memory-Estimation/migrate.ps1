# Auto Migration Script for Windows PowerShell
# Usage: .\migrate.ps1

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Project File Reorganization Script" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Confirm operation
$confirmation = Read-Host "This will reorganize your project structure. Continue? (y/n)"
if ($confirmation -eq 'n' -or $confirmation -eq 'N') {
    Write-Host "Operation cancelled" -ForegroundColor Yellow
    exit
}

Write-Host ""
Write-Host "Starting migration..." -ForegroundColor Yellow

# 1. Move Python source code to src/
Write-Host "Moving Python source files..." -ForegroundColor Cyan
if (Test-Path "python-estimating.py") {
    Move-Item python-estimating.py src/cli_estimator.py -Force
    Write-Host "OK python-estimating.py -> src/cli_estimator.py" -ForegroundColor Green
}
if (Test-Path "streamlit-estimating.py") {
    Move-Item streamlit-estimating.py src/web_estimator.py -Force
    Write-Host "OK streamlit-estimating.py -> src/web_estimator.py" -ForegroundColor Green
}

# 2. Move Notebook to notebooks/
Write-Host "Moving Jupyter Notebook..." -ForegroundColor Cyan
if (Test-Path "Estimate_the_Memory_Consumption_for_Running_LLMs_(V2).ipynb") {
    Move-Item "Estimate_the_Memory_Consumption_for_Running_LLMs_(V2).ipynb" notebooks/memory_estimation.ipynb -Force
    Write-Host "OK Notebook -> notebooks/memory_estimation.ipynb" -ForegroundColor Green
}

# 3. Move scripts to scripts/
Write-Host "Moving setup scripts..." -ForegroundColor Cyan
if (Test-Path "setup.sh") {
    Move-Item setup.sh scripts/ -Force
    Write-Host "OK setup.sh -> scripts/" -ForegroundColor Green
}
if (Test-Path "setup.ps1") {
    Move-Item setup.ps1 scripts/ -Force
    Write-Host "OK setup.ps1 -> scripts/" -ForegroundColor Green
}

# 4. Move images to docs/images/
Write-Host "Moving images..." -ForegroundColor Cyan
if (Test-Path "images") {
    Move-Item images docs/ -Force
    Write-Host "OK images/ -> docs/images/" -ForegroundColor Green
}

# 5. Clean up temporary files
Write-Host "Cleaning temporary files..." -ForegroundColor Cyan
if (Test-Path "estimatememory.pyc") {
    Remove-Item estimatememory.pyc -Force
    Write-Host "OK Deleted estimatememory.pyc" -ForegroundColor Green
}

# 6. Create __init__.py files
Write-Host "Creating Python package structure..." -ForegroundColor Cyan
New-Item -Path "src/__init__.py" -ItemType File -Force | Out-Null
if (Test-Path "src/core") {
    New-Item -Path "src/core/__init__.py" -ItemType File -Force | Out-Null
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  Migration Complete!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "New directory structure:" -ForegroundColor Cyan
Write-Host "src/           - Python source code" -ForegroundColor White
Write-Host "notebooks/     - Jupyter notebooks" -ForegroundColor White
Write-Host "scripts/       - Setup scripts" -ForegroundColor White
Write-Host "docs/          - Documentation and images" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. See MIGRATION_GUIDE.md for details" -ForegroundColor White
Write-Host "2. Test functionality:" -ForegroundColor White
Write-Host "   python src/cli_estimator.py" -ForegroundColor Yellow
Write-Host "   streamlit run src/web_estimator.py" -ForegroundColor Yellow
Write-Host "3. Update any hardcoded paths if needed" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor Cyan
