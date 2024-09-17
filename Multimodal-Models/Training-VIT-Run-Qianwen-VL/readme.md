# Train ViT and Run Qianwen-VL

As of now, CV models are primarily based on convolutional neural networks. However, with the rise of Transformers, Vision Transformers are gradually being applied.

Next, let's look at mainstream CV implementations and their characteristics.

##  CV Architecture

**U-Net**

- **Features**: Encoder-decoder structure, skip connections.
- **Network Type**: Convolutional Neural Network (CNN).
- **Applications**: Image segmentation, medical image processing.
- **Advantages**: Efficient in segmentation tasks, preserves details.
- **Disadvantages**: Limited scalability for large datasets.
- **Usage**: Widely used in medical image segmentation.
- **Main Models**: Original U-Net, 3D U-Net, Stable Diffusion.

**R-CNN**

- **Features**: Selective search for generating candidate regions.
- **Network Type**: CNN-based.
- **Applications**: Object detection.
- **Advantages**: High detection accuracy.
- **Disadvantages**: High computational complexity, slow speed.
- **Usage**: Replaced by faster models like Faster R-CNN.
- **Main Models**: Fast R-CNN, Faster R-CNN.

**GAN**

- **Features**: Adversarial training between generator and discriminator.
- **Network Type**: Framework, usually using CNN.
- **Applications**: Image generation, style transfer.
- **Advantages**: Generates high-quality images.
- **Disadvantages**: Unstable training, prone to mode collapse.
- **Usage**: Widely used in generation tasks.
- **Main Models**: DCGAN, StyleGAN.

**RNN/LSTM**

- **Features**: Handles sequential data, remembers long-term dependencies.
- **Network Type**: Recurrent Neural Network.
- **Applications**: Time series prediction, video analysis.
- **Advantages**: Suitable for sequential data.
- **Disadvantages**: Difficult to train, gradient vanishing.
- **Usage**: Commonly used in sequence tasks.
- **Main Models**: LSTM, GRU.

**GNN**

- **Features**: Processes graph-structured data.
- **Network Type**: Graph Neural Network.
- **Applications**: Social network analysis, chemical molecule modeling.
- **Advantages**: Captures graph structure information.
- **Disadvantages**: Limited scalability for large graphs.
- **Usage**: Used in graph data tasks.
- **Main Models**: GCN, GraphSAGE.

**Capsule Networks**

- **Features**: Capsule structure, captures spatial hierarchies.
- **Network Type**: CNN-based.
- **Applications**: Image recognition.
- **Advantages**: Captures pose variations.
- **Disadvantages**: High computational complexity.
- **Usage**: Research stage, not widely applied.
- **Main Models**: Dynamic Routing.

**Autoencoder**

- **Features**: Encoder-decoder structure.
- **Network Type**: Can be CNN-based.
- **Applications**: Dimensionality reduction, feature learning.
- **Advantages**: Unsupervised learning.
- **Disadvantages**: Limited generation quality.
- **Usage**: Used for feature extraction and dimensionality reduction.
- **Main Models**: Variational Autoencoder (VAE).

**Vision Transformer (ViT)**

- **Features**: Based on self-attention mechanism, processes image patches.
- **Network Type**: Transformer.
- **Applications**: Image classification.
- **Advantages**: Captures global information.
- **Disadvantages**: Requires large amounts of data for training.
- **Usage**: Gaining popularity, especially on large datasets.
- **Main Models**: Original ViT, DeiT.

## ViT and U-Net

According to the paper: "Understanding the Efficacy of U-Net & Vision Transformer for Groundwater Numerical Modelling," U-Net is generally more efficient than ViT, especially in sparse data scenarios. U-Net's architecture is simpler with fewer parameters, making it more efficient in terms of computational resources and time. While ViT has advantages in capturing global information, its self-attention mechanism has high computational complexity, particularly when handling large-scale data.

In the experiments of the paper, models combining U-Net and ViT outperformed the Fourier Neural Operator (FNO) in both accuracy and efficiency, especially in sparse data conditions.

In image processing, sparse data typically refers to incomplete or unevenly distributed information in images. For example:

- **Low-resolution images**: Fewer pixels, missing details.

- **Occlusion or missing data**: Parts of the image are blocked or data is missing.

- **Uneven sampling**: Lower pixel density in certain areas.

  In these cases, models need to infer the complete image content from limited pixel information.

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nVib4ichhVGCQBuUiaibdEnGvH0xr2WiaUia2l3vicpmFCVACartbIBsZCzmOfddAavBibEBMXAkYkEXl2KRg/640?wx_fmt=jpeg&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



