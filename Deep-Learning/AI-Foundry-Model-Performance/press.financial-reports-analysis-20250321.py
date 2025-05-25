#!/usr/bin/env python3  
# -*- coding: utf-8 -*-  
  
import urllib.request  
import urllib.error  
import json  
import os  
import ssl  
import time  
import concurrent.futures  
  
# Attempt to import tokenizer from transformers  
try:  
    from transformers import AutoTokenizer  
except ImportError as e:  
    print("Please install 'transformers' library to measure token usage. Error:", e)  
    exit(1)  
  
def allow_self_signed_https(allowed: bool) -> None:  
    """  
    If your inference service uses a self-signed certificate in a test environment,  
    you may need to skip certificate verification.  
    """  
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):  
        ssl._create_default_https_context = ssl._create_unverified_context  
  
# -----------------------------------------------------  
# Global variables  
# -----------------------------------------------------  
FINREPORT_URL = None  
API_KEY = None  
DEPLOYMENT_NAME = None  
HEADERS = {}  
REQUEST_TIMEOUT = 90  # Timeout (in seconds) for each request  
CONCURRENCY_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  
tokenizer = None  
  
# -----------------------------------------------------  
# Four different “10-K” excerpts  
# -----------------------------------------------------  
DEMO_10K_TEXTS = {  
    "short_10k": {  
        "text": (  
            "Below is a short excerpt from the 10-K filing of MicroExampleCorp "  
            "for the fiscal year ended December 31, 2022. The company focuses on "  
            "software development and small consumer electronics. Potential risks "  
            "involve software bugs, supply chain constraints, and fluctuations "  
            "in user demand."  
        ),  
        "summary_length": 512  
    },  
    "medium_10k": {  
        "text": (  
            "Below is a medium-length excerpt from the 10-K filing of TechExampleCorp "  
            "for the fiscal year ended December 31, 2022. The company primarily operates "  
            "in cloud computing services, cybersecurity, and consumer electronics. Key "  
            "risks revolve around data breaches, regulatory compliance issues, patent "  
            "disputes, and dependencies on critical third-party providers. Over the "  
            "fiscal year, TechExampleCorp reported a revenue growth of 12%, balanced by "  
            "increased operational costs in R&D for emerging technologies and expanded "  
            "marketing. This excerpt highlights major risk factors, operational analytics, "  
            "and ongoing strategic initiatives in digital transformation."  
        ),  
        "summary_length": 1024  
    },  
    "long_10k": {  
        "text": (  
            "Below is a longer excerpt from the 10-K filing of MacroExampleInc for the "  
            "fiscal year ended December 31, 2022. The company is engaged in manufacturing "  
            "large-scale industrial machinery, consumer electronics, and software platforms. "  
            "Throughout the year, MacroExampleInc faced supply chain disruptions, increased "  
            "commodity prices, and labor shortages in key production facilities. In parallel, "  
            "the firm pursued expansion into cloud-based solutions for real-time analytics "  
            "and specialized IoT devices, leading to a 15% year-over-year increase in "  
            "revenue. However, operating expenses also showed a sharp rise, partially due "  
            "to acquisitions, enhanced R&D efforts, and higher marketing budgets in global "  
            "markets. Risk factors central to this excerpt include fluctuating currency "  
            "exchange rates, reliance on strategic partnerships for integrated services, "  
            "cybersecurity vulnerabilities, and evolving consumer preferences for digital "  
            "offerings. Additional attention is given to regulatory compliance across "  
            "multiple jurisdictions, changing environmental standards, and intellectual "  
            "property litigation. The excerpt aims to illustrate key operational highlights, "  
            "identify principal uncertainties, and outline the company's strategies for "  
            "sustainable growth in a competitive worldwide market."  
        ),  
        "summary_length": 2048  
    },  
    "ultra_long_10k": {  
        "text": (  
            "Below is an ultra-long excerpt from the 10-K filing of GigaExampleLLC for "  
            "the fiscal year ended December 31, 2022. The company operates across multiple "  
            "industries, including advanced manufacturing, enterprise software solutions, "  
            "financial services, and renewable energy technologies. Throughout the year, "  
            "GigaExampleLLC invested heavily in new product lines designed to integrate "  
            "industrial automation with AI-driven analytics. This expansion led to an overall "  
            "18% growth in revenue compared to the prior year, partly attributed to strategic "  
            "alliances with key suppliers. However, significant challenges arose from global "  
            "supply chain constraints, rising raw material costs, and workforce management "  
            "issues. In addition, certain geopolitical tensions introduced heightened "  
            "regulatory compliance risks in international markets, requiring more robust "  
            "oversight and increased legal expenditure. "  
            "Moreover, GigaExampleLLC’s financial services arm experienced volatility in loan "  
            "portfolios due to fluctuating interest rates and unpredictable consumer behavior, "  
            "prompting revisions to the company’s risk management framework. Concurrently, "  
            "the renewable energy division engaged in extensive research and development to "  
            "optimize next-generation solar panel technologies and battery storage systems. "  
            "Despite strong investor interest, these initiatives demanded substantial upfront "  
            "capital expenditures, which weighed on short-term margins. The company faced "  
            "further complexity in reconciling environmental regulations across diverse "  
            "regions, leading to additional compliance costs. "  
            "Additionally, the enterprise software solutions segment confronted rising "  
            "competition from agile startups and larger multinational corporations, spurring "  
            "an escalation in marketing spend and accelerated product release cycles. New "  
            "software-as-a-service offerings required advanced cybersecurity measures to "  
            "protect client data and maintain regulatory standards. Heightened expectations "  
            "from stakeholders and board members further emphasized the need for transparent "  
            "reporting on sustainability metrics, corporate governance, and community impact. "  
            "Overall, this excerpt underlines the critical risk factors tied to macroeconomic "  
            "conditions, technological innovation, talent retention, and global compliance "  
            "harmonization. The narrative aims to detail both short-term dynamics and "  
            "forward-looking strategies designed to position GigaExampleLLC competitively "  
            "in an evolving global market."  
        ),  
        "summary_length": 4096  
    }  
}  
  
