"""Markdown and figure blocks for the 2026-10-26 direct tests; every number comes from coding_data."""
import base64
import hashlib
import html
import json
import re

from coding_data import (DEPLOYMENT, EFFORTS, EV, MODELS, NAME, OFF_MODE, ROOT, ROWS, _pricing, cache_numbers, cell,
                         matrix_numbers, model_cells, probe_outcomes, read_json, require, thinking)

REPO = "https://github.com/david-xinyuwei/david-share"
DOCS = "https://platform.claude.com/docs/en"
EFFORT_DOC = f"{DOCS}/build-with-claude/effort"
CACHE_DOC = f"{DOCS}/build-with-claude/prompt-caching"
PRICE_DOC = f"{DOCS}/about-claude/pricing"
FOUNDRY_DOC = f"{DOCS}/build-with-claude/claude-in-microsoft-foundry"
HOSTING_DOC = f"{FOUNDRY_DOC}#hosting-options"
THINKING_DOC = f"{DOCS}/build-with-claude/thinking"
POLYGLOT = "https://github.com/Aider-AI/polyglot-benchmark"
# Effort used when a request omits output_config.effort, per Claude's effort page.
DEFAULT_EFFORT = {"opus": "medium", "sonnet": "high", "haiku": "medium"}


def tr(chinese, en, cn):
    return cn if chinese else en


def secs(value):
    if value is None:
        return "—"
    return f"{value:.2f}" if value < 10 else f"{value:.1f}" if value < 100 else f"{value:.0f}"


def usd(value, digits=2):
    return f"${value:,.{digits}f}"


def pct(value, digits=1, sign=False):
    return f"{100 * value:+.{digits}f}" if sign else f"{100 * value:.{digits}f}"


def count(value):
    return f"{value:,}"


def span(low, high, fmt):
    a, b = fmt(low), fmt(high)
    return a if a == b else f"{a}–{b}"


def mode_label(mode):
    return f"`{mode}`"


def code(text):
    return f"`` {text} ``" if "`" in text else f"`{text}`"


def interval(lo, hi):
    a, b = pct(lo, 0), pct(hi, 0)
    return f"{a}%" if a == b else f"{a}–{b}%"


def cell_label(c):
    return f"{NAME[c['model']].split()[0]} · `{c['mode']}` · {c['effort']}"


def utc_time(stamp):
    return stamp[11:16]


def problem_link(problem_id):
    language, name = problem_id.split("/")
    return f"[`{problem_id}`]({POLYGLOT}/tree/7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/{language}/exercises/practice/{name})"


# ---------- grids ----------

