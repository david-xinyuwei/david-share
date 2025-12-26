Train Code

```
#!/usr/bin/env python  
# -*- coding: utf-8 -*-  
import os  
import csv  
import ast  
import torch  
import PIL  
from torch.utils.data import Dataset, DataLoader  
from transformers import AutoModelForCausalLM, AutoProcessor, AdamW, get_scheduler  
from tqdm import tqdm  
  
# 禁用 tokenizers 并行警告  
os.environ["TOKENIZERS_PARALLELISM"] = "false"  
  
# ---------------------------------------------------------------------------  
# 数据集路径配置  
# ---------------------------------------------------------------------------  
DATA_ROOT = "/root/BlueJayAnnotation"  # 数据集根目录  
TRAIN_SUBDIR = "train"  
VALID_SUBDIR = "valid"  
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  
  
# ---------------------------------------------------------------------------  
# 函数：将标注转换成 Florence 格式文本  
# ---------------------------------------------------------------------------  
def annotation_to_od_style(ann_str):  
    """将标注转换为 Florence 格式文本"""  
    try:  
        data = ast.literal_eval(ann_str)  # 解析字符串  
        bboxes = data.get("bboxes", [])  
        labels = data.get("labels", [])  
        od_texts = []  
        for i, bbox in enumerate(bboxes):  
            label = labels[i] if i < len(labels) else "object"  
            x1, y1, w, h = bbox  
            x2, y2 = x1 + w, y1 + h  
            od_texts.append(f"{label} <loc {int(x1)} {int(y1)} {int(x2)} {int(y2)}>")  
        final_text = " ".join(od_texts)  
        return final_text if final_text else "no_bbox"  
    except:  
        return "no_bbox"  
  
# ---------------------------------------------------------------------------  
# 自定义数据集类  
# ---------------------------------------------------------------------------  
class LocalBlueJayDataset(Dataset):  
    def __init__(self, root_dir, subset="train"):  
        super().__init__()  
        self.root_dir = root_dir  
        self.subset = subset  
        self.entries = []  
        csv_path = os.path.join(root_dir, subset, "metadata.csv")  
        with open(csv_path, "r", encoding="utf-8") as f:  
            reader = csv.reader(f)  
            header = next(reader, None)  
            if not header or len(header) < 2:  
                raise ValueError(f"CSV 文件 {csv_path} 格式不正确")  
            for row in reader:  
                if len(row) < 2:  
                    continue  
                file_name = row[0].strip()  
                ann_str = row[1].strip()  
                od_str = annotation_to_od_style(ann_str)  
                self.entries.append((file_name, od_str))  
  
    def __len__(self):  
        return len(self.entries)  
  
    def __getitem__(self, idx):  
        file_name, od_text = self.entries[idx]  
        img_path = os.path.join(self.root_dir, self.subset, file_name)  
        image = PIL.Image.open(img_path)  
        if image.mode != "RGB":  
            image = image.convert("RGB")  
        # 返回: (答案文本, 图像)，稍后会将 prompt 写死为 <BIRD_OD>。  
        return od_text, image  
  
# ---------------------------------------------------------------------------  
# 加载基础模型和 Processor  
# ---------------------------------------------------------------------------  
model_name = "microsoft/Florence-2-large"  
model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True).to(device)  
processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)  
  
# 冻结视觉塔参数，减少训练难度  
if hasattr(model, "vision_tower"):  
    for param in model.vision_tower.parameters():  
        param.requires_grad = False  
  
# ---------------------------------------------------------------------------  
# 构建 DataLoader 并定义 collate_fn  
# ---------------------------------------------------------------------------  
train_dataset = LocalBlueJayDataset(DATA_ROOT, subset=TRAIN_SUBDIR)  
val_dataset = LocalBlueJayDataset(DATA_ROOT, subset=VALID_SUBDIR)  
  
def collate_fn(batch):  
    # batch 内每个元素是 (od_text, image)  
    # 这里把 od_text 当作“答案”，把 <BIRD_OD> 当作“问题”  
    od_texts, images = zip(*batch)  
    questions = ["<BIRD_OD>" for _ in batch]  # 固定提示符  
    answers = list(od_texts)  
    # 利用 processor 处理输入 (问题 + 图像)，跟 DocVQA 一致  
    inputs = processor(text=questions, images=images, return_tensors="pt", padding=True).to(device)  
    return inputs, answers  
  
train_loader = DataLoader(train_dataset, batch_size=1, shuffle=True, collate_fn=collate_fn)  
val_loader = DataLoader(val_dataset, batch_size=1, collate_fn=collate_fn)  
  
# ---------------------------------------------------------------------------  
# 训练函数  
# ---------------------------------------------------------------------------  
def train_model(train_loader, val_loader, model, processor, epochs=5, lr=1e-6):  
    optimizer = AdamW(model.parameters(), lr=lr)  
    num_training_steps = epochs * len(train_loader)  
    lr_scheduler = get_scheduler(name="linear", optimizer=optimizer, num_warmup_steps=0, num_training_steps=num_training_steps)  
  
    for epoch in range(epochs):  
        # =============== train ===============  
        model.train()  
        train_loss_sum = 0  
        for inputs, answers in tqdm(train_loader, desc=f"Training Epoch {epoch+1}/{epochs}"):  
            input_ids = inputs["input_ids"]  
            pixel_values = inputs["pixel_values"]  
            # 把答案转成 labels  
            labels = processor.tokenizer(  
                text=answers,  
                return_tensors="pt",  
                padding=True,  
                return_token_type_ids=False  
            ).input_ids.to(device)  
            outputs = model(input_ids=input_ids, pixel_values=pixel_values, labels=labels)  
            loss = outputs.loss  
            loss.backward()  
            optimizer.step()  
            lr_scheduler.step()  
            optimizer.zero_grad()  
            train_loss_sum += loss.item()  
        avg_train_loss = train_loss_sum / len(train_loader)  
        print(f"[Epoch {epoch+1}] Train Loss: {avg_train_loss:.4f}")  
  
        # =============== eval ===============  
        model.eval()  
        val_loss_sum = 0  
        with torch.no_grad():  
            for inputs, answers in tqdm(val_loader, desc=f"Val Epoch {epoch+1}/{epochs}"):  
                input_ids = inputs["input_ids"]  
                pixel_values = inputs["pixel_values"]  
                labels = processor.tokenizer(  
                    text=answers,  
                    return_tensors="pt",  
                    padding=True,  
                    return_token_type_ids=False  
                ).input_ids.to(device)  
                outputs = model(input_ids=input_ids, pixel_values=pixel_values, labels=labels)  
                val_loss_sum += outputs.loss.item()  
        avg_val_loss = val_loss_sum / len(val_loader)  
        print(f"[Epoch {epoch+1}] Val Loss: {avg_val_loss:.4f}")  
  
        # 保存 checkpoint  
        save_dir = f"./model_checkpoints/epoch_{epoch+1}"  
        os.makedirs(save_dir, exist_ok=True)  
        model.save_pretrained(save_dir)  
        processor.save_pretrained(save_dir)  
        print(f"Checkpoint saved to {save_dir}")  
  
# ---------------------------------------------------------------------------  
# 开始训练  
# ---------------------------------------------------------------------------  
train_model(train_loader, val_loader, model, processor, epochs=7, lr=1e-6)  
  
# ---------------------------------------------------------------------------  
# 推理加载示例  
# ---------------------------------------------------------------------------  
def load_model_and_processor(model_path):  
    import json  
    from transformers import AutoConfig  
    # 修复 config.json (vision_config.model_type=davit)  
    config_path = os.path.join(model_path, "config.json")  
    if not os.path.exists(config_path):  
        raise FileNotFoundError(f"配置文件 {config_path} 不存在，请检查路径！")  
  
    with open(config_path, "r") as f:  
        config_data = json.load(f)  
    if "vision_config" in config_data and config_data["vision_config"].get("model_type") != "davit":  
        config_data["vision_config"]["model_type"] = "davit"  
        with open(config_path, "w") as f:  
            json.dump(config_data, f, indent=4)  
        print(f"修复后的配置文件已保存到 {config_path}")  
    config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)  
    model = AutoModelForCausalLM.from_pretrained(model_path, config=config, trust_remote_code=True).to(device)  
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)  
    return model, processor  
  
# ---------------------------------------------------------------------------  
# 推理调用示例  
# ---------------------------------------------------------------------------  
def run_inference_bird_od(model, processor, image_path, task_prompt="<BIRD_OD> Summary", max_new_tokens=128):  
    image = PIL.Image.open(image_path).convert("RGB")  
    inputs = processor(text=task_prompt, images=image, return_tensors="pt").to(device)  
    with torch.no_grad():  
        generated_ids = model.generate(  
            input_ids=inputs["input_ids"],  
            pixel_values=inputs["pixel_values"],  
            max_new_tokens=max_new_tokens,  
            num_beams=5,  
            do_sample=True,  
            temperature=0.7,  
            top_k=50,  
            top_p=0.9,  
            repetition_penalty=1.2,  
        )  
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]  
    return generated_text  
  
if __name__ == "__main__":  
    SAMPLE_IMAGE = "/root/BlueJayAnnotation/valid/BlueJay_1e8b8b6047d34edf.jpeg"  
    print(f"=== Running inference on: {SAMPLE_IMAGE} ===")  
    output = run_inference_bird_od(model, processor, SAMPLE_IMAGE)  
    print("\n===== Generated Output =====")  
    print(output)  
```

