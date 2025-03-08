import time
import concurrent.futures
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage

# ========== [1. Configuration: Replace with your actual Azure resource info] ==========
AZURE_AI_KEY = "avw"
ENDPOINT = "https://ai*ai.azure.com/models"  # If you use Azure AI Inference, usually append /models
DEPLOYMENT_NAME = "DeepSeek-R1"  # e.g., "DeepSeek-R1" or "mistral-large"
REQUEST_TIMEOUT = 0  # Timeout in seconds for future.result()

# Create a global ChatCompletionsClient to avoid repeated instantiation under concurrency
client = ChatCompletionsClient(
    endpoint=ENDPOINT,
    credential=AzureKeyCredential(AZURE_AI_KEY)
)

def generate_prompt_content(length: int) -> str:
    """
    Generate a longer string for User Message based on a given character length.
    This simply repeats a base_text until reaching the desired length.
    """
    base_text = "Riemann's Conjecture is a fundamental unsolved problem in mathematics. "
    repeat_count = (length // len(base_text)) + 1
    combined = (base_text * repeat_count)[:length]
    return combined

def send_request(prompt_length: int):
    """
    Send a single request to ChatCompletions and measure latency, tokens, etc.
    If an exception occurs, it will be caught in the upper-level function.
    """
    system_msg = SystemMessage(content="You are a helpful assistant.")
    user_msg_text = (
        "Explain Riemann's conjecture in 1 paragraph. "
        "Then expand with more details: "
    ) + generate_prompt_content(prompt_length)

    start_time = time.time()
    response = client.complete(
        messages=[system_msg, UserMessage(content=user_msg_text)],
        model=DEPLOYMENT_NAME
    )
    end_time = time.time()

    usage = getattr(response, "usage", None)
    total_tokens = usage.total_tokens if usage else 0

    return {
        "latency": end_time - start_time,      # Overall request time (seconds)
        "ttft": end_time - start_time,         # No streaming => TTFT ~ total time
        "tokens": total_tokens,
        "success": True
    }

def run_load_test(concurrency: int, total_requests: int, prompt_length: int):
    """
    Perform total_requests calls at a given concurrency level and prompt_length.
    Collect success count, fail count, average latency, average TTFT, and tokens/s.
    """
    results = []
    fail_count = 0
    start_batch_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_list = []
        for _ in range(total_requests):
            future = executor.submit(send_request, prompt_length)
            future_list.append(future)

        for future in concurrent.futures.as_completed(future_list):
            try:
                result = future.result(timeout=REQUEST_TIMEOUT)
                results.append(result)
            except concurrent.futures.TimeoutError:
                fail_count += 1
            except Exception:
                fail_count += 1

    end_batch_time = time.time()
    batch_duration = end_batch_time - start_batch_time

    success_count = len(results)
    if success_count == 0:
        print(f"=== Concurrency: {concurrency}, Prompt length: {prompt_length}, Total requests: {total_requests} ===")
        print(f"  All requests failed or timed out. Fail count: {fail_count}")
        return

    avg_latency = sum(r["latency"] for r in results) / success_count
    avg_ttft = sum(r["ttft"] for r in results) / success_count
    total_tokens = sum(r["tokens"] for r in results)
    tokens_per_second = (total_tokens / batch_duration) if batch_duration > 0 else 0

    print(f"=== Concurrency: {concurrency}, Prompt length: {prompt_length}, Total requests: {total_requests} ===")
    print(f"  Success count: {success_count}, Fail count: {fail_count}")
    print(f"  Average latency (s): {avg_latency:.3f}")
    print(f"  Average TTFT (s): {avg_ttft:.3f} (No streaming => same as total duration)")
    print(f"  Total tokens: {total_tokens}, Throughput: {tokens_per_second:.2f} tokens/s\n")

def main():
    """
    Main function: configure different concurrency levels and prompt lengths
    to perform load testing. Adjust them as needed.
    """
    #concurrency_levels = [5, 100, 500, 1000]  # Extend as needed, e.g., [5, 100, 500, 1000, 4000]
    concurrency_levels = [300, 1000]  # Extend as needed, e.g., [5, 100, 500, 1000, 4000]
    #prompt_lengths = [100, 512, 1024, 2048, 4096]   # Different input lengths to observe impact
    prompt_lengths = [4096, 8192]   # Different input lengths to observe impact
    total_requests_each = 10                  # Number of requests per scenario

    for c in concurrency_levels:
        for p_len in prompt_lengths:
            run_load_test(
                concurrency=c,
                total_requests=total_requests_each,
                prompt_length=p_len
            )

if __name__ == "__main__":
    main()