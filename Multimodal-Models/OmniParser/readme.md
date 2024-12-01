## OmniParser test and tuning

 ***Project address ：https://github.com/microsoft/OmniParser***

For more complex multi-step tasks, such as the mind2web benchmark, Omniparser performs relatively well compared to similar tools. 

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/4.png)

## Run Environment

Run OmniParser on GPU VM.

Only need to one of the icon_caption models.

```
yolo_model = get_yolo_model(model_path='weights/icon_detect/best.pt')
caption_model_processor = get_caption_model_processor(model_name="florence2", model_name_or_path="weights/icon_caption_florence")
```

```
yolo_model = get_yolo_model(model_path='weights/icon_detect/best.pt')
caption_model_processor = get_caption_model_processor(model_name="blip2", model_name_or_path="weights/icon_caption_blip2")
```

Based on actual test results, the effects of using icon_caption_blip2 and icon_caption_florence are the same. 

When you want to quantize model ,you only need do that on icon_caption model.

```

(omni) root@a100vm:~/OmniParser/weights# ls -al ./*
-rw-r--r-- 1 root root  319 Oct 28 11:20 ./convert_safetensor_to_pt.py


./icon_caption_blip2:
total 14628564
drwxr-xr-x 2 root root       4096 Oct 28 13:40 .
drwxr-xr-x 5 root root       4096 Oct 28 11:47 ..
-rw-r--r-- 1 root root       1140 Oct 28 11:57 LICENSE
-rw-r--r-- 1 root root        985 Oct 28 11:57 config.json
-rw-r--r-- 1 root root        136 Oct 28 11:57 generation_config.json
-rw-r--r-- 1 root root 4998300711 Oct  9 22:58 pytorch_model-00001-of-00002.bin
-rw-r--r-- 1 root root 4998064248 Oct 24 14:31 pytorch_model-00001-of-00002.safetensors
-rw-r--r-- 1 root root 2491516218 Oct  9 22:58 pytorch_model-00002-of-00002.bin
-rw-r--r-- 1 root root 2491456448 Oct 24 14:31 pytorch_model-00002-of-00002.safetensors
-rw-r--r-- 1 root root     121726 Oct 28 12:01 pytorch_model.bin.index.json



./icon_caption_florence:
total 1058612
drwxr-xr-x 2 root root       4096 Oct 28 11:56 .
drwxr-xr-x 5 root root       4096 Oct 28 11:47 ..
-rw-r--r-- 1 root root      72204 Oct 28 11:40 LICENSE
-rw-r--r-- 1 root root       5663 Oct 28 11:54 config.json
-rw-r--r-- 1 root root        292 Oct 28 11:54 generation_config.json
-rw-r--r-- 1 root root 1083916964 Oct 25 23:19 model.safetensors


./icon_detect:
total 18276
drwxr-xr-x 2 root root     4096 Oct 28 11:52 .
drwxr-xr-x 5 root root     4096 Oct 28 11:47 ..
-rw-r--r-- 1 root root   400264 Oct 28 11:43 LICENSE
-rw-r--r-- 1 root root 12222450 Oct 28 13:45 best.pt
-rw-r--r-- 1 root root  6075790 Oct 24 23:11 model.safetensors
-rw-r--r-- 1 root root     1087 Oct 28 11:52 model.yaml
```

Run OmniParser UI:

```
(omni) root@a100vm:~/OmniParser# python weights/convert_safetensor_to_pt.py
(omni) root@a100vm:~/OmniParser# python gradio_demo.py
```

## Effectiveness Verification

Original image：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/1.png)

Image analyzed by OmniParser:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/3.png)

Image download:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/2.webp)

Parsed screen elements:

