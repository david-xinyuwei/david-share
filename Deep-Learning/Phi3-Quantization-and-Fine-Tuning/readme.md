# Phi3-Quantization-and-Fine-Tuning
  
The fine-tuning and quantization of Phi3 are not fundamentally different from those of Phi2. However, there are minor differences in the details, which will be discussed in this article.  
  
## 1. Static and Runtime States of Neural Network Models  
  
A neural network model can be viewed from two perspectives: the static part and the runtime state.  
  
### Static Part  
  
1. **Model Weight File (model_weights.h5 or model_weights.pt)**:  
   - **Content**: Stores the model's weights and biases, which are learned through optimization algorithms during training.  
   - **Loading Process**:  
     1. **Read File**: The model weight file (e.g., .h5 or .pt file) is read into memory.  
     2. **Parse and Decode**: The binary data in the file is parsed and decoded into the model's weight matrices and bias vectors.  
     3. **Assign to Model**: The parsed weights and biases are assigned to the various layers and nodes of the model, initializing the model's parameters.  
  
2. **Configuration File (config.json)**:  
   - **Definition**: Defines the model's architecture, including the number of layers, the type of each layer (e.g., convolutional layer, fully connected layer), and the parameters of each layer (e.g., filter size, stride).  
  
3. **Vocabulary File (vocab.txt)**:  
   - **Purpose**: Used in processing text data, storing the vocabulary and their indices, which are used to convert text into numerical forms that the model can process.  
  
4. **Additional Tools and Scripts (preprocess.py, postprocess.py)**:  
   - **Purpose**: Used for data preprocessing and postprocessing, such as resizing and normalizing images, or tokenizing text.  
  
5. **Training/Fine-Tuning Scripts (train.py, finetune.py)**:  
   - **Content**: Contains the code for training or fine-tuning the model. These scripts define the training process, including the choice of loss function, optimizer configuration, and training epochs.  
  
### Runtime Part  
  
1. **Input (input_data)**:  
   - **Content**: The raw data received by the model, which can be in various forms such as images, text, or audio.  
  
2. **Activation (activations)**:  
   - **Content**: The output values processed by the activation function of each layer, which serve as the input for the next layer.  
  
3. **Intermediate States (layer_outputs)**:  
   - **Content**: Other forms of output that each layer may produce, such as feature maps in convolutional layers.  
  
4. **Gradients (gradients)**:  
   - **Content**: The gradients of each parameter calculated during training through the backpropagation algorithm.  
  
5. **Loss Value (loss_value)**:  
   - **Content**: The difference value between the current model output and the true labels, calculated by the loss function.  
  
6. **State Updates (weight_updates, optimizer_states)**:  
   - **Content**: The updated weights based on the gradients and learning rate, as well as the states maintained by the optimizer (e.g., momentum and adaptive learning rate information).  
  
7. **Caches (forward_cache)**:  
   - **Content**: Certain values cached during forward propagation, used for efficiently calculating gradients during backpropagation.  
  
These components together ensure the correct operation and performance of the model during training and inference. The static part defines the model's structure and initial state, while the runtime part involves the model's dynamic behavior and state updates when processing data.  
  
## 2. Quantization Methods  
  
From a higher-level classification, model quantization methods can generally be divided into two categories: Quantization-Aware Training (QAT) and Post-Training Quantization (PTQ).  
  
### Quantization-Aware Training (QAT)  
  
- **Characteristics**: Simulates the effects of quantization during model training, allowing the model to account for quantization errors during training.  
- **Advantages**: Typically produces higher precision quantized models because the model parameters adapt to the quantization constraints during training.  
  
### Post-Training Quantization (PTQ)  
  
- **Characteristics**: A quantization method applied after model training is completed, without the need to retrain the model.  
- **Popular Methods**: GPTQ, bitsandbytes, and AWQ, all of which belong to post-training quantization (PTQ).  
  
In deep learning model quantization, the primary focus is on the runtime part of the model, especially the quantization of weights and activation values. This is because the main goal of quantization is to reduce the computational complexity and memory usage during inference, thereby speeding up model execution and reducing power consumption, which is particularly important for deployment on resource-constrained devices.  
  
### Focus of Quantization  
  
1. **Weight Quantization**:  
   - **Content**: Weights are the static part of the model, stored in the model file. Weight quantization involves converting floating-point weights to lower precision formats (e.g., int8 or int16).  
   - **Purpose**: Performed before model deployment, it can significantly reduce model size and speed up model loading time.  
  
