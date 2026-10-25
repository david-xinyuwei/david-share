import argparse
import base64
import hashlib
import html
import json
from pathlib import Path

from analyze import ROOT, read_json, require, validate


LABELS = {
    "opus55-standard": "Opus 5.5",
    "sonnet55-standard": "Sonnet 5.5",
    "haiku55-standard": "Haiku 5.5",
}


def table(groups, chinese=False):
    header = "| 模型 | thinking | 缓存覆盖 | 样本 | 缓存读取占比 | 首字 P50（秒） | E2E P50（秒） | 输出 P50（token/秒） | 模型费（美元） |" if chinese else "| Model | Thinking | Cached prefix | N | Cache-read share | First text P50 (s) | E2E P50 (s) | Output P50 (tokens/s) | Model USD |"
    lines = [header, "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for group in groups.values():
        config = group["config"]
        cache = ("system" if config["cache"] == "system" else "system + history")
        lines.append(f'| {LABELS[config["model"]]} | {config["thinking"]} | {cache} | {group["samples"]} | {group["cacheReadSharePercent"]:.2f}% | {group["ttftSeconds"]["p50"]:.3f} | {group["e2eSeconds"]["p50"]:.3f} | {group["outputTokensPerSecond"]["p50"]:.2f} | {group["costUsd"]:.6f} |')
    return "\n".join(lines)


def architecture(chinese=False):
    icon_source = read_json(ROOT / "images/icon-sources.json")
    icons = {}
    for item in icon_source["icons"]:
        path = ROOT / item["file"]
        require(hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], "Icon changed")
        icons[path.name] = base64.b64encode(path.read_bytes()).decode()
    app_icon = icons["02989-icon-service-Container-Apps-Environments.svg"]
    foundry_icon = icons["036509415-icon-service-Foundry-Project.svg"]
    title = "实际测试路径与计时位置" if chinese else "Measured path and timing boundary"
    client = "固定问题 / Windows 客户端" if chinese else "Fixed workload / Windows client"
    gateway = "LiteLLM 1.106.2 / 单 worker" if chinese else "LiteLLM 1.106.2 / one worker"
    models = "Opus / Sonnet / Haiku 5.5"
    note = "计时全部在客户端；GlobalStandard 不保证推理固定在资源区域。" if chinese else "All timing is client-side; GlobalStandard does not pin inference to the resource region."
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="380" viewBox="0 0 1200 380">
<rect width="1200" height="380" fill="#ffffff"/>
<g font-family="Segoe UI,Microsoft YaHei,sans-serif" fill="#202020">
<text x="32" y="45" font-size="28" fill="#0078d4">{title}</text>
<rect x="32" y="90" width="320" height="148" rx="6" fill="#f5f5f5" stroke="#767676"/>
<text x="52" y="128" font-size="22">{client}</text><text x="52" y="163" font-size="20">PowerShell 7.6.7 / HTTPS</text><text x="52" y="199" font-size="19">headers / SSE / text / end</text>
<path d="M352 158 H412" fill="none" stroke="#0078d4" stroke-width="3"/><path d="M404 152 L416 158 L404 164" fill="#0078d4"/>
<rect x="416" y="90" width="342" height="148" rx="6" fill="#eef6fc" stroke="#0078d4"/>
<image x="434" y="108" width="38" height="38" href="data:image/svg+xml;base64,{app_icon}"/>
<text x="486" y="134" font-size="22">Azure Container Apps</text><text x="436" y="171" font-size="20">{gateway}</text><text x="436" y="207" font-size="19">Japan East / managed identity</text>
<path d="M758 158 H812" fill="none" stroke="#0078d4" stroke-width="3"/><path d="M804 152 L816 158 L804 164" fill="#0078d4"/>
<rect x="816" y="90" width="352" height="148" rx="6" fill="#eef6fc" stroke="#0078d4"/>
<image x="834" y="108" width="38" height="38" href="data:image/svg+xml;base64,{foundry_icon}"/>
<text x="886" y="134" font-size="22">Microsoft Foundry</text><text x="836" y="171" font-size="20">{models}</text><text x="836" y="207" font-size="19">East US 2 resource / global inference</text>
<path d="M990 254 H188" stroke="#107c10" stroke-width="2" fill="none"/><path d="M198 248 L186 254 L198 260" fill="#107c10"/>
<text x="375" y="289" font-size="20" fill="#107c10">SSE + usage + stop_reason</text>
<text x="32" y="344" font-size="19">{note}</text></g></svg>'''


def latency_chart(groups, chinese=False):
    title = "首个可见回答时间：每组五轮的 P50" if chinese else "Time to first visible answer: P50 of five turns per configuration"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="640" viewBox="0 0 1200 640"><rect width="1200" height="640" fill="white"/><g font-family="Segoe UI,Microsoft YaHei,sans-serif"><text x="28" y="40" font-size="27" fill="#202020">{title}</text>']
    for index, group in enumerate(groups.values()):
        config = group["config"]
        label = f'{LABELS[config["model"]]} / {config["thinking"]} / {config["cache"]}'
        value = group["ttftSeconds"]["p50"]
        top = 74 + index * 48
        colour = "#0078d4" if config["thinking"] == "adaptive" else "#107c10"
        parts.extend([f'<text x="28" y="{top+23}" font-size="17">{html.escape(label)}</text>', f'<rect x="510" y="{top}" width="{value*58:.3f}" height="30" fill="{colour}"/>', f'<text x="{522+value*58:.3f}" y="{top+23}" font-size="18">{value:.3f} s</text>'])
    note = "单会话、相关轮次；不是生产 P95，也未验证答案质量等价。" if chinese else "One conversation per cell; dependent turns. Not production P95 or quality equivalence."
    parts.append(f'<text x="28" y="608" font-size="19" fill="#555">{note}</text></g></svg>')
    return "\n".join(parts)


def pages(result):
    matrix = read_json(ROOT / "data/matrix.json")
    groups = result["groups"]
    output = {}
    for chinese in (False, True):
        suffix = "_CN" if chinese else ""
        language = "zh" if chinese else "en"
        readme_name = f"README{suffix}.md"
        other = "README.md" if chinese else "README_CN.md"
        title = "Claude on Foundry：thinking、缓存与首字延迟" if chinese else "Claude on Foundry: Thinking, Prompt Caching and First-Text Latency"
        purpose = "本项目把模型 thinking、缓存覆盖范围和客户端首字等待分开测量，避免把 HTTP 200、已开启流式或缓存标记存在当成性能达标。提供三模型的固定五轮输入、流式采集器、十组实际结果和离线验算。" if chinese else "Measure thinking mode, cache coverage and client-visible waiting separately. A successful HTTP response, streaming flag or cache marker is not a performance acceptance test. This project provides a fixed five-turn workload, a streaming collector, ten measured configurations and independent offline verification."
        limits = "这是一次固定资料问答实验，不是客户生产负载。没有答案质量评分、并发压测、AWS 对照或其他 effort 档位排名。" if chinese else "This is one fixed source-review workload, not customer production traffic. There is no answer-quality score, concurrent load test, AWS comparison or effort-level ranking."
        headings = ("目的", "操作步骤", "实现效果") if chinese else ("Purpose", "Steps", "Results")
        setup = "先准备自己的 Foundry 资源和三个 Azure-hosted 部署（版本 2），使用名称 claude-opus-5-5、claude-sonnet-5-5、claude-haiku-5-5。按实际配额分配容量；本次各为 40,000 TPM。需要 Windows PowerShell 7、Python 3.13、Docker 或 ACR Tasks，以及获授权的 Azure CLI 登录。" if chinese else "Use your own Foundry resource with three Azure-hosted deployments (version 2), named claude-opus-5-5, claude-sonnet-5-5 and claude-haiku-5-5. Allocate within your quota; this run used 40,000 TPM each. You need Windows PowerShell 7, Python 3.13, Docker or ACR Tasks, and an authorized Azure CLI session."
        identity = "部署到已有的、仅用于此测试的 Azure Container App：启用系统分配 Managed Identity，在 Foundry 资源范围授予 Cognitive Services User；私有 ACR 拉取还需 AcrPull。将入口密钥保存为 ACA Secret（例如 gateway-key），不要放入 Git 或命令行。" if chinese else "Use a dedicated Azure Container App with system-assigned managed identity and the Cognitive Services User role on the Foundry resource. A private registry also requires AcrPull. Store the gateway key as an ACA Secret (for example gateway-key), never in Git or a command line."
        instructions = "在本项目目录运行以下命令。变量均为自己的资源；密钥由安全终端提示输入，脚本只在进程内使用。" if chinese else "Run from this project directory. Supply your own resource values. Enter the key through a secure terminal prompt; it is used in-process only."
        build_note = "该 Dockerfile 从固定的公开 LiteLLM 镜像构建，不拉取作者的私有镜像。原测试容器的构建、启动和真实请求已验证；此公开包装的全新部署尚未实跑，不能把离线检查当成部署成功。" if chinese else "The Dockerfile builds from a pinned public LiteLLM image, not an author's private image. The measured gateway's build, startup and live requests were verified; a fresh deployment of this public packaging has not been run. Offline checks are not deployment proof."
        setting_note = "请在 ACA Ingress 中启用 HTTPS、目标端口 4000，并仅允许自己的测试客户端访问。保留原密钥；更新镜像前记录旧 digest 以便回滚。" if chinese else "Configure HTTPS ingress to target port 4000 and restrict access to your test client. Keep the gateway secret unchanged and record the previous image digest before upgrading."
        effect = f'本轮 **{result["requests"]}/50 正常完成**，模型费用按公开费率估算 **US${result["costUsd"]:.8f}**。以下每行五轮；输出吞吐为 output_tokens/E2E，包含 thinking。' if chinese else f'All **{result["requests"]}/50 requests completed**. Published-rate model cost: **US${result["costUsd"]:.8f}**. Each row contains five turns. Output throughput is output_tokens/E2E, including thinking.'
        not_guarantee = "关闭模式在无工具任务中均为零 thinking token。Sonnet 的 between_tools 不是所有场景下的完全关闭；Opus 5.5 不支持关闭。P95 在五个样本下等于最大值，不代表生产尾延迟。" if chinese else "The no-up-front-thinking modes produced zero thinking tokens in this tool-free workload. Sonnet between_tools is not a universal full-off switch; Opus 5.5 cannot disable thinking. With five samples, P95 is the maximum, not a production-tail estimate."
        output[readme_name] = f'''# {title}