def grid(d, chinese, value, title):
    header = "| " + tr(chinese, "Model · thinking", "模型 · 思考模式") + " | " + " | ".join(EFFORTS) + " |"
    lines = [f"**{title}**", "", header, "|---|" + "---:|" * len(EFFORTS)]
    for model, mode in ROWS:
        values = []
        for effort in EFFORTS:
            c = cell(d, model, mode, effort)
            values.append(value(c) if c else tr(chinese, "not accepted", "不接受"))
        lines.append(f"| {NAME[model]} · {mode_label(mode)} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def grids(d, chinese):
    return "\n\n".join([
        grid(d, chinese, lambda c: f"{c['passed']}/{c['attempted']}",
             tr(chinese, "Unit tests passed, of 54 answers", "通过单元测试的回答数（每格 54 个）")),
        grid(d, chinese, lambda c: secs(c["first_text_p50_s"]),
             tr(chinese, "First visible text, P50, seconds", "首个可见文字 P50（秒）")),
        grid(d, chinese, lambda c: usd(c["cost_per_1k_requests_usd"]),
             tr(chinese, "List-price cost per 1,000 requests, US dollars", "按标价计每 1,000 次请求的费用（美元）")),
    ])


# ---------- README: purpose ----------

def decision_table(d, chinese):
    summary = d["probe_summary"]
    defaults = DEFAULT_EFFORT
    rows = {key: [] for key in ("modes", "effort", "fast", "pass", "cost", "choose")}
    for model in MODELS:
        accepted = summary[DEPLOYMENT[model]]["accepted"]
        efforts = summary[DEPLOYMENT[model]]["listed_in_400"]
        require(accepted["adaptive"] == list(EFFORTS) and efforts == list(EFFORTS), "unexpected accepted efforts")
        off = OFF_MODE.get(model)
        if off:
            require(accepted[off] == ["low", "medium", "high"], "unexpected thinking-off efforts")
            rows["modes"].append(tr(chinese, f"`adaptive`; `{off}` at low, medium, high",
                                    f"`adaptive`；`{off}` 只接受 low、medium、high"))
        else:
            require(not accepted["disabled"] and not accepted["between_tools"], "Opus accepted a thinking-off mode")
            rows["modes"].append(tr(chinese, "`adaptive` only; `disabled` and `between_tools` return 400",
                                    "只接受 `adaptive`；`disabled` 和 `between_tools` 返回 400"))
        rows["effort"].append(tr(chinese, f"low to max / {defaults[model]}", f"low 到 max / {defaults[model]}"))
        fastest = min(model_cells(d, model), key=lambda c: c["first_text_p50_s"])
        rows["fast"].append(f"{secs(fastest['first_text_p50_s'])} 秒（`{fastest['mode']}` · {fastest['effort']}）" if chinese
                            else f"{secs(fastest['first_text_p50_s'])} s (`{fastest['mode']}` · {fastest['effort']})")
        if off:
            on = [c["passed"] for c in model_cells(d, model, "adaptive")]
            off_pass = [c["passed"] for c in model_cells(d, model, off)]
            if model == "sonnet":
                both = on + off_pass
                rows["pass"].append(tr(chinese, f"{min(both)} to {max(both)}", f"{min(both)} 到 {max(both)}"))
            else:
                rows["pass"].append(tr(chinese, f"{min(on)} to {max(on)} with `adaptive`; {min(off_pass)} to {max(off_pass)} with `{off}`",
                                       f"`adaptive` {min(on)} 到 {max(on)}；`{off}` {min(off_pass)} 到 {max(off_pass)}"))
        else:
            passes = {c["passed"] for c in model_cells(d, model)}
            require(passes == {54}, "Opus did not pass every answer")
            rows["pass"].append(tr(chinese, "54 in every cell", "每格都是 54"))
        costs = [c["cost_per_1k_requests_usd"] for c in model_cells(d, model)]
        rows["cost"].append(tr(chinese, f"{usd(min(costs))} to {usd(max(costs))}", f"{usd(min(costs))} 到 {usd(max(costs))}"))
    opus_low = cell(d, "opus", "adaptive", "low")
    sonnet_off = model_cells(d, "sonnet", "between_tools")
    haiku = thinking(d, "haiku")
    rows["choose"] = [
        tr(chinese, f"Answers must be right the first time. Start at `low`: every effort level passed all 54, and `low` was the fastest ({secs(opus_low['first_text_p50_s'])} s) and cheapest",
           f"答案必须一次就对。从 `low` 开始：每个档位都 54 个全过，`low` 最快（{secs(opus_low['first_text_p50_s'])} 秒）也最便宜"),
        tr(chinese, f"You want most of Opus's accuracy at a lower price: `between_tools` passed as often as `adaptive`, started in under 0.5 s and cost {span(min(c['cost_per_1k_requests_usd'] for c in sonnet_off), max(c['cost_per_1k_requests_usd'] for c in sonnet_off), usd)} per 1,000 requests",
           f"要接近 Opus 的正确率、价格更低：`between_tools` 的通过数与 `adaptive` 相当，首字不到 0.5 秒，每 1,000 次请求 {span(min(c['cost_per_1k_requests_usd'] for c in sonnet_off), max(c['cost_per_1k_requests_usd'] for c in sonnet_off), usd)}"),
        tr(chinese, f"Cost matters most and a wrong answer can be retried. Keep thinking on: at the same effort levels `adaptive` passed {pct(haiku['difference'])} points more often than `disabled`",
           f"费用最重要、答错可以重试。保持思考开启：同样的档位下 `adaptive` 比 `disabled` 通过率高 {pct(haiku['difference'])} 个百分点"),
    ]
    labels = tr(chinese,
                ["Thinking modes the API accepted", "Effort levels / default when omitted",
                 "First visible text, P50 of the fastest cell", "Unit tests passed per cell, of 54 answers",
                 "List-price cost per 1,000 requests", "Choose it when (our reading of this test)"],
                ["API 接受的思考模式", "推理档位 / 不传时的默认值", "最快一格的首个可见文字 P50",
                 "每格通过单元测试的回答数（共 54 个）", "按标价计每 1,000 次请求的费用", "适合的情况（本测试的解读）"])
    head = "| " + tr(chinese, "Question", "问题") + " | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |"
    lines = [head, "|---|---|---|---|"]
    for label, key in zip(labels, ("modes", "effort", "fast", "pass", "cost", "choose")):
        lines.append(f"| {label} | " + " | ".join(rows[key]) + " |")
    return "\n".join(lines)


def settings_table(d, chinese):
    summary, outcomes = d["probe_summary"], probe_outcomes(d)
    m, k = matrix_numbers(d), cache_numbers(d)
    accepted = {model: summary[DEPLOYMENT[model]]["accepted"] for model in MODELS}
    require(all(accepted[model]["adaptive"] == list(EFFORTS) for model in MODELS), "adaptive did not accept every effort")
    require(accepted["sonnet"]["between_tools"] == ["low", "medium", "high"] and not accepted["sonnet"]["disabled"]
            and accepted["haiku"]["disabled"] == ["low", "medium", "high"] and not accepted["haiku"]["between_tools"],
            "the thinking-off rules changed")
    sampling = ("temperature_0.5", "top_p_0.9", "top_k_40")
    rejected = [(name, model) for model in MODELS
                for name in ("thinking_enabled_budget", "max_tokens_1000000", *(f"adaptive_{s}" for s in sampling))]
    rejected += [(f"{OFF_MODE[model]}_{s}", model) for model in OFF_MODE for s in sampling]
    require(all(outcomes[key][0] == 400 for key in rejected), "a probe expected to return HTTP 400 did not")
    require(m["thought_streamed"] == 0, "a matrix answer streamed thinking text")
    require(d["runs"]["cache"]["http"] == {200: k["requests"]}, "a cache request did not return HTTP 200")
    require({x["sku"] for x in d["provenance"]["models"]["deployments"]} == {"GlobalStandard"}, "a deployment is not GlobalStandard")
    prices = _pricing().PRICES

    def times(model, key):
        return round(prices[DEPLOYMENT[model]][key] / prices[DEPLOYMENT[model]]["input"], 3)

    w5, w1, read_big, read_haiku = times("opus", "write_5m"), times("opus", "write_1h"), times("opus", "read"), times("haiku", "read")
    require(all(times(x, "write_5m") == w5 and times(x, "write_1h") == w1 for x in MODELS) and times("sonnet", "read") == read_big,
            "cache price multipliers differ between models")
    max_tokens, cells, geo = d["runs"]["matrix"]["max_tokens"], len(d["facts"]["cells"]), m["geo_value"]
    opus_default, sonnet_default = DEFAULT_EFFORT["opus"], DEFAULT_EFFORT["sonnet"]
    require(DEFAULT_EFFORT["haiku"] == opus_default, "Opus and Haiku have different default efforts")
    rows = tr(chinese, [
        ('`thinking.type: "adaptive"`',
         "The model decides for each request whether to think before answering and for how long; `output_config.effort` steers how much. Sending no `thinking` field does the same on these three models",
         "All three models, effort low to max"),
        ('`thinking.type: "between_tools"`',
         "Sonnet 5.5's lowest setting: no thinking before the answer. Short progress updates written between tool calls still come back as thinking blocks; without tools the answer is text only. Accepted at effort `high` or below",
         "Sonnet, effort low, medium, high; no tools"),
        ('`thinking.type: "disabled"`',
         "Thinking off. Only Haiku 5.5 accepts it, at effort `high` or below; Opus 5.5 cannot turn thinking off",
         "Haiku, effort low, medium, high"),
        ('`thinking.type: "enabled"` with `budget_tokens`',
         "The older fixed thinking budget; these models do not support it",
         "Probe only: HTTP 400 on all three"),
        ("`thinking.display`",
         'Whether thinking text comes back. The default on these models, `"omitted"`, returns thinking blocks with empty text and an encrypted signature, so the answer starts streaming sooner; the thinking tokens are still billed. `"summarized"` returns a summary',
         f"Not sent: {count(m['thought'])} matrix answers used thinking tokens and none streamed thinking text"),
        ("`output_config.effort`",
         f"How much work goes into the whole response, thinking included: `low`, `medium`, `high`, `xhigh`, `max`. A behavioral signal, not a token budget. Default when omitted: Opus and Haiku `{opus_default}`, Sonnet `{sonnet_default}`",
         f"Every level each thinking mode accepted: {cells} cells"),
        ("`max_tokens`",
         'Hard limit on output tokens, thinking included; an answer that reaches it stops with `stop_reason: "max_tokens"`. At most 128,000 on these models',
         f"{count(max_tokens)} in the matrix; 1,000,000 returned HTTP 400"),
        ("`cache_control` at the top level",
         "Automatic caching: the breakpoint goes on the last cacheable block and moves forward as the conversation grows",
         "Cache test: most scenarios"),
        ("`cache_control` on a content block",
         "Explicit breakpoint: caches the prompt up to and including that block, in the order `tools`, `system`, `messages`. At most 4 breakpoints per request; a prompt under 512 tokens is not cached",
         "Cache test: after the repository files"),
        ("`cache_control.ttl`",
         f'How long an unused entry lives: `"5m"` by default, renewed on every read, or `"1h"`. Writes cost {w5:g}× the input price (5 minutes) or {w1:g}× (1 hour); reads cost {read_big:g}× on Opus and Sonnet, {read_haiku:g}× on Haiku',
         "Both: 6.5 minutes idle before the second turn"),
        ("Per-message effort",
         "An effort-only `system` message changes effort for later turns without touching the top-level field, so the cached prefix stays valid. Beta, header `anthropic-beta: mid-conversation-output-config-2026-07-01`; Foundry is not among the platforms the effort page lists for it",
         f"One cache scenario; all {count(k['requests'])} cache requests returned HTTP 200"),
        ("`temperature`, `top_p`, `top_k`",
         "Sampling. On these models any non-default value returns HTTP 400",
         "Probe only: HTTP 400 in every mode tried; never sent in the matrix"),
        ("`stream`",
         "`true` returns server-sent events, the only way to time the first visible text",
         "`true` on every timed request; the pre-warm request with `max_tokens: 0` is not streamed, as the API requires"),
        ("Deployment type, chosen when the deployment is created",
         'GlobalStandard may serve a request outside the resource\'s region; US Data Zone Standard keeps inference in the United States, like `inference_geo: "us"` on the Claude API. Sonnet 5.5 supports GlobalStandard only',
         f"GlobalStandard only; every matrix response reported `usage.inference_geo` `{geo}`"),
    ], [
        ('`thinking.type: "adaptive"`',
         "模型对每个请求自己决定要不要先思考、思考多久；`output_config.effort` 调节思考多少。这三个模型不传 `thinking` 字段时也是这样",
         "三个模型，档位 low 到 max"),
        ('`thinking.type: "between_tools"`',
         "Sonnet 5.5 最低的思考设置：回答前不思考。在工具调用之间写的简短进度仍以 thinking 块返回；不用工具时只返回文字。只接受 `high` 及以下档位",
         "Sonnet，档位 low、medium、high；不用工具"),
        ('`thinking.type: "disabled"`',
         "关闭思考。只有 Haiku 5.5 接受，且只在 `high` 及以下档位；Opus 5.5 关不掉思考",
         "Haiku，档位 low、medium、high"),
        ('`thinking.type: "enabled"` 加 `budget_tokens`',
         "旧的固定思考预算，这些模型不支持",
         "只在探测中发送：三个模型都返回 HTTP 400"),
        ("`thinking.display`",
         '是否返回思考文字。这些模型默认 `"omitted"`：thinking 块的文字为空、只带加密签名，所以回答更早开始流式返回；思考 token 照样计费。`"summarized"` 返回摘要',
         f"未发送：矩阵中 {count(m['thought'])} 个回答用了思考 token，没有一个流式返回思考文字"),
        ("`output_config.effort`",
         f"模型在整个回答上投入多少，包括思考：`low`、`medium`、`high`、`xhigh`、`max`。它是行为信号，不是 token 预算。不传时 Opus 和 Haiku 为 `{opus_default}`，Sonnet 为 `{sonnet_default}`",
         f"每种思考模式接受的全部档位，共 {cells} 格"),
        ("`max_tokens`",
         '输出 token 的硬上限，包括思考；回答达到上限时以 `stop_reason: "max_tokens"` 停止。这些模型最大 128,000',
         f"矩阵用 {count(max_tokens)}；1,000,000 返回 HTTP 400"),
        ("顶层 `cache_control`",
         "自动缓存：断点放在最后一个可缓存块上，随对话增长自动后移",
         "缓存测试的大多数场景"),
        ("内容块上的 `cache_control`",
         "显式断点：缓存到该块为止的提示，顺序为 `tools`、`system`、`messages`。每个请求最多 4 个断点；不足 512 个 token 的提示不会被缓存",
         "缓存测试：放在仓库文件之后"),
        ("`cache_control.ttl`",
         f'缓存条目闲置多久后失效：默认 `"5m"`，每次读取都会续期；也可设为 `"1h"`。写入按输入价的 {w5:g} 倍（5 分钟）或 {w1:g} 倍（1 小时）计费；读取在 Opus 和 Sonnet 上按 {read_big:g} 倍，在 Haiku 上按 {read_haiku:g} 倍',
         "两种都测了：第 2 轮前空闲 6.5 分钟"),
        ("按消息设置 effort",
         "用只含 effort 的 `system` 消息改变后续轮次的档位，不动顶层字段，缓存前缀因此保持有效。Beta 功能，请求头 `anthropic-beta: mid-conversation-output-config-2026-07-01`；effort 文档列出的支持平台中没有 Foundry",
         f"一个缓存场景；缓存测试的 {count(k['requests'])} 个请求全部返回 HTTP 200"),
        ("`temperature`、`top_p`、`top_k`",
         "采样参数。这些模型上任何非默认值都返回 HTTP 400",
         "只在探测中发送：试过的每种模式都返回 HTTP 400；矩阵从未发送"),
        ("`stream`",
         "为 `true` 时以服务端事件流返回，只有这样才能测首个可见文字的时间",
         "计时的请求都是 `true`；`max_tokens: 0` 的预热请求按 API 要求不用流式"),
        ("部署类型（创建部署时选择，不是请求参数）",
         'GlobalStandard 的请求可能在资源所在区域以外处理；US Data Zone Standard 把推理留在美国，相当于 Claude API 的 `inference_geo: "us"`。Sonnet 5.5 只支持 GlobalStandard',
         f"只测了 GlobalStandard；矩阵每个响应的 `usage.inference_geo` 都是 `{geo}`"),
    ])
    lines = ["| " + tr(chinese, "Setting | What it does | In this test", "设置 | 作用 | 本测试") + " |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return "\n".join(lines)


def purpose(d, chinese, language):
    m, k = matrix_numbers(d), cache_numbers(d)
    models = d["provenance"]["models"]
    versions = {x["version"] for x in models["deployments"]}
    require(versions == {"2"}, "the deployments are not all version 2, the Hosted on Azure version")
    version, region = next(iter(versions)), models["resourceRegion"]
    cells, n_problems, repeats = len(d["facts"]["cells"]), len(m["problems"]), m["repeats"]
    require(cells * n_problems * repeats == m["measured"] and m["warmups"] == cells, "matrix request counts do not add up")
    date = d["runs"]["matrix"]["first"][:10]
    probe_n, cache_n, requests = count(d["runs"]["probe"]["requests"]), count(k["requests"]), count(m["requests"])
    intro = tr(chinese,
               f"**What this measures.** How Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5 perform as deployed in Microsoft Foundry with the [Hosted on Azure]({HOSTING_DOC}) option: model version {version}, an Anthropic-operated service running on Azure infrastructure, in GlobalStandard deployments. For each coding request we measure how long the first visible text and the full answer take, whether the code passes the problem's own unit tests, and what the request costs at list price. The request settings in the table below change all of these, and some combinations are rejected with HTTP 400; a successful HTTP response shows none of this.",
               f"**测什么。** 测 Claude Opus 5.5、Sonnet 5.5 和 Haiku 5.5 以 [Hosted on Azure]({HOSTING_DOC}) 方式部署在 Microsoft Foundry 上时的表现：模型版本 {version}，即 Anthropic 运营、运行在 Azure 基础设施上的服务，部署类型为 GlobalStandard。对每个编码请求，我们测首个可见文字和完整回答各要等多久、写出的代码能否通过题目自带的单元测试、按标价花多少钱。下表中的请求设置会同时改变这几项，有些组合还会直接返回 HTTP 400；只看请求成功看不出这些。")
    methods = tr(chinese,
                 f"Two test methods, both calling the same Foundry resource in {region}:\n\n"
                 f"1. **Direct from a VM ({date}).** Python test scripts on a Linux VM in the same Azure region call the Foundry Messages API with the VM's managed identity: a parameter probe ({probe_n} requests), a coding matrix ({cells} accepted thinking-mode × effort cells, {n_problems} problems, {repeats} runs each, plus one warm-up per cell: {requests} requests) and a prompt-cache test ({cache_n} requests). Each model has one request in flight at a time, so this measures single requests, not load. Results come from this method unless a section says otherwise.\n"
                 "2. **Through a LiteLLM gateway on Azure Container Apps (2026-10-24).** A client sends Anthropic Messages requests to LiteLLM, which forwards them to the same deployments with its own managed identity; LiteLLM was set not to drop parameters and not to retry. That run sent a five-turn conversation from a Windows client to a gateway in Japan East, so its times include a round trip between Japan and the eastern United States. See [the results page](docs/results.md#gateway-test-2026-10-24).",
                 f"两种测试方法，调用的都是 {region} 的同一个 Foundry 资源：\n\n"
                 f"1. **从 VM 直连（{date}）。** 同一 Azure 区域的 Linux VM 上运行 Python 测试脚本，用 VM 的托管身份调用 Foundry Messages API：参数探测（{probe_n} 个请求）、编码矩阵（{cells} 个被接受的思考模式 × 推理档位组合，{n_problems} 道题各答 {repeats} 次，每格另加 1 次预热，共 {requests} 个请求）和提示缓存测试（{cache_n} 个请求）。每个模型同一时间只有 1 个请求，测的是单个请求的表现，不是压力测试。除非某节另有说明，结果都来自这种方法。\n"
                 "2. **经 Azure Container Apps 上的 LiteLLM 网关（2026-10-24）。** 客户端把 Anthropic Messages 请求发给 LiteLLM，由 LiteLLM 用自己的托管身份转发到同一组部署；LiteLLM 设置为不丢弃参数、不重试。那次测试由一台 Windows 客户端发起五轮对话，网关在 Japan East，所以时间里包含日本到美国东部的往返。详见[结果页](docs/results_CN.md#网关测试)。")
    figure = (f'<img src="images/topology-{language}.svg" width="900" alt="'
              + tr(chinese, "How we measured, method 1: one Azure region, East US 2. The only client, a Linux VM, calls one Microsoft Foundry resource with three Claude 5.5 deployments over HTTPS and runs each answer's unit tests in Docker on the same VM. On the right, the method in five steps.",
                   "测试方法 1：同一个 Azure 区域 East US 2 里，唯一的客户端 Linux VM 通过 HTTPS 调用一个 Microsoft Foundry 资源上的三个 Claude 5.5 部署，并在同一台 VM 的 Docker 中运行每个回答的单元测试。右侧分五步列出测试方法。")
              + '" />')
    caption = tr(chinese,
                 f"What the figure shows: method 1, the client, the resource and the steps behind the {date} results; times are taken on the VM, from the request being written to the first visible text. Method 2 is noted under the figure and described on [the results page](docs/results.md#gateway-test-2026-10-24). Original explanatory diagram with unmodified [Azure icons](images/icon-sources.json).",
                 f"图中内容：方法 1，即 {date} 结果背后的客户端、资源和测试步骤；时间在 VM 上计，从请求发出到首个可见文字。方法 2 在图下注明，详见[结果页](docs/results_CN.md#网关测试)。原创说明图，使用未修改的 [Azure 图标](images/icon-sources.json)。")
    settings_lead = tr(chinese,
                       "**Request settings.** What each setting does, from Claude's documentation, and what this test sent. Which values each deployment accepted comes from our probe:",
                       "**请求设置。** 每个设置的作用（依据 Claude 官方文档）和本测试发送了什么；各部署接受哪些取值来自我们的参数探测：")
    not_covered = tr(chinese,
                     "**Not covered:** tool use, where `between_tools` and progress updates matter; `display: \"summarized\"`; US Data Zone deployments; and the separate `claude-opus-5-5-fast` model in the Foundry catalog.",
                     "**未覆盖：** 工具调用（`between_tools` 和进度更新只在使用工具时才起作用）、`display: \"summarized\"`、US Data Zone 部署，以及 Foundry 模型目录里单独的 `claude-opus-5-5-fast` 模型。")
    per_model = tr(chinese,
                   f"**Per model.** What each deployment accepted and how it did on the {n_problems} problems:",
                   f"**按模型汇总。** 每个部署接受什么，以及在这 {n_problems} 道题上的表现：")
    scope = tr(chinese,
               f"**Scope.** The problems are public Exercism exercises from [Aider's polyglot benchmark]({POLYGLOT}), each answered once, without tools and without seeing the tests; they are not your production tasks. In method 1 every request went straight to the Foundry Messages API, one at a time per deployment. Costs use list prices and were not reconciled with an Azure invoice.",
               f"**范围。** 题目是 [Aider polyglot benchmark]({POLYGLOT}) 收录的 Exercism 公开练习，每次只答一次、不用工具、看不到测试；它们不是你的生产任务。方法 1 的所有请求直接发往 Foundry 的 Messages API，每个部署同一时间只有一个请求。费用按标价计算，没有与 Azure 账单核对。")
    sources = tr(chinese,
                 f"**Sources.** Accepted values and the HTTP 400 messages come from our probe ([results](docs/results.md#parameter-probe-2026-10-26)). What each setting does, the defaults, the rules for `between_tools` and `disabled`, and the advice to set `max_tokens` to 128,000 for agentic coding on Sonnet 5.5 come from Claude's [thinking]({THINKING_DOC}) and [effort]({EFFORT_DOC}) pages; cache rules and price multipliers from [prompt caching]({CACHE_DOC}); prices from [pricing]({PRICE_DOC}); hosting options and Foundry setup from [Claude in Microsoft Foundry]({FOUNDRY_DOC}); all read on 2026-10-26. The *Choose it when* row is our reading of these {n_problems} problems, not general advice.",
                 f"**来源。** 接受哪些取值、HTTP 400 的报错原文来自我们的参数探测（[结果页](docs/results_CN.md#参数探测)）。各设置的作用、默认值、`between_tools` 和 `disabled` 的使用规则，以及 Sonnet 5.5 做智能体编码时把 `max_tokens` 设为 128,000 的建议，来自 Claude 的 [thinking]({THINKING_DOC}) 和 [effort]({EFFORT_DOC}) 文档；缓存规则和价格倍数来自 [prompt caching]({CACHE_DOC})；价格来自 [pricing]({PRICE_DOC})；托管方式和 Foundry 配置来自 [Claude in Microsoft Foundry]({FOUNDRY_DOC})；均于 2026-10-26 查阅。“适合的情况”一行是我们对这 {n_problems} 道题的解读，不是通用建议。")
    return "\n\n".join([intro, methods, figure, caption, settings_lead, settings_table(d, chinese), not_covered,
                        per_model, decision_table(d, chinese), scope, sources])


# ---------- README: results ----------

def glossary(chinese):
    rows = tr(chinese, [
        ("Cell", "One model × thinking mode × effort level. Each cell answered the 18 problems three times: 54 answers"),
        ("Thinking mode, effort level", "Defined in the request-settings table under [Purpose](#purpose)"),
        ("First visible text", "Seconds from just before the request is written to the first non-empty `text_delta`, timed on the VM. Thinking comes first and its text is not streamed (`display` omitted), so this wait includes all thinking"),
        ("First event", "Seconds to the first server-sent event, `message_start`"),
        ("Full answer", "Seconds to the end of the stream, completed requests only"),
        ("Completed", "HTTP 200, `message_stop` received, `stop_reason` `end_turn` and non-empty text"),
        ("Pass", "The files in the answer, written over the exercise's solution files, make its own unit tests exit 0 in an offline container (Aider's first-attempt rule)"),
        ("By-problem 95% interval", "2.5th to 97.5th percentile over 5,000 resamples of the 18 problems (seed 20261026). The three answers to one problem are not independent, so the problem is the unit"),
        ("Cost", "List price × the token counts in the API's `usage`, cache writes and reads included"),
    ], [
        ("格", "一个模型 × 思考模式 × 推理档位的组合。每格把 18 道题各答 3 次，共 54 个回答"),
        ("思考模式、推理档位", "定义见[目的](#目的)一节的请求设置表"),
        ("首个可见文字", "从请求即将发出到收到第一个非空 `text_delta` 的秒数，在 VM 上计时。思考在它之前进行，且思考文字默认不流式返回（`display` 为 omitted），所以这段等待包含全部思考时间"),
        ("首个事件", "收到第一个服务端事件 `message_start` 的秒数"),
        ("完整回答", "收到流结束的秒数，只统计完成的请求"),
        ("完成", "HTTP 200、收到 `message_stop`、`stop_reason` 为 `end_turn` 且文字不为空"),
        ("通过", "把回答里的文件覆盖到练习的解答文件上，题目自带的单元测试在离线容器里以 0 退出（Aider 的首次作答规则）"),
        ("按题目的 95% 区间", "对 18 道题有放回重抽 5,000 次（种子 20261026）取 2.5% 到 97.5% 分位。同一道题的 3 个回答不独立，所以以题目为单位"),
        ("费用", "标价 × API 返回的 `usage` 中的 token 数，包括缓存写入和读取"),
    ])
    lines = ["| " + tr(chinese, "Term | Meaning", "术语 | 含义") + " |", "|---|---|"]
    lines += [f"| {a} | {b} |" for a, b in rows]
    return "\n".join(lines)


def where_table(d, chinese):
    m = matrix_numbers(d)
    env = d["environment"]
    kernel = env[1].split("kernel=")[1]
    versions = env[2].split()
    rows = tr(chinese, [
        ("Client: probe, matrix, cache test", "Linux VM `Standard_D4s_v5`, East US 2",
         f"Ubuntu 24.04, kernel {kernel}, Python {versions[1]}, httpx {versions[3]}, azure-identity {versions[5]}; Entra token from the VM's managed identity; TCP connect to the endpoint {m['tcp_ms']} ms median before the matrix"),
        ("Models", "Foundry resource in East US 2",
         "`claude-opus-5-5` 40,000 tokens per minute; `claude-sonnet-5-5` and `claude-haiku-5-5` 80,000 each; version 2, GlobalStandard, so a request may be served outside East US 2"),
        ("Unit tests", "Docker on the same VM",
         "`--network none`, 1.5 CPUs, 3 GB; the toolchains of Aider's benchmark image: Python 3.11, Go 1.21.5, Rust, Node 20, OpenJDK 21, CMake and Boost"),
    ], [
        ("客户端：参数探测、编码矩阵、缓存测试", "Linux VM `Standard_D4s_v5`，East US 2",
         f"Ubuntu 24.04，内核 {kernel}，Python {versions[1]}，httpx {versions[3]}，azure-identity {versions[5]}；用 VM 的托管身份取 Entra 令牌；矩阵开始前到端点的 TCP 建连中位数 {m['tcp_ms']} 毫秒"),
        ("模型", "East US 2 的 Foundry 资源",
         "`claude-opus-5-5` 每分钟 40,000 token；`claude-sonnet-5-5` 和 `claude-haiku-5-5` 各 80,000；版本 2，GlobalStandard，请求可能在 East US 2 以外执行"),
        ("单元测试", "同一台 VM 上的 Docker",
         "`--network none`，1.5 个 CPU，3 GB；工具链与 Aider 评测镜像一致：Python 3.11、Go 1.21.5、Rust、Node 20、OpenJDK 21、CMake 和 Boost"),
    ])
    lines = ["| " + tr(chinese, "Part | Where | Detail", "部分 | 位置 | 说明") + " |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return "\n".join(lines)


def request_block(d, chinese):
    system = d["problems"]["system_prompt"]
    first = system.split("\n")[0]
    user = d["problems"]["problems"][0]["user_message"].split("\n")[0]
    body = ("{\n"
            '  "model": "claude-sonnet-5-5",\n'
            '  "max_tokens": 128000,\n'
            '  "stream": true,\n'
            '  "thinking": {"type": "between_tools"},\n'
            '  "output_config": {"effort": "low"},\n'
            f'  "system": {json.dumps(first + " …", ensure_ascii=False)},\n'
            f'  "messages": [{{"role": "user", "content": {json.dumps(user + " …", ensure_ascii=False)}}}]\n'
            "}")
    lead = tr(chinese,
              "**What each matrix request sent.** One streamed Messages request per answer; the `system` and `content` values are shortened here:",
              "**编码矩阵每个请求发送的内容。** 每个回答对应一次流式 Messages 请求；这里截短了 `system` 和 `content`：")
    after = tr(chinese,
               "Only `model`, `thinking.type` and `output_config.effort` change between cells. There is no `cache_control`, no tool and no `temperature`, `top_p` or `top_k`. The full system prompt and a complete user message are quoted in [the results page](docs/results.md#coding-matrix-2026-10-26); all 18 are in [problems.json](evidence/coding-matrix-20261026/matrix/problems.json).",
               "各格之间只有 `model`、`thinking.type` 和 `output_config.effort` 不同。没有 `cache_control`、工具，也没有 `temperature`、`top_p` 或 `top_k`。完整的系统提示和一条完整的用户消息见[结果页](docs/results_CN.md#编码矩阵)；18 条全部在 [problems.json](evidence/coding-matrix-20261026/matrix/problems.json)。")
    return f"{lead}\n\n```json\n{body}\n```\n\n{after}"


def timing_table(chinese):
    rows = tr(chinese, [
        ("Accepted values", "HTTP 200 or 400 for a one-word prompt sent with each value", "[`probe.py`](coding-matrix/probe.py)"),
        ("First visible text, first event, full answer", "request written → first `text_delta`, `message_start`, end of stream; clock on the VM", "[`claude_api.py`](coding-matrix/claude_api.py) `stream_message`"),
        ("Completed, thinking and output tokens", "status, `stop_reason` and `usage` of each stream", "[`bench.py`](coding-matrix/bench.py)"),
        ("Pass", "the exercise's unit tests, offline in Docker", "[`judge.py`](coding-matrix/judge.py)"),
        ("P50, P95, intervals, cost per 1,000", "nearest rank; bootstrap over problems; mean list-price cost × 1,000", "[`analyze.py`](coding-matrix/analyze.py)"),
        ("Cache reads and writes, conversation cost", "`usage` of each turn; the same tokens priced as if nothing were cached", "[`cache_test.py`](coding-matrix/cache_test.py), [`cache_analyze.py`](coding-matrix/cache_analyze.py)"),
    ], [
        ("接受的取值", "带上每个取值发一个只需回答一个词的请求，看返回 200 还是 400", "[`probe.py`](coding-matrix/probe.py)"),
        ("首个可见文字、首个事件、完整回答", "请求发出 → 第一个 `text_delta`、`message_start`、流结束；在 VM 上计时", "[`claude_api.py`](coding-matrix/claude_api.py) `stream_message`"),
        ("完成、思考 token、输出 token", "每个流的状态、`stop_reason` 和 `usage`", "[`bench.py`](coding-matrix/bench.py)"),
        ("通过", "练习自带的单元测试，在 Docker 里离线运行", "[`judge.py`](coding-matrix/judge.py)"),
        ("P50、P95、区间、每 1,000 次费用", "最近秩分位；按题目自助重抽；平均标价费用 × 1,000", "[`analyze.py`](coding-matrix/analyze.py)"),
        ("缓存读写、整段对话费用", "每轮的 `usage`；同样的 token 按不缓存计价作对照", "[`cache_test.py`](coding-matrix/cache_test.py)、[`cache_analyze.py`](coding-matrix/cache_analyze.py)"),
    ])
    lines = ["| " + tr(chinese, "Number | From → to, or how | Script", "指标 | 起止或算法 | 脚本") + " |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return "\n".join(lines)


def interval_spans(d):
    spans = [hi - lo for cid, item in d["facts"]["intervals"]["cells"].items() if not cid.startswith("opus")
             for lo, hi in [item["ci95"]]]
    return min(spans), max(spans)


def caution(d, chinese):
    low, high = interval_spans(d)
    example = cell(d, "sonnet", "between_tools", "high")
    lo, hi = d["facts"]["intervals"]["cells"][example["cell_id"]]["ci95"]
    return tr(chinese,
              f"**Do not read these grids as a general ranking of the three models.** Opus answered all 18 problems correctly in every cell, so this test cannot separate its effort levels. With 18 problems, a Sonnet or Haiku cell's 95% interval spans {pct(low, 0)} to {pct(high, 0)} points (for example Sonnet `between_tools` · high: {example['passed']} of 54, {pct(lo, 0)}% to {pct(hi, 0)}%). The problems are short single-file exercises. Each row is one model and thinking mode, each column an effort level; *not accepted* means the API returned HTTP 400. P95, full-answer times, token counts and every interval are on [the results page](docs/results.md#results-per-cell).",
              f"**不要把下面三张表当成三个模型的通用排名。** Opus 每一格都把 18 道题全部答对，这次测试分不出它各档位的差别。只有 18 道题，Sonnet 和 Haiku 每格的 95% 区间宽 {pct(low, 0)} 到 {pct(high, 0)} 个百分点（例如 Sonnet `between_tools` · high：54 个通过 {example['passed']} 个，区间 {pct(lo, 0)}% 到 {pct(hi, 0)}%）。题目都是短小的单文件练习。每行是一个模型加一种思考模式，每列是一个推理档位；*不接受* 表示 API 返回 HTTP 400。P95、完整回答耗时、token 数和每格的区间见[结果页](docs/results_CN.md#每格结果)。")


def stands_out(d, chinese):
    m = matrix_numbers(d)
    fails = m["failures"]
    max_tokens = [r for r in fails if r["status"] == "max_tokens"]
    stalls = [r for r in fails if r["status"] == "timeout"]
    require(len(max_tokens) == 3 and len(stalls) == 1 and all(r["model"] == "claude-haiku-5-5" for r in max_tokens), "failure set changed")
    stall = stalls[0]
    require(stall["event_types"] == {"message_start": 1, "content_block_start": 1, "ping": 2}, "stall events changed")
    so, ha = thinking(d, "sonnet"), thinking(d, "haiku")
    opus_low, opus_max = cell(d, "opus", "adaptive", "low"), cell(d, "opus", "adaptive", "max")
    sonnet_passes = [c["passed"] for c in model_cells(d, "sonnet")]
    pp = m["per_problem"]
    haiku_zero = [p for p in m["problems"] if pp[("haiku", p)][0] == 0]
    require(all(pp[("opus", p)][0] == pp[("opus", p)][1] for p in m["problems"]), "Opus missed a problem")
    house, promises = pp[("sonnet", "java/house")], pp[("sonnet", "javascript/promises")]
    maxes = {model: cell(d, model, "adaptive", "max")["first_text_p50_s"] for model in MODELS}
    event_low = min(c["first_event_p50_s"] for c in d["facts"]["cells"])
    event_high = max(c["first_event_p50_s"] for c in d["facts"]["cells"])
    return "\n".join(tr(chinese, [
        "What stands out:",
        f"- **The platform answered every request.** All {count(m['requests'])} matrix requests returned HTTP 200, none with 429 or 5xx, and {count(m['completed'])} of the {count(m['measured'])} measured requests completed. Of the other four, three Haiku `adaptive` · max answers spent all 128,000 output tokens on thinking (`stop_reason: max_tokens`), and one Sonnet `adaptive` · max stream sent `message_start` and two pings, then nothing until the client's 600 s read timeout ended it at {stall['timing']['end']:.0f} s.",
        f"- **Without thinking, text starts in under half a second.** Sonnet `between_tools` and Haiku `disabled` showed the first visible text after {secs(m['off_p50'])} s P50 and {secs(m['off_p95'])} s P95 over {m['off_n']} requests. The first event came after {secs(m['first_event_p50'])} s P50 over all requests, and between {secs(event_low)} and {secs(event_high)} s P50 in each cell; the rest of the wait is thinking, which is not streamed. At effort max the first visible text took {secs(maxes['opus'])} s (Opus), {secs(maxes['sonnet'])} s (Sonnet) and {secs(maxes['haiku'])} s (Haiku), P50.",
        f"- **Thinking raised Haiku's pass rate, not Sonnet's.** At the same three effort levels, Haiku passed {pct(ha['on_share'])}% with `adaptive` and {pct(ha['off_share'])}% with `disabled`: {pct(ha['difference'], sign=True)} points (95% interval {pct(ha['difference_ci95'][0], sign=True)} to {pct(ha['difference_ci95'][1], sign=True)}; {ha['problems_better_on']} problems better, {ha['problems_better_off']} worse, {ha['problems_equal']} equal). Sonnet: {pct(so['on_share'])}% against {pct(so['off_share'])}% with `between_tools`, {pct(so['difference'], sign=True)} points ({pct(so['difference_ci95'][0], sign=True)} to {pct(so['difference_ci95'][1], sign=True)}).",
        f"- **Higher effort mostly bought time and cost.** Opus cost {usd(opus_low['cost_per_1k_requests_usd'])} per 1,000 requests at low and {usd(opus_max['cost_per_1k_requests_usd'])} at max for the same 54 passes. Sonnet's eight cells passed {min(sonnet_passes)} to {max(sonnet_passes)} times each, inside one another's intervals.",
        f"- **The problem mattered more than the setting.** Over all its cells Sonnet passed `java/house` {house[0]} time in {house[1]} and `javascript/promises` {promises[0]} times in {promises[1]}; Haiku never passed {len(haiku_zero)} of the 18 problems. Opus passed every problem every time.",
    ], [
        "值得注意的几点：",
        f"- **平台接住了每一个请求。** 矩阵的 {count(m['requests'])} 个请求全部返回 HTTP 200，没有 429，也没有 5xx；{count(m['measured'])} 个计分请求中 {count(m['completed'])} 个完成。另外 4 个里，3 个是 Haiku `adaptive` · max 把 128,000 个输出 token 全部用在思考上（`stop_reason: max_tokens`）；1 个是 Sonnet `adaptive` · max 的流在发出 `message_start` 和两个 ping 后再无数据，直到客户端 600 秒读超时在第 {stall['timing']['end']:.0f} 秒结束它。",
        f"- **不思考时，文字半秒内就开始出现。** Sonnet `between_tools` 和 Haiku `disabled` 共 {m['off_n']} 个请求，首个可见文字 P50 为 {secs(m['off_p50'])} 秒，P95 为 {secs(m['off_p95'])} 秒。全部请求的首个事件 P50 为 {secs(m['first_event_p50'])} 秒，各格在 {secs(event_low)} 到 {secs(event_high)} 秒之间；其余的等待是思考，思考内容不流式返回。effort 为 max 时，首个可见文字 P50 为 {secs(maxes['opus'])} 秒（Opus）、{secs(maxes['sonnet'])} 秒（Sonnet）、{secs(maxes['haiku'])} 秒（Haiku）。",
        f"- **思考提高了 Haiku 的通过率，没有提高 Sonnet 的。** 在相同的三个档位上，Haiku 用 `adaptive` 通过 {pct(ha['on_share'])}%，用 `disabled` 通过 {pct(ha['off_share'])}%，高 {pct(ha['difference'])} 个百分点（95% 区间 {pct(ha['difference_ci95'][0], sign=True)} 到 {pct(ha['difference_ci95'][1], sign=True)}；{ha['problems_better_on']} 道题更好，{ha['problems_better_off']} 道更差，{ha['problems_equal']} 道持平）。Sonnet 用 `adaptive` 通过 {pct(so['on_share'])}%，用 `between_tools` 通过 {pct(so['off_share'])}%，{'低' if so['difference'] < 0 else '高'} {pct(abs(so['difference']))} 个百分点（区间 {pct(so['difference_ci95'][0], sign=True)} 到 {pct(so['difference_ci95'][1], sign=True)}）。",
        f"- **提高推理档位主要换来更长的时间和更高的费用。** Opus 同样 54 个全过，low 每 1,000 次请求 {usd(opus_low['cost_per_1k_requests_usd'])}，max 要 {usd(opus_max['cost_per_1k_requests_usd'])}。Sonnet 的 8 格每格通过 {min(sonnet_passes)} 到 {max(sonnet_passes)} 个，彼此都在对方的区间内。",
        f"- **题目本身比设置影响更大。** Sonnet 所有格合计，`java/house` {house[1]} 次只过了 {house[0]} 次，`javascript/promises` {promises[1]} 次过了 {promises[0]} 次；Haiku 有 {len(haiku_zero)} 道题一次都没过。Opus 每道题每次都过。",
    ]))


def caching(d, chinese):
    k = cache_numbers(d)
    ctx = k["context"]
    pairs = k["pairs"]

    def pair(model, size):
        p = pairs[(DEPLOYMENT[model], size)]
        return f"{secs(p['cold_first_text_p50_s'])} → {secs(p['warm_first_text_p50_s'])} {tr(chinese, 's', '秒')}"

    def r(values, fmt=count):
        return span(values[0], values[1], lambda v: fmt(round(v)))

    def share(values, digits=0):
        return span(values[0], values[1], lambda v: pct(v, digits)) + "%"

    def saving(values):
        low, high = sorted(abs(v) for v in values)
        return span(low, high, lambda v: pct(v, 0)) + "%"

    repo_tokens = round(pairs[("claude-opus-5-5", "repo")]["prompt_tokens"], -2)
    large_tokens = round(pairs[("claude-sonnet-5-5", "large")]["prompt_tokens"], -2)
    lead = tr(chinese,
              f"**Prompt caching in a four-turn coding conversation.** Each conversation sends the same instructions and three httpx source files (about {count(int(repo_tokens))} tokens) as the system prompt, then four questions in turn: how an `Auth` subclass takes part in a request, a new `BearerTokenAuth` class, pytest tests for it, and a commit message. Opus uses `adaptive`, Sonnet `between_tools` and Haiku `disabled`, effort low, two repetitions per scenario. Each scenario changes one thing; results are the range over the three models:",
              f"**四轮编码对话中的提示缓存。** 每段对话都把同样的说明和三个 httpx 源文件（约 {count(int(repo_tokens))} 个 token）作为系统提示，再依次问四个问题：`Auth` 子类在请求中怎样起作用、写一个新的 `BearerTokenAuth` 类、为它写 pytest 测试、写提交信息。Opus 用 `adaptive`，Sonnet 用 `between_tools`，Haiku 用 `disabled`，推理档位 low，每个场景重复 2 次。每个场景只改一处；结果是三个模型的范围：")
    rows = tr(chinese, [
        ("Automatic caching", "top-level `cache_control` on every turn", f"turns 2–4 read {share(k['auto_share'])} of the prompt from cache; the conversation cost {saving(k['auto_saving'])} less than the same tokens without cache"),
        ("Breakpoint after the files, new conversation", "`cache_control` on the repository block; then a second conversation with the same files and a new question", f"the new conversation read {r(k['second_read'])} tokens from cache and cost {saving(k['second_saving'])} less"),
        ("Automatic caching only, new conversation", "top-level `cache_control`; then a second conversation with the same files", f"read {r(k['auto_second_read'])} tokens and wrote a new entry: {saving(k['auto_second_saving'])} more than without cache"),
        ("Top-level effort change", "effort low → high on turn 3", f"turn 3 still read {share(k['effort_share'])} of the prompt from cache"),
        ("Per-message effort", "the same change as an effort-only system message, beta header `mid-conversation-output-config-2026-07-01`", f"turn 3 read {share(k['message_share'])} from cache"),
        ("Thinking mode change (Sonnet, Haiku)", "thinking off → `adaptive` on turn 3", f"turn 3 read {r(k['mode_read'])} tokens and rewrote {r(k['mode_write'])}; turn 4 read {share(k['mode_t4_share'])} again"),
        ("6.5 minutes idle, 5-minute TTL", "default TTL", f"turn 2 read {r(k['idle5_read'])} tokens and rewrote {r(k['idle5_write'])}"),
        ("6.5 minutes idle, 1-hour TTL", "`\"ttl\": \"1h\"`", f"turn 2 read {r(k['idle1h_read'])} tokens"),
        ("Pre-warm", "a non-streaming request with `max_tokens: 0`, then the first question", f"the first question read {r(k['prewarm_read'])} tokens ({share(k['prewarm_share'], 1)} of its prompt)"),
        ("Cold and warm, same prompt", "five pairs, one-word answer",
         f"first visible text P50 at about {count(int(repo_tokens))} tokens: Opus {pair('opus', 'repo')}, Sonnet {pair('sonnet', 'repo')}, Haiku {pair('haiku', 'repo')}; at about {count(int(large_tokens))}: Sonnet {pair('sonnet', 'large')}, Haiku {pair('haiku', 'large')}. The warm request cost {share(k['warm_cost_ratio'])} of the cold one"),
    ], [
        ("自动缓存", "每轮都带顶层 `cache_control`", f"第 2–4 轮有 {share(k['auto_share'])} 的提示从缓存读取；整段对话比同样 token 不缓存便宜 {saving(k['auto_saving'])}"),
        ("在文件后设断点，开新对话", "在仓库文件块上放 `cache_control`；再开一段文件相同、问题不同的对话", f"新对话从缓存读取 {r(k['second_read'])} 个 token，便宜 {saving(k['second_saving'])}"),
        ("只用自动缓存，开新对话", "顶层 `cache_control`；再开一段文件相同的对话", f"读取 {r(k['auto_second_read'])} 个 token，又写了一份新缓存：比不缓存贵 {saving(k['auto_second_saving'])}"),
        ("改顶层推理档位", "第 3 轮把 effort 从 low 改成 high", f"第 3 轮仍有 {share(k['effort_share'])} 的提示从缓存读取"),
        ("按消息改推理档位", "同样的改动用只含 effort 的 system 消息表达，beta 头 `mid-conversation-output-config-2026-07-01`", f"第 3 轮有 {share(k['message_share'])} 从缓存读取"),
        ("切换思考模式（Sonnet、Haiku）", "第 3 轮从不思考改为 `adaptive`", f"第 3 轮读取 {r(k['mode_read'])} 个 token，重写 {r(k['mode_write'])} 个；第 4 轮又有 {share(k['mode_t4_share'])} 从缓存读取"),
        ("空闲 6.5 分钟，5 分钟 TTL", "默认 TTL", f"第 2 轮读取 {r(k['idle5_read'])} 个 token，重写 {r(k['idle5_write'])} 个"),
        ("空闲 6.5 分钟，1 小时 TTL", "`\"ttl\": \"1h\"`", f"第 2 轮读取 {r(k['idle1h_read'])} 个 token"),
        ("预热", "先发一个 `max_tokens: 0` 的非流式请求，再问第一个问题", f"第一个问题从缓存读取 {r(k['prewarm_read'])} 个 token（占其提示的 {share(k['prewarm_share'], 1)}）"),
        ("冷请求与热请求，提示相同", "五对，只答一个词",
         f"约 {count(int(repo_tokens))} 个 token 时首个可见文字 P50：Opus {pair('opus', 'repo')}，Sonnet {pair('sonnet', 'repo')}，Haiku {pair('haiku', 'repo')}；约 {count(int(large_tokens))} 个 token 时：Sonnet {pair('sonnet', 'large')}，Haiku {pair('haiku', 'large')}。热请求的费用是冷请求的 {share(k['warm_cost_ratio'])}"),
    ])
    table = ["| " + tr(chinese, "Scenario | What changed | Result", "场景 | 改了什么 | 结果") + " |", "|---|---|---|"]
    table += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    note = tr(chinese,
              f"Claude's [effort page]({EFFORT_DOC}) says that changing the top-level effort between requests invalidates cache breakpoints. In this test, with automatic caching, turn 3 still read the cached prefix; we did not find out why, so treat it as an observation on these deployments on 2026-10-26. The per-message form, which the docs say keeps the cache, behaved the same. All {count(k['requests'])} cache requests returned HTTP 200. Per-turn read shares and costs are on [the results page](docs/results.md#prompt-caching-2026-10-26).",
              f"Claude 的 [effort 文档]({EFFORT_DOC}) 写明：两次请求之间改动顶层 effort 会让缓存断点失效。本测试在自动缓存下，第 3 轮仍然读到了缓存前缀；原因未查明，只能当作 2026-10-26 这些部署上的观察结果。文档说明会保留缓存的按消息改档方式，表现相同。缓存测试的 {count(k['requests'])} 个请求全部返回 HTTP 200。每轮的读取占比和费用见[结果页](docs/results_CN.md#提示缓存)。")
    return "\n\n".join([lead, "\n".join(table), note])


def gateway_summary(gateway, chinese):
    groups = gateway["groups"]
    ttft = [g["ttftSeconds"]["p50"] for g in groups.values()]
    off = [g["ttftSeconds"]["p50"] for g in groups.values() if g["config"]["thinking"] != "adaptive"]
    return tr(chinese,
              f"**Through a LiteLLM gateway (2026-10-24).** An earlier test sent a five-turn source-review conversation through LiteLLM 1.106.2 on Azure Container Apps in Japan East to the same East US 2 resource, in ten configurations at effort medium. {'All 50 requests' if gateway['requests'] == 50 else str(gateway['requests']) + ' of 50 requests'} completed, and the gateway's outbound log showed the model, thinking mode, effort, `stream`, `max_tokens` and cache markers of every request reaching Foundry unchanged. First visible text P50 was {secs(min(off))} to {secs(max(off))} s with thinking off and up to {secs(max(ttft))} s with `adaptive`. The gateway and the models were in different regions, so these times include a round trip between Japan and the eastern United States and do not measure the gateway's own overhead. Its full tables are on [the results page](docs/results.md#gateway-test-2026-10-24).",
              f"**经过 LiteLLM 网关（2026-10-24）。** 更早的一次测试把五轮代码审阅对话经 Japan East 的 Azure Container Apps 上的 LiteLLM 1.106.2 发到同一个 East US 2 资源，共十种配置，推理档位 medium。{'50 个请求全部完成' if gateway['requests'] == 50 else f"50 个请求完成 {gateway['requests']} 个"}；网关自己的出站日志显示，每个请求的模型、思考模式、推理档位、`stream`、`max_tokens` 和缓存标记都原样到达 Foundry。首个可见文字 P50 在关闭思考时为 {secs(min(off))} 到 {secs(max(off))} 秒，`adaptive` 时最高 {secs(max(ttft))} 秒。网关和模型不在同一个区域，这些时间包含日本到美国东部的往返，不能代表网关本身增加的延迟。完整表格见[结果页](docs/results_CN.md#网关测试)。")


def runs_table(d, gateway, chinese):
    runs = d["runs"]
    m = matrix_numbers(d)
    pilot = runs["pilot-32k"]

    def when(r):
        return f"2026-10-26 {utc_time(r['first'])}–{utc_time(r['last'])}" if utc_time(r["first"]) != utc_time(r["last"]) else f"2026-10-26 {utc_time(r['first'])}"
    rows = tr(chinese, [
        ("`probe`", when(runs["probe"]), "accepted values, one-word prompt", runs["probe"]["requests"], runs["probe"]["cost"],
         f"{runs['probe']['http'][200]} × HTTP 200, {runs['probe']['http'][400]} × HTTP 400"),
        ("`smoke`", when(runs["smoke"]), "one problem in each of the 21 cells, `max_tokens` 32,000", runs["smoke"]["requests"], runs["smoke"]["cost"],
         f"{runs['smoke']['statuses']['completed']} completed"),
        ("`pilot-32k`", when(pilot), "the matrix with `max_tokens` 32,000", pilot["requests"], pilot["cost"],
         f"stopped: {pilot['statuses']['max_tokens']} answers hit 32,000 tokens and {pilot['http'][429]} hit the output-token-per-minute limit (HTTP 429); not used in the results"),
        ("`matrix`", when(runs["matrix"]), "21 cells × 18 problems × 3, plus 21 warm-ups", runs["matrix"]["requests"], runs["matrix"]["cost"],
         f"{count(m['completed'])} of {count(m['measured'])} completed; no 429"),
        ("`cache`", when(runs["cache"]), "caching scenarios", runs["cache"]["requests"], runs["cache"]["cost"],
         f"{runs['cache']['http'][200]} × HTTP 200"),
        ("`gateway`", "2026-10-24", "five-turn conversation through LiteLLM, ten configurations", 50, gateway["costUsd"],
         f"{gateway['requests']} completed"),
    ], [
        ("`probe`", when(runs["probe"]), "接受的取值，只需回答一个词", runs["probe"]["requests"], runs["probe"]["cost"],
         f"{runs['probe']['http'][200]} 个 HTTP 200，{runs['probe']['http'][400]} 个 HTTP 400"),
        ("`smoke`", when(runs["smoke"]), "21 格各答一道题，`max_tokens` 32,000", runs["smoke"]["requests"], runs["smoke"]["cost"],
         f"{runs['smoke']['statuses']['completed']} 个完成"),
        ("`pilot-32k`", when(pilot), "`max_tokens` 32,000 的矩阵", pilot["requests"], pilot["cost"],
         f"已停止：{pilot['statuses']['max_tokens']} 个回答用满 32,000 token，{pilot['http'][429]} 个触发每分钟输出 token 上限（HTTP 429）；不计入结果"),
        ("`matrix`", when(runs["matrix"]), "21 格 × 18 题 × 3 次，另有 21 个预热请求", runs["matrix"]["requests"], runs["matrix"]["cost"],
         f"{count(m['measured'])} 个中 {count(m['completed'])} 个完成；没有 429"),
        ("`cache`", when(runs["cache"]), "缓存场景", runs["cache"]["requests"], runs["cache"]["cost"],
         f"{runs['cache']['http'][200]} 个 HTTP 200"),
        ("`gateway`", "2026-10-24", "经 LiteLLM 的五轮对话，十种配置", 50, gateway["costUsd"],
         f"{gateway['requests']} 个完成"),
    ])
    head = tr(chinese, "| Run | When, UTC | What | Requests | List-price cost | Result |",
              "| 运行 | 时间（UTC） | 内容 | 请求数 | 标价费用 | 结果 |")
    lines = [head, "|---|---|---|---:|---:|---|"]
    lines += [f"| {a} | {b} | {c} | {count(n)} | {usd(cost)} | {e} |" for a, b, c, n, cost, e in rows]
    total = sum(runs[name]["cost"] for name in ("probe", "smoke", "pilot-32k", "matrix", "cache"))
    after = tr(chinese,
               f"The 2026-10-26 runs cost {usd(total)} at list prices. Their records are in [`evidence/coding-matrix-20261026/`](evidence/coding-matrix-20261026/), with the endpoint and VM names replaced; the 2026-10-24 records are in [`evidence/`](evidence/).",
               f"2026-10-26 的几次运行按标价共 {usd(total)}。记录在 [`evidence/coding-matrix-20261026/`](evidence/coding-matrix-20261026/)，端点和 VM 名称已替换；2026-10-24 的记录在 [`evidence/`](evidence/)。")
    lead = tr(chinese, "**Measured runs.**", "**每次实测。**")
    return f"{lead}\n\n" + "\n".join(lines) + f"\n\n{after}"


def limits(d, chinese):
    m = matrix_numbers(d)
    return "\n".join(tr(chinese, [
        "**Limits.**",
        "- **One client, one region, one day, one request at a time per deployment.** No concurrency, load or soak test, and no client outside Azure.",
        "- **Public exercises, first attempt, no tools.** As in Aider's benchmark the model sees the stub and the instructions but not the tests. `between_tools` differs from `disabled` only in tool loops, which this test never ran.",
        "- **Ceiling and sample size.** Opus passed all 54 answers in every cell, and 18 problems give wide intervals; a difference of a few answers between two cells is within noise.",
        f"- **Thinking display.** {count(m['thought'])} matrix requests used thinking tokens and {m['thought_streamed']} streamed any thinking text, so the first visible text includes all thinking. `display: \"summarized\"` was not tested.",
        f"- **Routing.** GlobalStandard deployments may serve a request outside East US 2, and all {count(sum(m['geo'].values()))} matrix responses reported `usage.inference_geo` as `{m['geo_value']}`; other client locations or deployment types will give other latencies.",
        "- **Cost.** List prices on 2026-10-26, not an Azure invoice.",
        "- **Gateway.** The 2026-10-24 gateway ran in another region; a gateway in the same region as the models has not been tested.",
    ], [
        "**边界。**",
        "- **一个客户端、一个区域、一天、每个部署同一时间一个请求。** 没有并发、压力或长时间测试，也没有 Azure 以外的客户端。",
        "- **公开练习、只答一次、不用工具。** 与 Aider 的评测一样，模型能看到待补全的文件和题目说明，看不到测试。`between_tools` 与 `disabled` 只在工具循环里有区别，本测试没有工具循环。",
        "- **上限与样本量。** Opus 每格 54 个全过；18 道题的区间很宽，两格之间差几个回答属于噪声范围。",
        f"- **思考内容的显示。** 矩阵中 {count(m['thought'])} 个请求用了思考 token，流式返回思考文字的有 {m['thought_streamed']} 个，所以首个可见文字包含全部思考时间。没有测试 `display: \"summarized\"`。",
        f"- **路由。** GlobalStandard 部署可能在 East US 2 以外处理请求，矩阵的 {count(sum(m['geo'].values()))} 个响应里 `usage.inference_geo` 都是 `{m['geo_value']}`；换客户端位置或部署类型，延迟会不同。",
        "- **费用。** 按 2026-10-26 的标价计算，不是 Azure 账单。",
        "- **网关。** 2026-10-24 的网关在另一个区域；与模型同区域的网关尚未测试。",
    ]))


def navigation(chinese):
    suffix = "_CN" if chinese else ""
    rows = tr(chinese, [
        ("See every cell, problem, probe message and cache turn", f"[Results](docs/results{suffix}.md)"),
        ("Repeat the tests or run the offline checks", f"[Testing](docs/testing{suffix}.md)"),
        ("Check what each public script changed from the measured one", "[Provenance](evidence/coding-matrix-20261026/provenance.json)"),
    ], [
        ("查看每一格、每道题、每条探测报错和每轮缓存", f"[实测结果](docs/results{suffix}.md)"),
        ("重做测试或运行离线检查", f"[复测与核验](docs/testing{suffix}.md)"),
        ("核对公开脚本相对实测脚本改了什么", "[来源记录](evidence/coding-matrix-20261026/provenance.json)"),
    ])
    lines = ["| " + tr(chinese, "You want to | Read", "想要 | 去看") + " |", "|---|---|"]
    lines += [f"| {a} | {b} |" for a, b in rows]
    return "\n".join(lines)


def results(d, gateway, chinese):
    parts = [
        tr(chinese, "Words used in the results:", "看结果时会用到的词："), glossary(chinese),
        tr(chinese, "**Where each part ran.**", "**各部分在哪里运行。**"), where_table(d, chinese),
        request_block(d, chinese),
        tr(chinese, "**How each number is measured, and the scripts.**", "**每个指标怎么测、用哪个脚本。**"), timing_table(chinese),
        caution(d, chinese), grids(d, chinese), stands_out(d, chinese), caching(d, chinese),
        gateway_summary(gateway, chinese), runs_table(d, gateway, chinese), limits(d, chinese), navigation(chinese),
    ]
    return "\n\n".join(parts)


# ---------- README: steps ----------

def steps(d, chinese):
    suffix = "_CN" if chinese else ""
    step4 = read_json(EV / "readme-step4.json")
    result = step4["stderr_result"]
    require(step4["exit_code"] == 0 and result["status"] == "completed", "README step 4 check did not pass")
    sample = f'{{"status": "completed", "http_status": {result["http_status"]}, "first_text_s": {result["first_text_s"]}, ...}}'
    blocks = [
        tr(chinese,
           f"**Deploy first, then call.** These steps deploy the three models and send one streamed request with the request shape used in the tests. Repeating the measurements, the 2026-10-24 gateway test and the offline checks are in [docs/testing.md](docs/testing{suffix}.md).",
           f"**先部署，再调用。** 下面的步骤部署三个模型，并用测试中的请求格式发一个流式请求。重做测量、2026-10-24 的网关测试和离线检查见 [docs/testing_CN.md](docs/testing{suffix}.md)。"),
        tr(chinese,
           f"**Execution boundary:** the 2026-10-26 results came from these scripts, on a VM created with the commands of step 3 under our own resource names. The repository was assembled afterwards. Step 4 was then run once from the same VM with the published `claude_api.py`, `pricing.py` and `call_once.py`: completed, HTTP {result['http_status']}, first visible text after {secs(result['first_text_s'])} s ([record](evidence/coding-matrix-20261026/readme-step4.json)). Steps 1 to 3 have not been re-run in a fresh subscription.",
           f"**执行边界：** 2026-10-26 的结果由这些脚本产生，所用 VM 由第 3 步的命令（换成我们自己的资源名）创建。仓库是事后整理的。整理后在同一台 VM 上用公开的 `claude_api.py`、`pricing.py` 和 `call_once.py` 运行了一次第 4 步：完成，HTTP {result['http_status']}，首个可见文字在 {secs(result['first_text_s'])} 秒后出现（[记录](evidence/coding-matrix-20261026/readme-step4.json)）。第 1 到 3 步还没有在全新订阅中重跑。"),
        tr(chinese,
           "| Order | Where | Action | Entry |\n|---|---|---|---|\n| 1 | Bash with Azure CLI | Sign in and name the resources | `az login` |\n| 2 | Foundry portal and Azure CLI | Deploy the three models | `az cognitiveservices account deployment create` |\n| 3 | Azure CLI | Create a VM in the same region and let its identity call Foundry | `az vm create`, `az role assignment create` |\n| 4 | The VM | Install the client and send one request | [`coding-matrix/call_once.py`](coding-matrix/call_once.py) |",
           "| 顺序 | 位置 | 操作 | 入口 |\n|---|---|---|---|\n| 1 | 装有 Azure CLI 的 Bash | 登录并填写资源名 | `az login` |\n| 2 | Foundry 门户和 Azure CLI | 部署三个模型 | `az cognitiveservices account deployment create` |\n| 3 | Azure CLI | 在同一区域创建 VM，并允许它的身份调用 Foundry | `az vm create`、`az role assignment create` |\n| 4 | VM | 安装客户端并发一个请求 | [`coding-matrix/call_once.py`](coding-matrix/call_once.py) |"),
        tr(chinese,
           "**Prerequisites.** Bash with Azure CLI (we used 2.91.0; Azure Cloud Shell works); a Foundry resource in a region that offers Claude 5.5 (East US 2 here); permission to deploy models, create a VM and assign roles on the Foundry resource; Claude 5.5 quota; and the Marketplace terms for Anthropic models, which the subscription owner accepts in the portal on the first deployment. Model calls, the VM and its disk are charged.",
           "**前提。** 装有 Azure CLI 的 Bash（我们用的是 2.91.0；Azure Cloud Shell 也可以）；位于提供 Claude 5.5 的区域的 Foundry 资源（这里是 East US 2）；部署模型、创建 VM 和在 Foundry 资源上分配角色的权限；Claude 5.5 配额；以及 Anthropic 模型的 Marketplace 条款，首次部署时由订阅所有者在门户中接受。模型调用、VM 和磁盘都会产生费用。"),
        tr(chinese,
           "**1. Sign in and name the resources.** Fill in the five values; `LOCATION` is the Foundry resource's region.",
           "**1. 登录并填写资源名。** 填好五个值；`LOCATION` 是 Foundry 资源所在的区域。"),
        """```bash
SUBSCRIPTION_ID="<subscription-id>"
FOUNDRY_RG="<resource-group-of-the-Foundry-resource>"
FOUNDRY="<Foundry-resource-name>"
VM_RG="<new-resource-group-for-the-client-VM>"
LOCATION="eastus2"
az login
az account set --subscription "$SUBSCRIPTION_ID"
az cognitiveservices account show -g "$FOUNDRY_RG" -n "$FOUNDRY" --query "{name:name, location:location}" -o table
```""",
        tr(chinese,
           "Success: the last command prints the resource and its region. If it fails, check the subscription and the resource names before going on.",
           "成功时最后一条命令输出资源名和区域。失败时先核对订阅和资源名再继续。"),
        tr(chinese,
           "**2. Deploy the three models.** Capacity is thousands of tokens per minute; these are the values of the test (Opus 40, Sonnet and Haiku 80). If a command fails on Marketplace terms, deploy that model once in the Foundry portal (**Discover → Models**, then **Deploy → Custom settings**, deployment type **Global**, version 2) and run the command again.",
           "**2. 部署三个模型。** capacity 的单位是每分钟千 token；这里用的是测试时的值（Opus 40，Sonnet 和 Haiku 各 80）。如果命令因 Marketplace 条款失败，先在 Foundry 门户部署一次该模型（**Discover → Models**，然后 **Deploy → Custom settings**，部署类型选 **Global**，版本 2），再重新运行命令。"),
        """```bash
az cognitiveservices account deployment create -g "$FOUNDRY_RG" -n "$FOUNDRY" --deployment-name claude-opus-5-5 \\
  --model-name claude-opus-5-5 --model-version 2 --model-format Anthropic --sku-name GlobalStandard --sku-capacity 40
az cognitiveservices account deployment create -g "$FOUNDRY_RG" -n "$FOUNDRY" --deployment-name claude-sonnet-5-5 \\
  --model-name claude-sonnet-5-5 --model-version 2 --model-format Anthropic --sku-name GlobalStandard --sku-capacity 80
az cognitiveservices account deployment create -g "$FOUNDRY_RG" -n "$FOUNDRY" --deployment-name claude-haiku-5-5 \\
  --model-name claude-haiku-5-5 --model-version 2 --model-format Anthropic --sku-name GlobalStandard --sku-capacity 80
az cognitiveservices account deployment list -g "$FOUNDRY_RG" -n "$FOUNDRY" \\
  --query "[?properties.model.format=='Anthropic'].{name:name, sku:sku.name, capacity:sku.capacity, version:properties.model.version, state:properties.provisioningState}" -o table
```""",
        tr(chinese,
           "Success: three rows with `GlobalStandard`, version `2` and `Succeeded`. Without quota, request it rather than switching models. The test client paces itself to these capacities (`TPM` in `bench.py` and `cache_test.py`); with other capacities, change those two values before repeating the measurements.",
           "成功时输出三行，都是 `GlobalStandard`、版本 `2`、`Succeeded`。没有配额就申请配额，不要换模型。测试客户端按这些容量控制发送速度（`bench.py` 和 `cache_test.py` 里的 `TPM`）；容量不同，重做测量前先改这两处。"),
        tr(chinese,
           "**3. Create the client VM in the same region.** The VM gets a system-assigned managed identity, and `Cognitive Services User` on the Foundry resource lets that identity call the models. `--nsg-rule NONE` opens no inbound port: connect through Azure Bastion (we used it), or add an SSH rule limited to your own IP address.",
           "**3. 在同一区域创建客户端 VM。** VM 带系统分配的托管身份；在 Foundry 资源上授予该身份 `Cognitive Services User`，它就能调用模型。`--nsg-rule NONE` 不开放任何入站端口：通过 Azure Bastion 连接（我们用的方式），或者添加一条只允许你自己 IP 的 SSH 规则。"),
        """```bash
az group create -n "$VM_RG" -l "$LOCATION"
az vm create -g "$VM_RG" -n claude-client -l "$LOCATION" \\
  --image Canonical:ubuntu-24_04-lts:server:latest --size Standard_D4s_v5 --os-disk-size-gb 128 \\
  --admin-username azureuser --generate-ssh-keys --assign-identity '[system]' \\
  --public-ip-sku Standard --nsg-rule NONE
PRINCIPAL_ID=$(az vm show -g "$VM_RG" -n claude-client --query identity.principalId -o tsv)
FOUNDRY_ID=$(az cognitiveservices account show -g "$FOUNDRY_RG" -n "$FOUNDRY" --query id -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \\
  --role "Cognitive Services User" --scope "$FOUNDRY_ID"
```""",
        tr(chinese,
           "Success: `az vm create` prints `\"powerState\": \"VM running\"` and the role assignment prints its JSON. A new role assignment can take a few minutes to apply.",
           "成功时 `az vm create` 输出 `\"powerState\": \"VM running\"`，角色分配输出它的 JSON。新分配的角色可能要几分钟才生效。"),
        tr(chinese,
           "**4. Install the client and send one request.** Run this on the VM. Set `FOUNDRY_ANTHROPIC_BASE` to your resource's endpoint ending in `/anthropic`.",
           "**4. 安装客户端并发一个请求。** 在 VM 上运行。把 `FOUNDRY_ANTHROPIC_BASE` 设为你的资源以 `/anthropic` 结尾的端点。"),
        """```bash
sudo apt-get update && sudo apt-get install -y python3-venv git
git clone --filter=blob:none --sparse --depth=1 https://github.com/david-xinyuwei/david-share.git
git -C david-share sparse-checkout set Agents/Claude-Foundry-LiteLLM-Performance
cd david-share/Agents/Claude-Foundry-LiteLLM-Performance/coding-matrix
python3 -m venv ~/venv && ~/venv/bin/pip install -r requirements.txt
export FOUNDRY_ANTHROPIC_BASE="https://<foundry-resource>.services.ai.azure.com/anthropic"
~/venv/bin/python call_once.py --model claude-sonnet-5-5 --thinking between_tools --effort low \\
  "Write a Python function that returns the n-th Fibonacci number."
```""",
        tr(chinese,
           f"Success: the answer, then a line such as `{sample}`, and exit code 0. HTTP 401 or 403: the role has not applied yet or was assigned on another resource; wait and retry. HTTP 400: the model does not accept that thinking mode or effort (see the first table). HTTP 404: the deployment name or the endpoint is wrong.",
           f"成功时先输出回答，再输出一行类似 `{sample}` 的结果，退出码 0。HTTP 401 或 403：角色还没生效，或者分配到了别的资源上，稍等后重试。HTTP 400：模型不接受这个思考模式或推理档位（见第一张表）。HTTP 404：部署名或端点写错了。"),
        tr(chinese,
           f"**Done.** The three deployments answer a client in their own region with the parameters used here. To repeat the measurements, follow [docs/testing.md](docs/testing{suffix}.md).",
           f"**完成。** 三个部署已能用这里的参数回答同区域客户端的请求。要重做测量，按 [docs/testing_CN.md](docs/testing{suffix}.md) 操作。"),
        tr(chinese,
           "**Remove resources only after the owner approves; this is not part of deployment.** Each block removes one thing; run only the one you need.",
           "**只有在资源所有者同意后才删除资源；这不是部署步骤。** 每个代码块只删除一样东西，只运行需要的那一个。"),
        tr(chinese, "Delete the client VM and its resource group (`az` asks you to confirm):", "删除客户端 VM 及其资源组（`az` 会要求确认）："),
        """```bash
az group delete -n "$VM_RG"
```""",
        tr(chinese, "Delete the three model deployments:", "删除三个模型部署："),
        """```bash
for name in claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5; do
  az cognitiveservices account deployment delete -g "$FOUNDRY_RG" -n "$FOUNDRY" --deployment-name "$name"
done
```""",
        tr(chinese,
           "**Repository.** [`coding-matrix/`](coding-matrix/) client, probe, matrix, judge, cache test and analysis · [`data/`](data/) the measured problem list and the gateway workload · [`evidence/coding-matrix-20261026/`](evidence/coding-matrix-20261026/) run records, facts and provenance · [`evidence/`](evidence/) gateway records · [`scripts/`](scripts/) gateway collector, gateway analysis and the page generator · [`deploy/`](deploy/) gateway image · [`images/`](images/) figures and icon ledger · [`tests/`](tests/) offline tests (`python -B -m unittest discover -s tests -v`, run by CI) · [`NOTICE.md`](NOTICE.md) third-party notices.",
           "**仓库目录。** [`coding-matrix/`](coding-matrix/) 客户端、参数探测、编码矩阵、评分、缓存测试和分析 · [`data/`](data/) 实测题目清单和网关测试的对话 · [`evidence/coding-matrix-20261026/`](evidence/coding-matrix-20261026/) 运行记录、汇总和来源 · [`evidence/`](evidence/) 网关测试记录 · [`scripts/`](scripts/) 网关采集、网关分析和页面生成 · [`deploy/`](deploy/) 网关镜像 · [`images/`](images/) 图和图标台账 · [`tests/`](tests/) 离线测试（`python -B -m unittest discover -s tests -v`，CI 每次推送都会运行）· [`NOTICE.md`](NOTICE.md) 第三方声明。"),
    ]
    return "\n\n".join(blocks)


# ---------- figure ----------

def topology(d, chinese):
    """'How we measured' figure: one region, one client, one resource, and the method beside it."""
    m = matrix_numbers(d)
    k = cache_numbers(d)
    cfg = d["facts"]["state"]["config"]
    summary = d["probe_summary"]
    prov = d["provenance"]
    region = prov["client"]["region"]
    require(prov["models"]["resourceRegion"] == region, "the client and the models are not in one region")
    kinds = {(x["sku"], x["version"]) for x in prov["models"]["deployments"]}
    require(len(kinds) == 1, "deployments differ in SKU or version")
    sku, version = next(iter(kinds))
    n_problems = len(m["problems"])
    languages = sorted({p.split("/")[0] for p in m["problems"]})
    per_language = n_problems // len(languages)
    require(per_language * len(languages) == n_problems, "problems are not evenly split over languages")
    require(m["http"] == {200: m["requests"]}, "a matrix request did not return HTTP 200")
    require(list(m["regions"]) == [region], "x-ms-region differs from the resource region on a matrix response")
    require(list(m["spilled"]) == ["false"], "a matrix response was spilled over")
    cells = len(d["facts"]["cells"])
    python = ".".join(d["environment"][2].split()[1].split(".")[:2])
    turns = len(k["context"]["questions"])
    ledger = read_json(ROOT / "images/icon-sources.json")
    icons = {}
    for item in ledger["icons"]:
        path = ROOT / item["file"]
        require(hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], "Icon changed: " + item["file"])
        icons[path.name] = base64.b64encode(path.read_bytes()).decode()

    ink, body, head, accent, muted = "#111111", "#252525", "#0408AC", "#432FC8", "#666666"
    judge_ink, judge_line = "#A35F00", "#C88A1E"
    font = "'Segoe UI', Aptos, 'Segoe Sans Display', system-ui, -apple-system, 'Helvetica Neue', Arial, 'Microsoft YaHei', 'PingFang SC', 'Noto Sans CJK SC', sans-serif"
    out = []

    def text(x, y, content, size, fill=body, weight=400, anchor="start"):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
                   f'text-anchor="{anchor}">{html.escape(content, quote=False)}</text>')

    def runs(x, y, parts, size, fill=body):
        spans = "".join(f'<tspan font-weight="{700 if bold else 400}"{f" fill={chr(34)}{head}{chr(34)}" if bold else ""}>'
                        f'{html.escape(part, quote=False)}</tspan>' for part, bold in parts)
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}">{spans}</text>')

    def icon(name, x, y, size):
        out.append(f'<image x="{x}" y="{y}" width="{size}" height="{size}" href="data:image/svg+xml;base64,{icons[name]}"/>')

    def t(en, cn):
        return tr(chinese, en, cn)

    text(40, 62, t("How we measured: one region, one client, one resource", "测试方法：一个区域、一个客户端、一个资源"), 36, ink)
    out.append(f'<rect x="40" y="92" width="760" height="444" rx="24" fill="none" stroke="{accent}" stroke-width="2.5" stroke-dasharray="12 8"/>')
    text(62, 127, t(f"Azure region: {region}", f"Azure 区域：{region}"), 20, accent, 700)

    out.append('<rect x="62" y="146" width="270" height="256" rx="16" fill="#ECECEC"/>')
    icon("10021-icon-service-Virtual-Machine.svg", 181, 156, 32)
    vm_lines = [
        ("Linux VM", "Linux VM", 21, head, 700, 214),
        ("the only client", "唯一的客户端", 16, muted, 400, 239),
        (f"Python {python} + httpx", f"Python {python} + httpx", 17, body, 700, 270),
        ("Messages API, streaming", "Messages API，流式返回", 17, body, 400, 295),
        ("1 request in flight per model", "每个模型同时只有 1 个请求", 17, body, 400, 320),
        ("managed identity, no API key", "托管身份，不用 API 密钥", 17, body, 400, 345),
        ("stops if TCP connect ≥ 50 ms", "TCP 建连 ≥ 50 毫秒就停止", 14.5, muted, 400, 377),
    ]
    for en, cn, size, fill, weight, y in vm_lines:
        text(197, y, t(en, cn), size, fill, weight, "middle")

    out.append(f'<line x1="197" y1="404" x2="197" y2="424" stroke="{judge_line}" stroke-width="2" stroke-dasharray="5 4"/>')
    out.append(f'<polygon points="191,423 203,423 197,434" fill="{judge_line}"/>')
    text(208, 424, t("answers", "回答"), 14.5, judge_ink)
    out.append(f'<rect x="62" y="436" width="270" height="84" rx="10" fill="#FFF6E5" stroke="{judge_line}" stroke-width="1.6" stroke-dasharray="7 4"/>')
    text(197, 463, t("Docker judge · same VM", "Docker 评分 · 同一台 VM"), 17, judge_ink, 700, "middle")
    text(197, 486, t("runs each problem's unit tests", "运行每道题自带的单元测试"), 15, body, 400, "middle")
    text(197, 508, t("offline · pass = tests exit 0", "离线运行 · 以 0 退出即通过"), 15, body, 400, "middle")

    text(400, 232, "HTTPS", 16, accent, 700, "middle")
    text(400, 254, t("TCP connect", "TCP 建连"), 15, muted, 400, "middle")
    text(400, 274, t(f"median {m['tcp_ms']:.1f} ms", f"中位数 {m['tcp_ms']:.1f} 毫秒"), 15, muted, 400, "middle")
    out.append(f'<line x1="346" y1="292" x2="454" y2="292" stroke="{accent}" stroke-width="2.5"/>')
    out.append(f'<polygon points="336,292 348,286 348,298" fill="{accent}"/>')
    out.append(f'<polygon points="464,292 452,286 452,298" fill="{accent}"/>')

    out.append('<rect x="468" y="146" width="312" height="374" rx="18" fill="#EFECFA" stroke="#C4BFF3" stroke-width="1.5"/>')
    icon("036509415-icon-service-Foundry-Project.svg", 484, 160, 28)
    text(520, 182, t("One Foundry resource", "一个 Foundry 资源"), 20, head, 700)
    text(484, 208, t(f"{sku} deployments, version {version}", f"{sku} 部署，版本 {version}"), 14.5, muted)
    y = 222
    for model in MODELS:
        deployment = DEPLOYMENT[model]
        accepted = summary[deployment]["accepted"]
        modes = [f"{mode}{t(': ', '：')}{accepted[mode][0]} → {accepted[mode][-1]}"
                 for mode in ("adaptive", "between_tools", "disabled") if accepted[mode]]
        height = 36 + 22 * len(modes)
        out.append(f'<rect x="484" y="{y}" width="280" height="{height}" rx="8" fill="#FFFFFF" stroke="#DAD5F4"/>')
        text(498, y + 24, NAME[model], 17, head, 700)
        text(750, y + 24, f"{cfg['tpm'][deployment] // 1000}K TPM", 14, muted, 400, "end")
        for index, line in enumerate(modes):
            text(498, y + 46 + 21 * index, line, 15, accent)
        y += height + 10
    runs(484, 500, [("Messages API ", True), ("/anthropic/v1/messages", False)], 14.5)

    text(836, 127, t("Method", "方法"), 32, head, 700)
    probe_n, cache_n, measured = d["runs"]["probe"]["requests"], k["requests"], m["measured"]
    steps = [
        (t(f"{n_problems} problems, {len(languages)} languages", f"{n_problems} 道题，{len(languages)} 种语言"),
         t(f"Aider polyglot, {per_language} per language;", f"Aider polyglot，每种语言 {per_language} 道；"),
         t("public exercises, not customer data", "公开练习，不是客户数据")),
        (t("Probe accepted settings first", "先探测接受的取值"),
         t(f"{probe_n} requests: every thinking × effort", f"{probe_n} 个探测请求，返回 200 的"),
         t("pair that returns 200 becomes a cell", "思考模式 × 档位组合才成为一格")),
        (t(f"{m['repeats']} runs per problem and cell", f"每格每题 {m['repeats']} 次"),
         t(f"{n_problems * m['repeats']} answers per cell, plus 1 warm-up;", f"每格 {n_problems * m['repeats']} 个回答，另加 1 次预热；"),
         t(f"{cells} cells, {measured:,} measured, all HTTP 200", f"{cells} 格共 {measured:,} 次计分，全部 HTTP 200")),
        (t(f"Prompt cache: {turns}-turn chat", f"提示缓存：{turns} 轮编码对话"),
         t(f"{cache_n} requests: breakpoints, TTL,", f"{cache_n} 个请求：断点、TTL、"),
         t("effort and thinking-mode switches", "切换推理档位和思考模式")),
        (t("Pass and cost", "通过与费用"),
         t("pass = unit tests exit 0, offline;", "通过 = 单元测试以 0 退出，离线运行；"),
         t("cost = recorded tokens × list price", "费用 = 记录的 token × 标价")),
    ]
    out.append(f'<defs><linearGradient id="badge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#C4BFF3"/>'
               f'<stop offset="1" stop-color="{accent}"/></linearGradient></defs>')
    for index, (title, first, second) in enumerate(steps):
        ty = 178 + 72 * index
        out.append(f'<circle cx="853" cy="{ty - 6}" r="17" fill="url(#badge)"/>')
        text(853, ty, str(index + 1), 16, "#FFFFFF", 700, "middle")
        text(882, ty, title, 17, head, 700)
        text(882, ty + 23, first, 15.5, body)
        text(882, ty + 44, second, 15.5, body)

    spans = [
        [(t(f"{sku}: ", f"{sku}："), True),
         (t("Azure may serve a request on GPUs in another region, so ‘one region’ means the same entry point and network path",
            "Azure 可能在其他区域的 GPU 上处理请求，所以“一个区域”指每个模型的入口和网络路径相同，"), False)],
        [(t(f"for every model, not the same GPU. All {m['requests']:,} matrix responses carried x-ms-region {region} and were not spilled over.",
            f"不是同一块 GPU。矩阵的 {m['requests']:,} 个响应，x-ms-region 都是 {region}，x-ms-is-spilled-over 都是 false。"), False)],
        [(t("Not drawn: ", "图中未画："), True),
         (t("the 2026-10-24 gateway test (Windows client → LiteLLM on Azure Container Apps in Japan East → this resource).",
            "2026-10-24 的网关测试（Windows 客户端 → Japan East 的 Azure Container Apps 上的 LiteLLM → 本资源）。"), False)],
    ]
    for index, parts in enumerate(spans):
        runs(40, 570 + 25 * index, parts, 16)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="650" viewBox="0 0 1200 650">\n'
            '<rect width="1200" height="650" fill="#FFFFFF"/>\n'
            f'<g font-family="{font}">\n' + "\n".join(out) + "\n</g></svg>")


