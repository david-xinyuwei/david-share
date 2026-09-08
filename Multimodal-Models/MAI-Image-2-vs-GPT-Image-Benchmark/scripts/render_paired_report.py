import argparse
import json
import re
import statistics
from pathlib import Path

from summarize_paired_run import GROUPS, summarize
from summarize_web_grounding import summarize as summarize_grounding
from summarize_multi_image_edit import summarize as summarize_multi_image


LABELS = ("MAI-Image-2.6", "GPT-Image-2 low", "GPT-Image-2 medium", "GPT-Image-2 high")
GROUNDING_ARCHIVE = "data/lenovo-web-grounding-20260908"
MULTI_IMAGE_ARCHIVE = "data/mai-multi-image-edit-20260908"


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


def reproduction_section(archive_path, language, grounding_archive=None, multi_image_archive=None):
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
    grounding = ""
    if grounding_archive:
        grounding = "\n\n".join([
            ("联网信息补充测试只需 MAI 部署。第一条只读核验已有归档；第二条只检查参数；第三条才真实重跑完整三题，结果写入新目录，不覆盖已发布数据。"
             if language == "zh" else
             "The web-grounding test needs only the MAI deployment. The first command verifies the existing archive without writing; the second checks parameters without network calls; only the third reruns all three subjects into a new directory, leaving published data unchanged."),
            grounding_reproduction_commands(grounding_archive)])
    multi_image = ""
    if multi_image_archive:
        multi_image = "\n\n".join([
            ("多图输入测试只需 MAI 部署。第一条只读核验已有证据并检查 PNG 是否含 alpha 通道；"
             "后三条会真实调用接口重跑能力组、字段校验与张数探测，并写入各自的输出目录。"
             if language == "zh" else
             "The multi-image test needs only the MAI deployment. The first command verifies the saved evidence "
             "and checks whether the PNGs carry an alpha channel; the remaining three call the API to rerun the "
             "capability group, the field validation and the count probe into their own output directories."),
            multi_image_reproduction_commands(multi_image_archive)])
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

{grounding}

{multi_image}

{'执行脚本' if language == 'zh' else 'Runner'}: [benchmark_5way_v2.py](scripts/benchmark_5way_v2.py); {'离线汇总' if language == 'zh' else 'offline summary'}: [summarize_paired_run.py](scripts/summarize_paired_run.py); {'报告生成' if language == 'zh' else 'report rendering'}: [render_paired_report.py](scripts/render_paired_report.py); {'回归测试' if language == 'zh' else 'regressions'}: [tests](tests).
"""


def render_overview(summary, quality, archive_path, language, grounding_section="",
                    multi_image_section=""):
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

{grounding_section}

{multi_image_section}

### {heading('Measured API Settings', '本轮实际接口设置')}

{api}

{reproduction_section(archive_path, language, GROUNDING_ARCHIVE if grounding_section else None, MULTI_IMAGE_ARCHIVE if multi_image_section else None)}

### {heading('Limits', '结论边界')}

{limits}

{'证据目录' if chinese else 'Evidence directory'}: [{archive_path}]({archive_path}). {'包含原始图片、测量记录、逐次请求、响应元数据及删减后的公开源码副本。非财务测量字段和图片保持不变；原始执行哈希与公开文件哈希分别记录于' if chinese else 'Contains original images, measurement records, attempts, response metadata and a redacted public source copy. Non-financial measurement fields and image bytes are unchanged; original execution hashes and published-file hashes are recorded separately in'} [{'来源说明' if chinese else 'provenance'}]({archive_path}/provenance.json). {'提示词 SHA-256' if chinese else 'Prompt SHA-256'}: `{summary['prompts_sha256']}`.
"""


