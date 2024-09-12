# Easy-way-to-Understand-Training

## Overall Training process

### Obtain Activation Values:
Retrieve the input activation values for specific batches (e.g., 2 and 3) from the model. The batch number refers to the specific batch index in the dataset. The amount of data in each batch is determined by the batch size, which defines the number of data samples processed in one training iteration.
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
Delete unnecessary memory to optimize resource usage.
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
The bar chart in the diagram represents memory usage and batch processing at different time steps.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXMn02lYfyxBTsfdXibIbTv3nTnm5adPT88BG7cibncpbrVJn4Gf0XUGjZ1ft56zA9bYVJ7D1ebRt0Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Detailed validation

### Puzzle 0 - Standard Training

Write a standard (non-distributed) training loop that acts on all the batches and loads all the weights. It should just run forward, loss, backward, and update. Aim for the least amount of max memory used. 

* Target Time:  17 steps
* Target Memory: 2600000

Refer to：*https://github.com/srush/LLM-Training-Puzzles/tree/main*

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
```
out = basic(Model(layers=2, batches=4, rank=0, dist=Dist(1)))
draw_group(out.final_weights)
```