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

def support_matrix_rows(d):
    outcomes = probe_outcomes(d)
    rows = []
    for model in MODELS:
        for mode in ("adaptive", "between_tools", "disabled", "enabled"):
            if mode == "enabled":
                status, message, _ = outcomes[("thinking_enabled_budget", model)]
                require(status == 400 and "thinking.type.enabled" in message,
                        "enabled-mode rejection is not established")
                efforts = {effort: status for effort in (*EFFORTS, "omitted")}
            else:
                efforts = {effort: outcomes[(f"{mode}_{'default_effort' if effort == 'omitted' else effort}", model)][0]
                           for effort in (*EFFORTS, "omitted")}
            require(all(status in (200, 400) for status in efforts.values()), "unresolved parameter probe")
            cached = any(row["model"] == DEPLOYMENT[model] and row["mode"] == mode
                         and (row.get("usage") or {}).get("cache_read_input_tokens", 0) > 0
                         for row in d["cache_rows"])
            rows.append({"model": model, "mode": mode, "efforts": efforts, "cache_observed": cached})
    return rows


def cache_setting_values(d):
    turns = cache_numbers(d)["turns"]
    values = {}
    for model in MODELS:
        deployment = DEPLOYMENT[model]
        values[model] = {}
        for scenario in ("auto", "system_only", "system_plus_auto"):
            shares = [turns[(deployment, scenario, turn)]["read_share"] for turn in (2, 3, 4)]
            values[model][scenario] = {
                "min": min(shares), "max": max(shares),
                "new_conversation": turns[(deployment, scenario + "_second", 1)]["read_share"],
            }
        for scenario in ("idle_5m", "idle_1h"):
            values[model][scenario] = turns[(deployment, scenario, 2)]["read_share"]
    return values


def matrix_figure(title, description, headers, widths, rows, heights, group=None, row_group=1,
                  unsupported_label="Not\nsupported"):
    left, top, header_height = 20, 76, 88
    width, height = sum(widths) + 40, top + header_height + sum(heights) + 20
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">',
             f'<title id="title">{html.escape(title)}</title>',
             f'<desc id="description">{html.escape(description)}</desc>',
             f'<rect width="{width}" height="{height}" fill="white"/>',
             '<g font-family="Segoe UI,Microsoft YaHei,sans-serif">',
             f'<text x="20" y="32" font-size="25" font-weight="600" fill="#1b1b1b">{html.escape(title)}</text>',
             f'<text x="20" y="58" font-size="17" fill="#605e5c">{html.escape(description)}</text>']

    def text_block(value, x_pos, y_pos, cell_width, cell_height, heading=False, align_left=False):
        lines = value.split("\n")
        baseline = y_pos + cell_height / 2 - (len(lines) - 1) * 12 + 6
        x_text = x_pos + 10 if align_left else x_pos + cell_width / 2
        anchor = "start" if align_left else "middle"
        colour = "white" if heading else "#242424"
        weight = "600" if heading else "400"
        for offset, line in enumerate(lines):
            parts.append(f'<text x="{x_text}" y="{baseline + offset * 24}" text-anchor="{anchor}" '
                         f'font-size="18" font-weight="{weight}" fill="{colour}" '
                         f'data-cell-width="{cell_width - 20}">{html.escape(line)}</text>')

    x_pos = left
    for column, (header, cell_width) in enumerate(zip(headers, widths)):
        grouped = group is not None and group[0] <= column < group[0] + group[1]
        y_pos, cell_height = (top + 40, header_height - 40) if grouped else (top, header_height)
        parts.append(f'<rect x="{x_pos}" y="{y_pos}" width="{cell_width}" height="{cell_height}" '
                     'fill="#0078d4" stroke="#2b88d8"/>')
        text_block(header, x_pos, y_pos, cell_width, cell_height, heading=True)
        x_pos += cell_width
    if group is not None:
        start, columns, label = group
        x_pos, cell_width = left + sum(widths[:start]), sum(widths[start:start + columns])
        parts.append(f'<rect x="{x_pos}" y="{top}" width="{cell_width}" height="40" fill="#005a9e"/>')
        text_block(label, x_pos, top, cell_width, 40, heading=True)
    y_pos = top + header_height
    for row_index, (row, row_height) in enumerate(zip(rows, heights)):
        x_pos = left
        for column, (value, cell_width) in enumerate(zip(row, widths)):
            if column == 0 and row_index % row_group:
                x_pos += cell_width
                continue
            cell_height = sum(heights[row_index:row_index + row_group]) if column == 0 else row_height
            unsupported = value is None
            fill = "#faf9f8" if unsupported else "#f3f2f1" if column == 0 else "#ffffff"
            if value and value.startswith(("Supported", "支持", "Default", "默认", "Applicable", "适用")):
                fill = "#dff6dd"
            parts.append(f'<g data-row="{row_index}" data-column="{column}" '
                         f'data-unsupported="{str(unsupported).lower()}">')
            parts.append(f'<rect x="{x_pos}" y="{y_pos}" width="{cell_width}" height="{cell_height}" '
                         f'fill="{fill}" stroke="#c8c6c4"/>')
            if unsupported:
                text_block(unsupported_label, x_pos, y_pos, cell_width, cell_height)
            else:
                text_block(value, x_pos, y_pos, cell_width, cell_height,
                           align_left=column == 1 or (len(headers) == 6 and column == 5))
            parts.append('</g>')
            x_pos += cell_width
        y_pos += row_height
    return "\n".join(parts) + "\n</g></svg>"


def support_figure(d, chinese):
    rows, heights = [], []
    for item in support_matrix_rows(d):
        model, mode = item["model"], item["mode"]
        mode_text = "enabled +\nbudget_tokens" if mode == "enabled" else mode
        values = []
        for effort, status in item["efforts"].items():
            value = None if status == 400 else tr(chinese, "Supported", "支持")
            if value and effort == "omitted":
                value = tr(chinese, "Default\n", "默认\n") + DEFAULT_EFFORT[model]
            values.append(value)
        applicable = any(status == 200 for status in item["efforts"].values())
        cached = tr(chinese, "Applicable", "适用") if applicable else tr(chinese, "Not applicable", "不适用")
        rows.append([NAME[model], mode_text, *values, cached])
        heights.append(82)
    headers = [tr(chinese, "Model", "模型"), tr(chinese, "Thinking mode\nthinking.type", "思考模式\nthinking.type"),
               *EFFORTS, tr(chinese, "Omitted", "不传"), tr(chinese, "Prompt cache\ncache_control", "提示缓存\ncache_control")]
    return matrix_figure(
        tr(chinese, "Table 1. Thinking modes, effort levels and prompt caching",
           "表 1　思考模式、推理档位与提示缓存"),
          tr(chinese, "Direct Foundry probe, 2026-10-26. Not supported: rejected mode/combination. See scope notes below.",
              "2026-10-26 直连 Foundry 探测。不支持：模式或组合被拒绝；缓存列的实测范围见图下注。"),
        headers, [115, 235, *([110] * 6), 170], rows, heights,
          group=(2, 6, tr(chinese, "Effort: output_config.effort", "推理档位：output_config.effort")), row_group=4,
          unsupported_label=tr(chinese, "Not\nsupported", "不支持"))


def cache_settings_figure(d, chinese):
    values = cache_setting_values(d)
    supported = tr(chinese, "Supported", "支持")
    rows = [[tr(chinese, "cache_control:\nomitted", "不传\ncache_control"),
             tr(chinese, "No cache_control field", "不加 cache_control 字段"),
             *([tr(chinese, "No reads/writes", "缓存读写均为 0")] * 3),
             tr(chinese, f"Historical coding matrix:\n{count(len(d['responses']))} requests, no cache reads\nor writes; no tool calls.",
                f"历史编码矩阵 {count(len(d['responses']))} 个请求，\n缓存读写均为 0；没有工具调用。")]]
    labels = {"auto": ("Position: automatic", "位置：自动断点"),
              "system_only": ("Position: explicit", "位置：显式断点"),
              "system_plus_auto": ("Position: combined", "位置：自动＋显式")}
    syntax = {
        "auto": tr(chinese, 'At request top level:\ncache_control: {"type": "ephemeral"}', '请求顶层：\ncache_control: {"type": "ephemeral"}'),
        "system_only": tr(chinese, 'On a content block:\ncache_control: {"type": "ephemeral"}', '内容块上：\ncache_control: {"type": "ephemeral"}'),
        "system_plus_auto": tr(chinese, "At both positions above", "上面两处都写"),
    }
    notes = {
        "auto": tr(chinese, "Tested new conversation: same\ninstructions/files, different question.\nThe prior full-prefix entry did not match.",
                   "本次新对话复用指令和文件，\n但换了问题；旧的完整前缀没有命中。\n不能据此断言所有新对话都不能命中。"),
        "system_only": tr(chinese, "Measured: end of repository in system.\ntools/messages locations: docs only.\nUp to 4 breakpoints per request (docs).",
                          "实测：system 中仓库文件末尾。\ntools、messages 位置仅有文档依据。\n每请求最多 4 个断点（文档）。"),
        "system_plus_auto": tr(chinese, "Both positions in one request.\nThe new-conversation result applies\nto this same-files test.",
                               "同一请求同时使用两种位置；\n新对话结果限于本次同文件测试。"),
    }
    for scenario in ("auto", "system_only", "system_plus_auto"):
        cells = []
        for model in MODELS:
            value = values[model][scenario]
            interval_text = span(value["min"], value["max"], pct) + "%"
            cells.append(supported + "\n" + tr(chinese, f"turns 2-4: {interval_text}", f"第 2-4 轮：{interval_text}")
                         + "\n" + tr(chinese, "new chat: ", "新对话：") + pct(value["new_conversation"]) + "%")
        rows.append([tr(chinese, *labels[scenario]), syntax[scenario], *cells, notes[scenario]])
    for scenario, duration in (("idle_5m", "5m"), ("idle_1h", "1h")):
        cells = [supported + "\n" + tr(chinese, "after 6.5 min idle", "闲置 6.5 分钟后")
                 + "\n" + tr(chinese, "read ", "读取 ") + pct(values[model][scenario]) + "%" for model in MODELS]
        rows.append([
            tr(chinese, "TTL: 5 minutes" if duration == "5m" else "TTL: 1 hour",
               "有效期：5 分钟" if duration == "5m" else "有效期：1 小时"),
            tr(chinese, 'Omit ttl (default), or "ttl": "5m"', '省略 ttl（默认），或 "ttl": "5m"') if duration == "5m"
            else 'cache_control:\n{"type": "ephemeral", "ttl": "1h"}',
            *cells,
            tr(chinese, "5-minute writes: 1.25x input price.\nHits refresh lifetime (docs).",
               "5 分钟写入按输入价 1.25 倍计费；\n命中会续期（文档）。") if duration == "5m"
            else tr(chinese, "1-hour writes: 2x input price (docs).\nIdle test waited 6.5 min, not 1 hour.",
                    "1 小时写入按输入价 2 倍计费（文档）；\n本次只闲置 6.5 分钟，未等满 1 小时。"),
        ])
    rows.append([tr(chinese, "Prompt:\n<512 tokens", "提示：\n不足 512 tokens"),
                 tr(chinese, "Either marker position", "任一缓存标记位置"),
                 *([tr(chinese, "No cache, no error", "不缓存，不报错")] * 3),
                 tr(chinese, "512-token minimum: documentation.\nMeasured short prompt: about 20 tokens;\nHTTP 200, zero cache reads and writes.",
                    "512 tokens 下限来自文档；\n实测约 20 tokens：HTTP 200，读写为 0。")])
    return matrix_figure(
        tr(chinese, "Table 2. Prompt-cache controls and observed cache-read share",
           "表 2　提示缓存设置与实测读取比例"),
        tr(chinese, "Direct Foundry cache test, 2026-10-26. Percentages describe these requests, not an ACA retest.",
           "2026-10-26 直连 Foundry 缓存测试。百分比对应该次请求，不是 ACA 重测结果。"),
        [tr(chinese, "Cache setting", "缓存设置"), tr(chinese, "Request syntax", "怎么写"),
         *[tr(chinese, "Model: ", "模型：") + NAME[model] for model in MODELS], tr(chinese, "Scope and notes", "说明与范围")],
        [190, 370, 230, 230, 230, 410], rows, [96, 116, 116, 104, 104, 104, 104])


