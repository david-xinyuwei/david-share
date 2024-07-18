# Florence2 applications in multiple CV scenarios and Fine Tuning


Florence-2 has 4 version released by Microsoft official:
```
Model	Model size	Model Description
Florence-2-base[HF]	0.23B	Pretrained model with FLD-5B
Florence-2-large[HF]	0.77B	Pretrained model with FLD-5B
Florence-2-base-ft[HF]	0.23B	Finetuned model on a colletion of downstream tasks
Florence-2-large-ft[HF]	0.77B	Finetuned model on a colletion of downstream tasks
```

In this blog, I am going to test via Florence-2-Large-ft
check memory need of loading model:

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/2.png)

After I finished all the tests in this blog, the GPU memory assumption is:
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/gpu.jpg)



## Load Model
```
model_id = 'microsoft/Florence-2-large-ft'
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True, device_map='cuda')
print(model)
processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
```
Define related functrions:
```
def run_example(task_prompt, image):
    inputs = processor(text=task_prompt, images=image, return_tensors="pt")
    generated_ids = model.generate(
      input_ids=inputs["input_ids"].cuda(),
      pixel_values=inputs["pixel_values"].cuda(),
      max_new_tokens=1024,
      early_stopping=False,
      do_sample=False,
      num_beams=3,
    )
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed_answer = processor.post_process_generation(
        generated_text,
        task=task_prompt,
        image_size=(image.width, image.height)
    )

    return parsed_answer
```
## Load images
Load images form website and local:
```
url1 = "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/tasks/bee.JPG?download=true"
image1 = Image.open(requests.get(url1, stream=True).raw)
image1.show()  

url2 = "https://images.unsplash.com/photo-1601751664209-be452817a8ce?q=80&w=2574&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
image2 = Image.open(requests.get(url2, stream=True).raw)
image2.show()  


# 从本地路径加载图片  
local_image_path = "/root/zhou.jpeg"  
image3 = Image.open(local_image_path)  
image3.show()  

local_image_path = "/root/4.jpg"  
image4 = Image.open(local_image_path)  
image4.show()  

local_image_path = "/root/letter.jpg"  
image5 = Image.open(local_image_path)  
image5.show()  

```
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/bee.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/city.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/zhou.jpeg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/4.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/letter.jpg)

## CV Scenarios test
### Genarate CAPTION from the images
```
task_prompt = "<CAPTION>"
results = run_example(task_prompt,image1)
print(results)

***output***
{'<CAPTION>': 'A bee is sitting on a pink flower.'}
```
```
task_prompt = "<CAPTION>"
results = run_example(task_prompt,image2)
print(results)

***output***
{'<CAPTION>': 'A crowded city street at night with lots of people.'}
```
```
task_prompt = "<CAPTION>"
results = run_example(task_prompt,image3)
print(results)

***output***
{'<CAPTION>': 'A man in a tuxedo sitting at a piano.'}
```
```
task_prompt = "<CAPTION>"
results = run_example(task_prompt,image4)
print(results)

***output***
{'<CAPTION>': 'A man standing on a stage in front of a large screen that says Microsoft Al Day.'}

```

```
task_prompt = '<DETAILED_CAPTION>'
run_example(task_prompt, image4)

***output***
{'<DETAILED_CAPTION>': 'In this image we can see a few people, among them, some people are holding the mics, there are some screens with some text and images, also we can some lights, and the background is dark.'}

```
```
task_prompt = '<MORE_DETAILED_CAPTION>'
run_example(task_prompt, image1)


***output***
{'<MORE_DETAILED_CAPTION>': 'A bee is sitting on a flower. The flower is a light pink color. The bee is black and yellow. There is a yellow center on the flower. There are other flowers around the flower as well.'}
```


### DENSE REGION CAPTION and REGION_PROPOSA

```
task_prompt = '<DENSE_REGION_CAPTION>'
results = run_example(task_prompt,image1)
print(results)
plot_bbox(image1, results['<DENSE_REGION_CAPTION>'])
```
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/bee2.jpg)


```
task_prompt = '<REGION_PROPOSAL>'
results = run_example(task_prompt,image3)
print(results)
plot_bbox(image3, results['<REGION_PROPOSAL>'])
```

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/zhou2.jpeg)


