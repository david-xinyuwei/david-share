# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第6章 §6.6.3 本地多模态语音助手系统示例 —— 2. 语言模型推理模块：导出 INT4 ONNX 模型

pip install onnxruntime-genai
python -m onnxruntime_genai.models.builder -m microsoft/Phi-4-mini-instruct -e cpu -p int4 -o ./Phi-4-mini-int4-cpu
