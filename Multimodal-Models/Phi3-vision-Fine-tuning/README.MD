# Phi-3.5-vision Fine tuning

In this test, I use Burberry's data to fine-tune Phi3.5-Vision comprehensively. The goal is to enable the fine-tuned model to predict brand, description, category, and price information based on product images.

 I ran the code on Azure NC H100 GPU VM.
![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/4.png)

## Base Model capability before SFT

Phi-3-v base model gives wrong answer based on text question "1.what is the price in 6.5? 2.What is the good?" and image.

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/7.png)



Phi-3.5-v base model gives wrong answer based on text question "1.what is the price in 6.5? 2.What is the good?" and image.

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/8.png)

 ##  Training Code

```
import os
import torch
from torch.utils.data import Dataset, DataLoader, random_split
from transformers import AutoModelForCausalLM, AutoProcessor
from torchvision import transforms
from PIL import Image
import torch.optim as optim
import pandas as pd
import random
import wandb
import torch.nn.functional as F
import numpy as np
from torchvision.transforms.functional import resize, to_pil_image




torch.manual_seed(3)


# Initialize Weights & Biases
run = wandb.init(project="davidwei-phi35-v")




# Custom Dataset for Burberry Product Prices and Images
class BurberryProductDataset(Dataset):
    def __init__(self, dataframe, tokenizer, max_length, image_size):
        self.dataframe = dataframe
        self.tokenizer = tokenizer
        self.tokenizer.padding_side = 'left'
        self.max_length = max_length
        
    def __len__(self):
        return len(self.dataframe)


    def __getitem__(self, idx):
        row = self.dataframe.iloc[idx]
        text = f"<|user|>\n<|image_1|>What is shown in this image?<|end|><|assistant|>\nProduct: {row['title']}, Category: {row['category3_code']}, Full Price: {row['full_price']}<|end|>"
        image_path = row['local_image_path']
        
        # Tokenize text
        encodings = self.tokenizer(text, truncation=True, padding='max_length', max_length=self.max_length)
        
        try:
            # Load and transform image
            image = Image.open(image_path).convert("RGB")
            image = self.image_transform_function(image)
        except (FileNotFoundError, IOError):
            # Skip the sample if the image is not found
            return None
        
        encodings['pixel_values'] = image
        encodings['price'] = row['full_price']
        
        return {key: torch.tensor(val) for key, val in encodings.items()}


    def image_transform_function(self, image):
        image = np.array(image)
        return image






# Load dataset from disk
dataset_path = './data/burberry_dataset/burberry_dataset.csv'
df = pd.read_csv(dataset_path)


# Initialize processor and tokenizer
model_id = "microsoft/Phi-3.5-vision-instruct"
processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
tokenizer = processor.tokenizer


# Split dataset into training and validation sets
train_size = int(0.9 * len(df))
val_size = len(df) - train_size
train_indices, val_indices = random_split(range(len(df)), [train_size, val_size])
train_indices = train_indices.indices
val_indices = val_indices.indices
train_df = df.iloc[train_indices]
val_df = df.iloc[val_indices]


# Create dataset and dataloader
train_dataset = BurberryProductDataset(train_df, tokenizer, max_length=512, image_size=128)
val_dataset = BurberryProductDataset(val_df, tokenizer, max_length=512, image_size=128)
train_loader = DataLoader(train_dataset, batch_size=1, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=1, shuffle=False)




# Initialize model
model = AutoModelForCausalLM.from_pretrained(model_id, device_map="cuda", trust_remote_code=True, torch_dtype="auto")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)


# Optimizer
optimizer = optim.AdamW(model.parameters(), lr=5e-5)
# Training loop
num_epochs = 1
eval_interval = 150  # Evaluate every 'eval_interval' steps
loss_scaling_factor = 1000.0  # Variable to scale the loss by a certain amount
save_dir = '/root/phi35v-saved_models'
step = 0
accumulation_steps = 64  # Accumulate gradients over this many steps


if not os.path.exists(save_dir):
    os.makedirs(save_dir)


best_val_loss = float('inf')
best_model_path = None


# Select 10 images from the validation set for logging
num_log_samples = 10
log_indices = random.sample(range(len(val_dataset)), num_log_samples)






def extract_price_from_predictions(predictions, tokenizer):
    # Assuming the price is at the end of the text and separated by a space
    predicted_text = tokenizer.decode(predictions[0], skip_special_tokens=True)
    try:
        predicted_price = float(predicted_text.split()[-1].replace(',', ''))
    except ValueError:
        predicted_price = 0.0
    return predicted_price








def evaluate(model, val_loader, device, tokenizer, step, log_indices, max_samples=None, ):
    model.eval()
    total_loss = 0
    total_price_error = 0
    log_images = []
    log_gt_texts = []
    log_pred_texts = []
    table = wandb.Table(columns=["Image", "Ground Truth Text", "Predicted Text"])


    with torch.no_grad():
        for i, batch in enumerate(val_loader):
            if max_samples and i >= max_samples:
                break


            if batch is None:  # Skip if the batch is None
                continue


            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            pixel_values = batch['pixel_values'].to(device)
            labels = input_ids.clone().detach()
            actual_price = batch['price'].item()


            outputs = model(
                input_ids=input_ids, 
                attention_mask=attention_mask, 
                pixel_values=pixel_values, 
                labels=labels
            )
            loss = outputs.loss
            total_loss += loss.item()


            # Calculate price error
            predictions = torch.argmax(outputs.logits, dim=-1)
            predicted_price = extract_price_from_predictions(predictions, tokenizer)
            price_error = abs(predicted_price - actual_price)
            total_price_error += price_error


            # Log images, ground truth texts, and predicted texts
            if i in log_indices:
                log_images.append(pixel_values.cpu().squeeze().numpy())
                log_gt_texts.append(tokenizer.decode(labels[0], skip_special_tokens=True))
                log_pred_texts.append(tokenizer.decode(predictions[0], skip_special_tokens=True))


                # Convert image to PIL format
                pil_img = to_pil_image(resize(torch.from_numpy(log_images[-1]).permute(2, 0, 1), (336, 336))).convert("RGB")
                
                # Add data to the table
                table.add_data(wandb.Image(pil_img), log_gt_texts[-1], log_pred_texts[-1])


                # Log the table incrementally
    
    wandb.log({"Evaluation Results step {}".format(step): table, "Step": step})


    avg_loss = total_loss / (i + 1)  # i+1 to account for the loop index
    avg_price_error = total_price_error / (i + 1)
    model.train()


    return avg_loss, avg_price_error




model.train()
for epoch in range(num_epochs):  # Number of epochs
    total_train_loss = 0
    total_train_price_error = 0
    batch_count = 0


    for batch in train_loader:
        step += 1


        if batch is None:  # Skip if the batch is None
            continue


        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        pixel_values = batch['pixel_values'].to(device)
        labels = input_ids.clone().detach()
        actual_price = batch['price'].float().to(device)


        outputs = model(
            input_ids=input_ids, 
            attention_mask=attention_mask, 
            pixel_values=pixel_values, 
            labels=labels
        )
        loss = outputs.loss
        total_loss = loss
        predictions = torch.argmax(outputs.logits, dim=-1)            
        predicted_price = extract_price_from_predictions(predictions, tokenizer)


        
        total_loss.backward()


        if (step % accumulation_steps) == 0:
            for param in model.parameters():
                if param.grad is not None:
                    param.grad /= accumulation_steps
            optimizer.step()
            optimizer.zero_grad()


        total_train_loss += total_loss.item()
        total_train_price_error += abs(predicted_price - actual_price.item())
        batch_count += 1


        # Log batch loss to wandb
        wandb.log({"Batch Loss": total_loss.item(), "Step": step})


        print(f"Epoch: {epoch}, Step: {step}, Batch Loss: {total_loss.item()}")


        if step % eval_interval == 0:
            val_loss, val_price_error = evaluate(model, val_loader, device, tokenizer=tokenizer, log_indices=log_indices, step=step )
            wandb.log({
                "Validation Loss": val_loss,
                "Validation Price Error (Average)": val_price_error,
                "Step": step
            })
            print(f"Step: {step}, Validation Loss: {val_loss}, Validation Price Error (Normalized): {val_price_error}")


            # Save the best model
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_model_path = os.path.join(save_dir, f"best_model")
                model.save_pretrained(best_model_path, safe_serialization=False)
                tokenizer.save_pretrained(best_model_path)






            avg_train_loss = total_train_loss / batch_count
            avg_train_price_error = total_train_price_error / batch_count
            wandb.log({
                "Epoch": epoch,
                "Average Training Loss": avg_train_loss,
                "Average Training Price Error": avg_train_price_error
            })
            
    print(f"Epoch: {epoch}, Average Training Loss: {avg_train_loss}, Average Training Price Error: {avg_train_price_error}")


    if best_model_path:
        run.log_model(
            path=best_model_path,
            name="phi35-v-burberry",
            aliases=["best"],
        )




    wandb.finish()

```

