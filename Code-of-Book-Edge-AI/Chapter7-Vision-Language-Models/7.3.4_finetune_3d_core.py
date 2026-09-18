# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第7章 §7.3.4 3D模式微调：肾上腺分割实践
# 完整脚本见 projects/BiomedParse-Fine-Tuning/finetune_3d.py

# 补充：导入语句（dice_loss 见 7.3.3_biomedparse_2d_key_snippets.py）
import numpy as np
import torch

def finetune_3d(model, train_npz_path, test_npz_path):
    """3D微调主流程"""
    # 加载训练数据
    train_data = np.load(train_npz_path)
    train_img = train_data['image']      # D×H×W
    train_label = train_data['label']    # N×D×H×W
    train_prompts = train_data['prompts']
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-5)
    for epoch in range(100):
        model.train()
        total_loss = 0
        # 对每个器官分别训练
        for organ_idx, prompt in enumerate(train_prompts):
            # 获取该器官的掩码
            mask_3d = train_label[organ_idx]  # D×H×W
            # 逐切片训练
            for slice_idx in range(train_img.shape[0]):
                img_slice = train_img[slice_idx]   # H×W
                mask_slice = mask_3d[slice_idx]    # H×W
                # 转换为tensor并添加batch和channel维度
                img_t = torch.from_numpy(img_slice).unsqueeze(0).unsqueeze(0)
                mask_t = torch.from_numpy(mask_slice).unsqueeze(0).unsqueeze(0)
                img_t = img_t.to('cuda').float()
                mask_t = mask_t.to('cuda').float()
                # 前向传播
                pred = model(img_t, prompt)
                # 计算损失
                loss = dice_loss(pred, mask_t)
                # 反向传播
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
        avg_loss = total_loss / (len(train_prompts) * train_img.shape[0])
        print(f"Epoch {epoch+1}, Loss: {avg_loss:.4f}")
    # 保存模型
    torch.save(model.state_dict(), "output/finetune_3d/final.pth")
    print("3D微调完成")
