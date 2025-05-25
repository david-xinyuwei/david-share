#!/usr/bin/env python3  
# -- coding: utf-8 --  
  
import urllib.request  
import urllib.error  
import json  
import os  
import ssl  
import time  
import concurrent.futures  
import sys  
  
try:  
    from transformers import AutoTokenizer  
except ImportError:  
    print("The transformers library is not installed, token count will be calculated using simple space splitting.")  
    AutoTokenizer = None  
  
# --------------------------- Global Variables ---------------------------  
API_URL = "https://custom-endpoint-1742021907.polandcentral.inference.ml.azure.com/score"  
API_KEY = "9Eo9xzYpxkY6KZOaSJT5QPeK9OaTBTW8SuMhz6yCfjPJ3yKS0PJeJQQJ99BCAAAAAAAAAAAAINFRAZML1W5R"  
HEADERS = {}  
  
BASE_PROMPT = "What are in these images? What is the difference between two images? Reply in 3000 tokens"  
  
IMAGE_URL1 = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"  
IMAGE_URL2 = "https://www.ilankelman.org/stopsigns/australia.jpg"  
  
DEFAULT_TEMPERATURE = 0.7  
REQUEST_TIMEOUT = 90 
CONCURRENCY_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  
tokenizer = None  
  
# --------------------------- Allow Self-Signed HTTPS Certificates ---------------------------  
def allow_self_signed_https(allowed: bool) -> None:  
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):  
        ssl._create_default_https_context = ssl._create_unverified_context  
  
# --------------------------- Input Configuration ---------------------------  
def input_config():  
    global API_URL, API_KEY, HEADERS, tokenizer  
  
    url_in = input(f"Please enter the API service URL (default: {API_URL}): ").strip()  
    if url_in:  
        API_URL = url_in  
  
    key_in = input(f"Please enter the API Key (default is configured): ").strip()  
    if key_in:  
        API_KEY = key_in  
  
    model_name = input("Please enter the HuggingFace model name for loading the tokenizer (default: gpt2, leave blank to skip loading): ").strip()  
    if model_name:  
        if AutoTokenizer:  
            try:  
                tokenizer = AutoTokenizer.from_pretrained(model_name)  
                print("Tokenizer loaded successfully:", model_name)  
            except Exception as e:  
                print("Failed to load tokenizer. Error:", e)  
                tokenizer = None  
        else:  
            tokenizer = None  
    else:  
        if AutoTokenizer:  
            try:  
                tokenizer = AutoTokenizer.from_pretrained("gpt2")  
                print("Default tokenizer gpt2 loaded successfully.")  
            except Exception as e:  
                print("Failed to load default tokenizer. Error:", e)  
                tokenizer = None  
        else:  
            tokenizer = None  
  
    HEADERS = {  
        "Content-Type": "application/json",  
        "Accept": "application/json",  
        "Authorization": "Bearer " + API_KEY,  
    }  
  
