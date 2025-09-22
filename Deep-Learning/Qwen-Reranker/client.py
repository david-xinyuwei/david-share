#!/usr/bin/env python3
import asyncio
import aiohttp
import time
import statistics
import signal
import os
import random
import csv
from datetime import datetime

# 确保用真实 libnvidia-ml.so
os.environ["LD_LIBRARY_PATH"] = "/usr/lib/x86_64-linux-gnu:" + os.environ.get("LD_LIBRARY_PATH", "")

try:
    import pynvml as nvml
    nvml.nvmlInit()
    NVML_AVAILABLE = True
    print("✅ NVML 初始化成功，GPU监控可用")
except Exception as e:
    NVML_AVAILABLE = False
    print(f"⚠️ NVML 初始化失败: {e}")

class GPUMonitor:
    def __init__(self, sample_interval=0.5):
        self.sample_interval = sample_interval
        self.gpu_handle = None
        self.monitoring = False
        self.stats = []
        if NVML_AVAILABLE:
            try:
                self.gpu_handle = nvml.nvmlDeviceGetHandleByIndex(0)
                print("✅ GPU监控已启用")
            except Exception as e:
                print(f"⚠️ GPU监控初始化失败: {e}")

    def start(self):
        if not self.gpu_handle:
            return
        self.monitoring = True
        import threading
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.monitoring = False
        time.sleep(0.1)

    def _loop(self):
        while self.monitoring:
            self.stats.append(self._current())
            if len(self.stats) > 1000:
                self.stats.pop(0)
            time.sleep(self.sample_interval)

    def _current(self):
        if not self.gpu_handle:
            return {"gpu_utilization": 0.0}
        util = nvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
        return {"gpu_utilization": float(util.gpu)}

    def summary(self):
        if not self.stats:
            return {"gpu_utilization_avg": 0.0, "gpu_utilization_max": 0.0}
        gpu_vals = [s["gpu_utilization"] for s in self.stats]
        return {
            "gpu_utilization_avg": statistics.mean(gpu_vals),
            "gpu_utilization_max": max(gpu_vals)
        }

