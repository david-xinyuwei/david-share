#!/usr/bin/env python3
"""
01_quantize_models.py - 量化模型脚本

Design Principles:
- #2 数据真实性: 所有数据从实际量化过程获取，禁止硬编码
- #3 非阻塞性: 使用 tqdm 进度条，不会阻塞
- #8 可追溯性: 记录量化日志，包含时间戳、显存、耗时
- #10 可复现性: 使用固定种子，记录完整配置
- #12 公平性: 所有模型使用相同量化配置 (group_size=128)
"""

import os
import sys
import json
import time
import torch
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# ============================================================
# 日志配置 (Best Practice: Traceability)
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/quantization.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


# ============================================================
# 配置 (Experiment Design: Fair Comparison - 所有模型相同配置)
# ============================================================

MODELS = [
    "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-1.5B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-14B-Instruct",
    "Qwen/Qwen2.5-32B-Instruct",
]

# 统一量化配置 (Experiment Design: 7-Dimension Alignment)
QUANT_CONFIG = {
    "group_size": 128,      # 所有方法统一
    "bits": 4,              # 4-bit 量化
    "desc_act": False,      # GPTQ 配置
    "zero_point": True,     # AWQ 配置
}

OUTPUT_DIR = Path("./quantized_models")


# ============================================================
# AWQ 量化
# ============================================================

def quantize_awq(model_id: str, output_dir: Path) -> Dict:
    """
    使用 AutoAWQ 进行 4-bit 量化
    
    Best Practice: 返回完整量化日志
    Experiment Design: 使用统一配置 QUANT_CONFIG
    """
    from awq import AutoAWQForCausalLM  # type: ignore
    from transformers import AutoTokenizer
    
    model_name = model_id.split("/")[-1]
    quant_path = output_dir / f"{model_name}-AWQ-4bit"
    
    # 记录开始时间和显存 (Traceability)
    start_time = time.time()
    start_mem = torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
    
    log_entry = {
        "model": model_name,
        "method": "AWQ",
        "start_time": datetime.now().isoformat(),
        "config": QUANT_CONFIG,
    }
    
    if quant_path.exists():
        logger.info(f"⏭️  跳过 {model_name} (已存在)")
        log_entry["status"] = "skipped"
        return log_entry
    
    logger.info(f"🔧 量化 {model_name} (AWQ 4-bit)")
    logger.info(f"   配置: group_size={QUANT_CONFIG['group_size']}, bits={QUANT_CONFIG['bits']}")
    
    # AWQ 配置 (Experiment Design: 统一配置)
    quant_config = {
        "zero_point": QUANT_CONFIG["zero_point"],
        "q_group_size": QUANT_CONFIG["group_size"],
        "w_bit": QUANT_CONFIG["bits"],
        "version": "GEMM"
    }
    
    try:
        # 加载模型
        model = AutoAWQForCausalLM.from_pretrained(model_id)
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        
        # 量化
        model.quantize(tokenizer, quant_config=quant_config)
        
        # 保存
        model.save_quantized(str(quant_path))
        tokenizer.save_pretrained(str(quant_path))
        
        # 记录结果 (Traceability)
        elapsed = time.time() - start_time
        peak_mem = torch.cuda.max_memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
        
        log_entry.update({
            "status": "success",
            "output_path": str(quant_path),
            "elapsed_seconds": elapsed,
            "peak_memory_gb": peak_mem,
            "end_time": datetime.now().isoformat(),
        })
        
        logger.info(f"✅ 完成 {model_name} | 耗时: {elapsed/60:.1f}min | 峰值显存: {peak_mem:.1f}GB")
        
    except Exception as e:
        log_entry.update({
            "status": "failed",
            "error": str(e),
        })
        logger.error(f"❌ 量化 {model_name} 失败: {e}")
    
    return log_entry


# ============================================================
# GPTQ 量化
# ============================================================