def build_prompt(excerpt: str, desired_summary_length: int) -> str:  
    """  
    Construct the request prompt, including instructions about the excerpt  
    and a desired summary length (in words or approximate tokens).  
    """  
    return (  
        "Please analyze the following excerpt from a hypothetical 10-K filing.\n\n"  
        f"{excerpt}\n\n"  
        f"Identify the main risk factors for this company and provide a concise summary "  
        f"in about {desired_summary_length} words. Thank you."  
    )  
  
def input_config():  
    """  
    交互式收集用户输入的 Endpoint URL, Key/Token, 部署名称, 以及 tokenizer 模型名。  
    将结果存储到全局变量中。  
    """  
    global FINREPORT_URL, API_KEY, DEPLOYMENT_NAME, HEADERS, tokenizer  
  
    FINREPORT_URL = input("Please enter the Azure ML Endpoint URL: ").strip()  
    if not FINREPORT_URL:  
        raise ValueError("The Endpoint URL cannot be empty!")  
  
    API_KEY = input("Please enter your Azure ML Endpoint Key or Token: ").strip()  
    if not API_KEY:  
        raise ValueError("The API Key or Token cannot be empty!")  
  
    DEPLOYMENT_NAME = input("If you need to specify a Deployment Name, enter it now (or press Enter to skip): ").strip()  
  
    hf_model_name = input("Please enter a HuggingFace model name for token counting (e.g., 'gpt2'): ").strip()  
    if not hf_model_name:  
        raise ValueError("You must provide a valid HF model name to measure tokens!")  
  
    print(f"Loading tokenizer for '{hf_model_name}'...")  
    tokenizer = AutoTokenizer.from_pretrained(hf_model_name)  
    print("Tokenizer loaded successfully!")  
  
    HEADERS = {  
        "Content-Type": "application/json",  
        "Accept": "application/json",  
        "Authorization": "Bearer " + API_KEY  
    }  
    if DEPLOYMENT_NAME:  
        HEADERS["azureml-model-deployment"] = DEPLOYMENT_NAME  
  
