# 证据与复算方法

## 证据链

每项MI300X公开分数必须经过以下链路：

1. evaluator结果artifact；
2. 私有环境中的覆盖率与配置严格validator；
3. 证据SHA-256 manifest；
4. 原子完成Marker；
5. 公开的哈希化逐回答审计记录；
6. Repo validator和不可变Git commit。

中断但没有Marker的分块一律排除，即使进度条曾显示部分请求完成。

## 公开审计Schema

`data/raw-audit/<dataset>.jsonl`中的每行包含：

- `question_id`、`repeat_id`或明确的provenance限制；
- 二值`metric`；
- 可用时记录finish reason和Token metadata；
- prompt、ground truth、prediction、response和response ID的SHA-256；
- 私有源artifact索引。

公开记录不包含原始文本，避免重新分发benchmark题目、答案和模型生成内容。

## Provenance限制

- AIME有显式Repeat ID。
- CMMLU Repeat 0由已验证的单遍旧Canary推定；Repeat 1–2有显式provenance。
- MMLU-Redux有显式Repeat ID。
- SuperGPQA合同只有1遍；旧单回答记录明确标为推定。
- MinervaMath每题保留3个有序回答slot，但旧artifact没有显式Repeat ID。
- MMLU-Pro可以证明配置了2遍并验证聚合结果，但旧artifact无法给出逐Repeat归因。

这些限制不影响公开子集聚合准确率的复算，但不支持更强的逐Repeat结论。

## 独立复算

```bash
python scripts/validate_repo.py .
```

该命令验证：

- 六个数据集条目；
- 最终合同60,533题、134,239次回答；
- 当前快照3,216道已观察题、8,080次有效回答；
- 审计文件SHA、行数、二值metric、唯一审计键和准确率；
- 中英文README数字与机器可读唯一来源一致。

## Evaluator源码边界

由于没有找到允许公开重新分发完整evaluator文件的许可证，仓库不复制完整供应方evaluator源码。`patches/`提供精确统一diff和原始/修改后SHA；`scripts/prepare_mini_eval_smoke.py`是实际使用的patch工具。