Get related files:

```
cd /root/phi35v-saved_models/best_model
wget https://huggingface.co/microsoft/Phi-3-vision-128k-instruct/resolve/main/preprocessor_config.json
wget https://huggingface.co/microsoft/Phi-3-vision-128k-instruct/resolve/main/processing_phi3_v.py
wget https://huggingface.co/microsoft/Phi-3-vision-128k-instruct/resolve/main/image_processing_phi3_v.py

```



## Inference Code

```
import os  
import torch  
from transformers import AutoModelForCausalLM, AutoProcessor  
from PIL import Image  
import requests  
from io import BytesIO  
import base64  
from pathlib import Path  
from IPython.display import display, Image as IPythonImage, HTML  
  
# 定义模型存储的本地目录  
artifact_dir = '/root/phi35v-saved_models/best_model'  # 请将此路径替换为您实际的模型目录  
  
# 加载模型和处理器  
try:  
    model = AutoModelForCausalLM.from_pretrained(  
        artifact_dir,  
        torch_dtype=torch.float16,  
        attn_implementation="flash_attention_2",  
        trust_remote_code=True  
    )  
    processor = AutoProcessor.from_pretrained(artifact_dir, trust_remote_code=True)  
except Exception as e:  
    print(f"Error loading model or processor: {e}")  
    raise  
  
# 确保模型在正确的设备上  
device = 'cuda' if torch.cuda.is_available() else 'cpu'  
model.to(device)  
  
# 将图像转换为 data URL 的函数  
EXT_TO_MIMETYPE = {  
    '.jpg': 'image/jpeg',  
    '.jpeg': 'image/jpeg',  
    '.png': 'image/png',  
    '.svg': 'image/svg+xml'  
}  
  
def image_to_data_url(image: Image.Image, ext: str) -> str:  
    ext = ext.lower()  
    if ext not in EXT_TO_MIMETYPE:  
        ext = '.jpg'  # 如果未知扩展名，默认使用 .jpg  
    mimetype = EXT_TO_MIMETYPE[ext]  
    buffered = BytesIO()  
    image_format = 'JPEG' if ext in ['.jpg', '.jpeg'] else ext.replace('.', '').upper()  
    image.save(buffered, format=image_format)  
    encoded_string = base64.b64encode(buffered.getvalue()).decode('utf-8')  
    data_url = f"data:{mimetype};base64,{encoded_string}"  
    return data_url  
  
# 对单张图像进行推理的函数  
def run_inference(image_path_or_url: str) -> dict:  
    try:  
        prompt = "<|user|>\n<|image_1|>1.what is the price in 8? 2.What is the good?<|end|><|assistant|>\n"  
  
        # 检查输入是 URL 还是本地文件路径  
        if image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://"):  
            # 从 URL 加载图像  
            image = Image.open(requests.get(image_path_or_url, stream=True).raw).convert('RGB')  
            ext = Path(image_path_or_url).suffix  
        else:  
            # 从本地文件路径加载图像  
            image = Image.open(image_path_or_url).convert('RGB')  
            ext = Path(image_path_or_url).suffix  
  
        # 将图像转换为 data URL  
        data_url = image_to_data_url(image, ext)  
        inputs = processor(prompt, images=[image], return_tensors="pt").to(device)  
        generation_args = {  
            "max_new_tokens": 500,  
            "do_sample": False  
        }  
        generate_ids = model.generate(**inputs, eos_token_id=processor.tokenizer.eos_token_id, **generation_args)  
        # 去除输入的 tokens  
        generate_ids = generate_ids[:, inputs['input_ids'].shape[1]:]  
        response_text = processor.batch_decode(generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]  
        return {  
            "predicted_text": response_text,  
            "image_data_url": data_url  
        }  
    except Exception as e:  
        print(f"Error during inference: {e}")  
        raise  
  
# 示例使用  
# 对于本地图像  
image_path_or_url = "/home/david/5.jpg"  
# 或者，对于 URL 图像  
# image_path_or_url = "https://example.com/image.jpg"  
  
try:  
    result = run_inference(image_path_or_url)  
    print("Predicted Text:", result['predicted_text'])  
  
    # 使用结果中的 data URL 显示图像  
    display(HTML(f'<img src="{result["image_data_url"]}" alt="Image" />'))  
  
    # 或者，根据图像路径类型显示图像  
    if image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://"):  
        # 对于 URL  
        response = requests.get(image_path_or_url)  
        image_data = response.content  
        display(IPythonImage(data=image_data))  
    else:  
        # 对于本地文件路径  
        display(IPythonImage(filename=image_path_or_url))  
  
except Exception as e:  
    print(f"Error running inference: {e}")  
```



