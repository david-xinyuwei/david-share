# Easy-way-to-Understand-Training

## Overall Training process

### Obtain Activation Values:
Retrieve the input activation values for specific batches (e.g., 2 and 3) from the model. The batch number refers to the specific batch index in the dataset. The amount of data in each batch is determined by the batch size, which defines the number of data samples processed in one training iteration.

- Need Attention: In neural networks, the input layer typically does not involve an activation function. The "activation values" of the input layer are essentially the input data itself. In other words, the output of the input layer is directly the input data, without any nonlinear transformation.



The green section in the diagram represents the activation values of the input layer.
     

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3ianAS515q8yZmyU05EaVe2WRZ11CN5ZxPeELyaEczNGdhbKxByC8h2A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Load Weights:
Load weights for layers 0 and 1.
The green section in the diagram represents the loaded weights.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3MNVmHg8EWribqb1yZicYZH3Idw6GWnKK3uUjbONZc0TMiaic3vWysK78Ig/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Forward Propagation:
Use the weights to forward propagate the activation values through the network layers.
The yellow section in the diagram represents the activation values after forward propagation.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3OmrGLZTZMSrib7dPNMAic2AdAoY0ibNuroeAauUv7kcoHicekoCWYrN2CQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Plot Current Activation Values:
Plot the activation values currently in memory.
Different colors represent activation values from different layers.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3A7zOubsy7CXtIX1j5NVxqG8qRJObD2mo5AJ637tEDywjud8TMB444Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Calculate Loss:
Compute the loss at the final layer and convert it into gradient activation values.
The red section in the diagram represents the gradient activation values after loss calculation.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3vxu3To4LwgUX11b9R1X3US0ovAiaX4gO2wUHwOqwicgy8n3fswQwbQnA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Backward Propagation:
Perform backward propagation to calculate the gradients for each layer.
The yellow section in the diagram represents the gradients calculated during backward propagation.
![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3ra0RfopXfNUKeiaRRmLic9E6iceBEsFx906XYcian2hSQ328GUeATcNCpg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Memory Management:
Delete unnecessary memory to optimize resource usage.This step is equivalent to deleting the gradients that have already been computed for the intermediate layer.
The diagram shows changes in memory usage.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3BrJUEgnyib6J5asrWCS0SYz38FWtTcZOKPicgNcicthLAFIxDml69P1MA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Gradient Weights:
Plot the gradient weights, showing their corresponding batches.
The green and yellow sections in the diagram represent the gradient weights for different batches.
![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3UM1qwQHrqHr7ovgfmzc8zxAtWRhBB5KAes9v4mhfEQpwXhfPibQvFeA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Error Handling:
Handle errors when attempting to update weights. At this step, errors may occur if the required gradient information is incomplete or mismatched during the weight update. Specifically, the code might have only calculated gradients for batches 2 and 3, while updating weights requires complete gradient information for all batches. Missing gradients for certain batches will lead to an error. This error message informs the user that currently only gradients for batches 2 and 3 are available.
Display an error message indicating that only gradients for batches 2 and 3 are available.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv305tibS9ap2pmUeI9fPDZia5szDPMqj926v0FKQrrNp8h2wUDEFtWkWyw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Assume Gradients:
Simulate the required gradients to continue training.
The green section in the diagram represents the assumed gradients.
![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3FYtaMSNWt3KYK10ZN5XqiaHPSeG8IlicOuDUfZGiaCqf151gjsLricpzGQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


### Merge Gradients and Update Weights:
Merge gradients to obtain the complete gradient.
Update weights and check the results.
The yellow and green sections in the diagram represent the updated weights.
![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv37Xvafrh8GgQHficym9PPtln6KQsnVU6WnsHxGiatpCibD3xEiaXDQLDHkw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Final Results:
Display the results of the entire training process, including batches of forward and backward propagation and memory usage.
The bar chart in the diagram represents memory usage and batch processing at different time steps.The yellow block on the far right represents the update operation. This block typically follows the forward and backward passes, indicating the step where model weights are updated. The gray block represents communication or other operations, used to indicate data transfer or synchronization steps.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3nTnm5adPT88BG7cibncpbrVJn4Gf0XUGjZ1ft56zA9bYVJ7D1ebRt0Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


## Standard Training

Write a standard (non-distributed) training loop that acts on all the batches and loads all the weights. It should just run forward, loss, backward, and update. Aim for the least amount of max memory used. 

* Target Time:  17 steps
* Target Memory: 2600000

```
def basic(model: Model) -> Model:
    # Storage on device.
    weights, opt_states, activations, grad_activations, grad_weights = model.storage()

    # Load in the full weights
    for l in range(model.LAYERS):
        weights[l], opt_states[l] = model.load_weights(l)

    # Load the input layer activations
    activations[0] = model.get_activation(range(model.BATCHES))

    ## USER CODE
    # Forward
    for l in range(model.LAYERS):
        activations[l + 1] = model.forward(l, activations[l], weights[l])

    # Backward
    grad_activations[model.LAYERS] = model.loss(activations[model.LAYERS])
    del activations[model.LAYERS]
    
    for l in range(model.LAYERS - 1, -1, -1):
        grad_weights[l], grad_activations[l] = model.backward(
            l, activations[l], grad_activations[l + 1], weights[l]
        )
        del grad_activations[l + 1], activations[l]
    del grad_activations[0]
    assert len(grad_activations) == 0 and len(activations) ==0

    # Update
    for l in range(model.LAYERS):
        weights[l], opt_states[l] = model.update(l, grad_weights[l], weights[l], opt_states[l])
    ## END USER CODE
    
    for l in range(model.LAYERS):
        model.set_final_weight(l, weights[l])
    return model
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/1.png)
```
out = basic(Model(layers=2, batches=4, rank=0, dist=Dist(1)))
draw_group(out.final_weights)
```
```
Timesteps: 16.5 
Maximum Memory: 2621440.0 at GPU: 0 time: 8
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/2.png)


Code explanation：
This code implements a basic neural network training process, including forward propagation, backward propagation, and weight updates. Here are the main steps of the code:
- Storage Initialization: Retrieve stored weights, optimizer states, activations, gradient activations, and gradient weights from the model.
- Load Weights: For each layer, load the complete weights and optimizer states.
- Load Input Activations: Get the activations for the input layer.
- Forward Propagation: For each layer, compute the activations for the next layer.
- Backward Propagation: Calculate the loss and convert it to gradient activations for the last layer. Compute gradient weights and gradient activations layer by layer, and delete unnecessary activations and gradient activations.
- Update Weights: Use the calculated gradient weights to update the weights and optimizer states for each layer.
- Set Final Weights: Set the updated weights as the final weights of the model.
Return Model: Return the updated model.

Finally, draw_group(out.final_weights) is used to plot a graphical representation of the final weights.


## Gradient Accumulation

For this puzzle, the goal is to reduce max memory usage. To do so you are going to run on each batch individually instead of all together. 

Write a function with four parts. First run on batches {0} and then {1} etc. Sum the grad weights and then update.

```
def grad_accum(model: Model) -> Model:
    # Storage on device.
    weights, opt_states, activations, grad_activations, grad_weights = model.storage()

    # Load in the full weights
    for l in range(model.LAYERS):
        weights[l], opt_states[l] = model.load_weights(l)

    ## USER CODE
    for r in range(model.BATCHES):
        # Load the input layer activations
        activations[0, r] = model.get_activation([r])

        ## USER CODE
        # Forward
        for l in range(model.LAYERS):
            activations[l + 1, r] = model.forward(l, activations[l, r], weights[l])

        # Backward
        grad_activations[model.LAYERS, r] = model.loss(activations[model.LAYERS, r])
        del activations[model.LAYERS, r]
        
        for l in range(model.LAYERS - 1, -1, -1):
            grad_weights[l, r], grad_activations[l, r] = model.backward(
                l, activations[l, r], grad_activations[l + 1, r], weights[l]
            )
            if r == 0:
                grad_weights[l] = grad_weights[l, r]
            else:
                grad_weights[l] = grad_weights[l] + grad_weights[l, r]
            del grad_activations[l + 1, r], activations[l,r], grad_weights[l, r]
        del grad_activations[0, r]
        assert len(grad_activations) == 0 and len(activations) == 0

    # Update
    for l in range(model.LAYERS):
        weights[l], opt_states[l] = \
            model.update(l, 
                        grad_weights[l], weights[l], opt_states[l])

    ## END USER CODE
    for l in range(model.LAYERS):
        model.set_final_weight(l, weights[l])
    return model
```
```
out = grad_accum(Model(layers=2, batches=4, rank=0, dist=Dist(1)))
draw_group(out.final_weights)
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/3.png)

```
draw([out])
```
```
Timesteps: 16.5 
Maximum Memory: 2621440.0 at GPU: 0 time: 8
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/4.png)

## Different between Gradient Accumulation with Standard Training
### Standard Training
Processing All Batches at Once

Characteristics: All data is processed simultaneously in one large batch.
Implementation: There is no explicit batch loop; all data is processed together during forward and backward propagation.

Memory Requirement: Requires enough memory to handle all data at once.
Gradient Update: Weights are updated immediately after processing all data.
Processing Batches Individually (Gradient Accumulation)

### Gradient Accumulation
Characteristics: Each small batch is processed individually, and the computed gradients are accumulated.

Implementation: There is a batch loop, processing one small batch at a time.
Memory Requirement: Suitable for limited memory situations, as only a small portion of data is processed at a time.

Gradient Update: Weights are updated only after accumulating gradients from all small batches.
Key to Gradient Accumulation

The key to gradient accumulation is batch-wise processing and accumulating gradients, rather than processing all data at once. By accumulating gradients over multiple small batches, it simulates the effect of a larger batch size without requiring additional memory.

##  Communications: AllReduce
When working with multiple GPUs we need to have communication. 
The primary communication primitives for GPUs are implemented in NCCL. 

https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/usage/operations.html

We are not going to use these directly, but simulate them using Python and asyncio. 

The first operation is AllReduce. We will have 4 GPUs (ranks=4) and use them each to compute a batch of weight grads.
```
ranks = 4
weight_grads = [WeightGrad(0, 1, {i}, ranks) for i in range(ranks)]
weight_grads[0] + weight_grads[1] + weight_grads[2] + weight_grads[3]
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/5.png)
```
# Simple asynchronous function that calls allreduce to sum the weight grads at layer 0
async def myfunc(model: Model) -> WeightGrad:
    return await model.allreduce(weight_grads[model.rank], 0)
```
```
# This code uses asyncio to run the above function on 4 "GPUs" .
dist = Dist(ranks)
out_weight_grads = await asyncio.gather(*[
    myfunc(Model(layers=1, batches=1, rank=i, dist=dist))
    for i in range(ranks)])
out_weight_grads[0]
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/6.png)

Note: When running communication operations like AllReduce on a GPU, the communication happens in parallel to the computation on that GPU. That means the API for AllReduce does not block, and allows the model to continue running while waiting for this command to run. This means it is beneficial to run AllReduce (and other communication) as early as possible so that other compute can be run during the reduction. 

We will ignore this in these puzzles and represent communication as happening efficiently.

## Distributed Data Parallel
Write a function with four parts. First run on batches {0} and then {1} etc. Sum the grad weights and then update. The main benefit of this approach is compute efficiency over gradient accumulation.

* Total Steps: 5
* Total Memory: 1800000

```
async def ddp(model: Model) -> Model:
    # Storage on device.
    weights, opt_states, activations, grad_activations, grad_weights = model.storage()
    # Load all the activations
    model.activations[0] = model.get_activation([model.rank])

    ## USER CODE

    # Load in the full weights
    for l in range(model.LAYERS):
        weights[l], opt_states[l] = model.load_weights(l)

    # Forward
    for l in range(model.LAYERS):
        activations[l + 1] = model.forward(l, activations[l], weights[l])

    # Backward
    grad_activations[model.LAYERS] = model.loss(activations[model.LAYERS])

    for l in range(model.LAYERS - 1, -1, -1):
        grad_weights[l], grad_activations[l] = model.backward(
            l, activations[l], grad_activations[l + 1], weights[l]
        )
        del grad_activations[l + 1], activations[l]

    # Update
    for l in range(model.LAYERS):
        grad_weights[l] = await model.allreduce(grad_weights[l], l)
        weights[l], opt_states[l] = model.update(l, grad_weights[l], weights[l], opt_states[l])
        
    ## END USER CODE
    for l in range(model.LAYERS):
        model.set_final_weight(l, weights[l])
    return model
```
```
dist = Dist(ranks)
out = await asyncio.gather(*[
    ddp(Model(layers=2, batches=ranks, rank=i, dist=dist))
    for i in range(ranks)])
draw_group(out[0].final_weights)
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/7.png)
```
draw(out)
```
```
Timesteps: 5.1 
Maximum Memory: 1835008.0 at GPU: 0 time: 4
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/8.png)