# ---------- results page ----------

def results_page(d, chinese):
    m = matrix_numbers(d)
    problems = d["problems"]
    shortest = min(problems["problems"], key=lambda p: p["user_message_chars"])
    warmup = re.search(r'^WARMUP_PROMPT = "(.*)"$', (ROOT / "coding-matrix/bench.py").read_text(encoding="utf-8"), re.M).group(1)
    by_language = {}
    for pid in m["problems"]:
        by_language.setdefault(pid.split("/")[0], []).append(pid)
    problem_list = "\n".join(f"- {lang}: " + ", ".join(problem_link(p) for p in ids) for lang, ids in by_language.items())
    out = []
    out.append(tr(chinese, "## Coding matrix, 2026-10-26", "## 编码矩阵"))
    out.append(tr(chinese,
                  "**Question.** For each thinking mode and effort level a Claude 5.5 deployment accepts, how often does a coding answer complete, how long until its first visible text, what does it cost and how often does it pass the problem's unit tests?",
                  "**问题。** 对每个 Claude 5.5 部署接受的每种思考模式和推理档位，编码回答完成的比例、首个可见文字的等待时间、费用，以及通过题目单元测试的比例各是多少？（2026-10-26）"))
    out.append(tr(chinese,
                  f"**Input.** Every request carried the same system prompt, adapted from Aider's whole-file edit format, and one user message per problem built as in Aider's benchmark: the exercise's stub files, its instructions and Aider's closing instruction. The model does not see the tests. The system prompt, verbatim ({len(problems['system_prompt'])} characters):",
                  f"**输入。** 每个请求都带同一个系统提示（改编自 Aider 的整文件编辑格式），以及按 Aider 评测方式为每道题生成的一条用户消息：待补全的文件、题目说明和 Aider 的收尾要求。模型看不到测试。系统提示原文（{len(problems['system_prompt'])} 个字符）："))
    out.append("````text\n" + problems["system_prompt"].rstrip("\n") + "\n````")
    out.append(tr(chinese,
                  f"The shortest of the 18 user messages, `{shortest['id']}`, verbatim ({count(shortest['user_message_chars'])} characters):",
                  f"18 条用户消息中最短的一条，`{shortest['id']}`，原文（{count(shortest['user_message_chars'])} 个字符）："))
    out.append("````text\n" + shortest["user_message"].rstrip("\n") + "\n````")
    out.append(tr(chinese,
                  "All 18 messages and their SHA-256 are in [problems.json](../evidence/coding-matrix-20261026/matrix/problems.json). The 18 problems, three per language:",
                  "18 条消息原文及其 SHA-256 在 [problems.json](../evidence/coding-matrix-20261026/matrix/problems.json)。18 道题，每种语言 3 道："))
    out.append(problem_list)
    out.append(tr(chinese,
                  f"**Varied and fixed.** Varied: the model, `thinking.type` and `output_config.effort`, over the 21 combinations the probe accepted. Fixed: `max_tokens` 128,000, `stream` true, no `cache_control`, no tool, no sampling parameter; 18 problems × {m['repeats']} repeats per cell; one discarded warm-up per cell (`{warmup}`); one request in flight per deployment, the three deployments in parallel; a seeded order that interleaves problems and cells, so a slow hour affects every cell alike. The client paced under 85% of each deployment's per-minute token and output-token limits; a 429 would have been resent after `Retry-After`, and none occurred. A 32,000-token pilot cut answers off at effort max, so the matrix ran with 128,000, the value Claude's effort page gives for agentic coding on Sonnet 5.5.",
                  f"**变量与固定项。** 变量：模型、`thinking.type` 和 `output_config.effort`，即探测接受的 21 种组合。固定项：`max_tokens` 128,000，`stream` 为 true，没有 `cache_control`、工具和采样参数；每格 18 道题 × {m['repeats']} 次；每格一个预热请求，不计分（`{warmup}`）；每个部署同一时间一个请求，三个部署并行；按固定种子交错安排题目和格子的顺序，让某个慢时段对每格的影响相同。客户端把每分钟 token 和输出 token 控制在部署上限的 85% 以内；若出现 429 会按 `Retry-After` 重发，实际一次也没有出现。32,000 token 的试跑在 effort 为 max 时会截断回答，所以矩阵用 128,000，这也是 Claude effort 文档为 Sonnet 5.5 智能体编码给出的值。"))
    out.append(tr(chinese, "### Results per cell", "### 每格结果"))
    out.append(tr(chinese,
                  "Times are seconds. First visible text uses every request that returned text; full answer uses completed requests. Nearest-rank percentiles.",
                  "时间单位为秒。首个可见文字统计所有返回了文字的请求；完整回答只统计完成的请求。分位数用最近秩法。"))
    head_a = tr(chinese, "| Cell | Completed | First text P50 | First text P95 | Full answer P50 | Full answer P95 |",
                "| 格 | 完成 | 首字 P50 | 首字 P95 | 完整回答 P50 | 完整回答 P95 |")
    lines = [head_a, "|---|---:|---:|---:|---:|---:|"]
    for c in d["facts"]["cells"]:
        lines.append(f"| {cell_label(c)} | {c['completed']}/{c['attempted']} | {secs(c['first_text_p50_s'])} | {secs(c['first_text_p95_s'])} | {secs(c['e2e_p50_s'])} | {secs(c['e2e_p95_s'])} |")
    out.append("\n".join(lines))
    head_b = tr(chinese, "| Cell | Thinking tokens P50 | Output tokens P50 | $ per 1,000 requests | Passed | By-problem 95% interval |",
                "| 格 | 思考 token P50 | 输出 token P50 | 每 1,000 次费用（美元） | 通过 | 按题目的 95% 区间 |")
    lines = [head_b, "|---|---:|---:|---:|---:|---:|"]
    for c in d["facts"]["cells"]:
        lo, hi = d["facts"]["intervals"]["cells"][c["cell_id"]]["ci95"]
        lines.append(f"| {cell_label(c)} | {count(c['thinking_tokens_p50'])} | {count(c['output_tokens_p50'])} | {usd(c['cost_per_1k_requests_usd'])} | {c['passed']}/{c['attempted']} | {interval(lo, hi)} |")
    out.append("\n".join(lines))
    out.append(tr(chinese, "### Requests that did not complete", "### 未完成的请求"))
    items = []
    for r in m["failures"]:
        timing = r.get("timing") or {}
        label = f"`{r['task_id']}`"
        if r["status"] == "max_tokens":
            items.append(tr(chinese,
                            f"- {label}: `stop_reason` `max_tokens` after {secs(timing.get('end'))} s; {count((r.get('usage') or {}).get('output_tokens'))} output tokens, " + ("no visible text." if timing.get("first_text") is None else f"visible text from {secs(timing.get('first_text'))} s."),
                            f"- {label}：{secs(timing.get('end'))} 秒后 `stop_reason` 为 `max_tokens`；输出 {count((r.get('usage') or {}).get('output_tokens'))} 个 token，" + ("没有可见文字。" if timing.get("first_text") is None else f"第 {secs(timing.get('first_text'))} 秒才出现可见文字。")))
        else:
            items.append(tr(chinese,
                            f"- {label}: `message_start` at {secs(timing.get('message_start'))} s, then two pings and no further event; the client's 600 s read timeout ended it at {secs(timing.get('end'))} s. Scored as no code.",
                            f"- {label}：第 {secs(timing.get('message_start'))} 秒收到 `message_start`，随后只有两个 ping，再无事件；客户端 600 秒读超时在第 {secs(timing.get('end'))} 秒结束请求。按没有代码计分。"))
    out.append("\n".join(items))
    out.append(tr(chinese, "### By problem", "### 按题目"))
    out.append(tr(chinese,
                  "Answers that passed over all cells of a model: Opus has 5 cells × 3 = 15 answers per problem, Sonnet and Haiku 8 × 3 = 24.",
                  "每个模型所有格合计的通过数：Opus 每道题 5 格 × 3 次 = 15 个回答，Sonnet 和 Haiku 8 × 3 = 24 个。"))
    lines = ["| " + tr(chinese, "Problem", "题目") + " | Opus | Sonnet | Haiku |", "|---|---:|---:|---:|"]
    for pid in m["problems"]:
        lines.append(f"| `{pid}` | " + " | ".join(f"{m['per_problem'][(model, pid)][0]}/{m['per_problem'][(model, pid)][1]}" for model in MODELS) + " |")
    out.append("\n".join(lines))
    out.append(tr(chinese, "### By language", "### 按语言"))
    lines = ["| " + tr(chinese, "Language", "语言") + " | Opus | Sonnet | Haiku |", "|---|---:|---:|---:|"]
    for language in by_language:
        lines.append(f"| {language} | " + " | ".join(f"{m['per_language'][(model, language)][0]}/{m['per_language'][(model, language)][1]}" for model in MODELS) + " |")
    out.append("\n".join(lines))
    out.append(tr(chinese, "### Thinking on and off at the same effort", "### 相同档位下开启与关闭思考"))
    out.append(tr(chinese,
                  "Both sides use effort low, medium and high, the levels where thinking can be off, on the same problems: 162 answers each. Intervals resample the problems.",
                  "两边都用 low、medium、high 三个可以关闭思考的档位，题目相同，各 162 个回答。区间按题目重抽。"))
    lines = [tr(chinese, "| Model | `adaptive` | Thinking off | Difference, points | 95% interval | Problems better / worse / equal |",
                "| 模型 | `adaptive` | 关闭思考 | 差（百分点） | 95% 区间 | 更好 / 更差 / 持平的题数 |"),
             "|---|---:|---:|---:|---:|---:|"]
    for model in ("sonnet", "haiku"):
        t = thinking(d, model)
        lines.append(f"| {NAME[model]} (`{OFF_MODE[model]}`) | {pct(t['on_share'])}% | {pct(t['off_share'])}% | {pct(t['difference'], sign=True)} | {pct(t['difference_ci95'][0], sign=True)} to {pct(t['difference_ci95'][1], sign=True)} | {t['problems_better_on']} / {t['problems_better_off']} / {t['problems_equal']} |"
                     if not chinese else
                     f"| {NAME[model]}（`{OFF_MODE[model]}`） | {pct(t['on_share'])}% | {pct(t['off_share'])}% | {pct(t['difference'], sign=True)} | {pct(t['difference_ci95'][0], sign=True)} 到 {pct(t['difference_ci95'][1], sign=True)} | {t['problems_better_on']} / {t['problems_better_off']} / {t['problems_equal']} |")
    out.append("\n".join(lines))
    out.append(probe_section(d, chinese))
    out.append(cache_section(d, chinese))
    return "\n\n".join(out)


