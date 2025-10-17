#!/usr/bin/env python3  
# -*- coding: utf-8 -*-  
  
import urllib.request  
import urllib.error  
import json  
import os  
import ssl  
import time  
import concurrent.futures  
import random  
  
try:  
    from transformers import AutoTokenizer  
except ImportError as e:  
    print("Please install the transformers library first. Error:", e)  
    exit(1)  
  
# --------------------------- Global Variables ---------------------------  
URL = None  
API_KEY = None  
HEADERS = None  
tokenizer = None  
REQUEST_TIMEOUT = 90  # Timeout for each individual request (in seconds)  
  
# --------------------------- Input Configuration ---------------------------  
def input_config():  
    """  
    Prompt the user to input the API service URL, the API Key,  
    and the HuggingFace model name for loading the tokenizer.  
    """  
    global URL, API_KEY, HEADERS, tokenizer  
  
    URL = input("Please enter the API service URL: ").strip()  
    if not URL:  
        raise Exception("URL cannot be empty!")  
  
    API_KEY = input("Please enter the API Key: ").strip()  
    if not API_KEY:  
        raise Exception("API Key cannot be empty!")  
  
    model_name = input("Please enter the model name for tokenizer loading: ").strip()  
    if not model_name:  
        raise Exception("Model name cannot be empty!")  
  
    try:  
        tokenizer = AutoTokenizer.from_pretrained(model_name)  
        print("Tokenizer loaded successfully:", model_name)  
    except Exception as e:  
        print("Failed to load tokenizer. Please check the model name or dependencies. Error:", e)  
        tokenizer = None  
  
    HEADERS = {  
        "Content-Type": "application/json",  
        "Accept": "application/json",  
        "Authorization": "Bearer " + API_KEY,  
    }  
  
# --------------------------- Allow Self-Signed HTTPS Certificates (if needed) ---------------------------  
def allow_self_signed_https(allowed: bool) -> None:  
    """  
    If your inference service uses a self-signed certificate, this function  
    allows skipping certificate verification.  
    """  
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):  
        ssl._create_default_https_context = ssl._create_unverified_context  
  
# --------------------------- Scenario Prompts ---------------------------  
scenario_prompts = {  
    "Text Generation": (  
        "Please craft a unique imaginative story that merges elements of hard "  
        "science fiction with epic fantasy, showcasing futuristic technology, "  
        "magical powers, and a conflict that highlights humanity’s resilience. "  
        "Incorporate deep character interactions, vivid settings spanning galaxies "  
        "and ancient realms, and a central theme exploring the intersection of myth "  
        "and innovation. Emphasize moral dilemmas, evolving relationships, and "  
        "surprising revelations that challenge preconceived notions about progress. "  
        "You must answer with exactly 500 tokens. Introduce imaginative technologies, "  
        "diverse magical traditions, and unexpected allies, weaving them into a "  
        "richly layered narrative that highlights tension between rational inquiry "  
        "and arcane mysticism. Ensure the resolution offers thought-provoking insights."  
    ),  
    "Question Answering": (  
        "Imagine this prompt represents a very long passage of approximately 2000 tokens, "  
        "potentially discussing advanced mathematical concepts, detailed historical events, "  
        "or intricate literary analyses. In a real application, you would insert the full text "  
        "here, ensuring it reaches the necessary length. After reading the entire text, "  
        "you are asked to provide a concise conclusion or answer to a specific question. "  
        "In your final response, you must synthesize the main ideas, highlight the crucial "  
        "evidence, and form a well-reasoned argument. Please note that you must answer with "  
        "approximately 500 tokens to fulfill this scenario."  
    ),  
    "Translation": (  
        "Here is a brief passage describing a serene lakeside scene, where gentle ripples "  
        "dance across the water under the golden glow of the late afternoon sun, and tall "  
        "reeds sway gracefully in the soft breeze, evoking a sense of tranquility. Birds "  
        "occasionally chirp in the surrounding trees, adding subtle melodies to this idyllic "  
        "environment. Please translate this passage into French. You must respond with "  
        "50–500 tokens."  
    ),  
    "Text Summarization": (  
        "Assume this is a placeholder representing an extensive document of approximately "  
        "3000 tokens, potentially covering a thorough explanation of a scientific process, "  
        "a historical timeline, or a policy report. The real content would be inserted here "  
        "in full. Your task is to distill the essential ideas, main findings, or critical "  
        "arguments into a concise summary. You must respond with around 200 tokens, focusing "  
        "on capturing the core message and most relevant details without excessive length."  
    ),  
    "Code Generation": (  
        "You are given a brief technical specification that outlines the requirements for "  
        "a Python application. The specification details the input format, core functionalities, "  
        "and expected behaviors, including data validation and error handling. You must write "  
        "the necessary Python code that meets these requirements. Your response should include "  
        "function definitions, docstrings, and any relevant documentation comments. Please "  
        "respond using approximately 1000 tokens to thoroughly address the specification."  
    ),  
    "Chatbot": (  
        "User: Hi there! I’m looking for some advice on how to stay motivated while learning "  
        "a new language. Specifically, I’ve been struggling with consistency in my study "  
        "routine, and I wonder if you have any practical tips or techniques for building a "  
        "daily habit. You must answer with 200 tokens."  
    ),  
    "Sentiment Analysis / Classification": (  
        "This text represents a lengthy user feedback of about 500 tokens, where the user "  
        "expresses mixed emotions about a recent product purchase. They mention both positive "  
        "aspects, such as reliable performance, and negative points, including delayed shipping "  
        "and lackluster customer service follow-up. Your task is to classify the overall sentiment "  
        "(e.g., Positive, Negative, or Neutral). You must respond using only 1–10 tokens."  
    ),  
    "Multi-turn Reasoning / Complex Tasks": (  
        "Envision a scenario that spans approximately 3000 tokens, containing intricate details "  
        "about a multi-step problem—potentially a lengthy math puzzle, a legal case requiring "  
        "extended analysis, or a multi-faceted project plan. The text poses various questions "  
        "and presents branching paths of logic. Your objective is to parse all the relevant "  
        "details, then methodically explain how to arrive at the correct conclusion or proposed "  
        "solution. Finally, you must respond with roughly 1000 tokens, illustrating your "  
        "comprehensive reasoning process."  
    ),  
}  
  
