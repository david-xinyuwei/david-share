import streamlit as st
import urllib.request
import json
import base64
import os
from PIL import Image
import io
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

# 设置页面配置
st.set_page_config(page_title="MedImageParse Model Caller", layout="wide")

st.title("🏥 医学图像解析模型调用")

# 侧边栏：配置端点和密钥
st.sidebar.header("⚙️ 配置")

# 预定义的模型配置
MODEL_CONFIGS = {
    "MedImageParse (2D)": {
        "url": os.getenv("AZURE_OPENAI_ENDPOINT_2D", ""),
        "key": os.getenv("AZURE_OPENAI_KEY_2D", "")
    },
    "MedImageParse 3D": {
        "url": os.getenv("AZURE_OPENAI_ENDPOINT_3D", ""),
        "key": os.getenv("AZURE_OPENAI_KEY_3D", "")
    }
}

# 选择模型类型
model_type = st.sidebar.radio(
    "选择模型类型",
    ["MedImageParse (2D)", "MedImageParse 3D"],
    help="根据您部署的模型选择对应类型"
)

# 根据选择的模型类型获取默认配置
default_url = MODEL_CONFIGS[model_type]["url"]
default_key = MODEL_CONFIGS[model_type]["key"]

st.sidebar.markdown("---")

# 输入 REST endpoint
endpoint_url = st.sidebar.text_input(
    "REST Endpoint URL",
    value=default_url,
    help="输入 Azure ML 端点 URL",
    key=f"endpoint_{model_type}"  # 使用不同的key避免缓存问题
)

# 输入 API Key
api_key = st.sidebar.text_input(
    "Primary Key",
    value=default_key,
    type="password",
    help="输入 API 密钥",
    key=f"apikey_{model_type}"  # 使用不同的key避免缓存问题
)

# 保存配置按钮
if st.sidebar.button("💾 保存配置"):
    if endpoint_url and api_key:
        st.session_state['endpoint_url'] = endpoint_url
        st.session_state['api_key'] = api_key
        st.session_state['model_type'] = model_type
        st.sidebar.success("✅ 配置已保存！")
    else:
        st.sidebar.error("❌ 请填写完整的配置信息！")

# 显示当前配置状态
if 'endpoint_url' in st.session_state and 'api_key' in st.session_state:
    st.sidebar.info(f"✅ 配置已保存\n\n当前模型: **{st.session_state.get('model_type', 'MedImageParse (2D)')}**")
else:
    st.sidebar.warning("⚠️ 请保存配置后再上传图片")

# 侧边栏说明
st.sidebar.markdown("---")
st.sidebar.markdown("""
### 📖 模型说明
**MedImageParse (2D)**: 
- 用于2D医学图像分割
- 支持病理、X光等图像
- 可分割多个对象（用 & 分隔）

**MedImageParse 3D**:
- 用于3D医学图像分割  
- 支持CT、MRI等3D体数据
- 通常用于分割单个器官

**两种模型都需要图片 + 文本提示**
""")

st.markdown("---")

# 主界面：上传图片
st.header("📤 上传图片")

# 根据模型类型显示不同的提示
if 'model_type' in st.session_state:
    if "3D" in st.session_state['model_type']:
        st.warning("⚠️ **注意**: MedImageParse 3D 官方要求 **NIfTI 格式** (.nii 或 .nii.gz)，不支持普通图片格式")
        uploaded_file = st.file_uploader(
            "选择要分析的3D医学影像文件",
            type=['nii', 'gz', 'png', 'jpg', 'jpeg'],
            help="推荐: NIfTI格式 (.nii, .nii.gz)。PNG/JPG仅用于测试，可能无法正常工作"
        )
    else:
        uploaded_file = st.file_uploader(
            "选择要分析的2D医学图片",
            type=['png', 'jpg', 'jpeg', 'bmp', 'tiff'],
            help="支持PNG, JPG等常见图像格式"
        )