PROBE_ROWS = [
    ("effort `\"probe-invalid-value\"`", "effort 设为 `\"probe-invalid-value\"`", {"*": ["effort_invalid"]}),
    ("`adaptive`, effort low to max", "`adaptive`，effort low 到 max", {"*": [f"adaptive_{e}" for e in EFFORTS]}),
    ("`adaptive`, no effort", "`adaptive`，不传 effort", {"*": ["adaptive_default_effort"]}),
    ("`disabled`, effort low, medium, high", "`disabled`，effort low、medium、high", {"*": ["disabled_low", "disabled_medium", "disabled_high"]}),
    ("`disabled`, effort xhigh, max", "`disabled`，effort xhigh、max", {"*": ["disabled_xhigh", "disabled_max"]}),
    ("`disabled`, no effort", "`disabled`，不传 effort", {"*": ["disabled_default_effort"]}),
    ("`between_tools`, effort low, medium, high", "`between_tools`，effort low、medium、high", {"*": ["between_tools_low", "between_tools_medium", "between_tools_high"]}),
    ("`between_tools`, effort xhigh, max", "`between_tools`，effort xhigh、max", {"*": ["between_tools_xhigh", "between_tools_max"]}),
    ("`between_tools`, no effort", "`between_tools`，不传 effort", {"*": ["between_tools_default_effort"]}),
    ("no `thinking` field", "不传 `thinking`", {"*": ["thinking_omitted"]}),
    ("`enabled` with `budget_tokens` 1,024", "`enabled` 加 `budget_tokens` 1,024", {"*": ["thinking_enabled_budget"]}),
    ("`adaptive` + `temperature` 0.5", "`adaptive` + `temperature` 0.5", {"*": ["adaptive_temperature_0.5"]}),
    ("`adaptive` + `top_p` 0.9", "`adaptive` + `top_p` 0.9", {"*": ["adaptive_top_p_0.9"]}),
    ("`adaptive` + `top_k` 40", "`adaptive` + `top_k` 40", {"*": ["adaptive_top_k_40"]}),
    ("thinking off + `temperature` 0.5", "关闭思考 + `temperature` 0.5", {"sonnet": ["between_tools_temperature_0.5"], "haiku": ["disabled_temperature_0.5"]}),
    ("thinking off + `top_p` 0.9", "关闭思考 + `top_p` 0.9", {"sonnet": ["between_tools_top_p_0.9"], "haiku": ["disabled_top_p_0.9"]}),
    ("thinking off + `top_k` 40", "关闭思考 + `top_k` 40", {"sonnet": ["between_tools_top_k_40"], "haiku": ["disabled_top_k_40"]}),
    ("`max_tokens` 1,000,000", "`max_tokens` 1,000,000", {"*": ["max_tokens_1000000"]}),
    ("`max_tokens` 32,000", "`max_tokens` 32,000", {"*": ["max_tokens_32000"]}),
    ("system block with `cache_control` and `\"ttl\": \"1h\"`", "system 块带 `cache_control` 和 `\"ttl\": \"1h\"`", {"*": ["cache_ttl_1h_system"]}),
    ("top-level `cache_control`", "顶层 `cache_control`", {"*": ["cache_top_level_auto"]}),
    ("four `max_tokens` 32,000 requests back to back", "连续四个 `max_tokens` 32,000 的请求", {"*": [f"tpm_burst_{i}" for i in range(1, 5)]}),
]


