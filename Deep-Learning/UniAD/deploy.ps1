# UniAD FlashAttention-2 Quick Deployment Script (PowerShell)
# Usage: .\deploy.ps1 -UniadRoot "C:\path\to\UniAD"

param(
    [Parameter(Mandatory=$true)]
    [string]$UniadRoot
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "UniAD FlashAttention-2 Deployment Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Validate UniAD directory
if (-not (Test-Path $UniadRoot)) {
    Write-Host "Error: UniAD directory not found: $UniadRoot" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Found UniAD directory: $UniadRoot" -ForegroundColor Green

# Check required directories
$ModuleDir = Join-Path $UniadRoot "projects\mmdet3d_plugin\uniad\modules"
$ConfigDir = Join-Path $UniadRoot "projects\configs\stage1_track_map"

if (-not (Test-Path $ModuleDir)) {
    Write-Host "Error: Module directory not found: $ModuleDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $ConfigDir)) {
    Write-Host "Error: Config directory not found: $ConfigDir" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Validated UniAD directory structure" -ForegroundColor Green
Write-Host ""

# Deploy code files
Write-Host "Step 1: Deploying FlashAttention module..." -ForegroundColor Yellow
Copy-Item "01_Code\flash_attention.py" -Destination $ModuleDir -Force
Copy-Item "01_Code\__init__.py" -Destination $ModuleDir -Force
Write-Host "✓ FlashAttention module deployed" -ForegroundColor Green
Write-Host ""

# Deploy config files
Write-Host "Step 2: Deploying configuration files..." -ForegroundColor Yellow
Copy-Item "02_Configs\base_track_map_fp32.py" -Destination $ConfigDir -Force
Copy-Item "02_Configs\base_track_map_fp16.py" -Destination $ConfigDir -Force
Copy-Item "02_Configs\base_track_map_flashattn.py" -Destination $ConfigDir -Force
Write-Host "✓ Configuration files deployed" -ForegroundColor Green
Write-Host ""

# Check Python environment
Write-Host "Step 3: Checking Python environment..." -ForegroundColor Yellow

# Check PyTorch
try {
    $torchVersion = python -c "import torch; print(torch.__version__)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ PyTorch installed: $torchVersion" -ForegroundColor Green
    } else {
        throw
    }
} catch {
    Write-Host "⚠ PyTorch not found. Please install: pip install torch>=2.0.1" -ForegroundColor Yellow
}

# Check FlashAttention
try {
    $faVersion = python -c "import flash_attn; print(flash_attn.__version__)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ FlashAttention installed: $faVersion" -ForegroundColor Green
    } else {
        throw
    }
} catch {
    Write-Host "⚠ FlashAttention not found" -ForegroundColor Yellow
    Write-Host "  To use FP16+FA2 config, install with:" -ForegroundColor Yellow
    Write-Host "  pip install flash-attn>=2.4.2 --no-build-isolation" -ForegroundColor White
    Write-Host ""
    Write-Host "  Note: FP32 and FP16 configs work without FlashAttention" -ForegroundColor Gray
}

# Check MMCV
try {
    $mmcvVersion = python -c "import mmcv; print(mmcv.__version__)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ MMCV installed: $mmcvVersion" -ForegroundColor Green
    } else {
        throw
    }
} catch {
    Write-Host "⚠ MMCV not found. Please install: pip install mmcv-full>=1.6.0" -ForegroundColor Yellow
}

Write-Host ""

# Summary
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Deployed Files:" -ForegroundColor White
Write-Host "  ✓ $ModuleDir\flash_attention.py" -ForegroundColor Gray
Write-Host "  ✓ $ModuleDir\__init__.py" -ForegroundColor Gray
Write-Host "  ✓ $ConfigDir\base_track_map_fp32.py" -ForegroundColor Gray
Write-Host "  ✓ $ConfigDir\base_track_map_fp16.py" -ForegroundColor Gray
Write-Host "  ✓ $ConfigDir\base_track_map_flashattn.py" -ForegroundColor Gray
Write-Host ""

$ToolsDir = Join-Path $UniadRoot "tools"

Write-Host "Quick Start Commands:" -ForegroundColor White
Write-Host ""
Write-Host "# FP32 Baseline" -ForegroundColor Cyan
Write-Host "python $ToolsDir\train.py $ConfigDir\base_track_map_fp32.py" -ForegroundColor Gray
Write-Host ""
Write-Host "# FP16 Baseline" -ForegroundColor Cyan
Write-Host "python $ToolsDir\train.py $ConfigDir\base_track_map_fp16.py" -ForegroundColor Gray
Write-Host ""
Write-Host "# FP16 + FlashAttention-2 (Recommended)" -ForegroundColor Cyan
Write-Host "python $ToolsDir\train.py $ConfigDir\base_track_map_flashattn.py" -ForegroundColor Gray
Write-Host ""

Write-Host "Multi-GPU Training (Windows requires torchrun):" -ForegroundColor White
Write-Host "torchrun --nproc_per_node=2 $ToolsDir\train.py $ConfigDir\base_track_map_flashattn.py" -ForegroundColor Gray
Write-Host ""

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Deployment Complete! 🚀" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Review documentation in 06_Documentation\" -ForegroundColor White
Write-Host "2. Run a 1-epoch test to validate setup" -ForegroundColor White
Write-Host "3. Check logs match expected performance (~1.29x speedup)" -ForegroundColor White
Write-Host ""
Write-Host "For troubleshooting, see README.md or DEPLOYMENT_GUIDE.md" -ForegroundColor Gray
