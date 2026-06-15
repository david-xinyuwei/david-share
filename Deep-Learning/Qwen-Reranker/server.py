import os
# Clear problematic environment variables before importing vllm
os.environ.pop('VLLM_ATTENTION_BACKEND', None)  # Let VLLM auto-select compatible backend
os.environ["VLLM_USE_V1"] = "0"  # Force V0 engine to avoid threading issues
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# Remove CUDA_LAUNCH_BLOCKING for better performance
# os.environ["CUDA_LAUNCH_BLOCKING"] = "1"  # Disabled for performance
os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu:" + os.environ.get("LD_LIBRARY_PATH", "")
try:
    import pynvml as nvml
    nvml.nvmlInit()
    NVML_AVAILABLE = True
    print("✅ NVML 初始化成功，GPU监控可用")
except Exception as e:
    NVML_AVAILABLE = False
    print(f"⚠️ NVML 初始化失败: {e}")
import logging
import asyncio
from typing import List, Dict, Optional
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from vllm.distributed.parallel_state import destroy_model_parallel
import gc
import math
from sentence_transformers import CrossEncoder
from vllm.inputs.data import TokensPrompt
import time
import threading
try:
    import nvidia_ml_py3 as nvml
    nvml.nvmlInit()
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False
    print("nvidia-ml-py3 not available, GPU monitoring disabled")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enhanced performance monitor with GPU tracking
class SimplePerformanceMonitor:
    def __init__(self):
        self.request_count = 0
        self.total_response_time = 0.0
        self.start_time = time.time()
        self.lock = threading.Lock()
        self.gpu_handle = None
        if NVML_AVAILABLE and torch.cuda.is_available():
            try:
                self.gpu_handle = nvml.nvmlDeviceGetHandleByIndex(0)
            except Exception as e:
                print(f"Failed to get GPU handle: {e}")
    
    def record_request(self, response_time: float):
        with self.lock:
            self.request_count += 1
            self.total_response_time += response_time
    
    def get_gpu_stats(self) -> Dict[str, float]:
        if not self.gpu_handle:
            return {"gpu_utilization": 0.0, "gpu_memory_used": 0.0, "gpu_memory_total": 0.0}
        
        try:
            utilization = nvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
            memory_info = nvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
            return {
                "gpu_utilization": float(utilization.gpu),
                "gpu_memory_used": float(memory_info.used) / 1024**3,  # GB
                "gpu_memory_total": float(memory_info.total) / 1024**3,  # GB
                "gpu_memory_utilization": float(memory_info.used) / float(memory_info.total) * 100
            }
        except Exception:
            return {"gpu_utilization": 0.0, "gpu_memory_used": 0.0, "gpu_memory_total": 0.0}
    
    def get_stats(self) -> Dict[str, float]:
        with self.lock:
            if self.request_count == 0:
                stats = {"tps": 0.0, "avg_response_time": 0.0, "total_requests": 0.0}
            else:
                elapsed_time = time.time() - self.start_time
                tps = float(self.request_count) / elapsed_time if elapsed_time > 0 else 0.0
                avg_response_time = self.total_response_time / self.request_count
                
                stats = {
                    "tps": tps,
                    "avg_response_time": avg_response_time,
                    "total_requests": float(self.request_count),
                    "uptime": elapsed_time
                }
            
            # Add GPU stats
            gpu_stats = self.get_gpu_stats()
            stats.update(gpu_stats)
            return stats

# Global performance monitor
perf_monitor = SimplePerformanceMonitor()

# Pydantic models
class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    instruction: Optional[str] = "Retrieval document that can answer user's query"
    max_length: int = 2048

class RerankResponse(BaseModel):
    scores: List[float]
    query: str
    documents: List[str]
    processing_time: float

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    performance_stats: Dict[str, float]

