"""Generate the Azure Monitor Workbook + idle-GPU alert as an ARM template.

Run:  python build_workbook.py
Writes (next to this file):
  workbook.json             ARM template: Microsoft.Insights/workbooks + scheduledQueryRules
  workbook.parameters.json  serializedData parameter (the workbook body)
  workbook.gallery.json     raw workbook JSON, importable via Portal > Workbooks > Advanced Editor
  queries.kql               the same KQL, ready for Log Analytics Query API / platform integration

Labels are Chinese because the first customer is Chinese; the KQL column aliases are the
only place they live, so translating is a find-and-replace in this file.
"""
import json
import pathlib
import uuid

HERE = pathlib.Path(__file__).parent

# Common KQL building blocks. {TimeRange} / {Computer} / {IdlePct} are workbook parameters.
FILTER = "| where '*' in ({Computer}) or Computer in ({Computer})"
BASE = f"""let gpu = GpuMetrics_CL
| where TimeGenerated {{TimeRange}}
{FILTER};
let gpuCount = gpu | summarize Gpus = dcount(GpuId) by Computer;
let alloc = Heartbeat
| where TimeGenerated {{TimeRange}}
| where Computer in ((gpuCount | project Computer))
| summarize RunMinutes = dcount(bin(TimeGenerated, 1m)) by Computer
| join kind=inner gpuCount on Computer
| extend AllocGpuHours = RunMinutes * Gpus / 60.0;
let used = gpu
| summarize BusyGpuHours = countif(ProcCount > 0 or GpuUtil >= {{IdlePct}}) / 60.0,
            EffGpuHours  = sum(coalesce(SmActive, 0.0)) / 60.0,
            UtilGpuHours = sum(coalesce(GpuUtil, 0.0) / 100.0) / 60.0
          by Computer;
"""

SUMMARY_TILES = BASE + """alloc
| join kind=leftouter used on Computer
| summarize Alloc = sum(AllocGpuHours), Busy = sum(BusyGpuHours), Eff = sum(EffGpuHours)
| extend Idle = max_of(Alloc - Busy, 0.0), UtilPct = iff(Alloc > 0, 100.0 * Eff / Alloc, 0.0)
| project Metric = pack_array('① 分配卡时 (GPU-h)', '② 占用卡时 (GPU-h)', '③ 有效计算卡时 (SM加权, GPU-h)', '④ 空闲卡时 (GPU-h)', '⑤ 有效利用率 %'),
          Value = pack_array(round(Alloc, 2), round(Busy, 2), round(Eff, 2), round(Idle, 2), round(UtilPct, 1))
| mv-expand Metric to typeof(string), Value to typeof(real)
"""

PER_VM = BASE + """alloc
| join kind=leftouter used on Computer
| extend BusyGpuHours = coalesce(BusyGpuHours, 0.0), EffGpuHours = coalesce(EffGpuHours, 0.0)
| extend IdleGpuHours = max_of(AllocGpuHours - BusyGpuHours, 0.0),
         UtilPct = iff(AllocGpuHours > 0, 100.0 * EffGpuHours / AllocGpuHours, 0.0)
| project Computer, Gpus, RunHours = round(RunMinutes / 60.0, 2),
          ['分配卡时'] = round(AllocGpuHours, 2), ['占用卡时'] = round(BusyGpuHours, 2),
          ['有效计算卡时'] = round(EffGpuHours, 2), ['空闲卡时'] = round(IdleGpuHours, 2),
          ['有效利用率%'] = round(UtilPct, 1)
| order by ['分配卡时'] desc
"""