# --------------------------- Helper: Generate Prompt for a Given Scenario ---------------------------  
def generate_prompt(scenario: str) -> str:  
    return scenario_prompts.get(scenario, f"Generate a response for scenario: {scenario}")  
  
# --------------------------- Send Single Request to phi4 (Retry & 429 Backoff Included) ---------------------------  
def send_ph4_request_scenario(prompt: str, stream: bool) -> dict:  
    """  
    Single request logic for phi4, which includes retry (3 times) and exponential backoff for 429.  
    If all three attempts fail, it returns {"success": False} to record this request as a failure.  
    """  
    RETRY_COUNT = 3  
    for attempt in range(RETRY_COUNT):  
        try:  
            # Optionally count input tokens using the loaded tokenizer.  
            if tokenizer:  
                prompt_tokens_list = tokenizer.tokenize(prompt)  
                prompt_token_count = len(prompt_tokens_list)  
            else:  
                prompt_token_count = len(prompt.split())  
  
            # Example payload for phi4. Adjust to actual usage if needed.  
            payload = {  
                "input_data": {  
                    "input_string": [{"role": "user", "content": prompt}],  
                    "parameters": {  
                        "max_new_tokens": 4096  
                    }  
                }  
            }  
  
            body = json.dumps(payload).encode("utf-8")  
            req = urllib.request.Request(URL, data=body, headers=HEADERS)  
  
            start_time = time.perf_counter()  
            response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)  
  
            if stream:  
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
                total_content = b"".join(chunks)  
                result_str = total_content.decode("utf-8", errors="ignore")  
                ttft = (first_chunk_time - start_time) if first_chunk_time else (end_time - start_time)  
                total_latency = end_time - start_time  
            else:  
                result_bytes = response.read()  
                end_time = time.perf_counter()  
                result_str = result_bytes.decode("utf-8", errors="ignore")  
                total_latency = end_time - start_time  
                ttft = total_latency  
  
            if tokenizer:  
                output_tokens_list = tokenizer.tokenize(result_str)  
                output_token_count = len(output_tokens_list)  
            else:  
                output_token_count = len(result_str.split())  
  
            tokens_per_second = output_token_count / total_latency if total_latency > 0 else float('inf')  
  
            return {  
                "latency": total_latency,  
                "ttft": ttft,  
                "prompt_tokens": prompt_token_count,  
                "output_tokens": output_token_count,  
                "throughput": tokens_per_second,  
                "success": True,  
            }  
  
        except urllib.error.HTTPError as e:  
            if e.code == 429:  
                backoff_time = 2 ** attempt  
                print(f"Attempt {attempt + 1}: Received 429 Too Many Requests. Backing off for {backoff_time} seconds.")  
                time.sleep(backoff_time)  
                if attempt == RETRY_COUNT - 1:  
                    return {  
                        "latency": None,  
                        "ttft": None,  
                        "prompt_tokens": prompt_token_count if 'prompt_token_count' in locals() else 0,  
                        "output_tokens": 0,  
                        "throughput": 0,  
                        "success": False,  
                    }  
                else:  
                    continue  
            else:  
                print(f"Attempt {attempt + 1}: HTTPError {e.code}: {e.reason}")  
                if attempt == RETRY_COUNT - 1:  
                    return {  
                        "latency": None,  
                        "ttft": None,  
                        "prompt_tokens": prompt_token_count if 'prompt_token_count' in locals() else 0,  
                        "output_tokens": 0,  
                        "throughput": 0,  
                        "success": False,  
                    }  
                else:  
                    time.sleep(1)  
                    continue  
  
        except Exception as e:  
            print(f"Attempt {attempt + 1} failed: {e}")  
            if attempt == RETRY_COUNT - 1:  
                return {  
                    "latency": None,  
                    "ttft": None,  
                    "prompt_tokens": prompt_token_count if 'prompt_token_count' in locals() else 0,  
                    "output_tokens": 0,  
                    "throughput": 0,  
                    "success": False,  
                }  
            else:  
                time.sleep(1)  
                continue  
  
