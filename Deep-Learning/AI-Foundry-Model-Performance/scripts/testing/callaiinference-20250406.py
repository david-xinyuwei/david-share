#!/usr/bin/env python3  
# -- coding: utf-8 --  
  
import time  
import concurrent.futures  
from azure.core.credentials import AzureKeyCredential  
from azure.ai.inference import ChatCompletionsClient  
from azure.ai.inference.models import SystemMessage, UserMessage  
  
# ==========[1. Configuration: Replace with your actual Azure resource info]==========  
# Prompt the user to input Azure configuration information  
ENDPOINT = input("Please enter the Azure AI endpoint URL, such as https://xinyu.services.ai.azure.com/models format: ").strip()  
AZURE_AI_KEY = input("Please enter the Azure AI key: ").strip()  
DEPLOYMENT_NAME = input("Please enter the deployment name: ").strip()  
  
REQUEST_TIMEOUT = 90  # Default timeout in seconds  
  
# Create a global ChatCompletionsClient to avoid repeated instantiation under concurrency  
client = ChatCompletionsClient(endpoint=ENDPOINT, credential=AzureKeyCredential(AZURE_AI_KEY))  
  
def get_prompt_by_length(length: int) -> str:  
    """Return a meaningful prompt based on the requested length."""  
    prompts = {  
        128: "Describe the significance of the Riemann Hypothesis in modern mathematics and its potential applications in number theory.",  
        256: "Explain the concept of black holes, their formation, and how they affect the surrounding space-time. Discuss their significance in understanding the universe and the role of Hawking radiation in studying them.",  
        512: "Write a brief essay on the history of artificial intelligence (AI), covering its origins, key milestones, and current advancements. Include a discussion on the ethical implications and future challenges of AI in society, particularly in areas like employment, privacy, and decision-making.",  
        1024: "Provide a detailed explanation of the process of photosynthesis in plants. Include the roles of chloroplasts, light absorption, and the Calvin cycle. Additionally, discuss how environmental factors such as light intensity, carbon dioxide concentration, and temperature affect the efficiency of photosynthesis. Conclude with the significance of photosynthesis for life on Earth.",  
        2048: "Draft a fictional story about a group of astronauts who discover an ancient alien civilization on a distant exoplanet. The story should describe their journey to the planet, their initial exploration, and their interaction with the remnants of the alien civilization. Include elements of mystery, suspense, and the philosophical implications of finding intelligent life beyond Earth. Highlight the challenges the astronauts face and how they overcome them, while leaving room for the reader's imagination to ponder the unanswered questions about the aliens' fate.",  
        4096: "Compose a comprehensive research article on the impact of climate change on global biodiversity. The article should begin with an introduction to climate change, its causes, and the mechanisms through which it affects ecosystems. Provide specific examples of species and habitats that are particularly vulnerable, and discuss the cascading effects on food webs and ecosystem services. Additionally, evaluate the role of human activities, such as deforestation and pollution, in exacerbating the problem. Conclude with potential solutions, including conservation efforts, policy changes, and technological innovations that could mitigate the impact of climate change on biodiversity.",  
    }  
    return prompts.get(length, "Default prompt for unknown lengths.")  # Default prompt if length is not in the dictionary  
  
def send_request(prompt_length: int, stream: bool):  
    """Send a single request to ChatCompletions and measure latency, TTFT, tokens, etc."""  
    RETRY_COUNT = 3  # Maximum retry attempts  
  
    for attempt in range(RETRY_COUNT):  
        try:  
            system_msg = SystemMessage(content="You are a helpful assistant.")  
            user_msg_text = get_prompt_by_length(prompt_length)  # Use the meaningful prompt based on length  
            start_time = time.time()  
  
            if stream:  
                # Stream mode: incremental token generation  
                response = client.complete(  
                    stream=True,  
                    messages=[system_msg, UserMessage(content=user_msg_text)],  
                    model=DEPLOYMENT_NAME,  
                )  
                token_times = []  # Record the time of each token arrival  
                first_token_time = None  
  
                for update in response:  
                    if update.choices:  
                        if first_token_time is None:  
                            first_token_time = time.time()  # Record time for first token  
                        token_times.append(time.time())  # Record each token's arrival time  
  
                end_time = time.time()  
                # Calculate TTFT (Time to First Token)  
                ttft = first_token_time - start_time if first_token_time else None  
                total_tokens = len(token_times)  
                throughput = total_tokens / (end_time - start_time) if total_tokens > 0 else 0  
            else:  
                # Non-stream mode: complete response in one go  
                response = client.complete(  
                    stream=False,  
                    messages=[system_msg, UserMessage(content=user_msg_text)],  
                    model=DEPLOYMENT_NAME,  
                )  
                end_time = time.time()  
                # Extract token usage from the response (if available)  
                usage = getattr(response, "usage", None)  
                total_tokens = usage.total_tokens if usage else 0  
                # In non-stream mode, TTFT is the total latency  
                ttft = end_time - start_time  
                throughput = total_tokens / (end_time - start_time) if total_tokens > 0 else 0  
  
            return {  
                "latency": end_time - start_time,  
                "ttft": ttft,  
                "tokens": total_tokens,  
                "throughput": throughput,  
                "success": True,  
            }  
        except Exception as e:  
            print(f"Attempt {attempt + 1} failed: {e}")  
            if attempt == RETRY_COUNT - 1:  
                return {  
                    "latency": None,  
                    "ttft": None,  
                    "tokens": 0,  
                    "throughput": 0,  
                    "success": False,  
                }  
  
