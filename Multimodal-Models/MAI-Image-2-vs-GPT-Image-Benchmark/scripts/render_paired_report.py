import argparse
import json
import re
from pathlib import Path

from summarize_paired_run import GROUPS, summarize


LABELS = ("MAI-Image-2.6", "GPT-Image-2 low", "GPT-Image-2 medium", "GPT-Image-2 high")


def table(headers, rows):
    if any(len(row) != len(headers) for row in rows):
        raise ValueError("Table row does not match its header")
    return "\n".join(["| " + " | ".join(headers) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |",
                      *("| " + " | ".join(str(value) for value in row) + " |" for row in rows)])


def round_rows(prompt_record, round_number):
    configurations = prompt_record["configurations"]
    if [item["group"] for item in configurations] != list(GROUPS):
        raise ValueError("Every scenario must contain all four configurations in display order")
    selected = []
    for configuration in configurations:
        matches = [row for row in configuration["rounds"] if row["round"] == round_number]
        if len(matches) != 1:
            raise ValueError("Every configuration must contain exactly one result for this round")
        selected.append(matches[0])
    return selected


def comparison_table(prompt_record, round_number, archive_path, language):
    rows = round_rows(prompt_record, round_number)
    images = []
    details = []
    for label, row in zip(LABELS, rows):
        if row["ok"]:
            if not row["image"]:
                raise ValueError("Successful sample is missing its original image")
            image_path = row["image"]
            expected_path = f"{GROUPS[len(images)]}/r{round_number}/{prompt_record['prompt_index']:02d}_test.png"
            if image_path != expected_path:
                raise ValueError("Displayed image does not belong to its configuration")
            alt = f"{label}, prompt {prompt_record['prompt_index']}, round {round_number}"
            images.append(f"![{alt}]({archive_path}/{image_path})")
            details.append(f"{row['request_seconds']:.2f} s<br>{row['image_kib']:.0f} KiB")
        else:
            if row["image"] is not None:
                raise ValueError("Failed sample cannot display a replacement image")
            images.append("未返回图片" if language == "zh" else "No image returned")
            details.append((f"{row['attempts']} 次尝试；任务耗时 {row['logical_request_seconds']:.2f} s"
                            if language == "zh" else
                            f"{row['attempts']} attempts; logical duration {row['logical_request_seconds']:.2f} s"))
    return table(LABELS, [images, details])


def prompt_latency_table(summary, language):
    headers = ["场景 / 轮次" if language == "zh" else "Scenario / round", *LABELS]
    rows = []
    for prompt_record in summary["per_prompt"]:
        for round_number in (1, 2):
            values = round_rows(prompt_record, round_number)
            rows.append([f"{prompt_record['prompt_index']:02d} / R{round_number}",
                         *(f"{row['request_seconds']:.2f}" if row["ok"] else
                           ("失败" if language == "zh" else "Failed") for row in values)])
    return table(headers, rows)


def number(value, decimals=2):
    return "N/A" if value is None else f"{value:,.{decimals}f}"


def metrics_table(summary, language):
    groups = summary["groups"]
    definitions = [
        ("成功 / 计划样本", "Successful / planned samples", lambda group: f"{group['successful_samples']} / {group['planned_samples']}"),
        ("首试成功 / 计划样本", "First-attempt successes / planned", lambda group: f"{group['first_attempt_successful_samples']} / {group['planned_samples']}"),
        ("HTTP 尝试次数 / 429", "HTTP attempts / 429 responses", lambda group: f"{group['formal_http_attempts']} / {group['http_429_attempts']}"),
        ("未成功的 HTTP 尝试", "Unsuccessful HTTP attempts", lambda group: str(group['unsuccessful_http_attempts'])),
        ("未成功尝试累计耗时 (s)", "Total unsuccessful attempt duration (s)", lambda group: number(group['unsuccessful_attempt_seconds'])),
        ("平均请求耗时 (s)", "Mean request latency (s)", lambda group: number((group['successful_request_latency'] or {}).get('mean_seconds'))),
        ("P50 / 描述性 P95 (s)", "P50 / descriptive P95 (s)", lambda group: number((group['successful_request_latency'] or {}).get('p50_seconds')) + " / " + number((group['successful_request_latency'] or {}).get('p95_seconds'))),
        ("样本标准差 (s)", "Sample standard deviation (s)", lambda group: number((group['successful_request_latency'] or {}).get('sample_stddev_seconds'))),
        ("最小 / 最大请求耗时 (s)", "Minimum / maximum request latency (s)", lambda group: number((group['successful_request_latency'] or {}).get('minimum_seconds')) + " / " + number((group['successful_request_latency'] or {}).get('maximum_seconds'))),
        ("第一轮 / 第二轮平均 (s)", "Round 1 / round 2 mean (s)", lambda group: " / ".join(number(item['latency']['mean_seconds']) if item['latency'] else "N/A" for item in group['per_round'])),
        ("全部样本平均任务耗时 (s)", "Mean logical duration, all samples (s)", lambda group: number(group['logical_request_latency_all_samples']['mean_seconds'])),
        ("成功图片平均大小 (KiB)", "Mean successful PNG size (KiB)", lambda group: number(group['mean_image_kib'], 0)),
    ]
    rows = []
    for chinese, english, value in definitions:
        rows.append([chinese if language == "zh" else english,
                     *(value(group) for group in groups)])
    return table(["指标" if language == "zh" else "Metric", *LABELS], rows)