def probe_section(d, chinese):
    outcomes = probe_outcomes(d)
    letters = {}
    used = set()
    lines = ["| " + tr(chinese, "Request", "请求") + " | Opus | Sonnet | Haiku |", "|---|---|---|---|"]
    for en, cn, names in PROBE_ROWS:
        values = []
        for model in MODELS:
            probes = names.get(model, names.get("*"))
            if not probes:
                values.append(tr(chinese, "not sent: no thinking-off mode", "未发送：没有关闭思考的模式"))
                continue
            results = []
            for name in probes:
                status, message, _ = outcomes[(name, model)]
                used.add((name, model))
                if message is not None and message not in letters:
                    letters[message] = "abcdefghijklmnopqrstuvwxyz"[len(letters)]
                results.append((status, letters.get(message)))
            statuses = sorted({s for s, _ in results})
            marks = sorted({x for _, x in results if x})
            values.append(" / ".join(str(s) for s in statuses) + (f" ({', '.join(marks)})" if marks else ""))
        lines.append(f"| {tr(chinese, en, cn)} | " + " | ".join(values) + " |")
    require(used == set(outcomes), "a probe request is missing from the table")
    messages = "\n".join(f"- ({letter}) {code(message)}" for message, letter in letters.items())
    thought = [(name, model, tok) for (name, model), (status, _, tok) in outcomes.items() if status == 200 and tok]
    thought_text = ", ".join(f"{NAME[model].split()[0]} `{name}` {tok}" for name, model, tok in sorted(thought, key=lambda x: (MODELS.index(x[1]), x[0])))
    return "\n\n".join([
        tr(chinese, "## Parameter probe, 2026-10-26", "## 参数探测"),
        tr(chinese,
           f"**Question.** Which thinking modes, effort levels, sampling parameters, output limits and cache settings does each deployment accept? **Input.** One streamed request per value and model, `max_tokens` 1,024 unless the row changes it, with the user message `Reply with exactly one word: OK`; {count(d['runs']['probe']['requests'])} requests on 2026-10-26 between {utc_time(d['runs']['probe']['first'])} and {utc_time(d['runs']['probe']['last'])} UTC. A cell lists the HTTP status; letters point to the messages below. The accepted thinking modes and efforts became the cells of the matrix.",
           f"**问题。** 每个部署接受哪些思考模式、推理档位、采样参数、输出上限和缓存设置？**输入。** 每个取值和模型发一个流式请求，除非该行另有说明，`max_tokens` 为 1,024，用户消息为 `Reply with exactly one word: OK`；2026-10-26 UTC {utc_time(d['runs']['probe']['first'])} 到 {utc_time(d['runs']['probe']['last'])} 共 {count(d['runs']['probe']['requests'])} 个请求。单元格是 HTTP 状态，字母对应下方的报错原文。被接受的思考模式和推理档位就是编码矩阵的各格。"),
        "\n".join(lines),
        tr(chinese, "HTTP 400 messages, verbatim:", "HTTP 400 报错原文："),
        messages,
        tr(chinese,
           f"**Thinking text.** Thinking tokens in this probe: {thought_text}; every other accepted request answered without thinking. In the matrix, {count(matrix_numbers(d)['thought'])} requests used thinking tokens and none streamed thinking text: the thinking blocks arrived with a signature and no text, the documented `omitted` display.",
           f"**思考内容。** 本次探测中用了思考 token 的请求：{thought_text}；其余被接受的请求都没有思考。编码矩阵中 {count(matrix_numbers(d)['thought'])} 个请求用了思考 token，没有一个流式返回思考文字：thinking 块只带签名、没有文字，即文档所说的 `omitted` 显示方式。"),
    ])