LiteLLM 1.106.2 · Claude 5.5 · 50 requests · [Other language]({other})

## {headings[0]}

{purpose}

{limits}

<img src="images/architecture-{language}.svg" width="880" alt="Measured gateway architecture and timing points" />

{'原创解释图；Azure 图标来源见 images/icon-sources.json。图不是运行证据。' if chinese else 'Original explanatory diagram. Azure icon provenance: images/icon-sources.json. A diagram is not runtime evidence.'}

## {headings[1]}

{setup}

{identity}

{instructions}

**1. {'构建自己的网关镜像' if chinese else 'Build your gateway image'}**

```powershell
$env:ACR_NAME = Read-Host 'Your ACR name'
$env:APP_RG = Read-Host 'Your dedicated Container App resource group'
$env:APP_NAME = Read-Host 'Your dedicated Container App name'
$env:FOUNDRY_ANTHROPIC_BASE = Read-Host 'Your Foundry /anthropic base URL'
az acr build --registry $env:ACR_NAME --image claude-gateway:1.106.2 --file deploy/Dockerfile deploy
```

{build_note}

**2. {'更新专用 Container App' if chinese else 'Update the dedicated Container App'}**

```powershell
$digest = az acr repository show --name $env:ACR_NAME --image claude-gateway:1.106.2 --query digest -o tsv
$server = az acr show --name $env:ACR_NAME --query loginServer -o tsv
$image = "$server/claude-gateway@$digest"
az containerapp update --resource-group $env:APP_RG --name $env:APP_NAME --image $image --set-env-vars "FOUNDRY_ANTHROPIC_BASE=$env:FOUNDRY_ANTHROPIC_BASE" 'LITELLM_MASTER_KEY=secretref:gateway-key' 'PYTHONPATH=/app/claude-gateway'
```