def render_multi_image_section(summary, archive_path, language):
    """Render the input-count section: capability arms first, then attribution."""
    chinese = language == "zh"
    if summary["transparent_cutout_supported"]:
        raise ValueError("Alpha channel found; the cutout wording below would be wrong")
    capability = {entry["image_count"]: entry for entry in summary["capability"]}
    attribution = {entry["label"]: entry for entry in summary["attribution"]}
    limit = summary["contract"]["service_limit_message"]
    quota = summary["contract"]["quota_limited_counts"]

    intro = (
        "本节测试 `/mai/v1/images/edits` 接受几张参考图。官方参数表把 `image` 标为 `string`、"
        "描述为 the image，既没有多图说明也没有张数上限，因此下列张数与字段规则取自服务端自身的校验消息，"
        "属实测结果，不是官方支持承诺。"
        if chinese else
        "This section measures how many reference images `/mai/v1/images/edits` accepts. The official parameter "
        "table types `image` as a `string` described as \"the image\", with no multi-image statement and no count "
        "limit, so the counts and field rules below come from the service's own validation messages. They are "
        "measured behaviour, not an official support commitment."
    )
    capability_note = (
        "能力组给每种输入配一条它能满足的提示词：单图用单数指令，双图用双数指令。"
        "两次提示词不同，因此本组只展示各自用法的实际效果，不能把差异归因于第二张图。"
        if chinese else
        "The capability group gives each input count a prompt it can satisfy: a singular instruction for one image "
        "and a plural instruction for two. The prompts differ, so this group shows what each usage returns and "
        "cannot attribute a difference to the second image."
    )
    capability_rows = [
        [("单图输入 `image` x 1" if chinese else "One image, `image` x 1"),
         f"`{capability[1]['prompt']}`", f"{capability[1]['request_seconds']} s",
         f"{capability[1]['png']['bytes']:,} bytes"],
        [("双图输入 `image` x 2" if chinese else "Two images, `image` x 2"),
         f"`{capability[2]['prompt']}`", f"{capability[2]['request_seconds']} s",
         f"{capability[2]['png']['bytes']:,} bytes"],
    ]
    attribution_note = (
        "归因组固定同一条提示词，只更换输入图，并同时保留两条单图臂，使对照对称。"
        "该提示词对单张输入是欠定的，因此本组只用于归因，不代表单图编辑质量。"
        if chinese else
        "The attribution group holds one prompt constant and changes only the images, keeping both single-image "
        "arms so the comparison is symmetric. That prompt is under-determined for a single input, so this group "
        "measures attribution only and is not evidence of single-image edit quality."
    )
    attribution_rows = [
        [("只给输入图 1" if chinese else "Image 1 only"), "1",
         f"{attribution['single_image']['request_seconds']} s",
         ("仅紫色机身，无第二张图元素" if chinese else "Purple chassis only, no elements from image 2")],
        [("只给输入图 2" if chinese else "Image 2 only"), "1",
         f"{attribution['fixed_prompt_image_two_only']['request_seconds']} s",
         ("仅输入图 2 的设备，无紫色机身" if chinese else "Only the image-2 device, no purple chassis")],
        [("同时给两张" if chinese else "Both images"), "2",
         f"{attribution['two_image_fields']['request_seconds']} s",
         ("两张图各自的设备与模式排列同时出现" if chinese else
          "Devices and mode row from both images appear together")],
    ]
    attribution_prompt = summary["attribution_prompts"][0]
    attribution_finding = (
        "每张输入图的独有元素只在该图在场时出现，因此第二张图被读取并影响了生成结果，不是被静默忽略。"
        if chinese else
        "Each image's unique elements appear only when that image is present, so the second image was read and "
        "influenced the result rather than being silently ignored."
    )
    contract_rows = [
        ["`image` x 1", "200", ("返回图片" if chinese else "Returned an image")],
        ["`image` x 2", "200", ("返回图片，第二张图生效" if chinese else "Returned an image; the second image took effect")],
        [f"`image` x {', '.join(str(count) for count in sorted(quota))}", "429",
         ("配额限制（本部署 2 RPM），既非能力否证也非支持证明" if chinese else
          "Quota limit (2 RPM on this deployment); neither a capability refutation nor proof of support")],
        ["`image` x 9", "400", f"`{limit}`"],
        [("不传图片" if chinese else "No image field"), "400", f"`{limit}`"],
        ["`image[]`, `images`, `image1`+`image2`, `image_a`+`image_b`, `reference`", "400",
         f"`{summary['contract']['field_prefix_message']}`"],
    ]
    field_boundary = (
        "服务端提示字段名需以 `image` 开头，但 `image1`、`image_a`、`image[]`、`images` 实测均被拒，"
        "实际只接受重复命名为 `image` 的字段。上限 1–5 取自服务端消息；3 与 5 张因配额未取得成功样本。"
        if chinese else
        "The service says the field name must start with `image`, yet `image1`, `image_a`, `image[]` and `images` "
        "were all rejected, so only repeated fields named `image` are accepted. The 1–5 range comes from the "
        "service message; no successful sample was obtained for 3 or 5 images because of the quota."
    )
    cutout_boundary = (
        f"三张输出均为 PNG colour type {capability[1]['png']['colour_type']}，文件不含 alpha 通道，"
        "四角为不透明近白像素。因此白色背景是模型画出来的背景，不是透明区域，用于合成仍需另行抠图。"
        "接口没有 `background` 或 `output_format` 参数可要求透明输出，也没有 `mask` 参数，"
        "无法指定各输入图的哪一部分进入结果；输出是重新生成的画面，不是图像拼接。"
        if chinese else
        f"All three outputs are PNG colour type {capability[1]['png']['colour_type']} with no alpha channel and "
        "opaque near-white corners. The white background is drawn by the model, not transparency, so compositing "
        "still requires a separate cutout. The API exposes no `background` or `output_format` parameter to request "
        "transparency and no `mask` parameter to select which part of each input is used; the output is a "
        "regenerated image, not a composite."
    )
    repeatability = (
        "每种组合各调用一次，未做重复性验证；`MAI-Image-2.6` 为 Preview，无 SLA，接口行为可能变化。"
        "耗时为客户端 `requests.post` 往返时间，不是服务端推理时长。"
        if chinese else
        "Each combination was called once with no repeatability check. `MAI-Image-2.6` is in preview with no SLA "
        "and its behaviour may change. Latency is client-side `requests.post` round-trip time, not server-side "
        "inference duration."
    )
    question = (
        "要回答的问题是：这个编辑接口一次能接受几张参考图，多传的那张会不会真的被用上。"
        "官方文档没有答案，所以下面用实际调用来定。"
        if chinese else
        "The question is how many reference images this edit endpoint accepts in one call, and whether an extra "
        "image is actually used. The official documentation does not say, so the answer below comes from real calls."
    )
    quota_note = (
        "术语说明：`HTTP 429` 是配额用尽（本部署每分钟 2 次请求），表示请求没被处理，"
        "与接口拒绝某个张数是两件事；`HTTP 400` 才是接口明确拒绝。"
        if chinese else
        "Terminology: `HTTP 429` means the quota was exhausted (two requests per minute on this deployment), so the "
        "request was never processed. That differs from the endpoint refusing an image count, which returns "
        "`HTTP 400`."
    )
    sections = [
        f"### {'多图输入编辑测试' if chinese else 'Multi-Image Input Edit Test'}",
        f"**{'要回答什么' if chinese else 'What this section determines'}**", question, intro,
        f"**{'两张输入图' if chinese else 'The two input images'}**",
        ("两张图都取自上文联网补测的模型输出，在这里复用为输入素材。左图是一张深色配色信息图，"
         "画面里有四个配色圆点、14/16 英寸标注和一台紫色笔记本；右图是一张浅色规格信息图，"
         "有一台棕色笔记本、屏幕文字和下排四种使用模式（其中平板模式带手写笔）。"
         "它们是模型生成内容，不是官方素材，图中的配色名与规格文字不代表官方产品信息。"
         if chinese else
         "Both images are model outputs from the web-grounding section above, reused here as input material. The "
         "left one is a dark colour-lineup infographic containing four colour dots, 14/16-inch labels and a purple "
         "laptop. The right one is a light specification infographic containing a brown laptop, on-screen text and "
         "a row of four usage modes, one of which holds a pen. They are generated content, not official assets, and "
         "their colour names and specification text do not represent official product information."),
        table([("输入图 1（深色配色信息图）" if chinese else "Input image 1, colour-lineup infographic"),
               ("输入图 2（浅色规格信息图）" if chinese else "Input image 2, specification infographic")],
              [[f"![Input image 1]({GROUNDING_ARCHIVE}/mai-image-2.6-web-off/r1/01_test.png)",
                f"![Input image 2]({GROUNDING_ARCHIVE}/mai-image-2.6-web-off/r1/02_test.png)"]]),
        f"**{'第一组：各自用法的实际效果' if chinese else 'Group 1: what each usage returns'}**", capability_note,
        (f"单图提示词（发送 1 张图时）：\n\n```text\n{capability[1]['prompt']}\n```\n\n"
         f"双图提示词（发送 2 张图时）：\n\n```text\n{capability[2]['prompt']}\n```"
         if chinese else
         f"Prompt sent with one image:\n\n```text\n{capability[1]['prompt']}\n```\n\n"
         f"Prompt sent with two images:\n\n```text\n{capability[2]['prompt']}\n```"),
        table(([ "输入", "请求耗时", "输出大小"] if chinese else
               ["Input", "Request latency", "Output size"]),
              [[row[0], row[2], row[3]] for row in capability_rows]),
        table([("单图输入的输出" if chinese else "One-image output"),
               ("双图输入的输出" if chinese else "Two-image output")],
              [[f"![Single-image edit output]({archive_path}/{capability[1]['output']})",
                f"![Two-image edit output]({archive_path}/{capability[2]['output']})"]]),
        f"**{'第二组：第二张图到底有没有被用上' if chinese else 'Group 2: was the second image actually used'}**",
        attribution_note,
        (f"本组三次调用都用这一条提示词：\n\n```text\n{attribution_prompt}\n```"
         if chinese else
         f"All three calls in this group use this one prompt:\n\n```text\n{attribution_prompt}\n```"),
        table(([ "输入组合", "张数", "请求耗时", "画面结果"] if chinese else
               ["Input combination", "Images", "Request latency", "Observed result"]), attribution_rows),
        table([("只给输入图 1" if chinese else "Image 1 only"),
               ("只给输入图 2" if chinese else "Image 2 only")],
              [[f"![Attribution, image 1 only]({archive_path}/{attribution['single_image']['output']})",
                f"![Attribution, image 2 only]({archive_path}/{attribution['fixed_prompt_image_two_only']['output']})"]]),
        table([("同时给两张输入图" if chinese else "Both input images")],
              [[f"![Attribution, both images]({archive_path}/{attribution['two_image_fields']['output']})"]]),
        attribution_finding,
        f"**{'第三组：能传几张，字段该怎么写' if chinese else 'Group 3: how many images, and how the field must be named'}**",
        quota_note,
        table(([ "multipart 字段", "状态", "服务端返回"] if chinese else
               ["Multipart field", "Status", "Service response"]), contract_rows),
        field_boundary,
        f"**{'是否等于抠图' if chinese else 'Is this a cutout'}**", cutout_boundary, repeatability,
        " | ".join([
            f"[{'能力组与归因组第三臂' if chinese else 'Capability and third attribution arm'}]({archive_path}/clean-results.json)",
            f"[{'字段形式' if chinese else 'Field shapes'}]({archive_path}/field-shape-results.json)",
            f"[{'校验与上限' if chinese else 'Validation and limit'}]({archive_path}/limit-probe-results.json)",
            f"[{'探测脚本' if chinese else 'Probe scripts'}]({archive_path}/source)",
        ]),
    ]
    return "\n\n".join(sections)


