import streamlit as st
import urllib.request
import json
import base64
from PIL import Image
import io
import os
from pathlib import Path
import numpy as np
import tempfile
import matplotlib.pyplot as plt
import matplotlib
# 设置matplotlib支持中文
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 配置文件路径
CONFIG_FILE = Path.home() / ".medimageparse_config.json"

# 加载保存的配置
def load_config():
    """从本地文件加载配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

# 保存配置
def save_config(config):
    """保存配置到本地文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

# 加载已保存的配置
saved_config = load_config()

# ===== 3D NIfTI 解码函数 =====
def decode_base64_to_nifti(base64_string: str):
    """
    将Base64编码的NIfTI数据解码为numpy数组
    
    Args:
        base64_string: Base64编码的字符串（包装在JSON中）
        
    Returns:
        np.ndarray: 解码后的3D医学影像数据
    """
    try:
        # 尝试导入nibabel库
        import nibabel as nib
    except ImportError:
        st.error(TEXTS["error_nibabel"])
        return None
    
    try:
        # 解析内层JSON获取'data'字段
        base64_string = json.loads(base64_string)["data"]
        
        # 将Base64字符串解码为原始字节
        byte_data = base64.b64decode(base64_string)
        
        # 写入临时.nii.gz文件
        temp_file = tempfile.NamedTemporaryFile(suffix='.nii.gz', delete=False)
        temp_file_name = temp_file.name
        try:
            temp_file.write(byte_data)
            temp_file.close()  # 先关闭文件，确保数据写入
            
            # 然后加载文件
            nifti_image = nib.load(temp_file_name)
            nifti_data = nifti_image.get_fdata()
            
            # 最后清理临时文件
            os.unlink(temp_file_name)
            
            return nifti_data
        except Exception as inner_error:
            # 确保清理临时文件
            if os.path.exists(temp_file_name):
                os.unlink(temp_file_name)
            raise inner_error
            
    except Exception as e:
        st.error(f"{TEXTS['error_nifti_decode']}: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return None

def plot_3d_slices(segmentation_masks, max_slices=16):
    """
    显示3D分割掩码的多个2D切片
    
    Args:
        segmentation_masks: 3D numpy数组 (H, W, D)
        max_slices: 最多显示的切片数量
    """
    import matplotlib.pyplot as plt
    
    slices_to_show = []
    
    # 收集包含非零掩码的切片
    for i in range(segmentation_masks.shape[2]):
        if segmentation_masks[:, :, i].sum() > 0:
            slices_to_show.append(i)
    
    if not slices_to_show:
        st.warning(TEXTS["warning_no_slices"])
        return None
    
    # 限制显示数量
    slices_to_show = slices_to_show[:max_slices]
    
    # 创建图像
    num_slices = len(slices_to_show)
    cols = min(4, num_slices)
    rows = (num_slices + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=(15, 4 * rows))
    if num_slices == 1:
        axes = [axes]
    else:
        axes = axes.flatten()
    
    for idx, slice_num in enumerate(slices_to_show):
        axes[idx].imshow(segmentation_masks[:, :, slice_num], cmap='gray')
        axes[idx].set_title(f'Slice {slice_num}')
        axes[idx].axis('off')
    
    # 隐藏多余的子图
    for idx in range(num_slices, len(axes)):
        axes[idx].axis('off')
    
    plt.tight_layout()
    return fig

# 设置页面配置
st.set_page_config(page_title="MedImageParse Model Caller", layout="wide")

# 语言选择（放在侧边栏顶部）
language = st.sidebar.selectbox(
    "🌐 Language / 语言",
    ["中文", "English"],
    index=0,
    help="Select interface language / 选择界面语言"
)

# 根据语言设置文本
if language == "中文":
    TEXTS = {
        "title": "🏥 医学图像解析模型调用",
        "subtitle": "Developed by Xinyuwei",
        "config": "⚙️ 配置",
        "model_type": "选择模型类型",
        "save_config": "💾 保存配置",
        "config_saved": "✅ 配置已保存！",
        "upload_image": "📤 上传图片",
        "upload_2d": "请上传PNG/JPG图片（用于2D模型）",
        "upload_3d": "请上传NIfTI文件（.nii或.nii.gz）",
        "file_name": "文件名",
        "file_size": "文件大小",
        "original_size": "原始尺寸",
        "image_shape": "影像形状",
        "data_type": "数据类型",
        "data_size": "3D数据大小",
        "view_mode": "显示模式",
        "quick_preview": "三视图（快速预览）",
        "interactive_browser": "交互式切片浏览器",
        "view_direction": "视图方向",
        "axial": "轴位（Axial）",
        "coronal": "冠状位（Coronal）",
        "sagittal": "矢状位（Sagittal）",
        "select_slice": "选择切片编号",
        "slice_stats": "当前切片统计信息",
        "min_value": "最小值",
        "max_value": "最大值",
        "mean_value": "平均值",
        "std_value": "标准差",
        "view_examples": "📚 查看使用示例",
        "prompt_input": "输入分割对象",
        "prompt_help": "💡 **模型支持任意自然语言描述！** 可以输入任何医学对象名称，不限于预设选项。使用 & 分隔多个对象。",
        "selected": "已选择",
        "analyze": "🔍 开始分析",
        "analyzing": "正在调用模型...",
        "success": "✅ 模型调用成功！",
        "results": "📊 分割结果",
        "error_nibabel": "❌ 需要安装nibabel库来处理NIfTI文件。请运行: pip install nibabel",
        "error_nifti_decode": "❌ NIfTI解码失败",
        "error_3d_preview": "❌ 无法加载3D影像预览",
        "error_empty_file": "❌ 文件为空，请上传有效的NIfTI文件",
        "error_file_small": "⚠️ 文件太小",
        "error_size_mismatch": "数据大小不匹配",
        "warning_no_slices": "⚠️ 没有找到包含分割结果的切片",
        "warning_save_config": "⚠️ 请先在左侧保存配置信息！",
        "warning_rgb_convert": "⚠️ 检测到复杂数据类型（RGB结构），正在转换...",
        "info_use_field": "使用字段",
        "info_rgb_channel": "检测到RGB数据，取R通道",
        "info_4d_data": "检测到4D数据",
        "bytes_info": "bytes，可能不是有效的NIfTI文件",
        "config_saved_persistent": "✅ 配置已保存（包括持久化到本地）！",
        "config_saved_session": "✅ 配置已保存到当前会话，但无法写入本地文件",
        "config_file": "配置文件",
        "config_loaded": "✅ 配置已保存",
        "current_model": "当前模型",
        "use_saved_config": "📂 使用已保存的配置",
        "error_incomplete_config": "❌ 请填写完整的配置信息！",
        "model_categories": "🎯 模型会自动将识别的对象归类到16个生物医学类别：liver, lung, kidney, pancreas, heart anatomies, brain anatomies, eye anatomies, vessel, other organ, tumor, infection, other lesion, fluid disturbance, other abnormality, histology structure, other",
        "prompt_category": "选择提示词类别（或选择'自定义'输入任意对象）",
        "custom": "自定义",
        "input_objects": "请输入要分割的对象（用 & 分隔多个对象）",
        "will_segment": "将分割",
        "objects": "个对象",
        "image_quality": "图片质量 (%)",
        "debug_info": "🔍 调试信息（点击查看）",
        "base64_decoded": "✅ Base64解码成功，数据大小",
        "bytes": "字节",
        "parsing_array": "🔄 解析为原始数据数组...",
        "array_length": "原始数组长度",
        "cannot_infer_size": "无法推断正方形尺寸，数组长度",
        "reshape_success": "✅ 去掉3字节头部后成功重塑为 1024x1024！",
        "converted_grayscale": "已将数组转换为灰度图像",
        "original_image": "🖼️ 原始图片",
        "seg_mask": "🎭 分割掩码",
        "overlay": "🔍 叠加效果",
        "size": "尺寸",
        "mask_overlay": "掩码半透明叠加",
        "seg_classification": "📋 分割对象分类",
        "detected_objects": "检测到的对象",
        "input_prompts": "输入的提示词",
        "download_mask": "下载分割掩码",
        "download_json": "下载原始JSON",
    }
else:
    TEXTS = {
        "title": "🏥 Medical Image Parsing Model",
        "subtitle": "Developed by Xinyuwei",
        "config": "⚙️ Configuration",
        "model_type": "Select Model Type",
        "save_config": "💾 Save Config",
        "config_saved": "✅ Configuration saved!",
        "upload_image": "📤 Upload Image",
        "upload_2d": "Upload PNG/JPG image (for 2D model)",
        "upload_3d": "Upload NIfTI file (.nii or .nii.gz)",
        "file_name": "File name",
        "file_size": "File size",
        "original_size": "Original size",
        "image_shape": "Image shape",
        "data_type": "Data type",
        "data_size": "3D data size",
        "view_mode": "View mode",
        "quick_preview": "Three-view (Quick Preview)",
        "interactive_browser": "Interactive Slice Browser",
        "view_direction": "View direction",
        "axial": "Axial",
        "coronal": "Coronal",
        "sagittal": "Sagittal",
        "select_slice": "Select slice number",
        "slice_stats": "Current slice statistics",
        "min_value": "Min",
        "max_value": "Max",
        "mean_value": "Mean",
        "std_value": "Std",
        "view_examples": "📚 View Examples",
        "prompt_input": "Input segmentation target",
        "prompt_help": "💡 **The model supports arbitrary natural language descriptions!** You can input any medical object name, not limited to preset options. Use & to separate multiple objects.",
        "selected": "Selected",
        "analyze": "🔍 Start Analysis",
        "analyzing": "Calling model...",
        "success": "✅ Model call successful!",
        "results": "📊 Segmentation Results",
        "error_nibabel": "❌ nibabel library is required for NIfTI files. Please run: pip install nibabel",
        "error_nifti_decode": "❌ NIfTI decoding failed",
        "error_3d_preview": "❌ Cannot load 3D image preview",
        "error_empty_file": "❌ File is empty, please upload a valid NIfTI file",
        "error_file_small": "⚠️ File too small",
        "error_size_mismatch": "Data size mismatch",
        "warning_no_slices": "⚠️ No slices with segmentation results found",
        "warning_save_config": "⚠️ Please save configuration on the left sidebar first!",
        "warning_rgb_convert": "⚠️ Complex data type detected (RGB structure), converting...",
        "info_use_field": "Using field",
        "info_rgb_channel": "RGB data detected, using R channel",
        "info_4d_data": "4D data detected",
        "bytes_info": "bytes, may not be a valid NIfTI file",
        "config_saved_persistent": "✅ Configuration saved (persisted to local file)!",
        "config_saved_session": "✅ Configuration saved to current session, but unable to write to local file",
        "config_file": "Config file",
        "config_loaded": "✅ Configuration saved",
        "current_model": "Current model",
        "use_saved_config": "📂 Using saved configuration",
        "error_incomplete_config": "❌ Please fill in all configuration fields!",
        "model_categories": "🎯 The model automatically classifies recognized objects into 16 biomedical categories: liver, lung, kidney, pancreas, heart anatomies, brain anatomies, eye anatomies, vessel, other organ, tumor, infection, other lesion, fluid disturbance, other abnormality, histology structure, other",
        "prompt_category": "Select prompt category (or choose 'Custom' to input any object)",
        "custom": "Custom",
        "input_objects": "Please enter objects to segment (separate multiple objects with &)",
        "will_segment": "Will segment",
        "objects": "object(s)",
        "image_quality": "Image Quality (%)",
        "debug_info": "🔍 Debug Info (click to view)",
        "base64_decoded": "✅ Base64 decoded successfully, data size",
        "bytes": "bytes",
        "parsing_array": "🔄 Parsing to raw data array...",
        "array_length": "Raw array length",
        "cannot_infer_size": "Cannot infer square size, array length",
        "reshape_success": "✅ Successfully reshaped to 1024x1024 after removing 3-byte header!",
        "converted_grayscale": "Converted array to grayscale image",
        "original_image": "🖼️ Original Image",
        "seg_mask": "🎭 Segmentation Mask",
        "overlay": "🔍 Overlay Effect",
        "size": "Size",
        "mask_overlay": "Mask semi-transparent overlay",
        "seg_classification": "📋 Segmentation Object Classification",
        "detected_objects": "Detected Objects",
        "input_prompts": "Input Prompts",
        "download_mask": "Download Segmentation Mask",
        "download_json": "Download Raw JSON",
    }

# 标题和副标题
st.title(TEXTS["title"])
st.caption(TEXTS["subtitle"])

# 侧边栏：配置端点和密钥
st.sidebar.header(TEXTS["config"])

# 从环境变量读取（可选，主要用于服务器部署）
# 本地运行时不需要设置环境变量，直接在UI输入即可
MODEL_CONFIGS = {
    "MedImageParse (2D)": {
        "url": os.getenv("AI_FOUNDRY_MedImageParse2D_ENDPOINT", ""),
        "key": os.getenv("AI_FOUNDRY_MedImageParse2D_KEY", "")
    },
    "MedImageParse 3D": {
        "url": os.getenv("AI_FOUNDRY_MedImageParse3D_ENDPOINT", ""),
        "key": os.getenv("AI_FOUNDRY_MedImageParse3D_KEY", "")
    }
}

# 选择模型类型
model_type = st.sidebar.radio(
    TEXTS["model_type"],
    ["MedImageParse (2D)", "MedImageParse 3D"],
    help="根据您在 Azure AI Foundry 部署的模型选择对应类型" if language == "中文" else "Select the model type based on your Azure AI Foundry deployment",
    index=0 if saved_config.get('model_type', 'MedImageParse (2D)') == 'MedImageParse (2D)' else 1
)

# 加载配置：优先使用本地保存的配置，其次是环境变量，最后是空字符串
if saved_config.get('model_type') == model_type:
    # 使用保存的配置
    default_url = saved_config.get('endpoint_url', '')
    default_key = saved_config.get('api_key', '')
else:
    # 新模型类型，尝试从环境变量读取（服务器部署场景）
    default_url = MODEL_CONFIGS[model_type]["url"]
    default_key = MODEL_CONFIGS[model_type]["key"]

st.sidebar.markdown("---")

# 输入配置信息
endpoint_url = st.sidebar.text_input(
    "REST Endpoint URL" if language == "English" else "REST 端点 URL",
    value=default_url,
    placeholder="https://your-endpoint.swedencentral.inference.ml.azure.com/score",
    help="从 Azure AI Foundry 部署详情中复制端点 URL" if language == "中文" else "Copy endpoint URL from Azure AI Foundry deployment details"
)

api_key = st.sidebar.text_input(
    "Primary Key" if language == "English" else "主密钥",
    value=default_key,
    type="password",
    placeholder="输入密钥 / Enter key",
    help="从 Azure AI Foundry 部署详情中复制主密钥" if language == "中文" else "Copy primary key from Azure AI Foundry deployment details"
)

# 保存配置按钮
if st.sidebar.button(TEXTS["save_config"], type="primary"):
    if endpoint_url and api_key:
        # 保存配置到本地文件（永久有效）
        config_to_save = {
            'endpoint_url': endpoint_url,
            'api_key': api_key,
            'model_type': model_type
        }
        
        if save_config(config_to_save):
            # 同时保存到 session state，立即生效
            st.session_state['endpoint_url'] = endpoint_url
            st.session_state['api_key'] = api_key
            st.session_state['model_type'] = model_type
            
            st.sidebar.success(TEXTS["config_saved_persistent"])
            st.sidebar.caption(f"{TEXTS['config_file']}: {CONFIG_FILE}")
            
            # 提示刷新页面或直接使用
            if language == "中文":
                st.sidebar.info("✅ 配置已永久保存，下次打开自动加载")
            else:
                st.sidebar.info("✅ Configuration saved permanently, auto-loads next time")
        else:
            st.sidebar.warning(TEXTS["config_saved_session"])
    else:
        st.sidebar.error(TEXTS["error_incomplete_config"])

# 显示配置状态
if saved_config and saved_config.get('model_type') == model_type and saved_config.get('endpoint_url'):
    # 有本地保存的配置，自动加载到 session state
    if 'endpoint_url' not in st.session_state:
        st.session_state['endpoint_url'] = saved_config.get('endpoint_url')
        st.session_state['api_key'] = saved_config.get('api_key')
        st.session_state['model_type'] = model_type
    
    st.sidebar.success(f"✅ {TEXTS['config_loaded']}")
    st.sidebar.caption(f"{TEXTS['current_model']}: **{model_type}**")
elif 'endpoint_url' in st.session_state and st.session_state.get('endpoint_url'):
    # Session 中有配置
    st.sidebar.success(f"✅ {TEXTS['config_loaded']}")
    st.sidebar.caption(f"{TEXTS['current_model']}: **{st.session_state.get('model_type', model_type)}**")
else:
    # 没有配置
    if language == "中文":
        st.sidebar.warning("⚠️ 请先输入并保存端点配置")
    else:
        st.sidebar.warning("⚠️ Please enter and save endpoint configuration first")

# 使用说明
st.sidebar.markdown("---")
if language == "中文":
    st.sidebar.markdown("""
### 📖 模型说明

**MedImageParse (2D)**: 
- 👁️ 眼科图像（视网膜、血管、病变）
- 🔬 病理切片
- 🩻 X光、CT单层切片
- 💊 可同时分割多个对象（用 & 分隔）
- 📐 图像尺寸: 1024×1024

**MedImageParse 3D**:
- 🫁 3D 医学影像
- 🧠 CT、MRI 体数据
- ❤️ 器官、肿瘤分割
- 📐 文件格式: NIfTI (.nii, .nii.gz)

### 👁️ 眼科常用场景

- 视网膜病变检测
- 糖尿病性视网膜病变
- 视网膜血管分割
- 视神经盘、黄斑定位
- 青光眼筛查（视杯/视盘比）

### 🎯 支持的对象类别

可以用任何医学英文术语描述目标对象：

**眼科**: retina, optic disc, macula, vessels, lesion  
**器官**: liver, lung, kidney, pancreas, heart, spleen  
**解剖**: brain/heart/eye anatomies  
**病变**: tumor, infection, lesion, abnormality  
**其他**: vessel, fluid, histology structure

**提示**: 
- 使用英文医学术语
- 不限于预设选项
- 可以输入复杂描述，如 "diabetic retinopathy"
""")
else:
    st.sidebar.markdown("""
### 📖 Model Description

**MedImageParse (2D)**: 
- 👁️ Ophthalmology images (retina, vessels, lesions)
- 🔬 Pathology slides
- 🩻 X-ray, CT single slices
- 💊 Multi-object segmentation (use & to separate)
- 📐 Image size: 1024×1024

**MedImageParse 3D**:
- 🫁 3D medical images
- 🧠 CT, MRI volumetric data
- ❤️ Organ and tumor segmentation
- 📐 File format: NIfTI (.nii, .nii.gz)

### 👁️ Common Ophthalmology Use Cases

- Retinal lesion detection
- Diabetic retinopathy
- Retinal vessel segmentation
- Optic disc & macula localization
- Glaucoma screening (cup-to-disc ratio)

### 🎯 Supported Object Categories

Use any medical terminology in English to describe targets:

**Ophthalmology**: retina, optic disc, macula, vessels, lesion  
**Organs**: liver, lung, kidney, pancreas, heart, spleen  
**Anatomies**: brain/heart/eye anatomies  
**Lesions**: tumor, infection, lesion, abnormality  
**Others**: vessel, fluid, histology structure

**Tips**: 
- Use medical terminology in English
- Not limited to preset options
- Supports complex descriptions like "diabetic retinopathy"
""")

# 使用技巧
if language == "中文":
    with st.sidebar.expander("💡 使用技巧"):
        st.markdown("""
**提示词:**
- 用 `&` 分隔多个对象
- 示例: `optic disc & macula`
- 示例: `retinal vessels & hemorrhages`
- 任何医学英文术语都可以

**图像质量:**
- 降低质量可减小传输大小
- 推荐: 85-95%
- 网络慢时可降至 60-70%

**注意事项:**
- 2D 图像自动调整为 1024×1024
- 支持 PNG, JPG, JPEG
- 眼底照片建议高分辨率
- 3D 数据使用 NIfTI 格式

**配置保存:**
- 点保存后永久有效
- 下次打开自动加载
""")
else:
    with st.sidebar.expander("💡 Usage Tips"):
        st.markdown("""
**Prompts:**
- Use `&` to separate multiple objects
- Example: `optic disc & macula`
- Example: `retinal vessels & hemorrhages`
- Any medical terminology works

**Image Quality:**
- Lower quality reduces transfer size
- Recommended: 85-95%
- Can go 60-70% for slow networks

**Notes:**
- 2D images auto-resized to 1024×1024
- Supports PNG, JPG, JPEG
- High resolution recommended for fundus images
- 3D data requires NIfTI format

**Configuration:**
- Click save for permanent storage
- Auto-loads next time
""")

st.markdown("---")

# 主界面：上传图片
st.header(TEXTS["upload_image"])

# 添加使用示例
with st.expander(TEXTS["view_examples"]):
    st.markdown("""
    ### 病理学图像示例
    **乳腺病理**:
    - 提示词: `neoplastic cells & inflammatory cells`
    - 用途: 识别肿瘤细胞和炎症细胞
    
    **肿瘤组织**:
    - 提示词: `tumor tissue & necrosis`
    - 用途: 分割肿瘤组织和坏死区域
    
    ### 放射学图像示例
    **肺部X光/CT**:
    - 提示词: `pulmonary nodule` 或 `lung mass`
    - 用途: 检测肺结节或肿块
    
    **多器官分割**:
    - 提示词: `liver & kidney & pancreas`
    - 用途: 同时分割多个腹部器官
    
    **肿瘤详细分析**:
    - 提示词: `tumor core & enhancing tumor & non-enhancing tumor`
    - 用途: 详细分割肿瘤的不同部分
    
    ### 💡 提示
    - 每个提示词会生成对应的分割掩码
    - 使用 `&` 可以一次分割多个目标
    - 模型会自动将对象分类到16个生物医学类别之一
    """)

# 根据模型类型选择文件上传格式
if model_type == "MedImageParse 3D":
    uploaded_file = st.file_uploader(
        TEXTS["upload_3d"],
        type=['nii', 'nii.gz', 'gz'],
        help="支持NIfTI格式（.nii, .nii.gz）的3D医学影像，常用于CT和MRI扫描" if language == "中文" else "Supports NIfTI format (.nii, .nii.gz) for 3D medical images, commonly used for CT and MRI scans"
    )
else:
    uploaded_file = st.file_uploader(
        TEXTS["upload_2d"],
        type=['png', 'jpg', 'jpeg', 'bmp', 'tiff'],
        help="支持PNG, JPG等常见图像格式。图像会自动调整为1024×1024像素" if language == "中文" else "Supports PNG, JPG and other common image formats. Images will be automatically resized to 1024×1024 pixels"
    )

if uploaded_file is not None:
    # 显示上传的图片
    col1, col2 = st.columns(2)
    
    with col1:
        if model_type == "MedImageParse 3D":
            st.subheader("📊 3D影像预览" if language == "中文" else "📊 3D Image Preview")
            st.info(f"{TEXTS['file_name']}: {uploaded_file.name}")
            st.info(f"{TEXTS['file_size']}: {len(uploaded_file.getvalue()) / 1024:.2f} KB")
            
            # 加载并预览3D影像
            try:
                import nibabel as nib
                import matplotlib.pyplot as plt
                
                # 保存到临时文件并加载
                temp_file = tempfile.NamedTemporaryFile(suffix='.nii.gz', delete=False)
                temp_file.write(uploaded_file.getvalue())
                temp_file.close()
                
                nifti_img = nib.load(temp_file.name)
                
                # 尝试不同的方法加载数据
                img_data = None
                try:
                    # 方法1: 直接获取dataobj
                    img_data = np.asarray(nifti_img.dataobj)
                except:
                    try:
                        # 方法2: 使用get_fdata但不缩放
                        img_data = nifti_img.get_fdata(caching='unchanged')
                    except:
                        # 方法3: 直接读取原始数据
                        img_data = np.array(nifti_img.dataobj)
                
                # 处理特殊数据类型
                if img_data.dtype == np.void or img_data.dtype.kind == 'V':
                    st.warning(TEXTS["warning_rgb_convert"])
                    # 获取原始形状
                    original_shape = img_data.shape
                    
                    # 如果是RGB结构化数组，转换第一个通道
                    if img_data.dtype.names:
                        field_name = img_data.dtype.names[0]
                        img_data = img_data[field_name]
                        st.info(f"{TEXTS['info_use_field']}: {field_name}")
                    else:
                        # 尝试直接转换为uint8
                        img_data_bytes = img_data.tobytes()
                        # 假设是RGB (3字节per voxel)
                        expected_size = original_shape[0] * original_shape[1] * original_shape[2] * 3
                        if len(img_data_bytes) == expected_size:
                            st.info(TEXTS["info_rgb_channel"])
                            img_data = np.frombuffer(img_data_bytes, dtype=np.uint8)
                            img_data = img_data.reshape(original_shape[0], original_shape[1], original_shape[2], 3)
                            img_data = img_data[:, :, :, 0]  # 取红色通道
                        else:
                            st.error(f"{TEXTS['error_size_mismatch']}: {len(img_data_bytes)} vs {expected_size}")
                            raise ValueError("无法解析数据格式" if language == "中文" else "Cannot parse data format")
                    
                    img_data = img_data.astype(np.float64)
                
                # 如果是4D数据（如多时相或RGB），取第一个volume
                if len(img_data.shape) == 4:
                    st.info(f"{TEXTS['info_4d_data']} {img_data.shape}，{'取第一个volume' if language == '中文' else 'using first volume'}")
                    img_data = img_data[:, :, :, 0]
                
                os.unlink(temp_file.name)
                
                st.success(f"✅ {TEXTS['image_shape']}: {img_data.shape}")
                st.info(f"📊 {TEXTS['data_type']}: {img_data.dtype}")
                
                # 保存到session state供后续使用
                st.session_state['img_data_3d'] = img_data
                
                # 选择查看模式
                view_mode = st.radio(
                    TEXTS["view_mode"],
                    [TEXTS["quick_preview"], TEXTS["interactive_browser"]],
                    horizontal=True,
                    help="三视图显示中间切片，交互式浏览器可以滑动查看所有切片" if language == "中文" else "Three-view shows middle slices, interactive browser allows sliding through all slices"
                )
                
                if view_mode == TEXTS["quick_preview"]:
                    # 显示三个正交切片（中间切片）
                    mid_x = img_data.shape[0] // 2
                    mid_y = img_data.shape[1] // 2
                    mid_z = img_data.shape[2] // 2
                    
                    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
                    
                    # 轴向切片 (Axial)
                    axes[0].imshow(img_data[:, :, mid_z], cmap='gray')
                    axes[0].set_title(f'轴向 (Axial) - Slice {mid_z}/{img_data.shape[2]}')
                    axes[0].axis('off')
                    
                    # 冠状切片 (Coronal)
                    axes[1].imshow(img_data[:, mid_y, :], cmap='gray')
                    axes[1].set_title(f'冠状 (Coronal) - Slice {mid_y}/{img_data.shape[1]}')
                    axes[1].axis('off')
                    
                    # 矢状切片 (Sagittal)
                    axes[2].imshow(img_data[mid_x, :, :], cmap='gray')
                    axes[2].set_title(f'矢状 (Sagittal) - Slice {mid_x}/{img_data.shape[0]}')
                    axes[2].axis('off')
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                
                else:  # 交互式切片浏览器
                    st.write(f"**🔍 {TEXTS['interactive_browser']}**")
                    
                    # 选择查看方向
                    if language == "中文":
                        directions = ["轴向 (Axial) - 从头到脚", "冠状 (Coronal) - 从前到后", "矢状 (Sagittal) - 从左到右"]
                    else:
                        directions = ["Axial - Head to Foot", "Coronal - Front to Back", "Sagittal - Left to Right"]
                    
                    direction = st.selectbox(
                        TEXTS["view_direction"],
                        directions
                    )
                    
                    if "轴向" in direction or "Axial" in direction:
                        max_slice = img_data.shape[2] - 1
                        default_slice = img_data.shape[2] // 2
                        slice_idx = st.slider(
                            TEXTS["select_slice"],
                            min_value=0,
                            max_value=max_slice,
                            value=default_slice,
                            help=f"{'拖动滑块浏览' if language == '中文' else 'Drag to browse'} {max_slice + 1} {'个轴向切片' if language == '中文' else 'axial slices'}"
                        )
                        slice_data = img_data[:, :, slice_idx]
                        title = f"{TEXTS['axial']} - Slice {slice_idx}/{max_slice}"
                    
                    elif "冠状" in direction or "Coronal" in direction:
                        max_slice = img_data.shape[1] - 1
                        default_slice = img_data.shape[1] // 2
                        slice_idx = st.slider(
                            TEXTS["select_slice"],
                            min_value=0,
                            max_value=max_slice,
                            value=default_slice,
                            help=f"{'拖动滑块浏览' if language == '中文' else 'Drag to browse'} {max_slice + 1} {'个冠状切片' if language == '中文' else 'coronal slices'}"
                        )
                        slice_data = img_data[:, slice_idx, :]
                        title = f"{TEXTS['coronal']} - Slice {slice_idx}/{max_slice}"
                    
                    else:  # 矢状 / Sagittal
                        max_slice = img_data.shape[0] - 1
                        default_slice = img_data.shape[0] // 2
                        slice_idx = st.slider(
                            TEXTS["select_slice"],
                            min_value=0,
                            max_value=max_slice,
                            value=default_slice,
                            help=f"{'拖动滑块浏览' if language == '中文' else 'Drag to browse'} {max_slice + 1} {'个矢状切片' if language == '中文' else 'sagittal slices'}"
                        )
                        slice_data = img_data[slice_idx, :, :]
                        title = f"{TEXTS['sagittal']} - Slice {slice_idx}/{max_slice}"
                    
                    # 显示选中的切片
                    fig, ax = plt.subplots(figsize=(10, 8))
                    im = ax.imshow(slice_data, cmap='gray')
                    ax.set_title(title, fontsize=14)
                    ax.axis('off')
                    
                    # 添加颜色条显示强度值
                    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
                    cbar.set_label('强度值' if language == "中文" else 'Intensity', rotation=270, labelpad=15)
                    
                    plt.tight_layout()
                    st.pyplot(fig)
                    
                    # 显示当前切片的统计信息
                    col_a, col_b, col_c, col_d = st.columns(4)
                    with col_a:
                        st.metric(TEXTS["min_value"], f"{slice_data.min():.1f}")
                    with col_b:
                        st.metric(TEXTS["max_value"], f"{slice_data.max():.1f}")
                    with col_c:
                        st.metric(TEXTS["mean_value"], f"{slice_data.mean():.1f}")
                    with col_d:
                        st.metric(TEXTS["std_value"], f"{slice_data.std():.1f}")
                
                # 显示完整影像统计信息
                with st.expander("📈 " + ("完整影像统计信息" if language == "中文" else "Complete Image Statistics")):
                    st.write(f"- **{TEXTS['image_shape']}**: {img_data.shape}")
                    st.write(f"- **{TEXTS['data_type']}**: {img_data.dtype}")
                    st.write(f"- **{'数据范围' if language == '中文' else 'Data Range'}**: {img_data.min():.2f} ~ {img_data.max():.2f}")
                    st.write(f"- **{TEXTS['mean_value']}**: {img_data.mean():.2f}")
                    st.write(f"- **{TEXTS['std_value']}**: {img_data.std():.2f}")
                    try:
                        st.write(f"- **{'体素间距' if language == '中文' else 'Voxel Spacing'}**: {nifti_img.header.get_zooms()[:3]}")
                    except:
                        st.write(f"- **{'体素间距' if language == '中文' else 'Voxel Spacing'}**: {'无法获取' if language == '中文' else 'Not available'}")
                
            except Exception as e:
                st.error(f"{TEXTS['error_3d_preview']}: {e}")
                import traceback
                with st.expander("查看错误详情" if language == "中文" else "View Error Details"):
                    st.code(traceback.format_exc())
                
        else:
            st.subheader("📷 " + ("上传的图片" if language == "中文" else "Uploaded Image"))
            try:
                image = Image.open(uploaded_file)
                st.image(image, width=400)
                st.info(f"{TEXTS['original_size']}: {image.size[0]} x {image.size[1]}")
                uploaded_file.seek(0)
            except:
                st.info(f"{TEXTS['file_name']}: {uploaded_file.name}")
    
    with col2:
        st.subheader("🚀 " + ("调用模型" if language == "中文" else "Call Model"))
        
        if 'endpoint_url' not in st.session_state or 'api_key' not in st.session_state:
            st.warning(TEXTS["warning_save_config"])
        else:
            # 输入分割对象
            st.write(f"**{TEXTS['prompt_input']}:**")
            st.info(TEXTS["prompt_help"])
            
            if language == "中文":
                st.caption("💡 提示：模型会将识别的对象归类到16个生物医学类别")
            else:
                st.caption("💡 Tip: Model classifies objects into 16 biomedical categories")
            
            # 预设提示词模板 - 根据语言选择不同的选项列表
            if language == "中文":
                category_options = [
                    TEXTS["custom"],
                    "--- 眼科 (Ophthalmology) ⭐ ---",
                    "眼部完整解剖结构",
                    "视网膜",
                    "视网膜血管",
                    "视神经盘",
                    "黄斑",
                    "视网膜病变",
                    "视网膜出血",
                    "视网膜渗出",
                    "糖尿病性视网膜病变",
                    "青光眼 - 视杯视盘",
                    "白内障",
                    "角膜",
                    "晶状体",
                    "玻璃体",
                    "眼底病变检测",
                    "视网膜新生血管",
                    "视网膜水肿",
                    "视网膜脱离",
                    "--- 病理学 (Pathology) ---",
                    "肿瘤细胞与炎症细胞",
                    "肿瘤组织与坏死",
                    "组织结构分析",
                    "乳腺病理 - 肿瘤与炎症",
                    "--- 放射学 - 胸部 ---",
                    "肺部结节",
                    "肺部肿块与实变",
                    "肺 - 多对象",
                    "--- 放射学 - 腹部 ---",
                    "肝脏",
                    "肝脏与肾脏",
                    "肝脏、肾脏、胰腺",
                    "所有腹部器官",
                    "--- 放射学 - 肿瘤 ---",
                    "肿瘤核心",
                    "肿瘤详细分析（三部分）",
                    "肿瘤与周围水肿",
                    "--- 放射学 - 脑部 ---",
                    "脑部解剖结构",
                    "脑肿瘤",
                    "脑出血",
                    "--- 放射学 - 心脏 ---",
                    "心脏解剖",
                    "心脏腔室",
                    "--- 异常与病变 ---",
                    "感染",
                    "感染与病变",
                    "液体积聚",
                    "囊肿",
                    "钙化",
                    "--- 血管 ---",
                    "血管",
                    "动脉",
                    "静脉",
                    "--- 其他器官 ---",
                    "肾脏",
                    "胰腺",
                    "脾脏",
                    "--- 复杂场景 ---",
                    "异常组织",
                    "所有病变"
                ]
            else:
                category_options = [
                    TEXTS["custom"],
                    "--- Ophthalmology ⭐ ---",
                    "Complete Eye Anatomy",
                    "Retina",
                    "Retinal Vessels",
                    "Optic Disc",
                    "Macula",
                    "Retinal Lesions",
                    "Retinal Hemorrhages",
                    "Retinal Exudates",
                    "Diabetic Retinopathy",
                    "Glaucoma - Cup & Disc",
                    "Cataract",
                    "Cornea",
                    "Lens",
                    "Vitreous",
                    "Fundus Lesion Detection",
                    "Retinal Neovascularization",
                    "Retinal Edema",
                    "Retinal Detachment",
                    "--- Pathology ---",
                    "Neoplastic & Inflammatory Cells",
                    "Tumor Tissue & Necrosis",
                    "Tissue Structure Analysis",
                    "Breast Pathology - Tumor & Inflammation",
                    "--- Radiology - Chest ---",
                    "Pulmonary Nodule",
                    "Lung Mass & Consolidation",
                    "Lung - Multi-object",
                    "--- Radiology - Abdomen ---",
                    "Liver",
                    "Liver & Kidney",
                    "Liver, Kidney & Pancreas",
                    "All Abdominal Organs",
                    "--- Radiology - Tumor ---",
                    "Tumor Core",
                    "Tumor Detailed Analysis (3 parts)",
                    "Tumor & Surrounding Edema",
                    "--- Radiology - Brain ---",
                    "Brain Anatomies",
                    "Brain Tumor",
                    "Brain Hemorrhage",
                    "--- Radiology - Heart ---",
                    "Heart Anatomy",
                    "Heart Chambers",
                    "--- Abnormalities & Lesions ---",
                    "Infection",
                    "Infection & Lesion",
                    "Fluid Accumulation",
                    "Cyst",
                    "Calcification",
                    "--- Vessels ---",
                    "Vessel",
                    "Artery",
                    "Vein",
                    "--- Other Organs ---",
                    "Kidney",
                    "Pancreas",
                    "Spleen",
                    "--- Complex Scenarios ---",
                    "Abnormal Tissue",
                    "All Lesions"
                ]
            
            prompt_category = st.selectbox(
                TEXTS["prompt_category"],
                category_options
            )
            
            # 根据选择设置默认提示词（同时支持中英文键）
            prompt_templates = {
                # 眼科 (中文)
                "眼部完整解剖结构": "eye anatomies",
                "视网膜": "retina",
                "视网膜血管": "retinal vessels",
                "视神经盘": "optic disc",
                "黄斑": "macula",
                "视网膜病变": "retinal lesion",
                "视网膜出血": "retinal hemorrhage",
                "视网膜渗出": "retinal exudates",
                "糖尿病性视网膜病变": "diabetic retinopathy lesions & microaneurysms & hemorrhages",
                "青光眼 - 视杯视盘": "optic cup & optic disc",
                "白内障": "cataract",
                "角膜": "cornea",
                "晶状体": "lens",
                "玻璃体": "vitreous",
                "眼底病变检测": "retinal lesion & hemorrhage & exudates",
                "视网膜新生血管": "retinal neovascularization",
                "视网膜水肿": "retinal edema & macular edema",
                "视网膜脱离": "retinal detachment",
                # 眼科 (英文)
                "Complete Eye Anatomy": "eye anatomies",
                "Retina": "retina",
                "Retinal Vessels": "retinal vessels",
                "Optic Disc": "optic disc",
                "Macula": "macula",
                "Retinal Lesions": "retinal lesion",
                "Retinal Hemorrhages": "retinal hemorrhage",
                "Retinal Exudates": "retinal exudates",
                "Diabetic Retinopathy": "diabetic retinopathy lesions & microaneurysms & hemorrhages",
                "Glaucoma - Cup & Disc": "optic cup & optic disc",
                "Cataract": "cataract",
                "Cornea": "cornea",
                "Lens": "lens",
                "Vitreous": "vitreous",
                "Fundus Lesion Detection": "retinal lesion & hemorrhage & exudates",
                "Retinal Neovascularization": "retinal neovascularization",
                "Retinal Edema": "retinal edema & macular edema",
                "Retinal Detachment": "retinal detachment",
                
                # 病理学
                "肿瘤细胞与炎症细胞": "neoplastic cells & inflammatory cells",
                "肿瘤组织与坏死": "tumor tissue & necrosis",
                "组织结构分析": "histology structure",
                "乳腺病理 - 肿瘤与炎症": "neoplastic cells in breast pathology & inflammatory cells",
                "Neoplastic & Inflammatory Cells": "neoplastic cells & inflammatory cells",
                "Tumor Tissue & Necrosis": "tumor tissue & necrosis",
                "Tissue Structure Analysis": "histology structure",
                "Breast Pathology - Tumor & Inflammation": "neoplastic cells in breast pathology & inflammatory cells",
                
                # 放射学 - 胸部
                "肺部结节": "pulmonary nodule",
                "肺部肿块与实变": "lung mass & consolidation",
                "肺 - 多对象": "lung & nodule & mass",
                "Pulmonary Nodule": "pulmonary nodule",
                "Lung Mass & Consolidation": "lung mass & consolidation",
                "Lung - Multi-object": "lung & nodule & mass",
                
                # 放射学 - 腹部
                "肝脏": "liver",
                "肝脏与肾脏": "liver & kidney",
                "肝脏、肾脏、胰腺": "liver & kidney & pancreas",
                "所有腹部器官": "liver & lung & kidney & pancreas & heart & spleen",
                "Liver": "liver",
                "Liver & Kidney": "liver & kidney",
                "Liver, Kidney & Pancreas": "liver & kidney & pancreas",
                "All Abdominal Organs": "liver & lung & kidney & pancreas & heart & spleen",
                
                # 肿瘤
                "肿瘤核心": "tumor core",
                "肿瘤详细分析（三部分）": "tumor core & enhancing tumor & non-enhancing tumor",
                "肿瘤与周围水肿": "tumor & edema",
                "Tumor Core": "tumor core",
                "Tumor Detailed Analysis (3 parts)": "tumor core & enhancing tumor & non-enhancing tumor",
                "Tumor & Surrounding Edema": "tumor & edema",
                
                # 脑部
                "脑部解剖结构": "brain anatomies",
                "脑肿瘤": "brain tumor",
                "脑出血": "brain hemorrhage",
                "Brain Anatomies": "brain anatomies",
                "Brain Tumor": "brain tumor",
                "Brain Hemorrhage": "brain hemorrhage",
                
                # 心脏
                "心脏解剖": "heart anatomies",
                "心脏腔室": "heart chambers",
                "Heart Anatomy": "heart anatomies",
                "Heart Chambers": "heart chambers",
                
                # 异常与病变
                "感染": "infection",
                "感染与病变": "infection & lesion",
                "液体积聚": "fluid disturbance",
                "囊肿": "cyst",
                "钙化": "calcification",
                "Infection": "infection",
                "Infection & Lesion": "infection & lesion",
                "Fluid Accumulation": "fluid disturbance",
                "Cyst": "cyst",
                "Calcification": "calcification",
                
                # 血管
                "血管": "vessel",
                "动脉": "artery",
                "静脉": "vein",
                "Vessel": "vessel",
                "Artery": "artery",
                "Vein": "vein",
                
                # 其他器官
                "肾脏": "kidney",
                "胰腺": "pancreas",
                "脾脏": "spleen",
                "Kidney": "kidney",
                "Pancreas": "pancreas",
                "Spleen": "spleen",
                
                # 复杂场景
                "异常组织": "abnormal tissue",
                "所有病变": "tumor & infection & lesion & abnormality",
                "Abnormal Tissue": "abnormal tissue",
                "All Lesions": "tumor & infection & lesion & abnormality"
            }
            
            # 根据类别获取默认提示词
            if prompt_category in prompt_templates:
                default_prompt = prompt_templates[prompt_category]
            elif prompt_category.startswith("---") or prompt_category == TEXTS["custom"] or prompt_category.strip().lower() in ["自定义", "custom"]:
                # 若session_state中没有custom_prompt，默认给nodule
                default_prompt = st.session_state.get('custom_prompt', 'nodule') or 'nodule'
            else:
                default_prompt = "nodule"
            
            # 显示当前选择的提示词（只读显示）
            if prompt_category in prompt_templates:
                st.success(f"✅ {TEXTS['selected']}: **{default_prompt}**")
                text_prompt = default_prompt
                # 提供修改选项
                if st.checkbox("✏️ " + ("修改此提示词" if language == "中文" else "Modify this prompt"), key=f"edit_{prompt_category}"):
                    custom_text = st.text_input(
                        "自定义提示词" if language == "中文" else "Custom prompt",
                        value=default_prompt,
                        help="修改后的提示词" if language == "中文" else "Modified prompt"
                    )
                    text_prompt = custom_text
            elif prompt_category.startswith("---") or prompt_category == TEXTS["custom"] or prompt_category.strip().lower() in ["自定义", "custom"]:
                # 自定义输入
                text_prompt = st.text_input(
                    TEXTS["input_objects"],
                    value=default_prompt,
                    help="例如: tumor & nodule 或 liver & kidney & pancreas" if language == "中文" else "Example: tumor & nodule or liver & kidney & pancreas"
                )
                # 保证 custom_prompt 始终有值
                if text_prompt:
                    st.session_state['custom_prompt'] = text_prompt
            else:
                # 兜底，防止text_prompt为空
                text_prompt = default_prompt or 'nodule'
            
            # 显示提示词说明
            if '&' in text_prompt:
                objects = [obj.strip() for obj in text_prompt.split('&')]
                st.caption(f"✅ {TEXTS['will_segment']} {len(objects)} {TEXTS['objects']}: {', '.join(objects)}")
            else:
                st.caption(f"✅ {TEXTS['will_segment']} 1 {TEXTS['objects']}: {text_prompt}")
            
            # 图片质量控制 (仅2D模型需要)
            if model_type == "MedImageParse (2D)":
                image_quality = st.slider(
                    TEXTS["image_quality"],
                    min_value=50,
                    max_value=100,
                    value=85,
                    step=5,
                    help="降低质量可减小文件大小" if language == "中文" else "Lower quality reduces file size"
                )
            else:
                image_quality = 85  # 3D模型不需要，设置默认值
            
            # 调用模型按钮
            if st.button(TEXTS["analyze"], type="primary"):
                with st.spinner(TEXTS["analyzing"]):
                    try:
                        uploaded_file.seek(0)
                        
                        if model_type == "MedImageParse 3D":
                            # ===== 3D模型处理逻辑 =====
                            # 读取NIfTI文件并编码为base64
                            nifti_bytes = uploaded_file.read()
                            
                            # 验证文件不为空
                            if len(nifti_bytes) == 0:
                                st.error(TEXTS["error_empty_file"])
                                raise ValueError("Empty file")
                            
                            # 检查文件头（NIfTI文件应该有特定的magic number）
                            if len(nifti_bytes) < 348:
                                st.warning(f"{TEXTS['error_file_small']} ({len(nifti_bytes)} {TEXTS['bytes_info']})")
                            
                            nifti_base64 = base64.b64encode(nifti_bytes).decode('utf-8')
                            
                            st.info(f"📦 {TEXTS['data_size']}: {len(nifti_bytes) / 1024:.2f} KB")
                            st.info(f"📦 {'Base64编码后大小' if language == '中文' else 'Base64 encoded size'}: {len(nifti_base64) / 1024:.2f} KB")
                            
                            # 准备请求数据（3D模型格式）
                            data = {
                                "input_data": {
                                    "columns": ["image", "text"],
                                    "index": [0],
                                    "data": [[nifti_base64, text_prompt]]
                                }
                            }
                        else:
                            # ===== 2D模型处理逻辑 =====
                            image = Image.open(uploaded_file)
                            
                            # 调整图片大小为 1024x1024
                            target_size = (1024, 1024)
                            background = Image.new('RGB', target_size, (0, 0, 0))
                            
                            # 计算缩放比例
                            img_ratio = image.size[0] / image.size[1]
                            
                            if img_ratio > 1.0:
                                new_width = target_size[0]
                                new_height = int(target_size[0] / img_ratio)
                            else:
                                new_height = target_size[1]
                                new_width = int(target_size[1] * img_ratio)
                            
                            # 调整大小
                            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            
                            # 粘贴到黑色背景中心
                            offset_x = (target_size[0] - new_width) // 2
                            offset_y = (target_size[1] - new_height) // 2
                            
                            if image.mode == 'RGBA':
                                image = image.convert('RGB')
                            
                            background.paste(image, (offset_x, offset_y))
                            image = background
                            
                            # 转换为JPEG并编码
                            buffer = io.BytesIO()
                            image.save(buffer, format='JPEG', quality=image_quality, optimize=True)
                            image_bytes = buffer.getvalue()
                            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                            st.info(f"📦 {TEXTS['data_size'] if 'data_size' in TEXTS else ('数据大小' if language == '中文' else 'Data size')}: {len(image_bytes) / 1024:.2f} KB")
                            # 准备请求数据（2D模型格式）
                            data = {
                                "input_data": {
                                    "columns": ["image", "text"],
                                    "index": [0],
                                    "data": [[image_base64, text_prompt]]
                                }
                            }
                        
                        # 发送请求
                        body = str.encode(json.dumps(data))
                        
                        # 显示调试信息
                        with st.expander(TEXTS["debug_info"]):
                            st.write(f"**{'模型类型' if language == '中文' else 'Model Type'}**: {model_type}")
                            st.write(f"**Endpoint**: {st.session_state['endpoint_url']}")
                            st.write(f"**{'请求体大小' if language == '中文' else 'Request Body Size'}**: {len(body) / 1024:.2f} KB")
                            st.write(f"**{'提示词' if language == '中文' else 'Prompt'}**: `{text_prompt}`")
                            st.write(f"**{'数据结构' if language == '中文' else 'Data Structure'}**:")
                            st.json({
                                "columns": data["input_data"]["columns"],
                                "index": data["input_data"]["index"],
                                "data_length": len(data["input_data"]["data"]),
                                "text": data["input_data"]["data"][0][1],
                                "image_length": len(data["input_data"]["data"][0][0])
                            })
                        
                        headers = {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'Authorization': ('Bearer ' + st.session_state['api_key'])
                        }
                        
                        req = urllib.request.Request(
                            st.session_state['endpoint_url'],
                            body,
                            headers
                        )
                        
                        response = urllib.request.urlopen(req, timeout=300)
                        result = response.read()
                        result_json = json.loads(result.decode('utf-8'))
                        
                        st.success(TEXTS["success"])
                        
                        # 显示结果
                        st.subheader(TEXTS["results"])
                        
                        try:
                            # 解析返回数据
                            if isinstance(result_json, list) and len(result_json) > 0:
                                result_data = result_json[0]
                                
                                # ===== 3D模型结果处理 =====
                                if model_type == "MedImageParse 3D" and isinstance(result_data, dict) and 'nifti_file' in result_data:
                                    st.info("🔄 " + ("正在解码3D分割结果..." if language == "中文" else "Decoding 3D segmentation result..."))
                                    
                                    nifti_file_str = result_data['nifti_file']
                                    mask_data = decode_base64_to_nifti(nifti_file_str)
                                    
                                    if mask_data is not None:
                                        st.success(f"✅ {'3D分割掩码解码成功！' if language == '中文' else '3D segmentation mask decoded successfully!'}")
                                        st.info(f"📏 {'3D数据形状' if language == '中文' else '3D data shape'}: {mask_data.shape}")
                                        
                                        # 加载原始上传的NIfTI文件用于对比
                                        try:
                                            import nibabel as nib
                                            uploaded_file.seek(0)
                                            
                                            # 保存到临时文件并加载
                                            temp_file = tempfile.NamedTemporaryFile(suffix='.nii.gz', delete=False)
                                            temp_file.write(uploaded_file.read())
                                            temp_file.close()
                                            
                                            original_nifti = nib.load(temp_file.name)
                                            original_data = original_nifti.get_fdata()
                                            os.unlink(temp_file.name)
                                            
                                            st.info(f"📏 {'原始影像形状' if language == '中文' else 'Original image shape'}: {original_data.shape}")
                                            
                                            # 检查并调整维度匹配
                                            if mask_data.shape != original_data.shape:
                                                st.warning(f"⚠️ {'维度不匹配，尝试调整...' if language == '中文' else 'Dimension mismatch, trying to adjust...'}")
                                                # 尝试转置匹配
                                                if mask_data.shape == (original_data.shape[2], original_data.shape[0], original_data.shape[1]):
                                                    mask_data = np.transpose(mask_data, (1, 2, 0))
                                                    st.success(f"✅ 已转置为: {mask_data.shape}")
                                                elif mask_data.shape == (original_data.shape[1], original_data.shape[2], original_data.shape[0]):
                                                    mask_data = np.transpose(mask_data, (2, 0, 1))
                                                    st.success(f"✅ 已转置为: {mask_data.shape}")
                                                elif mask_data.shape == (original_data.shape[0], original_data.shape[2], original_data.shape[1]):
                                                    mask_data = np.transpose(mask_data, (0, 2, 1))
                                                    st.success(f"✅ 已转置为: {mask_data.shape}")
                                            
                                            # 显示原始影像和分割结果的对比
                                            st.write("**📊 " + ("原始影像 vs 分割结果对比" if language == "中文" else "Original Image vs Segmentation Comparison") + "**" + ("（显示包含分割的切片）" if language == "中文" else " (Showing slices with segmentation)") + "：")
                                            
                                            import matplotlib.pyplot as plt
                                            
                                            # 找到包含分割结果的切片
                                            slices_with_mask = []
                                            st.info(f"🔍 {'扫描' if language == '中文' else 'Scanning'} {mask_data.shape[2]} {'个切片' if language == '中文' else 'slices'}...")
                                            for i in range(mask_data.shape[2]):
                                                slice_sum = mask_data[:, :, i].sum()
                                                if slice_sum > 0:
                                                    slices_with_mask.append(i)
                                            
                                            # 显示统计信息
                                            st.write(f"**掩码统计**:")
                                            st.write(f"- 总体素数: {mask_data.size}")
                                            st.write(f"- 非零体素: {np.count_nonzero(mask_data)}")
                                            st.write(f"- 值范围: {mask_data.min():.2f} - {mask_data.max():.2f}")
                                            
                                            if slices_with_mask:
                                                # 最多显示8对对比图
                                                num_slices = min(8, len(slices_with_mask))
                                                selected_slices = [slices_with_mask[int(i * len(slices_with_mask) / num_slices)] 
                                                                 for i in range(num_slices)]
                                                
                                                fig, axes = plt.subplots(num_slices, 3, figsize=(15, 4 * num_slices))
                                                if num_slices == 1:
                                                    axes = axes.reshape(1, -1)
                                                
                                                for idx, slice_num in enumerate(selected_slices):
                                                    # 原始影像
                                                    axes[idx, 0].imshow(original_data[:, :, slice_num], cmap='gray')
                                                    axes[idx, 0].set_title(f'原始影像 - Slice {slice_num}')
                                                    axes[idx, 0].axis('off')
                                                    
                                                    # 分割掩码
                                                    axes[idx, 1].imshow(mask_data[:, :, slice_num], cmap='jet', alpha=0.8)
                                                    axes[idx, 1].set_title(f'分割掩码 - Slice {slice_num}')
                                                    axes[idx, 1].axis('off')
                                                    
                                                    # 叠加显示
                                                    axes[idx, 2].imshow(original_data[:, :, slice_num], cmap='gray')
                                                    axes[idx, 2].imshow(mask_data[:, :, slice_num], cmap='jet', alpha=0.5)
                                                    axes[idx, 2].set_title(f'叠加显示 - Slice {slice_num}')
                                                    axes[idx, 2].axis('off')
                                                
                                                plt.tight_layout()
                                                st.pyplot(fig)
                                                
                                                st.info(f"✅ {'共找到' if language == '中文' else 'Found'} {len(slices_with_mask)} {'个包含分割结果的切片，显示其中' if language == '中文' else 'slices with segmentation, displaying'} {num_slices} {'个' if language == '中文' else ''}")
                                            else:
                                                st.warning(TEXTS["warning_no_slices"])
                                        
                                        except Exception as viz_error:
                                            st.warning(f"⚠️ {'无法加载原始影像进行对比' if language == '中文' else 'Cannot load original image for comparison'}: {viz_error}")
                                            # 降级为只显示分割结果
                                            st.write("**" + ("分割掩码切片预览" if language == "中文" else "Segmentation Mask Slice Preview") + "**：")
                                            fig = plot_3d_slices(mask_data, max_slices=16)
                                            if fig:
                                                st.pyplot(fig)
                                        
                                        # 提供下载选项
                                        st.download_button(
                                            label="📥 下载完整3D分割结果（JSON格式）",
                                            data=json.dumps(result_json, indent=2, ensure_ascii=False),
                                            file_name="segmentation_3d_result.json",
                                            mime="application/json"
                                        )
                                    else:
                                        st.error("❌ " + ("无法解码3D分割结果" if language == "中文" else "Cannot decode 3D segmentation result"))
                                
                                # ===== 2D模型结果处理 =====
                                elif isinstance(result_data, dict) and 'image_features' in result_data:
                                    image_features = result_data['image_features']
                                    
                                    # 解码 base64 图像
                                    if isinstance(image_features, str):
                                        try:
                                            # 尝试base64解码
                                            decoded_bytes = base64.b64decode(image_features)
                                            st.info(f"{TEXTS['base64_decoded']}: {len(decoded_bytes)} {TEXTS['bytes']}")
                                            
                                            mask_image = None
                                            
                                            # 先检查是否是标准图像格式
                                            try:
                                                test_image = Image.open(io.BytesIO(decoded_bytes))
                                                mask_image = test_image
                                                st.success(f"✅ {'识别为标准图像格式！' if language == '中文' else 'Recognized as standard image format!'} {'尺寸' if language == '中文' else 'Size'}: {mask_image.size}, {'模式' if language == '中文' else 'Mode'}: {mask_image.mode}")
                                            except:
                                                # 不是标准图像格式，尝试作为原始数据处理
                                                pass
                                            
                                            # 如果不是标准图像，尝试作为numpy数组
                                            if mask_image is None:
                                                import numpy as np
                                                
                                                st.info(TEXTS["parsing_array"])
                                                
                                                # 尝试不同的方式解析
                                                # 1. 尝试作为原始numpy数组
                                                try:
                                                    mask_array = np.frombuffer(decoded_bytes, dtype=np.uint8)
                                                    st.info(f"{TEXTS['array_length']}: {len(mask_array)}")
                                                    
                                                    # 尝试reshape为1024x1024
                                                    if len(mask_array) == 1024 * 1024:
                                                        mask_array = mask_array.reshape(1024, 1024)
                                                        st.success(f"✅ {'成功重塑为 1024x1024！' if language == '中文' else 'Successfully reshaped to 1024x1024!'}")
                                                    elif len(mask_array) == 512 * 512:
                                                        mask_array = mask_array.reshape(512, 512)
                                                        st.success(f"✅ {'成功重塑为 512x512！' if language == '中文' else 'Successfully reshaped to 512x512!'}")
                                                    else:
                                                        # 尝试推断尺寸
                                                        size = int(np.sqrt(len(mask_array)))
                                                        if size * size == len(mask_array):
                                                            mask_array = mask_array.reshape(size, size)
                                                            st.success(f"✅ {'成功重塑为' if language == '中文' else 'Successfully reshaped to'} {size}x{size}！")
                                                        else:
                                                            st.warning(f"{TEXTS['cannot_infer_size']}: {len(mask_array)}")
                                                            # 尝试去掉可能的头部信息
                                                            if len(mask_array) == 1024 * 1024 + 3:
                                                                mask_array = mask_array[3:].reshape(1024, 1024)
                                                                st.success(TEXTS["reshape_success"])
                                                            else:
                                                                mask_array = None
                                                    
                                                    if mask_array is not None and len(mask_array.shape) == 2:
                                                        # 转换为图像
                                                        mask_image = Image.fromarray(mask_array, mode='L')
                                                        st.info(TEXTS["converted_grayscale"])
                                                    else:
                                                        mask_image = None
                                                        
                                                except Exception as array_error:
                                                    st.error(f"❌ numpy数组解析失败: {str(array_error)}")
                                                    mask_image = None
                                        
                                        except Exception as outer_error:
                                            st.error(f"❌ Base64解码失败: {str(outer_error)}")
                                            mask_image = None
                                        
                                        if mask_image:
                                            # 显示图像
                                            col_res1, col_res2, col_res3 = st.columns(3)
                                            
                                            with col_res1:
                                                st.write(f"**{TEXTS['original_image']}**")
                                                st.image(image, width=300)
                                                st.caption(f"{TEXTS['size']}: {image.size[0]}×{image.size[1]}")
                                            
                                            with col_res2:
                                                st.write(f"**{TEXTS['seg_mask']}**")
                                                st.image(mask_image, width=300)
                                                st.caption(f"{TEXTS['size']}: {mask_image.size[0]}×{mask_image.size[1]}")
                                            
                                            with col_res3:
                                                st.write(f"**{TEXTS['overlay']}**")
                                                # 简单叠加
                                                try:
                                                    combined = Image.blend(
                                                        image.resize(mask_image.size).convert('RGB'), 
                                                        mask_image.convert('RGB'), 
                                                        0.5
                                                    )
                                                    st.image(combined, width=300)
                                                    st.caption(TEXTS["mask_overlay"])
                                                except:
                                                    st.write("无法生成叠加效果" if language == "中文" else "Cannot generate overlay")
                                            
                                            # 显示分割信息
                                            if 'text_features' in result_data:
                                                st.markdown("---")
                                                st.subheader(TEXTS["seg_classification"])
                                                text_features = result_data['text_features']
                                                
                                                if isinstance(text_features, list):
                                                    col_info1, col_info2 = st.columns(2)
                                                    
                                                    with col_info1:
                                                        st.write(f"**{TEXTS['detected_objects']}:**")
                                                        for i, obj in enumerate(text_features, 1):
                                                            st.write(f"{i}. {obj}")
                                                    
                                                    with col_info2:
                                                        st.write(f"**{TEXTS['input_prompts']}:**")
                                                        input_objects = text_prompt.split('&')
                                                        for i, obj in enumerate(input_objects, 1):
                                                            st.write(f"{i}. {obj.strip()}")
                                                        
                                                        if len(text_features) != len(input_objects):
                                                            st.warning(f"⚠️ {'检测数量' if language == '中文' else 'Detected'}({len(text_features)}){'与输入' if language == '中文' else 'vs Input'}({len(input_objects)}){'不匹配' if language == '中文' else 'mismatch'}")
                                            
                                            # 下载按钮
                                            st.markdown("---")
                                            col_dl1, col_dl2 = st.columns(2)
                                            
                                            with col_dl1:
                                                buf = io.BytesIO()
                                                mask_image.save(buf, format='PNG')
                                                st.download_button(
                                                    f"📥 {TEXTS['download_mask']}",
                                                    data=buf.getvalue(),
                                                    file_name="mask.png",
                                                    mime="image/png"
                                                )
                                            
                                            with col_dl2:
                                                st.download_button(
                                                    f"📥 {TEXTS['download_json']}",
                                                    data=json.dumps(result_json, indent=2),
                                                    file_name="result.json",
                                                    mime="application/json"
                                                )
                                        else:
                                            st.error("无法生成掩码图像" if language == "中文" else "Cannot generate mask image")
                                    else:
                                        st.warning("image_features " + ("不是字符串格式" if language == "中文" else "is not a string format"))
                                        st.json(result_json)
                                else:
                                    st.warning("未找到 image_features 字段" if language == "中文" else "image_features field not found")
                                    st.json(result_json)
                            else:
                                st.warning("返回数据格式异常" if language == "中文" else "Abnormal data format returned")
                                st.json(result_json)
                        
                        except Exception as e:
                            st.error(f"❌ {'处理结果时出错' if language == '中文' else 'Error processing results'}: {str(e)}")
                            
                            # 显示数据结构帮助调试
                            st.write("**" + ("数据结构信息" if language == "中文" else "Data Structure Information") + "：**")
                            st.write(f"- {'数据类型' if language == '中文' else 'Data Type'}: {type(result_json)}")
                            
                            if isinstance(result_json, list) and len(result_json) > 0:
                                st.write(f"- {'列表长度' if language == '中文' else 'List Length'}: {len(result_json)}")
                                st.write(f"- {'第一个元素类型' if language == '中文' else 'First Element Type'}: {type(result_json[0])}")
                                
                                if isinstance(result_json[0], dict):
                                    st.write(f"- {'字典的键' if language == '中文' else 'Dictionary Keys'}: {list(result_json[0].keys())}")
                                    
                                    if 'image_features' in result_json[0]:
                                        img_feat = result_json[0]['image_features']
                                        st.write(f"- {'image_features 类型' if language == '中文' else 'image_features Type'}: {type(img_feat)}")
                                        
                                        if isinstance(img_feat, str):
                                            st.write(f"- 字符串长度: {len(img_feat)}")
                                            st.write(f"- 前50个字符: {img_feat[:50]}")
                            
                            with st.expander("查看完整原始数据"):
                                st.json(result_json)
                        
                    except urllib.error.HTTPError as error:
                        st.error(f"❌ HTTP请求失败，状态码: {error.code}")
                        error_details = error.read().decode("utf8", 'ignore')
                        with st.expander("查看错误详情"):
                            st.code(error_details)
                    
                    except Exception as e:
                        st.error(f"❌ 发生错误: {str(e)}")
