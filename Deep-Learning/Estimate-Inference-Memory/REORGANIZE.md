# 项目文件重组方案

## 📋 问题分析

当前项目文件结构较为混乱：
- Python脚本、Notebook、图片、配置文件都在根目录
- 文件命名不统一
- 缺少清晰的组织结构
- 不符合Python项目最佳实践

## 🎯 解决方案

### 方案1: 自动迁移（推荐）⭐

**一键执行**，自动重组所有文件：

#### Windows PowerShell
```powershell
.\migrate.ps1
```

#### Linux/Mac
```bash
chmod +x migrate.sh
./migrate.sh
```

**迁移内容**：
| 原文件 | 新位置 | 说明 |
|--------|--------|------|
| `python-estimating.py` | `src/cli_estimator.py` | 命令行工具 |
| `streamlit-estimating.py` | `src/web_estimator.py` | Web界面 |
| `Estimate_the_Memory_Consumption_for_Running_LLMs_(V2).ipynb` | `notebooks/memory_estimation.ipynb` | Jupyter Notebook |
| `setup.sh` | `scripts/setup.sh` | 安装脚本 |
| `setup.ps1` | `scripts/setup.ps1` | 安装脚本 |
| `images/` | `docs/images/` | 图片资源 |
| `estimatememory.pyc` | 删除 | 临时编译文件 |

### 方案2: 手动迁移

如果您想自己控制迁移过程，请参考 [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)

## 📁 新的目录结构

```
Estimate-Inference-Memory/
│
├── 📂 src/                        # 源代码目录
│   ├── __init__.py
│   ├── cli_estimator.py          # CLI工具
│   └── web_estimator.py          # Web界面
│
├── 📂 notebooks/                  # Jupyter笔记本
│   └── memory_estimation.ipynb
│
├── 📂 scripts/                    # 安装脚本
│   ├── setup.sh
│   └── setup.ps1
│
├── 📂 docs/                       # 文档和资源
│   └── images/
│       ├── 1.png
│       ├── 2.png
│       └── 3.png
│
├── 📄 README.md                   # 主文档
├── 📄 requirements.txt            # Python依赖
├── 📄 .gitignore                  # Git忽略规则
├── 📄 MIGRATION_GUIDE.md          # 迁移指南
├── 🔧 migrate.sh                  # 迁移脚本(Linux/Mac)
└── 🔧 migrate.ps1                 # 迁移脚本(Windows)
```

## ✅ 迁移后的优势

### 1. **更清晰的结构**
- 源代码集中在 `src/` 目录
- 文档和资源在 `docs/` 目录
- 笔记本在 `notebooks/` 目录
- 脚本在 `scripts/` 目录

### 2. **更好的命名**
- `cli_estimator.py` - 清晰表明是CLI工具
- `web_estimator.py` - 清晰表明是Web界面
- `memory_estimation.ipynb` - 简洁的笔记本名称

### 3. **符合Python项目标准**
- 遵循标准Python项目布局
- 易于打包和分发
- 方便添加测试和文档

### 4. **更专业的呈现**
- 适合开源社区分享
- 符合Silver/Gold IP标准
- 易于协作和维护

## 🚦 迁移步骤

### 第一步：备份（可选但推荐）
```bash
# 提交当前更改到Git
git add .
git commit -m "Backup before migration"
```

### 第二步：运行迁移脚本

**Windows**:
```powershell
.\migrate.ps1
```

**Linux/Mac**:
```bash
chmod +x migrate.sh
./migrate.sh
```

### 第三步：验证迁移结果

检查新的目录结构：
```bash
# Windows
tree /F

# Linux/Mac
tree
```

### 第四步：测试功能

```bash
# 激活虚拟环境
# Windows
.\venv\Scripts\Activate.ps1
# Linux/Mac
source venv/bin/activate

# 测试CLI工具
python src/cli_estimator.py

# 测试Web界面
streamlit run src/web_estimator.py

# 测试Notebook
jupyter notebook notebooks/memory_estimation.ipynb
```

### 第五步：提交更改

```bash
git add .
git commit -m "Reorganize project structure for better maintainability"
git push
```

## ⚠️ 注意事项

1. **迁移前备份**: 建议先提交到Git
2. **虚拟环境**: 迁移不会影响已有的虚拟环境
3. **路径更新**: 迁移脚本会自动更新相关路径
4. **功能测试**: 迁移后请测试所有功能

## 🆘 常见问题

### Q: 迁移会影响虚拟环境吗？
A: 不会，虚拟环境 `venv/` 目录保持不变。

### Q: 迁移失败了怎么办？
A: 使用 `git reset --hard` 恢复到迁移前的状态，或手动移动文件。

### Q: 需要更新什么配置吗？
A: 不需要，迁移脚本已经创建了新的setup脚本，路径都已更新。

### Q: 可以只迁移部分文件吗？
A: 可以，参考 [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) 手动选择性迁移。

## 📞 获取帮助

如果在迁移过程中遇到问题：
1. 查看 [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)
2. 查看 [README.md](./README.md)
3. 提交Issue到GitHub

---

**准备好了吗？运行 `.\migrate.ps1` (Windows) 或 `./migrate.sh` (Linux/Mac) 开始迁移！** 🚀