DAILY = f"""let gpu = GpuMetrics_CL
| where TimeGenerated {{TimeRange}}
{FILTER};
let gpuCount = gpu | summarize Gpus = dcount(GpuId) by Computer;
let alloc = Heartbeat
| where TimeGenerated {{TimeRange}}
| where Computer in ((gpuCount | project Computer))
| summarize RunMinutes = dcount(bin(TimeGenerated, 1m)) by Computer, Day = startofday(TimeGenerated)
| join kind=inner gpuCount on Computer
| project Day, Computer, AllocGpuHours = RunMinutes * Gpus / 60.0;
let used = gpu
| summarize BusyGpuHours = countif(ProcCount > 0 or GpuUtil >= {{IdlePct}}) / 60.0,
            EffGpuHours = sum(coalesce(SmActive, 0.0)) / 60.0
          by Computer, Day = startofday(TimeGenerated);
alloc
| join kind=leftouter used on Computer, Day
| project Day, Computer, ['分配卡时'] = round(AllocGpuHours, 2), ['占用卡时'] = round(coalesce(BusyGpuHours, 0.0), 2),
          ['有效计算卡时'] = round(coalesce(EffGpuHours, 0.0), 2),
          ['有效利用率%'] = round(iff(AllocGpuHours > 0, 100.0 * coalesce(EffGpuHours, 0.0) / AllocGpuHours, 0.0), 1)
| order by Day desc, Computer asc
"""

BY_USER = f"""GpuMetrics_CL
| where TimeGenerated {{TimeRange}}
{FILTER}
| where isnotempty(Users)
| mv-expand User = split(Users, ',') to typeof(string)
| summarize ['占用卡时'] = round(count() / 60.0, 2),
            ['有效计算卡时'] = round(sum(coalesce(SmActive, 0.0)) / 60.0, 2),
            ['平均SM Active%'] = round(100.0 * avg(SmActive), 1),
            ['峰值显存GB'] = round(max(FbUsedMiB) / 1024.0, 1),
            Processes = make_set(Processes, 10)
          by User, Computer
| order by ['占用卡时'] desc
"""

# Chart bin: ~1440 points per range, never coarser-looking than the 1-minute source data
# (24h -> 1m, 7d -> 7m, 30d -> 30m). {TimeRange:grain} is ~30m at 24h and hides short jobs.
GRAIN = "let g = max_of(1m, {TimeRange:seconds} * 1s / 1440);\n"

UTIL_CHART = GRAIN + f"""GpuMetrics_CL
| where TimeGenerated {{TimeRange}}
{FILTER}
| extend Gpu = strcat(Computer, '/GPU', GpuId)
| summarize ['SM Active %'] = avg(SmActive) * 100, ['GPU Util %'] = avg(GpuUtil), ['Tensor Active %'] = avg(TensorActive) * 100
          by bin(TimeGenerated, g), Gpu
"""

MEM_CHART = GRAIN + f"""GpuMetrics_CL
| where TimeGenerated {{TimeRange}}
{FILTER}
| extend Gpu = strcat(Computer, '/GPU', GpuId)
| summarize UsedGB = avg(FbUsedMiB) / 1024.0 by bin(TimeGenerated, g), Gpu
"""

POWER_CHART = GRAIN + f"""GpuMetrics_CL
| where TimeGenerated {{TimeRange}}
{FILTER}
| extend Gpu = strcat(Computer, '/GPU', GpuId)
| summarize PowerW = avg(PowerW) by bin(TimeGenerated, g), Gpu
"""

HOURLY = f"""let gpu = GpuMetrics_CL
| where TimeGenerated {{TimeRange}}
{FILTER};
let gpuCount = gpu | summarize Gpus = dcount(GpuId) by Computer;
let alloc = Heartbeat
| where TimeGenerated {{TimeRange}}
| where Computer in ((gpuCount | project Computer))
| summarize RunMinutes = dcount(bin(TimeGenerated, 1m)) by Computer, Hour = bin(TimeGenerated, 1h)
| join kind=inner gpuCount on Computer
| summarize ['分配卡时'] = sum(RunMinutes * Gpus) / 60.0 by Hour;
let used = gpu
| summarize ['占用卡时'] = countif(ProcCount > 0 or GpuUtil >= {{IdlePct}}) / 60.0,
            ['有效计算卡时'] = sum(coalesce(SmActive, 0.0)) / 60.0
          by Hour = bin(TimeGenerated, 1h);
alloc
| join kind=leftouter used on Hour
| project Hour, ['分配卡时'], ['占用卡时'] = coalesce(['占用卡时'], 0.0), ['有效计算卡时'] = coalesce(['有效计算卡时'], 0.0)
| order by Hour asc
"""