2. **Activation Quantization**:  
   - **Content**: Activation values are generated during model runtime, representing the data passed between layers. Activation quantization usually occurs during model inference, i.e., dynamic quantization.  
   - **Purpose**: Reduces computational requirements and memory usage during runtime.  
  
### Static File and Runtime Quantization  
  
- **Static File Quantization**: Mainly involves weight quantization, which is completed before model deployment to reduce the model file size.  
- **Runtime Quantization**: Involves the quantization of activation values, performed during model execution to optimize inference performance.  
  
In summary, quantization involves both the static part of the model (e.g., weights) and the runtime part (e.g., activation values). Both types of quantization aim to optimize the storage and execution efficiency of the model, especially in resource-constrained environments.  
  
## 3. Specific Implementation of Quantization Methods  
  
### BitsandBytes  
  
- **Main Quantization Part**: Primarily quantizes the model's weights.  
- **Characteristics**: Uses a special 4-bit data type called NormalFloat (NF) to achieve weight quantization. This method focuses on reducing the storage and computational requirements of model weights, thereby optimizing model size and inference speed while maintaining performance.  
  
### GPTQ (Gradient-based Post-Training Quantization)  
  
- **Main Quantization Part**: Primarily quantizes the model's weights but may also involve activation quantization, especially in lower bit-width settings.  
- **Characteristics**: Provides more flexibility, supporting the reduction of model precision to 8-bit, 4-bit, 3-bit, or even 2-bit. This method uses gradient information to optimize the quantization process, reducing the impact of quantization on model performance.  
  
### AWQ (Activation-aware Weight Quantization)  
  
- **Quantization Type**: Dynamic quantization  
- **Quantization Part**: Primarily quantizes weights.  
- **Characteristics**:  
  - **Activation-Aware**: Considers the distribution and characteristics of activation values when quantizing weights. This means that AWQ adaptively adjusts quantization parameters based on the statistical properties of activation values during the quantization process, reducing the negative impact of quantization on model performance.  
  - **Adaptive Quantization**: Adjusts quantization parameters adaptively based on the statistical properties of weights, which can change dynamically during different training stages or data batches.  
  - **Quantization During Training**: Unlike static quantization, AWQ can be applied during model training, allowing the model to optimize while considering quantization effects.  
  
### QAT (Quantization-Aware Training)  
  
- **Quantization Type**: Mixed quantization  
- **Quantization Part**: Quantizes both weights and activations.  
- **Characteristics**:  
  - **Simulates Quantization During Training**: Simulates the effects of quantization throughout the training process, helping to train models that maintain high performance even after quantization.  
  - **Reduces Quantization-Induced Accuracy Loss**: By considering the impact of quantization during training, QAT can significantly reduce the negative impact of quantization on model accuracy.  
  
In summary, BitsandBytes and GPTQ primarily focus on weight quantization because weight quantization can significantly reduce model size and improve computational efficiency with relatively minor impact on model performance. Both methods aim to improve model deployment efficiency and runtime speed by optimizing weight storage and computation. AWQ, on the other hand, considers the distribution and characteristics of activation values when quantizing weights, further reducing the negative impact of quantization on model performance. Among various mainstream quantization techniques, AWQ currently achieves relatively high precision (compared to GPTQ, bitsandbytes, etc.) and fast inference speed for quantized models.  
  
## 4. Example of AWQ Quantization Parameters  
  
Below is a configuration example for quantization using AWQ:  
```  
quant_config = {  
    "zero_point": True,  
    "q_group_size": 128,  
    "w_bit": 4,  
    "version": "GEMM"  
}  
```

### Parameter Explanation:

### `zero_point`

- **Type**: Boolean (True or False)
- **Description**: Determines whether to use zero point during the quantization process. A zero point is an offset used to align floating-point numbers with their integer representation during quantization.
- **Benefits**: Using a zero point can improve the accuracy of quantization, especially when dealing with tensors that have negative values.
- **Overhead**: Using a zero point increases computational complexity because each quantization and dequantization operation needs to account for this offset.

### `q_group_size`

- **Type**: Integer
- **Description**: Specifies the size of groups during the quantization process. Quantization grouping involves dividing weights or activations into multiple groups, with each group being quantized independently.
- **Benefits**: Smaller group sizes can enhance the flexibility and accuracy of quantization but also increase computational overhead. A group size of 128 is common, balancing precision and computational efficiency.
- **Overhead**: Smaller group sizes increase computational and storage overhead as each group requires independent quantization parameters. Larger group sizes reduce these overheads but may decrease quantization accuracy.

### `w_bit`