```
Text Box ID 0: Technical Info
Text Box ID 1: #AB; ~
Text Box ID 2: [EXTERNAL]
Text Box ID 3: tested
Text Box ID 4: Al tools to generate Ul from the same prompt
Text Box ID 5: Xin .
Text Box ID 6: CE
Text Box ID 7: 4T
Text Box ID 8: 0 =2
Text Box ID 9: 2832
Text Box ID 10: Medium Daily Digest
Text Box ID 11: MD
Text Box ID 12: Medium Daily Digest <noreply@medium com>
Text Box ID 13: [EXTERNAL]
Text Box ID 14: tested
Text Box ID 15: Al tools to generate
Text Box ID 16: 7:40
Text Box ID 17: W/#A
Text Box ID 18: Xinyu Wei
Text Box ID 19: 2024/12/1 (AA) 7:40
Text Box ID 20: <https: | /mediumcom/
Text Box ID 21: #IFA noreply@mediumcom #BYBYWHB.
Text Box ID 22: BFR
Text Box ID 23: b1RRlLbb#AJPIAIAF
Text Box ID 24: JRAI NXTE Web Mk3E+ZZ1HB+.
Text Box ID 25: Medium Daily Digest
Text Box ID 26: [EXTERNAL] Turn $20,000
Text Box ID 27: Savings into
Text Box ID 28: 7:40
Text Box ID 29: <https:/ /medium.com/
Text Box ID 30: Stories for Xinyuwei
Text Box ID 31: xinyuwei_71929-Become
Text Box ID 32: member
Text Box ID 33: Bwz
Text Box ID 34: The Kaitchup
Text Box ID 35: [EXTERNAL] The Weekly Kaitchup #69-
Text Box ID 36: 11/29 (Az)
Text Box ID 37: Medium Daily Digest
Text Box ID 38: <https://eotrxsubstackcdncom/
Text Box ID 39: Medium Daily Digest
Text Box ID 40: TODAY'S HIGHLIGHTS
Text Box ID 41: [EXTERNAL]
Text Box ID 42: Introduction to VLMs: The
Text Box ID 43: <https:/ /medium.com/
Text Box ID 44: Bwd
Text Box ID 45: Xinran Ma
Text Box ID 46: The Kaitchup
Text Box ID 47: prcmoc
Text Box ID 48: [EXTERNAL] Fine-Tune Llama
Text Box ID 49: Vision;
Text Box ID 50: 11/28
Text Box ID 51: Step-by-step guide for memory-efficient
Text Box ID 52: Jim Monge from Generative
Text Box ID 53: [EXTERNAL] Flux Labs Al's Black Friday
Text Box ID 54: <https:/ [eotrxsubstackcdn.com/
Text Box ID 55: tested
Text Box ID 56: Al tools to generate Ul from the same prompt
Text Box ID 57: Medium Daily Digest
Text Box ID 58: [EXTERNAL] 10 ChatGPT and Claude
Text Box ID 59: Pro_ 11/28
Text Box ID 60: And here are the results
Text Box ID 61: <https:/ /mediumcom/
Text Box ID 62: min read
Text Box ID 63: Commercial Solution Areas
Text Box ID 64: Propel Your Career
Text Box ID 65: Speaker Series, fe_ 11/28
Text Box ID 66: Join us on December 10 at &.OOAM PTI
Text Box ID 67: BWE
Text Box ID 68: The Salt
Text Box ID 69: Curated
Text Box ID 70: Papers
Text Box ID 71: [EXTERNAL] Addressing the Numerical Issu_ 11/27
Text Box ID 72: <https:|/eotrxsubstackcdncom/
Text Box ID 73: Shenggang LiinTowards
Icon Box ID 74: More options or settings.
Icon Box ID 75: Teams
Icon Box ID 76: Forward navigation.
Icon Box ID 77: Expand to show more options
Icon Box ID 78: a scroll bar.
Icon Box ID 79: Ribbon display options
Icon Box ID 80: A messaging or chat feature.
Icon Box ID 81: Browsing.
Icon Box ID 82: Expand to show more options
Icon Box ID 83: Up arrow
Icon Box ID 84: Browsing.
```

## OmniParser Parameters

**Box Threshold** and **IOU Threshold** are two important parameters used to control the output of object detection models (YOLO models). Their specific meanings are as follows:

### Box Threshold


This parameter is used to set the confidence threshold for the detected bounding boxes.

- Bounding box confidence indicates the model's confidence level in the detected object. The higher the confidence, the more certain the model is that the bounding box contains an object.
- The value of the Box Threshold ranges between 0.01 and 1.0. When the confidence of a detected bounding box is lower than this threshold, the bounding box will be filtered out and will not appear in the final output.
- For example, if the Box Threshold is set to 0.05, bounding boxes with confidence lower than 0.05 will be ignored.

### IOU Threshold

 
IOU (Intersection over Union) is a metric used to measure the overlap between two bounding boxes.

- The IOU Threshold is used to set the threshold for Non-Maximum Suppression (NMS), a post-processing step that removes overlapping bounding boxes, keeping only the most likely one.
- The value of the IOU Threshold ranges between 0.01 and 1.0. When the IOU value between two bounding boxes is greater than this threshold, the bounding box with the lower confidence will be removed.
- For example, if the IOU Threshold is set to 0.1, when the IOU value between two bounding boxes is greater than 0.1, the bounding box with lower confidence will be removed.

### Summary

 

- **Box Threshold**: Used to filter out bounding boxes with confidence lower than this threshold.

- **IOU Threshold**: Used to remove bounding boxes with high overlap during Non-Maximum Suppression.

  Setting these two parameters can help you adjust the precision and recall of object detection to achieve the best detection results in different application scenarios.

## OmniParser Performance enhancement in V1.5

The results in small icon detect are significantly better than in previous.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/5.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/3.webp)

## Model Datatype

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/gpu.png)