IDLE_NOW = """GpuMetrics_CL
| where TimeGenerated > ago(60m)
| summarize Minutes = count(), BusyMinutes = countif(ProcCount > 0 or GpuUtil >= {IdlePct}),
            LastSeen = max(TimeGenerated), VmSize = any(VmSize)
          by Computer, GpuId
| where Minutes >= 30 and BusyMinutes == 0
| project Computer, GpuId, VmSize, ['最近60分钟空闲分钟数'] = Minutes, LastSeen
"""

LATEST = f"""GpuMetrics_CL
| where TimeGenerated > ago(15m)
{FILTER}
| summarize arg_max(TimeGenerated, *) by Computer, GpuId
| project TimeGenerated, Computer, VmSize, GpuId, GpuName,
          ['GPU Util %'] = GpuUtil, ['SM Active %'] = round(SmActive * 100, 1),
          ['显存 GB'] = round(FbUsedMiB / 1024.0, 1), ['功耗 W'] = PowerW, ['温度 C'] = TempC,
          Users, Processes
"""


def qitem(title, query, viz, size=0, extra=None):
    item = {
        "type": 3,
        "content": {
            "version": "KqlItem/1.0",
            "query": query,
            "size": size,
            "title": title,
            "timeContextFromParameter": "TimeRange",
            "queryType": 0,
            "resourceType": "microsoft.operationalinsights/workspaces",
            "visualization": viz,
        },
        "name": title,
    }
    if viz in ("timechart", "barchart", "unstackedbar", "linechart", "areachart"):
        # Legend "big numbers" default to Sum over all points (e.g. "SM Active % (Sum) 945"), which is meaningless here.
        item["content"]["chartSettings"] = {"showMetrics": False, "showLegend": True}
    if extra:
        cs = extra.pop("chartSettings", None)
        item["content"].update(extra)
        if cs:
            item["content"].setdefault("chartSettings", {}).update(cs)
    return item


def half(item):
    item["customWidth"] = "50"
    return item


def grid(widths, bar_cols=()):
    """Fixed column widths so Chinese headers are not truncated; utilization columns as bars."""
    fmts = []
    for col, w in widths.items():
        if col in bar_cols:
            fmts.append({"columnMatch": col, "formatter": 4,
                         "formatOptions": {"min": 0, "max": 100, "palette": "redGreen",
                                           "customColumnWidthSetting": w},
                         "numberFormat": {"unit": 0, "options": {"style": "decimal", "maximumFractionDigits": 1}}})
        else:
            fmts.append({"columnMatch": col, "formatter": 0,
                         "formatOptions": {"customColumnWidthSetting": w}})
    return {"gridSettings": {"formatters": fmts}}


# Chinese characters render ~2ch wide, plus ~4ch for the sort icon.
HOUR_COLS = {"分配卡时": "16ch", "占用卡时": "16ch", "有效计算卡时": "20ch", "空闲卡时": "16ch"}
VM_GRID = grid({"Computer": "24ch", "Gpus": "9ch", "RunHours": "13ch", **HOUR_COLS, "有效利用率%": "24ch"},
               bar_cols=("有效利用率%",))
DAY_GRID = grid({"Day": "22ch", "Computer": "24ch", **HOUR_COLS, "有效利用率%": "24ch"},
                bar_cols=("有效利用率%",))
USER_GRID = grid({"User": "14ch", "Computer": "24ch", "占用卡时": "16ch", "有效计算卡时": "20ch",
                  "平均SM Active%": "22ch", "峰值显存GB": "18ch"}, bar_cols=("平均SM Active%",))