# --------------------------- Send Single VLM Request ---------------------------  
def send_vlm_request(temperature: float, desired_length: int, iteration: int) -> dict:  
    RETRY_COUNT = 3  
  
    for attempt in range(RETRY_COUNT):  
        try:  
            full_prompt = BASE_PROMPT + f" Please answer using about {desired_length} tokens."  
  
            payload = {  
                "input_data": {  
                    "input_string": [  
                        {  
                            "role": "user",  
                            "content": [  
                                {"type": "image_url", "image_url": {"url": IMAGE_URL1}},  
                                {"type": "image_url", "image_url": {"url": IMAGE_URL2}},  
                                {"type": "text", "text": full_prompt},  
                            ],  
                        }  
                    ],  
                },  
                "parameters": {"temperature": temperature, "max_new_tokens": 4096},  
            }  
  
            body = json.dumps(payload).encode("utf-8")  
            req = urllib.request.Request(API_URL, data=body, headers=HEADERS)  
  
            start_time = time.perf_counter()  
  
            response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)  
  
            first_chunk_time = None  
            chunks = []  
            chunk_size = 1024  
  
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
  
            # Token statistics  
            if tokenizer:  
                prompt_token_count = len(tokenizer.tokenize(full_prompt))  
                output_token_count = len(tokenizer.tokenize(result_str))  
            else:  
                prompt_token_count = len(full_prompt.split())  
                output_token_count = len(result_str.split())  
  
            throughput = output_token_count / total_latency if total_latency > 0 else float('inf')  
  
            print(f"Iteration {iteration}: Success | Desired tokens={desired_length} "  
                  f"| Temp={temperature} | Latency={total_latency:.3f}s, TTFT={ttft:.3f}s, Throughput={throughput:.2f} tokens/s")  
  
            return {  
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
                print(f"Iteration {iteration}: Attempt {attempt + 1} received 429 Too Many Requests, backing off for {backoff_time} seconds.")  
                time.sleep(backoff_time)  
                continue  
            else:  
                print(f"Iteration {iteration}: HTTPError {e.code}: {e.reason}")  
                if attempt == RETRY_COUNT - 1:  
                    return {"latency": None, "ttft": None, "prompt_tokens": 0, "output_tokens": 0, "throughput": 0, "success": False}  
                else:  
                    time.sleep(1)  
                    continue  
  
        except Exception as ex:  
            print(f"Iteration {iteration}: Exception: {str(ex)}")  
            if attempt == RETRY_COUNT - 1:  
                return {"latency": None, "ttft": None, "prompt_tokens": 0, "output_tokens": 0, "throughput": 0, "success": False}  
            else:  
                time.sleep(1)  
                continue  
  
    return {"latency": None, "ttft": None, "prompt_tokens": 0, "output_tokens": 0, "throughput": 0, "success": False}  
  
# --------------------------- Load Testing Logic ---------------------------  
def run_load_test(concurrency: int, total_requests: int) -> None:  
    print(f"\nStarting load test: Concurrency={concurrency}, Total Requests={total_requests}")  
    start_batch = time.time()  
    results = []  # Correct initialization  
    fail_count = 0  
  
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:  
        futures = []  
        for i in range(total_requests):  
            desired_length = 3000  # Fixed length is 1000  
            temp = 1.0  # Fixed temperature is 1.0  
            futures.append(executor.submit(send_vlm_request, temp, desired_length, i + 1))  
  
        for future in concurrent.futures.as_completed(futures):  
            try:  
                res = future.result(timeout=REQUEST_TIMEOUT + 10)  
                results.append(res)  
            except Exception as e:  
                print(f"Request error: {e}")  
                fail_count += 1  
  
    end_batch = time.time()  
    batch_duration = end_batch - start_batch  
  
    success_results = [r for r in results if r.get("success")]  
    success_count = len(success_results)  
  
    print("\nDetailed Results:")  
    for idx, r in enumerate(success_results):  
        print(f"  Request {idx + 1}:")  
        print(f"    TTFT          : {r['ttft']:.3f} s")  
        print(f"    Latency       : {r['latency']:.3f} s")  
        print(f"    Throughput    : {r['throughput']:.2f} tokens/s")  
        print(f"    Prompt tokens : {r['prompt_tokens']}, Output tokens: {r['output_tokens']}")  
  
    avg_ttft = (sum(r["ttft"] for r in success_results) / success_count) if success_count > 0 else float('nan')  
    avg_throughput = (sum(r["throughput"] for r in success_results) / success_count) if success_count > 0 else float('nan')  
    overall_throughput = sum(r["throughput"] for r in success_results)  
  
    print(f"\nSummary for concurrency={concurrency}:")  
    print(f"  Successful requests          : {success_count}")  
    print(f"  Failed requests              : {fail_count}")  
    print(f"  Average TTFT per request     : {avg_ttft:.3f} s")  
    print(f"  Average throughput per req   : {avg_throughput:.2f} tokens/s")  
    print(f"  Overall throughput (sum)     : {overall_throughput:.2f} tokens/s")  
    print(f"  Batch duration (wall-clock)  : {batch_duration:.3f} s\n")  
  
# --------------------------- Main Function ---------------------------  
def main():  
    input_config()  
    allow_self_signed_https(True)  
  
    if len(sys.argv) == 3:  
        try:  
            total_requests = int(sys.argv[1])  
            concurrency = int(sys.argv[2])  
            run_load_test(concurrency, total_requests)  
        except Exception as e:  
            print("Command-line arguments error, using default test method.", e)  
            for conc in CONCURRENCY_LEVELS:  
                run_load_test(conc, conc)  
    else:  
        for conc in CONCURRENCY_LEVELS:  
            run_load_test(conc, conc)  
  
if __name__ == "__main__":  
    main()     