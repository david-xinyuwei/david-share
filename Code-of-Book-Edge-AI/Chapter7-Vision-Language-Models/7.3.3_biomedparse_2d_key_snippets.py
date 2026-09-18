# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第7章 §7.3.3 2D模式微调：CT器官分割实践
# 完整脚本见 projects/BiomedParse-Fine-Tuning/finetune_2d.py

# 配置参数
NUM_EPOCHS = 100
LEARNING_RATE = 1e-5
BATCH_SIZE = 1  #  必须为1，避免不同提示词混batch
#  关键点1: 图像保持0-255范围，不要归一化到0-1
img = img.astype(np.float32)  # 与预训练数据分布保持一致，避免性能骤减
# 关键点2: 正确提取提示词（保留完整器官名）
# 错误: "kidney"  →  正确: "left kidney"
parts = fname.split("_")[1:]  # 示例 ['left', 'kidney']
organ = " ".join(parts)     # 拼接为标准提示词"left kidney"
# 关键点3: 使用Dice Loss(医学分割核心损失函数)
def dice_loss(pred, target):
    pred = torch.sigmoid(pred)
    intersection = (pred * target).sum()
    return 1 - (2 * intersection + 1) / (pred.sum() + target.sum() + 1)
