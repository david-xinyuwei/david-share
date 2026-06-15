#!/bin/bash
# UniAD FlashAttention-2 Quick Deployment Script
# Usage: ./deploy.sh <UniAD_ROOT_PATH>

set -e  # Exit on any error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "UniAD FlashAttention-2 Deployment Script"
echo "=========================================="
echo ""

# Check if UniAD path is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Please provide UniAD root path${NC}"
    echo "Usage: ./deploy.sh <UniAD_ROOT_PATH>"
    echo "Example: ./deploy.sh ~/UniAD"
    exit 1
fi

UNIAD_ROOT="$1"

# Validate UniAD directory exists
if [ ! -d "$UNIAD_ROOT" ]; then
    echo -e "${RED}Error: UniAD directory not found: $UNIAD_ROOT${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found UniAD directory: $UNIAD_ROOT${NC}"

# Check required directories
MODULE_DIR="$UNIAD_ROOT/projects/mmdet3d_plugin/uniad/modules"
CONFIG_DIR="$UNIAD_ROOT/projects/configs/stage1_track_map"

if [ ! -d "$MODULE_DIR" ]; then
    echo -e "${RED}Error: Module directory not found: $MODULE_DIR${NC}"
    exit 1
fi

if [ ! -d "$CONFIG_DIR" ]; then
    echo -e "${RED}Error: Config directory not found: $CONFIG_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Validated UniAD directory structure${NC}"
echo ""

# Deploy code files
echo "Step 1: Deploying FlashAttention module..."
cp -v 01_Code/flash_attention.py "$MODULE_DIR/"
cp -v 01_Code/__init__.py "$MODULE_DIR/"
echo -e "${GREEN}✓ FlashAttention module deployed${NC}"
echo ""

# Deploy config files
echo "Step 2: Deploying configuration files..."
cp -v 02_Configs/base_track_map_fp32.py "$CONFIG_DIR/"
cp -v 02_Configs/base_track_map_fp16.py "$CONFIG_DIR/"
cp -v 02_Configs/base_track_map_flashattn.py "$CONFIG_DIR/"
echo -e "${GREEN}✓ Configuration files deployed${NC}"
echo ""

# Check Python environment
echo "Step 3: Checking Python environment..."

# Check PyTorch
if python -c "import torch" 2>/dev/null; then
    TORCH_VERSION=$(python -c "import torch; print(torch.__version__)")
    echo -e "${GREEN}✓ PyTorch installed: $TORCH_VERSION${NC}"
else
    echo -e "${YELLOW}⚠ PyTorch not found. Please install: pip install torch>=2.0.1${NC}"
fi

# Check FlashAttention
if python -c "import flash_attn" 2>/dev/null; then
    FA_VERSION=$(python -c "import flash_attn; print(flash_attn.__version__)")
    echo -e "${GREEN}✓ FlashAttention installed: $FA_VERSION${NC}"
else
    echo -e "${YELLOW}⚠ FlashAttention not found${NC}"
    echo "  To use FP16+FA2 config, install with:"
    echo "  pip install flash-attn>=2.4.2 --no-build-isolation"
    echo ""
    echo "  Note: FP32 and FP16 configs work without FlashAttention"
fi

# Check MMCV
if python -c "import mmcv" 2>/dev/null; then
    MMCV_VERSION=$(python -c "import mmcv; print(mmcv.__version__)")
    echo -e "${GREEN}✓ MMCV installed: $MMCV_VERSION${NC}"
else
    echo -e "${YELLOW}⚠ MMCV not found. Please install: pip install mmcv-full>=1.6.0${NC}"
fi

echo ""

# Summary
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo ""
echo "Deployed Files:"
echo "  ✓ $MODULE_DIR/flash_attention.py"
echo "  ✓ $MODULE_DIR/__init__.py"
echo "  ✓ $CONFIG_DIR/base_track_map_fp32.py"
echo "  ✓ $CONFIG_DIR/base_track_map_fp16.py"
echo "  ✓ $CONFIG_DIR/base_track_map_flashattn.py"
echo ""

echo "Quick Start Commands:"
echo ""
echo "# FP32 Baseline"
echo "python $UNIAD_ROOT/tools/train.py $CONFIG_DIR/base_track_map_fp32.py"
echo ""
echo "# FP16 Baseline"
echo "python $UNIAD_ROOT/tools/train.py $CONFIG_DIR/base_track_map_fp16.py"
echo ""
echo "# FP16 + FlashAttention-2 (Recommended)"
echo "python $UNIAD_ROOT/tools/train.py $CONFIG_DIR/base_track_map_flashattn.py"
echo ""

echo "Multi-GPU Training (8 GPUs):"
echo "bash $UNIAD_ROOT/tools/uniad_dist_train.sh $CONFIG_DIR/base_track_map_flashattn.py 8"
echo ""

echo -e "${GREEN}=========================================="
echo "Deployment Complete! 🚀"
echo "==========================================${NC}"
echo ""
echo "Next Steps:"
echo "1. Review documentation in 06_Documentation/"
echo "2. Run a 1-epoch test to validate setup"
echo "3. Check logs match expected performance (~1.29x speedup)"
echo ""
echo "For troubleshooting, see README.md or DEPLOYMENT_GUIDE.md"