After the emergence of Vision Transformers, new branches and variations have appeared:

- **DeiT (Data-efficient Image Transformers) by Facebook AI**: DeiT models are refined ViT models. The authors also released more training-efficient ViT models, which can be directly integrated into ViTModel or ViTForImageClassification. Four variants are available (in three different sizes): `facebook/deit-tiny-patch16-224`, `facebook/deit-small-patch16-224`, `facebook/deit-base-patch16-224`, and `facebook/deit-base-patch16-384`. Note that images should be prepared using DeiTImageProcessor.

- **BEiT (BERT pre-training of Image Transformers) by Microsoft Research**: BEiT models use a self-supervised method inspired by BERT (masked image modeling) and based on VQ-VAE, outperforming vision transformers with supervised pre-training.

- **DINO (a self-supervised training method for Vision Transformers) by Facebook AI**: Vision Transformers trained with the DINO method exhibit interesting properties not found in convolutional models. They can segment objects without being explicitly trained for it. DINO checkpoints can be found on the hub.

- **MAE (Masked Autoencoder) by Facebook AI**: By pre-training Vision Transformers to reconstruct the pixel values of a large portion (75%) of masked patches (using an asymmetric encoder-decoder architecture), the authors demonstrate that this simple method outperforms supervised pre-training after fine-tuning.

  The following diagram describes the workflow of Vision Transformer (ViT):

1. **Image Patching**: The input image is divided into small, fixed-size patches.

2. **Linear Projection**: Each image patch is flattened and transformed into a vector through linear projection.

3. **Position Embedding**: Position embeddings are added to each image patch to retain positional information.

4. **CLS Token**: A learnable CLS token is added at the beginning of the sequence for classification tasks.

5. **Transformer Encoder**: These embedded vectors (including the CLS token) are fed into the Transformer encoder for multi-layer processing. Each layer includes a multi-head attention mechanism and a feedforward neural network.

6. **MLP Head**: After processing by the encoder, the output of the CLS token is passed to a multi-layer perceptron (MLP) head for the final classification decision.

   This entire process demonstrates how the Transformer architecture can directly handle sequences of image patches to perform image classification tasks.

   ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVib4ichhVGCQBuUiaibdEnGvH0t7zLI4cGoibJ8JbBsuk5tNvoTmWoBm8khC4pOHsTYqmjic8zu8QTu50Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

   ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX6nFMO3vFQ8F8xEicCzcLwUb1gcicpmMEWk88xaSHxXoaUG1NUejYN3Kia5a4bJ4EHwkeZIm5dDrrGg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

This diagram illustrates the structure of the Attention Layer in the Transformer encoder, specifically including:

- **Multi-Head Attention**: This is the core component of the Transformer. By using multiple attention heads, the model can focus on different parts of the input sequence in various subspaces, capturing richer features and relationships.

- **Normalization (Norm)**: Applied after the multi-head attention mechanism to help stabilize and accelerate the training process.

- **Residual Connection**: A residual connection in the attention layer adds the input directly to the output, promoting information flow and alleviating the vanishing gradient problem.

  These components work together to enable the Transformer to efficiently process and understand the complex relationships in the input data.

  ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX6nFMO3vFQ8F8xEicCzcLwUA5ribia4mXHedcsyLibESlAjHItXanmdWL3BtQrmMlYwWnOPSzpfvZzpA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

  ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX6nFMO3vFQ8F8xEicCzcLwUIXspK6B3KBhO4cIdhgqIpqkrKm8gLxGpviawygS4ia24Xs5aBwvRek0A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Residual Connections are a network design used to mitigate the vanishing gradient problem in deep neural networks. By adding direct skip connections between layers, they allow the input to be added directly to the output. This design makes the network easier to train, as it enables gradients to propagate directly through the skip connections, maintaining information flow. Residual connections were initially introduced in ResNet and are widely used in many modern deep learning models.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nX6nFMO3vFQ8F8xEicCzcLwUEWbZ3ICViccFhQprIYvSiabg69FTTxTn9nmicSIBxaBGbia0aubMow0A1Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Training ViT

Pure ViT is mainly for Image Classifier.