Result

```
Training Epoch 1/7: 100%|██████████| 144/144 [00:40<00:00,  3.54it/s]
[Epoch 1] Train Loss: 3.4285
Val Epoch 1/7: 100%|██████████| 35/35 [00:06<00:00,  5.18it/s]
[Epoch 1] Val Loss: 2.6094
Checkpoint saved to ./model_checkpoints/epoch_1
Training Epoch 2/7: 100%|██████████| 144/144 [00:40<00:00,  3.53it/s]
[Epoch 2] Train Loss: 2.4303
Val Epoch 2/7: 100%|██████████| 35/35 [00:07<00:00,  4.97it/s]
[Epoch 2] Val Loss: 2.4561
Checkpoint saved to ./model_checkpoints/epoch_2
Training Epoch 3/7: 100%|██████████| 144/144 [00:40<00:00,  3.54it/s]
[Epoch 3] Train Loss: 2.3023
Val Epoch 3/7: 100%|██████████| 35/35 [00:06<00:00,  5.02it/s]
[Epoch 3] Val Loss: 2.3886
Checkpoint saved to ./model_checkpoints/epoch_3
Training Epoch 4/7: 100%|██████████| 144/144 [00:40<00:00,  3.59it/s]
[Epoch 4] Train Loss: 2.2235
Val Epoch 4/7: 100%|██████████| 35/35 [00:06<00:00,  5.17it/s]
[Epoch 4] Val Loss: 2.3334
Checkpoint saved to ./model_checkpoints/epoch_4
Training Epoch 5/7: 100%|██████████| 144/144 [00:40<00:00,  3.59it/s]
[Epoch 5] Train Loss: 2.1638
Val Epoch 5/7: 100%|██████████| 35/35 [00:06<00:00,  5.14it/s]
[Epoch 5] Val Loss: 2.3266
Checkpoint saved to ./model_checkpoints/epoch_5
Training Epoch 6/7: 100%|██████████| 144/144 [00:39<00:00,  3.61it/s]
[Epoch 6] Train Loss: 2.1388
Val Epoch 6/7: 100%|██████████| 35/35 [00:07<00:00,  5.00it/s]
[Epoch 6] Val Loss: 2.3135
Checkpoint saved to ./model_checkpoints/epoch_6
Training Epoch 7/7: 100%|██████████| 144/144 [00:40<00:00,  3.60it/s]
[Epoch 7] Train Loss: 2.1209
Val Epoch 7/7: 100%|██████████| 35/35 [00:06<00:00,  5.04it/s]
[Epoch 7] Val Loss: 2.3098
Checkpoint saved to ./model_checkpoints/epoch_7
=== Running inference on: /root/BlueJayAnnotation/valid/BlueJay_1e8b8b6047d34edf.jpeg ===

===== Generated Output =====
</s><s><s><s>Blue Jay <loc 753 557 1237 875></s>
```

