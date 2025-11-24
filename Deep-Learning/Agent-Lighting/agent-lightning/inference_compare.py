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
    os.path.join(os.getcwd(), "checkpoints/AgentLightningTutorial/math_agent_robust/global_step_125/actor/huggingface_converted"),
)

# 可通过环境变量覆盖模型来源
BASE_MODEL_REPO = os.environ.get(
    "BASE_MODEL_REPO",
    "Qwen/Qwen2.5-0.5B-Instruct",
)
TRAINED_MODEL_REPO = os.environ.get("TRAINED_MODEL_REPO")

# vLLM 端口和 API Key，可通过环境变量覆写
PORT = int(os.environ.get("VLLM_PORT", "8001"))
API_KEY = os.environ.get("VLLM_API_KEY", "EMPTY")
LAUNCH_TIMEOUT = int(os.environ.get("VLLM_LAUNCH_TIMEOUT", "180"))

VLLM_URL = f"http://127.0.0.1:{PORT}/v1"
SYSTEM_PROMPT = "You are a math assistant. Output ONLY the final number."

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
                temperature=0.1,
                max_tokens=50
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
        f"{'Base Model':<15} | {'Trained Model':<15} | {'Status'}"
    )
    print("-" * 90)
    
    correct_base = 0
    correct_trained = 0
    
    def extract_num(text):
        if text == "N/A": return None
        matches = re.findall(r'-?\d+\.?\d*', text)
        return float(matches[-1]) if matches else None

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

        print(
            f"{q:<35} | {ans:<8} | {res_base:<15} | "
            f"{res_trained:<15} | {status}"
        )
        
    print("-" * 90)
    print(f"准确率: Base Model = {correct_base/len(TEST_QUESTIONS):.1%}")
    print(f"准确率: Trained Model = {correct_trained/len(TEST_QUESTIONS):.1%}")
    print("="*90)

if __name__ == "__main__":
    asyncio.run(main())
