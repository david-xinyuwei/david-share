import os
import time
import subprocess
import asyncio
import sys
import re
from datetime import datetime
from typing import Optional, Tuple

from huggingface_hub import snapshot_download
from openai import AsyncOpenAI

# --- 配置 ---
DEFAULT_TRAINED_LOCAL_PATH = os.environ.get(
    "DEFAULT_TRAINED_MODEL_PATH",
    os.path.join(os.getcwd(), "checkpoints/trained_model"),
)

# 可通过环境变量覆盖模型来源
BASE_MODEL_REPO = os.environ.get(
    "BASE_MODEL_REPO",
    "microsoft/Phi-3-mini-4k-instruct",
)
TRAINED_MODEL_REPO = os.environ.get("TRAINED_MODEL_REPO")

# vLLM 端口和 API Key，可通过环境变量覆写
PORT = int(os.environ.get("VLLM_PORT", "8001"))
API_KEY = os.environ.get("VLLM_API_KEY", "EMPTY")
LAUNCH_TIMEOUT = int(os.environ.get("VLLM_LAUNCH_TIMEOUT", "180"))

VLLM_URL = f"http://127.0.0.1:{PORT}/v1"
# 修正 System Prompt，引导模型输出思考过程和标准格式
SYSTEM_PROMPT = """You are a helpful math assistant.
1. First, think through the problem step by step within <think>...</think> tags.
2. Then, provide your final answer within <answer>...</answer> tags.
Example:
<think>
To calculate 1+1, I know that...
</think>
<answer>
2
</answer>
"""

# 测试题目
TEST_QUESTIONS = [
    {"question": "Calculate 25 * 4 + 10", "answer": "110"},
    {"question": "What is 15% of 200?", "answer": "30"},
    {"question": "Solve 3x = 12", "answer": "4"},
    {"question": "100 divided by 5 plus 8", "answer": "28"},
    {"question": "Square root of 144", "answer": "12"},
    {"question": "Calculate 50 * 2 - 10", "answer": "90"},
    {"question": "What is 20% of 500?", "answer": "100"}
]


def get_hf_token() -> Optional[str]:
    """Return the first available Hugging Face token from the environment."""
    for key in ("HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN"):
        token = os.environ.get(key)
        if token:
            return token
    return None


def resolve_model_path(
    env_key: str,
    description: str,
    default_repo: Optional[str] = None,
    fallback_path: Optional[str] = None,
) -> str:
    """Resolve a local model path, downloading from Hugging Face if needed."""

    candidates = []
    env_value = os.environ.get(env_key)
    if env_value:
        candidates.append(env_value)
    if fallback_path and fallback_path not in candidates:
        candidates.append(fallback_path)

    for candidate in candidates:
        if not candidate:
            continue
        if os.path.isdir(candidate):
            print(f"📁 使用{description}: {candidate}")
            return candidate
        print(f"⚠️ 指定的{description}路径不存在: {candidate}")

    if default_repo:
        token = get_hf_token()
        print(f"⬇️ 正在从 Hugging Face 下载{description} ({default_repo})...")
        downloaded_path = snapshot_download(
            repo_id=default_repo,
            token=token,
            local_dir=None,
            local_dir_use_symlinks=False,
        )
        print(f"📁 下载完成: {downloaded_path}")
        return downloaded_path

    raise FileNotFoundError(
        f"无法解析{description}路径。请设置 {env_key} 或提供对应仓库/本地路径。"
    )


async def wait_for_server(url: str, timeout: int = LAUNCH_TIMEOUT) -> bool:
    """等待 vLLM 服务器就绪"""
    start_time = time.time()
    client = AsyncOpenAI(base_url=url, api_key=API_KEY)
    
    while time.time() - start_time < timeout:
        try:
            # 尝试列出模型
            await client.models.list()
            print(" ✅ 就绪!")
            return True
        except Exception:
            print(".", end="", flush=True)
            await asyncio.sleep(5)

    print(" ❌ 超时!")
    return False


def start_vllm(model_path: str) -> Tuple[subprocess.Popen, object]:
    """启动 vLLM 服务器"""
    print(f"\n🚀 正在启动 vLLM (Model: {model_path})...")
    
    # 1. 清理旧进程
    subprocess.run(
        ["pkill", "-f", "vllm.entrypoints.openai.api_server"],
        check=False,
    )
    time.sleep(5)  # 等待端口释放

    # 2. 启动新进程
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_path,
        "--port", str(PORT),
        "--trust-remote-code",
        "--gpu-memory-utilization", "0.8",
        "--dtype", "float16",
        "--api-key", API_KEY,
    ]
    
    # 后台运行，重定向输出以保持控制台整洁
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_name = os.environ.get(
        "VLLM_LOG_FILE",
        f"vllm_{os.path.basename(model_path)}_{timestamp}.log",
    )
    log_file = open(log_name, "w")
    process = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
    return process, log_file


