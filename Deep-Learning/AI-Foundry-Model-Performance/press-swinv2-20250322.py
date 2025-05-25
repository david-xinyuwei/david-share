#!/usr/bin/env python3  
# -- coding: utf-8 --  
  
import urllib.request  
import urllib.error  
import json  
import os  
import ssl  
import time  
import concurrent.futures  
import threading  
import sys  
  
try:  
    from transformers import AutoTokenizer  
except ImportError:  
    print("The transformers library is not installed, token count will be calculated using simple space splitting.")  
    AutoTokenizer = None  
  
# --------------------------- Global Variables ---------------------------  
  
# 1) 可以将此默认值更改为你的 microsoft-swinv2-base-patch4-window12-192-192-22k 部署端点  
API_URL = "https://aml-westus-1-nc24-a100.westus.inference.ml.azure.com/score"  
  
# 2) 在此处填入实际的 Key，或者在输入阶段改为手动输入  
API_KEY = "YOUR_API_KEY"  
  
HEADERS = {}  
  
# 此时仅保留第一张图片，供测试之用  
BASE_PROMPT = "What are in this image? Reply in 3000 tokens"  
IMAGE_URL1 = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"  
  
DEFAULT_TEMPERATURE = 0.7  
REQUEST_TIMEOUT = 90  
CONCURRENCY_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  
  
tokenizer = None  
  
# --------------------------- 线程安全打印 ---------------------------  
print_lock = threading.Lock()  
  
def safe_print(*args, **kwargs):  
    with print_lock:  
        print(*args, **kwargs)  
  
# --------------------------- Allow Self-Signed HTTPS Certificates ---------------------------  
def allow_self_signed_https(allowed: bool) -> None:  
    """  
    如果推理服务使用了自签名证书，需要忽略证书验证。  
    若使用的是正规证书，可将 allowed 设置为 False 或去掉此函数的调用。  
    """  
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):  
        ssl._create_default_https_context = ssl._create_unverified_context  
  
# --------------------------- Input Configuration ---------------------------  
def input_config():  
    global API_URL, API_KEY, HEADERS, tokenizer  
  
    url_in = input(f"Please enter the API service URL (default: {API_URL}): ").strip()  
    if url_in:  
        API_URL = url_in  
  
    key_in = input("Please enter the API Key (default is configured): ").strip()  
    if key_in:  
        API_KEY = key_in  
  
    model_name = input(  
        "Please enter the HuggingFace model name for loading the tokenizer (default: gpt2, leave blank to skip loading): "  
    ).strip()  
  
    if model_name:  
        if AutoTokenizer:  
            try:  
                tokenizer = AutoTokenizer.from_pretrained(model_name)  
                safe_print("Tokenizer loaded successfully:", model_name)  
            except Exception as e:  
                safe_print("Failed to load tokenizer. Error:", e)  
                tokenizer = None  
        else:  
            tokenizer = None  
    else:  
        if AutoTokenizer:  
            try:  
                tokenizer = AutoTokenizer.from_pretrained("gpt2")  
                safe_print("Default tokenizer gpt2 loaded successfully.")  
            except Exception as e:  
                safe_print("Failed to load default tokenizer. Error:", e)  
                tokenizer = None  
        else:  
            tokenizer = None  
  
    HEADERS = {  
        "Content-Type": "application/json",  
        "Accept": "application/json",  
        "Authorization": "Bearer " + API_KEY,  
    }  
  
# --------------------------- Send Single Request (Adapted for microsoft-swinv2) ---------------------------  
def send_vlm_request(temperature: float, desired_length: int, iteration: int) -> dict:  
    """  
    使用与 microsoft-swinv2-base-patch4-window12-192-22k 类似的调用方式做推理请求。  
    """  
    RETRY_COUNT = 3  
  
    for attempt in range(RETRY_COUNT):  
        try:  
            # 保留原有 full_prompt 逻辑以计算 token，但不会发送给该模型  
            full_prompt = BASE_PROMPT + f" Please answer using about {desired_length} tokens."  
  
            # 构造请求体：对于 microsoft-swinv2-base-patch4-window12-192-22k，只需传入一组图片 URL 列表  
            payload = {  
                "input_data": [  
                    IMAGE_URL1  
                ]  
            }  
            body = json.dumps(payload).encode("utf-8")  
            req = urllib.request.Request(API_URL, data=body, headers=HEADERS)  
  
            start_time = time.perf_counter()  
            response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)  
  
            first_chunk_time = None  
            chunks = []  
            chunk_size = 1024  
  
            # 按块读取，以计算首字节到达时间 (TTFT)  
            while True:  
                chunk = response.read(chunk_size)  
                if not chunk:  
                    break  
                if first_chunk_time is None and chunk.strip():  
                    first_chunk_time = time.perf_counter()  
                chunks.append(chunk)  
  
            end_time = time.perf_counter()  
            total_latency = end_time - start_time  
            ttft = (first_chunk_time - start_time) if first_chunk_time else total_latency  
  
            total_content = b"".join(chunks)  
            result_str = total_content.decode("utf-8", errors="ignore")  
  
            safe_print(f"\n[Iteration {iteration}] Model Completion:")  
            safe_print(result_str)  
            safe_print("----- End of Completion -----\n")  
  
            # 保留原有的 tokenizer 逻辑测 token 数（只是为了保持脚本一致性）  
            if tokenizer:  
                prompt_token_count = len(tokenizer.tokenize(full_prompt))  
                output_token_count = len(tokenizer.tokenize(result_str))  
            else:  
                prompt_token_count = len(full_prompt.split())  
                output_token_count = len(result_str.split())  
  
            throughput = output_token_count / total_latency if total_latency > 0 else float('inf')  
  
            safe_print(  
                f"Iteration {iteration}: Success | Desired tokens={desired_length} "  
                f"| Temp={temperature} | Latency={total_latency:.3f}s, TTFT={ttft:.3f}s, Throughput={throughput:.2f} tokens/s"  
            )  
  
            return {  
                "iteration": iteration,  
                "latency": total_latency,  
                "ttft": ttft,  
                "prompt_tokens": prompt_token_count,  
                "output_tokens": output_token_count,  
                "throughput": throughput,  
                "success": True,  
            }  
  
        except urllib.error.HTTPError as e:  
            if e.code == 429:  
                backoff_time = 2 ** attempt  
                safe_print(f"Iteration {iteration}: Attempt {attempt + 1} received 429 Too Many Requests, backing off for {backoff_time} seconds.")  
                time.sleep(backoff_time)  
                continue  
            else:  
                safe_print(f"Iteration {iteration}: HTTPError {e.code}: {e.reason}")  
                if attempt == RETRY_COUNT - 1:  
                    return {  
                        "iteration": iteration, "latency": None, "ttft": None,  
                        "prompt_tokens": 0, "output_tokens": 0, "throughput": 0, "success": False  
                    }  
                else:  
                    time.sleep(1)  
                    continue  
        except Exception as ex:  
            safe_print(f"Iteration {iteration}: Exception: {str(ex)}")  
            if attempt == RETRY_COUNT - 1:  
                return {  
                    "iteration": iteration, "latency": None, "ttft": None,  
                    "prompt_tokens": 0, "output_tokens": 0, "throughput": 0, "success": False  
                }  
            else:  
                time.sleep(1)  
                continue  
  
    # 如果三次重试都未成功，则标记为失败  
    return {  
        "iteration": iteration,  
        "latency": None,  
        "ttft": None,  
        "prompt_tokens": 0,  
        "output_tokens": 0,  
        "throughput": 0,  
        "success": False,  
    }  
  