Inference code:

```
import os  
import json  
import torch  
import PIL  
from transformers import AutoConfig, AutoModelForCausalLM, AutoProcessor  
  
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  
  
def load_model_and_processor(model_path):  
    """  
    加载模型和 Processor，并修复配置文件中的问题。  
    Args:  
        model_path (str): 模型存储路径。  
    Returns:  
        model: 加载的 PyTorch 模型。  
        processor: 加载的 Processor 对象。  
    """  
    # 修复 config.json (vision_config.model_type=davit)  
    config_path = os.path.join(model_path, "config.json")  
    if not os.path.exists(config_path):  
        raise FileNotFoundError(f"配置文件 {config_path} 不存在，请检查路径！")  
  
    # 修复配置文件中的 vision_config.model_type  
    with open(config_path, "r") as f:  
        config_data = json.load(f)  
    if "vision_config" in config_data and config_data["vision_config"].get("model_type") != "davit":  
        config_data["vision_config"]["model_type"] = "davit"  
        with open(config_path, "w") as f:  
            json.dump(config_data, f, indent=4)  
        print(f"修复后的配置文件已保存到 {config_path}")  
  
    # 加载模型和 Processor  
    config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)  
    model = AutoModelForCausalLM.from_pretrained(model_path, config=config, trust_remote_code=True).to(device)  
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)  
    return model, processor  
  
def run_inference_bird_od(model, processor, image_path, task_prompt="<BIRD_OD>", max_new_tokens=128):  
    """  
    对给定的图像和任务提示符进行推理。  
    Args:  
        model: 加载的 PyTorch 模型。  
        processor: 加载的 Processor 对象。  
        image_path (str): 输入图像的路径。  
        task_prompt (str): 任务提示符，默认为 "<BIRD_OD>"。  
        max_new_tokens (int): 生成的最大 token 数量。  
    Returns:  
        generated_text (str): 模型生成的文本输出。  
    """  
    # 加载图像并预处理  
    image = PIL.Image.open(image_path).convert("RGB")  
    inputs = processor(text=task_prompt, images=image, return_tensors="pt").to(device)  
  
    # 进行推理  
    with torch.no_grad():  
        generated_ids = model.generate(  
            input_ids=inputs["input_ids"],  
            pixel_values=inputs["pixel_values"],  
            max_new_tokens=max_new_tokens,  
            num_beams=5,  
            do_sample=True,  
            temperature=0.1,  
            top_k=50,  
            top_p=0.9,  
            repetition_penalty=1.2,  
        )  
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]  
    return generated_text  
  
if __name__ == "__main__":  
    # 示例：加载模型并运行推理  
    MODEL_PATH = "./model_checkpoints/epoch_7"  # 替换为实际模型路径  
    SAMPLE_IMAGE = "/root/BlueJayAnnotation/valid/BlueJay_1e8b8b6047d34edf.jpeg"  # 替换为实际图像路径  
  
    print(f"=== 加载模型和 Processor ===")  
    model, processor = load_model_and_processor(MODEL_PATH)  
  
    print(f"=== 对图像进行推理: {SAMPLE_IMAGE} ===")  
    output = run_inference_bird_od(model, processor, SAMPLE_IMAGE)  
  
    print("\n===== 生成的输出 =====")  
    print(output)  
```

Result:

```
=== 加载模型和 Processor ===
=== 对图像进行推理: /root/BlueJayAnnotation/valid/BlueJay_1e8b8b6047d34edf.jpeg ===

===== 生成的输出 =====
</s><s><s><s>Blue Jay <loc 0 547 746 1079></s>
```