TILE_SETTINGS = {
    "tileSettings": {
        "titleContent": {"columnMatch": "Metric", "formatter": 1},
        "leftContent": {
            "columnMatch": "Value",
            "formatter": 12,
            "formatOptions": {"palette": "blue"},
            "numberFormat": {"unit": 17, "options": {"style": "decimal", "maximumFractionDigits": 2}},
        },
        "showBorder": True,
    }
}

workbook = {
    "version": "Notebook/1.0",
    "items": [
        {
            "type": 1,
            "content": {
                "json": "# GPU 卡时统计（Azure 原生：AMA + DCGM + Log Analytics）\n"
                        "- **分配卡时** = VM 运行分钟（AMA `Heartbeat`）× GPU 数 ÷ 60\n"
                        "- **占用卡时** = 有 GPU 进程或 GPU Util ≥ 阈值 的 GPU·分钟 ÷ 60\n"
                        "- **有效计算卡时** = Σ(SM Active) ÷ 60（DCGM `DCGM_FI_PROF_SM_ACTIVE` 加权）\n"
                        "- **空闲卡时** = 分配 − 占用；**有效利用率** = 有效计算卡时 ÷ 分配卡时"
            },
            "name": "header",
        },
        {
            "type": 9,
            "content": {
                "version": "KqlParameterItem/1.0",
                "parameters": [
                    {
                        "id": str(uuid.uuid4()),
                        "version": "KqlParameterItem/1.0",
                        "name": "TimeRange",
                        "label": "时间范围",
                        "type": 4,
                        "isRequired": True,
                        "value": {"durationMs": 86400000},
                        "typeSettings": {
                            "selectableValues": [
                                {"durationMs": 3600000}, {"durationMs": 14400000},
                                {"durationMs": 43200000}, {"durationMs": 86400000},
                                {"durationMs": 604800000}, {"durationMs": 2592000000},
                            ],
                            "allowCustom": True,
                        },
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "version": "KqlParameterItem/1.0",
                        "name": "Computer",
                        "label": "GPU VM",
                        "type": 2,
                        "multiSelect": True,
                        "quote": "'",
                        "delimiter": ",",
                        "query": "GpuMetrics_CL | where TimeGenerated > ago(30d) | distinct Computer | order by Computer asc",
                        "typeSettings": {
                            "additionalResourceOptions": ["value::all"],
                            "selectAllValue": "*",
                            "showDefault": False,
                        },
                        "defaultValue": "value::all",
                        "value": ["value::all"],
                        "queryType": 0,
                        "resourceType": "microsoft.operationalinsights/workspaces",
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "version": "KqlParameterItem/1.0",
                        "name": "IdlePct",
                        "label": "占用判定阈值 GPU Util %",
                        "type": 1,
                        "isRequired": True,
                        "value": "5",
                    },
                ],
                "style": "pills",
                "queryType": 0,
                "resourceType": "microsoft.operationalinsights/workspaces",
            },
            "name": "parameters",
        },
        qitem("卡时汇总", SUMMARY_TILES, "tiles", extra=TILE_SETTINGS),
        qitem("按 VM 统计卡时", PER_VM, "table", extra=VM_GRID),
        qitem("每小时卡时（分配 / 占用 / 有效计算，分组对比）", HOURLY, "unstackedbar",
              extra={"chartSettings": {"xAxis": "Hour"}}),
        half(qitem("GPU 利用率趋势（SM Active / GPU Util / Tensor）", UTIL_CHART, "timechart",
                   extra={"chartSettings": {"ySettings": {"min": 0, "max": 100}}})),
        half(qitem("显存占用 (GB)", MEM_CHART, "timechart")),
        half(qitem("功耗 (W)", POWER_CHART, "timechart")),
        half(qitem("按用户统计卡时（进程属主）", BY_USER, "table", extra=USER_GRID)),
        qitem("按天统计卡时", DAILY, "table", extra=DAY_GRID),
        half(qitem("当前状态（最近一次采样）", LATEST, "table")),
        half(qitem("最近 60 分钟完全空闲的 GPU（开机但未使用）", IDLE_NOW, "table")),
    ],
    "fallbackResourceIds": [],
    "$schema": "https://github.com/Microsoft/Application-Insights-Workbooks/blob/master/schema/workbook.json",
}