### Caption to Phrase Grounding
```
import requests

from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM 


model = AutoModelForCausalLM.from_pretrained("microsoft/Florence-2-large", trust_remote_code=True)
processor = AutoProcessor.from_pretrained("microsoft/Florence-2-large", trust_remote_code=True)

url = "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/transformers/tasks/car.jpg?download=true"
image = Image.open(requests.get(url, stream=True).raw)

  
def run_example(task_prompt, text_input=None):  
    if text_input is None:  
        prompt = task_prompt  
    else:  
        prompt = task_prompt + text_input  
      
    inputs = processor(text=prompt, images=image, return_tensors="pt")  
    generated_ids = model.generate(  
        input_ids=inputs["input_ids"],  
        pixel_values=inputs["pixel_values"],  
        max_new_tokens=1024,  
        num_beams=3  
    )  
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]  
    parsed_answer = processor.post_process_generation(generated_text, task=task_prompt, image_size=(image.width, image.height))  
      
    return parsed_answer  
  
def draw_bboxes(image, bboxes, labels):  
    draw = ImageDraw.Draw(image)  
    for bbox, label in zip(bboxes, labels):  
        # bbox 是 [x1, y1, x2, y2] 的格式  
        draw.rectangle(bbox, outline="red", width=3)  
        draw.text((bbox[0], bbox[1]), label, fill="red")  
    image.show()  
  
# 运行示例  
task_prompt = "<CAPTION_TO_PHRASE_GROUNDING>"  
text_input = "A green car parked in front of a yellow building."  
results = run_example(task_prompt, text_input=text_input)  
  
# 解析结果并绘制边界框  
bboxes = results['<CAPTION_TO_PHRASE_GROUNDING>']['bboxes']  
labels = results['<CAPTION_TO_PHRASE_GROUNDING>']['labels']  
draw_bboxes(image, bboxes, labels)  
```
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/car.jpg)

### Bounding boxes
To process the location tokens and render them on the image, the following method will be called to plot bounding boxes.
```
import matplotlib.pyplot as plt
import matplotlib.patches as patches
def plot_bbox(image, data):
   # Create a figure and axes
    fig, ax = plt.subplots()

    # Display the image
    ax.imshow(image)

    # Plot each bounding box
    for bbox, label in zip(data['bboxes'], data['labels']):
        # Unpack the bounding box coordinates
        x1, y1, x2, y2 = bbox
        # Create a Rectangle patch
        rect = patches.Rectangle((x1, y1), x2-x1, y2-y1, linewidth=1, edgecolor='r', facecolor='none')
        # Add the rectangle to the Axes
        ax.add_patch(rect)
        # Annotate the label
        plt.text(x1, y1, label, color='white', fontsize=8, bbox=dict(facecolor='red', alpha=0.5))

    # Remove the axis ticks and labels
    ax.axis('off')

    # Show the plot
    plt.show()

task_prompt = '<OD>'
results = run_example(task_prompt,image3)
print(results)
plot_bbox(image3, results['<OD>'])
```
```
{'<OD>': {'bboxes': [[220.4290008544922, 84.06000518798828, 312.9389953613281, 197.82000732421875], [69.86100006103516, 24.660001754760742, 363.34100341796875, 359.46002197265625], [71.13700103759766, 162.1800079345703, 358.875, 359.46002197265625], [222.34300231933594, 207.54000854492188, 279.76300048828125, 239.94000244140625]], 'labels': ['human face', 'person', 'suit', 'tie']}}
```
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/zhou1.jpeg)

```
results = run_example(task_prompt,image2)
print(results)
plot_bbox(image2, results['<OD>'])
```
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/city1.jpg)



### OCR test
```
def draw_ocr_bboxes(image, prediction):
    scale = 1
    draw = ImageDraw.Draw(image)
    bboxes, labels = prediction['quad_boxes'], prediction['labels']
    for box, label in zip(bboxes, labels):
        color = random.choice(colormap)
        new_box = (np.array(box) * scale).tolist()
        draw.polygon(new_box, width=3, outline=color)
        draw.text((new_box[0]+8, new_box[1]+2),
                    "{}".format(label),
                    align="right",

                    fill=color)
    display(image)
task_prompt = '<OCR>'
run_example(task_prompt,image5)
```
{'<OCR>': '26th May, 2010Dear Evie.I am in Paris which is a place in France. Ihave been eating some of the yummy food.They have the best cakes and pastries here.My favourite are the chocolate croissants.Today I went to the Louvre Museum. It isenormous! I saw some very famous paintingsand some big sculptures there.What painting might you like you like to seeif you visited the Louure?Yours truly.Gaby x x x'}