{setting_note}

**3. {'验证入口，再执行矩阵' if chinese else 'Verify the entry point, then run the matrix'}**

```powershell
$env:CLAUDE_GATEWAY_URL = Read-Host 'Your HTTPS gateway URL'
$secureKey = Read-Host 'Your gateway key' -AsSecureString
$env:CLAUDE_GATEWAY_KEY = [Net.NetworkCredential]::new('', $secureKey).Password
try {{
    $headers = @{{Authorization='Bearer '+$env:CLAUDE_GATEWAY_KEY}}
    (Invoke-RestMethod "$env:CLAUDE_GATEWAY_URL/v1/models" -Headers $headers).data.id
    $run = Join-Path 'live-runs' (Get-Date -Format 'yyyyMMdd-HHmmss')
    ./scripts/run_matrix.ps1 -RunDirectory $run
}} finally {{
    $env:CLAUDE_GATEWAY_KEY = $null
}}
```

{'元数据接口应列出三个 standard 别名；矩阵应保存 50 份响应。Ctrl+C 停止本地测试，不会停止 Azure 资源。资源停用和访问规则恢复由资源所有者单独执行。' if chinese else 'The metadata endpoint should list three standard aliases; the full matrix should save 50 responses. Ctrl+C stops the local test, not Azure resources. Resource shutdown and ingress restoration are separate owner-controlled actions.'}

