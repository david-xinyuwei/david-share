```
pip install git+https://github.com/sberbank-ai/Real-ESRGAN.git
```

```
pip install huggingface_hub==0.16.4
```

```
import torch
from PIL import Image
import numpy as np
from RealESRGAN import RealESRGAN

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = RealESRGAN(device, scale=4)
model.load_weights('weights/RealESRGAN_x4.pth', download=True)
#model.load_weights('weights/RealESRGAN_x2plus.pth', download=True)
#model.load_weights('weights/RealESRGAN_x8.pth', download=True)

path_to_image = './low_resolution_input.png'
image = Image.open(path_to_image).convert('RGB')
sr_image = model.predict(image)

sr_image.save('./sr_image-4.png')
```