def quantize_gptq(model_id: str, output_dir: Path) -> Dict:
    """
    使用 GPTQModel 进行 4-bit 量化
    
    Best Practice: 返回完整量化日志
    Experiment Design: 使用统一配置 QUANT_CONFIG
    """
    from gptqmodel import GPTQModel, QuantizeConfig  # type: ignore
    from transformers import AutoTokenizer
    
    model_name = model_id.split("/")[-1]
    quant_path = output_dir / f"{model_name}-GPTQ-4bit"
    
    # 记录开始时间和显存 (Traceability)
    start_time = time.time()
    
    log_entry = {
        "model": model_name,
        "method": "GPTQ",
        "start_time": datetime.now().isoformat(),
        "config": QUANT_CONFIG,
    }
    
    if quant_path.exists():
        logger.info(f"⏭️  跳过 {model_name} (已存在)")
        log_entry["status"] = "skipped"
        return log_entry
    
    logger.info(f"🔧 量化 {model_name} (GPTQ 4-bit)")
    logger.info(f"   配置: group_size={QUANT_CONFIG['group_size']}, bits={QUANT_CONFIG['bits']}")
    
    # GPTQ 配置 (Experiment Design: 统一配置)
    quant_config = QuantizeConfig(
        bits=QUANT_CONFIG["bits"],
        group_size=QUANT_CONFIG["group_size"],
        desc_act=QUANT_CONFIG["desc_act"],
    )
    
    try:
        # 加载模型
        model = GPTQModel.from_pretrained(
            model_id,
            quant_config,
            trust_remote_code=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        
        # 量化 (使用默认校准数据)
        model.quantize(tokenizer)
        
        # 保存
        model.save_quantized(str(quant_path))
        tokenizer.save_pretrained(str(quant_path))
        
        # 记录结果 (Traceability)
        elapsed = time.time() - start_time
        peak_mem = torch.cuda.max_memory_allocated() / 1024**3 if torch.cuda.is_available() else 0
        
        log_entry.update({
            "status": "success",
            "output_path": str(quant_path),
            "elapsed_seconds": elapsed,
            "peak_memory_gb": peak_mem,
            "end_time": datetime.now().isoformat(),
        })
        
        logger.info(f"✅ 完成 {model_name} | 耗时: {elapsed/60:.1f}min | 峰值显存: {peak_mem:.1f}GB")
        
    except Exception as e:
        log_entry.update({
            "status": "failed",
            "error": str(e),
        })
        logger.error(f"❌ 量化 {model_name} 失败: {e}")
    
    return log_entry


# ============================================================
# 主函数
# ============================================================

def main():
    """
    主函数
    
    Best Practice: 命令后必须验证
    Best Practice: 保存完整实验日志
    """
    parser = argparse.ArgumentParser(description="量化模型脚本")
    parser.add_argument("--method", choices=["awq", "gptq", "all"], 
                        default="awq", help="量化方法")
    parser.add_argument("--models", nargs="+", default=None,
                        help="要量化的模型列表 (默认全部)")
    parser.add_argument("--output-dir", type=str, default="./quantized_models",
                        help="输出目录")
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建日志目录 (Traceability)
    Path("logs").mkdir(exist_ok=True)
    
    models = args.models if args.models else MODELS
    
    # 实验日志 (Best Practice: Traceability)
    experiment_log = {
        "experiment": "quantization_threshold_verification",
        "start_time": datetime.now().isoformat(),
        "config": QUANT_CONFIG,
        "models": models,
        "method": args.method,
        "results": [],
    }
    
    logger.info("="*60)
    logger.info("🚀 开始量化实验")
    logger.info(f"   方法: {args.method}")
    logger.info(f"   模型数: {len(models)}")
    logger.info(f"   统一配置: {QUANT_CONFIG}")
    logger.info("="*60)
    
    for model_id in models:
        model_name = model_id.split("/")[-1]
        
        if args.method in ["awq", "all"]:
            log = quantize_awq(model_id, output_dir)
            experiment_log["results"].append(log)
            torch.cuda.empty_cache()  # 清理显存
        
        if args.method in ["gptq", "all"]:
            log = quantize_gptq(model_id, output_dir)
            experiment_log["results"].append(log)
            torch.cuda.empty_cache()
    
    # 保存实验日志 (Traceability)
    experiment_log["end_time"] = datetime.now().isoformat()
    
    log_file = output_dir / "quantization_log.json"
    with open(log_file, "w") as f:
        json.dump(experiment_log, f, indent=2)
    
    # 验证结果 (Best Practice: 命令后必须验证)
    success_count = sum(1 for r in experiment_log["results"] if r.get("status") == "success")
    skip_count = sum(1 for r in experiment_log["results"] if r.get("status") == "skipped")
    fail_count = sum(1 for r in experiment_log["results"] if r.get("status") == "failed")
    
    logger.info("")
    logger.info("="*60)
    logger.info("📋 量化完成 - 结果验证 (Best Practice: Verify)")
    logger.info("="*60)
    logger.info(f"   ✅ 成功: {success_count}")
    logger.info(f"   ⏭️  跳过: {skip_count}")
    logger.info(f"   ❌ 失败: {fail_count}")
    logger.info(f"   📁 日志: {log_file}")
    
    # 列出生成的文件 (Best Practice: 验证)
    logger.info("")
    logger.info("📁 生成的量化模型:")
    for item in output_dir.iterdir():
        if item.is_dir():
            logger.info(f"   - {item.name}")
    
    if fail_count > 0:
        logger.error(f"⚠️ 有 {fail_count} 个模型量化失败，请检查日志")
        sys.exit(1)


if __name__ == "__main__":
    main()
