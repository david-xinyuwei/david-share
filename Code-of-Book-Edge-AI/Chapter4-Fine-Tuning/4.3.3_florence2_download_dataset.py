# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第4章 §4.3.3 微调Florence-2 —— 1. 数据集的构建与准备

# 补充：Roboflow 客户端初始化
from roboflow import Roboflow
rf = Roboflow(api_key="YOUR_ROBOFLOW_API_KEY")

# 下载Roboflow数据集，使用object detection格式
project = rf.workspace("marcelo-rovai-riila").project("box-versus-wheel-auto-dataset")
version = project.version(5)
dataset = version.download("florence2-od") # 含图片+目标标注.jsonl文件
