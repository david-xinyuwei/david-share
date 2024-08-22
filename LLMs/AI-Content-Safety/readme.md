# AI-Content-Safety
This repo uses code from:
*https://github.com/Azure-Samples/AzureAIContentSafety.git* and did a little modification for fast PoC.

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/AI-Content-Safety/images/5.png)

## Prepare env

```
#git clone https://github.com/Azure-Samples/AzureAIContentSafety.git
#cd AzureAIContentSafety/python/1.0.0
```

```
#export CONTENT_SAFETY_KEY="70420***"
#export CONTENT_SAFETY_ENDPOINT="https://***/"
 ```
 ```
 (base) root@davidwei:/mnt/c/david-share/AzureAIContentSafety/python/1.0.0#
 
 ```
 ## Video filter
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
Refer tro sample_data/2.mp4, following is one frame of the video:

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/AI-Content-Safety/images/1.png)

I ran:
```
python3 sample_analyze_video.py
```
The process is as following：

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/AI-Content-Safety/images/2.png)

Results are：

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/AI-Content-Safety/images/3.png)

We could observe which pictures have issue.

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/AI-Content-Safety/images/4.png)

## Image filter
We could also use other scripts:
```
(base) root@davidwei:/mnt/c/david-share/AzureAIContentSafety/python/1.0.0# cat sample_analyze_image.py
```
```
# coding: utf-8

# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
import os

from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeImageOptions, ImageData, ImageCategory
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError


# Sample: Analyze image in sync request
def analyze_image():
    # analyze image
    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]
    image_path = os.path.abspath(os.path.join(os.path.abspath(__file__), "..", "./sample_data/2.jpg"))

    # Create a Content Safety client
    client = ContentSafetyClient(endpoint, AzureKeyCredential(key))

    # Build request
    with open(image_path, "rb") as file:
        request = AnalyzeImageOptions(image=ImageData(content=file.read()))

    # Analyze image
    try:
        response = client.analyze_image(request)
    except HttpResponseError as e:
        print("Analyze image failed.")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise

    hate_result = next(item for item in response.categories_analysis if item.category == ImageCategory.HATE)
    self_harm_result = next(item for item in response.categories_analysis if item.category == ImageCategory.SELF_HARM)
    sexual_result = next(item for item in response.categories_analysis if item.category == ImageCategory.SEXUAL)
    violence_result = next(item for item in response.categories_analysis if item.category == ImageCategory.VIOLENCE)

    if hate_result:
        print(f"Hate severity: {hate_result.severity}")
    if self_harm_result:
        print(f"SelfHarm severity: {self_harm_result.severity}")
    if sexual_result:
        print(f"Sexual severity: {sexual_result.severity}")
    if violence_result:
        print(f"Violence severity: {violence_result.severity}")


if __name__ == "__main__":
    analyze_image()
```
```
(base) root@davidwei:/mnt/c/david-share/AzureAIContentSafety/python/1.0.0# python sample_analyze_image.py
```
```
Hate severity: 0
SelfHarm severity: 0
Sexual severity: 2
Violence severity: 0
```
## Text filter
When we use text content fileter, we usually need customize blacklist of words.
```
(base) root@davidwei:/mnt/c/david-share/AzureAIContentSafety/python/1.0.0# cat sample_manage_blocklist.py
```
```
# coding: utf-8

# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------

# Sample: Create or modify a blocklist
def create_or_update_text_blocklist():
    # [START create_or_update_text_blocklist]

    import os
    from azure.ai.contentsafety import BlocklistClient
    from azure.ai.contentsafety.models import TextBlocklist
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import HttpResponseError

    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]

    # Create a Blocklist client
    client = BlocklistClient(endpoint, AzureKeyCredential(key))

    blocklist_name = "TestBlocklist"
    blocklist_description = "Test blocklist management."

    try:
        blocklist = client.create_or_update_text_blocklist(
            blocklist_name=blocklist_name,
            options=TextBlocklist(blocklist_name=blocklist_name, description=blocklist_description),
        )
        if blocklist:
            print("\nBlocklist created or updated: ")
            print(f"Name: {blocklist.blocklist_name}, Description: {blocklist.description}")
    except HttpResponseError as e:
        print("\nCreate or update text blocklist failed: ")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise

    # [END create_or_update_text_blocklist]


# Sample: Add blocklistItems to the list
def add_blocklist_items():
    import os
    from azure.ai.contentsafety import BlocklistClient
    from azure.ai.contentsafety.models import AddOrUpdateTextBlocklistItemsOptions, TextBlocklistItem
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import HttpResponseError

    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]

    # Create a Blocklist client
    client = BlocklistClient(endpoint, AzureKeyCredential(key))

    blocklist_name = "TestBlocklist"
    blocklist_item_text_1 = "k*ll"
    blocklist_item_text_2 = "h*te"
    blocklist_item_text_2 = "包子"

    blocklist_items = [TextBlocklistItem(text=blocklist_item_text_1), TextBlocklistItem(text=blocklist_item_text_2)]
    try:
        result = client.add_or_update_blocklist_items(
            blocklist_name=blocklist_name, options=AddOrUpdateTextBlocklistItemsOptions(blocklist_items=blocklist_items)
        )
        for blocklist_item in result.blocklist_items:
            print(
                f"BlocklistItemId: {blocklist_item.blocklist_item_id}, Text: {blocklist_item.text}, Description: {blocklist_item.description}"
            )
    except HttpResponseError as e:
        print("\nAdd blocklistItems failed: ")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise


# Sample: Analyze text with a blocklist
def analyze_text_with_blocklists():
    import os
    from azure.ai.contentsafety import ContentSafetyClient
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.contentsafety.models import AnalyzeTextOptions
    from azure.core.exceptions import HttpResponseError

    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]

    # Create a Content Safety client
    client = ContentSafetyClient(endpoint, AzureKeyCredential(key))

    blocklist_name = "TestBlocklist"
    input_text = "I h*te you and I want to k*ll you.我爱吃包子"

    try:
        # After you edit your blocklist, it usually takes effect in 5 minutes, please wait some time before analyzing
        # with blocklist after editing.
        analysis_result = client.analyze_text(
            AnalyzeTextOptions(text=input_text, blocklist_names=[blocklist_name], halt_on_blocklist_hit=False)
        )
        if analysis_result and analysis_result.blocklists_match:
            print("\nBlocklist match results: ")
            for match_result in analysis_result.blocklists_match:
                print(
                    f"BlocklistName: {match_result.blocklist_name}, BlocklistItemId: {match_result.blocklist_item_id}, "
                    f"BlocklistItemText: {match_result.blocklist_item_text}"
                )
    except HttpResponseError as e:
        print("\nAnalyze text failed: ")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise


# Sample: List all blocklistItems in a blocklist
def list_blocklist_items():
    import os
    from azure.ai.contentsafety import BlocklistClient
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import HttpResponseError

    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]

    # Create a Blocklist client
    client = BlocklistClient(endpoint, AzureKeyCredential(key))

    blocklist_name = "TestBlocklist"

    try:
        blocklist_items = client.list_text_blocklist_items(blocklist_name=blocklist_name)
        if blocklist_items:
            print("\nList blocklist items: ")
            for blocklist_item in blocklist_items:
                print(
                    f"BlocklistItemId: {blocklist_item.blocklist_item_id}, Text: {blocklist_item.text}, "
                    f"Description: {blocklist_item.description}"
                )
    except HttpResponseError as e:
        print("\nList blocklist items failed: ")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise


# Sample: List all blocklists
def list_text_blocklists():
    import os
    from azure.ai.contentsafety import BlocklistClient
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import HttpResponseError

    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]

    # Create a Blocklist client
    client = BlocklistClient(endpoint, AzureKeyCredential(key))

    try:
        blocklists = client.list_text_blocklists()
        if blocklists:
            print("\nList blocklists: ")
            for blocklist in blocklists:
                print(f"Name: {blocklist.blocklist_name}, Description: {blocklist.description}")
    except HttpResponseError as e:
        print("\nList text blocklists failed: ")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise


# Sample: Get a blocklist by blocklistName
def get_text_blocklist():
    import os
    from azure.ai.contentsafety import BlocklistClient
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import HttpResponseError

    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]

    # Create a Blocklist client
    client = BlocklistClient(endpoint, AzureKeyCredential(key))

    blocklist_name = "TestBlocklist"

    try:
        blocklist = client.get_text_blocklist(blocklist_name=blocklist_name)
        if blocklist:
            print("\nGet blocklist: ")
            print(f"Name: {blocklist.blocklist_name}, Description: {blocklist.description}")
    except HttpResponseError as e:
        print("\nGet text blocklist failed: ")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise


# Sample: Get a blocklistItem by blocklistName and blocklistItemId
def get_blocklist_item():
    import os
    from azure.ai.contentsafety import BlocklistClient
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.contentsafety.models import TextBlocklistItem, AddOrUpdateTextBlocklistItemsOptions
    from azure.core.exceptions import HttpResponseError

    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]

    # Create a Blocklist client
    client = BlocklistClient(endpoint, AzureKeyCredential(key))

    blocklist_name = "TestBlocklist"
    blocklist_item_text_1 = "k*ll"

    try:
        # Add a blocklistItem
        add_result = client.add_or_update_blocklist_items(
            blocklist_name=blocklist_name,
            options=AddOrUpdateTextBlocklistItemsOptions(blocklist_items=[TextBlocklistItem(text=blocklist_item_text_1)]),
        )
        if not add_result or not add_result.blocklist_items or len(add_result.blocklist_items) <= 0:
            raise RuntimeError("BlocklistItem not created.")
        blocklist_item_id = add_result.blocklist_items[0].blocklist_item_id

        # Get this blocklistItem by blocklistItemId
        blocklist_item = client.get_text_blocklist_item(blocklist_name=blocklist_name, blocklist_item_id=blocklist_item_id)
        print("\nGet blocklistItem: ")
        print(
            f"BlocklistItemId: {blocklist_item.blocklist_item_id}, Text: {blocklist_item.text}, Description: {blocklist_item.description}"
        )
    except HttpResponseError as e:
        print("\nGet blocklist item failed: ")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise


# Sample: Remove blocklistItems from a blocklist
def remove_blocklist_items():
    import os
    from azure.ai.contentsafety import BlocklistClient
    from azure.core.credentials import AzureKeyCredential
    from azure.ai.contentsafety.models import (
        TextBlocklistItem,
        AddOrUpdateTextBlocklistItemsOptions,
        RemoveTextBlocklistItemsOptions,
    )
    from azure.core.exceptions import HttpResponseError

    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]

    # Create a Blocklist client
    client = BlocklistClient(endpoint, AzureKeyCredential(key))

    blocklist_name = "TestBlocklist"
    blocklist_item_text_1 = "k*ll"

    try:
        # Add a blocklistItem
        add_result = client.add_or_update_blocklist_items(
            blocklist_name=blocklist_name,
            options=AddOrUpdateTextBlocklistItemsOptions(blocklist_items=[TextBlocklistItem(text=blocklist_item_text_1)]),
        )
        if not add_result or not add_result.blocklist_items or len(add_result.blocklist_items) <= 0:
            raise RuntimeError("BlocklistItem not created.")
        blocklist_item_id = add_result.blocklist_items[0].blocklist_item_id

        # Remove this blocklistItem by blocklistItemId
        client.remove_blocklist_items(
            blocklist_name=blocklist_name, options=RemoveTextBlocklistItemsOptions(blocklist_item_ids=[blocklist_item_id])
        )
        print(f"\nRemoved blocklistItem: {add_result.blocklist_items[0].blocklist_item_id}")
    except HttpResponseError as e:
        print("\nRemove blocklist item failed: ")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise


# Sample: Delete a list and all of its contents
def delete_blocklist():
    import os
    from azure.ai.contentsafety import BlocklistClient
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import HttpResponseError

    key = os.environ["CONTENT_SAFETY_KEY"]
    endpoint = os.environ["CONTENT_SAFETY_ENDPOINT"]

    # Create a Blocklist client
    client = BlocklistClient(endpoint, AzureKeyCredential(key))

    blocklist_name = "TestBlocklist"

    try:
        client.delete_text_blocklist(blocklist_name=blocklist_name)
        print(f"\nDeleted blocklist: {blocklist_name}")
    except HttpResponseError as e:
        print("\nDelete blocklist failed:")
        if e.error:
            print(f"Error code: {e.error.code}")
            print(f"Error message: {e.error.message}")
            raise
        print(e)
        raise


if __name__ == "__main__":
    create_or_update_text_blocklist()
    add_blocklist_items()
    analyze_text_with_blocklists()
    list_blocklist_items()
    list_text_blocklists()
    get_text_blocklist()
    get_blocklist_item()
    remove_blocklist_items()
    delete_blocklist()
```
```
(base) root@davidwei:/mnt/c/david-share/AzureAIContentSafety/python/1.0.0# python sample_manage_blocklist.py
```
```
Blocklist created or updated:
Name: TestBlocklist, Description: Test blocklist management.
BlocklistItemId: 0e3ad7f0-a445-4347-8908-8b0a21d59be7, Text: 包子, Description:
BlocklistItemId: 77bea3a5-a603-4760-b824-fa018762fcf7, Text: k*ll, Description:

Blocklist match results:
BlocklistName: TestBlocklist, BlocklistItemId: 541cad19-841c-40c5-a2ce-31cd8f1621f9, BlocklistItemText: h*te
BlocklistName: TestBlocklist, BlocklistItemId: 77bea3a5-a603-4760-b824-fa018762fcf7, BlocklistItemText: k*ll

List blocklist items:
BlocklistItemId: 77bea3a5-a603-4760-b824-fa018762fcf7, Text: k*ll, Description:
BlocklistItemId: 0e3ad7f0-a445-4347-8908-8b0a21d59be7, Text: 包子, Description:
BlocklistItemId: 541cad19-841c-40c5-a2ce-31cd8f1621f9, Text: h*te, Description:

List blocklists:
Name: TestBlocklist, Description: Test blocklist management.

Get blocklist:
Name: TestBlocklist, Description: Test blocklist management.

Get blocklistItem:
BlocklistItemId: 77bea3a5-a603-4760-b824-fa018762fcf7, Text: k*ll, Description:

Removed blocklistItem: 77bea3a5-a603-4760-b824-fa018762fcf7

Deleted blocklist: TestBlocklist
```