## Different between DDP with Standard Training

### `ddp`

 This code runs on multiple GPUs , with each "rank" representing a GPU( rank=4). It uses `asyncio.gather` to process multiple model instances in parallel, with each instance running on a different GPU. The number of GPUs is determined by the value of `ranks`.

#### Distributed Processing

- **Multi-device Parallelism**: The code runs simultaneously on multiple devices, with each device handling a portion of the data.
- **Asynchronous Operations**: Utilizes `async` and `await` to allow multiple tasks to proceed concurrently, rather than waiting for each to complete sequentially.

#### Gradient Aggregation

- **Using `allreduce`**: Each device computes its own gradients, then uses the `allreduce` operation to sum the gradients from all devices. This ensures that the updated model is consistent across all devices.
- **Role of `allreduce`**: It sums the gradients from each device and distributes the result back to all devices, ensuring consistent model parameters across all devices.

#### Differences from the standard training

1. Processing Method
   - **First Segment**: Processes all data on a single device.
   - **Third Segment**: Processes data simultaneously on multiple devices.
2. Gradient Update
   - **First Segment**: Directly updates the model with computed gradients.
   - **Third Segment**: Aggregates gradients from all devices before updating the model.
3. Execution Result
   - **First Segment**: Displays an overall result.
   - **Third Segment**: Displays results for each device, reflecting distributed processing.

