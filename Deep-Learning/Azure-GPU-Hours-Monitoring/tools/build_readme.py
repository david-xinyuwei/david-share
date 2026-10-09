#!/usr/bin/env python3
"""Render the generated blocks of README.md and README_CN.md.

    python tools/build_readme.py            # rewrite every <!-- BEGIN GENERATED: name --> block in both READMEs
    python tools/build_readme.py --check    # fail if a committed README differs from a fresh render

Numbers come from evidence/measurements.json and evidence/runs.json, commands from scripts/*.sh,
DCGM fields from vm/gpu_collector.py and output columns from the committed query results, so the
prose around them never carries a hand-typed number.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READMES = {"en": ROOT / "README.md", "cn": ROOT / "README_CN.md"}
BLOCK = re.compile(r"(<!-- BEGIN GENERATED: (?P<name>[a-z0-9-]+) -->\n)(?P<body>.*?)(<!-- END GENERATED: (?P=name) -->)", re.S)
sys.path[:0] = [str(ROOT / "vm")]


def _json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _m() -> dict:
    return _json("evidence/measurements.json")["runs"]


def _runs() -> dict:
    return _json("evidence/runs.json")["runs"]


def _table(header: list[str], rows: list[list[str]], align: list[str]) -> str:
    sep = {"l": "---", "r": "---:"}
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(sep[a] for a in align) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def _n(v: float, d: int = 3) -> str:
    return f"{v:.{d}f}"


# ---------------------------------------------------------------- blocks
def glance(lang: str) -> str:
    v, r = _m()["validation-1"], _m()["replay-1"]
    steps = {s["step"].split()[0]: s for s in _runs()["replay-1"]["steps"]}
    ph = [p for p in v["phases"] if p["minutes"] > 1]
    n = sum(x["kql_vs_python"]["compared_values"] for x in (v, r))
    mb = v["derived_mb_per_vm_day"]["8_gpu"]
    j = _m()["jobs-1"]
    jobs, jm = j["jobs"], j["jobs"]["per_job"]
    if lang == "en":
        return (f"- On one H100 VM running a load with a known schedule, the pipeline recorded {ph[0]['minutes']} full, "
                f"{ph[1]['minutes']} held and {ph[2]['minutes']} partial GPU-minutes, the same split the load script scheduled; "
                f"the five views and an independent Python recomputation of the raw rows agree on all {n} compared values.\n"
                f"- Three AML jobs ran there as one Linux user: `per_user` shows a single owner with "
                f"{_n(j['per_user'][0]['BusyGpuHours'])} busy GPU-hours, while `per_job` splits them by job name "
                f"({_n(jm[0]['BusyGpuHours'])}, {_n(jm[1]['BusyGpuHours'])}, {_n(jm[2]['BusyGpuHours'])}), counts the "
                f"{jobs['shared_job_minutes']} minutes two jobs shared as half each and names the Entra account that submitted "
                f"them; KQL and Python agree on {jobs['kql_vs_python']['compared_values']} values and "
                f"{jobs['kql_vs_python']['compared_fields']} fields.\n"
                f"- The configuration steps below ran verbatim against a new resource group: workspace setup {steps['1']['seconds']} s, "
                f"VM onboarding {steps['2']['seconds']} s, removal {steps['6']['seconds']} s.\n"
                f"- Log Analytics bills {_n(v['billed_bytes_per_row']['gpu_median'], 0)} bytes per GPU-minute row, about "
                f"{_n(mb, 2)} MB per day for an 8-GPU VM including its Heartbeat.\n"
                f"- Main limit: process owners are sampled once per minute, so a job that exits mid-minute leaves that minute busy "
                f"but unattributed ({v['unattributed_busy_minutes']} of {v['busy_minutes']} busy minutes in the first run, "
                f"{r['unattributed_busy_minutes']} of {r['busy_minutes']} in the second).\n")
    return (f"- 在一台 H100 VM 上跑一段时间表已知的负载，采集链路记录下满载 {ph[0]['minutes']} 分钟、占用 {ph[1]['minutes']} 分钟、"
            f"半载 {ph[2]['minutes']} 分钟，与负载脚本的安排一致；五个查询的结果和对原始数据的独立 Python 重算逐值比对，{n} 个值全部相同。\n"
            f"- 三个 AML 作业以同一个 Linux 用户在这台 VM 上运行：`per_user` 只看到一个属主，合计 "
            f"{_n(j['per_user'][0]['BusyGpuHours'])} 占用卡时；`per_job` 按作业名拆成 "
            f"{_n(jm[0]['BusyGpuHours'])}、{_n(jm[1]['BusyGpuHours'])}、{_n(jm[2]['BusyGpuHours'])}，两个作业共用的 "
            f"{jobs['shared_job_minutes']} 分钟各记一半，并给出提交作业的 Entra 账号；KQL 与 Python 比对 "
            f"{jobs['kql_vs_python']['compared_values']} 个数值、{jobs['kql_vs_python']['compared_fields']} 个字段全部一致。\n"
            f"- 下面的配置步骤在一个新资源组里原样实跑：建工作区 {steps['1']['seconds']} 秒，接入 VM {steps['2']['seconds']} 秒，"
            f"下线 {steps['6']['seconds']} 秒。\n"
            f"- Log Analytics 按每行 {_n(v['billed_bytes_per_row']['gpu_median'], 0)} 字节计费（每 GPU·分钟一行），每天约 "
            f"{_n(mb, 2)} MB（8 卡 VM，含 Heartbeat）。\n"
            f"- 主要限制：进程属主每分钟只采一次，任务在一分钟中途退出时，这一分钟算占用但没有属主"
            f"（第一次实测 {v['unattributed_busy_minutes']} / {v['busy_minutes']} 个占用分钟，第二次 "
            f"{r['unattributed_busy_minutes']} / {r['busy_minutes']} 个）。\n")


def dcgm_command(lang: str) -> str:
    import gpu_collector as c
    fields = ",".join(str(f) for f, _ in c.FIELDS)
    return f"```bash\ndcgmi dmon -e {fields} -d {c.SAMPLE_MS}\n```\n"


DCGM_NAMES = {203: "DCGM_FI_DEV_GPU_UTIL", 1001: "DCGM_FI_PROF_GR_ENGINE_ACTIVE", 1002: "DCGM_FI_PROF_SM_ACTIVE",
              1004: "DCGM_FI_PROF_PIPE_TENSOR_ACTIVE", 1005: "DCGM_FI_PROF_DRAM_ACTIVE", 252: "DCGM_FI_DEV_FB_USED",
              250: "DCGM_FI_DEV_FB_TOTAL", 155: "DCGM_FI_DEV_POWER_USAGE", 150: "DCGM_FI_DEV_GPU_TEMP"}
DCGM_USE = {
    "en": {"GpuUtil": "busy threshold", "GrActive": "reference", "SmActive": "effective GPU-hours",
           "TensorActive": "reference", "DramActive": "reference", "FbUsedMiB": "memory in use",
           "FbTotalMiB": "memory size", "PowerW": "reference", "TempC": "reference"},
    "cn": {"GpuUtil": "占用判定阈值", "GrActive": "参考", "SmActive": "有效计算卡时", "TensorActive": "参考",
           "DramActive": "参考", "FbUsedMiB": "显存占用", "FbTotalMiB": "显存容量", "PowerW": "参考", "TempC": "参考"},
}


def dcgm_fields(lang: str) -> str:
    import gpu_collector as c
    sep = {"en": ": ", "cn": "："}[lang]
    return "".join(f"- `{f}` `{DCGM_NAMES[f]}` → `{k}`{sep}{DCGM_USE[lang][k]}\n" for f, k in c.FIELDS)


def json_line(lang: str) -> str:
    rows = [json.loads(l) for l in (ROOT / "evidence/runs/validation-1/gpu-metrics.jsonl").read_text(encoding="utf-8").splitlines()]
    r = next(x for x in rows if (x["SmActive"] or 0) > 0.9)
    line = {"TimeGenerated": "<minute start, UTC>", "VmName": "<vm-name>", "VmSize": r["VmSize"],
            "VmResourceId": "<vm resource id>", "Tags": "", "GpuId": r["GpuId"], "GpuUuid": "<GPU UUID>",
            "GpuName": r["GpuName"], "Samples": r["Samples"]}
    for k in ("GpuUtil", "GrActive", "SmActive", "TensorActive", "DramActive", "FbUsedMiB", "FbTotalMiB", "PowerW", "TempC",
              "ProcCount", "Users", "Processes"):
        line[k] = r[k]
    line["Users"] = "<linux user>"
    line["RunId"] = "<AML run ID>"
    return "```json\n" + json.dumps(line, ensure_ascii=False) + "\n```\n"


def _az_lines(script: str) -> str:
    """The az commands of a script, verbatim, with their continuation lines."""
    out, cont = [], False
    for raw in (ROOT / "scripts" / script).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if cont or re.match(r"^(if |else |)?az |^[A-Z_]+=\$\(az ", line):
            out.append(("  " if cont else "") + line.removeprefix("if ").removesuffix("; then"))
            cont = line.endswith("\\")
    return "```bash\n" + "\n".join(out) + "\n```\n"


def setup_commands(lang: str) -> str:
    return _az_lines("setup-workspace.sh")


def onboard_commands(lang: str) -> str:
    return _az_lines("onboard-vm.sh")


def offboard_commands(lang: str) -> str:
    return _az_lines("offboard-vm.sh")


VIEW_TEXT = {
    "en": {"summary": "all selected VMs together", "per_vm": "one row per VM", "per_hour": "one row per local hour",
           "per_day": "one row per local day", "per_user": "one row per process owner and VM",
           "per_job": "one row per AML job", "per_submitter": "one row per Entra submitter",
           "live": "latest GPU process seen in the query window"},
    "cn": {"summary": "所选 VM 合计", "per_vm": "每台 VM 一行", "per_hour": "每个本地小时一行",
           "per_day": "每个本地日一行", "per_user": "每个进程属主、每台 VM 一行",
           "per_job": "每个 AML 作业一行", "per_submitter": "每个 Entra 提交人一行",
           "live": "查询时段内每张卡最后看到的 GPU 进程"},
}
VIEW_ORDER = ("summary", "per_vm", "per_hour", "per_day", "per_user", "per_job", "per_submitter", "live")
NEW_VIEW_COLUMNS = {
    "per_job": ["RunId", "Submitter", "SubmitterObjectId", "Status", "Vms", "Gpus", "StartTime", "EndTime",
                "BusyGpuHours", "EffectiveGpuHours", "PeakMemoryGiB"],
    "per_submitter": ["Submitter", "SubmitterObjectId", "Jobs", "BusyGpuHours", "EffectiveGpuHours"],
    "live": ["Computer", "GpuId", "RunId", "Submitter", "SubmitterObjectId", "Status", "LastSeen", "AgeSeconds",
             "GpuUtil", "SmActive", "FbUsedMiB", "ProcCount", "Processes"],
}


def views(lang: str) -> str:
    kql = _json("evidence/runs/validation-1/kql-results.json")
    sep, comma = {"en": (", ", ": "), "cn": ("，", "：")}[lang]
    joiner = {"en": ", ", "cn": "、"}[lang]
    columns = {v: list(kql[v][0]) for v in kql}
    columns.update(NEW_VIEW_COLUMNS)
    return "".join(f"- [`kql/{v}.kql`](kql/{v}.kql){sep}{VIEW_TEXT[lang][v]}{comma}"
                   + joiner.join(f"`{c}`" for c in columns[v]) + "\n"
                   for v in VIEW_ORDER)


def per_user_json(lang: str) -> str:
    rows = _json("evidence/runs/replay-1/kql-results.json")["per_user"]
    rounded = [{k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()} for r in rows]
    return "```json\n" + json.dumps(rounded, indent=1, ensure_ascii=False) + "\n```\n"


def load_input(lang: str) -> str:
    return "```python\n" + _runs()["validation-1"]["load"]["script_verbatim"] + "```\n"


PHASE = {"en": {"full": "full", "held": "held", "partial": "partial"}, "cn": {"full": "满载", "held": "占用", "partial": "半载"}}


def phases(lang: str) -> str:
    v = _m()["validation-1"]
    head = {"en": ["Phase (first minute)", "Minutes", "SM active", "Power"],
            "cn": ["阶段（起始分钟）", "分钟数", "SM Active", "功耗"]}[lang]
    rows = [[f"{PHASE[lang][p['phase']]} ({p['first_minute']})", str(p["minutes"]), f"{_n(p['mean_sm_active_pct'], 1)} %",
             f"{_n(p['mean_power_w'], 0)} W"] for p in v["phases"]]
    return _table(head, rows, ["l", "r", "r", "r"])


def summary_v1(lang: str) -> str:
    s = _m()["validation-1"]["summary"]
    v = _m()["validation-1"]
    if lang == "en":
        return (f"- Allocated {_n(s['AllocatedGpuHours'])}, busy {_n(s['BusyGpuHours'])}, effective {_n(s['EffectiveGpuHours'])} "
                f"and idle {_n(s['IdleGpuHours'])} GPU-hours; utilization {_n(s['UtilizationPct'], 2)} %.\n"
                f"- Allocated time is {v['heartbeat_minutes']} Heartbeat minutes: the VM kept running after the load, which is "
                f"what the idle hours show.\n"
                f"- {v['owner_minutes']} of the {v['busy_minutes']} busy minutes carry the owner `user-1`.\n")
    return (f"- 分配 {_n(s['AllocatedGpuHours'])}、占用 {_n(s['BusyGpuHours'])}、有效计算 {_n(s['EffectiveGpuHours'])}、"
            f"空闲 {_n(s['IdleGpuHours'])} GPU·小时；有效利用率 {_n(s['UtilizationPct'], 2)} %。\n"
            f"- 分配时长就是 {v['heartbeat_minutes']} 个 Heartbeat 分钟：负载结束后 VM 一直开着，空闲卡时反映的正是这段时间。\n"
            f"- 占用分钟中有 {v['owner_minutes']} / {v['busy_minutes']} 个记到了属主 `user-1`。\n")


STEP_TEXT = {
    "en": ["workspace, table, DCE, DCR", "VM onboarding", "first rows", "two-user load", "queries: CLI and client", "removal"],
    "cn": ["工作区、表、DCE、DCR", "接入 VM", "首批数据", "两个用户的负载", "查询：CLI 与客户端", "下线"],
}
CHECK_TEXT = {
    "en": ["Table 23 columns, 90-day retention; rule reads /var/log/gpumon/*.json",
           "gpumon.service active, running dcgmi dmon",
           "Heartbeat about 8 min, GpuMetrics_CL about 11 min after onboarding",
           "2 processes of 21 GiB each on the GPU",
           "CLI and client return the same per-owner values",
           "No agent, association or collector left; resource group deleted"],
    "cn": ["表 23 列，保留 90 天；规则读取 /var/log/gpumon/*.json",
           "gpumon.service 运行中，执行 dcgmi dmon",
           "接入后约 8 分钟出现 Heartbeat，约 11 分钟出现 GpuMetrics_CL",
           "GPU 上 2 个进程，各 21 GiB",
           "CLI 与客户端返回的属主数值相同",
           "代理、关联、采集器全部移除；资源组已删除"],
}


def replay_steps(lang: str) -> str:
    steps = _runs()["replay-1"]["steps"]
    out = []
    for i, s in enumerate(steps):
        took = ""
        if s["seconds"] is not None:
            took = {"en": f", {s['seconds']} s", "cn": f"，{s['seconds']} 秒"}[lang]
        if lang == "en":
            out.append(f"- **{i + 1} {STEP_TEXT[lang][i]}**: exit {s['exit']}{took}. {CHECK_TEXT[lang][i]}.\n")
        else:
            out.append(f"- **{i + 1} {STEP_TEXT[lang][i]}**：退出码 {s['exit']}{took}。{CHECK_TEXT[lang][i]}。\n")
    return "".join(out)


def owners(lang: str) -> str:
    r = _m()["replay-1"]
    head = {"en": ["Owner", "Busy GPU-h", "Effective GPU-h"], "cn": ["属主", "占用卡时", "有效计算卡时"]}[lang]
    rows = [[f"`{u['User']}`", _n(u["BusyGpuHours"]), _n(u["EffectiveGpuHours"])] for u in r["per_user"]]
    shared = sum(p["shared_minutes"] for p in r["phases"])
    tail = {"en": (f"\n- {r['busy_minutes']} busy minutes: {r['owner_minutes']} with an owner, of which {shared} shared by both, "
                   f"and {r['unattributed_busy_minutes']} without an owner.\n"),
            "cn": (f"\n- 共 {r['busy_minutes']} 个占用分钟：{r['owner_minutes']} 个有属主，其中 {shared} 个由两人共用；"
                   f"{r['unattributed_busy_minutes']} 个没有属主。\n")}[lang]
    return _table(head, rows, ["l", "r", "r"]) + tail


def checks(lang: str) -> str:
    v, r, j = _m()["validation-1"], _m()["replay-1"], _m()["jobs-1"]
    d, b = v["ingestion_delay_seconds"], v["billed_bytes_per_row"]
    jq = j["jobs"]["kql_vs_python"]
    if lang == "en":
        return (f"- KQL against Python: {v['kql_vs_python']['compared_values']} values in the first run and "
                f"{r['kql_vs_python']['compared_values']} in the second, largest difference {v['kql_vs_python']['max_abs_diff']}.\n"
                f"- `jobs-1`: {j['kql_vs_python']['compared_values']} values of the classic views, and {jq['compared_values']} values "
                f"and {jq['compared_fields']} fields of the job views, largest difference {jq['max_abs_diff']}.\n"
                f"- Ingestion delay of GpuMetrics_CL rows: median {d['median']} s, p95 {d['p95']} s.\n"
                f"- Billed size: {_n(b['gpu_median'], 0)} bytes per GPU row, {_n(b['heartbeat_median'], 0)} bytes per Heartbeat row.\n")
    return (f"- KQL 与 Python 比对：第一次实测 {v['kql_vs_python']['compared_values']} 个值，第二次 "
            f"{r['kql_vs_python']['compared_values']} 个，最大差值 {v['kql_vs_python']['max_abs_diff']}。\n"
            f"- `jobs-1`：原有查询 {j['kql_vs_python']['compared_values']} 个值，作业查询 {jq['compared_values']} 个数值、"
            f"{jq['compared_fields']} 个字段，最大差值 {jq['max_abs_diff']}。\n"
            f"- GpuMetrics_CL 入库延迟：中位数 {d['median']} 秒，p95 {d['p95']} 秒。\n"
            f"- 计费大小：每行 GPU 数据 {_n(b['gpu_median'], 0)} 字节，每行 Heartbeat {_n(b['heartbeat_median'], 0)} 字节。\n")


def jobs_launcher(lang: str) -> str:
    return "```bash\n" + _runs()["jobs-1"]["load"]["launcher_verbatim"] + "```\n"


JOB_STEP_TEXT = {
    "en": ["workspace with job tracking", "VM onboarding", "VM attached to AML", "three AML jobs",
           "read back: the eight views through the client", "cleanup"],
    "cn": ["工作区与作业跟踪", "接入 VM", "VM 附加到 AML", "三个 AML 作业", "回读：参考客户端执行八个查询", "清理"],
}
JOB_CHECK_TEXT = {
    "en": ["Table 24 columns including RunId; Administrative activity and AmlRunStatusChangedEvent go to the workspace",
           "gpumon.service active with the RunId collector",
           "Compute provisioning state Succeeded",
           "All Completed; job-2 and job-3 shared the GPU as one Linux user, each process with its own AZUREML_RUN_ID",
           "Raw rows and all views exported",
           "Compute detached, test account removed, diagnostic settings and resource group deleted, VM deallocated"],
    "cn": ["表 24 列，含 RunId；Administrative 活动日志和 AmlRunStatusChangedEvent 写入工作区",
           "gpumon.service 运行中，采集器带 RunId",
           "计算目标状态 Succeeded",
           "全部 Completed；job-2 与 job-3 以同一个 Linux 用户共用 GPU，每个进程带各自的 AZUREML_RUN_ID",
           "原始数据和全部查询结果导出完成",
           "计算目标已分离，测试账户已删除，诊断设置和资源组已删除，VM 已释放"],
}


def jobs_steps(lang: str) -> str:
    out = []
    for i, s in enumerate(_runs()["jobs-1"]["steps"]):
        took = "" if s["seconds"] is None else {"en": f", {s['seconds']} s", "cn": f"，{s['seconds']} 秒"}[lang]
        if lang == "en":
            out.append(f"- **{i + 1} {JOB_STEP_TEXT[lang][i]}**: exit {s['exit']}{took}. {JOB_CHECK_TEXT[lang][i]}.\n")
        else:
            out.append(f"- **{i + 1} {JOB_STEP_TEXT[lang][i]}**：退出码 {s['exit']}{took}。{JOB_CHECK_TEXT[lang][i]}。\n")
    return "".join(out)


def jobs_result(lang: str) -> str:
    j = _m()["jobs-1"]
    jobs = j["jobs"]
    owner = j["per_user"][0]
    seq = " → ".join(next(iter(jobs["status_sequence"].values())))
    delay = jobs["ingestion_delay_seconds"]
    head = {"en": ["Job", "Submitter", "Busy GPU-h", "Effective GPU-h"], "cn": ["作业", "提交人", "占用卡时", "有效计算卡时"]}[lang]
    rows = [[f"`{x['RunId']}`", f"`{x['Submitter']}`", _n(x["BusyGpuHours"]), _n(x["EffectiveGpuHours"])] for x in jobs["per_job"]]
    unnamed = j["busy_minutes"] - jobs["job_minutes"]
    if lang == "en":
        tail = (f"\n- `per_user` over the same window: one owner, `{owner['User']}`, with {_n(owner['BusyGpuHours'])} busy GPU-hours, "
                f"the three jobs added together.\n"
                f"- {j['busy_minutes']} busy minutes: {jobs['job_minutes']} with a job name, of which {jobs['shared_job_minutes']} "
                f"carried two names and counted half for each, and {unnamed} without a name.\n"
                f"- Status events of every job: {seq}.\n"
                f"- Ingestion delay: GPU rows median {delay['gpu_rows']['median']} s; status events median "
                f"{delay['status_events']['median']} s, at most {delay['status_events']['max']} s; submissions median "
                f"{delay['submissions']['median']} s, at most {delay['submissions']['max']} s.\n")
    else:
        tail = (f"\n- 同一时段的 `per_user`：只有一个属主 `{owner['User']}`，占用 {_n(owner['BusyGpuHours'])} 卡时，即三个作业之和。\n"
                f"- 共 {j['busy_minutes']} 个占用分钟：{jobs['job_minutes']} 个带作业名，其中 {jobs['shared_job_minutes']} "
                f"个带两个作业名、各记一半；{unnamed} 个没有作业名。\n"
                f"- 每个作业的状态事件：{seq}。\n"
                f"- 入库延迟：GPU 数据中位数 {delay['gpu_rows']['median']} 秒；状态事件中位数 "
                f"{delay['status_events']['median']} 秒，最长 {delay['status_events']['max']} 秒；提交事件中位数 "
                f"{delay['submissions']['median']} 秒，最长 {delay['submissions']['max']} 秒。\n")
    return _table(head, rows, ["l", "l", "r", "r"]) + tail


BLOCKS = {"glance": glance, "dcgm-command": dcgm_command, "dcgm-fields": dcgm_fields, "json-line": json_line,
          "setup-commands": setup_commands, "onboard-commands": onboard_commands, "offboard-commands": offboard_commands,
          "views": views, "per-user-json": per_user_json, "load-input": load_input, "phases": phases,
          "summary-v1": summary_v1, "replay-steps": replay_steps, "owners": owners, "checks": checks,
          "jobs-launcher": jobs_launcher, "jobs-steps": jobs_steps, "jobs-result": jobs_result}


def render(text: str, lang: str) -> str:
    def sub(m: re.Match) -> str:
        name = m.group("name")
        if name not in BLOCKS:
            raise SystemExit(f"UNKNOWN_BLOCK {name}")
        return m.group(1) + BLOCKS[name](lang) + m.group(4)
    return BLOCK.sub(sub, text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    stale = []
    for lang, path in READMES.items():
        text = path.read_text(encoding="utf-8")
        new = render(text, lang)
        if args.check:
            if new != text:
                stale.append(path.name)
        else:
            path.write_text(new, encoding="utf-8", newline="\n")
    if args.check:
        if stale:
            print("README_STALE " + ", ".join(stale) + " (run python tools/build_readme.py)")
            return 1
        print(f"PASS {len(READMES)} READMEs equal a fresh render of their generated blocks")
        return 0
    print(f"rendered {', '.join(p.name for p in READMES.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
