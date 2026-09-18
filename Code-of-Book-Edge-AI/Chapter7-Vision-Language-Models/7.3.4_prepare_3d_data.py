# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第7章 §7.3.4 3D模式微调：肾上腺分割实践

import numpy as np
import nibabel as nib
def prepare_3d_data(nii_path, label_path, output_npz):
    """将NIFTI格式转换为BiomedParse的NPZ格式"""
    # 读取NIFTI文件
    img_nii = nib.load(nii_path)
    label_nii = nib.load(label_path)
    # 获取数组数据
    img_data = img_nii.get_fdata()      # D×H×W
    label_data = label_nii.get_fdata()  # D×H×W
    # 归一化图像到0-255（3D模式可以归一化）
    img_min, img_max = img_data.min(), img_data.max()
    img_data = ((img_data - img_min) / (img_max - img_min) * 255)
    img_data = img_data.astype(np.uint8)
    # 提取左右肾上腺的掩码（假设label=1是左，label=2是右）
    left_adrenal = (label_data == 1).astype(np.uint8)
    right_adrenal = (label_data == 2).astype(np.uint8)
    # 保存为NPZ格式
    np.savez_compressed(
        output_npz,
        image=img_data,
        label=np.stack([left_adrenal, right_adrenal], axis=0),
        prompts=['left adrenal gland', 'right adrenal gland']
    )
    print(f"已保存: {output_npz}")
    print(f"  图像形状: {img_data.shape}")
    print(f"  标签形状: {left_adrenal.shape}")
# 示例调用
prepare_3d_data(
    "ct_volume.nii.gz",
    "adrenal_label.nii.gz",
    "train_adrenal.npz"
)