def usage_table(summary, language):
    rows = []
    for label, group in zip(LABELS, summary["groups"]):
        tokens = group["returned_output_tokens"]
        token_label = str(tokens[0]) if len(tokens) == 1 else (f"{min(tokens)}-{max(tokens)}" if tokens else "N/A")
        rows.append([label, token_label, f"{group['successful_samples']}/{group['planned_samples']}"])
    headers = (["配置", "返回的输出 token", "成功 / 计划样本"] if language == "zh" else
               ["Configuration", "Returned output tokens", "Successful / planned samples"])
    return table(headers, rows)


def exception_section(summary, language):
    attempts = summary["unsuccessful_attempts"]
    if not attempts:
        return "本轮未记录失败尝试。" if language == "zh" else "No unsuccessful attempts were recorded."
    headers = (["样本", "尝试", "HTTP / 异常类型", "客户端耗时 (s)", "开始 (UTC)", "结束 (UTC)"]
               if language == "zh" else ["Sample", "Attempt", "HTTP / exception", "Client duration (s)", "Started (UTC)", "Finished (UTC)"])
    rows = [[attempt["sample_id"], str(attempt["attempt"]),
             attempt["exception_type"] or str(attempt["http_status"]), number(attempt["request_seconds"]),
             attempt["started_at_utc"], attempt["finished_at_utc"]] for attempt in attempts]
    longest = max(attempts, key=lambda attempt: attempt["request_seconds"])
    text = (f"最长的未成功尝试是 `{longest['sample_id']}`，客户端记录 {number(longest['request_seconds'])} 秒。"
            "这是请求调用的客户端经过时间，不是服务端 GPU 推理时长；底层原因未被这些日志确定。异常保留在任务耗时、请求计数和实际完成速率中，未返回图片的样本仍计入计划分母。"
            if language == "zh" else
            f"The longest unsuccessful attempt was `{longest['sample_id']}` at {number(longest['request_seconds'])} client-observed seconds. "
            "This is elapsed client request time, not server-side GPU inference duration; these logs do not establish the underlying cause. Exceptions remain in logical durations, attempt counts and observed completion rate, and missing-image samples remain in the planned denominator.")
    return text + "\n\n" + table(headers, rows)


