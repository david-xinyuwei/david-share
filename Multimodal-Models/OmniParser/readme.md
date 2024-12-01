## OmniParser

 ***Project address ：https://github.com/microsoft/OmniParser***

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/OmniParser/images/4.png)

## Run Environment

Run OmniParser on GPU VM.

Only need to one of the icon_caption models. When you want to quantize model ,you only need do that on icon_caption model..

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