async def run_inference(model_name: str):
    """运行推理"""
    client = AsyncOpenAI(base_url=VLLM_URL, api_key=API_KEY)
    results = []
    
    print(f"🧪 正在测试模型: {model_name}")
    for item in TEST_QUESTIONS:
        q = item["question"]
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": q}
                ],
                temperature=0.6, # 稍微增加温度以鼓励多样化的思考
                max_tokens=1024  # 增加 token 限制以容纳思考过程
            )
            pred = response.choices[0].message.content.strip()
        except Exception as e:
            pred = f"Error: {e}"
            
        results.append(pred)
        # print(f"  Q: {q} -> A: {pred}") # 暂时不打印详细日志，最后统一输出
        
    return results


async def main():
    base_model_path = resolve_model_path(
        env_key="BASE_MODEL_PATH",
        description="基础模型",
        default_repo=BASE_MODEL_REPO,
    )
    trained_model_path = resolve_model_path(
        env_key="TRAINED_MODEL_PATH",
        description="训练后模型",
        default_repo=TRAINED_MODEL_REPO,
        fallback_path=DEFAULT_TRAINED_LOCAL_PATH,
    )

    print("="*80)
    print("🤖 模型对比测试脚本 (Base vs Trained)")
    print("="*80)

    # --- 1. 测试 Base Model ---
    p1, log1 = start_vllm(base_model_path)
    if await wait_for_server(VLLM_URL):
        base_results = await run_inference(base_model_path)
    else:
        print("❌ Base Model 启动失败，跳过测试")
        base_results = ["N/A"] * len(TEST_QUESTIONS)
    
    # 关闭 Base Model
    p1.terminate()
    p1.wait()
    log1.close()
    
    # --- 2. 测试 Trained Model ---
    p2, log2 = start_vllm(trained_model_path)
    if await wait_for_server(VLLM_URL):
        trained_results = await run_inference(trained_model_path)
    else:
        print("❌ Trained Model 启动失败，跳过测试")
        trained_results = ["N/A"] * len(TEST_QUESTIONS)
        
    # 关闭 Trained Model
    p2.terminate()
    p2.wait()
    log2.close()
    
    # --- 3. 输出对比结果 ---
    print("\n" + "="*90)
    print(
        f"{'Question':<35} | {'Answer':<8} | "
        f"{'Base Model':<15} | {'Trained Model':<15} | {'Status'} | {'Thinking'}"
    )
    print("-" * 110)
    
    correct_base = 0
    correct_trained = 0
    
    def extract_num(text):
        if text == "N/A": return None
        # 优先尝试提取 <answer> 标签内的内容
        answer_match = re.search(r'<answer>(.*?)</answer>', text, re.DOTALL)
        if answer_match:
            text_to_parse = answer_match.group(1)
        else:
            text_to_parse = text
            
        matches = re.findall(r'-?\d+\.?\d*', text_to_parse)
        return float(matches[-1]) if matches else None

    def has_thinking(text):
        return "<think>" in text and "</think>" in text

    for i, item in enumerate(TEST_QUESTIONS):
        q = item["question"]
        ans = item["answer"]
        res_base = base_results[i]
        res_trained = trained_results[i]
        
        val_ans = extract_num(ans)
        val_base = extract_num(res_base)
        val_trained = extract_num(res_trained)
        
        if val_ans is not None:
            is_base_correct = (val_base is not None and abs(val_base - val_ans) < 1e-6)
            is_trained_correct = (val_trained is not None and abs(val_trained - val_ans) < 1e-6)
        else:
            is_base_correct = (res_base == ans)
            is_trained_correct = (res_trained == ans)
        
        if is_base_correct:
            correct_base += 1
        if is_trained_correct:
            correct_trained += 1
        
        # 状态标记
        if is_trained_correct and not is_base_correct:
            status = "✅ 提升"
        elif is_trained_correct == is_base_correct:
            status = "➖ 持平"
        else:
            status = "❌ 下降"

        # 检查是否有思考过程
        thinking_status = "🧠 有思考" if has_thinking(res_trained) else "⚪ 无思考"

        # 格式化输出，截断过长的结果以便显示
        disp_base = str(val_base) if val_base is not None else "Error"
        disp_trained = str(val_trained) if val_trained is not None else "Error"

        print(
            f"{q:<35} | {ans:<8} | {disp_base:<15} | "
            f"{disp_trained:<15} | {status} | {thinking_status}"
        )
        
    print("-" * 110)
    print(f"准确率: Base Model = {correct_base/len(TEST_QUESTIONS):.1%}")
    print(f"准确率: Trained Model = {correct_trained/len(TEST_QUESTIONS):.1%}")
    print("="*90)

if __name__ == "__main__":
    asyncio.run(main())
