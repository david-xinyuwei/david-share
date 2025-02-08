# DeepSeek on Azure

**Methods for Deploying DeepSeek on Microsoft Platforms:**

- **Azure AI Foundry**   

- **Azure GPU VM**    

- - ND H100 × 2    
  - ND H200 × 1    
  - ND MI300X × 1  

  

***Please click below pictures to see my demo video on Youtube*** about deploy and do inference test on ND MI300X:
[![DSonAMDMI300X-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/R2ug8BmQB6Y)



## Deployment steps

**On NVIDIA H200**

Refer to *https://datacrunch.io/blog/deploy-deepseek-r1-on-8x-nvidia-h200*

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/DeepSeek-R1-on-Azure/images/1.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/DeepSeek-R1-on-Azure/images/2.png)

Refer to *https://blogs.nvidia.com/blog/deepseek-r1-nim-microservice/*

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/DeepSeek-R1-on-Azure/images/3.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/DeepSeek-R1-on-Azure/images/4.png)



**On AMD MI300X**

Refer to: *https://techcommunity.microsoft.com/blog/azurehighperformancecomputingblog/running-deepseek-r1-on-a-single-ndv5-mi300x-vm/4372726*

Run container on MI300X VM:

```
docker run --device=/dev/kfd --device=/dev/dri --security-opt seccomp=unconfined --cap-add=SYS_PTRACE --group-add video --privileged --shm-size 32g --ipc=host -p 30000:30000 -v /mnt/resource_nvme:/mnt/resource_nvme -e HF_HOME=/mnt/resource_nvme/hf_cache -e HSA_NO_SCRATCH_RECLAIM=1 lmsysorg/sglang:v0.4.2-rocm620 python3 -m sglang.launch_server --model deepseek-ai/DeepSeek-R1 --tp 8 trust-remote-code --host 0.0.0.0
```

The DeepSeek Will take some time to load:

```
[2025-02-07 12:25:38 TP3] max_total_num_tokens=1061980, chunked_prefill_size=8192, max_prefill_tokens=16384, max_running_requests=3319, context_len=163840
[2025-02-07 12:25:38 TP7] max_total_num_tokens=1061980, chunked_prefill_size=8192, max_prefill_tokens=16384, max_running_requests=3319, context_len=163840
[2025-02-07 12:25:38] INFO:     Started server process [1]
[2025-02-07 12:25:38] INFO:     Waiting for application startup.
[2025-02-07 12:25:38] INFO:     Application startup complete.
[2025-02-07 12:25:38] INFO:     Uvicorn running on http://0.0.0.0:30000 (Press CTRL+C to quit)
[2025-02-07 12:25:39] INFO:     127.0.0.1:35626 - "GET /get_model_info HTTP/1.1" 200 OK
```

Run test python programm:

```
root@mi300-hpcimage:~# cat xinyuwei.py 
import asyncio  
import aiohttp  
import time  
import json  
  
# Configure the requests  
url = 'http://localhost:30000/generate'  
headers = {'Content-Type': 'application/json'}  
  
# List of prompts (including some math problems)  
prompts = [  
    "Suppose you are participating in a game show, and you have three doors to choose from: behind one door is a gold bar, behind another door is rotten vegetables. You have chosen one door, for example, door number 1. The host asks you: Do you want to choose door number 2? Which door choice would give you the greatest advantage now?",  
    "Solve the equation: What is x if 2x + 3 = 15?",  
    "Explain the Pythagorean theorem and its applications.",  
    "Calculate the derivative of the function f(x) = x^2 + 3x + 5.",  
    "What is the integral of sin(x) dx from 0 to π?",  
    "If a car travels at a constant speed of 60 miles per hour, how long will it take to cover a distance of 180 miles?",  
    "Describe Newton's second law of motion and provide an example.",  
    "What are the differences between renewable and non-renewable energy sources?",  
    "Explain the concept of photosynthesis in plants.",  
    "Calculate the sum of all even numbers between 1 and 100."  
]  
  
# Function to send a request and process the response asynchronously  
async def send_request(semaphore, session, prompt, index):  
    async with semaphore:  
        start_time = time.time()  
        data = {  
            "text": prompt,  
            "sampling_params": {  
                "max_new_tokens": 512,  # Adjust as necessary  
                "temperature": 0.6  
            }  
        }  
        try:  
            # Print debug message when starting request  
            print(f"Prompt {index+1} started at {time.strftime('%X')}")  
  
            async with session.post(url, headers=headers, json=data) as response:  
                response_json = await response.json()  
                response_text = response_json.get('text', '')  
                # Calculate the number of generated characters  
                num_chars = len(response_text)  
                # Estimate tokens for English by splitting into words  
                num_tokens = len(response_text.split())  
                elapsed_time = time.time() - start_time  
                print(f"Prompt {index+1} processed in {elapsed_time:.2f} seconds")  
                return {  
                    'prompt': prompt,  
                    'response_text': response_text,  
                    'num_chars': num_chars,  
                    'num_tokens': num_tokens,  
                    'elapsed_time': elapsed_time  
                }  
        except Exception as e:  
            print(f"Error processing prompt {index+1}: {e}")  
            return {  
                'prompt': prompt,  
                'response_text': '',  
                'num_chars': 0,  
                'num_tokens': 0,  
                'elapsed_time': time.time() - start_time  
            }  
  
async def main():  
    # Record the start time  
    overall_start_time = time.time()  
    semaphore = asyncio.Semaphore(5)  # Limit concurrency to 5  
  
    # Create a client session  
    async with aiohttp.ClientSession() as session:  
        tasks = []  
        for index, prompt in enumerate(prompts):  
            # Schedule the task to run concurrently  
            task = asyncio.create_task(send_request(semaphore, session, prompt, index))  
            tasks.append(task)  
  
        # Execute tasks concurrently and collect results  
        results = await asyncio.gather(*tasks)  
  
    # Record the total elapsed time  
    total_elapsed_time = time.time() - overall_start_time  
  
    # Calculate total tokens and tokens per second  
    total_tokens = sum(result['num_tokens'] for result in results)  
    tokens_per_second = total_tokens / total_elapsed_time if total_elapsed_time > 0 else 0  
  
    # Output the results  
    print(f"\nExecution time: {total_elapsed_time:.2f} seconds")  
    print(f"Total number of generated tokens: {total_tokens}")  
    print(f"Tokens generated per second: {tokens_per_second:.2f}")  
  
    # Save all generated texts to a file  
    with open("generated_texts.txt", "w", encoding="utf-8") as f:  
        for i, result in enumerate(results):  
            f.write(f"--- Prompt {i+1} ---\n")  
            f.write(f"Question: {result['prompt']}\n")  
            f.write("Response:\n")  
            f.write(result['response_text'] + "\n\n")  
  
    print("\nAll generated texts have been saved to generated_texts.txt.")  
  
# Run the main function  
if __name__ == "__main__":  
    asyncio.run(main())
```



**After model is loaded before inference**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/DeepSeek-R1-on-Azure/images/5.png)

**During Inference**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/DeepSeek-R1-on-Azure/images/6.png)



## **Phi-4 14B Distillation** **Supervied** **fine-tuning**

*https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/SLM-DeepSeek-R1*