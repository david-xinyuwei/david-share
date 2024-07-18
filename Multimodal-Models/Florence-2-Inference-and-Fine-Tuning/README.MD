# Florence2 applications in multiple CV scenarios

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

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/2.png)

After I finished all the tests in this blog, the GPU memory assumption is:
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/gpu.jpg)



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
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/bee.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/city.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/zhou.jpeg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/4.jpg)
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/letter.jpg)

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
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/bee2.jpg)


```
task_prompt = '<REGION_PROPOSAL>'
results = run_example(task_prompt,image3)
print(results)
plot_bbox(image3, results['<REGION_PROPOSAL>'])
```

![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/zhou2.jpeg)


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
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/car.jpg)

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
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/zhou1.jpeg)

```
results = run_example(task_prompt,image2)
print(results)
plot_bbox(image2, results['<OD>'])
```
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/city1.jpg)



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
![image](https://github.com/davidsajare/david-share/blob/master/Multimodal-Models/Florence-2-Inference/images/letter1.jpg)