```
class Attention(nn.Module):  
    def __init__(self, dim, heads=8, dim_head=64, dropout=0.):  
        super().__init__()  
        inner_dim = dim_head * heads  
        project_out = not (heads == 1 and dim_head == dim)  
        self.heads = heads  
        self.scale = dim_head ** -0.5  
        self.norm = nn.LayerNorm(dim)  
        self.attend = nn.Softmax(dim=-1)  
        self.dropout = nn.Dropout(dropout)  
        self.to_qkv = nn.Linear(dim, inner_dim * 3, bias=False)  
        self.to_out = nn.Sequential(  
            nn.Linear(inner_dim, dim),  
            nn.Dropout(dropout)  
        ) if project_out else nn.Identity()  
  
    def forward(self, x):  
        x = self.norm(x)  
        qkv = self.to_qkv(x).chunk(3, dim=-1)  
        q, k, v = map(lambda t: rearrange(t, 'b n (h d) -> b h n d', h=self.heads), qkv)  
        dots = torch.matmul(q, k.transpose(-1, -2)) * self.scale  
        attn = self.attend(dots)  
        attn = self.dropout(attn)  
        out = torch.matmul(attn, v)  
        out = rearrange(out, 'b h n d -> b n (h d)')  
        return self.to_out(out)  
  
# 定义Feed Forward Network (FFN)  
class FFN(nn.Module):  
    def __init__(self, dim, hidden_dim, dropout=0.):  
        super().__init__()  
        self.net = nn.Sequential(  
            nn.LayerNorm(dim),  
            nn.Linear(dim, hidden_dim),  
            nn.GELU(),  
            nn.Dropout(dropout),  
            nn.Linear(hidden_dim, dim),  
            nn.Dropout(dropout)  
        )  
  
    def forward(self, x):  
        return self.net(x)  
  
# 定义Transformer Encoder  
class Transformer(nn.Module):  
    def __init__(self, dim, depth, heads, dim_head, mlp_dim_ratio, dropout):  
        super().__init__()  
        self.layers = nn.ModuleList([])  
        mlp_dim = mlp_dim_ratio * dim  
        for _ in range(depth):  
            self.layers.append(nn.ModuleList([  
                Attention(dim=dim, heads=heads, dim_head=dim_head, dropout=dropout),  
                FFN(dim=dim, hidden_dim=mlp_dim, dropout=dropout)  
            ]))  
  
    def forward(self, x):  
        for attn, ffn in self.layers:  
            x = attn(x) + x  
            x = ffn(x) + x  
        return x  
  
# 定义Vision Transformer (ViT)  
class ViT(nn.Module):  
    def __init__(self, *, image_size, patch_size, num_classes, dim, depth, heads, mlp_dim_ratio, pool='cls', channels=3, dim_head=64, dropout=0.):  
        super().__init__()  
        image_height, image_width = pair(image_size)  
        patch_height, patch_width = pair(patch_size)  
        assert image_height % patch_height == 0 and image_width % patch_width == 0, 'Image dimensions must be divisible by the patch size.'  
        num_patches = (image_height // patch_height) * (image_width // patch_width)  
        patch_dim = channels * patch_height * patch_width  
  
        self.to_patch_embedding = nn.Sequential(  
            Rearrange('b c (h p1) (w p2) -> b (h w) (p1 p2 c)', p1=patch_height, p2=patch_width),  
            nn.LayerNorm(patch_dim),  
            nn.Linear(patch_dim, dim),  
            nn.LayerNorm(dim)  
        )  
  
        self.cls_token = nn.Parameter(torch.randn(1, 1, dim))  
        self.pos_embedding = nn.Parameter(torch.randn(1, num_patches + 1, dim))  
        self.dropout = nn.Dropout(dropout)  
        self.transformer = Transformer(dim, depth, heads, dim_head, mlp_dim_ratio, dropout)  
        self.pool = pool  
        self.to_latent = nn.Identity()  
        self.mlp_head = nn.Linear(dim, num_classes)  
  
    def forward(self, img):  
        x = self.to_patch_embedding(img)  
        b, n, _ = x.shape  
        cls_tokens = repeat(self.cls_token, '1 1 d -> b 1 d', b=b)  
        x = torch.cat((cls_tokens, x), dim=1)  
        x += self.pos_embedding[:, :(n + 1)]  
        x = self.dropout(x)  
        x = self.transformer(x)  
        cls_token = x[:, 0]  
        feature_map = x[:, 1:]  
        pooled_output = cls_token if self.pool == 'cls' else feature_map.mean(dim=1)  
        pooled_output = self.to_latent(pooled_output)  
        classification_result = self.mlp_head(pooled_output)  
        return classification_result  
  
# 辅助函数  
def pair(t):  
    return t if isinstance(t, tuple) else (t, t)  
  
# 数据预处理  
transform = transforms.Compose([  
    transforms.Resize((32, 32)),  
    transforms.ToTensor(),  
    transforms.Normalize((0.5,), (0.5,))  
])  
  
# 加载CIFAR-10数据集  
train_dataset = datasets.CIFAR10(root='./data', train=True, download=True, transform=transform)  
train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)  
  
# 初始化ViT模型  
model = ViT(  
    image_size=32,  
    patch_size=4,  
    num_classes=10,  
    dim=128,  
    depth=6,  
    heads=8,  
    mlp_dim_ratio=4,  
    dropout=0.1  
)  
  
# 定义损失函数和优化器  
criterion = nn.CrossEntropyLoss()  
optimizer = optim.Adam(model.parameters(), lr=3e-4)  
  
# 训练模型  
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')  
model.to(device)  
  
for epoch in range(10):  # 训练10个epoch  
    model.train()  
    total_loss = 0  
    for images, labels in train_loader:  
        images, labels = images.to(device), labels.to(device)  
        optimizer.zero_grad()  
        outputs = model(images)  
        loss = criterion(outputs, labels)  
        loss.backward()  
        optimizer.step()  
        total_loss += loss.item()  
  
    print(f'Epoch {epoch+1}, Loss: {total_loss/len(train_loader)}')  
  
# 保存整个模型  
torch.save(model, 'vit_complete_model.pth')  
print("训练完成并保存模型！")  
```