#### About `AllGather`

- **Function of `AllGather`**: Shares data among multiple devices. Each device sends its data to all other devices and receives data from them. Ultimately, each device has the complete data set from all devices.
- **Use Cases**: Commonly used when synchronizing complete data sets across all devices, such as collecting outputs or intermediate results in distributed training.
- **Not Used in the Third Code Segment**: Instead, `allreduce` is used for gradient aggregation.

## Communication: AllGather / Sharding

Our next primitive is AllGather. This allows us to communicate "shards" of an object stored on different GPUs to all the GPUs.

```
# Load only part of a weights.
model = Model(layers=2, batches=1, rank=0, dist=Dist(1))
weight, _ = model.load_weights(0, shard=0, total=4)
weight
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/9.png)

```
# Combine togegher two shards on one machine.
weights = [model.load_weights(0, shard=i, total=ranks)[0] for i in range(ranks)]
weights[0].combine(weights[2])
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/10.png)

```
# Use allgather to collect the shards from all machines.
async def mygather(model: Model) -> WeightGrad:
    # Allreduce sums together all the weight grads
    return await model.allgather(weights[model.rank], 0)

dist = Dist(ranks)
out_weights = await asyncio.gather(*[
    mygather(Model(layers=1, batches=1, rank=i, dist=dist))
    for i in range(ranks)])
out_weights[0]
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/11.png)

## Weight-Sharded Data Parallel

Run a model that shards each layer weight over all the machines. Reconstruct the layer weight at each layer using allgather. Finally update the weights on each machine using allreduce.

* Total Steps: 20
* Total Memory: 2800000

```
async def wsdp(model: Model) -> Model:
    # Storage on device.
    weights, opt_states, activations, grad_activations, grad_weights = model.storage()

    # Load all the activations
    model.activations[0] = model.get_activation([model.rank])

    # Load a shard of the weights for every layer. Load in the full weights
    for l in range(model.LAYERS):
        weights[l], opt_states[l] = model.load_weights(l, model.rank, model.RANKS) 

    ## USER CODE
    # Forward
    for l in range(model.LAYERS):        
        weights[l, 0] = await model.allgather(weights[l], l)
        activations[l + 1] = model.forward(l, activations[l], weights[l, 0])
        del weights[l, 0]

    # Backward
    grad_activations[model.LAYERS] = model.loss(activations[model.LAYERS])

    for l in range(model.LAYERS - 1, -1, -1):
        weights[l, 0] = await model.allgather(weights[l], l)
        grad_weights[l], grad_activations[l] = model.backward(
            l, activations[l], grad_activations[l + 1], weights[l, 0]
        )
        del grad_activations[l + 1], activations[l], weights[l, 0]

    # Update
    for l in range(model.LAYERS):
        grad_weights[l] = await model.allreduce(grad_weights[l], l)
        weights[l], opt_states[l] = model.update(l, grad_weights[l], weights[l], opt_states[l])

    ## END USER CODE
    for l in range(model.LAYERS):
        model.set_final_weight(l, weights[l])

    return model
