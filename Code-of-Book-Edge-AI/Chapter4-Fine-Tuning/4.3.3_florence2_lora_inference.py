# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第4章 §4.3.3 微调Florence-2 —— 3. 验证模型的泛化能力

# 补充：导入语句
import json
import os
import torch
import supervision as sv
from IPython.display import display
from peft import PeftModel
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Florence-2 基础模型
BASE_MODEL_NAME = "microsoft/Florence-2-base-ft"
REVISION = "refs/pr/6"
# LoRA 微调后权重的保存路径
ADAPTER_PATH = "/content/florence2-lora"  # 示例: "/content/florence2-lora"
# 测试图像的路径
IMAGE_PATH = "/var/3.png"     # 请替换为自身真实图像文件路径
# --------------------------#
# 1) 加载基础模型 + Processor
# --------------------------#
print("Loading base model...")
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL_NAME,
    trust_remote_code=True,
    revision=REVISION
).to(DEVICE)
print("Loading processor...")
processor = AutoProcessor.from_pretrained(
    BASE_MODEL_NAME,
    trust_remote_code=True,
    revision=REVISION
)
# --------------------------#
# 2) 加载 LoRA Adapter
# --------------------------#
print(f"Loading LoRA adapter from: {ADAPTER_PATH}")
peft_model = PeftModel.from_pretrained(
    base_model,
    ADAPTER_PATH
).to(DEVICE)
# --------------------------#
# 3) 推理示例
# --------------------------#
def run_inference(image_path: str):
    """
    读取图像做推理，并将推理后的检测结果保存为 result.jpg，同时在 Jupyter 内联显示。
    """
    task = "<OD>"         # Florence-2 对目标检测的触发关键词
    text = "<OD>"         # 推理文本提示
    if not os.path.exists(image_path):
        print(f"Error: 图像路径不存在 -> {image_path}")
        return
    print(f"\n[推理] 读取图像: {image_path}")
    image = Image.open(image_path).convert("RGB")
    # 将图像和文本打包成模型可接受的输入
    inputs = processor(
        text=text,
        images=image,
        return_tensors="pt"
    ).to(DEVICE)
    # 调用模型进行推理
    print("[推理] 正在生成推理结果...")
    with torch.no_grad():
        generated_ids = peft_model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            num_beams=3
        )
    # 解码模型输出
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    # 后处理: 把模型的输出(文本)转换为检测框、标签等
    response = processor.post_process_generation(
        generated_text,
        task=task,
        image_size=image.size
    )
    # 可视化检测结果
    print("[推理] 解析检测框并可视化...")
    detections = sv.Detections.from_vlm(
        vlm="florence_2",
        result=response,
        resolution_wh=image.size
    )
    # 标注框和标签
    box_annotator = sv.BoxAnnotator(color_lookup=sv.ColorLookup.INDEX)
    label_annotator = sv.LabelAnnotator(color_lookup=sv.ColorLookup.INDEX)
    image_annotated = box_annotator.annotate(
        scene=image.copy(),
        detections=detections
    )
    image_annotated = label_annotator.annotate(
        scene=image_annotated,
        detections=detections
    )
    # 保存结果到本地文件
    output_path = "result.jpg"
    image_annotated.save(output_path)
    print(f"[完成] 已将检测结果保存至: {output_path}")
    # 打印原始 JSON 结果 (可自行再做额外处理)
    print("\n[推理结果 JSON] =")
    print(json.dumps(response, indent=2, ensure_ascii=False))
    # 在 Jupyter Notebook 中内联显示处理后的图
    display(image_annotated)
if __name__ == "__main__":
    # --------------------------#
    # 运行推理并打印结果
    # --------------------------#
    run_inference(IMAGE_PATH)