Training result:

```
Files already downloaded and verified
Epoch 1, Loss: 1.5606277365513774
Epoch 2, Loss: 1.2305729564498453
Epoch 3, Loss: 1.0941925532067829
Epoch 4, Loss: 1.0005672584714183
Epoch 5, Loss: 0.9230595080139082
Epoch 6, Loss: 0.8589703797379418
Epoch 7, Loss: 0.7988450761188937
Epoch 8, Loss: 0.7343863746546724
Epoch 9, Loss: 0.6837297593388716
Epoch 10, Loss: 0.6306750321632151
训练完成并保存模型！
```

Inference test:

```
# 数据预处理  
transform = transforms.Compose([  
    transforms.Resize((32, 32)),  
    transforms.ToTensor(),  
    transforms.Normalize((0.5,), (0.5,))  
])  
  
# 加载CIFAR-10数据集  
test_dataset = datasets.CIFAR10(root='./data', train=False, download=True, transform=transform)  
test_loader = DataLoader(test_dataset, batch_size=64, shuffle=False)  
  
# 加载整个模型  
model = torch.load('vit_complete_model.pth')  
model.eval()  
  
# 设备设置  
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')  
model.to(device)  
  
# 进行推理测试  
with torch.no_grad():  
    for images, labels in test_loader:  
        images, labels = images.to(device), labels.to(device)  
        outputs = model(images)  
        _, predicted = torch.max(outputs, 1)  
  
        # 显示前5个样本的预测结果和图像  
        for i in range(5):  
            image = images[i].cpu().numpy().transpose((1, 2, 0))  
            image = (image * 0.5) + 0.5  # 反归一化  
            plt.imshow(image)  
            plt.title(f'预测: {test_dataset.classes[predicted[i]]}, 实际: {test_dataset.classes[labels[i]]}')  
            plt.show()  
  
        break  # 只显示一批数据 
```

Inference result:

![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Training-VIT-Run-Qianwen-VL/images/1.png)



![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Training-VIT-Run-Qianwen-VL/images/2.png)



![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Training-VIT-Run-Qianwen-VL/images/3.png)



![image](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/Training-VIT-Run-Qianwen-VL/images/4.png)

## Florence-2

Microsoft's Florence-2 uses a Transformer-based architecture, specifically adopting DeiT (Data-efficient Vision Transformer) as its visual encoder. DeiT's architecture is the same as ViT, with the addition of a distillation token in the input tokens. Distillation is a method to improve training performance, especially since ViT performs poorly with insufficient data.

Florence-2's model architecture employs a sequence-to-sequence learning approach. This means the model processes input sequences (such as images with text prompts) progressively and generates output sequences (such as descriptions or labels). In the sequence-to-sequence framework, each task is treated as a translation problem: the model receives an input image and a specific task prompt, then generates the corresponding output.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWiae5MCufG4IficQWbUIUOsBzafMHDvGgs07TrUPpac3PUcJE74zwGc4tNvgMygv5siaZUYogycMljg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Please refer to my repo get more info about  Florence-2 :

*https://github.com/xinyuwei-david/david-share/tree/master/Multimodal-Models/Florence-2-Inference-and-Fine-Tuning*



