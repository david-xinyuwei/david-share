# How to make AI training faster

### Factors Affecting AI Training Time

In deep learning training, the calculation of training time involves multiple factors, including the number of epochs, global batch size, micro batch size, and the number of computing devices, among others. Below is a basic formula illustrating the relationship between these parameters (note that this is just a basic illustrative formula, mainly explaining proportional and inversely proportional relationships; actual training may require considering more factors):

![thumbnail image 2 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							How to make AI training faster 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613633i23E2C72E457C6514/image-size/medium?v=v2&px=400)

Among them—

- Epochs refer to the number of times the model processes the entire training dataset.
- Total Number of Samples is the total number of samples in the training dataset.
- Global Batch Size is the total number of data samples processed in each training iteration.
- Time per Step is the time required for each training iteration, which depends on hardware performance, model complexity, optimization algorithms, and other factors.
- Number of Devices is the number of computing devices used for training, such as the number of GPUs.

This formula provides a basic framework, but please note that the actual training time may be influenced by many other factors, including I/O speed, network latency (for distributed training), CPU-GPU communication speed, The Frequency of Hardware Failures During GPU Training, etc. Therefore, this formula can only serve as a rough estimate, and the actual training time may vary.

 

### Detailed explanations

The training time of a deep learning model is determined by multiple factors, including but not limited to the following:

- Number of Epochs: An epoch means that the model has processed the entire training dataset once. The more epochs, the more data the model needs to process, and thus the longer the training time.
- Global Batch Size: The global batch size is the total number of data samples processed in each training iteration. The larger the global batch size, the more data is processed in each iteration, which may reduce the number of iterations required per epoch, potentially shortening the total training time. However, if the global batch size is too large, it may lead to memory overflow.
- Micro Batch Size: The micro batch size refers to the number of data samples processed by each computing device in each training iteration. The larger the micro batch size, the more data each device processes per iteration, which may improve computational efficiency and thus shorten training time. However, if the micro batch size is too large, it may lead to memory overflow.
- Hardware Performance: The performance of the computing devices used (such as CPUs, GPUs) will also affect training time. More powerful devices can perform computations faster, thereby shortening training time.
- Model Complexity: The complexity of the model (such as the number of layers, number of parameters, etc.) will also affect training time. The more complex the model, the more computations are required, and thus the longer the training time.
- Optimization Algorithm: The optimization algorithm used (such as SGD, Adam, etc.) and hyperparameter settings like learning rate will also affect training time.
- Parallel Strategy: The use of parallel computing strategies such as data parallelism, model parallelism, etc., will also affect training time.


There are many factors that determine the length of training time, and they need to be considered comprehensively based on the specific training task and environment.

So, in this formula

![thumbnail image 3 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							How to make AI training faster 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613635i9153CF5AFE6A4BD4/image-size/medium?v=v2&px=400)

Time per step should be understood as primarily related to the computational power of the GPU."Time per Step," that is, the time required for each training step, is determined by multiple factors, including but not limited to the following:

- Hardware Performance: The performance of the computing devices used (such as CPUs, GPUs) will directly affect the speed of each training iteration. More powerful devices can perform computations faster.
- Model Complexity: The complexity of the model (such as the number of layers, number of parameters, etc.) will also affect the time for each training iteration. The more complex the model, the more computations are required.
- Optimization Algorithm: The optimization algorithm used (such as SGD, Adam, etc.) will also affect the time for each training iteration. Some optimization algorithms may require more complex computational steps to update the model parameters.
- Data type used in training：Different data types used in training have significant effect on time per step. Data types include FP32, FP/BF16, FP8, etc.

### Training steps

So, what determines the total training steps?"Total Training Steps" is determined by the number of training epochs and the number of steps per epoch. Specifically, it equals the number of epochs multiplied by the number of steps per epoch. This can be expressed with the following formula:

 

![thumbnail image 4 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							How to make AI training faster 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613636i2FCBE0BFD8517BD7/image-size/medium?v=v2&px=400)

####  

#### Global Batch Size

So, what determines the Global Batch Size?

 

![thumbnail image 5 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							How to make AI training faster 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613637i94F36A08D463CB64/image-size/medium?v=v2&px=400)

```applescript
global_batch_size = 
gradient_accumulation_steps 
* nnodes （node mumbers） 
* nproc_per_node （GPU in one node） 
* per_device_train_batch_si（micro bs size） 
```

Assume a scenario:

```applescript
batch_size = 10  # Batch size  
total_num = 1000  # Total number of training data  
```

When training one batch of data and updating the gradient once (gradient accumulation steps = 1):

 

```applescript
train_steps = total_num / batch_size = 1000 / 10 = 100  
```

 

This means there are 100 steps per epoch, and the gradient update steps are also 100.
When the memory is insufficient to support a batch size of 10, we can use gradient accumulation to reduce the size of each micro-batch. Suppose we set the gradient accumulation steps to 2:

 

```applescript
gradient_accumulation_steps = 2  
micro_batch_size = batch_size / gradient_accumulation_steps = 10 / 2 = 5  
```

 

This means that for each gradient update, we accumulate data from 2 micro-batches, with each micro-batch size being 5. This reduces memory pressure, but the data size per gradient update remains 10 data points.

**Result:**

- The number of training steps per epoch (train_steps) remains 100 because the total amount of data and the number of steps per epoch have not changed.
- The gradient update steps remain 100 because each gradient update accumulates data from 2 micro-batches.

It is important to note that when using gradient accumulation, each training step handles the accumulation of gradients from multiple micro-batches, which may slightly increase the computation time per step. Therefore, if memory is sufficient, it is better to increase the batch size to reduce the number of gradient accumulations. When memory is insufficient, gradient accumulation is an effective method.

The global batch size significantly impacts the training effectiveness of the model. Generally, a larger global batch size provides more accurate gradient estimates, aiding model convergence. However, it also increases memory pressure on each device. If memory resources are limited, using a large global batch size may not be feasible.

In such cases, gradient accumulation can be used. By training with a smaller micro-batch size on each device, we reduce memory pressure while maintaining a large global batch size for accurate gradient estimates. This allows training large models on limited hardware resources without sacrificing the global batch size.

In summary, gradient accumulation is a trade-off strategy to balance global batch size and training effectiveness when memory resources are limited.


So, if we look at these two formulas:

![thumbnail image 6 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							How to make AI training faster 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613638i4011964808232FA1/image-size/medium?v=v2&px=400)

 

![thumbnail image 7 of blog post titled  	 	 	  	 	 	 				 		 			 				 						 							How to make AI training faster 							 						 					 			 		 	 			 	 	 	 	 	 ](https://techcommunity.microsoft.com/t5/image/serverpage/image-id/613640i30E3B089A2A27200/image-size/medium?v=v2&px=400)

The larger the global batch size, the shorter the total training time, provided that there is no OOM (Out of Memory) and the GPU computational power is not fully utilized.

 

### The Relationship Between Data Parallelism and Batch Size

 This section essentially analyzes this formula:

```applescript
global_batch_size = 
gradient_accumulation_steps 
* nnodes （The number of nodes is, in effect, the PP） 
* nproc_per_node （The number of cards per node is, in effect, the TP） 
* per_device_train_batch_si（micro bs size） 
```

In distributed deep learning, data parallelism is a common strategy. The training data is split into multiple small batches and distributed to different computing nodes. Each node has a copy of the model and trains on its data subset, speeding up the training process.

At the end of each training step, the model weights of all nodes are synchronized using the AllReduce operation. AllReduce aggregates gradients from all nodes and broadcasts the result back, allowing each node to update its model parameters.

If training on a single device, AllReduce is not needed as all computations occur on the same device. However, in distributed training, especially with data parallelism, AllReduce or similar operations are necessary to synchronize model parameters across devices.

Many deep learning frameworks (e.g., PyTorch, TensorFlow) use NVIDIA's NCCL for communication across multiple GPUs. Each GPU trains on its data subset and synchronizes model weights using NCCL's AllReduce at the end of each step.

Although AllReduce is commonly used in data parallelism, other NCCL operations may be employed depending on the framework and strategy.

Data parallelism (DP) and micro batch size are interrelated. DP involves training on multiple devices, each processing a portion of the data. Micro batch size is the number of samples each device processes per iteration. With DP, the original batch size is split into micro batches across devices. Without DP or model parallelism (MP), micro batch size equals global batch size. With DP or MP, the global batch size is the sum of all micro batches.

DP can be applied on multiple devices within a single server or across multiple servers. Setting DP to 8 means training on 8 devices, either on the same server or distributed across servers.

Pipeline parallelism (PP) is a different strategy where different model parts run on different devices. Setting DP to 8 in PP means 8 devices process data in parallel at each pipeline stage.

In summary, DP and PP can be used simultaneously on devices within a single server or across multiple servers.