ALERT_QUERY = """GpuMetrics_CL
| where TimeGenerated > ago(60m)
| summarize Minutes = count(), BusyMinutes = countif(ProcCount > 0 or GpuUtil >= 5) by Computer, GpuId
| where Minutes >= 50 and BusyMinutes == 0
"""

template = {
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        "location": {"type": "string", "defaultValue": "[resourceGroup().location]"},
        "workspaceName": {"type": "string", "defaultValue": "law-gpuhours-demo"},
        "workbookDisplayName": {"type": "string", "defaultValue": "GPU 卡时统计 (DCGM + AMA)"},
        "workbookId": {"type": "string", "defaultValue": "[newGuid()]"},
        "serializedData": {"type": "string"},
    },
    "variables": {
        "workspaceId": "[resourceId('Microsoft.OperationalInsights/workspaces', parameters('workspaceName'))]",
    },
    "resources": [
        {
            "type": "Microsoft.Insights/workbooks",
            "apiVersion": "2023-06-01",
            "name": "[parameters('workbookId')]",
            "location": "[parameters('location')]",
            "kind": "shared",
            "properties": {
                "displayName": "[parameters('workbookDisplayName')]",
                "serializedData": "[replace(parameters('serializedData'), '__WORKSPACE_ID__', variables('workspaceId'))]",
                "category": "workbook",
                "sourceId": "[variables('workspaceId')]",
            },
        },
        {
            "type": "Microsoft.Insights/scheduledQueryRules",
            "apiVersion": "2023-03-15-preview",
            "name": "alert-gpu-idle-60min",
            "location": "[parameters('location')]",
            "properties": {
                "displayName": "GPU 开机但空闲超过 60 分钟",
                "description": "VM 在运行、GPU 无进程且 GPU Util < 5% 持续 ≥ 50 分钟（最近 60 分钟窗口）",
                "severity": 3,
                "enabled": True,
                "evaluationFrequency": "PT15M",
                "windowSize": "PT1H",
                "scopes": ["[variables('workspaceId')]"],
                "criteria": {
                    "allOf": [
                        {
                            "query": ALERT_QUERY,
                            "timeAggregation": "Count",
                            "dimensions": [
                                {"name": "Computer", "operator": "Include", "values": ["*"]},
                            ],
                            "operator": "GreaterThan",
                            "threshold": 0,
                            "failingPeriods": {"numberOfEvaluationPeriods": 1, "minFailingPeriodsToAlert": 1},
                        }
                    ]
                },
                "autoMitigate": True,
            },
        },
    ],
    "outputs": {
        "workbookId": {"type": "string", "value": "[resourceId('Microsoft.Insights/workbooks', parameters('workbookId'))]"},
    },
}

workbook["fallbackResourceIds"] = ["__WORKSPACE_ID__"]
(HERE / "workbook.gallery.json").write_text(json.dumps(workbook, ensure_ascii=False, indent=2), encoding="utf-8")
(HERE / "workbook.json").write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
(HERE / "workbook.parameters.json").write_text(json.dumps({
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {"serializedData": {"value": json.dumps(workbook, ensure_ascii=False)}},
}, ensure_ascii=False, indent=2), encoding="utf-8")

# Also dump raw KQL for API/platform integration
(HERE / "queries.kql").write_text(
    "// ===== 卡时汇总 (Log Analytics Query API 可直接调用；把 {TimeRange} 换成 > ago(1d)，{Computer} 换成 '*'，{IdlePct} 换成 5) =====\n"
    + SUMMARY_TILES + "\n// ===== 按 VM =====\n" + PER_VM + "\n// ===== 按天 =====\n" + DAILY
    + "\n// ===== 按用户 =====\n" + BY_USER + "\n// ===== 空闲告警 =====\n" + ALERT_QUERY,
    encoding="utf-8")
print("written:", [p.name for p in HERE.glob("*.json")])
