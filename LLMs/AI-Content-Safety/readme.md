# AI-Content-Safety
This repo uses code from  https://github.com/Azure-Samples/AzureAIContentSafety.git, and did a little modification for fast PoC.

## Prepare env

```
#git clone https://github.com/Azure-Samples/AzureAIContentSafety.git
#cd AzureAIContentSafety/python/1.0.0
```

```
#export CONTENT_SAFETY_KEY="7042*"
#export CONTENT_SAFETY_ENDPOINT="https:*cognitiveservices.azure.com/"
 ```
 ```
 (base) root@davidwei:/mnt/c/david-share/AzureAIContentSafety/python/1.0.0#
 
 ```
 There are lots of useful python scripts. I mainly modified  sample_analyze_video.py.
 
 ```
 #cat sample_analyze_video.py
 ```
 ```
 import os
import imageio.v3 as iio
import numpy as np
from PIL import Image
from io import BytesIO
import datetime
from tqdm import tqdm
from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.contentsafety.models import AnalyzeImageOptions, ImageData, ImageCategory

def analyze_video():
    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]
    video_path = os.path.abspath(
        os.path.join(os.path.abspath(__file__), "..", "./sample_data/2.mp4"))
    client = ContentSafetyClient(endpoint, AzureKeyCredential(key))

    video = iio.imread(video_path, plugin='pyav')
    sampling_fps = 1
    fps = 30  # 假设视频的帧率为30，如果不同，请调整
    key_frames = [frame for i, frame in enumerate(video) if i % int(fps / sampling_fps) == 0]

    results = []  # 用于存储每个帧的分析结果
    output_dir = "./video-results"
    os.makedirs(output_dir, exist_ok=True)

    for key_frame_idx in tqdm(range(len(key_frames)), desc="Processing video",
                              total=len(key_frames)):
        frame = Image.fromarray(key_frames[key_frame_idx])
        frame_bytes = BytesIO()
        frame.save(frame_bytes, format="PNG")

        # 保存帧到本地
        frame_filename = f"frame_{key_frame_idx}.png"
        frame_path = os.path.join(output_dir, frame_filename)
        frame.save(frame_path)

        request = AnalyzeImageOptions(image=ImageData(content=frame_bytes.getvalue()))

        frame_time_ms = key_frame_idx * 1000 / sampling_fps
        frame_timestamp = datetime.timedelta(milliseconds=frame_time_ms)
        print(f"Analyzing video at {frame_timestamp}")
        try:
            response = client.analyze_image(request)
        except HttpResponseError as e:
            print(f"Analyze video failed at {frame_timestamp}")
            if e.error:
                print(f"Error code: {e.error.code}")
                print(f"Error message: {e.error.message}")
            raise

        hate_result = next(
            (item for item in response.categories_analysis if item.category == ImageCategory.HATE), None)
        self_harm_result = next(
            (item for item in response.categories_analysis if item.category == ImageCategory.SELF_HARM), None)
        sexual_result = next(
            (item for item in response.categories_analysis if item.category == ImageCategory.SEXUAL), None)
        violence_result = next(
            (item for item in response.categories_analysis if item.category == ImageCategory.VIOLENCE), None)

        frame_result = {
            "frame": frame_filename,
            "timestamp": str(frame_timestamp),
            "hate_severity": hate_result.severity if hate_result else None,
            "self_harm_severity": self_harm_result.severity if self_harm_result else None,
            "sexual_severity": sexual_result.severity if sexual_result else None,
            "violence_severity": violence_result.severity if violence_result else None
        }
        results.append(frame_result)

    # 打印所有帧的分析结果
    for result in results:
        print(result)

if __name__ == "__main__":
    analyze_video()
 ```
 The code now could divide video into pictures in one directory and give a finall tables which frames/picture have issue.
 
 