import os  
import json  
import ssl  
import requests  
import threading  
import argparse  
import csv  
import random  
from time import time, sleep  
  
# Allow self-signed HTTPS certificates (if required)  
def allowSelfSignedHttps(allowed):  
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):  
        ssl._create_default_https_context = ssl._create_unverified_context  
  
allowSelfSignedHttps(True)  
  
# Function to invoke the endpoint for a single request with retry mechanism and jitter  
def invoke_endpoint(url, api_key, input_string, max_new_tokens, results_list, lock, max_retries=5, initial_delay=1, max_delay=10):  
    headers = {  
        'Content-Type': 'application/json',  
        'Authorization': f'Bearer {api_key}'  
    }  
    data = {  
        "input_data": {  
            "input_string": input_string,  
            "parameters": {  
                "temperature": 0.7,  
                "top_p": 1,  
                "max_new_tokens": max_new_tokens  
            }  
        }  
    }  
    retries = 0  
    delay = initial_delay  
  
    while retries <= max_retries:  
        try:  
            start_time = time()  
            response = requests.post(url, json=data, headers=headers, timeout=60)  
            latency = time() - start_time  # Total latency  
            if response.status_code == 200:  
                result = response.json()  
                first_token_time = time()  # Assuming we get the full response at once  
                ttft = first_token_time - start_time  
                output_content = result.get('output', '')  
                output_tokens = len(output_content.split())  
                with lock:  
                    results_list.append({  
                        "success": True,  
                        "latency": latency,  
                        "ttft": ttft,  
                        "output_tokens": output_tokens  
                    })  
                return  
            elif response.status_code == 429:  
                retries += 1  
                if retries > max_retries:  
                    with lock:  
                        results_list.append({  
                            "success": False,  
                            "status_code": response.status_code,  
                            "error": response.reason  
                        })  
                    return  
                else:  
                    retry_after = response.headers.get('Retry-After')  
                    if retry_after:  
                        delay = max(float(retry_after), delay)  
                    else:  
                        jitter = random.uniform(0, 1)  
                        delay = min(delay * 2 + jitter, max_delay)  
                    sleep(delay)  
            else:  
                with lock:  
                    results_list.append({  
                        "success": False,  
                        "status_code": response.status_code,  
                        "error": response.reason  
                    })  
                return  
        except Exception as e:  
            with lock:  
                results_list.append({  
                    "success": False,  
                    "error": str(e)  
                })  
            return  
  
# Function to test a specific combination of concurrency, prompt_size, and response_size  
def test_combination(endpoint_url, api_key, concurrency, prompt_size, response_size):  
    # Generate input prompts with specified size  
    base_prompt = "Sample input prompt with token size."  
    repeat_times = max(1, int(prompt_size / len(base_prompt.split())))  
    prompt_content = " ".join([base_prompt] * repeat_times)  
    input_prompts = [  
        {"role": "user", "content": prompt_content}  
    ] * concurrency  # Duplicate the prompt for testing concurrency  
  
    results_list = []  
    lock = threading.Lock()  
    threads = []  
  
    total_start_time = time()  
  
    for i in range(concurrency):  
        t = threading.Thread(target=invoke_endpoint, args=(  
            endpoint_url,  
            api_key,  
            [input_prompts[i]],  
            response_size,  
            results_list,  
            lock  
        ))  
        threads.append(t)  
        t.start()  
  
    # Wait for all threads to complete  
    for t in threads:  
        t.join()  
  
    total_execution_time = time() - total_start_time  
  
    # Aggregate statistics  
    total_latency = 0  
    total_ttft = 0  
    total_tokens = 0  
    successful_requests = 0  
    failed_requests = 0  
    error_status_codes = {}  
  
    for result in results_list:  
        if result["success"]:  
            total_latency += result["latency"]  
            total_ttft += result["ttft"]  
            total_tokens += result["output_tokens"]  
            successful_requests += 1  
        else:  
            failed_requests += 1  
            status_code = result.get("status_code", "Unknown")  
            error_status_codes[status_code] = error_status_codes.get(status_code, 0) + 1  
  
    avg_latency = total_latency / successful_requests if successful_requests > 0 else 0  
    avg_ttft = total_ttft / successful_requests if successful_requests > 0 else 0  
    throughput = total_tokens / total_execution_time if total_execution_time > 0 else 0  
  
    return {  
        "concurrency": concurrency,  
        "prompt_size": prompt_size,  
        "response_size": response_size,  
        "successful_requests": successful_requests,  
        "failed_requests": failed_requests,  
        "avg_latency": avg_latency,  
        "avg_ttft": avg_ttft,  
        "throughput": throughput,  
        "total_execution_time": total_execution_time,  
        "error_status_codes": error_status_codes  
    }  
  
