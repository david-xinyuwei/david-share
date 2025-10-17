# Setup script for LLM Inference Memory Estimation Tool (新版本)
# Usage: .\scripts\setup_new.ps1

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  LLM Inference Memory Estimation Tool - Setup" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version
    Write-Host "Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
python -m venv venv

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host ""
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  Setup completed successfully!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To use the tool:" -ForegroundColor Cyan
Write-Host "  1. Activate the virtual environment:" -ForegroundColor White
Write-Host "     .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Run the command-line tool:" -ForegroundColor White
Write-Host "     python src/cli_estimator.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "  3. Or run the web interface:" -ForegroundColor White
Write-Host "     streamlit run src/web_estimator.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "  4. Or open the Jupyter Notebook:" -ForegroundColor White
Write-Host "     jupyter notebook notebooks/memory_estimation.ipynb" -ForegroundColor Yellow
Write-Host ""
Write-Host "  5. To deactivate the virtual environment:" -ForegroundColor White
Write-Host "     deactivate" -ForegroundColor Yellow
Write-Host "======================================================" -ForegroundColor Cyan