```
task_prompt = '<OCR_WITH_REGION>'
results = run_example(task_prompt,image5)
print(results)
output_image5 = copy.deepcopy(image5)
draw_ocr_bboxes(output_image5, results['<OCR_WITH_REGION>'])
```
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/letter1.jpg)

##  Fine Tuning Florence2
Load dataset on HF:
```
import torch
from datasets import load_dataset 

data = load_dataset("HuggingFaceM4/DocumentVQA")

from transformers import AutoModelForCausalLM, AutoProcessor
import torch

device = torch.device("cuda" if torch.cuda.is_available() else "cpu") 

model = AutoModelForCausalLM.from_pretrained(
    "microsoft/Florence-2-base-ft",
    trust_remote_code=True,
    revision='refs/pr/6'
).to(device) 
processor = AutoProcessor.from_pretrained("microsoft/Florence-2-large-ft", 
    trust_remote_code=True, revision='refs/pr/6')

for param in model.vision_tower.parameters():
  param.is_trainable = False
  
import torch  
from torch.utils.data import Dataset  
  
class DocVQADataset(Dataset):  
    def __init__(self, data):  
        self.data = data  
  
    def __len__(self):  
        return len(self.data)  
  
    def __getitem__(self, idx):  
        example = self.data[idx]  
        question = "<DocVQA>" + example['question']  
        first_answer = example['answers'][0]  
        image = example['image'].convert("RGB")  
        return question, first_answer, image  


class DocVQADataset(Dataset): 

    def __init__(self, data): 
        self.data = data
        
    def __len__(self): 
        return len(self.data)
        
    def __getitem__(self, idx):
        example = self.data[idx]
        question = "<DocVQA>" + example['question'] 
        first_answer = example['answers'][0]
        image = example['image'].convert("RGB")
        return question, first_answer, image

```
Identify training and validation dataset:
```
import os 
from torch.utils.data import DataLoader
from tqdm import tqdm 
from transformers import AdamW, get_scheduler

def collate_fn(batch): 
    questions, answers, images = zip(*batch)
    inputs = processor(text=list(questions), images=list(images), return_tensors="pt", padding=True).to(device)
    return inputs, answers 

train_dataset = DocVQADataset(data['train'])
val_dataset = DocVQADataset(data['validation']) 
batch_size = 20
num_workers = 0

train_loader = DataLoader(train_dataset, batch_size=batch_size, 
                          collate_fn=collate_fn, num_workers=num_workers, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=batch_size, 
                          collate_fn=collate_fn, num_workers=num_workers)
```
Set training parameters and lauch training:
```
epochs = 1  
optimizer = AdamW(model.parameters(), lr=1e-6)  
num_training_steps = epochs * len(train_loader)  
lr_scheduler = get_scheduler(  
    name="linear",  
    optimizer=optimizer,  
    num_warmup_steps=0,  
    num_training_steps=num_training_steps,  
)  
  
# 创建保存模型的目录  
model_dir = "/root/models/florence2"  
os.makedirs(model_dir, exist_ok=True)  
  
for epoch in range(epochs):  
    model.train()  
    train_loss = 0  
    i = -1  
    for inputs, answers in tqdm(train_loader, desc=f"Training Epoch {epoch + 1}/{epochs}"):  
        i += 1  
        input_ids = inputs["input_ids"]  
        pixel_values = inputs["pixel_values"]  
        labels = processor.tokenizer(text=answers, return_tensors="pt", padding=True, return_token_type_ids=False).input_ids.to(device)  
        outputs = model(input_ids=input_ids, pixel_values=pixel_values, labels=labels)  
        loss = outputs.loss  
        loss.backward()  
        optimizer.step()  
        lr_scheduler.step()  
        optimizer.zero_grad()  
        train_loss += loss.item()  
    avg_train_loss = train_loss / len(train_loader)  
    print(f"Average Training Loss: {avg_train_loss}")  
  
    model.eval()  
    val_loss = 0  
    with torch.no_grad():  
        for batch in tqdm(val_loader, desc=f"Validation Epoch {epoch + 1}/{epochs}"):  
            inputs, answers = batch  
            input_ids = inputs["input_ids"]  
            pixel_values = inputs["pixel_values"]  
            labels = processor.tokenizer(text=answers, return_tensors="pt", padding=True, return_token_type_ids=False).input_ids.to(device)  
            outputs = model(input_ids=input_ids, pixel_values=pixel_values, labels=labels)  
            loss = outputs.loss  
            val_loss += loss.item()  
    print(val_loss / len(val_loader))  
  
    # 保存检查点  
    checkpoint_dir = os.path.join(model_dir, f"checkpoint-epoch-{epoch + 1}")  
    model.save_pretrained(checkpoint_dir)  
    processor.save_pretrained(checkpoint_dir)  
    print(f"Checkpoint saved at {checkpoint_dir}")  
  
# 最终保存模型  
model.save_pretrained(model_dir)  
processor.save_pretrained(model_dir)  
print(f"Model saved at {model_dir}")  
  
```
Traing result is as following
```
Resolving data files:   0%|          | 0/38 [00:00<?, ?it/s]Resolving data files:   0%|          | 0/17 [00:00<?, ?it/s]Resolving data files:   0%|          | 0/17 [00:00<?, ?it/s]Resolving data files:   0%|          | 0/38 [00:00<?, ?it/s]Resolving data files:   0%|          | 0/17 [00:00<?, ?it/s]Resolving data files:   0%|          | 0/17 [00:00<?, ?it/s]Loading dataset shards:   0%|          | 0/51 [00:00<?, ?it/s]
/opt/miniconda/envs/florence2/lib/python3.10/site-packages/transformers/optimization.py:591: FutureWarning: This implementation of AdamW is deprecated and will be removed in a future version. Use the PyTorch implementation torch.optim.AdamW instead, or set `no_deprecation_warning=True` to disable this warning
  warnings.warn(
Training Epoch 1/1: 100%|█████████████████████████████████████████████████████████| 1974/1974 [2:49:29<00:00,  5.15s/it]
Average Training Loss: 1.8126093233277853
Validation Epoch 1/1: 100%|███████████████████████████████████████████████████████████| 268/268 [12:55<00:00,  2.89s/it]
0.7707678641178715
Checkpoint saved at /root/models/florence2/checkpoint-epoch-1
Model saved at /root/models/florence2
```
Resource comsumed in training:

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/gpu2.jpg)
Then load trained model from local and do Inference
```
from transformers import AutoModelForCausalLM, AutoProcessor, AutoConfig  
import torch  
from PIL import Image  
import matplotlib.pyplot as plt  
  
# 加载配置、模型和处理器  
config = AutoConfig.from_pretrained("/root/models/florence2", trust_remote_code=True)  
if config.vision_config.model_type != 'davit':  
    config.vision_config.model_type = 'davit'  
  
model = AutoModelForCausalLM.from_pretrained("/root/models/florence2", config=config, trust_remote_code=True)  
processor = AutoProcessor.from_pretrained("/root/models/florence2", trust_remote_code=True)  
  
# 设置设备  
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  
model.to(device)  
  
def prepare_inference_data(question, image_path):  
    image = Image.open(image_path).convert("RGB")  
    inputs = processor(text=[question], images=[image], return_tensors="pt", padding=True).to(device)  
    return inputs  
  
def infer(question, image_path):  
    model.eval()  
    inputs = prepare_inference_data(question, image_path)  
    with torch.no_grad():  
        outputs = model.generate(input_ids=inputs["input_ids"], pixel_values=inputs["pixel_values"], max_new_tokens=100)  
    answer = processor.tokenizer.decode(outputs[0], skip_special_tokens=True)  
    return answer  
  
# 示例问题和图像路径  
question = "<DocVQA>What is the stage betweenHidden states and LLM?"  
image_path = "/home/david/2.jpg"  
  
# 进行推理  
answer = infer(question, image_path)  
  
# 显示图片  
image = Image.open(image_path)  
plt.imshow(image)  
plt.axis('off')  # 关闭坐标轴  
plt.show()  
  
# 打印问题和答案  
print(f"Question: {question}")  
print(f"Answer: {answer}")  
```
The output is as following:
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning/images/arch.jpg)


**Refer:**
https://huggingface.co/blog/finetune-florence2