```
```
dist = Dist(ranks)
out = await asyncio.gather(*[
    wsdp(Model(layers=6, batches=ranks, rank=i, dist=dist))
    for i in range(ranks)])
draw_group(out[1].final_weights)
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/12.png)

```
draw(out)
```
```
Timesteps: 19.90000000000001 
Maximum Memory: 2752512.0 at GPU: 0 time: 14.600000000000003
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/13.png)

## Different between Weight-Sharded Data Parallel with DDP

### DDP

- **Uses `allreduce`**: For aggregating gradients across multiple devices.
- **Data Processing**: Each device handles the complete weights.
- **Execution Result**: Displays results for each device, reflecting distributed processing.

### wsdp

- Uses `allgather` and `allreduce`
  - **`allgather`**: Collects weight shards for each layer during forward and backward passes.
  - **`allreduce`**: For aggregating gradients.
- **Data Processing**: Each device processes only a shard of the weights, then collects the complete weights using `allgather`.
- **Execution Result**: Shows more complex distributed processing, reflecting the process of weight sharding and aggregation.

### Key Differences

1. Communication Operations
   - **DDP**: Uses only `allreduce`.
   - **WSDP**: Combines `allgather` and `allreduce` to handle weight sharding.
2. Weight Processing
   - **DDP**: Each device processes complete weights.
   - **WSDP**: Each device processes a shard of the weights and collects complete weights using `allgather`.
3. Complexity
   - **WSDP**: More complex communication pattern, suitable for larger-scale distributed training.

### Summary


WSDP optimizes distributed training through weight sharding and `allgather` operations, making it suitable for handling larger models and data.

## Communication: Scatter-Reduce

Scatter across shards, Reduce across batches
```
grad_weight = WeightGrad(0, 1, batches={1}, total_batches=4, 
                         shards={1}, total=4)
grad_weight
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/14.png)
```
grad_weights = {i: WeightGrad(0, 1, batches={i}, total_batches=4, 
                         shards={0,1,2,3}, total=4) for i in range(4)}
grad_weights[2]
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/15.png)

```
async def scatterreduce(model: Model) -> WeightGrad:
    # Allreduce sums together all the weight grads
    return await model.scatterreduce(grad_weights[model.rank], 0)

