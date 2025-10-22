# MedImageParse 3D 模型测试指南

## 📦 已准备的测试文件

### 1. 本地生成的测试文件
- **文件**: `samples_3d/test_organ.nii.gz`
- **大小**: ~4.7 KB
- **内容**: 模拟的3D器官数据 (128×128×64)
- **用途**: 快速功能测试

### 2. 真实医学影像示例（需手动下载）

由于网络限制，请从以下公开数据集手动下载真实的3D医学影像：

#### 推荐数据源：

**A. MSD (Medical Segmentation Decathlon)**
- 网址: http://medicaldecathlon.com/
- 包含多个器官的CT/MRI数据
- 任务3：肝脏分割
- 任务6：肺部分割
- 任务7：胰腺分割

**B. 使用Medical Image Samples**
一些可以直接测试的小型样本：

1. **简单CT扫描示例**
   ```bash
   # 可以从以下网站下载示例NIfTI文件
   https://www.slicer.org/wiki/SampleData
   ```

2. **直接使用3D Slicer软件下载**
   - 下载并安装 3D Slicer: https://download.slicer.org/
   - 打开软件后，从 Sample Data 模块下载示例
   - 将下载的数据保存为 .nii.gz 格式

## 🧪 测试步骤

### 使用本地测试文件：

1. **启动应用**
   ```bash
   streamlit run app_clean.py
   ```

2. **配置模型**
   - 在侧边栏选择 "MedImageParse 3D"
   - 确认endpoint URL和API key正确

3. **上传测试文件**
   - 点击文件上传按钮
   - 选择 `samples_3d/test_organ.nii.gz`

4. **输入提示词**
   - 测试提示词: `organ`, `tumor`, `tissue`
   - 或使用中文: `器官`, `肿瘤`

5. **分析并查看结果**
   - 点击"开始分析"
   - 查看返回的3D分割切片

## 📋 3D模型支持的提示词示例

### 腹部器官：
- `liver` - 肝脏
- `kidney` - 肾脏
- `pancreas` - 胰腺
- `spleen` - 脾脏
- `stomach` - 胃

### 胸部器官：
- `lung` - 肺
- `heart` - 心脏

### 脑部结构：
- `brain` - 脑
- `tumor` - 肿瘤

### 血管：
- `aorta` - 主动脉
- `vessel` - 血管

### 异常/病变：
- `tumor` - 肿瘤
- `lesion` - 病变
- `cyst` - 囊肿

## 🔍 预期结果

模型会返回：
1. **3D分割掩码**: NIfTI格式的3D数组
2. **切片可视化**: 自动提取包含分割结果的2D切片（最多16个）
3. **数据形状**: 显示3D数据的维度信息

## ⚠️ 注意事项

1. **文件大小**: 真实的医学影像可能较大（几MB到几百MB）
2. **处理时间**: 3D模型处理时间比2D模型长
3. **网络超时**: 已设置300秒超时，大文件可能需要更长时间
4. **内存占用**: 3D数据会占用较多内存

## 🐛 故障排除

### 问题1: 上传失败
- **原因**: 文件太大
- **解决**: 使用较小的测试文件，或裁剪影像

### 问题2: 解码失败
- **原因**: nibabel库未安装
- **解决**: 
  ```bash
  pip install nibabel
  ```

### 问题3: 没有显示切片
- **原因**: 分割结果为空（没有找到目标对象）
- **解决**: 
  - 检查提示词是否与影像内容匹配
  - 尝试更通用的提示词如 "organ" 或 "tissue"

### 问题4: 网络超时
- **原因**: 文件太大或网络不稳定
- **解决**: 
  - 使用较小的测试文件
  - 增加超时时间设置

## 📚 相关资源

- [MedImageParse 3D 文档](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/healthcare-ai/deploy-medimageparse?tabs=medimageparse-3d)
- [NIfTI 格式说明](https://nifti.nimh.nih.gov/)
- [3D Slicer 软件](https://www.slicer.org/)
- [Medical Segmentation Decathlon](http://medicaldecathlon.com/)