class AdaptiveLoadTester:
    def __init__(self, base_url="http://localhost:8000", timeout_seconds=30,
                 max_concurrency=2048, start_concurrency=2, requests_per_user=10):
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_concurrency = max_concurrency
        self.start_concurrency = start_concurrency
        self.requests_per_user = requests_per_user
        self.session = None
        self.monitor = GPUMonitor()
        self.stop_requested = False
        self.performance_history = []
        signal.signal(signal.SIGINT, self._sig_stop)
        signal.signal(signal.SIGTERM, self._sig_stop)
        self.documents = self._generate_test_docs()
        self.csv_file = f"h100_reranker_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._init_csv()

    def _sig_stop(self, *args):
        print("\n🛑 停止测试")
        self.stop_requested = True

    def _init_csv(self):
        with open(self.csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "concurrency", "total_requests", "successful_requests", "failed_requests",
                "success_rate", "tps", "docs_per_sec", "tokens_per_sec",
                "avg_rt_ms", "p95_rt_ms",
                "gpu_util_avg", "gpu_util_max"
            ])

    def _save_csv_row(self, stats):
        with open(self.csv_file, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                stats['concurrency'],
                stats['total_requests'],
                stats['successful_requests'],
                stats['failed_requests'],
                f"{stats['success_rate']:.2f}",
                f"{stats['tps']:.2f}",
                f"{stats['docs_per_sec']:.2f}",
                f"{stats['tokens_per_sec']:.2f}",
                f"{stats['avg_rt']*1000:.2f}",
                f"{stats['p95_rt']*1000:.2f}",
                f"{stats['gpu_utilization_avg']:.2f}",
                f"{stats['gpu_utilization_max']:.2f}"
            ])

    def _generate_test_docs(self):
        short_docs = [
            "AI是智能机器的科学工程。",
            "机器学习是AI的一个子集。",
            "深度学习使用多层神经网络。",
            "自然语言处理让机器理解人类语言。",
            "计算机视觉使计算机理解图片和视频。"
        ]
        medium_docs = [
            "人工智能是计算机科学的一个分支，包括学习、推理和语言理解等，广泛用于机器人、自动化、推荐系统等领域。",
            "机器学习无需显性编程，通过数据训练模型，常用在金融风控、图像识别、自然语言处理等场景。",
            "深度学习用多层神经网络模拟人脑处理复杂数据的过程，尤其在图像和语音领域表现突出。"
        ]
        long_docs = [
            "大型语言模型(LLM)基于Transformer架构，通过对大量文本数据进行训练，学会语言的统计规律，可以进行文本生成、问答、翻译、代码辅助等任务。",
            "区块链是一种分布式账本技术，通过加密和共识机制保证数据不可篡改和透明性，应用于数字货币、供应链追溯等领域。"
        ]
        extra_long_docs = [
            "元宇宙是集成虚拟现实、增强现实、人工智能、区块链的沉浸式数字世界，用户可生成和交换数字资产，进行社交、娱乐、学习等活动。",
            "量子计算利用量子比特的叠加和纠缠特性，能够在某些问题上比传统计算机更快，虽然目前仍处于研究阶段，但在密码学、材料科学等领域潜力巨大。"
        ]
        docs = short_docs * 50 + medium_docs * 40 + long_docs * 30 + extra_long_docs * 20
        related_docs = [f"这是关于AI应用和挑战的特别相关文档 {i}" for i in range(50)]
        docs.extend(related_docs)
        random.shuffle(docs)
        return docs

    async def create_session(self):
        connector = aiohttp.TCPConnector(limit=5000, limit_per_host=5000)
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)

    async def close_session(self):
        if self.session:
            await self.session.close()

    async def single_request(self, query, documents, print_example=False):
        payload = {"query": query, "documents": documents}
        start_t = time.time()
        try:
            async with self.session.post(f"{self.base_url}/rerank", json=payload) as resp:
                rt = time.time() - start_t
                if resp.status == 200:
                    data = await resp.json()
                    if print_example:
                        print("🔹 示例返回 scores:", data.get("scores", []))
                        print("🔹 示例返回 top1 文档:", data.get("documents", [])[0] if data.get("documents") else None)
                    return {"success": True, "rt": rt, "tokens": sum(len(d) for d in documents)}
                else:
                    return {"success": False, "rt": rt, "tokens": 0}
        except Exception:
            return {"success": False, "rt": time.time() - start_t, "tokens": 0}

    async def run_stage(self, concurrency):
        docs = random.sample(self.documents, 50)
        total_requests = concurrency * self.requests_per_user
        sem = asyncio.Semaphore(concurrency)
        counter = 0

        async def bound_req():
            nonlocal counter
            async with sem:
                counter += 1
                return await self.single_request("AI应用和挑战有哪些？", docs, print_example=(counter == 1))

        self.monitor.start()
        start = time.time()
        tasks = [bound_req() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks)
        total_t = time.time() - start
        self.monitor.stop()

        succ = [r for r in results if r["success"]]
        fail = [r for r in results if not r["success"]]
        success_rate = (len(succ) / len(results) * 100) if results else 0
        tokens_total = sum(r["tokens"] for r in succ)

        rts = [r["rt"] for r in succ]
        avg_rt = statistics.mean(rts) if rts else 0
        p95_rt = statistics.quantiles(rts, n=20)[18] if len(rts) > 20 else (max(rts) if rts else 0)

        gpu_stats = self.monitor.summary()

        stats = {
            "concurrency": concurrency,
            "total_requests": len(results),
            "successful_requests": len(succ),
            "failed_requests": len(fail),
            "success_rate": success_rate,
            "tps": len(succ) / total_t if total_t > 0 else 0,
            "docs_per_sec": len(succ) * len(docs) / total_t if total_t > 0 else 0,
            "tokens_per_sec": tokens_total / total_t if total_t > 0 else 0,
            "avg_rt": avg_rt,
            "p95_rt": p95_rt
        }
        stats.update(gpu_stats)
        self.performance_history.append(stats)
        self._save_csv_row(stats)
        return stats

async def main():
    tester = AdaptiveLoadTester()
    await tester.create_session()

    concurrency = tester.start_concurrency
    while concurrency <= tester.max_concurrency and not tester.stop_requested:
        print(f"\n[并发 {concurrency}] 测试中 ... (总请求数: {concurrency * tester.requests_per_user})")
        stats = await tester.run_stage(concurrency)
        print(f"TPS: {stats['tps']:.2f}, Docs/s: {stats['docs_per_sec']:.2f}, Tokens/s: {stats['tokens_per_sec']:.2f}")
        print(f"成功率: {stats['success_rate']:.1f}% ({stats['successful_requests']}/{stats['total_requests']})")
        print(f"延迟: 平均 {stats['avg_rt']*1000:.1f} ms, P95 {stats['p95_rt']*1000:.1f} ms")
        print(f"GPU利用率: 平均 {stats['gpu_utilization_avg']:.1f}%, 峰值 {stats['gpu_utilization_max']:.1f}%")

        if stats['gpu_utilization_avg'] >= 90 or stats['success_rate'] < 95:
            break
        concurrency *= 2

    best = max(tester.performance_history, key=lambda x: x['tps'])
    print("\n🏆 最佳性能配置:")
    print(f"最优并发: {best['concurrency']}")
    print(f"最大TPS: {best['tps']:.2f}")
    print(f"Docs/s: {best['docs_per_sec']:.2f}, Tokens/s: {best['tokens_per_sec']:.2f}")
    print(f"延迟: 平均 {best['avg_rt']*1000:.1f} ms, P95 {best['p95_rt']*1000:.1f} ms")
    print(f"成功率: {best['success_rate']:.1f}%")
    print(f"GPU利用率: 平均 {best['gpu_utilization_avg']:.1f}%, 峰值 {best['gpu_utilization_max']:.1f}%")

    print(f"\n📁 测试数据已保存到: {tester.csv_file}")
    await tester.close_session()

if __name__ == "__main__":
    asyncio.run(main())