## Qianwen-VL

Qwen2-VL adopts an encoder-decoder architecture, combining Vision Transformer (ViT) with the Qwen2 language model. This architecture enables Qwen2-VL to handle image and video inputs and support multimodal tasks.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWiae5MCufG4IficQWbUIUOsB5nrMFqUxibBY8WTLTbmBZcrax5ibV5Dg9lPFOc10NHL0G8Ozed0lkbDw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Qwen2-VL also utilizes a new Multimodal Rotary Position Embedding (M-ROPE). Position embeddings are decomposed to capture one-dimensional text, two-dimensional visual, and three-dimensional video positional information, enhancing the model's ability to process multimodal data.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWiae5MCufG4IficQWbUIUOsBULNsa0kdBAZ5CYr8LRETUibODiaPKRNQnzxSnvlSRIYojDnaTWwxEThw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**Training of Qwen2-VL**

**Pre-training Phase:**

- **Objective**: The main goal is to optimize the visual encoder and adapter, while the language model (LLM) remains frozen.

- **Dataset**: A large, curated image-text pair dataset is used, crucial for the model to understand the relationship between visuals and text.

- **Optimization Goal**: Improve the model's text generation ability by minimizing the cross-entropy of text tokens, enabling more accurate text descriptions given an image.

  **Multitask Pre-training Phase:**

- **Training the Entire Model**: In this phase, the entire model, including the LLM, is trained.

- **Task Types**: The model is trained on various vision-language tasks, such as image captioning and visual question answering.

- **Data Quality**: High-quality, fine-grained data is used to provide richer visual and language information.

- **Input Resolution**: Increasing the input resolution of the visual encoder to reduce information loss, helping the model capture image details better.

  **Instruction Fine-tuning Phase:**

- **Objective**: Enhance the model's conversational and instruction-following capabilities.

- **Freezing the Visual Encoder**: The visual encoder remains frozen, focusing on optimizing the LLM and adapter.

- **Data Type**: A mix of multimodal and pure text dialogue data is used for optimization, aiding the model in better understanding and generating natural language when processing multimodal inputs.



## Qianwen-VL-Inference



```
messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                "image": "/root/image0.jpg",
            },
            {"type": "text", "text": "How many dogs do you see? What are they doing? Reply in Chinese."},
        ],
    }
]
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWiae5MCufG4IficQWbUIUOsBpf2YDnUFfOsKxvXHmwmgNhknj4eQn8icf9WbLBibXAo6TdBVQLY6AibhQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**['在这张图片中，我看到两只狗。左边的狗看起来像是柯基犬，而右边的狗看起来像是约克夏梗犬。它们似乎在户外的环境中奔跑，可能是散步或玩耍。']**



The model supports analysing video, but also using frame splitting. The model does not analyse audio.

```
model_name = "Qwen/Qwen2-VL-2B-Instruct"  
model = Qwen2VLForConditionalGeneration.from_pretrained(  
    model_name,   
    torch_dtype=torch.bfloat16,   
    attn_implementation="flash_attention_2",   
    device_map="auto"  
)  
processor = AutoProcessor.from_pretrained(model_name)  
  
messages = [  
    {  
        "role": "user",  
        "content": [  
            {  
                "type": "video",  
                "video": "/root/cars.mp4",  
                "max_pixels": 360 * 420,  
                "fps": 1.0,  # 确保 fps 正确传递  
                "video_fps": 1.0,  # 添加 video_fps  
            },  
            {"type": "text", "text": "Describe this video in Chinese."},  
        ],  
    }  
]  
  
text = processor.apply_chat_template(  
    messages, tokenize=False, add_generation_prompt=True  
)  
  
image_inputs, video_inputs = process_vision_info(messages)  
  
inputs = processor(  
    text=[text],  
    images=image_inputs,  
    videos=video_inputs,  
    padding=True,  
    return_tensors="pt",  
)  
  
inputs = inputs.to("cuda")  
  
generated_ids = model.generate(**inputs, max_new_tokens=256)  
generated_ids_trimmed = [  
    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)  
]  
  
output_text = processor.batch_decode(  
    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False  
)  
  
print(output_text)  
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWiae5MCufG4IficQWbUIUOsB5jWyU73sXfVcHic1OVFojs6j4G6B1oU0qockicKVcAUz7ppeG3z2c34Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**['视频中展示了一条繁忙的街道，车辆密集，交通堵塞。街道两旁是高楼大厦，天空阴沉，可能是傍晚或清晨。']**