def reproduction_section(archive_path, language):
    intro = ("需要可用的 MAI-Image-2.6 和 GPT-Image-2 部署。部署身份由您查询确认，不能仅凭 deployment 名称判断底层模型。先克隆仓库、拉取本项目的 Git LFS 文件，并在 Python 环境安装 requests："
             if language == "zh" else
             "Supply accessible MAI-Image-2.6 and GPT-Image-2 deployments. Verify their underlying model versions; deployment names alone are not model identity. Clone the repository, fetch this project's Git LFS inputs, and install requests in your Python environment:")
    credentials = ("下列两个资源根地址和 GPT deployment 名称由您填写。通过自己的秘密管理机制在当前进程提供 `AZURE_API_KEY`（MAI）和 `AZURE_OPENAI_API_KEY`（GPT），不要把值写入源码或 Git。各模型的版本、区域、SKU 和限额环境变量必须填写实际查询结果；下面展示本次实测元数据，不代表您的资源设置。"
                   if language == "zh" else
                   "Replace the two resource origins and GPT deployment name below. Supply `AZURE_API_KEY` (MAI) and `AZURE_OPENAI_API_KEY` (GPT) in the process through your secret-management mechanism, never source control. Model version, region, SKU and rate-limit metadata must match your verified deployments; the values below describe this measurement, not your resources.")
    continuation = ("第一条模型命令只预热四组，第二条从同一输出目录继续正式矩阵；均会消耗 Azure 服务用量。已有结果不会覆盖，已记录样本不会重跑。续跑要求同一脚本、提示词、端点和配置；中断时在途请求可能已被服务接收。新测试应在执行前保存脚本与 CSV，运行期间不得修改。"
                    if language == "zh" else
                    "The first model command runs four warmups; the second continues the same output directory through the formal matrix. Both consume Azure service usage. Existing results are not overwritten and recorded samples are not rerun. Resume requires unchanged script, prompts, endpoints and configuration. An interrupted in-flight request may already have reached the service. Save the script and CSV before each new run and keep them unchanged during execution.")
    tests = ("以下命令只重算已保存结果，不调用模型。回归覆盖四档请求、失败分母、原始 usage、图片归属和报告覆盖；模拟 HTTP 只用于离线单元测试，不是图像质量证据。新测批次的汇总与发布必须等全部计划样本结束。"
             if language == "zh" else
             "These commands validate saved evidence without model calls. Regressions cover request tiers, failure denominators, original usage, image ownership and report coverage. HTTP mocks exist only in offline tests and do not establish image quality. A new run cannot produce its final summary until every planned sample is recorded.")
    return f"""## {'复现与测试' if language == 'zh' else 'Reproduction and Tests'}

{intro}

```powershell
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark
git lfs install
git lfs pull --include="Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/**"
python -m pip install requests==2.34.2
```

{credentials}

```powershell
$env:MAI_ENDPOINT = 'https://<mai-resource>.services.ai.azure.com'
$env:GPT_ENDPOINT = 'https://<openai-resource>.openai.azure.com'
$env:GPT_DEPLOYMENT = '<gpt-image-2-deployment>'
$env:GPT_API_VERSION = '2025-04-01-preview'
$env:MAI_MODEL_VERSION = '2026-07-31'
$env:GPT_MODEL_VERSION = '2026-04-21'
$env:MAI_DEPLOYMENT_SKU = 'GlobalStandard'
$env:GPT_DEPLOYMENT_SKU = 'GlobalStandard'
$env:MAI_DEPLOYMENT_REGION = 'swedencentral'
$env:GPT_DEPLOYMENT_REGION = 'eastus2'
$env:MAI_RATE_LIMIT_RPM = '2.0'
$env:GPT_RATE_LIMIT_RPM = '2.0'
$env:BENCHMARK_CLIENT_LOCATION = 'Describe your actual client location'
python scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --dry-run
```

{continuation}

```powershell
$run = 'runs/paired-all-quality-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --resume
python scripts/summarize_paired_run.py $run
```

{tests}

```powershell
python scripts/summarize_paired_run.py {archive_path}
python scripts/render_paired_report.py {archive_path} --check
python -m unittest discover -s tests -v
```

{'执行脚本' if language == 'zh' else 'Runner'}: [benchmark_5way_v2.py](scripts/benchmark_5way_v2.py); {'离线汇总' if language == 'zh' else 'offline summary'}: [summarize_paired_run.py](scripts/summarize_paired_run.py); {'报告生成' if language == 'zh' else 'report rendering'}: [render_paired_report.py](scripts/render_paired_report.py); {'回归测试' if language == 'zh' else 'regressions'}: [tests](tests).
"""


