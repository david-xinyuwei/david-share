#!/bin/bash
# 00_check_environment.sh - 环境检查脚本
#
# Best Practice: Config First - 调用任何 API/服务前，必须先检查环境
# Best Practice: History First - 先查历史命令和已有配置
#
# 运行此脚本确保环境符合实验要求

set -e

echo "============================================================"
echo "🔍 量化精度转折点实验 - 环境检查"
echo "============================================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS="${GREEN}✅ PASS${NC}"
FAIL="${RED}❌ FAIL${NC}"
WARN="${YELLOW}⚠️ WARN${NC}"

errors=0
warnings=0

# ============================================================
# 1. GPU 检查
# ============================================================

echo "📊 1. GPU 检查"
echo "------------------------------------------------------------"

if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    GPU_MEMORY=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | awk '{print $9}')
    
    echo -e "   GPU 型号: $GPU_NAME"
    echo -e "   GPU 显存: $GPU_MEMORY"
    echo -e "   驱动版本: $DRIVER_VERSION"
    echo -e "   CUDA 版本: $CUDA_VERSION"
    
    # 检查显存是否足够 (至少 40GB)
    GPU_MEM_GB=$(echo "$GPU_MEMORY" | grep -oP '\d+' | head -1)
    GPU_MEM_GB=$((GPU_MEM_GB / 1024))  # MiB to GB
    
    if [[ $GPU_MEM_GB -ge 70 ]]; then
        echo -e "   显存检查: $PASS (${GPU_MEM_GB}GB >= 70GB, 可量化 32B)"
    elif [[ $GPU_MEM_GB -ge 40 ]]; then
        echo -e "   显存检查: $WARN (${GPU_MEM_GB}GB, 只能量化到 14B)"
        ((warnings++))
    else
        echo -e "   显存检查: $FAIL (${GPU_MEM_GB}GB < 40GB, 显存不足)"
        ((errors++))
    fi
else
    echo -e "   $FAIL nvidia-smi 不可用"
    ((errors++))
fi

echo ""

# ============================================================
# 2. Python 环境检查
# ============================================================

echo "🐍 2. Python 环境检查"
echo "------------------------------------------------------------"

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "   Python 版本: $PYTHON_VERSION"

# 检查 Python 版本 (需要 3.10+)
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -ge 10 ]]; then
    echo -e "   版本检查: $PASS"
else
    echo -e "   版本检查: $FAIL (需要 Python 3.10+)"
    ((errors++))
fi

echo ""

# ============================================================
# 3. 关键包版本检查
# ============================================================

echo "📦 3. 关键包版本检查"
echo "------------------------------------------------------------"

check_package() {
    local pkg=$1
    local min_version=$2
    
    if python3 -c "import $pkg" 2>/dev/null; then
        VERSION=$(python3 -c "import $pkg; print($pkg.__version__)" 2>/dev/null || echo "unknown")
        echo -e "   $pkg: $VERSION"
    else
        echo -e "   $pkg: $FAIL (未安装)"
        ((errors++))
    fi
}

# 检查关键包
check_package "vllm" "0.7.0"
check_package "transformers" "4.40.0"
check_package "torch" "2.0.0"

# 检查量化工具
echo ""
echo "   量化工具:"
if python3 -c "import awq" 2>/dev/null; then
    AWQ_VER=$(python3 -c "import awq; print(awq.__version__)" 2>/dev/null || echo "installed")
    echo -e "   - AutoAWQ: $AWQ_VER"
else
    echo -e "   - AutoAWQ: $WARN (未安装, 需要 pip install autoawq)"
    ((warnings++))
fi

if python3 -c "import gptqmodel" 2>/dev/null; then
    echo -e "   - GPTQModel: installed"
else
    echo -e "   - GPTQModel: $WARN (未安装, 需要 pip install gptqmodel)"
    ((warnings++))
fi

# 检查 lm-eval
if command -v lm_eval &> /dev/null; then
    LM_EVAL_VER=$(lm_eval --version 2>/dev/null || echo "installed")
    echo -e "   - lm-eval: $LM_EVAL_VER"
else
    echo -e "   - lm-eval: $WARN (未安装, 需要 pip install lm-eval)"
    ((warnings++))
fi

echo ""

# ============================================================
# 4. 磁盘空间检查
# ============================================================

echo "💾 4. 磁盘空间检查"
echo "------------------------------------------------------------"

DISK_AVAIL=$(df -BG . | awk 'NR==2 {print $4}' | grep -oP '\d+')
echo -e "   可用空间: ${DISK_AVAIL}GB"

if [[ $DISK_AVAIL -ge 200 ]]; then
    echo -e "   空间检查: $PASS (需要约 150GB)"
elif [[ $DISK_AVAIL -ge 100 ]]; then
    echo -e "   空间检查: $WARN (建议 200GB+)"
    ((warnings++))
else
    echo -e "   空间检查: $FAIL (至少需要 100GB)"
    ((errors++))
fi

echo ""

# ============================================================
# 5. 网络检查 (Hugging Face)
# ============================================================

echo "🌐 5. 网络检查"
echo "------------------------------------------------------------"

if curl -s --connect-timeout 5 https://huggingface.co > /dev/null; then
    echo -e "   Hugging Face: $PASS (可访问)"
else
    echo -e "   Hugging Face: $WARN (连接超时, 可能需要代理)"
    ((warnings++))
fi

# 检查 HF Token
if [[ -n "$HF_TOKEN" ]] || [[ -f ~/.cache/huggingface/token ]]; then
    echo -e "   HF Token: $PASS (已配置)"
else
    echo -e "   HF Token: $WARN (未配置, 部分模型可能无法下载)"
    ((warnings++))
fi

echo ""

# ============================================================
# 6. 历史命令检查 (History First)
# ============================================================

echo "📜 6. 历史命令检查 (History First)"
echo "------------------------------------------------------------"

echo "   最近的量化/评估相关命令:"
history 2>/dev/null | grep -iE "lm_eval|autoawq|gptq|quantize" | tail -5 || echo "   (无历史记录)"

echo ""

# ============================================================
# 汇总
# ============================================================

echo "============================================================"
echo "📋 检查结果汇总"
echo "============================================================"

if [[ $errors -eq 0 && $warnings -eq 0 ]]; then
    echo -e "${GREEN}✅ 环境检查通过！可以开始实验。${NC}"
elif [[ $errors -eq 0 ]]; then
    echo -e "${YELLOW}⚠️ 有 $warnings 个警告，建议修复后再开始。${NC}"
else
    echo -e "${RED}❌ 有 $errors 个错误，必须修复后才能开始！${NC}"
fi

echo ""
echo "下一步:"
echo "  1. 修复上述问题 (如有)"
echo "  2. pip install -r requirements.txt"
echo "  3. python scripts/01_quantize_models.py --method awq"
echo ""

exit $errors