# Main function to adaptively adjust concurrency  
def main(endpoint_url, api_key, initial_concurrency, prompt_sizes, response_sizes, max_tests, output_file, max_concurrency):  
    results = []  
    test_count = 0  
  
    print("Starting concurrency testing...\n")  
  
    # Generate all possible prompt and response size combinations  
    pr_combinations = [  
        (prompt_size, response_size)  
        for prompt_size in prompt_sizes  
        for response_size in response_sizes  
    ]  
  
    # Randomly shuffle the combinations to avoid systematic biases  
    random.shuffle(pr_combinations)  
  
    for prompt_size, response_size in pr_combinations:  
        concurrency = initial_concurrency  
        min_concurrency = 1  
        # Use the max_concurrency passed from the arguments  
        while test_count < max_tests and concurrency <= max_concurrency:  
            print(f"Testing combination: Concurrency={concurrency}, Prompt Size={prompt_size}, Response Size={response_size}")  
            result = test_combination(endpoint_url, api_key, concurrency, prompt_size, response_size)  
            results.append(result)  
            test_count += 1  
  
            # Print results for this combination  
            total_requests = result['successful_requests'] + result['failed_requests']  
            failure_rate = result['failed_requests'] / total_requests if total_requests > 0 else 0  
  
            print(f"Concurrency: {result['concurrency']}")  
            print(f"Prompt Size: {result['prompt_size']}")  
            print(f"Response Size: {result['response_size']}")  
            print(f"Successful Requests: {result['successful_requests']}")  
            print(f"Failed Requests: {result['failed_requests']}")  
            print(f"Failure Rate: {failure_rate*100:.2f}%")  
            print(f"Average Latency (seconds): {result['avg_latency']:.2f}")  
            print(f"Average TTFT (seconds): {result['avg_ttft']:.2f}")  
            print(f"Throughput (tokens/second): {result['throughput']:.2f}")  
            print(f"Total Execution Time (seconds): {result['total_execution_time']:.2f}")  
            if result["failed_requests"] > 0:  
                print(f"Error Status Codes: {result['error_status_codes']}")  
            print("-" * 50)  
  
            # Adaptive concurrency adjustment  
            if failure_rate > 0.2:  
                # Reduce concurrency if failure rate is high  
                concurrency = max(concurrency - 1, min_concurrency)  
                if concurrency == min_concurrency:  
                    print("Concurrency reduced to minimum due to high failure rate.")  
                    break  
            else:  
                # Increase concurrency to test higher loads  
                concurrency = concurrency + 1  
  
            # Limit the concurrency to max_concurrency  
            if concurrency > max_concurrency:  
                print(f"Reached maximum concurrency limit of {max_concurrency}.")  
                break  
  
    # Find the combination with the maximum throughput  
    if results:  
        best_throughput_result = max(results, key=lambda x: x['throughput'])  
  
        print("\nBest Throughput Achieved:")  
        print(f"Concurrency: {best_throughput_result['concurrency']}")  
        print(f"Prompt Size: {best_throughput_result['prompt_size']}")  
        print(f"Response Size: {best_throughput_result['response_size']}")  
        print(f"Throughput (tokens/second): {best_throughput_result['throughput']:.2f}")  
        print(f"Average Latency (seconds): {best_throughput_result['avg_latency']:.2f}")  
        print(f"Average TTFT (seconds): {best_throughput_result['avg_ttft']:.2f}")  
    else:  
        print("No successful test results to report.")  
  
    # Save results to CSV  
    with open(output_file, mode='w', newline='') as file:  
        fieldnames = [  
            "concurrency", "prompt_size", "response_size",  
            "successful_requests", "failed_requests", "avg_latency",  
            "avg_ttft", "throughput", "total_execution_time", "error_status_codes"  
        ]  
        writer = csv.DictWriter(file, fieldnames=fieldnames)  
        writer.writeheader()  
        for result in results:  
            # Convert error_status_codes dict to string for CSV  
            result['error_status_codes'] = json.dumps(result['error_status_codes'])  
            writer.writerow(result)  
  
    print(f"\nTest completed. Results saved to {output_file}")  
  
if __name__ == '__main__':  
    # Parse command-line arguments  
    parser = argparse.ArgumentParser(description="Concurrency and throughput testing of Azure ML Endpoint using threading")  
    parser.add_argument('--endpoint_url', type=str, required=True, help="URL of the Azure ML Endpoint")  
    parser.add_argument('--api_key', type=str, required=True, help="API key for the Azure ML Endpoint")  
    parser.add_argument('--initial_concurrency', type=int, default=1, help="Initial concurrency level to start testing")  
    parser.add_argument('--prompt_sizes', type=int, nargs='+', default=[64, 128, 256], help="List of input prompt sizes in tokens")  
    parser.add_argument('--response_sizes', type=int, nargs='+', default=[64, 128, 256], help="List of output response sizes in tokens")  
    parser.add_argument('--max_tests', type=int, default=30, help="Maximum number of tests to perform")  
    parser.add_argument('--output_file', type=str, default="concurrency_test_final_results.csv", help="Output CSV file")  
    parser.add_argument('--max_concurrency', type=int, default=50, help="Maximum concurrency level to test")  # 新增的参数  
    args = parser.parse_args()  
  
    # Run the main function  
    main(  
        endpoint_url=args.endpoint_url,  
        api_key=args.api_key,  
        initial_concurrency=args.initial_concurrency,  
        prompt_sizes=args.prompt_sizes,  
        response_sizes=args.response_sizes,  
        max_tests=args.max_tests,  
        output_file=args.output_file,  
        max_concurrency=args.max_concurrency  # 传入最大并发参数  
    )  