dist = Dist(ranks)
out = await asyncio.gather(*[
    scatterreduce(Model(layers=1, batches=1, rank=i, dist=dist))
    for i in range(ranks)])
out[0]
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/16.png)

## Different between Scatter-Reduce and all-reduce

### All-Reduce

 

- **Purpose**: Aggregate data from all devices and distribute the result to each device.
- **Operation**: Each device contributes data, performs operations (e.g., sum, average), and then shares the result with all devices.
- **Use Case**: Commonly used in distributed training to synchronize gradients, ensuring model parameters are the same on each device.

### Scatter-Reduce

 

- **Purpose**: Distribute data to different devices, where each device performs its own computation.
- **Operation**: Data is distributed to each device for local computation.
- **Use Case**: Suitable for scenarios where data needs to be processed separately, such as in large-scale data processing where each device handles only its portion of the data.

### Key Differences

 

- Data Distribution

  :

  - **All-Reduce**: Results are shared with all devices, and everyone gets the same result.

  - **Scatter-Reduce**: Data is processed separately, and each device computes its own result, which may differ.

    In simple terms, All-Reduce is for tasks requiring global synchronization, where everyone shares the result, while Scatter-Reduce is for tasks needing separate processing. Choose different operations based on task requirements.

    All-Reduce and Scatter-Reduce can be combined in some complex distributed computing tasks. Here are some possible scenarios:

### Combined Use Scenarios

 

- Large-Scale Model Training

  :

  - **Scatter-Reduce**: Used to shard model parameters or data across different devices for local computation, reducing the burden on a single device.
  - **All-Reduce**: After local computation, it aggregates gradients from all devices to ensure consistency of model parameters.

- Distributed Data Processing

  :

  - **Scatter-Reduce**: Distributes large datasets to multiple devices for parallel processing.
  - **All-Reduce**: After processing, it aggregates results to obtain a global view or statistics.

### Benefits of Combined Use

 

- **Efficiency**: Reduces communication overhead through sharding and local computation.

- **Flexibility**: Allows dynamic adjustment of data distribution and result aggregation strategies based on task requirements.

  This combined use can provide higher efficiency and flexibility in tasks that require both large-scale data processing and global consistency.

## Fully-Sharded Data Parallel
Run a model that shards each layer weight over all the machines. Reconstruct the layer weight at each layer using allgather. Collect the gradients with scatter-reduce.

* Total Steps: 20
* Total Memory: 2300000
```
async def fsdp(model: Model) -> Model:
    # Storage on device.
    weights, opt_states, activations, grad_activations, grad_weights = model.storage()

    # Load all the activations
    model.activations[0] = model.get_activation([model.rank])

    # Load a shard of the weights for every layer. Load in the full weights
    for l in range(model.LAYERS):
        weights[l], opt_states[l] = model.load_weights(l, model.rank, model.RANKS) 

    ## USER CODE
    # Forward
    for l in range(model.LAYERS):        
        weights[l, 0] = await model.allgather(weights[l], l)
        activations[l + 1] = model.forward(l, activations[l], weights[l, 0])
        del weights[l, 0]

    # Backward
    grad_activations[model.LAYERS] = model.loss(activations[model.LAYERS])
    del(activations[model.LAYERS])
    
    for l in range(model.LAYERS - 1, -1, -1):
        weights[l, 0] = await model.allgather(weights[l], l)
        grad_weights[l], grad_activations[l] = model.backward(
            l, activations[l], grad_activations[l + 1], weights[l, 0]
        )
        grad_weights[l] = await model.scatterreduce(grad_weights[l], l)
        del grad_activations[l + 1], activations[l], weights[l, 0]

    # Update
    for l in range(model.LAYERS):
        weights[l], opt_states[l] = model.update(l, grad_weights[l], weights[l], opt_states[l])
        
    ## END USER CODE
    for l in range(model.LAYERS):
        model.set_final_weight(l, weights[l])
    return model
```
```
dist = Dist(ranks)
out = await asyncio.gather(*[
    fsdp(Model(layers=6, batches=ranks, rank=i, dist=dist))
    for i in range(ranks)])
draw_group(out[1].final_weights)
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/17.png)
```
draw(out)
```
```
Timesteps: 19.900000000000006 
Maximum Memory: 2359296.0 at GPU: 0 time: 9.1
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/18.png)

## Differences between Weight Sharding Data Parallelism (WSDP)

**Differences between Weight Sharding Data Parallelism (WSDP) and Fully Sharded Data Parallelism (FSDP):**

1. **Weight Sharding Data Parallelism (WSDP)**

   - **Weight Sharding**: The weights of each layer are sharded across different machines. Each machine only stores a portion of the weights.
   - **Allgather**: During forward and backward propagation, the allgather operation is used to collect the complete weights.
   - **Allreduce**: In the update phase, the allreduce operation is used to aggregate gradients from all machines and update the weights.
   - **Memory Usage**: Memory usage is efficient as each machine only stores a portion of the weights.