## {headings[2]}

{effect}

{table(groups, chinese)}

{not_guarantee}

{'更高缓存占比不等于全部首字改善来自缓存：各会话独立生成，历史和 thinking 用量随之变化。所有计时在客户端，未分离服务端排队、网络和推理计算。' if chinese else 'Higher cache share does not attribute all first-text improvements to caching: conversations generate independently, changing history and thinking usage. All timing is client-side; server queues, network time and model compute are not isolated.'}

| {'想要' if chinese else 'Goal'} | {'入口' if chinese else 'Read'} |
|---|---|
| {'查看逐轮与分段计时' if chinese else 'Inspect per-turn and timing results'} | [Results](docs/results{suffix}.md) |
| {'核验、复测与限制' if chinese else 'Verify, reproduce and understand limits'} | [Testing](docs/testing{suffix}.md) |

{'目录' if chinese else 'Directories'}: [deploy](deploy/), [scripts](scripts/), [data](data/), [evidence](evidence/), [images](images/), [tests](tests/). [Dependencies](requirements.txt).
'''
        timing_lines = ["| Case | N | Headers P50 s | First SSE P50 s | First text P50 s | Post-SSE wait P50 s | First text P95 s | Thinking requests |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for case_id, group in groups.items():
            timing_lines.append(f'| {case_id} | 5 | {group["headersSeconds"]["p50"]:.3f} | {group["firstSseSeconds"]["p50"]:.3f} | {group["ttftSeconds"]["p50"]:.3f} | {group["postFirstSseWaitSeconds"]["p50"]:.3f} | {group["ttftSeconds"]["p95"]:.3f} | {group["thinkingRequests"]}/5 |')
        detail_lines = ["| Case | Turn | First text s | E2E s | Input | Cache read | Cache write | Output | Thinking |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for case_id, group in groups.items():
            for row in group["rows"]:
                detail_lines.append(f'| {case_id} | {row["turn"]} | {row["ttftSeconds"]:.3f} | {row["e2eSeconds"]:.3f} | {row["totalInputTokens"]} | {row["cacheReadTokens"]} | {row["cacheWriteTokens"]} | {row["outputTokens"]} | {row["thinkingTokens"]} |')
        intro = "本轮比较关闭回答前的 thinking，以及扩大缓存覆盖范围，是否改变首个可见回答的等待。下面是实际发送的五个问题原文；所有配置使用同一材料和顺序。" if chinese else "This run asks whether disabling up-front thinking and extending cache coverage changes time to the first visible answer. The five prompts below are verbatim inputs; every configuration uses the same source material and order."
        questions = "\n\n".join(f'{index}. {question}' for index, question in enumerate(matrix["questions"], 1))
        output[f"docs/results{suffix}.md"] = f'''# {'实测结果' if chinese else 'Measured Results'}

[README](../{readme_name}) · [Testing](testing{suffix}.md) · [Other language](results{'' if chinese else '_CN'}.md)