SCENARIOS = [
    ("none", "no `cache_control`", "不带 `cache_control`"),
    ("auto", "top-level `cache_control` (automatic caching) on every turn", "每轮带顶层 `cache_control`（自动缓存）"),
    ("auto_second", "a new conversation with the same instructions and files after `auto`, one question", "`auto` 之后开一段说明和文件相同的新对话，问一个问题"),
    ("system_only", "one breakpoint at the end of the repository block", "只在仓库文件块末尾放一个断点"),
    ("system_only_second", "a new conversation after `system_only`, one question", "`system_only` 之后的新对话，问一个问题"),
    ("system_plus_auto", "repository breakpoint and top-level automatic caching", "仓库断点加顶层自动缓存"),
    ("system_plus_auto_second", "a new conversation after `system_plus_auto`, one question", "`system_plus_auto` 之后的新对话，问一个问题"),
    ("effort_switch", "`adaptive`, automatic caching, top-level effort low, low, high, low", "`adaptive`，自动缓存，顶层 effort 依次为 low、low、high、low"),
    ("effort_switch_message", "the same switch as per-message effort with the beta header", "同样的切换改用按消息设置 effort，带 beta 头"),
    ("mode_switch", "automatic caching; thinking off, off, `adaptive`, `adaptive` (Sonnet, Haiku)", "自动缓存；思考依次为关、关、`adaptive`、`adaptive`（Sonnet、Haiku）"),
    ("prewarm", "a non-streaming `max_tokens: 0` request with the repository breakpoint, then the first question", "先发带仓库断点的非流式 `max_tokens: 0` 请求，再问第一个问题"),
    ("idle_5m", "automatic caching, default 5-minute TTL, 6.5 minutes idle before turn 2", "自动缓存，默认 5 分钟 TTL，第 2 轮前空闲 6.5 分钟"),
    ("idle_1h", "automatic caching with `\"ttl\": \"1h\"`, 6.5 minutes idle before turn 2", "自动缓存，`\"ttl\": \"1h\"`，第 2 轮前空闲 6.5 分钟"),
    ("ttft_cold_repo", "cold request, repository context, one-word answer, five pairs", "冷请求，仓库上下文，只答一个词，五对"),
    ("ttft_warm_repo", "the same prompt again", "再发一次相同提示"),
    ("ttft_cold_large", "cold request, larger context (Sonnet, Haiku)", "冷请求，更大的上下文（Sonnet、Haiku）"),
    ("ttft_warm_large", "the same prompt again", "再发一次相同提示"),
]