From the above figure, it can be seen that using F2 for icon_caption is more resource-efficient.

The inference code can be modified from FP32 inference to BF16 inference. After the modification, memory usage drops significantly, with a slight decrease in accuracy.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/gpu2.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/gpu3.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/image-32.webp)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/image16.webp)

```
(omni) root@a100vm:~/OmniParser# cat gradio_demo-f2-bf16.py
from typing import Optional

import gradio as gr
import numpy as np
import torch
from PIL import Image
import io

import base64, os
from utils import check_ocr_box, get_yolo_model, get_caption_model_processor, get_som_labeled_img

# 设置设备为 CUDA
DEVICE = torch.device('cuda')

# 加载模型并将其移动到 DEVICE
yolo_model = get_yolo_model(model_path='weights/icon_detect/best.pt')
yolo_model = yolo_model.to(DEVICE)

caption_model_processor = get_caption_model_processor(
    model_name="florence2",
    model_name_or_path="weights/icon_caption_florence"
)
caption_model_processor['model'] = caption_model_processor['model'].to(DEVICE)

platform = 'pc'
if platform == 'pc':
    draw_bbox_config = {
        'text_scale': 0.8,
        'text_thickness': 2,
        'text_padding': 2,
        'thickness': 2,
    }
elif platform == 'web':
    draw_bbox_config = {
        'text_scale': 0.8,
        'text_thickness': 2,
        'text_padding': 3,
        'thickness': 3,
    }
elif platform == 'mobile':
    draw_bbox_config = {
        'text_scale': 0.8,
        'text_thickness': 2,
        'text_padding': 3,
        'thickness': 3,
    }

MARKDOWN = """
# OmniParser for Pure Vision Based General GUI Agent 🔥
<div>
    <a href="https://arxiv.org/pdf/2408.00203">
        <img src="https://img.shields.io/badge/arXiv-2408.00203-b31b1b.svg" alt="Arxiv" style="display:inline-block;">
    </a>
</div>

OmniParser is a screen parsing tool to convert general GUI screen to structured elements.
"""

# 启用推理模式
@torch.inference_mode()
def process(
    image_input,
    box_threshold,
    iou_threshold
) -> Optional[Image.Image]:

    image_save_path = 'imgs/saved_image_demo.png'
    image_input.save(image_save_path)

    # 禁用自动混合精度，以避免 EasyOCR 出现问题
    with torch.amp.autocast('cuda', enabled=False):
        # OCR 处理
        ocr_bbox_rslt, is_goal_filtered = check_ocr_box(
            image_save_path,
            display_img=False,
            output_bb_format='xyxy',
            goal_filtering=None,
            easyocr_args={'paragraph': False, 'text_threshold': 0.9}
        )
        text, ocr_bbox = ocr_bbox_rslt

    # 启用自动混合精度，处理支持 BF16 的部分
    with torch.amp.autocast('cuda', dtype=torch.bfloat16):
        # 使用模型进行推理
        dino_labled_img, label_coordinates, parsed_content_list = get_som_labeled_img(
            image_save_path,
            yolo_model,
            BOX_TRESHOLD=box_threshold,
            output_coord_in_ratio=True,
            ocr_bbox=ocr_bbox,
            draw_bbox_config=draw_bbox_config,
            caption_model_processor=caption_model_processor,
            ocr_text=text,
            iou_threshold=iou_threshold
        )

    image = Image.open(io.BytesIO(base64.b64decode(dino_labled_img)))
    print('finish processing')
    parsed_content_list = '\n'.join(parsed_content_list)
    return image, str(parsed_content_list)

with gr.Blocks() as demo:
    gr.Markdown(MARKDOWN)
    with gr.Row():
        with gr.Column():
            image_input_component = gr.Image(
                type='pil', label='Upload image')
            # 设置用于移除低置信度边界框的阈值，默认值为 0.05
            box_threshold_component = gr.Slider(
                label='Box Threshold', minimum=0.01, maximum=1.0, step=0.01, value=0.05)
            # 设置用于移除大量重叠边界框的阈值，默认值为 0.1
            iou_threshold_component = gr.Slider(
                label='IOU Threshold', minimum=0.01, maximum=1.0, step=0.01, value=0.1)
            submit_button_component = gr.Button(
                value='Submit', variant='primary')
        with gr.Column():
            image_output_component = gr.Image(
                type='pil', label='Image Output')
            text_output_component = gr.Textbox(
                label='Parsed screen elements', placeholder='Text Output')

    submit_button_component.click(
        fn=process,
        inputs=[
            image_input_component,
            box_threshold_component,
            iou_threshold_component
        ],
        outputs=[image_output_component, text_output_component]
    )

# 启动 Gradio 应用
demo.launch(share=True, server_port=7861, server_name='0.0.0.0')
```

