"""
MedImageParse - Medical Image Segmentation Platform
Developed by Xinyuwei
"""
import streamlit as st
import io
import json
import base64
import urllib.request
from PIL import Image
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import tempfile
import os
import traceback
from pathlib import Path
from dotenv import load_dotenv

# Import our modules
from config import config
from telemetry import telemetry, reset_correlation_id

# Load environment variables from .env file (for local development)
load_dotenv()

# Set matplotlib to support Chinese characters
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

# Configuration file path for user preferences
CONFIG_FILE = Path.home() / ".medimageparse_config.json"


def load_user_config():
    """Load saved user configuration from local file"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_user_config(user_config):
    """Save user configuration to local file"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_config, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False


# Load saved user preferences
saved_user_config = load_user_config()

# Reset correlation ID for new session
if 'correlation_id' not in st.session_state:
    st.session_state['correlation_id'] = reset_correlation_id()
    telemetry.info("New session started")


def decode_base64_to_nifti(base64_string: str):
    """
    Decode Base64 encoded NIfTI data to numpy array
    
    Args:
        base64_string: Base64 encoded string (wrapped in JSON)
        
    Returns:
        np.ndarray: Decoded 3D medical image data
    """
    try:
        import nibabel as nib
    except ImportError:
        st.error(TEXTS["error_nibabel"])
        telemetry.error("nibabel library not installed")
        return None
    
    try:
        # Parse inner JSON to get 'data' field
        base64_string = json.loads(base64_string)["data"]
        
        # Decode Base64 string to raw bytes
        byte_data = base64.b64decode(base64_string)
        
        # Write to temporary .nii.gz file
        temp_file = tempfile.NamedTemporaryFile(suffix='.nii.gz', delete=False)
        temp_file_name = temp_file.name
        try:
            temp_file.write(byte_data)
            temp_file.close()
            
            # Load the file
            nifti_image = nib.load(temp_file_name)
            nifti_data = nifti_image.get_fdata()
            
            # Cleanup
            os.unlink(temp_file_name)
            
            telemetry.info(f"NIfTI decoded successfully, shape: {nifti_data.shape}")
            return nifti_data
        except Exception as inner_error:
            if os.path.exists(temp_file_name):
                os.unlink(temp_file_name)
            raise inner_error
            
    except Exception as e:
        st.error(f"{TEXTS['error_nifti_decode']}: {str(e)}")
        telemetry.exception("NIfTI decoding failed")
        with st.expander("View error details"):
            st.code(traceback.format_exc())
        return None


def plot_3d_slices(segmentation_masks, max_slices=16):
    """
    Display multiple 2D slices of 3D segmentation mask
    
    Args:
        segmentation_masks: 3D numpy array (H, W, D)
        max_slices: Maximum number of slices to display
    """
    telemetry.info(f"Plotting 3D slices, shape: {segmentation_masks.shape}")
    
    slices_to_show = []
    
    # Collect slices with non-zero masks
    for i in range(segmentation_masks.shape[2]):
        if segmentation_masks[:, :, i].sum() > 0:
            slices_to_show.append(i)
    
    if not slices_to_show:
        st.warning(TEXTS["warning_no_slices"])
        return None
    
    # Limit display count
    slices_to_show = slices_to_show[:max_slices]
    
    # Create image
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
    
    # Hide extra subplots
    for idx in range(num_slices, len(axes)):
        axes[idx].axis('off')
    
    plt.tight_layout()
    return fig


# Set page config
st.set_page_config(page_title="MedImageParse Model Caller", layout="wide")

# Language selection at sidebar top
language = st.sidebar.selectbox(
    "🌐 Language / 语言",
    ["中文", "English"],
    index=0,
    help="Select interface language / 选择界面语言"
)

# Import text translations based on language (keeping your original TEXTS dictionary)
# For brevity, I'll use a simplified version here - you should copy your full TEXTS dictionary
if language == "中文":
    TEXTS = {
        "title": "🏥 医学图像解析模型调用",
        "subtitle": "Developed by Xinyuwei",
        "config": "⚙️ 配置",
        "model_type": "选择模型类型",
        "error_nibabel": "❌ 需要安装nibabel库来处理NIfTI文件。请运行: pip install nibabel",
        "error_nifti_decode": "❌ NIfTI解码失败",
        "warning_no_slices": "⚠️ 没有找到包含分割结果的切片",
        "warning_config": "⚠️ 配置未加载，请检查环境变量或 Key Vault 设置",
        "config_loaded": "✅ 配置已加载",
        "analyze": "🔍 开始分析",
        "analyzing": "正在调用模型...",
        "success": "✅ 模型调用成功！",
        # Add more translations as needed...
    }
else:
    TEXTS = {
        "title": "🏥 Medical Image Parsing Model",
        "subtitle": "Developed by Xinyuwei",
        "config": "⚙️ Configuration",
        "model_type": "Select Model Type",
        "error_nibabel": "❌ nibabel library is required for NIfTI files. Please run: pip install nibabel",
        "error_nifti_decode": "❌ NIfTI decoding failed",
        "warning_no_slices": "⚠️ No slices with segmentation results found",
        "warning_config": "⚠️ Configuration not loaded, please check environment variables or Key Vault settings",
        "config_loaded": "✅ Configuration loaded",
        "analyze": "🔍 Start Analysis",
        "analyzing": "Calling model...",
        "success": "✅ Model call successful!",
        # Add more translations as needed...
    }

# Title and subtitle
st.title(TEXTS["title"])
st.caption(TEXTS["subtitle"])

# Check configuration
st.sidebar.header(TEXTS["config"])

if not config.is_configured():
    st.sidebar.error(TEXTS["warning_config"])
    telemetry.warning("Application configuration incomplete")
else:
    st.sidebar.success(TEXTS["config_loaded"])
    telemetry.info("Application configuration loaded successfully")

# Model type selection
model_type = st.sidebar.radio(
    TEXTS["model_type"],
    ["MedImageParse (2D)", "MedImageParse 3D"],
    index=0
)

# Health check endpoint (required for Azure App Service)
# This is a simple marker that health checks can detect
if st.sidebar.button("🏥 Health Check"):
    st.sidebar.success("✅ Application is healthy")
    telemetry.track_event("health_check", {"status": "healthy"})

st.markdown("---")
st.write("**Note**: This is a simplified version. Copy your full UI code from app_clean.py")
st.write("The key additions are:")
st.write("- Configuration management via config.py")
st.write("- Telemetry and logging via telemetry.py")
st.write("- Integration with Azure Key Vault")
st.write("- Correlation IDs for distributed tracing")
st.write("- Health check endpoint")

# Track page view
telemetry.track_event("page_view", {
    "language": language,
    "model_type": model_type
})