def cache_section(d, chinese):
    k = cache_numbers(d)
    ctx = k["context"]
    turns, sessions = k["turns"], k["sessions"]
    questions = "\n".join(f"{i}. {q}" for i, q in enumerate(ctx["questions"], 1))
    out = [tr(chinese, "## Prompt caching, 2026-10-26", "## 提示缓存")]
    out.append(tr(chinese,
                  "**Question.** In a multi-turn coding conversation, how much of each prompt is read from cache, what does it save, and what breaks the cache?",
                  "**问题。** 在多轮编码对话中，每次提示有多少从缓存读取、能省多少钱、哪些操作会让缓存失效？（2026-10-26）"))
    out.append(tr(chinese,
                  f"**Input.** The system prompt has two blocks: `Conversation <nonce>. ` followed by the instructions below, then `Repository files:` followed by three httpx 0.28.1 source files ({', '.join('`' + f + '`' for f in ctx['repo_files'])}; {count(ctx['context_chars']['repo'])} characters). The nonce makes every conversation start cold; a *second conversation* reuses the nonce of the one before it. A larger context of five files ({count(ctx['context_chars']['large'])} characters) was used only for cold and warm pairs. The instructions, verbatim:",
                  f"**输入。** 系统提示分两块：先是 `Conversation <nonce>. ` 加下面的说明，然后是 `Repository files:` 加三个 httpx 0.28.1 源文件（{'、'.join('`' + f + '`' for f in ctx['repo_files'])}；{count(ctx['context_chars']['repo'])} 个字符）。nonce 让每段对话都从冷缓存开始；*新对话* 复用前一段对话的 nonce。五个文件的更大上下文（{count(ctx['context_chars']['large'])} 个字符）只用于冷热对照。说明原文："))
    out.append("````text\n" + ctx["instructions"] + "\n````")
    out.append(tr(chinese, "The four questions, verbatim, in order:", "四个问题原文，按顺序："))
    out.append(questions)
    out.append(tr(chinese,
                  f"The new-conversation question: `{ctx['second_question']}` The cold and warm question: `{ctx['pair_question']}`",
                  f"新对话的问题：`{ctx['second_question']}` 冷热对照的问题：`{ctx['pair_question']}`"))
    out.append(tr(chinese,
                  f"**Fixed.** Effort low; Opus `adaptive`, Sonnet `between_tools`, Haiku `disabled` unless the scenario changes it; `max_tokens` {count(ctx['max_tokens'])} ({ctx['pair_max_tokens']} for the pairs); {ctx['repetitions']} repetitions per scenario and {ctx['pairs']} pairs per context; the client paced under 85% of each deployment's limits; each model's cache test started after its matrix requests had finished. {count(k['requests'])} requests, all HTTP 200, {k['throttled']} throttled.",
                  f"**固定项。** effort 为 low；除非场景另有改动，Opus 用 `adaptive`，Sonnet 用 `between_tools`，Haiku 用 `disabled`；`max_tokens` {count(ctx['max_tokens'])}（冷热对照为 {ctx['pair_max_tokens']}）；每个场景重复 {ctx['repetitions']} 次，每种上下文 {ctx['pairs']} 对；客户端把速率控制在部署上限的 85% 以内；每个模型的缓存测试在它的矩阵请求全部结束后才开始。共 {count(k['requests'])} 个请求，全部 HTTP 200，限流 {k['throttled']} 次。"))
    lines = ["| " + tr(chinese, "Scenario | What it changes", "场景 | 改了什么") + " |", "|---|---|"]
    lines += [f"| `{name}` | {tr(chinese, en, cn)} |" for name, en, cn in SCENARIOS]
    out.append("\n".join(lines))
    out.append(tr(chinese, "### Share of each prompt read from cache", "### 每轮提示从缓存读取的比例"))
    out.append(tr(chinese,
                  "Read tokens / (uncached + written + read input tokens), mean of the repetitions. `—`: the model did not run that scenario.",
                  "读取 token ÷（未缓存 + 写入 + 读取的输入 token），取各次重复的平均。`—`：该模型没有这个场景。"))
    lines = ["| " + tr(chinese, "Scenario | Turn", "场景 | 轮次") + " | Opus | Sonnet | Haiku |", "|---|---:|---:|---:|---:|"]
    for name, _, _ in SCENARIOS:
        turn_numbers = sorted({t for (model, scenario, t) in turns if scenario == name})
        for turn in turn_numbers:
            values = []
            for model in MODELS:
                item = turns.get((DEPLOYMENT[model], name, turn))
                values.append("—" if item is None else f"{pct(item['read_share'] or 0, 1)}%")
            lines.append(f"| `{name}` | {turn} | " + " | ".join(values) + " |")
    out.append("\n".join(lines))
    out.append(tr(chinese, "### Cost of each conversation against no cache", "### 每段对话相对不缓存的费用变化"))
    out.append(tr(chinese,
                  "Mean list-price cost of the scenario's requests, compared with the same token counts priced as if nothing were cached. Negative is cheaper.",
                  "场景内各请求的平均标价费用，与同样 token 数按不缓存计价相比。负数表示更便宜。"))
    lines = ["| " + tr(chinese, "Scenario", "场景") + " | Opus | Sonnet | Haiku |", "|---|---:|---:|---:|"]
    for name, _, _ in SCENARIOS:
        values = []
        for model in MODELS:
            item = sessions.get((DEPLOYMENT[model], name))
            values.append("—" if item is None else f"{pct(-item['saving_vs_no_cache'], 0, sign=True)}%")
        lines.append(f"| `{name}` | " + " | ".join(values) + " |")
    out.append("\n".join(lines))
    out.append(tr(chinese, "### Cold and warm requests", "### 冷请求与热请求"))
    lines = [tr(chinese, "| Model | Context | Prompt tokens | First text P50 cold → warm, s | Cost cold → warm, US$ |",
                "| 模型 | 上下文 | 提示 token | 首字 P50 冷 → 热（秒） | 费用 冷 → 热（美元） |"),
             "|---|---|---:|---:|---:|"]
    for (model, size), p in sorted(k["pairs"].items(), key=lambda kv: (MODELS.index(kv[0][0].split("-")[1]), kv[0][1] != "repo")):
        lines.append(f"| {NAME[model.split('-')[1]]} | {tr(chinese, 'three files' if size == 'repo' else 'five files', '三个文件' if size == 'repo' else '五个文件')} | {count(round(p['prompt_tokens']))} | {secs(p['cold_first_text_p50_s'])} → {secs(p['warm_first_text_p50_s'])} | {p['cold_cost_mean_usd']:.4f} → {p['warm_cost_mean_usd']:.4f} |")
    out.append("\n".join(lines))
    out.append(tr(chinese,
                  f"Five pairs per row; differences of a tenth of a second are within the spread of single requests. Per-turn token counts are in [cache_facts.json](../evidence/coding-matrix-20261026/cache/cache_facts.json); every request is in [cache_results.jsonl](../evidence/coding-matrix-20261026/cache/cache_results.jsonl).",
                  f"每行五对；相差零点一秒左右在单个请求的波动范围内。每轮的 token 数在 [cache_facts.json](../evidence/coding-matrix-20261026/cache/cache_facts.json)，每个请求在 [cache_results.jsonl](../evidence/coding-matrix-20261026/cache/cache_results.jsonl)。"))
    return "\n\n".join(out)