# --------------------------- Load Testing Logic ---------------------------  
def run_load_test(concurrency: int, total_requests: int) -> None:  
    safe_print(f"\nStarting load test: Concurrency={concurrency}, Total Requests={total_requests}")  
    start_batch = time.time()  
    results = []  
    fail_count = 0  
  
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:  
        futures = []  
        for i in range(total_requests):  
            desired_length = 4096  
            temp = 1.0  
            futures.append(executor.submit(send_vlm_request, temp, desired_length, i + 1))  
  
        for future in concurrent.futures.as_completed(futures):  
            try:  
                res = future.result(timeout=REQUEST_TIMEOUT + 10)  
                results.append(res)  
            except Exception as e:  
                safe_print(f"Request error: {e}")  
                fail_count += 1  
  
    end_batch = time.time()  
    batch_duration = end_batch - start_batch  
  
    # 先按 iteration 排序，保证输出顺序清晰  
    results.sort(key=lambda x: x.get('iteration', 999999))  
  
    success_results = [r for r in results if r.get("success")]  
    success_count = len(success_results)  
    fail_count += len(results) - success_count  # 加上脚本内标记success=False的  
  
    safe_print("\nDetailed Results:")  
    for idx, r in enumerate(success_results):  
        safe_print(f"  Request {r['iteration']}:")  
        safe_print(f"    TTFT          : {r['ttft']:.3f} s")  
        safe_print(f"    Latency       : {r['latency']:.3f} s")  
        safe_print(f"    Throughput    : {r['throughput']:.2f} tokens/s")  
        safe_print(f"    Prompt tokens : {r['prompt_tokens']}, Output tokens: {r['output_tokens']}")  
  
    avg_ttft = (sum(r["ttft"] for r in success_results) / success_count) if success_count > 0 else float('nan')  
    avg_throughput = (sum(r["throughput"] for r in success_results) / success_count) if success_count > 0 else float('nan')  
    overall_throughput = sum(r["throughput"] for r in success_results)  
  
    safe_print(f"\nSummary for concurrency={concurrency}:")  
    safe_print(f"  Successful requests          : {success_count}")  
    safe_print(f"  Failed requests              : {fail_count}")  
    safe_print(f"  Average TTFT per request     : {avg_ttft:.3f} s")  
    safe_print(f"  Average throughput per req   : {avg_throughput:.2f} tokens/s")  
    safe_print(f"  Overall throughput (sum)     : {overall_throughput:.2f} tokens/s")  
    safe_print(f"  Batch duration (wall-clock)  : {batch_duration:.3f} s\n")  
  
# --------------------------- Main Function ---------------------------  
def main():  
    # Gather user inputs (optional if you want to hardcode)  
    input_config()  
  
    # Allow self-signed certificate in dev/test environment  
    allow_self_signed_https(True)  
  
    # Command line usage example: python script.py 10 3  # where 10 is total requests, 3 is concurrency  
    if len(sys.argv) == 3:  
        try:  
            total_requests = int(sys.argv[1])  
            concurrency = int(sys.argv[2])  
            run_load_test(concurrency, total_requests)  
        except Exception as e:  
            safe_print("Command-line arguments error, using default test method.", e)  
            for conc in CONCURRENCY_LEVELS:  
                run_load_test(conc, conc)  
    else:  
        # If no command line args, run with default concurrency levels  
        for conc in CONCURRENCY_LEVELS:  
            run_load_test(conc, conc)  
  
if __name__ == "__main__":  
    main() 