2. **Fully Sharded Data Parallelism (FSDP)**

   - **Weight Sharding**: Similar to WSDP, weights are also sharded.

   - **Allgather**: During forward and backward propagation, the allgather operation is used to collect the complete weights.

   - **Scatterreduce**: In backward propagation, the scatterreduce operation is used to reduce communication of gradients.

   - **Memory Usage**: Memory and communication efficiency are further optimized through scatterreduce.

     **Main Differences**

- Communication Operations in Update Phase

  :

  - WSDP uses allreduce, meaning all machines participate in gradient aggregation.
  - FSDP uses scatterreduce, which reduces communication by aggregating gradients only among necessary machines.

- Memory and Communication Efficiency

  :

  - FSDP optimizes communication efficiency in backward propagation through scatterreduce, potentially performing better in large-scale distributed training.

    **Summary**

- WSDP is more suitable for scenarios requiring simple implementation, with higher communication overhead.

- FSDP is more complex but may be more efficient in large-scale training, especially when communication becomes a bottleneck.

### Communication: Point-to-Point
An alternative approach to communication is to directly communicate specific information between GPUs. In our model, both GPUs talking to each other block and wait for the handoff. 
```
async def talk(model: Model) -> None:
    if model.rank == 0:
        await model.pass_to(1, "extra cheese")
        val = await model.receive()
        print(val)
    else:
        val = await model.receive()
        print(val)
        val = await model.pass_to(0, "pizza")

dist = Dist(2)
result = await asyncio.gather(*[
    talk(Model(layers=1, batches=1, rank=i, dist=dist))
    for i in range(2)])
```
```
extra cheese
pizza
```
## Pipeline Parallelism

Split the layer weights and optimizers equally between GPUs. Have each GPU handle only its layer. Pass the full set of batches for activations and grad_activations between layers using p2p communication. No need for any global communication.

* Total Steps: 66
* Total Memory: 3300000

```
async def pipeline(model: Model) -> Model:
    weights, opt_states, activations, grad_activations, grad_weights = model.storage()
    per_rank = model.LAYERS // model.RANKS
    my_layers = list([l + (model.rank * per_rank) for l in range(per_rank)])
    for l in my_layers:
        weights[l], opt_states[l] = model.load_weights(l)
    ## USER CODE

    if model.rank == 0:
        activations[0] = model.get_activation(range(model.BATCHES))
    else:
        activations[my_layers[0]] = await model.receive()

    # Forward
    for l in my_layers:
        activations[l + 1] = model.forward(l, activations[l], weights[l])

    # Backward
    if model.rank == model.RANKS - 1:
        grad_activations[model.LAYERS] = model.loss(
            activations[model.LAYERS]
        )
    else:
        await model.pass_to(model.rank + 1, activations[l + 1])
        grad_activations[l + 1] = await model.receive()

    for l in reversed(my_layers):
        grad_weights[l], grad_activations[l] = model.backward(
            l, activations[l], grad_activations[l + 1], model.weights[l]
        )
        del model.grad_activations[l + 1], model.activations[l]

    if model.rank != 0:
        await model.pass_to(model.rank - 1, grad_activations[l])

    # Update
    for l in my_layers:
        weights[l], opt_states[l] = model.update(l, grad_weights[l], weights[l], opt_states[l])

    ## END USER CODE
    for l in my_layers:
        model.set_final_weight(l, weights[l])
    return model
```
```
dist = Dist(ranks)
out = await asyncio.gather(*[
    pipeline(Model(layers=8, batches=ranks, rank=i, dist=dist))
    for i in range(ranks)])
draw_group(out[1].final_weights)
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/19.png)
```
draw(out)
```
```
Timesteps: 66.9 
Maximum Memory: 3145728.0 at GPU: 0 time: 58.40000000000001
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/20.png)

## Different between PP with WSDP/FSDP

### Pipeline Parallelism

 

- **Layer Assignment**: Each GPU is responsible for specific layers. This means each GPU only handles the forward and backward propagation for the layers it is assigned.
- **Weight Storage**: Each GPU only stores the weights and optimizer states for its assigned layers.
- **Data Transfer**: Activations and gradients are passed between layers using point-to-point communication. This method does not require global synchronization.

### WSDP and FSDP

 

- **Weight Sharding**: Weights are sharded across all machines, with each machine storing only a portion of the weights.
- **Global Communication**: Global communication operations (such as allgather and allreduce) are needed to synchronize weights and gradients.
- **Layer Processing**: Each machine may participate in processing multiple layers, requiring global synchronization at each step.

### Key Differences

 

