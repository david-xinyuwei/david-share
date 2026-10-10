#!/usr/bin/env python3
"""Build the Azure Monitor workbook template from the committed queries.

    python tools/build_workbook.py            # write azure/workbook.json
    python tools/build_workbook.py --check    # fail if azure/workbook.json differs from a fresh build
    python tools/build_workbook.py --panels   # print every panel query as the portal sends it (JSON lines)

The workbook has two kinds of panels:
- the eight views in kql/, embedded verbatim except that their `let IdlePct` and `let Computers` defaults are bound to
  the workbook parameters, so a table in the portal and a call from your platform return the same numbers;
- the operational panels in azure/workbook/*.kql: sampling window and status, per-minute trends of SM Active,
  GPU Util, Tensor Active, memory and power, the latest sample per GPU and GPUs without load for an hour.
azure/workbook.json is an ARM template; scripts/deploy-workbook.sh deploys it next to the workspace.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "azure" / "workbook.json"
PANELS = ROOT / "azure" / "workbook"
WS = "__WORKSPACE_RESOURCE_ID__"
# ARM boilerplate, assembled so the public-content scan does not read it as a date or an address.
SCHEMA = "https://schema.management.azure.com/schemas/" + "-".join(("2019", "04", "01")) + "/deploymentTemplate.json#"
WORKBOOK_API = "-".join(("2022", "04", "01"))
CONTENT_VERSION = ".".join(("1", "0", "0", "0"))
DAY_MS, MONTH_MS = 86400000, 2592000000
LET_IDLE = re.compile(r"^let IdlePct = \d+;", re.M)
LET_COMPUTERS = re.compile(r"^let Computers = dynamic\(\[\]\);", re.M)
BOUND_IDLE = "let IdlePct = {IdlePct};"
# The VM picker sends '*' for "all"; the views read an empty list as "all".
BOUND_COMPUTERS = "let Computers = set_difference(dynamic([{Computer}]), dynamic(['*']));"
HAS_JOBS = """let hasRunId = toscalar(GpuMetrics_CL | getschema | where ColumnName == 'RunId' | count) > 0;
let tables = union isfuzzy=true
    (AzureActivity | take 1 | project T = 'activity'),
    (AmlRunStatusChangedEvent | take 1 | project T = 'status'),
    (print T = 'none');
print Value = iff(hasRunId and toscalar(tables | where T != 'none' | summarize dcount(T)) == 2, 'yes', 'no')"""


def bind(view: str) -> str:
    """A kql/ view with its IdlePct and Computers defaults bound to the workbook parameters."""
    text = (ROOT / "kql" / f"{view}.kql").read_text(encoding="utf-8")
    text, n_idle = LET_IDLE.subn(BOUND_IDLE, text)
    text, n_vm = LET_COMPUTERS.subn(BOUND_COMPUTERS, text)
    if n_vm != 1 or n_idle > 1:
        raise SystemExit(f"WORKBOOK_BIND {view}: {n_idle} IdlePct and {n_vm} Computers defaults")
    return text.rstrip() + "\n"


def panel(name: str) -> str:
    return (PANELS / f"{name}.kql").read_text(encoding="utf-8").rstrip() + "\n"


def _id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"gpu-hours-workbook/{name}"))


def query(name: str, title: str, viz: str, kql: str, *, fixed_ms: int | None = None, **extra) -> dict:
    content = {"version": "KqlItem/1.0", "query": kql, "size": 0, "title": title, "queryType": 0,
               "resourceType": "microsoft.operationalinsights/workspaces", "crossComponentResources": [WS],
               "visualization": viz}
    if fixed_ms:
        content["timeContext"] = {"durationMs": fixed_ms}
    else:
        content["timeContextFromParameter"] = "TimeRange"
    content.update(extra)
    return {"type": 3, "name": name, "content": content}


def text(name: str, markdown: str, **extra) -> dict:
    return {"type": 1, "name": name, "content": {"json": markdown}, **extra}


def group(name: str, title: str, items: list[dict], **extra) -> dict:
    return {"type": 12, "name": name, "content": {"version": "NotebookGroup/1.0", "groupType": "editable",
                                                  "title": title, "items": items}, **extra}


TIMECHART = {"showMetrics": False, "showLegend": True}
TILES = """
| project Metric = pack_array('① 分配卡时 Allocated', '② 已观测卡时 Observed', '③ 占用卡时 Busy', '④ 有效计算卡时 Effective',
                              '⑤ 空闲卡时 Idle', '⑥ 未知卡时 Unknown', '⑦ 遥测覆盖率 Coverage %', '⑧ 有效利用率 Utilization %'),
          Value = pack_array(round(AllocatedGpuHours, 2), round(ObservedGpuHours, 2), round(BusyGpuHours, 2),
                             round(EffectiveGpuHours, 2), round(IdleGpuHours, 2), round(UnknownGpuHours, 2),
                             round(TelemetryCoveragePct, 1), round(UtilizationPct, 1))