def render_overview(summary, quality, archive_path, language):
    chinese = language == "zh"
    metadata = summary["config"]["group_configurations"]
    if [group["group"] for group in summary["groups"]] != list(GROUPS):
        raise ValueError("Metric columns must contain all four groups in order")
    title = "本轮：两模型与全部质量档位" if chinese else "Current Run: Both Models and All Quality Tiers"
    outcome = (f"本轮 {summary['successful_samples']}/{summary['formal_samples']} 个正式样本返回图片，{summary['failed_samples']} 个未返回图片；另有 {summary['warmup_samples']} 次预热，不计入正式分母。"
               if chinese else f"This run returned images for {summary['successful_samples']}/{summary['formal_samples']} formal samples; {summary['failed_samples']} returned no image. The {summary['warmup_samples']} warmups are excluded from the formal denominator.")
    boundary = ("同一客户端交替调用，提示词、尺寸和轮数相同；部署区域不同，不能把端到端耗时差全部归因于模型。质量是非盲评的具体画面观察，不是官方 benchmark 分数、人类偏好胜率或生产可靠性证明。"
                if chinese else "Requests were interleaved on the same client with identical prompts, dimensions and repetitions. Deployment regions differ, so end-to-end latency differences cannot be attributed solely to the models. Quality observations are unblinded, not an official benchmark score, human-preference win rate or production reliability claim.")
    contract = table(["配置" if chinese else "Configuration", "模型版本" if chinese else "Model version",
                      "质量参数" if chinese else "Quality field", "尺寸" if chinese else "Dimensions",
                      "区域" if chinese else "Resource region", "正式样本" if chinese else "Formal samples"], [
        [label, item.get("model_version") or "not recorded", item["quality"] or ("未传入" if chinese else "omitted"),
         "1024x1024", item.get("deployment_region") or "not recorded", str(group["planned_samples"])]
        for label, item, group in zip(LABELS, metadata, summary["groups"])])
    procedure = ("输入是原报告同一份 11 题 CSV。每组先用 `blue circle` 预热一次；第一轮每题依次调用 MAI、GPT low、medium、high，第二轮反转。并发为 1，每次逻辑调用后间隔 5 秒，最多尝试 3 次，沿用原重试退避。两个 GlobalStandard 部署各配置每分钟 2 次请求；GPT 三档共享同一部署和限额。MAI 请求超时 180 秒，GPT 为 300 秒。"
                 if chinese else "The original eleven-prompt CSV is unchanged. Each configuration receives one `blue circle` warmup. Each prompt runs MAI, GPT low, medium, high in round 1, with reversed configuration order in round 2. Concurrency is 1, with 5 seconds after each logical call and at most 3 attempts under the original retry backoff. Each GlobalStandard deployment is configured for 2 requests/minute; GPT tiers share one deployment and limit. Request timeouts are 180 seconds for MAI and 300 for GPT.")
    timing = ("请求耗时从 `requests.post` 调用前到完整 HTTP 响应返回，只统计有图片的成功尝试，不包含后续 JSON/base64 处理和文件写盘。任务耗时覆盖失败尝试、重试等待和响应处理，按全部计划样本统计。失败不以 0 秒进入速度平均值，也不从成功率分母删除。P95 为每组最多 22 个值的描述性线性插值，不是生产尾延迟保证。"
              if chinese else "Request latency measures `requests.post` through receipt of the complete HTTP response, before JSON/base64 processing and file writes, for successful image-producing attempts only. Logical duration includes failed attempts, retry waits and response processing across all planned samples. Failures are not averaged as zero-second responses or removed from the success-rate denominator. P95 is descriptive linear interpolation over at most 22 observations per group, not a production tail guarantee.")
    usage_scope = ("token 用量取自接口返回的 usage，不从模型或档位推算。没有返回值的样本不补零。输出 token 数和 PNG 文件大小都不能单独证明画质。"
                   if chinese else "Token counts come from returned usage, not assumptions about the model or tier. Missing values are not replaced with zero. Output-token counts and PNG byte sizes do not independently establish image quality.")
    row_names = ["场景" if chinese else "Scenario", *LABELS]
    observation_rows = [[str(item["prompt_index"]), *(item["observations"][group][language] for group in GROUPS)]
                        for item in quality["per_prompt"]]
    observations = table(row_names, observation_rows)
    api = table(["接口项目" if chinese else "API item", "MAI-Image-2.6", "GPT-Image-2"], [
        ["POST", "`/mai/v1/images/generations`", "`/openai/deployments/{deployment}/images/generations?api-version=2025-04-01-preview`"],
        ["Payload", "`model`, `prompt`, `width=1024`, `height=1024`", "`prompt`, `n=1`, `size=1024x1024`, `quality=low/medium/high`"],
        ["Auth", "`api-key`", "`api-key`"],
        ["Output", "`data[0].b64_json`, PNG", "`data[0].b64_json`, PNG"],
        ["Usage", "`usage.num_input_text_tokens`, `usage.num_output_tokens`", "`usage.input_tokens_details`, `usage.output_tokens_details`"],
    ])
    limits = ("本报告只对比 MAI-Image-2.6 与 GPT-Image-2 的 low、medium、high 三档。范围为 11 个文生图场景与 1024x1024，不包括 2K、图像编辑、多图参考、文字准确率专项、并发压测或其他认证方式。MAI 没有传质量参数，不能称为 GPT high 的等价档位。所有指标只使用本次四组测试的数据。"
              if chinese else "This report compares only MAI-Image-2.6 and GPT-Image-2 at low, medium and high. Scope is eleven text-to-image scenarios at 1024x1024, excluding 2K, editing, multiple reference images, exact-text accuracy, concurrency capacity and other authentication modes. MAI sends no quality parameter and is not labeled as equivalent to GPT high. Every metric uses this four-configuration run only.")
    heading = lambda english, localized: localized if chinese else english
    return f"""## {title}

[{'English' if chinese else '中文'}]({'README.md' if chinese else 'README-CN.md'}) | [{'逐题图片' if chinese else 'Side-by-side images'}](#{'并排图片对比' if chinese else 'side-by-side-image-comparison'}) | [{'测量记录' if chinese else 'Measurements'}]({archive_path}/5way_v2_results.json) | [{'指标' if chinese else 'Metrics'}]({archive_path}/summary.json) | [{'请求记录' if chinese else 'Attempts'}]({archive_path}/attempts.jsonl)

**{outcome}** {boundary}

### {heading('Test Contract', '测试口径')}

{contract}

{procedure}

{'客户端' if chinese else 'Client'}: {summary['environment']['platform']}, {summary['environment']['architecture']}, Python {summary['environment']['python']}, requests {summary['environment']['requests']}.

{'正式起止时间 (UTC)' if chinese else 'Formal interval (UTC)'}: `{summary['formal_started_at_utc']}` to `{summary['formal_ended_at_utc']}`. {'正式窗口含等待' if chinese else 'Formal window including waits'}: **{number(summary['formal_window_seconds_including_waits'])} s**. {'四组合计观测完成速率' if chinese else 'Observed mixed-workload completion rate'}: **{number(summary['mixed_workload_observed_images_per_minute'])} {'张/分钟' if chinese else 'images/min'}** ({'不是单模型或最大吞吐' if chinese else 'not per-model or maximum throughput'}).

### {heading('Architecture and Measurement Boundary', '调用链与计时边界')}

```mermaid
flowchart LR
    prompts["Original 11 prompts"] --> runner["Local Windows Python runner"]
    runner --> mai["MAI-Image-2.6 / Sweden Central"]
    runner --> gpt["GPT-Image-2 / East US 2 / low, medium, high"]
    mai --> evidence["PNG, usage, request IDs, timestamps, failures"]
    gpt --> evidence
    evidence --> summary["Offline validation and report"]
```

{'原创解释图：本项目实际客户端与服务调用关系，不描绘模型内部结构。' if chinese else 'Original explanatory diagram of this project\'s client/service calls, not model internals.'} [MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image) | [GPT image API](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/dall-e).

### {heading('Performance and Reliability', '耗时与请求成功情况')}

{metrics_table(summary, language)}

{timing}

### {heading('Exceptions and Waiting', '异常与等待')}

{exception_section(summary, language)}

### {heading('Token Usage', 'Token 用量')}

{usage_table(summary, language)}

{usage_scope}

### {heading('Every Scenario, Both Rounds', '逐场景两轮耗时')}

{'单位为秒；失败格对应原始请求记录，不用其他轮次替换。' if chinese else 'Seconds; failed cells remain tied to their original requests and are not replaced by another round.'}

{prompt_latency_table(summary, language)}

### {heading('Quality Observations', '逐场景画面观察')}

{'仅为 AI 辅助非盲评。每格记录实际画面差异，不生成数值质量评分。' if chinese else 'AI-assisted, unblinded inspection only. Each cell describes observed image differences, not a numeric quality score.'} [{'检查记录' if chinese else 'Inspection record'}]({archive_path}/quality-review.json).

{observations}

### {heading('Measured API Settings', '本轮实际接口设置')}

{api}

{reproduction_section(archive_path, language)}

### {heading('Limits', '结论边界')}

{limits}

{'证据目录' if chinese else 'Evidence directory'}: [{archive_path}]({archive_path}). {'包含原始图片、测量记录、逐次请求、响应元数据及删减后的公开源码副本。非财务测量字段和图片保持不变；原始执行哈希与公开文件哈希分别记录于' if chinese else 'Contains original images, measurement records, attempts, response metadata and a redacted public source copy. Non-financial measurement fields and image bytes are unchanged; original execution hashes and published-file hashes are recorded separately in'} [{'来源说明' if chinese else 'provenance'}]({archive_path}/provenance.json). {'提示词 SHA-256' if chinese else 'Prompt SHA-256'}: `{summary['prompts_sha256']}`.
"""


