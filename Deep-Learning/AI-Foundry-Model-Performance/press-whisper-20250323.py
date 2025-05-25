#!/usr/bin/env python3  
# -- coding: utf-8 --  
  
import urllib.request  
import urllib.error  
import json  
import os  
import ssl  
import time  
import concurrent.futures  
import base64  
  
# --------------------------- Global Variables ---------------------------  
URL = None  
API_KEY = None  
HEADERS = None  
ENCODED_AUDIO = None  
REQUEST_TIMEOUT = 90  # Timeout for each request (in seconds)  
CONCURRENCY_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # Levels of concurrency for testing  
  
# --------------------------- Allow Self-Signed HTTPS Certificates ---------------------------  
def allow_self_signed_https(allowed: bool) -> None:  
    """If your inference service uses a self-signed certificate, you can ignore certificate validation."""  
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):  
        ssl._create_default_https_context = ssl._create_unverified_context  
  
# --------------------------- Input Configuration ---------------------------  
def input_config():  
    """Prompt the user to input:  
    - Whisper service URL  
    - API Key  
    - Local audio file path  
    """  
    global URL, API_KEY, HEADERS, ENCODED_AUDIO  
  
    URL = input("Please enter the Whisper service URL (e.g., https://xxx.inference.ml.azure.com/score): ").strip()  
    if not URL:  
        raise Exception("URL cannot be empty!")  
  
    API_KEY = input("Please enter the API Key: ").strip()  
    if not API_KEY:  
        raise Exception("API Key cannot be empty!")  
  
    audio_path = input("Please enter the local audio file path (e.g., /root/1.m4a): ").strip()  
    if not audio_path or not os.path.isfile(audio_path):  
        raise Exception("Invalid audio file path or file does not exist!")  
  
    # Read the audio file and encode it in base64  
    with open(audio_path, "rb") as f:  
        ENCODED_AUDIO = base64.b64encode(f.read()).decode("utf-8")  
  
    # Set request headers  
    HEADERS = {  
        "Content-Type": "application/json",  
        "Accept": "application/json",  
        "Authorization": "Bearer " + API_KEY,  
    }  
  
# --------------------------- Single Request (with Retry & 429 Backoff) ---------------------------  
def send_whisper_request(stream: bool) -> dict:  
    """Logic for calling the Whisper service, including:  
    - Up to 3 retries  
    - Exponential backoff for 429 responses  
    - Measure TTFT (time-to-first-byte) and total latency  
  
    Return example:  
    {  
        "latency": 1.23,  
        "ttft": 0.45,  
        "throughput": 12.34,  # Calculated as "output text token count / time taken"  
        "output": "<transcription text>",  
        "success": True  
    }  
    If failed, success = False, and other fields may be None or 0.  
    """  
    RETRY_COUNT = 3  
    for attempt in range(RETRY_COUNT):  
        try:  
            # Construct the payload required by Whisper  
            payload = {  
                "input_data": {  
                    # Note: Modify the language as needed  
                    "audio": [ENCODED_AUDIO],  
                    "language": ["en"]  
                }  
            }  
  
            body = json.dumps(payload).encode("utf-8")  
            req = urllib.request.Request(URL, data=body, headers=HEADERS)  
  
            start_time = time.perf_counter()  
            response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)  
  
            if stream:  
                # If the server supports chunked streaming, read in chunks  
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
                result_bytes = b"".join(chunks)  
                ttft = (first_chunk_time - start_time) if first_chunk_time else (end_time - start_time)  
                total_latency = end_time - start_time  
            else:  
                # Non-streaming: read all at once  
                result_bytes = response.read()  
                end_time = time.perf_counter()  
                total_latency = end_time - start_time  
                ttft = total_latency  
  
            # Parse the response  
            result_str = result_bytes.decode("utf-8", errors="ignore")  
            try:  
                # Assume the JSON structure is as follows:  
                # {  
                #   "output_data": {  
                #       "text": ["This is the transcription result..."]  
                #   }  
                # }  
                parsed_json = json.loads(result_str)  
                # Modify according to the actual field structure  
                output_text = parsed_json["output_data"]["text"][0]  
            except Exception:  
                # If not JSON or the structure is different, use the raw string  
                output_text = result_str  
  
            # Use simple whitespace tokenization to count output tokens  
            token_count = len(output_text.split())  
            throughput = token_count / total_latency if total_latency > 0 else 0.0  
  
            return {  
                "latency": total_latency,  
                "ttft": ttft,  
                "throughput": throughput,  
                "output": output_text,  
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
                        "throughput": 0,  
                        "output": None,  
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
                        "throughput": 0,  
                        "output": None,  
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
                    "throughput": 0,  
                    "output": None,  
                    "success": False,  
                }  
            else:  
                time.sleep(1)  
                continue  
  
# --------------------------- Concurrent Testing Function ---------------------------  
def run_whisper_load_test(stream: bool = False) -> None:  
    """Test the concurrency levels in CONCURRENCY_LEVELS and print the results."""  
    for concurrency in CONCURRENCY_LEVELS:  
        print(f"\nStarting test with concurrency level: {concurrency}")  
        start_time = time.time()  
        results = []  
        fail_count = 0  
  
        # Use a thread pool for concurrency  
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:  
            futures = [executor.submit(send_whisper_request, stream) for _ in range(concurrency)]  
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
  
        # Count failures (including script exceptions or success=False)  
        fail_count += sum(1 for r in results if not r or not r.get("success"))  
  
        # Print statistics for each successful request  
        for idx, r in enumerate(success_results):  
            print(f"  Request {idx + 1}:")  
            print(f"    Output       : {r['output']}")  
            print(f"    TTFT         : {r['ttft']:.3f} s")  
            print(f"    Latency      : {r['latency']:.3f} s")  
            print(f"    Throughput   : {r['throughput']:.2f} tokens/s")  
  
        # Calculate averages  
        avg_ttft = (sum(r["ttft"] for r in success_results) / success_count) if success_count > 0 else float('nan')  
        avg_throughput = (sum(r["throughput"] for r in success_results) / success_count) if success_count > 0 else float('nan')  
        overall_throughput = sum(r["throughput"] for r in success_results)  
  
        # Print summary  
        print(f"\n  Summary for concurrency level {concurrency}: ")  
        print(f"    Successful requests      : {success_count}")  
        print(f"    Failed requests          : {fail_count}")  
        print(f"    Average TTFT             : {avg_ttft:.3f} s")  
        print(f"    Average throughput       : {avg_throughput:.2f} tokens/s")  
        print(f"    Total throughput         : {overall_throughput:.2f} tokens/s")  
        print(f"    Total time (wall clock)  : {batch_duration:.3f} s")  
  
# --------------------------- Main Function ---------------------------  
def main():  
    # Set to True if using self-signed certificates; set to False for production  
    allow_self_signed_https(True)  
  
    # User input for URL, API Key, and audio file  
    input_config()  
  
    # Start load testing the Whisper service  
    run_whisper_load_test(stream=False)  
  
if __name__ == "__main__":  
    main() 