def support_tables(d, chinese, language):
    accepted = sum(status == 200 for row in support_matrix_rows(d) for status in row["efforts"].values())
    title1 = tr(chinese, "**Table 1. Complete thinking-mode and effort matrix.**",
                "**表 1：完整思考模式与推理档位矩阵。**")
    title2 = tr(chinese, "**Table 2. Complete prompt-cache settings.**", "**表 2：完整提示缓存设置。**")
    image1 = f'[![{title1.strip("*")}](images/parameter-support-{language}.svg)](images/parameter-support-{language}.svg)'
    image2 = f'[![{title2.strip("*")}](images/cache-settings-{language}.svg)](images/cache-settings-{language}.svg)'
    notes1 = tr(chinese,
                f"The 54 `adaptive`/`between_tools`/`disabled` × effort cells were individually probed; {accepted} were accepted, including five omitted-effort cells. For `enabled`, one request per model used `budget_tokens: 1024` and omitted effort; the HTTP 400 rejects the mode itself, so all effort cells say not supported. The cache column states applicability only: a rejected thinking mode makes the request inapplicable; it does not mean the model lacks caching. Default effort values are from the [effort documentation]({EFFORT_DOC}).",
                f"`adaptive`、`between_tools`、`disabled` 与六列档位共 54 格，均单独探测；其中 {accepted} 格被接受，包括五个不传 effort 的格子。`enabled` 每模型只测一次：`budget_tokens: 1024`，不传 effort；HTTP 400 拒绝的是模式本身，所以六个档位格都标“不支持”。缓存列只写适用性：思考模式使请求被拒时标“不适用”，不是说模型不支持缓存。默认档位来自[effort 文档]({EFFORT_DOC})。")
    cache_scope = tr(chinese,
                     "Historical cache scope: all five accepted model/mode rows read cache at effort low; adaptive also read cache in the high-effort switch scenario. The separate ACA performance section reports the later full mode/effort coverage. Applicability and parameter acceptance alone do not establish cache-enabled performance. Fixed historical matrix controls: `max_tokens: 128000`, `stream: true`; `temperature`, `top_p`, `top_k` omitted. No `thinking` field is documented to select adaptive; the three omitted-thinking/omitted-effort probes returned 200.",
                     "历史缓存范围：当时五个被接受的模型／模式行均在 low 档读到缓存；adaptive 在切换到 high 的场景也读到缓存。后续全矩阵的覆盖与结果见独立的 ACA 性能章节。“适用”和“参数被接受”本身不证明缓存性能。历史矩阵固定项为 `max_tokens: 128000`、`stream: true`；`temperature`、`top_p`、`top_k` 不传。不传 thinking 等同 adaptive 来自文档；三个模型同时不传 thinking、effort 的探测均返回 200。")
    notes2 = tr(chinese,
                f"Sources: [probe requests](evidence/coding-matrix-20261026/probe/probe_results.jsonl), [cache requests](evidence/coding-matrix-20261026/cache/cache_results.jsonl) and [prompt-caching documentation]({CACHE_DOC}). Table 2 uses two repetitions per scenario: Opus adaptive, Sonnet between_tools, Haiku disabled, effort low; first writes are separate from turns 2-4. Read share is read tokens / (uncached + written + read input tokens), aggregated within each model/scenario/turn. New conversations reuse the files but change the question. The 512-token boundary and four-breakpoint limit are documented, not boundary-sweep measurements. All cache markers use `type: ephemeral`; reads cost 0.05x base input on Opus/Sonnet and 0.1x on Haiku (documented prices). These are historical direct-VM observations, not evidence for the later ACA run.",
                f"来源：[探测请求](evidence/coding-matrix-20261026/probe/probe_results.jsonl)、[缓存请求](evidence/coding-matrix-20261026/cache/cache_results.jsonl)及[缓存文档]({CACHE_DOC})。表 2 每场景重复两次：Opus adaptive、Sonnet between_tools、Haiku disabled，effort low；首轮写入与第 2-4 轮读取分开。读取比例＝读取 tokens ÷（未缓存＋写入＋读取的输入 tokens），按模型／场景／轮次汇总。新对话话题变化，但复用文件。512-token 边界和四断点上限来自文档，并非边界扫描实测。缓存标记均为 `type: ephemeral`；读取按输入价计费：Opus／Sonnet 0.05 倍、Haiku 0.1 倍（文档价格）。这些是历史 VM 直连观察，不能作为后续 ACA 批次的证据。")
    return "\n\n".join([title1, image1, notes1, cache_scope, title2, image2, notes2])


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
                for name in ("max_tokens_1000000", *(f"adaptive_{s}" for s in sampling))]
    rejected += [(f"{OFF_MODE[model]}_{s}", model) for model in OFF_MODE for s in sampling]
    require(all(outcomes[key][0] == 400 for key in rejected), "a probe expected to return HTTP 400 did not")
    require(m["thought_streamed"] == 0, "a matrix answer streamed thinking text")
    require(d["runs"]["cache"]["http"] == {200: k["requests"]}, "a cache request did not return HTTP 200")
    require({x["sku"] for x in d["provenance"]["models"]["deployments"]} == {"GlobalStandard"}, "a deployment is not GlobalStandard")
    baseline = [r for r in d["cache_rows"] if r["scenario"] == "none"]
    require(baseline and not any(r["automatic"] or r["breakpoint"] for r in baseline), "the cache baseline sent cache_control")
    require(not any((r.get("usage") or {}).get(field) for r in d["responses"] + baseline
                    for field in ("cache_read_input_tokens", "cache_creation_input_tokens")),
            "a request without cache_control read or wrote the cache")
    prefix = round(min(r["usage"]["input_tokens"] for r in baseline if r["turn"] == 1), -2)
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
        ("`thinking.display`",
         'Whether thinking text comes back. The default on these models, `"omitted"`, returns thinking blocks with empty text and an encrypted signature, so the answer starts streaming sooner; the thinking tokens are still billed. `"summarized"` returns a summary',
         f"Not sent: {count(m['thought'])} matrix answers used thinking tokens and none streamed thinking text"),
        ("`output_config.effort`",
         f"How much work goes into the whole response, thinking included: `low`, `medium`, `high`, `xhigh`, `max`. A behavioral signal, not a token budget. Default when omitted: Opus and Haiku `{opus_default}`, Sonnet `{sonnet_default}`",
         f"Every level each thinking mode accepted: {cells} cells"),
        ("`max_tokens`",
         'Hard limit on output tokens, thinking included; an answer that reaches it stops with `stop_reason: "max_tokens"`. At most 128,000 on these models',
         f"{count(max_tokens)} in the matrix; 1,000,000 returned HTTP 400"),
        ("No `cache_control` (the default)",
         'Nothing is cached: caching is opt-in. "Automatic caching" also needs the top-level field; "automatic" means the breakpoint is placed for you, not that caching is on by default. The documented exceptions involve tools: in a tool-use loop, history sent back with tool results can be cached without a marker, and server-tool results are cached automatically',
         f"The coding matrix ({count(m['requests'])} requests) and the cache test's baseline ({len(baseline)} requests; each turn resent the same prefix of about {count(prefix)} tokens): 0 cache reads and 0 cache writes in every response"),
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
        ("`thinking.display`",
         '是否返回思考文字。这些模型默认 `"omitted"`：thinking 块的文字为空、只带加密签名，所以回答更早开始流式返回；思考 token 照样计费。`"summarized"` 返回摘要',
         f"未发送：矩阵中 {count(m['thought'])} 个回答用了思考 token，没有一个流式返回思考文字"),
        ("`output_config.effort`",
         f"模型在整个回答上投入多少，包括思考：`low`、`medium`、`high`、`xhigh`、`max`。它是行为信号，不是 token 预算。不传时 Opus 和 Haiku 为 `{opus_default}`，Sonnet 为 `{sonnet_default}`",
         f"每种思考模式接受的全部档位，共 {cells} 格"),
        ("`max_tokens`",
         '输出 token 的硬上限，包括思考；回答达到上限时以 `stop_reason: "max_tokens"` 停止。这些模型最大 128,000',
         f"矩阵用 {count(max_tokens)}；1,000,000 返回 HTTP 400"),
        ("不传 `cache_control`（默认）",
         "不缓存：缓存要由请求主动开启。“自动缓存”同样要在顶层传 `cache_control`，“自动”指断点位置由系统决定，不是默认开启。官方文档写明的例外都和工具有关：工具调用循环中随 tool_result 回传的历史不加标记也可能被缓存，服务器工具的结果会自动缓存",
         f"编码矩阵（{count(m['requests'])} 个请求）和缓存测试的基线场景（{len(baseline)} 个请求，每轮都重发同样约 {count(prefix)} 个 token 的前缀）：每个响应的缓存读取和写入都是 0"),
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
    lines = ["| " + tr(chinese, "Setting | What it does | Historical observation", "设置 | 作用 | 历史观测") + " |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return "\n".join(lines)


def purpose(d, chinese, language, historical=False):
    m = matrix_numbers(d)
    snapshot = read_json(ROOT / "evidence/gateway-cache-20261026/interim-facts.json")
    coverage = snapshot["coverage"]
    snapshot_link = tr(chinese,
        f"**Completed ACA run:** {coverage['observed_requests']}/{coverage['planned_requests']} requests retained, {coverage['observed_measured']} measured answers graded. Performance comes first below, followed by correctness. [Full results](docs/results.md#aca-gateway-snapshot).",
        f"**本轮 ACA 已完成：** 已保存 {coverage['observed_requests']}/{coverage['planned_requests']} 次请求，{coverage['observed_measured']} 份正式答案已评分。下面先看性能，再看正确率。[完整结果](docs/results_CN.md#aca-gateway-snapshot)。")
    models = d["provenance"]["models"]
    versions = {x["version"] for x in models["deployments"]}
    require(versions == {"2"}, "the deployments are not all version 2, the Hosted on Azure version")
    version, region = next(iter(versions)), models["resourceRegion"]
    cells, n_problems, repeats = len(d["facts"]["cells"]), len(m["problems"]), m["repeats"]
    require(cells * n_problems * repeats == m["measured"] and m["warmups"] == cells, "matrix request counts do not add up")
    intro = tr(chinese,
               f"**What this measures.** How Claude Opus 5.5, Sonnet 5.5 and Haiku 5.5 perform as deployed in Microsoft Foundry with the [Hosted on Azure]({HOSTING_DOC}) option: model version {version}, an Anthropic-operated service running on Azure infrastructure, in GlobalStandard deployments. For each coding request we measure how long the first visible text and the full answer take, whether the code passes the problem's own unit tests, and what the request costs at list price. The request settings in the table below change all of these, and some combinations are rejected with HTTP 400; a successful HTTP response shows none of this.",
               f"**测什么。** 测 Claude Opus 5.5、Sonnet 5.5 和 Haiku 5.5 以 [Hosted on Azure]({HOSTING_DOC}) 方式部署在 Microsoft Foundry 上时的表现：模型版本 {version}，即 Anthropic 运营、运行在 Azure 基础设施上的服务，部署类型为 GlobalStandard。对每个编码请求，我们测首个可见文字和完整回答各要等多久、写出的代码能否通过题目自带的单元测试、按标价花多少钱。下表中的请求设置会同时改变这几项，有些组合还会直接返回 HTTP 400；只看请求成功看不出这些。")
    methods = tr(chinese,
                 f"**Current test method.** Linux VM client → LiteLLM on Azure Container Apps → Foundry, with the client, gateway and Foundry resource in {region}. The client uses the gateway key; LiteLLM uses its managed identity to call Foundry. Prompt caching is enabled with top-level `cache_control`. Each model has one request in flight, so this measures individual requests, not load.\n\n"
                 "**Historical gateway check (2026-10-24).** A Windows client sent a five-turn conversation through LiteLLM on Azure Container Apps in Japan East to the same deployments; LiteLLM used its own managed identity and was set not to drop parameters or retry. Those times include Japan-to-US network latency and are not results from the current East US 2 run. See [the results page](docs/results.md#gateway-test-2026-10-24).",
                 f"**当前测试方法。** Linux VM 客户端 → Azure Container Apps 上的 LiteLLM → Foundry；客户端、网关和 Foundry 资源均位于 {region}。客户端使用网关入口密钥，LiteLLM 以自己的托管身份调用 Foundry。通过请求顶层 `cache_control` 开启提示缓存。每个模型同一时间只有 1 个请求，测的是单个请求的表现，不是压力测试。\n\n"
                 "**历史网关检查（2026-10-24）。** Windows 客户端通过 Japan East 的 Azure Container Apps 上的 LiteLLM，向同一组部署发送五轮对话；LiteLLM 用自己的托管身份转发，设置为不丢弃参数、不重试。那次耗时包含日本到美国东部的网络延迟，不是当前 East US 2 测试的结果。详见[结果页](docs/results_CN.md#网关测试)。")
    figure = (f'<img src="images/topology-{language}.svg" width="900" alt="'
                + tr(chinese, "Current cache-enabled test path: a Linux VM client sends streaming requests through LiteLLM on Azure Container Apps in East US 2 to the three Microsoft Foundry Claude deployments. Prompt caching is at Foundry; the client records timing and native usage.",
                    "当前开启缓存的测试路径：Linux VM 客户端经 East US 2 的 Azure Container Apps 上的 LiteLLM 调用三个 Microsoft Foundry Claude 部署。提示缓存在 Foundry 侧；客户端记录时间和原生 usage。")
              + '" />')
    caption = tr(chinese,
                  "The figure shows the East US 2 gateway path, not the historical direct-VM result path. The [runner](gateway-cache/aca_cache_matrix.py) uses the [12-problem manifest](data/gateway-cache-problems.json): 26 accepted mode/effort cells, two identical requests per problem/cell, plus 26 warm-ups (650 requests collected). Top-level `cache_control` is `ephemeral`, TTL `1h`; request 1 writes and request 2 is checked for native cache reads. These are repeated requests, not conversation turns or a cache-disabled comparison. The complete performance table reports each request number separately, with code-test outcomes for all measured answers. Historical results retain their dates and paths. Original explanatory diagram with unmodified [Azure icons](images/icon-sources.json).",
                  "图中展示美东二网关路径，不是历史 VM 直连结果的路径。[运行器](gateway-cache/aca_cache_matrix.py)使用[12 道题清单](data/gateway-cache-problems.json)：26 个被接受的模式／档位组合，每题每格原样发送两次，另有 26 个预热请求，已收齐 650 次。请求顶层 `cache_control` 为 `ephemeral`，有效期 `1h`；第1次写入，第2次检查原生缓存读取。这是重复请求，不是连续对话轮次，也不是关闭缓存的对照。完整性能表按请求次序分别列数，并保留全部正式答案的代码测试结果。历史结果保留原日期与调用路径。原创说明图，使用未修改的 [Azure 图标](images/icon-sources.json)。")
    settings_lead = tr(chinese,
                       "**Historical request settings.** What each setting does, from Claude's documentation, and what the retained direct-VM runs sent. Accepted values come from that historical probe; these observations do not describe the current ACA run:",
                       "**历史请求设置。** 每个设置的作用（依据 Claude 官方文档），以及保留的旧 VM 直连批次发送了什么；各部署接受哪些取值来自历史参数探测。这些观测不是当前 ACA 测试的结果：")
    not_covered = tr(chinese,
                     "**Not covered:** tool use, where `between_tools` and progress updates matter; `display: \"summarized\"`; US Data Zone deployments; and the separate `claude-opus-5-5-fast` model in the Foundry catalog. This repository does not establish production capacity, quota limits or the resolution of any earlier incident: every run here was paced under the deployments' per-minute limits with one request in flight per model.",
                     "**未覆盖：** 工具调用（`between_tools` 和进度更新只在使用工具时才起作用）、`display: \"summarized\"`、US Data Zone 部署，以及 Foundry 模型目录里单独的 `claude-opus-5-5-fast` 模型。本仓库不证明生产容量、配额上限或任何历史故障已解决：这里的每次运行都把节奏控制在部署的每分钟限额之下，每个模型同时只有一个请求。")
    per_model = tr(chinese,
                   f"**Historical per-model summary.** What each deployment accepted and how it did on the {n_problems} problems in the retired direct-VM batch; not current ACA results:",
                   f"**历史批次按模型汇总。** 已取缔的 VM 直连批次中，每个部署接受什么，以及在这 {n_problems} 道题上的表现；不是当前 ACA 测试的结果：")
    scope = tr(chinese,
               f"**Historical scope.** The problems are public Exercism exercises from [Aider's polyglot benchmark]({POLYGLOT}), each answered once, without tools and without seeing the tests; they are not your production tasks. The retired batch called Foundry directly, one request at a time per deployment. Its costs and accuracy are historical observations, not evidence for the current cache-enabled ACA path. Costs use list prices and were not reconciled with an Azure invoice.",
               f"**历史结果范围。** 题目是 [Aider polyglot benchmark]({POLYGLOT}) 收录的 Exercism 公开练习，每次只答一次、不用工具、看不到测试；它们不是你的生产任务。已取缔的批次曾直连 Foundry，每个部署同一时间只有一个请求。其费用和正确率是历史观测，不能证明当前开启缓存的 ACA 路径的表现。费用按标价计算，没有与 Azure 账单核对。")
    sources = tr(chinese,
                 f"**Sources.** Accepted values and the HTTP 400 messages come from our probe ([results](docs/results.md#parameter-probe-2026-10-26)). What each setting does, the defaults, the rules for `between_tools` and `disabled`, and the advice to set `max_tokens` to 128,000 for agentic coding on Sonnet 5.5 come from Claude's [thinking]({THINKING_DOC}) and [effort]({EFFORT_DOC}) pages; cache rules and price multipliers from [prompt caching]({CACHE_DOC}); prices from [pricing]({PRICE_DOC}); hosting options and Foundry setup from [Claude in Microsoft Foundry]({FOUNDRY_DOC}); all read on 2026-10-26. The *Choose it when* row is our reading of these {n_problems} problems, not general advice.",
                 f"**来源。** 接受哪些取值、HTTP 400 的报错原文来自我们的参数探测（[结果页](docs/results_CN.md#参数探测)）。各设置的作用、默认值、`between_tools` 和 `disabled` 的使用规则，以及 Sonnet 5.5 做智能体编码时把 `max_tokens` 设为 128,000 的建议，来自 Claude 的 [thinking]({THINKING_DOC}) 和 [effort]({EFFORT_DOC}) 文档；缓存规则和价格倍数来自 [prompt caching]({CACHE_DOC})；价格来自 [pricing]({PRICE_DOC})；托管方式和 Foundry 配置来自 [Claude in Microsoft Foundry]({FOUNDRY_DOC})；均于 2026-10-26 查阅。“适合的情况”一行是我们对这 {n_problems} 道题的解读，不是通用建议。")
    if historical:
        return "\n\n".join([settings_lead, settings_table(d, chinese), support_tables(d, chinese, language),
                            not_covered, per_model, decision_table(d, chinese), scope, sources])
    return "\n\n".join([intro, snapshot_link, methods, figure, caption,
                        '<a id="historical-settings"></a>', settings_lead, settings_table(d, chinese),
                        support_tables(d, chinese, language), not_covered, per_model,
                        decision_table(d, chinese), scope, sources])


# ---------- README: results ----------

def glossary(chinese):
    rows = tr(chinese, [
        ("Cell", "One model × thinking mode × effort level. Each cell answered the 18 problems three times: 54 answers"),
        ("Thinking mode, effort level", "Defined in the [historical request-settings table](#historical-settings)"),
        ("First visible text", "Seconds from just before the request is written to the first non-empty `text_delta`, timed on the VM. Thinking comes first and its text is not streamed (`display` omitted), so this wait includes all thinking"),
        ("First event", "Seconds to the first server-sent event, `message_start`"),
        ("Full answer", "Seconds to the end of the stream, completed requests only"),
        ("Completed", "HTTP 200, `message_stop` received, `stop_reason` `end_turn` and non-empty text"),
        ("Pass", "The files in the answer, written over the exercise's solution files, make its own unit tests exit 0 in an offline container (Aider's first-attempt rule)"),
        ("By-problem 95% interval", "2.5th to 97.5th percentile over 5,000 resamples of the 18 problems (seed 20261026). The three answers to one problem are not independent, so the problem is the unit"),
        ("Cost", "List price × the token counts in the API's `usage`, cache writes and reads included"),
    ], [
        ("格", "一个模型 × 思考模式 × 推理档位的组合。每格把 18 道题各答 3 次，共 54 个回答"),
        ("思考模式、推理档位", "定义见[历史请求设置表](#historical-settings)"),
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
        "- **Gateway.** The retained 2026-10-24 gateway results used another region and do not characterize the current East US 2 ACA path.",
    ], [
        "**边界。**",
        "- **一个客户端、一个区域、一天、每个部署同一时间一个请求。** 没有并发、压力或长时间测试，也没有 Azure 以外的客户端。",
        "- **公开练习、只答一次、不用工具。** 与 Aider 的评测一样，模型能看到待补全的文件和题目说明，看不到测试。`between_tools` 与 `disabled` 只在工具循环里有区别，本测试没有工具循环。",
        "- **上限与样本量。** Opus 每格 54 个全过；18 道题的区间很宽，两格之间差几个回答属于噪声范围。",
        f"- **思考内容的显示。** 矩阵中 {count(m['thought'])} 个请求用了思考 token，流式返回思考文字的有 {m['thought_streamed']} 个，所以首个可见文字包含全部思考时间。没有测试 `display: \"summarized\"`。",
        f"- **路由。** GlobalStandard 部署可能在 East US 2 以外处理请求，矩阵的 {count(sum(m['geo'].values()))} 个响应里 `usage.inference_geo` 都是 `{m['geo_value']}`；换客户端位置或部署类型，延迟会不同。",
        "- **费用。** 按 2026-10-26 的标价计算，不是 Azure 账单。",
        "- **网关。** 保留的 2026-10-24 网关结果来自另一个区域，不能代表当前 East US 2 的 ACA 路径。",
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


DIRECTORIES = [
    ("README.md", "README_CN.md", "Owning pages: purpose, complete ACA performance table and the current execution sequence",
     "入口页：目的、完整 ACA 性能表和当前执行顺序"),
    ("docs/", None, "Results and testing pages in both languages; generated, not hand-edited",
     "两种语言的结果页和复测页；由生成器输出，不手改"),
    ("gateway-cache/", None, "Current ACA runner, gateway adapter, problem builder, analyzer and SWE-bench scoring driver",
     "当前 ACA 运行器、网关适配器、题库构建器、分析器和 SWE-bench 评分驱动"),
    ("coding-matrix/", None, "Measured client (`claude_api.py`, `bench.py`), probe, Aider-style judge and pricing; reused unchanged by the ACA runner",
     "实测客户端（`claude_api.py`、`bench.py`）、参数探测、Aider 风格评判和价格表；ACA 运行器原样复用"),
    ("deploy/", None, "LiteLLM gateway image: digest-pinned Dockerfile, `config.yaml`, provider-trace hook and `.env.example`",
     "LiteLLM 网关镜像：digest 固定的 Dockerfile、`config.yaml`、provider-trace 钩子和 `.env.example`"),
    ("data/", None, "Frozen inputs: the 12-problem ACA manifest, the 18 Exercism problems and the 2026-10-24 gateway matrix",
     "冻结输入：12 道题的 ACA 清单、18 道 Exercism 题目和 2026-10-24 的网关矩阵"),
    ("evidence/", None, "Raw run records, metrics projections, official SWE-bench reports and export manifests, one directory per run",
     "原始运行记录、指标投影、官方 SWE-bench 报告和导出清单，每次运行一个目录"),
    ("images/", None, "Generated SVG figures and the unmodified Azure icons they use ([sources](images/icon-sources.json))",
     "生成的 SVG 图和它们使用的未修改 Azure 图标（[来源](images/icon-sources.json)）"),
    ("scripts/", None, "Page and figure generators, plus the 2026-10-24 gateway collector and its analyzer",
     "页面和图的生成器，以及 2026-10-24 的网关采集器和分析器"),
    ("tests/", None, "Offline unit tests run locally and in CI", "本地和 CI 运行的离线单元测试"),
    ("NOTICE.md", None, "Third-party notices: Exercism exercises, Aider prompts and judge, httpx context files, Azure icons",
     "第三方声明：Exercism 练习、Aider 提示词与评判、httpx 上下文文件、Azure 图标"),
]


def directories(chinese):
    lines = ["| " + tr(chinese, "Path | What it holds", "路径 | 内容") + " |", "|---|---|"]
    for path, twin, en, cn in DIRECTORIES:
        label = f"[`{path}`]({path})" if path.endswith(".md") else f"`{path}`"
        if twin:
            label += ", " + f"[`{twin}`]({twin})"
        lines.append(f"| {label} | {tr(chinese, en, cn)} |")
    return "\n".join([tr(chinese, "**Repository layout.**", "**仓库目录。**"), *lines])


def environment_block(chinese, prefix, detailed):
    env = read_json(ROOT / "evidence/gateway-cache-20261026/environment.json")
    client, gateway, target, run = env["client"], env["gateway"], env["target"], env["run"]
    source = prefix + "evidence/gateway-cache-20261026/environment.json"
    digest = gateway["image_digest"][:19] + "…"
    os_cn = client["os"].replace("Ubuntu 24.04, kernel ", "Ubuntu 24.04，内核 ")
    if not detailed:
        return tr(chinese,
            f"**Environment of this run.** Client: Azure VM `Standard_D4s_v5` in East US 2 running {client['os']}, Python {client['python']}, httpx {client['httpx']}; the same VM that ran the direct coding matrix, holding only the gateway key. Gateway: LiteLLM 1.106.2 built from [`deploy/Dockerfile`](deploy/Dockerfile), image digest `{digest}`, one replica with 2 vCPU and 4 GiB on Azure Container Apps in East US 2, [`config.yaml`](deploy/config.yaml) with `drop_params: false` and zero retries. Target: the three Foundry deployments above, model version 2, GlobalStandard; responses reported `inference_geo: global`. The client VM was stopped and restarted once by the operator between {run['started_utc']} and {run['completed_utc']}. In-run gateway telemetry and the gateway's own request log were not captured. [Full record]({source}); the results page tabulates it.",
            f"**本批次的运行环境。** 客户端：East US 2 的 Azure VM `Standard_D4s_v5`，{os_cn}，Python {client['python']}，httpx {client['httpx']}；与直连编码矩阵同一台 VM，只持有网关入口密钥。网关：LiteLLM 1.106.2，由 [`deploy/Dockerfile`](deploy/Dockerfile) 构建，镜像 digest `{digest}`，East US 2 的 Azure Container Apps 上 1 个副本（2 vCPU、4 GiB），[`config.yaml`](deploy/config.yaml) 设 `drop_params: false`、零重试。目标：上述三个 Foundry 部署，模型版本 2，GlobalStandard；响应报告 `inference_geo: global`。{run['started_utc']} 到 {run['completed_utc']} 之间操作者停止并重启过一次客户端 VM。未采集网关运行中的遥测和网关自己的请求日志。[完整记录]({source})；结果页有分项表格。")
    rows = tr(chinese, [
        ("Client", client["compute"], f"{client['os']}; Python {client['python']}, httpx {client['httpx']}, azure-identity {client['azure_identity']}; runs [`aca_cache_matrix.py`]({prefix}gateway-cache/aca_cache_matrix.py), which imports the measured `claude_api.py` and `bench.py` unchanged; holds only the gateway key"),
        ("Gateway", gateway["service"], f"LiteLLM 1.106.2 built from [`deploy/Dockerfile`]({prefix}deploy/Dockerfile) on the digest-pinned official base; built image digest `{digest}`; {gateway['revision']}; [`config.yaml`]({prefix}deploy/config.yaml) with `drop_params: false` and zero retries; HTTPS-only ingress with a /32 allow-list"),
        ("Target", target["service"], target["inference_placement"]),
        ("Run window", f"{run['started_utc']} → {run['completed_utc']}", "The operator stopped and restarted the client VM in between; two measured pairs crossed that gap and rewrote expired cache entries, so they stay in request, cost and correctness counts and are excluded only from cache-hit statistics"),
    ], [
        ("客户端", "Azure VM `Standard_D4s_v5`，East US 2；与 2026-10-26 直连编码矩阵同一台 VM",
         f"{os_cn}；Python {client['python']}、httpx {client['httpx']}、azure-identity {client['azure_identity']}；运行 [`aca_cache_matrix.py`]({prefix}gateway-cache/aca_cache_matrix.py)，原样导入实测的 `claude_api.py` 和 `bench.py`；只持有网关入口密钥"),
        ("网关", "Azure Container Apps，East US 2，Consumption 工作负载配置",
         f"LiteLLM 1.106.2，由 [`deploy/Dockerfile`]({prefix}deploy/Dockerfile) 基于 digest 固定的官方镜像构建；镜像 digest `{digest}`；单修订模式 1 个副本（最小 1、最大 1），2 vCPU、4 GiB 内存、8 GiB 临时存储；[`config.yaml`]({prefix}deploy/config.yaml) 设 `drop_params: false`、零重试；仅 HTTPS 入口，三条 /32 放行规则（地址已省略）"),
        ("目标", "Microsoft Foundry 资源，East US 2；Claude Opus 5.5、Sonnet 5.5、Haiku 5.5，模型版本 2，GlobalStandard",
         "响应报告 `inference_geo: global` 和 East US 2 服务区域头；GlobalStandard 不固定推理区域"),
        ("运行窗口", f"{run['started_utc']} → {run['completed_utc']}",
         "期间操作者停止并重启过客户端 VM；两组正式配对跨越该间隔、重写了过期缓存，仍计入请求、费用和正确率，只从缓存命中统计中排除"),
    ])
    lines = ["| " + tr(chinese, "Part | Where | Version and configuration", "部分 | 位置 | 版本与配置") + " |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    return "\n\n".join([
        tr(chinese,
           f"**Environment of this run.** Read from the operator's management-plane readbacks and the client VM's records after the run; identifiers that would name the subscription, resource group, hosts or addresses are omitted. [Full record]({source}).",
           f"**本批次的运行环境。** 取自运行后操作者的管理面读回和客户端 VM 自己的记录；会暴露订阅、资源组、主机或地址的标识已省略。[完整记录]({source})。"),
        "\n".join(lines),
        tr(chinese,
           f"Not captured: in-run CPU, memory or replica-restart telemetry on the gateway, packet captures, and the gateway's own request log for this batch, which is the outbound-audit gap stated below. The digest identifies the operator's built image; rebuilding [`deploy/Dockerfile`]({prefix}deploy/Dockerfile) yields a different digest from the same pinned base.",
           f"未采集：网关在运行中的 CPU、内存或副本重启遥测、抓包，以及网关自己对本批次的请求日志——这就是下文所说的出站审计缺口。digest 标识的是操作者构建的镜像；用同一固定基础镜像重新构建 [`deploy/Dockerfile`]({prefix}deploy/Dockerfile) 会得到不同 digest。"),
    ])


def gateway_controls(facts, chinese, prefix):
    suffix = "_CN" if chinese else ""
    source = prefix + "evidence/gateway-cache-20261026"
    legacy_link = ("results" if prefix else "docs/results") + suffix + ".md" + tr(chinese, "#gateway-test-2026-10-24", "#网关测试")
    transport = facts["transport"]
    http_counts = ", ".join(f"HTTP {status}: {count}" for status, count in sorted(transport["http_statuses"].items()))
    parts = [tr(chinese, "### What the parameter evidence proves", "### 参数证据能证明什么"),
             tr(chinese,
                f"**Transport is not task success.** Recorded physical attempts: {transport['attempts']}; {http_counts}; retries: {transport['retry_attempts']}. These counts include warm-ups and any recorded retry attempts. The completion table retains truncated answers; this small, paced run is not a capacity or reliability guarantee.",
                f"**HTTP 成功不等于任务完成。** 记录到 {transport['attempts']} 次物理尝试，状态分布为 {http_counts}；重试 {transport['retry_attempts']} 次。这里包含预热和所有已记录的重试；上面的完成表仍保留截断回答。这是限速后的小规模运行，不是容量或可靠性保证。"),
             tr(chinese,
                "| Evidence layer | Available evidence | What it does not establish |\n|---|---|---|\n"
                f"| Client request settings | `request_params` and `request_sha256` in the [captured requests]({source}/responses_opus.jsonl), before the documented model-alias mapping | Not a wire capture of the gateway's outbound request |\n"
                f"| Upstream response | Native cache and thinking usage, with completed / truncated outcomes in [all records]({source}/interim-facts.json) | Not proof that every accepted parameter was honored, or that effort monotonically controls tokens |\n"
                f"| Gateway outbound request | The [separate 2026-10-24 audit]({legacy_link}) correlates its own client requests with provider traces | Per-request outbound audit is not retained for the current batch; the older audit cannot fill this gap |",
                "| 证据层 | 已有证据 | 不能据此证明什么 |\n|---|---|---|\n"
                f"| 客户端请求参数 | [请求记录]({source}/responses_opus.jsonl)中的 `request_params`、`request_sha256`，记录在已说明的模型别名转换之前 | 不是网关出站请求的抓包 |\n"
                f"| 上游返回的行为 | [原生 usage 和终态]({source}/interim-facts.json)包含缓存读写、思考 token、完整结束和截断 | 不能证明所有被接受的参数都生效，也不能证明 effort 与 token 数严格单调 |\n"
                f"| 网关出站参数 | [2026-10-24 的独立审计]({legacy_link})对齐了该批次客户端请求与 provider trace | 当前批次未保留逐请求出站审计，不能拿旧批次补齐 |")]
    table = [tr(chinese,
        "| thinking.type | Measured requests | Native thinking usage present / requests | Requests with positive thinking tokens |",
        "| thinking.type | 正式请求数 | 有思考 token 字段／请求数 | 思考 token 大于零的请求数 |"),
        "|---|---:|---:|---:|"]
    for mode, item in facts["thinking_by_mode"].items():
        table.append(f"| `{mode}` | {item['requests']} | {item['usage_requests']}/{item['requests']} | {item['positive_thinking_requests']} |")
    parts.extend(["\n".join(table), tr(chinese,
        "This is observed usage, not a model ranking. No tool loop was exercised, so zero thinking in `between_tools` does not test its between-tool behavior. A zero value in an adaptive request alone does not prove a dropped parameter. Acceptance/rejection probes from the older direct path remain historical, not a current gateway support matrix.",
        "这些是 usage 观察，不是模型排名。本轮没有工具循环，因此 `between_tools` 的零思考 token 不能验证工具调用之间的行为。某条 adaptive 请求为零，也不能单凭这一点判定参数被丢弃。旧直连路径的接受／拒绝探测仍属历史证据，不是当前网关支持矩阵。"),
        tr(chinese, "### Configuration guidance and checks", "### 配置建议与验收观察"),
        tr(chinese,
            "| Setting to check | Reproducible configuration | Observable check and limit |\n|---|---|---|\n"
            f"| Gateway forwarding | Start from [config.yaml]({prefix}deploy/config.yaml): `drop_params: false`; gateway/router retries are zero | Capture [provider traces]({prefix}deploy/trace_hook.py) for the same call ID. Configuration text alone is not proof of forwarding; the matrix client can separately retry a 429 |\n"
            "| Prompt caching | This matrix uses top-level `cache_control`, `type: ephemeral`, `ttl: 1h` | Check native write and read token counts. It did not compare TTL choices or cache disabled; choose production TTL against actual session gaps and write cost |\n"
            "| Thinking and effort | Use the explicitly named configuration, preserving `default` as an omitted field | Compare matching rows plus their code-test outcomes. This public subset does not select a production-optimal effort |\n"
            "| Output cap and streaming | Reproduction uses `max_tokens: 128000`, `stream: true` | Require a terminal stream and inspect `stop_reason`; the cap still caused truncation. Do not count HTTP 200 or the first event as a completed answer |",
            "| 要检查的设置 | 可复现的配置 | 验收观察与边界 |\n|---|---|---|\n"
            f"| 网关透传 | 从 [config.yaml]({prefix}deploy/config.yaml) 开始：`drop_params: false`，网关与路由重试为零 | 采集同一 call ID 的 [provider trace]({prefix}deploy/trace_hook.py)。配置文本不等于已透传；矩阵客户端另有 429 重试策略 |\n"
            "| 提示缓存 | 本矩阵使用顶层 `cache_control`，`type: ephemeral`、`ttl: 1h` | 看原生写入和读取 token 数。本轮未比较不同 TTL 或关闭缓存；生产 TTL 须结合真实会话间隔和写入成本选择 |\n"
            "| 思考模式与档位 | 使用表中明确的配置，`default` 保留为不传字段 | 对比同条件性能和代码测试结果；这组公开题不能选出生产最优档位 |\n"
            "| 输出上限与流式响应 | 复现配置为 `max_tokens: 128000`、`stream: true` | 必须检查流终止及 `stop_reason`；该上限仍发生截断，不能把 HTTP 200 或首个事件当成回答完成 |")])
    return "\n\n".join(parts)


def gateway_performance_table(facts, score, chinese):
    lookup = {item["cell_id"]: item for item in score["cells"]}
    first = tr(chinese, "Request 1", "第1次")
    second = tr(chinese, "Request 2", "第2次")
    lines = [tr(chinese,
        "| Model / thinking.type / output_config.effort | Valid performance samples (requests) | TTFT P50 / P95 (s) | E2E P50 / P95 (s) | E2E output rate P50 (tokens/s, thinking included) | Mean cost (USD/request) | Cache-read share of input (%) | Resolved / graded answers (requests 1+2, %) |",
        "| 模型 / thinking.type / output_config.effort | 性能有效样本数（次） | TTFT P50 / P95（秒） | E2E P50 / P95（秒） | 端到端输出速率 P50（tokens/s，含思考） | 平均费用（美元/请求） | 输入缓存读取占比（%） | 已解决／评分答案数（第1+2次合计，%） |"),
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for cell, item in facts["by_cell"].items():
        model, mode, effort = cell.split("|")
        values = []
        for state in ("cold", "warm"):
            if not item["groups"]:
                values.append(["0", *([tr(chinese, "No eligible pair", "无有效配对")] * 5)])
                continue
            observed = item[state]
            require(observed["output_rate_samples"] == item["groups"], f"Missing output rate data: {cell}/{state}")
            values.append([str(item["groups"]),
                           f"{secs(observed['first_text_p50'])} / {secs(observed['first_text_p95'])}",
                           f"{secs(observed['end_p50'])} / {secs(observed['end_p95'])}",
                           f"{observed['output_tokens_per_second_p50']:.2f}",
                           usd(observed["cost_usd_per_request"], 6), pct(observed["read_share"], 2)])
        paired = [f"{first}: {initial}<br>{second}: {repeated}" for initial, repeated in zip(*values)]
        graded = lookup[cell]
        label = f"{NAME[model]}<br>`{mode}` / `{effort}`"
        lines.append(f"| {label} | " + " | ".join(paired)
                     + f" | {graded['resolved']}/{graded['denominator']} ({100 * graded['resolved'] / graded['denominator']:.2f}%) |")
    return "\n".join(lines)


def gateway_snapshot(chinese, detailed=False):
    evidence = ROOT / "evidence/gateway-cache-20261026"
    facts = read_json(evidence / "interim-facts.json")
    score_root = ROOT / "evidence/gateway-score-20261027"
    score = read_json(score_root / "score-summary.json")
    score_check = read_json(score_root / "verification.json")
    score_manifest = read_json(score_root / "manifest.json")
    observation = read_json(evidence / "collection-status.json")
    coverage = facts["coverage"]
    require(observation["snapshot_run_updated_utc"] == facts["run_updated_utc"], "ACA observation identifies another snapshot")
    prefix = "../" if detailed else ""
    source = prefix + "evidence/gateway-cache-20261026"
    suffix = "_CN" if chinese else ""
    heading = "##" if detailed else "###"
    parts = [f'{heading} ' + tr(chinese, "ACA gateway: performance results", "ACA 网关：性能测试结果")]
    if detailed:
        parts.insert(0, '<a id="aca-gateway-snapshot"></a>')
    parts.append(tr(chinese,
        f"**Complete collection, not universal success.** All {coverage['observed_requests']}/{coverage['planned_requests']} requests are retained: {coverage['observed_warmups']} warm-ups and {coverage['observed_measured']} measured answers. The run reached `{facts['status']}` at `{facts['run_updated_utc']}`. Failures and truncations remain in the counts. [Collection verification]({source}/collection-status.json).",
        f"**请求已收齐，不等于全部通过。** 已保留 {coverage['observed_requests']}/{coverage['planned_requests']} 次请求：{coverage['observed_warmups']} 次预热、{coverage['observed_measured']} 份正式答案。运行在 `{facts['run_updated_utc']}` 达到 `{facts['status']}`；失败和截断仍保留在统计中。[采集验收]({source}/collection-status.json)。"))
    parts.append(tr(chinese,
        "**Question and method.** For coding prompts sent through the East US 2 ACA LiteLLM gateway, does the identical second request read the cache written by the first, and what timing and cost were observed? The client and gateway were in East US 2; the Foundry resource was also in East US 2. One request was in flight per model. This is a cache-write versus cache-read pair, not a cache-disabled control or a gateway-overhead experiment.",
        "**问题与方法。** 编码提示通过 East US 2 的 ACA LiteLLM 网关发送后，原样重复的第二次请求能否读到第一次写入的缓存，观测到的耗时和费用是多少？客户端、网关和 Foundry 资源均在 East US 2；每个模型同时只有一个请求。这是首次写入与重复读取的配对，不是关闭缓存的对照，也不能隔离网关自身开销。"))
    parts.append(tr(chinese,
        f"**Input.** [12 public SWE-bench Lite BM25-13K problems]({prefix}data/gateway-cache-problems.json), with the source revision and prompt hashes in [run.json]({source}/run.json). This is a selected-subset experiment, not a full SWE-bench leaderboard score or customer production data. The [runner]({prefix}gateway-cache/aca_cache_matrix.py) uses 26 mode/effort cells, two identical requests per problem/cell and one warm-up per cell. Fixed: `max_tokens: 128000`, `stream: true`, top-level `cache_control: {{\"type\": \"ephemeral\", \"ttl\": \"1h\"}}`. Timing starts immediately before the client sends the request; first text is the first non-empty text delta, not a ping or thinking event.",
        f"**输入。** [12 道公开的 SWE-bench Lite BM25-13K 题目]({prefix}data/gateway-cache-problems.json)，来源版本和提示哈希在 [run.json]({source}/run.json)。这是选定子集实验，不是完整 SWE-bench 排行榜成绩，也不是客户生产数据。[运行器]({prefix}gateway-cache/aca_cache_matrix.py)遍历 26 个模式／档位组合，每题每格原样发送两次，每格另有一次预热。固定 `max_tokens: 128000`、`stream: true`、顶层 `cache_control: {{\"type\": \"ephemeral\", \"ttl\": \"1h\"}}`。计时从客户端即将发送请求时开始；首字是第一个非空文字增量，不是心跳或思考事件。"))
    sample = next(row for row in (json.loads(line) for line in
                  (evidence / "responses_opus.jsonl").read_text(encoding="utf-8").splitlines())
                  if row["kind"] == "measured")
    parts.append(tr(chinese,
        f"**Captured input settings.** The following fields are from measured request `{sample['task_id']}`, not its warm-up. The problem manifest above pins the public input reconstruction; this metrics projection omits prompt bodies.",
        f"**实际请求设置。** 以下字段取自正式请求 `{sample['task_id']}`，不是预热请求。上面的题单固定了公开输入的重建版本；本指标投影省略提示正文。"))
    parts.append("```json\n" + json.dumps(sample["request_params"], ensure_ascii=False, indent=2) + "\n```")
    parts.append(tr(chinese,
        "The runner prepends a deterministic system identifier per problem/configuration to isolate each pair's cache. The problem text is shared across configurations, but these identifiers differ. This controlled reuse is not an estimate of production cache-hit rate.",
        "运行器在每个题目／配置的 system 前添加确定性组标识，隔离各组缓存。各配置的题目正文相同，但组标识不同；这是受控复用，不是生产缓存命中率估计。"))
    parts.append(environment_block(chinese, prefix, detailed))
    parts.append(tr(chinese,
        "**Metric definitions.** TTFT is `timing.first_text`, the first non-empty visible text, not metadata or thinking. E2E is `timing.end`, through the end of the response stream. The client clock starts immediately before HTTP; credential acquisition, pacing and application/tool work are excluded. End-to-end output rate is `usage.output_tokens / timing.end` for each request, including thinking tokens; its P50 is not a ratio of medians or isolated decode speed. Costs include input, cache writes/reads and output at the recorded list prices, not infrastructure or an invoice.",
        "**指标定义。** TTFT 对应 `timing.first_text`，是首段非空可见文字，不是元数据或思考事件；E2E 对应 `timing.end`，到响应流结束。客户端在 HTTP 发送前开始计时，不含取凭据、发送前限速等待及应用或工具执行。端到端输出速率逐请求计算 `usage.output_tokens / timing.end`，包含思考 token，再取 P50；不是中位数相除，也不是纯解码速度。费用含输入、缓存写入／读取和输出，按记录中的标价计算，不含基础设施，也不是账单。"))
    parts.append(tr(chinese,
        "**All measured configurations, performance first.** A pair is the same problem and configuration sent twice: an observed cache write followed by a native cache hit, with both answers completed. Each state below uses one request from every eligible pair. P50/P95 use nearest rank; with at most 12 requests per state, P95 is the largest observation, not a production tail guarantee. `default` means effort was omitted. Compare matching configurations; generated output lengths may differ, so a timing or cost difference cannot be attributed entirely to caching.",
        "**先看全部配置的性能。** 一组对照是同题、同配置的两次请求：首次实际写入缓存，随后原生命中，且两次回答均完整结束。下表每种缓存状态各取一条请求。P50/P95 使用最近秩法；每组状态最多 12 条，P95 就是最大观测值，不是生产尾延迟保证。`default` 表示未传 effort。比较时须对齐配置；两次生成的输出长度可能不同，耗时或费用差异不能全部归因于缓存。"))
    parts.append(tr(chinese,
        "**Request numbers, not conversation turns.** Request 1 is the first identical-prompt submission and cache write; request 2 repeats that prompt and reads its cache. No answer history is appended, and there is no request 3 or 4 in this matrix. Each table cell names the request number. Cache-read share is the sum of native read tokens divided by all input tokens (uncached + write + read) for that request number. The last column grades both requests across all 12 problems: 24 answers per configuration, including failures, not just the performance subset.",
        "**请求次序，不是对话轮次。** 第1次是同题首次提交并写缓存；第2次原样重复该提示并读取缓存。没有追加上一轮答案，本矩阵也没有第3、4次请求。表中每个指标都标明对应次序。读取占比按该次序的原生读取 token 合计除以全部输入 token（未缓存＋写入＋读取）。最后一列对每个配置的12题×2次共24份答案评分，包含失败，不只使用性能有效样本。"))
    parts.append(gateway_performance_table(facts, score, chinese))
    headers = tr(chinese,
        "| Model | Retained / planned requests, warm-ups included | Completed requests | Truncated requests | Complete measured pairs | Cache-hit pairs |",
        "| 模型 | 已保存／计划请求数（含预热） | 正常结束的请求数 | 截断请求数 | 完整正式配对数（组） | 缓存命中配对数（组） |")
    table = [headers, "|---|---:|---:|---:|---:|---:|"]
    for model in MODELS:
        deployment = DEPLOYMENT[model]
        cells = [item for cell, item in facts["by_cell"].items() if cell.startswith(model + "|")]
        completed = sum(item["statuses"].get("completed", 0) for item in cells)
        truncated = sum(item["statuses"].get("max_tokens", 0) for item in cells)
        summary = facts["by_model"].get(deployment, {})
        table.append(f"| {NAME[model]} | {facts['final_requests'].get(deployment, 0)}/{facts['planned'][deployment]} | {completed} | {truncated} | {summary.get('completed_pairs', 0)} | {summary.get('groups', 0)} |")
    parts.append(tr(chinese, "### Completion and cache evidence", "### 完成情况与缓存证据"))
    if detailed:
        parts.append("\n".join(table))
    parts.append(tr(chinese,
        f"**Cache evidence.** {facts['groups_complete']} measured pairs completed; {facts['cache_hit_pairs']} show native cache hits. The other {len(facts['excluded_cache_pairs'])} crossed the shutdown/restart interval and rewrote expired entries. They remain in request, cost and correctness counts but not cache-hit performance statistics. Hit pairs read at least {pct(facts['warm_read_over_cold_write_min'])}% of the preceding cache write; {facts['same_message_id_groups']} reused a response message ID. This proves those cache reads, not a general speedup. Responses report `inference_geo: global` and an East US 2 region header; that is not a regional-inference guarantee.",
        f"**缓存证据。** {facts['groups_complete']} 组正式配对完整结束，其中 {facts['cache_hit_pairs']} 组有原生缓存命中。另 {len(facts['excluded_cache_pairs'])} 组跨越停机／恢复间隔，过期后重新写入缓存；它们仍计入请求数、费用和正确率，但不进入缓存命中性能统计。命中配对至少读回前次缓存写入的 {pct(facts['warm_read_over_cold_write_min'])}%，复用同一响应 message ID 的配对为 {facts['same_message_id_groups']}。这证明对应缓存读取，不证明普遍提速。响应报告 `inference_geo: global` 和 East US 2 区域头，不代表固定区域推理承诺。"))
    parts.append(tr(chinese,
        f"**Cost and limits.** The full run cost {usd(facts['cost_usd'])} at recorded [list prices]({prefix}coding-matrix/pricing.py), including warm-ups, writes, reads, output and truncated answers; infrastructure is excluded and this is not an invoice. Pair metrics exclude warm-ups and incomplete or non-hit pairs, never the correctness denominator. Full distributions and counts remain in [the facts]({source}/interim-facts.json).",
        f"**费用与边界。** 整轮按记录采用的[标价]({prefix}coding-matrix/pricing.py)计费共 {usd(facts['cost_usd'])}，包含预热、缓存写入／读取、输出和截断回答；不含基础设施费用，也不是账单。配对指标排除预热、不完整配对及非命中配对，但不会缩小正确率分母。完整分布与计数保存在[统计结果]({source}/interim-facts.json)。"))
    if detailed:
        progress = [tr(chinese,
            "| Model | thinking.type | output_config.effort | Retained / planned measured requests | Truncated requests, warm-ups included | Complete / planned pairs |",
            "| 模型 | thinking.type | output_config.effort | 已保存／计划正式请求数 | 截断请求数（含预热） | 完整／计划配对数 |"),
            "|---|---|---|---:|---:|---:|"]
        for cell, item in facts["by_cell"].items():
            model, mode, effort = cell.split("|")
            progress.append(f"| {NAME[model]} | `{mode}` | `{effort}` | {item['measured_requests']}/{item['planned_measured_requests']} | {item['statuses'].get('max_tokens', 0)} | {item['completed_pairs']}/{item['planned_groups']} |")
        parts.extend([tr(chinese, "### All configuration denominators", "### 全部配置的分母"), "\n".join(progress)])
    else:
        parts.append(tr(chinese, f"[All 26 configurations and paired observations](docs/results{suffix}.md#aca-gateway-snapshot).",
                        f"[查看全部 26 格及配对观测](docs/results{suffix}.md#aca-gateway-snapshot)。"))
    score_source = prefix + "evidence/gateway-score-20261027"
    if detailed:
        parts.append(gateway_controls(facts, chinese, prefix))
    else:
        parts.append(tr(chinese,
            f"**Evidence boundary.** Per-request outbound audit is not retained for the current batch. Earlier gateway traces cannot replace it. Parameter evidence and the separate audit are in [Results](docs/results{suffix}.md#aca-gateway-snapshot).",
            f"**证据边界。** 当前批次未保留逐请求出站审计，不能用早期网关日志补齐；参数证据和独立审计见[结果页](docs/results{suffix}.md#aca-gateway-snapshot)。"))
    parts.append(tr(chinese, "### Code correctness after performance", "### 性能之后：代码正确率"))
    parts.append(tr(chinese,
        f"**Method.** The same {score['denominator']} measured answers, excluding only warm-ups, were graded with the official SWE-bench harness {score_manifest['official_source']['installed_version']} at commit `{score_manifest['official_source']['commit']}`. The official `extract_diff` function extracted predictions; no answer repair or new model call was used. Each cell/repeat has a separate run ID. All {score_check['gold_controls']} selected gold controls passed. [Frozen inputs, native reports and verifier]({score_source}/verification.json).",
        f"**方法。** 对同一批 {score['denominator']} 份正式答案评分，只排除预热。使用官方 SWE-bench {score_manifest['official_source']['installed_version']}，固定提交 `{score_manifest['official_source']['commit']}`；由官方 `extract_diff` 提取补丁，没有替模型修答案，也没有新增模型调用。每个配置／重复次数使用独立 run ID；所选 {score_check['gold_controls']} 道金标准全部通过。[冻结输入、官方报告与验算]({score_source}/verification.json)。"))
    parts.append(tr(chinese,
        f"Overall: {score['resolved']}/{score['denominator']} ({100 * score['resolved'] / score['denominator']:.2f}%) resolved; {score['outcomes']['PATCH_APPLY_FAILED']} patch-application failures, {score['outcomes']['UNRESOLVED']} unresolved test results and {score['outcomes']['EMPTY_ANSWER_TRUNCATED']} truncated empty answers. These stay in the denominator. Different model/mode populations make the aggregate unsuitable as a fair overall ranking; each matched cell has 24 answers. This is a 12-instance subset, not the full SWE-bench Lite score.",
        f"合计 {score['resolved']}/{score['denominator']} 份解决问题（{100 * score['resolved'] / score['denominator']:.2f}%）；另有 {score['outcomes']['PATCH_APPLY_FAILED']} 份补丁应用失败、{score['outcomes']['UNRESOLVED']} 份测试未通过、{score['outcomes']['EMPTY_ANSWER_TRUNCATED']} 份截断空回答，均保留在分母中。不同模型的模式／档位组合数量不同，不能当成公平总榜；同条件每格均为 24 份答案。这只是 12 题子集，不是完整 SWE-bench Lite 成绩。"))
    grid = [tr(chinese, "| Model | thinking.type | output_config.effort | Resolved / measured answers | Resolved (%) |",
               "| 模型 | thinking.type | output_config.effort | 已解决／正式答案数 | 解决率（%） |"), "|---|---|---|---:|---:|"]
    lookup = {item["cell_id"]: item for item in score["cells"]}
    for cell in facts["by_cell"]:
        model, mode, effort = cell.split("|")
        item = lookup[cell]
        grid.append(f"| {NAME[model]} | `{mode}` | `{effort}` | {item['resolved']}/{item['denominator']} | {100 * item['resolved'] / item['denominator']:.2f} |")
    if detailed:
        parts.append("\n".join(grid))
    parts.append(tr(chinese,
        f"**Ambiguity retained.** {len(score_check['official_ambiguous_flags'])} official `no_tests_collected` flags remain unresolved. Each associated log first collected 92 top-level tests, includes nested zero-collection output, and shows `NameError: cached_eval`; none was silently removed or relabeled. [Six source-linked reviews]({score_source}/ambiguous-review.json). The [environment inventory]({score_source}/environment.json) was captured after evaluation, not as in-run telemetry.",
        f"**保留疑义。** {len(score_check['official_ambiguous_flags'])} 条官方 `no_tests_collected` 模糊标记仍保留为未解决。对应日志先收集了 92 项顶层测试，包含嵌套的零收集输出，并出现 `NameError: cached_eval`；没有暗中删除或改判。[六条来源复核]({score_source}/ambiguous-review.json)。[环境清单]({score_source}/environment.json)是在评分后采集，不冒充运行时遥测。"))
    parts.append(tr(chinese,
        f"**Evidence and replay.** [Facts]({source}/interim-facts.json), [export hashes and redactions]({source}/_export_manifest.json), [Opus]({source}/responses_opus.jsonl), [Sonnet]({source}/responses_sonnet.jsonl), [Haiku]({source}/responses_haiku.jsonl). The metrics-only projection omits prompt/answer bodies, thinking signatures, private endpoints and other headers; it is not a correctness-scoring dataset. Replay instructions are in [Testing]({'testing' if detailed else 'docs/testing'}{suffix}.md#aca-snapshot-replay).",
        f"**证据与复算。** [统计结果]({source}/interim-facts.json)、[导出哈希与脱敏范围]({source}/_export_manifest.json)、[Opus 记录]({source}/responses_opus.jsonl)、[Sonnet 记录]({source}/responses_sonnet.jsonl)、[Haiku 记录]({source}/responses_haiku.jsonl)。指标投影省略提示与回答正文、思考签名、私有端点和其他响应头，不能用于代码正确率评分。复算命令见[测试页]({'testing' if detailed else 'docs/testing'}{suffix}.md#aca-snapshot-replay)。"))
    return "\n\n".join(parts)


def gateway_snapshot_replay(chinese):
    return "\n\n".join([
        '<a id="aca-snapshot-replay"></a>',
        tr(chinese, "## Replay the complete ACA results", "## 复算 ACA 全量结果"),
        tr(chinese, "From the repository's project directory, use Python 3.12 or 3.13. This offline command sends no requests and needs no credentials:",
           "在仓库的本项目目录，用 Python 3.12 或 3.13 执行。下列离线命令不发送请求，也不需要凭据："),
        "```bash\npython -B gateway-cache/analyze_cache_matrix.py --run-dir evidence/gateway-cache-20261026 --out evidence/gateway-cache-20261026/interim-facts.json --check\npython -B gateway-cache/swebench_score.py check-public --out evidence/gateway-score-20261027 --inference-dir evidence/gateway-cache-20261026\n```",
          tr(chinese, "Expect `facts match`, then status PASS with denominator 624 and resolved 245, and exit 0. This replays saved metrics and official judgments; it does not generate new answers or rerun Docker. Cache-hit performance uses 302 pairs, while grading retains every measured answer.",
              "预期先输出 `facts match`，再输出 status PASS、denominator 624、resolved 245，退出码均为 0。这是在复算已保存指标与官方判定，不生成新答案、不重跑 Docker。缓存命中性能用 302 组配对，正确率保留每一份正式答案。"),
          tr(chinese, "### Run the official tests on the published patches", "### 对公开补丁重新执行官方测试"),
          tr(chinese,
              "On a Linux x86-64 machine with Docker access and sufficient disk for the 12 dataset images, run from this project directory. Use a new prefix to avoid reusing prior evaluation results. This executes the published model patches without generating new model answers; VM time and image storage may incur charges. The recorded setup used Python 3.12.3, two workers and a 1,800-second per-instance timeout.",
              "在可访问 Docker 的 Linux x86-64 机器上，从本项目目录执行；磁盘须能容纳数据集的 12 个镜像。新建 run_id 前缀，避免误用旧评分缓存。这会真实测试公开的模型补丁，不重新调用模型；机器运行和镜像存储可能计费。原评分使用 Python 3.12.3、2 个并发 worker，每题超时 1,800 秒。"),
          """```bash
python -m pip install 'git+https://github.com/SWE-bench/SWE-bench.git@02e7a74ffd0b707aab73d203fe87bdc7c76afc8e'
RUN_PREFIX="aca-regrade-$(date -u +%Y%m%d-%H%M%S)"
for prediction in evidence/gateway-score-20261027/predictions/*.jsonl; do
  label=$(basename "$prediction" .jsonl)
  python -u -m swebench.harness.run_evaluation \\
     --dataset_name evidence/gateway-score-20261027/dataset.json \\
     --predictions_path "$prediction" --max_workers 2 --timeout 1800 \\
     --run_id "$RUN_PREFIX-$label" || break
done
```""",
          tr(chinese,
              "Each of the 52 batches must produce `logs/evaluation/<run_id>/results.json`; inspect resolved, unresolved, empty-patch and error IDs, not just the CLI exit code. Patch-application failures are model-output outcomes; infrastructure failures require diagnosis and re-evaluating the same frozen patch. The published [official reports](../evidence/gateway-score-20261027/logs/evaluation) and [prediction hashes](../evidence/gateway-score-20261027/manifest.json) are the comparison reference. The public command blocks have not been replayed in a new machine during this documentation update.",
              "52 批各应生成 `logs/evaluation/<run_id>/results.json`。查看解决、未解决、空补丁和错误 ID，不能只看 CLI 退出码。补丁应用失败属于模型输出结果；基础设施失败应排查后复评同一份冻结补丁。对照[官方原始报告](../evidence/gateway-score-20261027/logs/evaluation)与[预测哈希](../evidence/gateway-score-20261027/manifest.json)。本次文档更新未在全新机器重跑这些公开命令。")])


def fresh_aca_analysis(chinese):
    manifest = read_json(ROOT / "evidence/gateway-score-20261027/manifest.json")
    revision = manifest["dataset"]["revision"]
    commit = manifest["official_source"]["commit"]
    return "\n\n".join([
        '<a id="fresh-aca-analysis"></a>',
        tr(chinese, "## Analyze and grade a new ACA run", "## 分析和评分新的 ACA 运行"),
        tr(chinese,
            "Follow the owning README for input preparation, the cache gate and collection. Its WORK, RUN and RUN_ID variables identify your new private directory. `analyze_cache_matrix.py --run-dir` reads that run's responses, including recorded retry attempts; it does not substitute published fixtures. A complete collection can still contain truncations or incorrect answers. The parameter records precede model-alias mapping and are not provider-wire traces.",
            "输入重建、缓存检查与采集按首页执行；WORK、RUN、RUN_ID 指向本次私有目录。`analyze_cache_matrix.py --run-dir` 读取该次响应及已记录重试，不回退到已发布快照。采集完整仍可能有截断和错误答案。参数记录在模型别名转换之前，不是 provider 出站抓包。"),
        tr(chinese,
            "**Separate outbound audit.** The gateway setup section's 50-request diagnostic uses `run_matrix.ps1` plus `scripts/analyze.py --run-directory --trace-file` to correlate each call. It is a different workload from the 650-request coding matrix. The coding analyzer does not perform that trace correlation; retain native gateway logs when collecting new performance results, and do not label this unimplemented audit as PASS.",
            "**出站审计单独进行。** 网关部署章节的 50 请求诊断使用 `run_matrix.ps1` 和 `scripts/analyze.py --run-directory --trace-file` 逐条关联调用。它与 650 请求编码矩阵是不同工作负载。编码矩阵分析器不执行该 trace 关联；新采集时保留原生网关日志，不能把尚未实现的关联审计标为通过。"),
        tr(chinese,
            "**Grade newly generated answers, not the public metrics projection.** On Linux x86-64 with Docker and space for the dataset images, reuse a compatible Python environment. This stage downloads official data/images and runs tests; it makes no model calls but consumes compute. The driver freezes the official evaluation dataset at prepare time. Before comparing with the published score, the following guard requires the same dataset revision. A mismatch requires a separately scoped evaluation, not a relabeled comparison.",
            "**评分新生成的答案，不使用公开指标投影。** 在可使用 Docker、磁盘足够容纳题目镜像的 Linux x86-64 环境中执行，复用兼容 Python 环境。本阶段会下载官方数据和镜像并运行测试，不调用模型，但消耗计算资源。驱动在 prepare 时冻结官方评分集；下方检查要求与已发布分数使用同一数据集版本。不一致时须另行限定评测范围，不能继续冒充同口径比较。"),
        "```bash\n" + f'''python -m pip install 'git+https://github.com/SWE-bench/SWE-bench.git@{commit}'
SCORE="$WORK/score"
python -B gateway-cache/swebench_score.py audit-input --run-dir "$RUN"
python -B gateway-cache/swebench_score.py prepare --run-dir "$RUN" \\
  --problems "$WORK/problems.json" --out "$SCORE" --evaluation-id "$RUN_ID"
python -c 'import json,sys; record=json.load(open(sys.argv[1], encoding="utf-8")); assert record["dataset"]["revision"] == "{revision}", "Evaluation dataset revision changed"' "$SCORE/manifest.json"
python -u gateway-cache/swebench_score.py run --out "$SCORE" --workers 2
python -B gateway-cache/swebench_score.py collect --out "$SCORE"
```''',
        tr(chinese,
            "Prepare must retain every measured answer and exclude only warm-ups. With the full protocol expect 624 answers and 52 batches; resolved counts are not predetermined. Read this SCORE's score-summary.json, scored-responses.json and native logs/evaluation reports. NOT_GRADED or EVALUATION_ERROR means incomplete evaluation, not an answer failure to silently discard. This command sequence was not rerun on fresh cloud compute during the documentation update.",
            "prepare 必须保留全部正式答案，只排除预热。完整协议应有 624 份答案、52 批，解决数没有预设值。读取本次 SCORE 的 score-summary.json、scored-responses.json 和 logs/evaluation 原生报告。NOT_GRADED 或 EVALUATION_ERROR 表示评分未完成，不能当成可静默删除的答案失败。本轮文档更新未在新云计算环境重跑这套命令。"),
    ])


def results(d, gateway, chinese):
    parts = [
        gateway_snapshot(chinese),
        tr(chinese,
           "**Historical results only.** The following direct-VM measurements belong to the retired method. In particular, the 21-cell coding matrix omitted `cache_control` and does not meet the current ACA cache-enabled protocol. The Japan East gateway check is separately dated. None of these numbers is a result from the current East US 2 ACA run.",
           "**以下仅为历史结果。** 下列 VM 直连测量属于已取缔的方案，尤其是 21 格编码矩阵未发送 `cache_control`，不满足当前 ACA 开启缓存的测试要求。Japan East 网关检查另列日期。这些数字都不是当前 East US 2 ACA 测试的结果。"),
        tr(chinese, "Words used in the results:", "看结果时会用到的词："), glossary(chinese),
        tr(chinese, "**Where each part ran.**", "**各部分在哪里运行。**"), where_table(d, chinese),
        request_block(d, chinese),
        tr(chinese, "**How each number is measured, and the scripts.**", "**每个指标怎么测、用哪个脚本。**"), timing_table(chinese),
        caution(d, chinese), grids(d, chinese), stands_out(d, chinese), caching(d, chinese),
        gateway_summary(gateway, chinese), runs_table(d, gateway, chinese), limits(d, chinese), navigation(chinese),
        directories(chinese),
    ]
    return "\n\n".join(parts)


# ---------- README: steps ----------

def gateway_steps(chinese):
    suffix = "_CN" if chinese else ""
    manifest = read_json(ROOT / "data/gateway-cache-problems.json")
    first_problem = manifest["problems"][0]["id"]
    return "\n\n".join([
        tr(chinese,
            "| Order | Execution location | Action and completion check |\n|---|---|---|\n"
            f"| 1 | Azure configuration workstation | Prepare Foundry and ACA LiteLLM; verify the active image and identities in [gateway setup](docs/testing{suffix}.md#gateway-setup) |\n"
            "| 2 | Linux measurement client | Install dependencies and rebuild the hash-checked input |\n"
            "| 3 | Same Linux client | Supply the HTTPS gateway origin and private key |\n"
            "| 4 | Same Linux client | Run one cache pair and check native write/read evidence |\n"
            "| 5 | Same Linux client | Run all frozen configurations into a new directory |\n"
            "| 6 | Same Linux client | Analyze that directory, retaining failures and missing requests |",
            "| 顺序 | 执行位置 | 操作与完成观察 |\n|---|---|---|\n"
            f"| 1 | Azure 配置工作机 | 准备 Foundry 和 ACA LiteLLM，按[网关部署](docs/testing{suffix}.md#gateway-setup)核对活动镜像与身份 |\n"
            "| 2 | Linux 测量客户端 | 安装依赖并重建通过哈希校验的输入 |\n"
            "| 3 | 同一 Linux 客户端 | 配置 HTTPS 网关地址，私下输入入口密钥 |\n"
            "| 4 | 同一 Linux 客户端 | 运行一组缓存对照，检查原生写入与读取 |\n"
            "| 5 | 同一 Linux 客户端 | 在新目录运行全部固定配置 |\n"
            "| 6 | 同一 Linux 客户端 | 分析该目录，保留失败与缺失请求 |"),
        tr(chinese,
            f"**Prerequisites and scope.** Use Bash on a Linux client with Python 3.12 or 3.13 and an existing ACA gateway. To reproduce the measured placement, use East US 2 for the client, gateway and Foundry resource; GlobalStandard still does not promise an inference region. Without a gateway, complete steps 1-4 of [gateway setup](docs/testing{suffix}.md#gateway-setup), then return here. Allow the measurement client's actual egress /32 in ingress restrictions; a separate configuration workstation needs its own allowed /32. The gateway uses managed identity for Foundry; the client uses only the gateway key. Model calls and infrastructure incur charges. These reorganized public command blocks have not been run on a fresh cloud environment in this update.",
            f"**前提与范围。** 在已有 Linux 客户端使用 Bash、Python 3.12 或 3.13，并准备好 ACA 网关。复现本次位置条件时，客户端、网关和 Foundry 资源均使用 East US 2；GlobalStandard 仍不承诺推理区域。还没有网关时，先完成[网关部署](docs/testing{suffix}.md#gateway-setup)第 1-4 步，再回到这里。Ingress 必须放行实际测量客户端的出口 /32；配置工作机不同时，单独放行它的 /32。调用 Foundry 的是网关托管身份，客户端只使用入口密钥。模型调用和基础设施会计费；本轮未在全新云环境执行这些重组后的公开命令。"),
        tr(chinese, "**1. Prepare the client and frozen input.** Start in the parent of your checkout. Reuse an existing compatible Python environment; the conditional creates one only when no environment is active and no local one exists.",
           "**1. 准备客户端和固定输入。** 从仓库工作副本的父目录开始。已有兼容 Python 环境就复用；下面仅在未激活环境且本地环境不存在时创建环境。"),
        r'''```bash
set -euo pipefail
test -d david-share || git clone --depth 1 --filter=blob:none https://github.com/david-xinyuwei/david-share.git
cd david-share/Agents/Claude-Foundry-LiteLLM-Performance
if [ -z "${VIRTUAL_ENV:-}" ]; then
  test -x .venv/bin/python || python3 -m venv .venv
  source .venv/bin/activate
fi
python -m pip install -r coding-matrix/requirements.txt pyarrow
RUN_ID="aca-$(date -u +%Y%m%d-%H%M%S)"
WORK="$PWD/private/$RUN_ID"
mkdir -p "$WORK"
python -B gateway-cache/build_swebench_problems.py \
  --manifest data/gateway-cache-problems.json --out "$WORK/problems.json"
```''',
        tr(chinese,
            f"Expect PASS, revision `{manifest['source']['revision']}` and {len(manifest['problems'])} problems. The builder checks the parquet, problem order, source commits and prompt hashes before writing the prepared JSON. A mismatch stops the run; do not substitute a newer dataset. The downloaded data and later responses stay under ignored `private/`.",
            f"预期 PASS、版本 `{manifest['source']['revision']}` 和 {len(manifest['problems'])} 道题。构建器在写出 JSON 前检查 parquet、题目顺序、源码提交及提示哈希。不一致就停止，不改用更新的数据集。下载数据及后续响应都保存在已忽略的 `private/` 下。"),
        tr(chinese, "**2. Configure the gateway, not the Foundry endpoint.** Get the HTTPS origin from Container Apps Ingress, without `/v1/messages` or `/anthropic`. Enter the key yourself; never put it in a command, screenshot or Git.",
           "**2. 配置网关，不填 Foundry 直连端点。** 从 Container Apps 的 Ingress 获取 HTTPS 源地址，不带 `/v1/messages` 或 `/anthropic`。密钥由使用者私下输入，不写进命令、截图或 Git。"),
        r'''```bash
export GATEWAY_URL="https://<your-container-app-fqdn>"
read -r -s -p 'Gateway key (private): ' CLAUDE_GATEWAY_KEY
printf '\n'
export CLAUDE_GATEWAY_KEY
export CLAUDE_GATEWAY_BUDGET_ROOT="$WORK"
```''',
        tr(chinese,
            "Aliases are `opus55-standard`, `sonnet55-standard` and `haiku55-standard` in `deploy/config.yaml`; the existing gateway adapter maps the runner's model names to them. No direct-Foundry fallback is used. Configure matching aliases before continuing.",
            "`deploy/config.yaml` 中的别名为 `opus55-standard`、`sonnet55-standard`、`haiku55-standard`，现有网关适配器将运行器模型名映射到这些别名；不会兜底直连 Foundry。别名不一致时先修正配置。"),
        tr(chinese,
            "**3. Verify one cache pair first.** This diagnostic plans one warm-up plus two measured requests. Its seed is separate from the full run, so it does not prewarm the full run's group prefix. Approve its model spend before executing.",
            "**3. 先验证一组缓存对照。** 此诊断计划一次预热及两次正式请求。它使用独立种子，不给后续全矩阵的组前缀预热。执行前确认本步骤的模型费用。"),
        "```bash\n" + f'''GATE="$WORK/gate"
python -u gateway-cache/aca_cache_matrix.py --run-dir "$GATE" \\
  --source coding-matrix --gateway-url "$GATEWAY_URL" --problems "$WORK/problems.json" \\
  --probe-summary evidence/coding-matrix-20261026/matrix/probe_summary.json \\
  --only-cells 'sonnet|adaptive|low' --only-problems '{first_problem}' \\
  --seed "$RUN_ID-gate" --repeats 2 --max-tokens 128000 --ttl 1h --budget-usd 5
python -B gateway-cache/analyze_cache_matrix.py --run-dir "$GATE" --out "$GATE/facts.json"
python -c 'import json,sys; record=json.load(open(sys.argv[1], encoding="utf-8")); assert record["coverage"]["collection_complete"] and record["cache_hit_pairs"] == 1, record; print("CACHE_PAIR_VERIFIED")' "$GATE/facts.json"
```''',
        tr(chinese,
            "Expect CACHE_PAIR_VERIFIED, two completed measured answers and native cache read after write. HTTP 200 alone is not enough. For 401/403 check the gateway key, ingress and gateway identity; for 400 inspect the actual parameter error; for 429 inspect the returned limit and pacing; for missing reads inspect the prefix, elapsed gap and route. A TCP check below 50 ms is only this runner's heuristic, not proof of location. Keep failures and their request identifiers.",
            "预期 CACHE_PAIR_VERIFIED、两份完整正式回答，以及先写后读的原生缓存证据。HTTP 200 不够。401/403 检查入口密钥、Ingress 和网关身份；400 看实际参数错误；429 看返回的限流维度与发送节奏；没有读取时检查前缀、间隔和路由。运行器的 TCP 低于 50 毫秒检查只是启发式条件，不证明地域。失败和请求标识都要保留。"),
        tr(chinese,
            "**4. Run and analyze the full matrix.** Use the same shell and a new directory. The frozen probe fixes 26 configurations, 12 problems and two measured repeats, plus warm-ups: 650 planned requests. A new seed changes ordering and group identifiers while preserving the protocol and problem texts; results need not equal the published run. The example's USD 85 stop threshold is not a guaranteed cost cap because calls can be in flight. The adapter also stops at USD 95 accounted under WORK, reserving USD 5 of its USD 100 guard; check current prices before choosing budgets.",
            "**4. 运行并分析全矩阵。** 仍在同一终端，新建运行目录。冻结的探测清单固定 26 种配置、12 道题、两次正式重复及预热，共 650 个计划请求。新种子改变顺序和组标识，协议与题目正文不变；不要求数字等于已发布结果。示例的 85 美元是停止阈值，不是严格费用上限，因为可能有在途请求。适配器另对 WORK 下已计费用设置 95 美元停止阈值、预留 5 美元，合计 100 美元保护；选择预算前须查当前价格。"),
        r'''```bash
RUN="$WORK/matrix"
printf 'RUN_DIRECTORY=%s\n' "$RUN"
python -u gateway-cache/aca_cache_matrix.py --run-dir "$RUN" \
  --source coding-matrix --gateway-url "$GATEWAY_URL" --problems "$WORK/problems.json" \
  --probe-summary evidence/coding-matrix-20261026/matrix/probe_summary.json \
  --seed "$RUN_ID" --repeats 2 --max-tokens 128000 --ttl 1h --budget-usd 85
python -B gateway-cache/analyze_cache_matrix.py --run-dir "$RUN" --out "$RUN/facts.json"
python -B gateway-cache/analyze_cache_matrix.py --run-dir "$RUN" --out "$RUN/facts.json" --check
unset CLAUDE_GATEWAY_KEY
```''',
        tr(chinese,
            f"The analyzer reads this RUN, not the published fixture. Expect `facts match`; separately check `coverage.collection_complete`, all 26 cells, transport errors, truncations and native cache pairs in facts.json. BUDGET_STOP or missing requests is not completion. The foreground process can be interrupted with Ctrl+C; this does not stop cloud resources. Use the printed directory in another terminal for `tail -F <run-directory>/progress.log`, or read its run.json for a snapshot. Keep the same inputs, seed and run directory when resuming; first re-enter the private key. [New-answer grading and separate outbound audit](docs/testing{suffix}.md#fresh-aca-analysis) are separate stages, not covered by `facts match`.",
            f"分析器读取本次 RUN，不读取已发布快照。预期 `facts match`；还须检查 facts.json 的 `coverage.collection_complete`、全部 26 格、传输错误、截断和原生缓存配对。BUDGET_STOP 或缺请求不算完成。前台进程可用 Ctrl+C 中断，这不会停止云资源。另开终端，用已输出目录运行 `tail -F <run-directory>/progress.log` 持续查看，或读取该目录的 run.json 看快照。续跑必须保留输入、种子和原运行目录，并先重新私下输入密钥。[新答案评分与独立出站审计](docs/testing{suffix}.md#fresh-aca-analysis)是另外的阶段，不由 `facts match` 覆盖。"),
        tr(chinese,
            f"**Only inspecting saved results?** Use [offline replay](docs/testing{suffix}.md#aca-snapshot-replay); it needs no Azure credentials or model calls. Deployment, input reconstruction, fresh collection and offline replay have distinct acceptance checks.",
            f"**只想核对已有结果？** 使用[离线复算](docs/testing{suffix}.md#aca-snapshot-replay)，无需 Azure 凭据或模型调用。部署、重建输入、新采集和离线复算的验收分别记录。"),
    ])


def steps(d, chinese, historical=False):
    if not historical:
        return gateway_steps(chinese)
    suffix = "_CN" if chinese else ""
    step4 = read_json(EV / "readme-step4.json")
    result = step4["stderr_result"]
    require(step4["exit_code"] == 0 and result["status"] == "completed", "README step 4 check did not pass")
    sample = f'{{"status": "completed", "http_status": {result["http_status"]}, "first_text_s": {result["first_text_s"]}, ...}}'
    blocks = [
        tr(chinese,
              "**Current test entry.** New tests use the [ACA cache runner](gateway-cache/aca_cache_matrix.py) and its [launcher](gateway-cache/run.sh), with the [12-problem manifest](data/gateway-cache-problems.json). Requests go from the VM client through the gateway, with `cache_control` enabled; do not use the old direct-VM client for the current test.",
              "**当前测试入口。** 新测试使用 [ACA 缓存运行器](gateway-cache/aca_cache_matrix.py)及其[启动脚本](gateway-cache/run.sh)，输入为 [12 道题清单](data/gateway-cache-problems.json)。VM 客户端通过网关发送请求，并开启 `cache_control`；当前测试不使用旧直连客户端。"),
          tr(chinese,
              f"**Retired direct-VM procedure: reference only.** The commands below document how the historical evidence was produced. They are not the current deployment or test instructions and must not be used for a new run under the ACA protocol. Historical procedures and offline evidence checks remain in [docs/testing.md](docs/testing{suffix}.md).",
              f"**已取缔的 VM 直连流程，仅供历史参考。** 以下命令记录旧证据的产生方式，不是当前部署或测试步骤，不能用于按 ACA 协议开展的新测试。历史流程和离线证据检查保留在 [docs/testing_CN.md](docs/testing{suffix}.md)。"),
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
    """Current gateway test topology, with planned workload separate from measured results."""
    spec = read_json(ROOT / "data/gateway-cache-problems.json")
    n_problems = len(spec["problems"])
    cells = sum(status == 200 for row in support_matrix_rows(d) for status in row["efforts"].values())
    repeats = 2
    measured = cells * n_problems * repeats
    planned = measured + cells
    require({item["sku"] for item in d["provenance"]["models"]["deployments"]} == {"GlobalStandard"},
            "Global PAYGO labels require GlobalStandard deployments")
    model_labels = [f"{NAME[model]} · Global PAYGO" for model in MODELS]
    ledger = read_json(ROOT / "images/icon-sources.json")
    icons = {}
    for item in ledger["icons"]:
        path = ROOT / item["file"]
        require(hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], "Icon changed: " + item["file"])
        icons[path.name] = base64.b64encode(path.read_bytes()).decode()

    ink, body, accent, muted = "#1b1b1b", "#242424", "#0078d4", "#605e5c"
    font = "'Segoe UI', 'Microsoft YaHei', sans-serif"
    out = []

    def text(x, y, content, size=16, fill=body, weight=400, max_width=1120):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
                   f'data-max-width="{max_width}">{html.escape(content, quote=False)}</text>')

    def icon(name, x, y, size):
        out.append(f'<image x="{x}" y="{y}" width="{size}" height="{size}" href="data:image/svg+xml;base64,{icons[name]}"/>')

    def t(en, cn):
        return tr(chinese, en, cn)

    title = t("Current test: client → ACA LiteLLM → Foundry", "当前测试：客户端 → ACA LiteLLM → Foundry")
    text(32, 44, title, 30, ink, 600)
    text(32, 76, t("Cache-enabled gateway run; planned request counts are not completed results.",
                   "开启提示缓存的网关测试；计划请求数不是已完成结果。"), 17, muted)
    out.append(f'<rect x="32" y="102" width="1136" height="328" rx="8" fill="none" '
               f'stroke="{accent}" stroke-width="2" stroke-dasharray="8 5"/>')
    text(52, 128, t("Client, gateway and Foundry resource: East US 2", "客户端、网关与 Foundry 资源入口：East US 2"),
         18, accent, 600)
    nodes = [
        (52, "#f3f2f1", "10021-icon-service-Virtual-Machine.svg", "Linux VM", [
            t("Request client only", "仅作为请求客户端"), "Python + httpx",
            t("Gateway key to call ACA", "使用网关入口密钥调用 ACA"),
            t("Streaming Messages requests", "发送流式 Messages 请求"),
            t("1 in-flight request per model", "每个模型同时 1 个请求"),
            t("Times first text and stream end", "记录首字与流结束时间"),
        ]),
        (460, "#eaf4fb", "02989-icon-service-Container-Apps-Environments.svg", "ACA / LiteLLM", [
            "Azure Container Apps", "East US 2",
            t("Fixed aliases for 3 models", "三个模型的固定别名映射"),
            "stream / thinking / effort", "cache_control",
            t("Managed identity to Foundry", "以托管身份调用 Foundry"),
        ]),
        (868, "#eef6ee", "036509415-icon-service-Foundry-Project.svg", "Microsoft Foundry", [
            t("Global Standard · pay-as-you-go", "Global Standard · 按量付费"), *model_labels,
            t("Prompt cache is on this side", "提示缓存在服务端这一侧"),
            t("Native usage: cache reads/writes", "原生 usage：缓存读取／写入"),
        ]),
    ]
    for x_pos, fill, icon_name, heading, lines in nodes:
        out.append(f'<rect x="{x_pos}" y="148" width="280" height="258" rx="8" fill="{fill}" stroke="#c8c6c4"/>')
        icon(icon_name, x_pos + 14, 162, 28)
        text(x_pos + 52, 184, heading, 20, accent, 600, 216)
        for index, line in enumerate(lines):
            y_pos = 222 + index * 30
            if line in model_labels:
                out.append(f'<circle cx="{x_pos + 19}" cy="{y_pos - 5}" r="3" fill="{accent}" data-model-bullet="true"/>')
                text(x_pos + 30, y_pos, line, 16, max_width=234)
            else:
                text(x_pos + 16, y_pos, line, 16, max_width=248)
    for start, end in ((332, 460), (740, 868)):
        text(start + 24, 246, "HTTPS", 16, accent, 600, 100)
        text(start + 12, 271, "/v1/messages", 14, muted, max_width=108)
        out.append(f'<path d="M{start + 8} 290 H{end - 15}" stroke="{accent}" stroke-width="2.2" fill="none"/>')
        out.append(f'<polygon points="{end - 6},290 {end - 16},284 {end - 16},296" fill="{accent}"/>')
        out.append(f'<path d="M{end - 8} 324 H{start + 15}" stroke="{accent}" stroke-width="1.5" fill="none"/>')
        out.append(f'<polygon points="{start + 6},324 {start + 16},319 {start + 16},329" fill="{accent}"/>')
        text(start + 20, 350, t("SSE stream", "SSE 返回"), 14, muted, max_width=104)
    columns = [
        (32, t("Inputs and combinations", "输入与组合"), [
            t(f"{n_problems} long SWE-bench Lite prompts", f"{n_problems} 道 SWE-bench Lite 长题"),
            t(f"{cells} mode/effort cells, defaults included", f"{cells} 个模式／档位组合，含不传档位"),
            t("Request 1 writes; identical request 2 reads", "第 1 次写入；第 2 次原样发送并读缓存"),
            t(f"Plan: {measured} measured + {cells} warm-ups", f"计划：{measured} 次正式请求＋{cells} 次预热"),
            t(f"{planned} requests; public prompts, not customer data", f"共 {planned} 次；公开题目，不是客户数据"),
        ]),
        (432, t("Request controls", "请求参数"), [
            "max_tokens: 128000; stream: true", "thinking.type / output_config.effort",
            'cache_control: {"type": "ephemeral",', '"ttl": "1h"}',
            t("Cache reads verified from native usage", "用原生 usage 确认真实缓存读取"),
        ]),
        (832, t("Observations and limits", "观察与结果边界"), [
            t("First visible text; end-to-end duration", "首个可见文本、完整回答耗时"),
            t("Tokens/s and native cache-read share", "tokens/s 与原生缓存读取占比"),
            t("Cost: actual tokens × list price", "费用：实际 token 数 × 标价"),
            t("Correctness needs separate evaluation", "正确率须另行评分后报告"),
            t("HTTP 200 alone does not prove a cache hit", "不能以 HTTP 200 代替缓存命中"),
        ]),
    ]
    for x_pos, heading, lines in columns:
        text(x_pos, 472, heading, 20, accent, 600, 350)
        for index, line in enumerate(lines):
            text(x_pos, 506 + index * 28, line, 15.5, max_width=350)
    text(32, 680, t("Global PAYGO = Global Standard, billed per token; resource location does not fix the inference region.",
                    "Global PAYGO：Global Standard 按 token 计费；资源在美东二不代表推理固定在美东二。"), 15.5, muted)
    text(32, 709, t("Historical direct-VM and Japan East gateway results remain separately labeled; they are not results from this run.",
                    "历史 VM 直连及 Japan East 网关结果仍单独标注；不能当作本轮新结果。"), 15.5, muted)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="740" viewBox="0 0 1200 740" '
            f'role="img" aria-label="{html.escape(title)}">\n'
            '<rect width="1200" height="740" fill="#FFFFFF"/>\n'
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
                  "**Retired method: historical evidence only.** This section records the direct-VM coding matrix without `cache_control`. It does not satisfy the current cache-enabled ACA protocol and is not a result from that run. The raw records and their original values are retained unchanged.",
                  "**已取缔的方案，仅保留历史证据。** 本节记录未带 `cache_control` 的 VM 直连编码矩阵，不满足当前开启缓存的 ACA 测试要求，也不是该轮测试的结果。原始记录和数值保持不变。"))
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
        tr(chinese,
           "**Windows first.** The official SWE-bench reports under `evidence/gateway-score-20261027/logs/` have paths longer than 260 characters. Enable long paths before cloning, or the checkout is incomplete and `check-public` fails: `git clone -c core.longpaths=true https://github.com/david-xinyuwei/david-share.git`, or `git config --global core.longpaths true` once. CI sets the same option; Linux and macOS need nothing.",
           "**Windows 先做一步。** `evidence/gateway-score-20261027/logs/` 下官方 SWE-bench 报告的路径超过 260 个字符。克隆前先启用长路径，否则检出不完整、`check-public` 会失败：`git clone -c core.longpaths=true https://github.com/david-xinyuwei/david-share.git`，或一次性执行 `git config --global core.longpaths true`。CI 设了同样的选项；Linux 和 macOS 不需要。"),
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