def multi_image_reproduction_commands(archive_path):
    return (f"```powershell\npython scripts/summarize_multi_image_edit.py {archive_path} --check\n"
            f"python {archive_path}/source/probe_multi_image_clean.py\n"
            f"python {archive_path}/source/probe_multi_image_limit.py\n"
            f"python {archive_path}/source/check_alpha_and_cutout.py\n```")


def grounding_reproduction_commands(archive_path):
    return (f"```powershell\npython scripts/summarize_web_grounding.py {archive_path} --require-complete --check\n"
            f"python {archive_path}/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both "
            f"--prompts-csv {archive_path}/source/prompts.csv --output runs/web-grounding-reproduction --dry-run\n"
            f"python {archive_path}/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both "
            f"--prompts-csv {archive_path}/source/prompts.csv --output runs/web-grounding-reproduction\n```")


def render_grounding_section(summary, archive_path, language):
    if not summary["complete"]:
        raise ValueError("Grounding results must be complete before publication")
    chinese = language == "zh"
    selected = [sample for sample in summary["samples"] if sample["prompt_idx"] in (1, 2)]
    settings = [False, True]
    rows_by_setting = [[sample for sample in selected if sample["web_grounding"] is enabled]
                       for enabled in settings]
    selected_ids = {(sample["group"], sample["round"], sample["prompt_idx"]) for sample in selected}
    unsuccessful = [attempt for attempt in summary["unsuccessful_attempts"]
                    if (attempt["group"], attempt["round"], attempt["prompt_idx"]) in selected_ids]
    metrics = []
    for label, measure in (
        ("返回图片 / 展示样本" if chinese else "Images returned / displayed samples",
         lambda rows: f"{sum(sample['ok'] for sample in rows)}/{len(rows)}"),
        ("首试成功 / 展示样本" if chinese else "First-attempt successes / displayed samples",
         lambda rows: f"{sum(sample['first_attempt_ok'] for sample in rows)}/{len(rows)}"),
        ("HTTP 请求次数" if chinese else "HTTP attempts",
         lambda rows: str(sum(sample["attempt_count"] for sample in rows))),
        ("HTTP 408 次数" if chinese else "HTTP 408 responses",
         lambda rows: str(sum(attempt.get("http_status") == 408 and attempt["group"] == rows[0]["group"]
                              for attempt in unsuccessful))),
    ):
        metrics.append([label, *(measure(rows) for rows in rows_by_setting)])
    unit = "秒" if chinese else "s"
    for label, statistic, field, successful_only in (
        ("成功请求平均耗时" if chinese else "Mean successful request", statistics.mean, "time", True),
        ("成功请求 P50" if chinese else "Successful request P50", statistics.median, "time", True),
        ("含失败重试的逻辑调用平均耗时" if chinese else "Mean logical call including retries",
         statistics.mean, "logical_request_seconds", False),
    ):
        values = [[sample[field] for sample in rows if sample["ok"] or not successful_only]
                  for rows in rows_by_setting]
        metrics.append([label, *(f"{statistic(values_for_setting):.2f} {unit}" if values_for_setting else "N/A"
                                 for values_for_setting in values)])
    headers = ["指标", "关闭联网", "开启联网"] if chinese else ["Metric", "Grounding off", "Grounding on"]
    intro = (
        "本节测试通用的联网信息补充能力：在相同提示词下，对比 MAI-Image-2.6 的 `web_grounding=false/true`，"
        "观察文字事实准确性与生成耗时。公开新品资料只是测试题材，不是客户项目或客户采纳案例。"
        if chinese else
        "This section tests web grounding as a general image-generation capability: identical prompts are sent to "
        "MAI-Image-2.6 with `web_grounding=false/true` to compare text factual accuracy and latency. "
        "Public product announcements supply the test subjects; this is not a customer project or adoption case."
    )
    scope = (
        f"完整补测为 {summary['planned_samples']} 个正式样本，另有 {summary['warmups_excluded']} 次预热。"
        f"按已观察到的文字事实改善选取两个题目，保留全部两轮开／关对照，共 {len(selected)} 张原图，"
        f"每组 {len(rows_by_setting[0])} 个样本。下表仅统计这些选例，不是全量提升率。"
        "本节没有 GPT 对照，不能据此得出相对 GPT-Image-2 的优势结论。"
        if chinese else
        f"The complete supplement contains {summary['planned_samples']} formal samples and "
        f"{summary['warmups_excluded']} excluded warmups. Two subjects were selected after observing improved text facts; "
        f"all off/on results from both rounds are shown, {len(selected)} original images and "
        f"{len(rows_by_setting[0])} samples per setting. The table covers only these examples, not an overall improvement rate. "
        "No GPT comparison was performed in this section, so it does not establish superiority over GPT-Image-2."
    )
    findings = (
        [["新品配色与尺寸", "两轮均出现非官方配色名和错误屏幕选项", "两轮均匹配七种官方配色名及 14/15 英寸选项"],
         ["产品规格与使用模式", "屏幕尺寸和计算平台错误，均漏掉 Canvas 模式", "两轮均写对 16 英寸、NVIDIA RTX Spark、五种模式及笔输入表面"]]
        if chinese else
        [["New-product colours and sizes", "Both rounds used unofficial colour names and incorrect screen options",
          "Both matched all seven official colour names and the 14/15-inch options"],
         ["Product specifications and usage modes", "Screen size and computing platform were wrong; Canvas mode was missing",
          "Both matched 16 inches, NVIDIA RTX Spark, five mode names and the pen-input surfaces"]]
    )
    boundaries = (
        "固定 1024x1024、`auto_aspect_ratio=false`，同一模型版本 2026-07-31、Sweden Central GlobalStandard 部署；"
        "第二轮反转请求顺序。两组仅联网开关不同，核对答案未加入提示词。"
        "成功请求耗时不含 JSON/base64 处理；逻辑调用耗时包含失败、退避和响应处理，不含外侧 5 秒间隔及最终 PNG 写盘。"
        "所有 HTTP 408 和重试均保留，服务未说明内部超时环节，不能把全部额外时间归因于搜索。"
        if chinese else
        "Both settings used 1024x1024, `auto_aspect_ratio=false`, model version 2026-07-31 and the same Sweden Central "
        "GlobalStandard deployment. Round 2 reversed request order. Only the grounding switch differed; reference answers "
        "were not included in prompts. Successful request time excludes JSON/base64 processing; logical call time includes "
        "failures, backoff and response processing, but excludes the outer five-second interval and final PNG write. "
        "All HTTP 408 responses and retries are retained. The internal timeout stage was not returned, so the additional "
        "time cannot all be attributed to search."
    )
    quality_boundary = (
        "文字事实改善不等于画面质量或产品外观保真。第二题第二轮开启图中，`Tablet Mode` 标签下仍画着竖起的屏幕，"
        "存在图文不一致。观察为 AI 辅助非盲评，只有少量重复，不是人工偏好或统计显著性结论。"
        "响应没有提供检索查询、来源 URL 或调用轨迹；usage 变化不能证明具体检索来源。"
        if chinese else
        "Improved text facts do not establish better aesthetics or product fidelity. In subject 2, round 2, the "
        "grounding-on `Tablet Mode` illustration still has an upright screen. Inspection was AI-assisted and unblinded, "
        "with few repetitions, not human preference voting or a statistically significant result. Responses included "
        "no search queries, source URLs or retrieval traces; usage changes do not identify retrieval sources."
    )
    subject_labels = ("新品配色与尺寸", "产品规格与使用模式") if chinese else (
        "New-product colours and sizes", "Product specifications and usage modes")
    prompt_block = []
    for index, label in enumerate(subject_labels):
        prompt_text = summary["prompts"][index]
        opened = "<details><summary>" + (
            f"题目 {index + 1}：{label} — 展开查看发给模型的完整提示词" if chinese else
            f"Subject {index + 1}: {label} — expand for the exact prompt sent") + "</summary>\n\n"
        prompt_block.append(opened + "```text\n" + prompt_text + "\n```\n\n</details>")
    asked = (
        "两个题目都要求模型把真实产品信息画进海报：题目 1 要求列出官方发布的全部配色名与屏幕尺寸选项，"
        "题目 2 要求写出产品名、屏幕尺寸、计算平台，并标出官方命名的翻转使用模式与支持笔输入的表面。"
        "提示词只要求以官方发布信息为准，没有把正确答案写进提示词。"
        if chinese else
        "Both subjects ask the model to put real product information into a poster. Subject 1 asks for every "
        "officially announced colour name and the screen-size options; subject 2 asks for the product name, screen "
        "size, computing platform, the officially named convertible modes and which surfaces accept pen input. The "
        "prompts only instruct the model to follow the official announcement; no correct answer is supplied in the "
        "prompt itself."
    )
    controlled = (
        "唯一变化的是 `web_grounding` 开关。提示词、尺寸、模型版本、部署与轮数完全相同。"
        if chinese else
        "The only thing that changes is the `web_grounding` switch. Prompt, dimensions, model version, deployment "
        "and round count are identical."
    )
    sections = [f"### {'联网信息补充测试' if chinese else 'Web Grounding Test'}", intro,
                f"**{'我们向模型提出的问题' if chinese else 'What we asked the model'}**", asked,
                *prompt_block,
                f"**{'受控变量' if chinese else 'Controlled variable'}**", controlled, scope,
                f"**{'文字事实核对结果' if chinese else 'Text-fact findings'}**",
                table(["测试项", "关闭联网", "开启联网"] if chinese else ["Test subject", "Grounding off", "Grounding on"], findings),
                f"**{'耗时与请求情况' if chinese else 'Latency and request outcomes'}**",
                table(headers, metrics), boundaries, quality_boundary]
    for prompt_index, subject in ((1, "新品配色与尺寸" if chinese else "New-product colours and sizes"),
                                  (2, "产品规格与使用模式" if chinese else "Product specifications and usage modes")):
        for round_number in (1, 2):
            rows = [next(sample for sample in selected if sample["prompt_idx"] == prompt_index
                         and sample["round"] == round_number and sample["web_grounding"] is enabled)
                    for enabled in settings]
            images = [f"![Web grounding {'on' if enabled else 'off'}, subject {prompt_index}, round {round_number}]"
                      f"({archive_path}/{sample['image']})" if sample["ok"] else
                      ("未返回图片" if chinese else "No image returned") for enabled, sample in zip(settings, rows)]
            caption = f"#### {subject} / {'第' + str(round_number) + '轮' if chinese else 'Round ' + str(round_number)}"
            sections.extend([caption, table(["`web_grounding=false`", "`web_grounding=true`"], [images])])
    sections.extend([
        ("完整原始数据保留，旧批次不重写；本节与上文双模型测试分别统计，复现命令见下方复现与测试章节。" if chinese else
         "Full original evidence is retained without rewriting previous runs. This section is measured separately from the two-model test above; its commands appear in the reproduction section below."),
        f"[{'原始结果' if chinese else 'Raw results'}]({archive_path}/5way_v2_results.json) | "
        f"[{'全部请求' if chinese else 'All attempts'}]({archive_path}/attempts.jsonl) | "
        f"[{'逐图观察' if chinese else 'Visual observations'}]({archive_path}/visual-review.json) | "
        f"[{'完整12样本统计' if chinese else 'Full 12-sample statistics'}]({archive_path}/web-grounding-summary.json) | "
        f"[{'出处与哈希' if chinese else 'Provenance and hashes'}]({archive_path}/provenance.json)",
        f"{'结果 SHA-256' if chinese else 'Result SHA-256'}: `{summary['result_sha256']}`.",
        ("官方参考：" if chinese else "Official references: ") +
        "[IdeaPad Vibe](https://news.lenovo.com/pressroom/press-releases/colorful-ideapad-vibe-series-all-in-one-ai-pcs/) | "
        "[Yoga](https://news.lenovo.com/pressroom/press-releases/yoga-portfolio-new-ai-pcs-and-tablets/) | "
        "[MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image#request-parameters)",
    ])
    return "\n\n".join(sections)


def update_document(text, summary, quality, archive_path, language, grounding_section="",
                    multi_image_section=""):
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
    content = render_overview(summary, quality, archive_path, language, grounding_section,
                              multi_image_section)
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
    grounding_summary = summarize_grounding(root / GROUNDING_ARCHIVE)
    multi_image_summary = summarize_multi_image(root / MULTI_IMAGE_ARCHIVE)
    documents = []
    for filename, language in (("README.md", "en"), ("README-CN.md", "zh")):
        path = root / filename
        original = path.read_text("utf-8")
        generated = update_document(
            original, summary, quality, archive_path, language,
            render_grounding_section(grounding_summary, GROUNDING_ARCHIVE, language),
            render_multi_image_section(multi_image_summary, MULTI_IMAGE_ARCHIVE, language))
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