def send_finreport_request(prompt_text: str) -> dict:  
    """  
    Sends one request to the financial-report analysis model and captures:  
    - total latency (seconds)  
    - TTFT (treated same as total latency here, since we are not streaming)  
    - prompt token count  
    - output token count  
    - throughput (tokens/sec)  
    - success status  
    - completion text  
    """  
    MAX_RETRY = 3  
    last_exception = None  
  
    # 统计 prompt 的 token 数  
    if tokenizer is not None:  
        prompt_tokens_list = tokenizer.tokenize(prompt_text)  
        prompt_token_count = len(prompt_tokens_list)  
    else:  
        prompt_token_count = len(prompt_text.split())  
  
    # 如果要让模型生成更多文本，可在这里修改或增加相应参数  
    payload = {  
        "input_data": {  
            "input_string": [  
                {  
                    "role": "user",  
                    "content": prompt_text  
                }  
            ],  
            "parameters": {  
                # 下面这些是 OpenAI 风格的常见参数示例，需确认后端是否兼容  
                "temperature": 0.7,  
                "max_tokens": 1024,  # 调大以获取更长的回复  
                "top_p": 0.95,  
                "frequency_penalty": 0.0,  
                "presence_penalty": 0.0  
            }  
        }  
    }  
  
    body = json.dumps(payload).encode("utf-8")  
  
    for attempt in range(MAX_RETRY):  
        try:  
            start_time = time.perf_counter()  
            req = urllib.request.Request(  
                FINREPORT_URL,  
                data=body,  
                headers=HEADERS,  
                method="POST"  
            )  
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:  
                result_bytes = resp.read()  
            end_time = time.perf_counter()  
  
            latency = end_time - start_time  
            ttft = latency  
  
            result_str = result_bytes.decode("utf-8", errors="ignore")  
  
            # 尝试解析 JSON，提取 "completion" 或直接返回所有内容  
            completion_text = ""  
            try:  
                parsed = json.loads(result_str)  
                if isinstance(parsed, dict) and "output" in parsed:  
                    completion_text = parsed["output"]  
                else:  
                    completion_text = result_str  
            except json.JSONDecodeError:  
                completion_text = result_str  
  
            # 统计生成的 tokens  
            if tokenizer is not None:  
                output_tokens_list = tokenizer.tokenize(result_str)  
                output_token_count = len(output_tokens_list)  
            else:  
                output_token_count = len(result_str.split())  
  
            throughput = output_token_count / latency if latency > 0 else float('inf')  
  
            return {  
                "latency": latency,  
                "ttft": ttft,  
                "prompt_tokens": prompt_token_count,  
                "output_tokens": output_token_count,  
                "throughput": throughput,  
                "success": True,  
                "completion": completion_text  
            }  
  
        except urllib.error.HTTPError as e:  
            last_exception = e  
            if e.code == 429:  
                backoff = 2 ** attempt  
                print(f"[Warning] Attempt {attempt+1}: HTTP 429 Too Many Requests, backing off {backoff} seconds.")  
                time.sleep(backoff)  
                continue  
            else:  
                print(f"[Warning] Attempt {attempt+1}: HTTP Error {e.code}, reason: {e.reason}")  
                time.sleep(1)  
                continue  
        except Exception as e:  
            last_exception = e  
            print(f"[Warning] Attempt {attempt+1}: Exception: {e}")  
            time.sleep(1)  
            continue  
  
    # 如果所有重试都失败  
    return {  
        "latency": None,  
        "ttft": None,  
        "prompt_tokens": 0,  
        "output_tokens": 0,  
        "throughput": 0,  
        "success": False,  
        "error": str(last_exception) if last_exception else "Unknown error",  
        "completion": ""  
    }  
  
def run_concurrency_test(scenario_name: str, prompt_text: str, concurrency: int):  
    """  
    Perform concurrent requests for the given prompt.  
    Then print stats in the format you requested.  
    """  
    print(f"\nScenario: {scenario_name}, Concurrency: {concurrency}")  
  
    start_wall_time = time.time()  
    results = []  
  
    # 并发执行  
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:  
        futures = [executor.submit(send_finreport_request, prompt_text) for _ in range(concurrency)]  
        for future in concurrent.futures.as_completed(futures):  
            results.append(future.result())  
  
    end_wall_time = time.time()  
    batch_duration = end_wall_time - start_wall_time  
  
    success_results = [r for r in results if r["success"]]  
    fail_results = [r for r in results if not r["success"]]  
    success_count = len(success_results)  
    fail_count = len(fail_results)  
  
    # 打印每条成功请求的详细信息  
    for idx, r in enumerate(success_results):  
        print(f"  Request {idx + 1}:")  
        print(f"    TTFT          : {r['ttft']:.3f} s")  
        print(f"    Latency       : {r['latency']:.3f} s")  
        print(f"    Throughput    : {r['throughput']:.2f} tokens/s")  
        print(f"    Prompt tokens : {r['prompt_tokens']}, Output tokens: {r['output_tokens']}")  
        print(f"    Completion    : {r['completion']}")  
  
    # 打印失败请求信息  
    if fail_count > 0:  
        for idx, r in enumerate(fail_results):  
            print(f"  Request {idx + 1 + success_count} failed: {r.get('error','N/A')}")  
  
    # 统计整体结果  
    if success_count > 0:  
        avg_ttft = sum(r["ttft"] for r in success_results) / success_count  
        avg_throughput = sum(r["throughput"] for r in success_results) / success_count  
        overall_throughput = sum(r["throughput"] for r in success_results)  
    else:  
        avg_ttft = float('nan')  
        avg_throughput = float('nan')  
        overall_throughput = 0  
  
    print(f"\n  Summary for concurrency {concurrency}:")  
    print(f"    Successful requests          : {success_count}")  
    print(f"    Failed requests              : {fail_count}")  
    print(f"    Average TTFT per request     : {avg_ttft:.3f} s")  
    print(f"    Average throughput per req   : {avg_throughput:.2f} tokens/s")  
    print(f"    Overall throughput (sum)     : {overall_throughput:.2f} tokens/s")  
    print(f"    Batch duration (wall-clock)  : {batch_duration:.3f} s")  
  
def main():  
    allow_self_signed_https(True)  
    input_config()  
    print("\nStarting load tests with multiple 10-K excerpts (short, medium, long, ultra-long)...\n")  
  
    for label, text_info in DEMO_10K_TEXTS.items():  
        excerpt_text = text_info["text"]  
        summary_length = text_info["summary_length"]  
        prompt_text = build_prompt(excerpt_text, summary_length)  
  
        for concurrency in CONCURRENCY_LEVELS:  
            run_concurrency_test(label, prompt_text, concurrency)  
  
if __name__ == "__main__":  
    main()  