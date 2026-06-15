#!/bin/bash
# 自动文件重组迁移脚本 (Linux/Mac)
# Usage: chmod +x migrate.sh && ./migrate.sh

set -e

echo "======================================================"
echo "  文件重组迁移脚本"
echo "======================================================"
echo ""

# 确认操作
read -p "此操作将重新组织项目文件结构。是否继续？ (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "操作已取消"
    exit 1
fi

echo ""
echo "开始迁移文件..."

# 1. 移动Python源代码到 src/
echo "移动Python源代码..."
[ -f "python-estimating.py" ] && mv python-estimating.py src/cli_estimator.py && echo "✓ python-estimating.py -> src/cli_estimator.py"
[ -f "streamlit-estimating.py" ] && mv streamlit-estimating.py src/web_estimator.py && echo "✓ streamlit-estimating.py -> src/web_estimator.py"

# 2. 移动Notebook到 notebooks/
echo "移动Jupyter Notebook..."
if [ -f "Estimate_the_Memory_Consumption_for_Running_LLMs_(V2).ipynb" ]; then
    mv "Estimate_the_Memory_Consumption_for_Running_LLMs_(V2).ipynb" notebooks/memory_estimation.ipynb
    echo "✓ Notebook -> notebooks/memory_estimation.ipynb"
fi

# 3. 移动脚本到 scripts/
echo "移动安装脚本..."
[ -f "setup.sh" ] && mv setup.sh scripts/ && echo "✓ setup.sh -> scripts/"
[ -f "setup.ps1" ] && mv setup.ps1 scripts/ && echo "✓ setup.ps1 -> scripts/"

# 4. 移动图片到 docs/images/
echo "移动图片资源..."
if [ -d "images" ]; then
    mv images docs/
    echo "✓ images/ -> docs/images/"
fi

# 5. 删除编译文件
echo "清理临时文件..."
[ -f "estimatememory.pyc" ] && rm -f estimatememory.pyc && echo "✓ 删除 estimatememory.pyc"

# 6. 创建 __init__.py 文件
echo "创建Python包结构..."
touch src/__init__.py
[ -d "src/core" ] && touch src/core/__init__.py

echo ""
echo "======================================================"
echo "  迁移完成！"
echo "======================================================"
echo ""
echo "新的目录结构："
echo "src/           - Python源代码"
echo "notebooks/     - Jupyter notebooks"
echo "scripts/       - 安装脚本"
echo "docs/          - 文档和图片"
echo ""
echo "下一步："
echo "1. 查看 MIGRATION_GUIDE.md 了解详细信息"
echo "2. 测试功能："
echo "   python src/cli_estimator.py"
echo "   streamlit run src/web_estimator.py"
echo "3. 更新 README.md 中的路径引用"
echo "======================================================"