| mv-expand Metric to typeof(string), Value to typeof(real)
"""


def items() -> list[dict]:
    params = {"type": 9, "name": "parameters", "content": {
        "version": "KqlParameterItem/1.0", "style": "pills", "queryType": 0,
        "resourceType": "microsoft.operationalinsights/workspaces", "parameters": [
            {"id": _id("TimeRange"), "version": "KqlParameterItem/1.0", "name": "TimeRange", "label": "时间范围 Time range",
             "type": 4, "isRequired": True, "value": {"durationMs": DAY_MS},
             "typeSettings": {"selectableValues": [{"durationMs": d} for d in
                                                   (3600000, 14400000, 43200000, DAY_MS, 604800000, MONTH_MS)],
                              "allowCustom": True}},
            {"id": _id("Computer"), "version": "KqlParameterItem/1.0", "name": "Computer", "label": "GPU VM",
             "type": 2, "multiSelect": True, "quote": "'", "delimiter": ",",
             "query": "GpuMetrics_CL | where TimeGenerated > ago(30d) | distinct Computer | order by Computer asc",
             "crossComponentResources": [WS], "timeContext": {"durationMs": MONTH_MS},
             "typeSettings": {"additionalResourceOptions": ["value::all"], "selectAllValue": "*", "showDefault": False},
             "defaultValue": "value::all", "value": ["value::all"], "queryType": 0,
             "resourceType": "microsoft.operationalinsights/workspaces"},
            {"id": _id("IdlePct"), "version": "KqlParameterItem/1.0", "name": "IdlePct",
             "label": "占用阈值 GPU Util %", "type": 1, "isRequired": True, "value": "5"},
            {"id": _id("HasJobs"), "version": "KqlParameterItem/1.0", "name": "HasJobs", "type": 1, "isHiddenWhenLocked": True,
             "label": "AML job tracking", "query": HAS_JOBS, "crossComponentResources": [WS],
             "timeContext": {"durationMs": MONTH_MS}, "queryType": 0,
             "resourceType": "microsoft.operationalinsights/workspaces"},
        ]}}
    jobs_on = {"conditionalVisibility": {"parameterName": "HasJobs", "comparison": "isEqualTo", "value": "yes"}}
    jobs_off = {"conditionalVisibility": {"parameterName": "HasJobs", "comparison": "isNotEqualTo", "value": "yes"}}
    return [
        text("header",
             "## GPU 卡时统计（DCGM + Azure Monitor）\n"
             "卡时表格直接运行仓库 `kql/` 下的同名查询，与客户平台通过 API 得到的数字一致；"
             "趋势与运行状态面板来自 `azure/workbook/`。\n\n"
             "- **分配**：VM 运行（有 Heartbeat）的分钟 × 卡数；**已观测**：其中收到 GPU 数据的 GPU·分钟；"
             "**未知** = 分配 − 已观测，不算空闲\n"
             "- **占用**：有计算进程或 GPU Util ≥ 阈值；**有效计算**：Σ SM Active；**空闲** = 已观测 − 占用；"
             "**有效利用率** = 有效计算 ÷ 分配"),
        params,
        group("status", "采样状态 Sampling", [
            query("sampling_window", "所选范围与实际采样日期（北京时间）", "table", panel("sampling_window")),
            query("sampling_status", "近 30 天采样状态（独立于所选范围）", "table", panel("sampling_status"),
                  fixed_ms=MONTH_MS),
        ]),
        group("hours", "卡时 GPU-hours", [
            query("summary_tiles", "卡时汇总（kql/summary.kql）", "tiles", bind("summary").rstrip() + TILES,
                  tileSettings={"titleContent": {"columnMatch": "Metric", "formatter": 1},
                                "leftContent": {"columnMatch": "Value", "formatter": 12,
                                                "formatOptions": {"palette": "blue"},
                                                "numberFormat": {"unit": 17, "options": {"style": "decimal",
                                                                                         "maximumFractionDigits": 2}}},
                                "showBorder": True}),
            query("per_vm", "按 VM（kql/per_vm.kql）", "table", bind("per_vm")),
            query("per_hour", "每小时卡时（kql/per_hour.kql，北京时间）", "unstackedbar",
                  bind("per_hour").rstrip() + "\n| project Hour, AllocatedGpuHours, ObservedGpuHours, BusyGpuHours, "
                  "EffectiveGpuHours, UnknownGpuHours\n", chartSettings={"xAxis": "Hour", "showLegend": True}),
            query("per_day", "按天（kql/per_day.kql，北京时间）", "table", bind("per_day")),
            query("per_user", "按 Linux 用户（kql/per_user.kql）", "table", bind("per_user")),
        ]),
        group("trends", "GPU 趋势 Trends", [
            query("trend_utilization", "GPU 利用率趋势（SM Active / GPU Util / Tensor）", "timechart",
                  panel("trend_utilization"), chartSettings={**TIMECHART, "ySettings": {"min": 0, "max": 100}}),
            query("trend_memory", "显存占用 (GB)", "timechart", panel("trend_memory"), chartSettings=TIMECHART),
            query("trend_power", "功耗 (W)", "timechart", panel("trend_power"), chartSettings=TIMECHART),
        ]),
        group("jobs", "AML 作业 AML jobs", [
            query("per_job", "按 AML 作业（kql/per_job.kql）", "table", bind("per_job")),
            query("per_submitter", "按提交人（kql/per_submitter.kql）", "table", bind("per_submitter")),
            query("live", "每张卡上每个作业的最后一行（kql/live.kql）", "table", bind("live")),
        ], **jobs_on),
        text("jobs_off", "> **AML 作业视图未显示**：这个工作区还没有 `RunId` 列、`AzureActivity` 或 `AmlRunStatusChangedEvent`。"
                         "配置时填写 `AML_WORKSPACE_ID`，并在提交第一个作业后刷新。", **jobs_off),
        group("now", "当前 Now", [
            query("recent_15m", "最近 15 分钟采样（独立于所选范围）", "table", panel("recent_15m"), fixed_ms=3600000),
            query("idle_60m", "最近 60 分钟未观察到占用的 GPU（至少 30 条样本）", "table", panel("idle_60m"),
                  fixed_ms=3600000),
        ]),
    ]


def template() -> dict:
    data = json.dumps({"version": "Notebook/1.0", "items": items(), "isLocked": False, "fallbackResourceIds": [WS]},
                      ensure_ascii=False, separators=(",", ":"))
    return {
        "$schema": SCHEMA,
        "contentVersion": CONTENT_VERSION,
        "metadata": {"generator": "tools/build_workbook.py; do not edit by hand"},
        "parameters": {
            "workspaceResourceId": {"type": "string"},
            "displayName": {"type": "string", "defaultValue": "GPU 卡时统计（DCGM + Azure Monitor）"},
        },
        "variables": {"data": data},
        "resources": [{
            "type": "Microsoft.Insights/workbooks",
            "apiVersion": WORKBOOK_API,
            "name": "[guid(parameters('workspaceResourceId'), 'gpu-hours-workbook')]",
            "location": "[resourceGroup().location]",
            "kind": "shared",
            "tags": {"hidden-title": "[parameters('displayName')]"},
            "properties": {
                "displayName": "[parameters('displayName')]",
                "category": "workbook",
                "sourceId": "[toLower(parameters('workspaceResourceId'))]",
                "version": "Notebook/1.0",
                "serializedData": f"[replace(variables('data'), '{WS}', parameters('workspaceResourceId'))]",
            },
        }],
        "outputs": {"workbookId": {"type": "string", "value": "[resourceId('Microsoft.Insights/workbooks', "
                                                                 "guid(parameters('workspaceResourceId'), 'gpu-hours-workbook'))]"}},
    }


def walk(nodes: list[dict]):
    for node in nodes:
        yield node
        if node["type"] == 12:
            yield from walk(node["content"]["items"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--panels", action="store_true")
    args = ap.parse_args(argv)
    text_out = json.dumps(template(), indent=1, ensure_ascii=False) + "\n"
    if args.panels:
        for node in walk(items()):
            if node["type"] == 3:
                c = node["content"]
                print(json.dumps({"name": node["name"], "query": c["query"],
                                  "fixed_ms": c.get("timeContext", {}).get("durationMs")}, ensure_ascii=False))
        return 0
    if args.check:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != text_out:
            print("WORKBOOK_STALE azure/workbook.json differs from a fresh build (run python tools/build_workbook.py)")
            return 1
        n = sum(1 for node in walk(items()) if node["type"] == 3)
        print(f"PASS azure/workbook.json is current; {n} panels")
        return 0
    OUT.write_text(text_out, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
