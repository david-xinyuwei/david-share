# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第7章 §7.1.2 微调实战：Burberry商品识别

# 补充：导入语句
import os
import pandas as pd
os.makedirs("./data/burberry_dataset/images", exist_ok=True)

# 数据下载脚本（精简版）
from datasets import load_dataset
import requests
from PIL import Image
from io import BytesIO
dataset = load_dataset('DBQ/Burberry.Product.prices.United.States')
df = dataset['train'].to_pandas()
filtered_rows = []
for idx, row in df.iterrows():
    image_url = row['imageurl']
    image_path = f"./data/burberry_dataset/images/{row['product_code']}.jpg"
    response = requests.get(image_url)
    Image.open(BytesIO(response.content)).save(image_path)
    row['local_image_path'] = image_path
    filtered_rows.append(row)
pd.DataFrame(filtered_rows).to_csv('./data/burberry_dataset/burberry_dataset.csv', index=False)