- **Type**: Integer
- **Description**: Specifies the bit-width used during quantization. The bit-width determines the precision of the quantized values.
- **Benefits**: Higher bit-width can improve quantization accuracy but also increases storage and computational overhead. 4-bit quantization (i.e., `w_bit=4`) is a common low-bit quantization method that significantly reduces model size and computation while maintaining high accuracy.
- **Overhead**: Higher bit-width increases storage and computational overhead as each quantized value requires more bits for representation. Lower bit-widths (like 4-bit or 2-bit) can significantly reduce model size and computation but may introduce more quantization error.

### `version`

- **Type**: String

- **Description**: Specifies the version or implementation of the quantization algorithm. "GEMM" typically refers to an implementation optimized using General Matrix Multiplication.

- **Benefits**: Using optimized versions can enhance computational efficiency, especially on hardware accelerators.

- **Overhead**: Different implementations may have varying hardware and software requirements, necessitating selection based on the specific application scenario and hardware platform.

  For example, `int4-awq-block-128` refers to a quantization result with `w_bit=4` and `q_group_size=128`.



## 5.Quantization Code Implementation

### bnb
```
model_name = "microsoft/Phi-3-mini-4k-instruct"
quant_path = 'Phi-3-mini-4k-instruct-bnb-4bit'

# 加载分词器
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

# 配置 BitsAndBytesConfig
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=compute_dtype,
    bnb_4bit_use_double_quant=True,
)

# 加载模型
model = AutoModelForCausalLM.from_pretrained(
    model_name, quantization_config=bnb_config, trust_remote_code=True
)

# 保存模型和分词器
model.save_pretrained("./" + quant_path, safetensors=True)
tokenizer.save_pretrained("./" + quant_path)
```

### GPTQ

```
from transformers import AutoModelForCausalLM, AutoTokenizer
from optimum.gptq import GPTQQuantizer
import torch
model_path = 'microsoft/Phi-3-mini-4k-instruct'
w = 4 #quantization to 4-bit. Change to 2, 3, or 8 to quantize with another precision

quant_path = 'Phi-3-mini-4k-instruct-gptq-'+str(w)+'bit'

# Load model and tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype=torch.float16, device_map="auto", trust_remote_code=True)
quantizer = GPTQQuantizer(bits=w, dataset="c4", model_seqlen = 2048)
quantized_model = quantizer.quantize_model(model, tokenizer)

quantized_model.save_pretrained("./"+quant_path, safetensors=True)
tokenizer.save_pretrained("./"+quant_path)
```

### AWQ
```
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

model_path = 'microsoft/Phi-3-mini-128k-instruct'
quant_path = 'Phi-3-mini-128k-instruct-awq-4bit'
quant_config = { "zero_point": True, "q_group_size": 128, "w_bit": 4, "version": "GEMM" }

# Load model and tokenizer
model = AutoAWQForCausalLM.from_pretrained(model_path, safetensors=True)
tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)

# Quantize
model.quantize(tokenizer, quant_config=quant_config)

# Save quantized model with safetensors
model.save_quantized("./"+quant_path, safetensors=True)
tokenizer.save_pretrained("./"+quant_path)
```
## 6. Fine Tuning
Training code:

```
model_name = "microsoft/Phi-3-mini-4k-instruct"

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, add_eos_token=True, use_fast=True)
tokenizer.pad_token = tokenizer.unk_token
tokenizer.pad_token_id = tokenizer.convert_tokens_to_ids(tokenizer.pad_token)
tokenizer.padding_side = 'left'

ds = load_dataset("timdettmers/openassistant-guanaco")

bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, torch_dtype=compute_dtype, trust_remote_code=True, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation
)

model = prepare_model_for_kbit_training(model)

peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


from trl import SFTConfig

training_arguments = SFTConfig(
        output_dir="./Phi-3_QLoRA",
        evaluation_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=64,
        #gradient_accumulation_steps=8,
        per_device_eval_batch_size=4,
        log_level="debug",
        save_strategy="epoch",
        logging_steps=100,
        learning_rate=1e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        eval_steps=100,
        num_train_epochs=3,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
)

trainer = SFTTrainer(
        model=model,
        train_dataset=ds['train'],
        eval_dataset=ds['test'],
        peft_config=peft_config,
        dataset_text_field="text",
        max_seq_length=512,
        tokenizer=tokenizer,
        args=training_arguments,
)

trainer.train()
```
Training results:
```
Step	Training Loss	Validation Loss
100	1.269000	1.282623
200	1.170900	1.269450
300	1.165900	1.263883
400	1.162900	1.262569
```