else:
    uploaded_file = st.file_uploader(
        "选择要分析的图片",
        type=['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'nii', 'gz'],
        help="支持常见图像格式和NIfTI格式"
    )

if uploaded_file is not None:
    # 显示上传的图片
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📷 上传的图片")
        try:
            image = Image.open(uploaded_file)
            st.image(image, use_container_width=True)
            st.info(f"原始尺寸: {image.size[0]} x {image.size[1]}")
            uploaded_file.seek(0)
        except:
            st.info(f"文件名: {uploaded_file.name}")
            st.info(f"文件大小: {uploaded_file.size / 1024:.2f} KB")
    
    with col2:
        st.subheader("🚀 调用模型")
        
        if 'endpoint_url' not in st.session_state or 'api_key' not in st.session_state:
            st.warning("⚠️ 请先在左侧保存配置信息！")
        else:
            current_model = st.session_state.get('model_type', 'MedImageParse (2D)')
            st.info(f"🎯 当前模型: **{current_model}**")
            
            # 文本提示输入（两种模型都需要）
            st.write("**文本提示 (Text Prompt):**")
            if "3D" in current_model:
                st.info("💡 输入要分割的器官或组织名称（3D模型通常用于单个器官）")
                
                # 3D模型的快捷选项
                preset_3d = st.selectbox(
                    "快捷提示词（可选）",
                    ["自定义", "liver", "kidney", "pancreas", "spleen", "lung", "heart"],
                    index=0
                )
                
                if preset_3d == "自定义":
                    text_prompt = st.text_input(
                        "请输入要分割的对象",
                        value="pancreas",
                        help="例如: liver, kidney, pancreas, spleen"
                    )
                else:
                    text_prompt = preset_3d
                    st.success(f"已选择: {text_prompt}")
            else:
                st.info("💡 输入您想要分割的对象，多个对象用 & 分隔")
                
                # 2D模型的快捷选项
                preset_2d = st.selectbox(
                    "快捷提示词（可选）",
                    [
                        "自定义",
                        "--- 异常检测 ---",
                        "tumor",
                        "nodule",
                        "mass",
                        "lesion",
                        "tumor & nodule",
                        "mass & lesion",
                        "--- 肺部 ---",
                        "pulmonary nodule",
                        "lung mass & consolidation",
                        "--- 病理 ---",
                        "neoplastic cells & inflammatory cells",
                        "tumor tissue & necrosis",
                        "--- 其他 ---",
                        "cyst",
                        "calcification",
                        "abnormal tissue"
                    ],
                    index=0
                )
                
                if preset_2d == "自定义" or preset_2d.startswith("---"):
                    text_prompt = st.text_input(
                        "请输入要分割的对象",
                        value="tumor & nodule",
                        help="例如: tumor, nodule, mass, lesion 或组合使用"
                    )
                else:
                    text_prompt = preset_2d
                    st.success(f"已选择: {text_prompt}")
            
            # 图片预处理
            st.write("**图片预处理选项:**")
            
            col_pre1, col_pre2 = st.columns(2)
            
            with col_pre1:
                resize_to_1024 = st.checkbox(
                    "调整为 1024x1024", 
                    value=True,
                    help="MedImageParse 模型标准尺寸"
                )
            
            with col_pre2:
                image_quality = st.slider(
                    "图片质量 (降低以减小文件)",
                    min_value=50,
                    max_value=100,
                    value=95,
                    step=5,
                    help="降低质量可以减小数据大小，避免连接超时"
                )
            
            if image_quality < 85:
                st.warning(f"⚠️ 当前质量设置为 {image_quality}%，这将减小文件大小但可能影响分割精度")
            
            # 调用模型按钮
            if st.button("🔍 开始分析", type="primary"):
                with st.spinner("正在调用模型..."):
                    try:
                        uploaded_file.seek(0)
                        image = Image.open(uploaded_file)
                        
                        # 调整图片大小为 1024x1024
                        if resize_to_1024:
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
                            
                            st.success(f"✅ 图片已调整为 {image.size[0]}x{image.size[1]}")
                        
                        # 转换为JPEG并编码（使用质量参数来控制大小）
                        buffer = io.BytesIO()
                        if image_quality < 100:
                            # 使用JPEG格式和质量压缩
                            image.save(buffer, format='JPEG', quality=image_quality, optimize=True)
                        else:
                            # 使用PNG格式（无损）
                            image.save(buffer, format='PNG', optimize=True)
                        image_bytes = buffer.getvalue()
                        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                        
                        st.info(f"📦 数据大小: {len(image_bytes) / 1024:.2f} KB, Base64长度: {len(image_base64)}")
                        
                        # 添加调试选项
                        with st.expander("🔧 高级选项（调试用）"):
                            use_raw_base64 = st.checkbox("使用原始base64（不添加换行符）", value=True)
                            test_connection = st.checkbox("测试连接（发送最小数据）", value=False)
                        
                        # 两种模型使用相同的数据格式
                        # 根据官方文档，MedImageParse 和 MedImageParse 3D 都需要 image + text
                        if test_connection:
                            # 发送最小测试数据
                            data = {
                                "input_data": {
                                    "columns": ["image", "text"],
                                    "index": [0],
                                    "data": [["test", "test"]]
                                }
                            }
                            st.warning("⚠️ 测试模式：发送最小数据以测试端点连接")
                        else:
                            data = {
                                "input_data": {
                                    "columns": ["image", "text"],
                                    "index": [0],
                                    "data": [[image_base64, text_prompt]]
                                }
                            }
                        
                        # 显示请求数据结构
                        with st.expander("📤 查看请求数据结构"):
                            display_data = {
                                "input_data": {
                                    "columns": ["image", "text"],
                                    "index": [0],
                                    "data": [[f"<base64: {len(image_base64)} chars>", text_prompt]]
                                }
                            }
                            st.json(display_data)
                        
                        # 发送请求
                        body = str.encode(json.dumps(data))
                        
                        st.info(f"📤 正在发送 {len(body) / 1024 / 1024:.2f} MB 数据到服务器...")
                        
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
                        
                        # 设置超时时间为5分钟
                        response = urllib.request.urlopen(req, timeout=300)
                        result = response.read()
                        result_json = json.loads(result.decode('utf-8'))
                        
                        st.success("✅ 模型调用成功！")
                        
                        # 显示结果
                        st.subheader("📊 分割结果")
                        
                        try:
                            # 解析返回数据
                            if isinstance(result_json, list) and len(result_json) > 0:
                                result_data = result_json[0]
                                
                                # 检查是否包含 image_features
                                if isinstance(result_data, dict) and 'image_features' in result_data:
                                    image_features = result_data['image_features']
                                    
                                    # 解码 base64 图像
                                    if isinstance(image_features, str):
                                        decoded_bytes = base64.b64decode(image_features)
                                        mask_image = Image.open(io.BytesIO(decoded_bytes))
                                        
                                        st.success(f"✅ 成功解码分割掩码！尺寸: {mask_image.size}")
                                        
                                        # 显示图像
                                        col1, col2, col3 = st.columns(3)
                                        
                                        with col1:
                                            st.write("**原始图片**")
                                            st.image(image, width=300)
                                        
                                        with col2:
                                            st.write("**分割掩码**")
                                            st.image(mask_image, width=300)
                                        
                                        with col3:
                                            st.write("**叠加效果**")
                                            # 简单叠加
                                            combined = Image.blend(image.resize(mask_image.size).convert('RGB'), 
                                                                 mask_image.convert('RGB'), 0.5)
                                            st.image(combined, width=300)
                                        
                                        # 下载按钮
                                        st.markdown("---")
                                        col_dl1, col_dl2 = st.columns(2)
                                        
                                        with col_dl1:
                                            buf = io.BytesIO()
                                            mask_image.save(buf, format='PNG')
                                            st.download_button(
                                                "� 下载分割掩码",
                                                data=buf.getvalue(),
                                                file_name="mask.png",
                                                mime="image/png"
                                            )
                                        
                                        with col_dl2:
                                            st.download_button(
                                                "📥 下载原始JSON",
                                                data=json.dumps(result_json, indent=2),
                                                file_name="result.json",
                                                mime="application/json"
                                            )
                                    else:
                                        st.warning("image_features 不是字符串格式")
                                        st.json(result_json)
                                else:
                                    st.warning("未找到 image_features 字段")
                                    st.json(result_json)
                            else:
                                st.warning("返回数据格式异常")
                                st.json(result_json)
                        
                        except Exception as e:
                            st.error(f"❌ 处理结果时出错: {str(e)}")
                            st.json(result_json)
                                        
                                        with col_vis2:
                                            st.write("**🎭 分割掩码**")
                                            
                                            try:
                                                # 如果是RGB图像，转换为灰度
                                                if len(mask_array.shape) == 3:
                                                    # 如果是彩色图像，转换为灰度
                                                    if mask_array.shape[2] == 3:
                                                        mask_array_gray = np.mean(mask_array.astype(np.float32), axis=2)
                                                    elif mask_array.shape[2] == 4:
                                                        mask_array_gray = np.mean(mask_array[:,:,:3].astype(np.float32), axis=2)
                                                    else:
                                                        mask_array_gray = mask_array.astype(np.float32)
                                                        
                                                    st.info("ℹ️ 已将彩色掩码转换为灰度")
                                                else:
                                                    mask_array_gray = mask_array.astype(np.float32)
                                                
                                                # 创建彩色掩码
                                                fig1, ax1 = plt.subplots(figsize=(8, 8))
                                                
                                                # 使用彩色映射显示不同的分割区域
                                                unique_values = np.unique(mask_array_gray)
                                                st.caption(f"检测到 {len(unique_values)} 个不同区域")
                                                
                                                # 使用tab20彩色方案
                                                im = ax1.imshow(mask_array_gray, cmap='tab20', interpolation='nearest')
                                                ax1.axis('off')
                                                plt.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
                                                st.pyplot(fig1)
                                                plt.close()
                                            
                                            except Exception as vis_error:
                                                st.error(f"显示掩码失败: {str(vis_error)}")
                                                # 尝试直接显示为图像
                                                try:
                                                    st.image(mask_array, caption="分割掩码（直接显示）", use_container_width=True)
                                                except:
                                                    st.write("无法显示掩码图像")
                                        
                                        with col_vis3:
                                            st.write("**🔍 叠加显示**")
                                            # 将掩码叠加在原图上
                                            fig2, ax2 = plt.subplots(figsize=(8, 8))
                                            
                                            # 显示原图
                                            ax2.imshow(image)
                                            
                                            # 使用灰度掩码创建叠加
                                            if len(mask_array.shape) == 2 or (len(mask_array.shape) == 3 and mask_array.shape[2] == 1):
                                                # 创建半透明的掩码叠加
                                                mask_to_use = mask_array_gray if 'mask_array_gray' in locals() else mask_array
                                                mask_colored = np.zeros((*mask_to_use.shape, 4))
                                                
                                                # 为每个区域分配颜色
                                                colors = plt.cm.tab20(np.linspace(0, 1, len(unique_values)))
                                                for idx, val in enumerate(unique_values):
                                                    if val > 0:  # 跳过背景
                                                        mask_colored[mask_to_use == val] = colors[idx]
                                                
                                                # 设置透明度
                                                mask_colored[:, :, 3] = 0.5 * (mask_to_use > 0)
                                            else:
                                                # 如果是彩色掩码，直接使用
                                                mask_colored = mask_array.copy()
                                                if mask_colored.shape[2] == 3:
                                                    # 添加透明度通道
                                                    alpha = 0.5 * np.ones((*mask_colored.shape[:2], 1))
                                                    mask_colored = np.concatenate([mask_colored / 255.0, alpha], axis=2)
                                            
                                            ax2.imshow(mask_colored)
                                            ax2.axis('off')
                                            st.pyplot(fig2)
                                            plt.close()
                                        
                                        # 显示统计信息
                                        st.subheader("📈 分割统计")
                                        
                                        col_stat1, col_stat2 = st.columns(2)
                                        
                                        with col_stat1:
                                            st.write("**区域统计:**")
                                            mask_for_stats = mask_array_gray if 'mask_array_gray' in locals() else mask_array
                                            for idx, val in enumerate(unique_values):
                                                pixel_count = np.sum(mask_for_stats == val)
                                                percentage = (pixel_count / mask_for_stats.size) * 100
                                                if val == 0 or val < 10:
                                                    st.write(f"- 背景: {pixel_count} 像素 ({percentage:.2f}%)")
                                                else:
                                                    st.write(f"- 区域 {int(val)}: {pixel_count} 像素 ({percentage:.2f}%)")
                                        
                                        with col_stat2:
                                            st.write("**提示词分析:**")
                                            st.write(f"输入提示: `{text_prompt}`")
                                            
                                            if '&' in text_prompt:
                                                objects = [obj.strip() for obj in text_prompt.split('&')]
                                                st.write(f"检测对象数量: {len(objects)}")
                                                for obj in objects:
                                                    st.write(f"  - {obj}")
                                            else:
                                                st.write(f"检测对象: {text_prompt}")
                                        
                                        # 添加下载按钮
                                        st.markdown("---")
                                        st.subheader("💾 导出结果")
                                        
                                        col_dl1, col_dl2 = st.columns(2)
                                        
                                        with col_dl1:
                                            # 保存掩码为图片
                                            try:
                                                if len(mask_array.shape) == 3:
                                                    # 如果是RGB，直接使用
                                                    if mask_array.dtype == np.float64 or mask_array.dtype == np.float32:
                                                        mask_image = Image.fromarray((mask_array * 255).astype(np.uint8))
                                                    else:
                                                        mask_image = Image.fromarray(mask_array.astype(np.uint8))
                                                else:
                                                    # 灰度图像
                                                    mask_for_save = mask_array_gray if 'mask_array_gray' in locals() else mask_array
                                                    max_val = float(np.max(mask_for_save))
                                                    if max_val > 0:
                                                        mask_image = Image.fromarray((mask_for_save * 255 / max_val).astype(np.uint8))
                                                    else:
                                                        mask_image = Image.fromarray(mask_for_save.astype(np.uint8))
                                                
                                                buf = io.BytesIO()
                                                mask_image.save(buf, format='PNG')
                                                st.download_button(
                                                    label="📥 下载分割掩码 (PNG)",
                                                    data=buf.getvalue(),
                                                    file_name="segmentation_mask.png",
                                                    mime="image/png"
                                                )
                                            except Exception as save_error:
                                                st.error(f"保存失败: {str(save_error)}")
                                        
                                        with col_dl2:
                                            # 保存原始数据为JSON
                                            json_str = json.dumps(result_json, indent=2)
                                            st.download_button(
                                                label="📥 下载原始数据 (JSON)",
                                                data=json_str,
                                                file_name="segmentation_data.json",
                                                mime="application/json"
                                            )
                                    else:
                                        st.error(f"❌ image_features 不是列表格式: {type(image_features)}")
                                
                                # 将掩码数据转换为numpy数组
                                elif isinstance(mask_data, list):
                                    # 如果是二维列表
                                    mask_array = np.array(mask_data)
                                    
                                    st.success(f"✅ 成功解析掩码数据！")
                                    st.info(f"📏 分割掩码尺寸: {mask_array.shape} | 数据类型: {mask_array.dtype} | 值范围: [{mask_array.min():.2f}, {mask_array.max():.2f}]")
                                    
                                    # 如果掩码是1维的，尝试reshape为2D
                                    if len(mask_array.shape) == 1:
                                        # 假设是1024x1024
                                        target_size = int(np.sqrt(mask_array.shape[0]))
                                        if target_size * target_size == mask_array.shape[0]:
                                            mask_array = mask_array.reshape(target_size, target_size)
                                            st.info(f"♻️ 已将1维数组重塑为: {mask_array.shape}")
                                        else:
                                            st.error(f"❌ 无法将长度为 {mask_array.shape[0]} 的数组重塑为正方形")
                                    
                                    # 创建三列布局
                                    col_vis1, col_vis2, col_vis3 = st.columns(3)
                                    
                                    with col_vis1:
                                        st.write("**🖼️ 原始图片**")
                                        st.image(image, use_container_width=True)
                                    
                                    with col_vis2:
                                        st.write("**🎭 分割掩码**")
                                        # 创建彩色掩码
                                        fig1, ax1 = plt.subplots(figsize=(8, 8))
                                        
                                        # 使用彩色映射显示不同的分割区域
                                        unique_values = np.unique(mask_array)
                                        st.caption(f"检测到 {len(unique_values)} 个不同区域")
                                        
                                        # 使用tab20彩色方案
                                        im = ax1.imshow(mask_array, cmap='tab20', interpolation='nearest')
                                        ax1.axis('off')
                                        plt.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
                                        st.pyplot(fig1)
                                        plt.close()
                                    
                                    with col_vis3:
                                        st.write("**🔍 叠加显示**")
                                        # 将掩码叠加在原图上
                                        fig2, ax2 = plt.subplots(figsize=(8, 8))
                                        
                                        # 显示原图
                                        ax2.imshow(image)
                                        
                                        # 创建半透明的掩码叠加
                                        mask_colored = np.zeros((*mask_array.shape, 4))
                                        
                                        # 为每个区域分配颜色
                                        colors = plt.cm.tab20(np.linspace(0, 1, len(unique_values)))
                                        for idx, val in enumerate(unique_values):
                                            if val > 0:  # 跳过背景
                                                mask_colored[mask_array == val] = colors[idx]
                                        
                                        # 设置透明度
                                        mask_colored[:, :, 3] = 0.5 * (mask_array > 0)
                                        
                                        ax2.imshow(mask_colored)
                                        ax2.axis('off')
                                        st.pyplot(fig2)
                                        plt.close()
                                    
                                    # 显示统计信息
                                    st.subheader("📈 分割统计")
                                    
                                    col_stat1, col_stat2 = st.columns(2)
                                    
                                    with col_stat1:
                                        st.write("**区域统计:**")
                                        for idx, val in enumerate(unique_values):
                                            pixel_count = np.sum(mask_array == val)
                                            percentage = (pixel_count / mask_array.size) * 100
                                            if val == 0:
                                                st.write(f"- 背景: {pixel_count} 像素 ({percentage:.2f}%)")
                                            else:
                                                st.write(f"- 区域 {int(val)}: {pixel_count} 像素 ({percentage:.2f}%)")
                                    
                                    with col_stat2:
                                        st.write("**提示词分析:**")
                                        st.write(f"输入提示: `{text_prompt}`")
                                        
                                        if '&' in text_prompt:
                                            objects = [obj.strip() for obj in text_prompt.split('&')]
                                            st.write(f"检测对象数量: {len(objects)}")
                                            for obj in objects:
                                                st.write(f"  - {obj}")
                                        else:
                                            st.write(f"检测对象: {text_prompt}")
                                    
                                    # 添加下载按钮
                                    st.markdown("---")
                                    st.subheader("� 导出结果")
                                    
                                    col_dl1, col_dl2 = st.columns(2)
                                    
                                    with col_dl1:
                                        # 保存掩码为图片
                                        mask_image = Image.fromarray((mask_array * 255 / mask_array.max()).astype(np.uint8))
                                        buf = io.BytesIO()
                                        mask_image.save(buf, format='PNG')
                                        st.download_button(
                                            label="📥 下载分割掩码 (PNG)",
                                            data=buf.getvalue(),
                                            file_name="segmentation_mask.png",
                                            mime="image/png"
                                        )
                                    
                                    with col_dl2:
                                        # 保存原始数据为JSON
                                        json_str = json.dumps(result_json, indent=2)
                                        st.download_button(
                                            label="📥 下载原始数据 (JSON)",
                                            data=json_str,
                                            file_name="segmentation_data.json",
                                            mime="application/json"
                                        )
                                    
                                else:
                                    st.warning("⚠️ 掩码数据不是列表格式")
                                    st.write(f"实际类型: {type(mask_data)}")
                                    
                                    # 尝试其他可能的格式
                                    if isinstance(mask_data, dict):
                                        st.write("掩码数据是字典，可用的键:")
                                        st.write(list(mask_data.keys()))
                            else:
                                st.warning("⚠️ 返回数据不是列表或为空")
                                st.write(f"实际类型: {type(result_json)}")
                                
                                # 如果是字典，显示可用的键
                                if isinstance(result_json, dict):
                                    st.write("返回的字典键:")
                                    st.write(list(result_json.keys()))
                        
                        except Exception as viz_error:
                            st.error(f"❌ 可视化失败: {str(viz_error)}")
                            st.write(f"错误详情: {type(viz_error).__name__}")
                            import traceback
                            st.code(traceback.format_exc())
                        
                        # 可选：显示原始JSON
                        with st.expander("🔍 查看原始JSON数据"):
                            st.json(result_json)
                        
                    except urllib.error.HTTPError as error:
                        st.error(f"❌ HTTP请求失败，状态码: {error.code}")
                        error_details = error.read().decode("utf8", 'ignore')
                        
                        with st.expander("🔍 查看详细错误信息", expanded=True):
                            st.code(error_details, language="json")
                        
                        if error.code == 424:
                            st.error("💡 **错误 424 - 模型处理失败**")
                        
                        col_err1, col_err2 = st.columns(2)
                        
                        with col_err1:
                            st.markdown("""
                            **常见原因:**
                            1. 端点URL不匹配部署的模型
                            2. 图片不是医学影像格式
                            3. 3D模型需要NIfTI格式
                            4. 文本提示不在模型词汇表中
                            5. 图片太大或格式不支持
                            """)
                        
                        with col_err2:
                            st.markdown("""
                            **建议尝试:**
                            - ✅ 确认这个endpoint部署的是哪个模型
                            - ✅ 如果是3D模型，需要NIfTI (.nii/.nii.gz)
                            - ✅ 如果是2D模型，使用PNG/JPG
                            - ✅ 尝试使用"测试连接"选项
                            - ✅ 检查API Key是否有权限
                            """)
                    
                    except urllib.error.URLError as e:
                        st.error(f"❌ 网络连接错误: {str(e.reason)}")
                        
                        st.error("🔌 **连接问题诊断:**")
                        
                        if "10054" in str(e.reason) or "强迫关闭" in str(e.reason):
                            st.markdown("""
                            **远程主机关闭连接 (Error 10054)** - 可能原因：
                            
                            1. **请求数据过大** 
                               - 当前数据: {:.2f} MB
                               - 建议: 尝试更小的图片或降低分辨率
                            
                            2. **服务器超时**
                               - Azure ML 端点可能设置了请求大小限制
                               - 建议: 联系管理员检查端点配置
                            
                            3. **端点不可用**
                               - 服务可能正在重启或维护
                               - 建议: 稍后重试
                            
                            4. **防火墙/网络问题**
                               - 网络可能阻止了大数据传输
                               - 建议: 检查网络设置
                            
                            **💡 立即尝试的解决方案:**
                            """.format(len(body) / 1024 / 1024))
                            
                            col_sol1, col_sol2 = st.columns(2)
                            
                            with col_sol1:
                                st.info("""
                                **方案1: 减小图片尺寸**
                                1. 取消 "自动调整为1024x1024"
                                2. 手动将图片调整为512x512或更小
                                3. 重新上传
                                """)
                            
                            with col_sol2:
                                st.info("""
                                **方案2: 使用测试连接**
                                1. 展开 "高级选项"
                                2. 勾选 "测试连接"
                                3. 验证端点是否可访问
                                """)
                        else:
                            st.write(f"错误详情: {e.reason}")
                        
                        # 提供在线端点测试
                        with st.expander("🔧 端点连接测试"):
                            if st.button("📡 测试端点连接"):
                                try:
                                    test_data = {"input_data": {"columns": ["image", "text"], "index": [0], "data": [["test", "test"]]}}
                                    test_body = str.encode(json.dumps(test_data))
                                    test_req = urllib.request.Request(
                                        st.session_state['endpoint_url'],
                                        test_body,
                                        headers
                                    )
                                    test_response = urllib.request.urlopen(test_req, timeout=30)
                                    st.success("✅ 端点连接正常！问题可能是数据太大。")
                                except Exception as test_e:
                                    st.error(f"❌ 端点连接失败: {str(test_e)}")
                        
                    except Exception as e:
                        st.error(f"❌ 发生未知错误: {str(e)}")
                        st.write(f"错误类型: {type(e).__name__}")
                        
                        import traceback
                        with st.expander("🐛 查看完整错误堆栈"):
                            st.code(traceback.format_exc())

# 底部说明
st.markdown("---")
st.markdown("""
### 📝 使用说明

#### 步骤：
1. **选择模型类型**: 在左侧选择 MedImageParse (2D) 或 MedImageParse 3D
2. **配置**: 输入 REST Endpoint URL 和 Primary Key
3. **保存**: 点击 "💾 保存配置" 按钮
4. **上传**: 选择要分析的医学图像文件
5. **设置提示**: (仅2D模型) 输入要分割的对象名称
6. **分析**: 点击 "🔍 开始分析" 按钮

#### 模型输入格式：
- **两种模型都需要**: 图片 (1024x1024) + 文本提示

#### 文本提示示例：
**2D 模型** (可以多个对象，用 & 分隔):
- 病理图像: `neoplastic cells & inflammatory cells`
- X光图像: `tumor core & enhancing tumor & non-enhancing tumor`

**3D 模型** (通常单个器官):
- CT/MRI扫描: `liver`, `kidney`, `pancreas`, `spleen`
- 肿瘤分割: `tumor`, `lesion`
""")
