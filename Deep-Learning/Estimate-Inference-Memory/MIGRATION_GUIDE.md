# 文件重组迁移指南

## 📁 新的目录结构

为了使项目更加专业和易于维护，建议采用以下目录结构：

```
Estimate-Inference-Memory/
├── src/                           # 源代码目录
│   ├── cli_estimator.py          # 命令行工具 (原 python-estimating.py)
│   ├── web_estimator.py          # Web界面 (原 streamlit-estimating.py)
│   └── core/                     # 核心计算模块
│       └── calculator.py         # 内存计算核心逻辑
├── notebooks/                     # Jupyter notebooks
│   └── memory_estimation.ipynb   # (原 Estimate_the_Memory_Consumption_for_Running_LLMs_(V2).ipynb)
├── scripts/                       # 安装和辅助脚本
│   ├── setup.sh                  # Linux/Mac 安装脚本
│   └── setup.ps1                 # Windows 安装脚本
├── docs/                          # 文档和资源
│   ├── images/                   # 图片资源
│   │   ├── 1.png
│   │   ├── 2.png
│   │   └── 3.png
│   └── ARCHITECTURE.md           # 架构文档
├── tests/                         # 单元测试 (可选)
│   └── test_calculator.py
├── README.md                      # 主文档
├── requirements.txt               # Python依赖
├── .gitignore                    # Git忽略规则
└── LICENSE                        # 许可证 (可选)
```

## 🔄 文件迁移命令

### Windows PowerShell

```powershell
# 1. 移动Python源代码到 src/
Move-Item python-estimating.py src/cli_estimator.py
Move-Item streamlit-estimating.py src/web_estimator.py

# 2. 移动Notebook到 notebooks/
Move-Item Estimate_the_Memory_Consumption_for_Running_LLMs_(V2).ipynb notebooks/memory_estimation.ipynb

# 3. 移动脚本到 scripts/
Move-Item setup.sh scripts/
Move-Item setup.ps1 scripts/

# 4. 移动图片到 docs/images/
Move-Item images docs/

# 5. 删除编译文件 (可选)
Remove-Item estimatememory.pyc -ErrorAction SilentlyContinue
```

### Linux/Mac

```bash
# 1. 移动Python源代码到 src/
mv python-estimating.py src/cli_estimator.py
mv streamlit-estimating.py src/web_estimator.py

# 2. 移动Notebook到 notebooks/
mv Estimate_the_Memory_Consumption_for_Running_LLMs_\(V2\).ipynb notebooks/memory_estimation.ipynb

# 3. 移动脚本到 scripts/
mv setup.sh scripts/
mv setup.ps1 scripts/

# 4. 移动图片到 docs/images/
mv images docs/

# 5. 删除编译文件 (可选)
rm -f estimatememory.pyc
```

## 📝 迁移后需要更新的地方

### 1. 更新 scripts/setup.ps1

将运行命令改为：
```powershell
python src/cli_estimator.py
streamlit run src/web_estimator.py
jupyter notebook notebooks/memory_estimation.ipynb
```

### 2. 更新 scripts/setup.sh

将运行命令改为：
```bash
python src/cli_estimator.py
streamlit run src/web_estimator.py
jupyter notebook notebooks/memory_estimation.ipynb
```

### 3. 更新 README.md

更新所有文件路径引用。

## ✅ 迁移后的优势

1. **更清晰的结构**：源代码、文档、脚本分开
2. **易于维护**：相关文件集中管理
3. **专业标准**：符合Python项目最佳实践
4. **易于扩展**：可以轻松添加测试、文档等
5. **更好的版本控制**：Git提交更清晰

## 🚀 快速执行（一键迁移）

### Windows PowerShell
```powershell
# 运行迁移脚本
.\migrate.ps1
```

### Linux/Mac
```bash
# 运行迁移脚本
chmod +x migrate.sh
./migrate.sh
```

## ⚠️ 注意事项

1. 迁移前建议先提交当前代码到Git
2. 迁移后测试所有功能是否正常
3. 更新任何硬编码的路径
4. 更新文档中的路径引用