- **Pipeline Parallelism** reduces the need for global communication by assigning different layers of the entire network to different GPUs. Each GPU only processes its assigned layers, and data is passed between layers via point-to-point communication.
- **WSDP and FSDP** require global communication at each step to ensure all machines have access to the complete weights and gradients.

### Summary

 

- **Pipeline Parallelism** is more like assigning different parts of the network to different GPUs, with each GPU handling a complete segment of computation.
- **WSDP and FSDP** involve sharding the weights of each layer across different machines, requiring global synchronization to complete the computation.

## GPipe Schedule
A major issue with the pipeline approach is that it causes a "bubble", i.e. time in the later layers waiting for the earlier layers to complete. An alternative approach is to split the batches smaller so you can pass them earlier. 

In this puzzle, you should run each batch by itself, and then pass. The graph should look similar as the one above but with a smaller bubble. 

* Total Steps: 33
* Total Memory: 4100000

```
async def gpipe(model: Model) -> Model:
    weights, opt_states, activations, grad_activations, grad_weights = model.storage()
    per_rank = model.LAYERS // model.RANKS
    my_layers = list([l + (model.rank * per_rank) for l in range(per_rank)])
    for l in my_layers:
        weights[l], opt_states[l] = model.load_weights(l)

    # USER CODE
    for mb in range(model.BATCHES):
        # Forward
        if model.rank == 0:
            activations[0, mb] = model.get_activation([mb])
        else:
            activations[my_layers[0], mb] = await model.receive()

        for l in my_layers:
            activations[l + 1, mb] = model.forward(l, activations[l, mb], weights[l])
        if model.rank != model.RANKS - 1:
            await model.pass_to(model.rank + 1, activations[l + 1, mb])

    for mb in range(model.BATCHES):
        # Backward
        if model.rank == model.RANKS - 1:
            grad_activations[model.LAYERS, mb] = model.loss(
                activations[model.LAYERS, mb]
            )
        else:
            grad_activations[my_layers[-1] + 1, mb] = await model.receive()

        for l in reversed(my_layers):
            grad_weights[l, mb], grad_activations[l, mb] = model.backward(
                l, activations[l, mb], grad_activations[l + 1, mb], weights[l]
            )
            del grad_activations[l + 1, mb], activations[l, mb]

        if model.rank != 0:
            await model.pass_to(model.rank - 1, grad_activations[l, mb])

    # Update
    for l in reversed(my_layers):
        for mb in range(model.BATCHES):
            if mb != 0:
                grad_weights[l] = grad_weights[l] + grad_weights[l, mb]
            else: 
                grad_weights[l] = grad_weights[l, 0]
            del grad_weights[l, mb]
        weights[l], opt_states[l] = model.update(l, grad_weights[l], weights[l], opt_states[l])

    ## END USER CODE
    for l in my_layers:
        model.set_final_weight(l, weights[l])

    return model
```
```
dist = Dist(ranks)
out = await asyncio.gather(*[
    gpipe(Model(layers=8, batches=ranks, rank=i, dist=dist))
    for i in range(ranks)])
draw_group(out[1].final_weights)
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/21.png)
```
draw(out)
```
```
Timesteps: 33.29999999999999
Maximum Memory: 4194304.0 at GPU: 1 time: 30.39999999999999
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/22.png)

## GPipe vs. Pipeline Parallelism

**GPipe** is an enhancement of pipeline parallelism designed to address the "bubble" issue, where later layers wait for earlier layers to complete. Here's how it differs:

1. Batch Splitting

   :

   - **GPipe** splits batches into smaller micro-batches, allowing them to be processed and passed earlier. This reduces idle time and improves efficiency.
   - **Pipeline Parallelism** processes larger batches, which can lead to idle time (bubbles) as layers wait for data.

2. Communication

   :

   - **GPipe** uses point-to-point communication for each micro-batch, allowing for more continuous data flow between layers.
   - **Pipeline Parallelism** may have more pronounced waiting periods between layers due to larger batch sizes.

3. Efficiency

   :

   - **GPipe** aims to minimize the bubble effect by overlapping computation and communication, leading to better utilization of resources.
   - **Pipeline Parallelism** might not fully utilize resources due to the bubble effect.

4. Implementation Complexity

   :

   - **GPipe** requires managing multiple micro-batches and ensuring correct synchronization, which can add complexity.
   - **Pipeline Parallelism** is simpler but may not be as efficient in terms of resource utilization.

### Summary

 

- **GPipe** improves upon traditional pipeline parallelism by reducing idle time through micro-batch processing, leading to more efficient use of computational resources.
- It requires careful management of micro-batches and synchronization but can significantly enhance performance in deep networks.

## Pipeline + FSDP

As a last exercise, we can put everything together. Here we are going to run a combination of pipeline parallelism while also sharding our weight between 16 different machines. Here the model only has 4 layers, so we will assign 4 GPUs to each layer in the pipeline parallel approach. 

This example requires combining both collective communication and p2p communication effectively. 

* Total Steps: 15
* Total Memory: 1000000