## {'输入与方法' if chinese else 'Inputs and Method'}

{intro}

{questions}

[{'完整材料与矩阵' if chinese else 'Complete material and matrix'}](../data/matrix.json)

{'五种合法模型/模式组合，各做两种缓存配置，每组独立五轮。固定 medium、stream=true、max_tokens=4096、无工具、零重试、单请求串行。首先执行 system-only 阶段，再执行会话缓存阶段；未清缓存，也没有额外预热。两阶段的模型执行顺序均为 Haiku disabled、Sonnet between_tools、Opus adaptive、Sonnet adaptive、Haiku adaptive。后续历史来自各组自己的响应，不保证逐字相同。' if chinese else 'Five valid model/mode combinations, two cache configurations and five dependent turns per cell. Fixed medium, stream=true, max_tokens=4096, no tools, no retries and one in-flight request. System-only ran before conversation caching; no cache flush or extra pre-warming. Both phases used Haiku disabled, Sonnet between_tools, Opus adaptive, Sonnet adaptive, then Haiku adaptive. Later histories come from each cell itself and are not byte-identical across cells.'}

## {'观察结果' if chinese else 'Observed Results'}

<img src="../images/latency-{language}.svg" width="880" alt="Measured first visible answer latency" />

{'图由本轮 50 条记录计算；蓝色为 adaptive，绿色为无前置 thinking。不是质量排名。' if chinese else 'Computed from the 50 records in this run. Blue: adaptive. Green: no up-front thinking. This is not a quality ranking.'}

{table(groups, chinese)}

## {'分段时间' if chinese else 'Timing Boundaries'}

{'所有时间从客户端发出请求起算。Headers 是完整响应头到达，First body byte 是响应正文首 byte，不是完整 HTTP 首 byte。First SSE 包括 metadata/heartbeat，不等于可见回答。thinking 事件到达不等于推理开始；omitted 模式可能延后或合并事件。Post-SSE wait 是逐请求相减后取 P50，不是两个 P50 相减。' if chinese else 'Times start at client send. Headers means completed response headers; first body byte is the first response-body byte, not the first byte of the HTTP exchange. First SSE can be metadata/heartbeat, not visible text. A thinking event does not mark the start of model compute; omitted display can defer or group events. Post-SSE wait is computed per request before taking P50, not by subtracting medians.'}

{chr(10).join(timing_lines)}

## {'逐轮记录' if chinese else 'Per-Turn Records'}

{'token 列均为 token 数；完整回答、请求及事件时间在证据文件内。' if chinese else 'Token columns are token counts. Full requests, visible responses and event timing are in the evidence file.'}

{chr(10).join(detail_lines)}

## {'结论边界与来源' if chinese else 'Limits and Sources'}

{limits} {not_guarantee}

{'Sonnet adaptive 的两组分别只有 3/5 与 2/5 请求产生 thinking；不能把其首字变化全部归因缓存。关闭 thinking 后的回答更短或推理步骤更少也可能影响结果，尚未证明质量等价。' if chinese else 'Sonnet adaptive produced thinking in 3/5 and 2/5 requests in the two cache groups. Its latency difference cannot all be attributed to caching. Shorter answers or reduced reasoning can also affect timing; quality equivalence was not established.'}

[Requests and responses](../evidence/requests.json) · [Summary](../evidence/summary.json) · [Provenance and hashes](../evidence/provenance.json)

