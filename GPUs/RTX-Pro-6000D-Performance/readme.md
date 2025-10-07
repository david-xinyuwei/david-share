## RTX 

![images](https://github.com/david-xinyuwei/Backend-of-david-share/blob/main/GPUs/RTX-6000/images/1.jpg)

之前有同事和客户问过RTX Pro 6000D这个卡的性能，目前我们内部还没找到很细的slides。我找了一些信息总结了一下仅供参考。RTX Pro 6000D: L20   **≈3.4倍 场景（Qwen3 30B 对比）**

- 模型：Qwen3‑30B
- 输入/输出：4K token prompt，1K token 输出
- 延迟目标：单 token 延迟（TPOT）< 50ms
- 精度/量化：
  - RTX 6000D：FP4 权重 + FP8 注意力
  - L20：FP8 权重 + FP8 注意力
- 并发配置（IFB 并发数 CC）：
  - RTX 6000D：≈128
  - L20：≈32
- 并行策略：两者都能单卡运行（TP=1，无跨卡通信）

![images](https://github.com/david-xinyuwei/Backend-of-david-share/blob/main/GPUs/RTX-6000/images/2.jpg)

------

**RTX Pro 6000D: L20  ≈6.4倍 场景（Qwen3 32B 对比）**

- 模型：Qwen3‑32B
- 输入/输出：4K token prompt，1K token 输出
- 延迟目标：单 token 延迟（TPOT）< 50ms
- 精度/量化：
  - RTX 6000D：FP4 权重 + FP8 注意力
  - L20：FP8 权重 + FP8 注意力
- 并发配置（IFB 并发数 CC）：
  - RTX 6000D：≈32
  - L20：≈8–16（受显存限制降低并发）
- 并行策略：
  - RTX 6000D：单卡运行（TP=1）
  - L20：显存不足需 TP=2（张量并行 2 卡），存在跨卡通信开销

![images](https://github.com/david-xinyuwei/Backend-of-david-share/blob/main/GPUs/RTX-6000/images/3.jpg)

![images](https://github.com/david-xinyuwei/Backend-of-david-share/blob/main/GPUs/RTX-6000/images/4.jpg)

![images](https://github.com/david-xinyuwei/Backend-of-david-share/blob/main/GPUs/RTX-6000/images/5.jpg)

![images](https://github.com/david-xinyuwei/Backend-of-david-share/blob/main/GPUs/RTX-6000/images/6.jpg)

![images](https://github.com/david-xinyuwei/Backend-of-david-share/blob/main/GPUs/RTX-6000/images/7.jpg)