class Qwen3Rerankervllm(CrossEncoder):
    def __init__(self, model_name_or_path, instruction="Given the user query, retrieval the relevant passages", **kwargs):
        self.instruction = instruction
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
        self.tokenizer.padding_side = "left"
        self.tokenizer.pad_token = self.tokenizer.eos_token
        self.suffix = "<|im_start|>assistant\n<think>\n\n</think>\n\n"
        self.max_length = kwargs.get('max_length', 8192)
        self.suffix_tokens = self.tokenizer.encode(self.suffix, add_special_tokens=False)
        self.true_token = self.tokenizer("yes", add_special_tokens=False).input_ids[0]
        self.false_token = self.tokenizer("no", add_special_tokens=False).input_ids[0]
        self.sampling_params = SamplingParams(
            temperature=0,
            top_p=1.0,  # Use deterministic sampling
            max_tokens=1,
            logprobs=20,
            use_beam_search=False,  # 确保快速推理
            skip_special_tokens=True,
        )
        # 高性能VLLM配置（充分利用H100）
        logger.info("Initializing VLLM with maximum performance settings for H100...")
        self.lm = LLM(
            model=model_name_or_path,
            tensor_parallel_size=1,  # 单卡H100
            max_model_len=4096,
            enable_prefix_caching=True,  # 启用前缀缓存提升性能
            gpu_memory_utilization=0.8,  # 最大化显存利用率（H100有80GB）
            disable_log_stats=True,
            enforce_eager=False,  # 启用CUDA graphs获得最佳性能
            trust_remote_code=False,
            quantization=None,
            max_num_seqs=25600,  # 大幅增加并发序列数
            max_num_batched_tokens=6553600,  # 增加批处理token数
            swap_space=4,  # 增加swap空间
            block_size=32,  # 优化块大小
            enable_chunked_prefill=True,  # 启用分块预填充
            max_num_on_the_fly_seqs=2560,  # 动态序列数
        )
        logger.info("VLLM initialized in HIGH PERFORMANCE mode (CUDA graphs enabled, max memory, large batch)")

    def format_instruction(self, instruction, query, doc):
        if isinstance(query, tuple):
            instruction = query[0]
            query = query[1]
        text = [
            {"role": "system", "content": "Judge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\"."},
            {"role": "user", "content": f"<Instruct>: {instruction}\n\n<Query>: {query}\n\n<Document>: {doc}"}
        ]
        return text

    def compute_scores(self, pairs, **kwargs):
        messages = [self.format_instruction(self.instruction, query, doc) for query, doc in pairs]
        messages = self.tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=False, enable_thinking=False
        )
        messages = [ele[:self.max_length] + self.suffix_tokens for ele in messages]
        messages = [TokensPrompt(prompt_token_ids=ele) for ele in messages]
        outputs = self.lm.generate(messages, self.sampling_params, use_tqdm=False)
        scores = []
        for i in range(len(outputs)):
            # Get the logprobs for the last token
            if outputs[i].outputs[0].logprobs:
                final_logits = outputs[i].outputs[0].logprobs[-1]
                
                # Look for yes/no tokens in the logprobs
                true_logit = final_logits.get(self.true_token, -10.0)
                false_logit = final_logits.get(self.false_token, -10.0)
                
                # If we have proper logprob objects, extract the logprob value
                if hasattr(true_logit, 'logprob'):
                    true_logit = true_logit.logprob
                if hasattr(false_logit, 'logprob'):
                    false_logit = false_logit.logprob
                
                true_score = math.exp(true_logit)
                false_score = math.exp(false_logit)
                score = true_score / (true_score + false_score)
            else:
                # Fallback: analyze the generated text
                generated_text = outputs[i].outputs[0].text.strip().lower()
                if 'yes' in generated_text:
                    score = 0.8  # High relevance
                elif 'no' in generated_text:
                    score = 0.2  # Low relevance
                else:
                    score = 0.5  # Neutral/unclear
            
            scores.append(score)
        return scores

    def stop(self):
        try:
            if hasattr(self, 'lm') and self.lm is not None:
                del self.lm
            destroy_model_parallel()
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            logger.warning(f"Warning during cleanup: {e}")