```
async def pipeline_fsdp(model: Model) -> Model:
    weights, opt_states, activations, grad_activations, grad_weights = model.storage()
    per_rank = model.LAYERS // (model.RANKS // 4)
    my_layers = list([l + ((model.rank % 4)  * per_rank) for l in range(per_rank)])
    for l in range(model.LAYERS):
        weights[l, 0], opt_states[l, 0] = model.load_weights(l, model.rank, model.RANKS)
    def empty_grad(l):
        return model.fake_grad(l, [])
    ## USER CODE
    # Forward
    for l in range(model.LAYERS):        
        if l == my_layers[0]:
            if model.rank % 4 == 0:
                activations[0] = model.get_activation([model.rank // 4])
            else:
                activations[l] = await model.receive()
    
        weights[l] = await model.allgather(weights[l, 0], l)
        if l in my_layers:
            activations[l + 1] = model.forward(l, activations[l], weights[l])
        del weights[l]
        if l == my_layers[-1]:
            if model.rank % 4 == 3 :
                grad_activations[model.LAYERS] = model.loss(
                    activations[model.LAYERS]
                )
            else:
                await model.pass_to(model.rank + 1, activations[l + 1])
    # Backward

    for l in reversed(range(model.LAYERS)):
        if l == my_layers[-1]:
            if model.rank % 4 != 3:
                grad_activations[l + 1] = await model.receive()
    
        weights[l] = await model.allgather(weights[l, 0], l)
        if l in my_layers:
            grad_weights[l], grad_activations[l] = model.backward(
                l, activations[l], grad_activations[l + 1], model.weights[l]
            )
            del grad_activations[l + 1], activations[l]
            grad_weights[l] = await model.scatterreduce(grad_weights[l], l)
        else:
            grad_weights[l] = await model.scatterreduce(empty_grad(l), l)
        del weights[l]

        if model.rank % 4 != 0 and l == my_layers[0]:
            await model.pass_to(model.rank - 1, grad_activations[l])
    for l in range(model.LAYERS):
        weights[l], opt_states[l] = model.update(l, grad_weights[l], weights[l, 0], opt_states[l, 0])

    # END USER CODE
    for l in range(model.LAYERS):
        model.set_final_weight(l, weights[l])
    # Update
    return model
```
```
dist = Dist(16)
out = await asyncio.gather(*[
    pipeline_fsdp(Model(layers=4, batches=ranks, rank=i, dist=dist))
    for i in range(16)])
```

```
Model.check(out)
chalk.set_svg_height(1000)
chalk.set_svg_draw_height(1000) 

draw(out)
```
```
Correct!
Timesteps: 15.5 
Maximum Memory: 966656.0 at GPU: 0 time: 13.7
```
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/23.png)

## Pipeline FSDP vs. Previous Approaches

 
**Pipeline FSDP** combines pipeline parallelism with fully sharded data parallelism (FSDP), utilizing both collective and point-to-point communication. Here are the differences from previous approaches:

- **Layer and Weight Distribution**: Pipeline FSDP assigns each layer to 4 GPUs and distributes the model across 16 machines. Each layer is handled by a group of GPUs, and weights are sharded among them. Previous approaches either focused on weight sharding (WSDP, FSDP) or layer distribution (Pipeline, GPipe), but not both simultaneously.
- **Communication**: Pipeline FSDP uses a combination of collective communication (such as allgather, scatterreduce) for weight synchronization and point-to-point communication for passing activations and gradients between layers. Previous approaches typically relied on either collective or point-to-point communication, not both.
- **Efficiency**: Pipeline FSDP optimizes computation and communication by effectively utilizing both types of parallelism, reducing idle time and improving resource utilization. Previous approaches might face limitations in communication overhead or resource utilization due to focusing on a single parallelism strategy.
- **Complexity**: Pipeline FSDP is more complex to implement, requiring careful coordination of both sharding and pipeline strategies. Previous approaches are simpler but may not achieve the same level of efficiency in large-scale distributed settings.

### Summary


Pipeline FSDP effectively combines the advantages of pipeline and sharded data parallelism, aiming for high efficiency and scalability. It requires managing both types of communication and synchronization, making it more complex but potentially more powerful in large-scale training scenarios.

## When does it make sense to combine?

There is not currently a one size fits all approach for distributed training. The right choice will depend on the constants such as batch size, memory per GPU, communication overhead, implementation complexity, model size, and specifics of architecture. 

As an example  of what's left to explore, this last method Pipeline + FSDP is often not a great choice due to the complexities of communication speed. And in fact GPipe + FSDP also gets you into a bad place. The paper [Breadth First Pipeline Parallelism](https://arxiv.org/pdf/2211.05953.pdf) proposes instead a combination of pipeline scheduling and communication. Here's what it looks like. 
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Easy-way-to-Understand-Training/images/24.png)

## Refer to
*https://github.com/srush/Transformer-Puzzles.git*