def run_load_test(concurrency: int, total_requests: int, prompt_length: int, stream: bool):  
    """Perform total_requests calls at a given concurrency level and prompt_length.  
    Collect success count, fail count, average latency, average TTFT, and tokens/s.  
    Supports both stream and non-stream modes."""  
    results = []  
    fail_count = 0  
    start_batch_time = time.time()  
  
    try:  
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:  
            future_list = [executor.submit(send_request, prompt_length, stream) for _ in range(total_requests)]  
            for future in concurrent.futures.as_completed(future_list):  
                try:  
                    results.append(future.result(timeout=REQUEST_TIMEOUT))  
                except concurrent.futures.TimeoutError:  
                    print("Request timed out.")  
                    fail_count += 1  
                except Exception as e:  
                    print(f"Error during request: {e}")  
                    fail_count += 1  
    except KeyboardInterrupt:  
        print("Test interrupted by user.")  
        executor.shutdown(wait=False)  # Force shutdown threads  
        raise  
  
    end_batch_time = time.time()  
    batch_duration = end_batch_time - start_batch_time  
  
    # Calculate per-request metrics  
    success_results = [r for r in results if r["success"]]  
    success_count = len(success_results)  
  
    if success_count == 0:  
        print(f"=== Concurrency: {concurrency}, Prompt length: {prompt_length}, Total requests: {total_requests} ===")  
        print(f"  All requests failed or timed out. Fail count: {fail_count}")  
        return  
  
    avg_latency = sum(r["latency"] for r in success_results) / success_count  
    avg_ttft = sum(r["ttft"] for r in success_results) / success_count  
    avg_throughput = sum(r["throughput"] for r in success_results) / success_count  
    total_tokens = sum(r["tokens"] for r in success_results)  
    overall_throughput = total_tokens / batch_duration if batch_duration > 0 else 0  
  
    mode = "Stream" if stream else "Non-Stream"  
    print(f"=== {mode} Mode | Concurrency: {concurrency}, Prompt length: {prompt_length}, Total requests: {total_requests} ===")  
    print(f"  Success count: {success_count}, Fail count: {fail_count}")  
    print(f"  Average latency (s): {avg_latency:.3f}")  
    print(f"  Average TTFT (s): {avg_ttft:.3f}")  
    print(f"  Average token throughput (tokens/s): {avg_throughput:.2f}")  
    print(f"  Overall throughput (tokens/s): {overall_throughput:.2f}\n")  
  
def main():  
    """Main function: configure concurrency levels and prompt lengths to perform load testing. Adjust them as needed."""  
    # 提示用户输入 concurrency_levels，并用逗号分隔  
    concurrency_input = input("Please enter concurrency levels separated by commas (e.g. 1,2,3): ").strip()  
    # 将输入的字符串按逗号分隔，转换为 int 列表  
    concurrency_levels = [int(x.strip()) for x in concurrency_input.split(',')]  
  
    # 打印提示，方便用户确认  
    print(f"Received concurrency levels: {concurrency_levels}")  
  
    # 可根据需求调整不同长度的 prompt  
    prompt_lengths = [128, 256, 512, 1024, 2048, 4096]  
  
    # 在本示例中，自动根据 concurrency c 设置 total_requests = 2 * c  
    for c in concurrency_levels:  
        total_requests = 1 * c  
        for p_len in prompt_lengths:  
            print(f"\n>>> Testing Concurrency: {c}, Prompt Length: {p_len}, Total Requests: {total_requests} <<<")  
  
            # First, test non-stream mode  
            run_load_test(  
                concurrency=c,  
                total_requests=total_requests,  
                prompt_length=p_len,  
                stream=False,  # Non-stream mode  
            )  
  
            # Then, test stream mode  
            run_load_test(  
                concurrency=c,  
                total_requests=total_requests,  
                prompt_length=p_len,  
                stream=True,   # Stream mode  
            )  
  
if __name__ == "__main__":  
    main()