class Qwen3RerankervllmServer:
    def __init__(self, model_name_or_path: str):
        self.model_name_or_path = model_name_or_path
        self.model = None
        self.load_model()
    
    def load_model(self):
        """Load the Qwen3 reranker model"""
        try:
            logger.info(f"Loading model: {self.model_name_or_path}")
            self.model = Qwen3Rerankervllm(
                model_name_or_path=self.model_name_or_path,
                instruction="Given the user query, retrieval the relevant passages"
            )
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise e
    
    def rerank(self, query: str, documents: List[str], instruction: Optional[str] = None, max_length: int = 2048) -> tuple[List[float], float]:
        """Rerank documents based on query"""
        start_time = time.time()
        
        if self.model is None:
            raise HTTPException(status_code=500, detail="Model not loaded")
        
        try:
            # Update instruction if provided
            if instruction:
                self.model.instruction = instruction
            
            # Update max_length if provided
            self.model.max_length = max_length
            
            # Create pairs
            pairs = [(query, doc) for doc in documents]
            
            # Compute scores
            scores = self.model.compute_scores(pairs)
            
            processing_time = time.time() - start_time
            perf_monitor.record_request(processing_time)
            
            return scores, processing_time
            
        except Exception as e:
            logger.error(f"Error during reranking: {e}")
            raise HTTPException(status_code=500, detail=f"Reranking failed: {str(e)}")
    
    def cleanup(self):
        """Clean up model resources"""
        if self.model:
            self.model.stop()

# Global model server instance
model_server = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    global model_server
    # Startup
    try:
        model_server = Qwen3RerankervllmServer('Qwen/Qwen3-Reranker-0.6B')
        logger.info("Compatible server started successfully")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise e
    
    yield
    
    # Shutdown
    if model_server:
        model_server.cleanup()
        logger.info("Server shutdown completed")

# FastAPI app
app = FastAPI(
    title="Qwen3 Reranker Compatible API",
    description="Compatible API for Qwen3 document reranking service - Maximum Compatibility Mode",
    version="1.2.0",
    lifespan=lifespan
)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with performance stats"""
    stats = perf_monitor.get_stats()
    return HealthResponse(
        status="healthy" if model_server and model_server.model else "unhealthy",
        model_loaded=bool(model_server and model_server.model),
        performance_stats=stats
    )

@app.post("/rerank", response_model=RerankResponse)
async def rerank_documents(request: RerankRequest):
    """Rerank documents endpoint"""
    if not model_server:
        raise HTTPException(status_code=500, detail="Model server not initialized")
    
    try:
        scores, processing_time = model_server.rerank(
            query=request.query,
            documents=request.documents,
            instruction=request.instruction,
            max_length=request.max_length
        )
        
        return RerankResponse(
            scores=scores,
            query=request.query,
            documents=request.documents,
            processing_time=processing_time
        )
    except Exception as e:
        logger.error(f"Error in rerank endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Get performance statistics"""
    stats = perf_monitor.get_stats()
    return {
        "performance": stats,
        "system_info": {
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "cuda_available": torch.cuda.is_available(),
            "attention_backend": "AUTO_SELECT",
            "cuda_graphs": "DISABLED",
            "mode": "COMPATIBLE"
        }
    }

@app.get("/")
async def root():
    """Root endpoint"""
    stats = perf_monitor.get_stats()
    return {
        "message": "Qwen3 Reranker Compatible API",
        "version": "1.2.0",
        "engine": "VLLM V0 (Compatible Mode)",
        "attention_backend": "AUTO_SELECT",
        "current_tps": f"{stats['tps']:.2f}",
        "total_requests": int(stats['total_requests']),
        "endpoints": {
            "health": "/health",
            "rerank": "/rerank",
            "stats": "/stats",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    # Start server with compatible configuration
    uvicorn.run(
        "qwen_reranker_server_compatible:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,  # 单进程，最大兼容
        access_log=False,
        log_level="info"
    )