[Claude thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) · [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [LiteLLM v1.106.2 source](https://github.com/BerriAI/litellm/blob/v1.106.2/litellm/llms/anthropic/chat/transformation.py)
'''
        output[f"docs/testing{suffix}.md"] = f'''# {'复测与核验' if chinese else 'Testing and Reproduction'}

[README](../{readme_name}) · [Results](results{suffix}.md) · [Other language](testing{'' if chinese else '_CN'}.md)

## {'离线核验' if chinese else 'Offline Verification'}

{'不需要 Azure 或模型密钥；Python 标准库即可。' if chinese else 'No Azure or model key is required. Uses the Python standard library.'}

```powershell
python scripts/analyze.py --check
python scripts/render_docs.py --check
python -m unittest discover -s tests -v
./scripts/run_matrix.ps1 -RunDirectory live-runs/offline -ValidateOnly
```

{'预期 50 条记录、10 个配置，全部检查通过。测试会故意改动副本中的 token、thinking、问题和计时，确认校验器拒绝；不会改原始证据。' if chinese else 'Expect 50 records, 10 configurations and passing checks. Tests deliberately corrupt in-memory token, thinking, question and timing values and require rejection; original evidence is not edited.'}

## {'实际调用的验收' if chinese else 'Live Acceptance'}

{'部署和运行命令只有 README 一份。新运行使用新目录，正常结束仅代表调用完成；还需读取网关 CLAUDE_PROVIDER_TRACE 日志，把每个响应的 x-litellm-call-id 对上模型、thinking、effort、stream、max_tokens 与 cache_control。无对应日志时只能标记参数透传未验证。' if chinese else 'Deployment and execution commands have one owner: the README. Use a fresh run directory. Completion alone is not parameter acceptance: correlate each response x-litellm-call-id with CLAUDE_PROVIDER_TRACE logs for model, thinking, effort, stream, max_tokens and cache_control. Missing traces mean passthrough is unverified.'}

{'必须同时检查：HTTP 200、end_turn、message_stop、非空回答、完整 usage、历史原样追加，以及关闭模式的零 thinking token。首轮缓存状态按 usage 判断，不凭新会话 ID 判冷。' if chinese else 'Check HTTP 200, end_turn, message_stop, nonempty text, complete usage, append-only history and zero thinking tokens for off modes. Classify first-turn cache state from usage, not a new session ID.'}

{'输入缓存读取占比 = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens)。输出吞吐 = output_tokens/E2E；另列减去 thinking 的可见输出吞吐。nearest-rank 分位方法不插值，N=5 时 P95=max。' if chinese else 'Cache-read share = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens). Output throughput = output_tokens/E2E; visible output throughput subtracts thinking tokens. Percentiles use nearest-rank without interpolation; at N=5, P95=max.'}

## {'安全、支持与未验证项' if chinese else 'Security, Support and Gaps'}

{'真实输入、模型回答、签名及认证信息可能敏感。live-runs 与 .env 已忽略；不要上传运行目录。公开证据的签名已省略，call ID 已假名化，因此不能拿公开证据的历史重放签名；新运行必须使用自己的真实响应。' if chinese else 'Live inputs, responses, signatures and authentication can be sensitive. live-runs and .env are ignored; do not upload them. Published signatures are omitted and call IDs pseudonymized. Do not replay published history signatures; a live run must carry its own actual responses.'}

{'Opus 5.5 不支持 disabled。Sonnet 5.5 使用 between_tools，Haiku 5.5 使用 disabled，且这两种模式仅接受 low/medium/high。temperature、top_p、top_k 不作为本轮可调项；未验证的服务端工具或 beta 参数不加入默认配置。' if chinese else 'Opus 5.5 does not accept disabled. Sonnet 5.5 uses between_tools and Haiku 5.5 uses disabled; these modes accept low/medium/high only. temperature/top_p/top_k are not tuning axes in this run. Unverified server tools or beta parameters are not enabled by default.'}

{'公开采集器只去除了作者认证入口和资源默认值，测量循环保持与实测版本一致。它的语法、离线请求及数据测试已验证；公开包装的独立新部署未执行，没有录制公开视频，也没有客户桌面客户端验收。' if chinese else 'The public collector removes author-specific authentication and resource defaults while preserving the measured loop. Syntax, offline request construction and data tests are verified. A standalone fresh deployment of the public packaging was not executed; there is no public demo recording or customer desktop-client acceptance.'}
'''
        output[f"images/architecture-{language}.svg"] = architecture(chinese)
        output[f"images/latency-{language}.svg"] = latency_chart(groups, chinese)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = pages(validate())
    for name, content in rendered.items():
        path = ROOT / name
        expected = content.rstrip() + "\n"
        if args.check:
            require(path.is_file() and path.read_text(encoding="utf-8") == expected, "Rendered output drift: " + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "artifacts": len(rendered), "mode": "check" if args.check else "write"}))


if __name__ == "__main__":
    main()