# ---------- testing page ----------

def testing_offline(chinese):
    return "\n\n".join([
        tr(chinese, "## Offline checks", "## 离线检查"),
        tr(chinese,
           "No Azure access or model key. Python 3.12 or 3.13 from this directory; the stream-parser tests also need the client packages.",
           "不需要 Azure 权限或模型密钥。在本目录用 Python 3.12 或 3.13 运行；流解析测试还需要客户端依赖包。"),
        """```bash
python -m pip install -r coding-matrix/requirements.txt
python -B coding-matrix/analyze.py --run-dir evidence/coding-matrix-20261026/matrix --check
python -B coding-matrix/cache_analyze.py --run-dir evidence/coding-matrix-20261026/cache --check
python -B scripts/analyze.py --check
python -B scripts/render_docs.py --check
python -B -m unittest discover -s tests -v
```""",
        tr(chinese,
           "Done when every command exits 0, each check prints `\"status\": \"PASS\"` and the tests end with `OK`.",
           "每条命令都以 0 退出、每个检查都输出 `\"status\": \"PASS\"`、测试最后输出 `OK`，即为通过。"),
        "\n".join(tr(chinese, [
            "- **`coding-matrix/analyze.py --check`** recomputes every cell, the per-problem and per-language counts and the bootstrap intervals from the 2026-10-26 run records and fails if `facts.json` differs.",
            "- **`coding-matrix/cache_analyze.py --check`** does the same for the cache test and `cache_facts.json`.",
            "- **`scripts/analyze.py --check`** verifies the 2026-10-24 gateway records: hashes, the outbound log of every request, history, token accounting and timing order.",
            "- **`scripts/render_docs.py --check`** fails if a README, results or testing page or a figure differs from a fresh render of the evidence.",
            "- **The tests** also check the export manifest hashes, the problem list against the measured prompts, the scorer's file extraction, the stream parser against a local test server (complete, truncated, HTTP 429 and `max_tokens` streams), that a tampered run record makes the check fail, that no private name or address is published, and the gateway collector with PowerShell 7 when it is installed. The local server tests the parser only; it is not evidence about Foundry.",
        ], [
            "- **`coding-matrix/analyze.py --check`** 用 2026-10-26 的运行记录重新计算每格、按题目和按语言的计数以及自助区间，与 `facts.json` 不一致即失败。",
            "- **`coding-matrix/cache_analyze.py --check`** 对缓存测试和 `cache_facts.json` 做同样的检查。",
            "- **`scripts/analyze.py --check`** 核验 2026-10-24 的网关记录：哈希、每个请求的出站日志、对话历史、token 计数和时间顺序。",
            "- **`scripts/render_docs.py --check`** 如果 README、结果页、复测页或图与按证据重新生成的结果不同就失败。",
            "- **测试** 还会检查导出清单的哈希、题目清单与实测提示是否一致、评分器的文件提取、流解析器在本地测试服务器下的行为（完整、截断、HTTP 429 和 `max_tokens` 的流）、篡改运行记录后检查会失败、没有公开私有名称或地址，以及装有 PowerShell 7 时的网关采集器。本地服务器只测试解析逻辑，不是关于 Foundry 的证据。",
        ])),
        tr(chinese,
           "CI runs the same on Ubuntu and Windows with Python 3.12 and 3.13 ([workflow](https://github.com/david-xinyuwei/david-share/blob/master/.github/workflows/claude-foundry-performance-ci.yml)).",
           "CI 在 Ubuntu 和 Windows 上用 Python 3.12 和 3.13 运行同样的检查（[workflow](https://github.com/david-xinyuwei/david-share/blob/master/.github/workflows/claude-foundry-performance-ci.yml)）。"),
    ])


def testing_repeat(d, chinese):
    runs = d["runs"]
    return "\n\n".join([
        tr(chinese, "## Repeat the 2026-10-26 tests", "## 重做 2026-10-26 的测试"),
        tr(chinese,
           f"**Before you start.** Finish README steps 1 to 4. These runs cost money: at list prices our matrix cost {usd(runs['matrix']['cost'])}, the cache test {usd(runs['cache']['cost'])} and the probe {usd(runs['probe']['cost'])}. `--budget-usd` stops the matrix at a limit (default 150). The client paces itself to Opus 40,000 and Sonnet and Haiku 80,000 tokens per minute (`TPM` in `bench.py` and `cache_test.py`); change those values if your capacities differ. Run everything on the VM, in `coding-matrix/`.",
           f"**开始之前。** 先完成 README 的第 1 到 4 步。这些运行要花钱：按标价，我们的矩阵花了 {usd(runs['matrix']['cost'])}，缓存测试 {usd(runs['cache']['cost'])}，参数探测 {usd(runs['probe']['cost'])}。`--budget-usd` 在达到上限时停止矩阵（默认 150）。客户端按 Opus 每分钟 40,000、Sonnet 和 Haiku 各 80,000 token 控制速率（`bench.py` 和 `cache_test.py` 里的 `TPM`）；容量不同就改这两处。以下命令都在 VM 的 `coding-matrix/` 目录运行。"),
        tr(chinese,
           "**1. Prepare the VM and build the judge image.** `vm_setup.sh` installs Docker and the client packages and clones the problems; the Java warm-up exercise lets Gradle run offline inside the image.",
           "**1. 准备 VM，构建评分镜像。** `vm_setup.sh` 安装 Docker 和客户端依赖，并克隆题库；Java 预热练习让 Gradle 能在镜像里离线运行。"),
        """```bash
cd ~/david-share/Agents/Claude-Foundry-LiteLLM-Performance/coding-matrix
bash vm_setup.sh
git -C ~/polyglot-benchmark checkout 7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f
cp -r ~/polyglot-benchmark/java/exercises/practice/affine-cipher judge/java-warmup
sudo docker build -t polyglot-judge:1 judge
export FOUNDRY_ANTHROPIC_BASE="https://<foundry-resource>.services.ai.azure.com/anthropic"
```""",
        tr(chinese,
           "Success: `vm_setup.sh` prints the httpx and azure-identity versions and the number of exercises per language, and the build ends with the versions of Python, Go, Rust, Node, Java and CMake. Sign out and back in once so that your user can run `docker` without `sudo`; the judge needs it.",
           "成功时 `vm_setup.sh` 输出 httpx 和 azure-identity 的版本以及每种语言的练习数，镜像构建最后输出 Python、Go、Rust、Node、Java 和 CMake 的版本。退出再重新登录一次，让当前用户不用 `sudo` 就能运行 `docker`，评分器需要这一点。"),
        tr(chinese, "**2. Probe the accepted values.** About 102 requests.", "**2. 探测接受的取值。** 约 102 个请求。"),
        """```bash
~/venv/bin/python probe.py --out-dir runs/probe
```""",
        tr(chinese,
           "Success: `runs/probe/probe_summary.json` lists the accepted modes and efforts; compare it with [ours](../evidence/coding-matrix-20261026/probe/probe_summary.json). A different list means the deployments behave differently from 2026-10-26; the matrix will follow your list.",
           "成功时 `runs/probe/probe_summary.json` 列出接受的思考模式和推理档位，可与[我们的结果](../evidence/coding-matrix-20261026/probe/probe_summary.json)对比。列表不同说明部署的行为已与 2026-10-26 不同；矩阵会按你的列表运行。"),
        tr(chinese, "**3. Rebuild the measured problems.**", "**3. 重建实测题目。**"),
        """```bash
~/venv/bin/python prepare.py --ids ../data/coding-problems.json --out problems.json
```""",
        tr(chinese,
           "Success: 18 `ACCEPT` lines. It stops if a rebuilt prompt differs from the measured one, or if a reference solution fails or an unedited stub passes in the judge.",
           "成功时输出 18 行 `ACCEPT`。如果重建的提示与实测不同，或者参考答案在评分器里失败、未修改的待补全文件反而通过，脚本会停止。"),
        tr(chinese,
           "**4. Run the matrix and the judge.** Both run in the background; the judge scores answers as they arrive.",
           "**4. 运行编码矩阵和评分器。** 两者都在后台运行；评分器边收到回答边评分。"),
        """```bash
RUN=runs/matrix-$(date -u +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
nohup ~/venv/bin/python bench.py --run-dir "$RUN" --problems problems.json \\
  --probe-summary runs/probe/probe_summary.json --repeats 3 --max-tokens 128000 --budget-usd 150 \\
  > "$RUN/bench.log" 2>&1 &
nohup ~/venv/bin/python judge.py --run-dir "$RUN" --problems problems.json --workers 2 --watch \\
  > "$RUN/judge.log" 2>&1 &
tail -F "$RUN/progress.log"
```""",
        tr(chinese,
           "Success: one `progress.log` line per request and `\"status\": \"COMPLETED\"` in `$RUN/run.json` at the end; ours took about five hours. `bench.py` exits at once if the median TCP connect time to the endpoint is 50 ms or more, because the client would not be in the models' region. To stop, end both processes (`pkill -f bench.py; pkill -f judge.py`); running the same two commands with the same `RUN` resumes and skips finished requests.",
           "成功时每个请求在 `progress.log` 里有一行，结束时 `$RUN/run.json` 显示 `\"status\": \"COMPLETED\"`；我们的运行用了约五小时。如果到端点的 TCP 建连中位数达到 50 毫秒，`bench.py` 会立即退出，因为这说明客户端不在模型所在区域。要停止就结束两个进程（`pkill -f bench.py; pkill -f judge.py`）；用同一个 `RUN` 再运行这两条命令会续跑，并跳过已完成的请求。"),
        tr(chinese, "**5. Analyse the run.**", "**5. 分析运行结果。**"),
        """```bash
~/venv/bin/python analyze.py --run-dir "$RUN"
```""",
        tr(chinese,
           "Success: a 21-row table and `$RUN/facts.json` with the same fields as [ours](../evidence/coding-matrix-20261026/matrix/facts.json). Answers are not deterministic and latency changes with load, so expect different numbers; compare them with our intervals rather than single values.",
           "成功时输出 21 行的表格，并生成字段与[我们的](../evidence/coding-matrix-20261026/matrix/facts.json)相同的 `$RUN/facts.json`。回答不是确定的，延迟随负载变化，数字会不同；请与我们的区间比较，而不是与单个数值比较。"),
        tr(chinese,
           "**6. Run the prompt-cache test.** Start it after the matrix, or add `--wait-run-dir \"$RUN\"` to let each model start when its matrix requests are done. The idle scenarios wait 6.5 minutes.",
           "**6. 运行提示缓存测试。** 在矩阵结束后启动，或者加上 `--wait-run-dir \"$RUN\"`，让每个模型在自己的矩阵请求结束后再开始。空闲场景要等 6.5 分钟。"),
        """```bash
CACHE=runs/cache-$(date -u +%Y%m%d-%H%M%S)
HTTPX_DIR=$(~/venv/bin/python -c "import httpx, os; print(os.path.dirname(httpx.__file__))")
~/venv/bin/python cache_test.py --out-dir "$CACHE" --package-dir "$HTTPX_DIR" --repetitions 2
~/venv/bin/python cache_analyze.py --run-dir "$CACHE"
```""",
        tr(chinese,
           "Success: `cache_analyze.py` prints one line per scenario and turn, and `$CACHE/context.json` has the same `context_sha256` as [ours](../evidence/coding-matrix-20261026/cache/context.json) when httpx is 0.28.1.",
           "成功时 `cache_analyze.py` 每个场景的每一轮输出一行；httpx 为 0.28.1 时，`$CACHE/context.json` 的 `context_sha256` 与[我们的](../evidence/coding-matrix-20261026/cache/context.json)相同。"),
        tr(chinese,
           "**What these steps cannot reproduce exactly.** The answers, and therefore pass counts, vary between runs; latency depends on time and load; GlobalStandard deployments may route requests differently. The public scripts differ from the measured ones only as listed in [provenance.json](../evidence/coding-matrix-20261026/provenance.json): `bench.py`, `probe.py`, `cache_test.py` and the judge image files are byte-identical.",
           "**这些步骤无法精确重现的部分。** 回答以及通过数每次都会不同；延迟取决于时间和负载；GlobalStandard 部署的路由可能不同。公开脚本与实测脚本的差异全部列在 [provenance.json](../evidence/coding-matrix-20261026/provenance.json)：`bench.py`、`probe.py`、`cache_test.py` 和评分镜像文件逐字节相同。"),
    ])