def update_document(text, summary, quality, archive_path, language):
    chinese = language == "zh"
    title = ("# MAI-Image-2.6 与 GPT-Image-2：全质量档位图像生成对比" if chinese else
             "# MAI-Image-2.6 vs GPT-Image-2: All Quality Tiers")
    author = re.search(r"(?m)^> \*\*(?:Author|作者)\*\*:[^\n]+", text)
    if author is None:
        raise ValueError("Existing report author attribution was not found")
    titles = {int(index): heading.strip() for index, heading in
              re.findall(r"(?m)^### Test (\d+): ([^\n]+)$", text)}
    if set(titles) != set(range(1, 12)) or [item["prompt_index"] for item in summary["per_prompt"]] != list(range(1, 12)):
        raise ValueError("All eleven original scenarios are required")
    content = render_overview(summary, quality, archive_path, language)
    comparison_heading = "## 并排图片对比" if chinese else "## Side-by-Side Image Comparison"
    description = ("每个场景、每一轮只展示 MAI-Image-2.6 与 GPT-Image-2 low、medium、high。图片来自本次四组测试，未返回图片的格子保留失败说明。点击图片查看原始 1024x1024 PNG。"
                   if chinese else "Every scenario and round compares only MAI-Image-2.6 with GPT-Image-2 low, medium and high. Images come from this four-configuration run; missing images retain their failure record. Click an image for the original 1024x1024 PNG.")
    sections = [title, author.group(), content.strip(), comparison_heading, description]
    for prompt_record in summary["per_prompt"]:
        prompt_index = prompt_record["prompt_index"]
        sections.extend([f"### Test {prompt_index}: {titles[prompt_index]}",
                         "> **Prompt**: " + prompt_record["prompt"]])
        for round_number in (1, 2):
            sections.extend([f"**Round {round_number}:**",
                             comparison_table(prompt_record, round_number, archive_path, language)])
    return "\n\n".join(sections) + "\n"