## Training Steps

Original training data URL:

https://huggingface.co/datasets/DBQ/Burberry.Product.prices.United.States


After processing the original training data with the code, a CSV file and a directory containing product images will be generated locally on the Azure GPU VM:
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/1.png)
Here is a preview of the CSV file contents:
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/2.png)

Here is a sample image from the images directory:
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/3.png)

Training Results:
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/5.png)
![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/6.png)

We could also check training report on wandb:

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/9.png)

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/10.png)

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/12.png)

## Inference validation

Since the training data consists entirely of Burberry items, the model's predictions for Burberry products are highly accurate. I won't elaborate on this further. I tried using an image of Nike shoes for prediction. If only the shoe image is provided, the model can correctly identify the brand and features but not the price. However, if the e-commerce image information is provided, it can accurately describe the item.

***prompt = "<|user|>\n<|image_1|>1.what is the price in 6.5? 2.What is the good?<|end|><|assistant|>\n"***

image_path_or_url = "/root/5.jpg"  

![image](https://github.com/davidsajare/Phi3-vision-Fine-tuning/blob/main/images/7.jpg)

Inference Results:

***Predicted Text: 1. The price for size 6.5 is $115.00. 2. The good is Nike Dunk Low DD1503-101 Women's White Black Leather Sneaker Shoes Size 9 PRO43.***

You can see that I specifically asked for the price of the product of size 6.5 in the prompt. The response was quite accurate. This scenario is particularly suitable for e-commerce quality inspectors performing edge inference detection.

Do more complex test:

***Prompt: 1.what are the prices in 6.5， 7.5， 8? 2.What is the good?<|end|><|assistant|>\n"***  

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Phi3-vision-Fine-tuning/images/13.png)

**Reference Link:**

*https://wandb.ai/byyoung3/mlnews3/reports/How-to-fine-tune-Phi-3-vision-on-a-custom-dataset--Vmlldzo4MTEzMTg3*