# --------------------------- Concurrency Levels ---------------------------  
CONCURRENCY_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  
  
# --------------------------- Run Test for Each Scenario ---------------------------  
def run_scenario_test(scenario: str, stream: bool = False) -> None:  
    for concurrency in CONCURRENCY_LEVELS:  
        prompt = generate_prompt(scenario)  
        print(f"\nScenario: {scenario}, Concurrency: {concurrency}")  
        start_time = time.time()  
        results = []  
        fail_count = 0  
  
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:  
            futures = [executor.submit(send_ph4_request_scenario, prompt, stream) for _ in range(concurrency)]  
            for future in concurrent.futures.as_completed(futures):  
                try:  
                    res = future.result(timeout=REQUEST_TIMEOUT + 10)  
                    results.append(res)  
                except Exception as e:  
                    print(f"Request error: {e}")  
                    fail_count += 1  
  
        end_time = time.time()  
        batch_duration = end_time - start_time  
  
        success_results = [r for r in results if r and r.get("success")]  
        success_count = len(success_results)  
  
        # Anything that is None or {"success": False} is considered a failure  
        fail_count += sum(1 for r in results if not r or not r.get("success"))  
  
        for idx, r in enumerate(success_results):  
            print(f"  Request {idx + 1}:")  
            print(f"    TTFT          : {r['ttft']:.3f} s")  
            print(f"    Latency       : {r['latency']:.3f} s")  
            print(f"    Throughput    : {r['throughput']:.2f} tokens/s")  
            print(f"    Prompt tokens : {r['prompt_tokens']}, Output tokens: {r['output_tokens']}")  
  
        avg_ttft = (sum(r["ttft"] for r in success_results) / success_count) if success_count > 0 else float('nan')  
        avg_throughput = (sum(r["throughput"] for r in success_results) / success_count) if success_count > 0 else float('nan')  
        overall_throughput = sum(r["throughput"] for r in success_results)  
  
        print(f"\n  Summary for concurrency {concurrency}:")  
        print(f"    Successful requests          : {success_count}")  
        print(f"    Failed requests              : {fail_count}")  
        print(f"    Average TTFT per request     : {avg_ttft:.3f} s")  
        print(f"    Average throughput per req   : {avg_throughput:.2f} tokens/s")  
        print(f"    Overall throughput (sum)     : {overall_throughput:.2f} tokens/s")  
        print(f"    Batch duration (wall-clock)  : {batch_duration:.3f} s")  
  
# --------------------------- Main Function ---------------------------  
def main():  
    # Prompt user inputs for URL, API Key, and HF model name  
    input_config()  
  
    # If using a self-signed certificate, set True; otherwise False  
    allow_self_signed_https(True)  
  
    # Run tests for each scenario in scenario_prompts  
    for scenario in scenario_prompts.keys():  
        run_scenario_test(scenario, stream=False)  
  
if __name__ == "__main__":  
    main()