def validate_quality(summary, quality):
    if quality.get("result_sha256") != summary["result_sha256"]:
        raise ValueError("Visual review does not belong to the current measured results")
    expected_images = {row["image"] for prompt in summary["per_prompt"] for group in prompt["configurations"]
                       for row in group["rounds"] if row["ok"]}
    if set(quality.get("inspected_images", [])) != expected_images:
        raise ValueError("Visual inspection must cover every returned formal image")
    if [item["prompt_index"] for item in quality.get("per_prompt", [])] != list(range(1, 12)):
        raise ValueError("Visual review is missing an original scenario")
    for item in quality["per_prompt"]:
        if set(item["observations"]) != set(GROUPS):
            raise ValueError("Visual review must cover all four configurations")
        if any(not item["observations"][group].get(language) for group in GROUPS for language in ("en", "zh")):
            raise ValueError("Visual review needs both language observations")


def main():
    parser = argparse.ArgumentParser(description="Generate both language reports from one validated paired image run.")
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--check", action="store_true", help="Check generated content without editing either README.")
    parser.add_argument("--validate-review-only", action="store_true", help="Validate run and visual coverage without rendering or editing reports.")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run_directory = arguments.run_directory.resolve()
    summary = summarize(run_directory, root / "prompts.csv")
    quality = json.loads((run_directory / "quality-review.json").read_text("utf-8"))
    validate_quality(summary, quality)
    if arguments.validate_review_only:
        print(json.dumps({"status": "PASS", "formal_samples": summary["formal_samples"],
                          "inspected_images": len(quality["inspected_images"]), "scenarios": len(quality["per_prompt"])}))
        return
    archive_path = run_directory.relative_to(root).as_posix()
    documents = []
    for filename, language in (("README.md", "en"), ("README-CN.md", "zh")):
        path = root / filename
        original = path.read_text("utf-8")
        generated = update_document(original, summary, quality, archive_path, language)
        documents.append((path, original, generated))
    if arguments.check:
        changed = [path.name for path, original, generated in documents if original != generated]
        if changed:
            raise SystemExit("Report differs from current evidence: " + ", ".join(changed))
    else:
        for path, _, generated in documents:
            path.write_text(generated, encoding="utf-8")
    print(json.dumps({"status": "PASS", "formal_samples": summary["formal_samples"],
                      "configurations": len(GROUPS), "scenario_round_tables_per_language": len(summary["per_prompt"]) * 2}))


if __name__ == "__main__":
    main()