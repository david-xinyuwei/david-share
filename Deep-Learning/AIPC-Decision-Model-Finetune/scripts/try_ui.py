#!/usr/bin/env python3
"""Local browser page to try the fine-tuned decision model by hand: edit the message and device fields, submit, and see
every option's probability, next to what the vendor policy says, plus the llama-server process's live memory and CPU.
Standard library only; Chinese/English switch in the page.

  python scripts\try_ui.py                       # expects llama-server on 127.0.0.1:8080 (README step A1)
  python scripts\try_ui.py --start-server         # also starts llama-server (see --engine / --model) and stops it on exit
  python scripts\try_ui.py --port 8090 --server http://127.0.0.1:8080

Then open http://127.0.0.1:8090 on this machine. The page sends exactly what systemone_client.py sends (state +
unlabeled questions) to /v1/systemone and shows the raw answers and probabilities; nothing is cached or corrected.
Optionally choose the scenario the message describes to see the vendor policy's answer (scripts/vendor_policy.py,
computed locally; the model never sees it). The resource panel reads the llama-server process through the Windows
API (working set, private bytes, CPU time -> utilisation); on other systems it shows "not available".
Query string: ?auto=<scenario>[&workload=assistant][&region=SG][&lang=en] submits the example once on load.
The page binds to 127.0.0.1 only.
"""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vendor_policy as vp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SERVER = "http://127.0.0.1:8080"
EXAMPLES = {name: json.loads((ROOT / "data" / "contoso" / "examples" / f"{name}.json").read_text(encoding="utf-8-sig"))
            for name in ("support", "support-sg", "assistant")}

META = {
    "support": {
        "questions": vp.SUPPORT_QUESTIONS,
        "fields": {"channel": list(vp.CHANNELS), "product_line": list(vp.PRODUCT_LINES), "region": list(vp.REGIONS),
                   "warranty_plan": list(vp.PLAN_DAYS),
                   "last_error_code": ["none", "BAT-047", "THM-212", "BIOS-0x1F", "BIOS-0x2A", "SSD-501", "NPU-118", "DSP-330"]},
        "scenarios": {key: value[0] for key, value in vp.SUPPORT_SCENARIOS.items()},
        "example": EXAMPLES["support"], "example_sg": EXAMPLES["support-sg"],
    },
    "assistant": {
        "questions": vp.ASSIST_QUESTIONS,
        "fields": {"foreground_app": list(vp.FOREGROUND_APPS), "power_source": ["ac", "battery"], "network": ["wifi", "metered", "offline"]},
        "intents": {key: value[1] for key, value in vp.ASSIST_INTENTS.items()},
        "example": EXAMPLES["assistant"],
    },
}


def policy_answer(workload, state, scenario, modifiers):
    if not scenario:
        return None
    if workload == "support":
        case = {"device": state["device"], "scenario": scenario,
                "modifiers": {"deadline_today": bool(modifiers.get("deadline_today")), "legal_deadline": bool(modifiers.get("legal_deadline")),
                              "has_backup": bool(modifiers.get("has_backup", True))}}
        return vp.support_labels(case)
    return vp.assistant_labels({"context": state["context"], "intent": scenario})


def ask_model(server, workload, state):
    questions = {qid: {key: value for key, value in question.items() if key != "label"} for qid, question in META[workload]["questions"].items()}
    body = json.dumps({"state": state, "questions": questions}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(server + "/v1/systemone", data=body, method="POST", headers={"content-type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read())
    return data, round((time.perf_counter() - started) * 1000, 1), {"state": state, "questions": questions}


# ---- llama-server process resources (Windows API through ctypes; standard library only) -------------------------------
class ProcessMonitor:
    """Working set / private bytes / CPU utilisation of the process listening on the server port, sampled on demand."""

    def __init__(self, port):
        self.port = port
        self.pid = None
        self.last = None   # (monotonic time, cpu seconds)
        self.peak_ws = 0
        self.busy_pct = None
        self.lock = threading.Lock()
        self.cpu_count = os.cpu_count() or 1

    def find_pid(self):
        if sys.platform != "win32":
            return None
        try:
            out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=10).stdout
        except Exception:  # noqa: BLE001
            return None
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(f":{self.port}") and parts[3] == "LISTENING":
                return int(parts[4])
        return None

    def sample(self):
        if sys.platform != "win32":
            return {"available": False, "reason": "process metrics are read through the Windows API; not available on this OS"}
        with self.lock:
            if self.pid is None:
                self.pid = self.find_pid()
            if self.pid is None:
                return {"available": False, "reason": f"no process listening on port {self.port}"}
            import ctypes.wintypes as w
            kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi

            class PMC(ctypes.Structure):
                _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]
            handle = kernel32.OpenProcess(0x1000, False, self.pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                self.pid = None
                return {"available": False, "reason": "server process exited"}
            try:
                pmc = PMC()
                pmc.cb = ctypes.sizeof(PMC)
                if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                    return {"available": False, "reason": "GetProcessMemoryInfo failed"}
                times = [w.FILETIME() for _ in range(4)]
                kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times])
                cpu_s = sum(((t.dwHighDateTime << 32) | t.dwLowDateTime) / 1e7 for t in times[2:])
            finally:
                kernel32.CloseHandle(handle)
            now = time.monotonic()
            if self.last is not None and now - self.last[0] >= 0.2:
                self.busy_pct = round(100 * (cpu_s - self.last[1]) / (now - self.last[0]) / self.cpu_count, 1)
            self.last = (now, cpu_s)
            self.peak_ws = max(self.peak_ws, pmc.PeakWorkingSetSize)
            return {"available": True, "pid": self.pid, "working_set_mib": round(pmc.WorkingSetSize / 2**20, 1),
                    "peak_working_set_mib": round(pmc.PeakWorkingSetSize / 2**20, 1), "private_mib": round(pmc.PrivateUsage / 2**20, 1),
                    "cpu_seconds": round(cpu_s, 1), "cpu_pct": self.busy_pct, "logical_processors": self.cpu_count}


PAGE = r"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title data-i18n="title">Kev 决策模型 · 本机试用</title>
<style>
:root{--ink:#243746;--muted:#536471;--blue:#0078D4;--blue2:#106ebe;--line:#d9e1e7;--soft:#f3f5f7;--card:#fff;--ok:#107c10;--bad:#d83b01;--orange:#d83b01}
*{box-sizing:border-box}
body{font-family:"Segoe UI",system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0;background:linear-gradient(180deg,#eef3f8 0,#f3f5f7 240px);color:var(--ink)}
header{background:var(--blue);color:#fff;padding:0 28px;height:58px;display:flex;align-items:center;gap:16px;box-shadow:0 2px 8px rgba(0,0,0,.12)}
header h1{font-size:19px;font-weight:600;margin:0;letter-spacing:.01em}
header .sub{font-size:12.5px;opacity:.85}
header .spacer{flex:1}
.pill{font-size:12px;padding:3px 10px;border-radius:999px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);color:#fff}
.pill.ok{background:#0b6a0b;border-color:#0b6a0b}.pill.bad{background:#b3300a;border-color:#b3300a}
.lang button{font:inherit;font-size:12.5px;padding:4px 10px;border:1px solid rgba(255,255,255,.5);background:transparent;color:#fff;cursor:pointer}
.lang button:first-child{border-radius:4px 0 0 4px}.lang button:last-child{border-radius:0 4px 4px 0;border-left:0}
.lang button.on{background:#fff;color:var(--blue);font-weight:600}
main{display:grid;grid-template-columns:minmax(340px,460px) 1fr;gap:22px;padding:22px 28px;max-width:1480px;margin:0 auto}
@media(max-width:980px){main{grid-template-columns:1fr}}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;box-shadow:0 1px 3px rgba(36,55,70,.06)}
h2{font-size:12.5px;margin:0 0 14px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-weight:600}
label{display:block;font-size:12.5px;color:var(--muted);margin-top:10px}
label code{font-size:11px;color:#8a97a3;font-family:Consolas,"Cascadia Mono",monospace}
input,select,textarea{width:100%;font:inherit;font-size:13.5px;padding:7px 9px;border:1px solid #b8cedf;border-radius:6px;margin-top:4px;background:#fff;color:var(--ink)}
input:focus,select:focus,textarea:focus{outline:2px solid rgba(0,120,212,.35);border-color:var(--blue)}
textarea{min-height:92px;resize:vertical;line-height:1.5}
.row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.check{display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:var(--ink)}
.check input{width:auto;margin:0}
.tabs{display:flex;gap:6px;margin-bottom:6px}
.tabs button{font:inherit;font-size:13.5px;padding:7px 16px;border:1px solid #b8cedf;background:#fff;border-radius:999px;cursor:pointer;color:var(--ink)}
.tabs button.on{background:var(--blue);color:#fff;border-color:var(--blue)}
.go{margin-top:16px;width:100%;padding:11px;font:inherit;font-size:14.5px;font-weight:600;background:var(--blue);color:#fff;border:0;border-radius:8px;cursor:pointer;transition:background .15s}
.go:hover{background:var(--blue2)}.go:disabled{background:#9bbfdc;cursor:wait}
.hint{font-size:12px;color:var(--muted);line-height:1.55;margin:10px 0 0}
.divider{border-top:1px dashed var(--line);margin:16px 0 4px}
.q{border-top:1px solid #e6ebf0;padding:14px 0 10px}
.q:first-of-type{border-top:0;padding-top:4px}
.q h3{margin:0 0 8px;font-size:15px;display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
.q h3 .qi{font-weight:normal;color:var(--muted);font-size:12.5px}
.bar{display:grid;grid-template-columns:minmax(160px,250px) 1fr 62px;gap:10px;align-items:center;font-size:12.5px;margin:4px 0}
.bar span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar .track{height:12px;background:#eef2f5;border-radius:6px;overflow:hidden}
.bar .fill{height:100%;background:#9bbfdc;border-radius:6px;transition:width .35s}
.bar.top .fill{background:var(--blue)}
.bar.top b{color:var(--blue)}
.bar b{text-align:right;font-variant-numeric:tabular-nums}
.verdict{font-size:13.5px;margin-top:8px;padding:8px 12px;border-radius:6px;background:var(--soft);display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:0 0 14px}
.kpi{background:var(--soft);border-radius:8px;padding:10px 12px}
.kpi .v{font-size:19px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--ink)}
.kpi .k{font-size:11.5px;color:var(--muted);margin-top:2px}
.res{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.res .kpi .v{font-size:17px}
.res .kpi .v small{font-size:12px;font-weight:normal;color:var(--muted)}
.meter{height:6px;background:#e6ebf0;border-radius:3px;margin-top:6px;overflow:hidden}
.meter i{display:block;height:100%;background:var(--blue);border-radius:3px;transition:width .4s}
details summary{cursor:pointer;color:var(--blue);font-size:13px;margin-top:12px}
pre{background:var(--soft);border:1px solid #e6ebf0;border-radius:6px;padding:10px;font-size:11.5px;overflow:auto;max-height:280px;font-family:Consolas,"Cascadia Mono",monospace}
.empty{color:var(--muted);font-size:13.5px;line-height:1.6;padding:8px 0}
footer{font-size:11.5px;color:var(--muted);padding:0 28px 20px;max-width:1480px;margin:0 auto}
</style></head><body>
<header>
  <h1 data-i18n="title">Kev 决策模型 · 本机试用</h1>
  <span class="sub" data-i18n="subtitle">同一个微调后的 GGUF，本机 llama-server，/v1/systemone</span>
  <span class="spacer"></span>
  <span id="srv" class="pill">…</span>
  <span class="lang"><button id="lang-zh" class="on" onclick="setLang('zh')">中文</button><button id="lang-en" onclick="setLang('en')">EN</button></span>
</header>
<main>
<section>
  <h2 data-i18n="input">输入</h2>
  <div class="tabs"><button id="tab-support" class="on" onclick="setWorkload('support')" data-i18n="tab_support">售后工单</button><button id="tab-assistant" onclick="setWorkload('assistant')" data-i18n="tab_assistant">助手路由</button></div>
  <div id="form"></div>
  <button class="go" id="go" onclick="submit()" data-i18n="go">提交给模型</button>
  <p class="hint" data-i18n="hint_in">模型只看到上面的原话和字段，不知道你选的"场景"。场景只用于在右侧算出"规则说该怎样"，方便对照。</p>
</section>
<section>
  <h2 data-i18n="resources">本机 llama-server 进程</h2>
  <div class="res" id="res"></div>
  <p class="hint" id="reshint"></p>
  <div class="divider"></div>
  <h2 data-i18n="output">模型输出</h2>
  <div id="out"><p class="empty" data-i18n="empty">点"提交给模型"。每道题显示全部选项的概率，概率最高的即答案；概率已按模型文件内的校准温度缩放。</p></div>
</section>
</main>
<footer data-i18n="footer">本页只连接 127.0.0.1 上的本机服务；模型不生成文字，只给每个选项打分。模拟厂商数据，不是真实客户数据。</footer>
<script>
const META = __META__;
const I18N = {
  zh: {title:'Kev 决策模型 · 本机试用', subtitle:'同一个微调后的 GGUF，本机 llama-server，/v1/systemone', input:'输入', tab_support:'售后工单', tab_assistant:'助手路由',
       go:'提交给模型', busy:'正在请求本机模型…', hint_in:'模型只看到上面的原话和字段，不知道你选的"场景"。场景只用于在右侧算出"规则说该怎样"，方便对照。',
       resources:'本机 llama-server 进程', output:'模型输出', empty:'点"提交给模型"。每道题显示全部选项的概率，概率最高的即答案；概率已按模型文件内的校准温度缩放。',
       footer:'本页只连接 127.0.0.1 上的本机服务；模型不生成文字，只给每个选项打分。模拟厂商数据，不是真实客户数据。',
       ready:'llama-server 就绪', notready:'llama-server 未就绪', message:'客户原话', utterance:'用户原话', channel:'渠道', product_line:'产品线', region:'地区', warranty_plan:'保修类型',
       days_since_purchase:'购买天数', battery_cycles:'电池循环次数', last_error_code:'诊断代码', bios_version:'BIOS 版本', scenario_s:'这段原话描述的场景（可选，只用于算规则答案）',
       scenario_a:'这句话的意图（可选，只用于算规则答案）', none:'— 不对照规则 —', deadline_today:'客户今天有截止期限', legal_deadline:'有法律时限（隐私类）', has_backup:'客户有备份（SSD 类）',
       foreground_app:'前台应用', power_source:'电源', battery_pct:'电量 %', network:'网络', enterprise_managed:'企业管理设备', camera_in_use:'摄像头在用', external_display:'外接显示器',
       latency:'本次请求耗时', latency_k:'毫秒（客户端计量）', tokens:'输入 token', model:'模型', answer:'模型答案', policy:'规则答案', match:'✓ 一致', mismatch:'✗ 不一致',
       yes:'是 (true)', no:'否 (false)', raw:'原始请求与响应 JSON', ws:'工作集', peak:'峰值工作集', priv:'提交内存', cpu:'CPU 占用', cput:'累计 CPU 时间', secs:'秒',
       reshint:'每 2 秒从 Windows 读一次 llama-server 进程：工作集 = 实际占用的物理内存；提交内存 = 向系统申请的内存；CPU 占用 = 该进程用掉的 CPU 时间 ÷ 采样间隔 ÷ 逻辑处理器数（{n} 个），100% 即全部核心跑满。',
       resna:'进程指标不可用：{r}', q_queue:'派到哪个队列', q_onsite:'能否上门维修', q_urgency:'多紧急', q_tool:'调用哪个工具', q_run:'是否只在本机处理', q_confirm:'执行前是否要确认'},
  en: {title:'Kev decision model · local trial', subtitle:'The same fine-tuned GGUF, local llama-server, /v1/systemone', input:'Input', tab_support:'Support ticket', tab_assistant:'Assistant routing',
       go:'Send to the model', busy:'Asking the local model…', hint_in:'The model sees only the message and fields above; it does not know the "scenario" you pick. The scenario is used only to compute what the policy says, for comparison.',
       resources:'Local llama-server process', output:'Model output', empty:'Press "Send to the model". Each question shows every option\'s probability; the highest is the answer. Probabilities are scaled by the calibration temperature stored in the model file.',
       footer:'This page talks only to the local service on 127.0.0.1; the model generates no text, it scores options. Simulated vendor data, not real customer data.',
       ready:'llama-server ready', notready:'llama-server not ready', message:'Customer message', utterance:'User utterance', channel:'Channel', product_line:'Product line', region:'Region', warranty_plan:'Warranty plan',
       days_since_purchase:'Days since purchase', battery_cycles:'Battery cycles', last_error_code:'Diagnostic code', bios_version:'BIOS version', scenario_s:'Scenario the message describes (optional, policy answer only)',
       scenario_a:'Intent of the utterance (optional, policy answer only)', none:'— no policy comparison —', deadline_today:'Customer has a deadline today', legal_deadline:'Legal deadline (privacy)', has_backup:'Customer has a backup (SSD)',
       foreground_app:'Foreground app', power_source:'Power source', battery_pct:'Battery %', network:'Network', enterprise_managed:'Enterprise-managed device', camera_in_use:'Camera in use', external_display:'External display',
       latency:'Request time', latency_k:'ms (measured at the client)', tokens:'Input tokens', model:'Model', answer:'Model answer', policy:'Policy answer', match:'✓ match', mismatch:'✗ differs',
       yes:'yes (true)', no:'no (false)', raw:'Raw request and response JSON', ws:'Working set', peak:'Peak working set', priv:'Commit charge', cpu:'CPU usage', cput:'CPU time total', secs:'s',
       reshint:'Read from Windows every 2 s for the llama-server process: working set = physical memory in use; commit charge = memory requested from the OS; CPU usage = CPU time used by the process ÷ sampling interval ÷ logical processors ({n}), 100% = every core busy.',
       resna:'Process metrics not available: {r}', q_queue:'Which queue', q_onsite:'Onsite visit allowed?', q_urgency:'How urgent', q_tool:'Which tool', q_run:'Only on the device?', q_confirm:'Confirm before acting?'}
};
const QKEY = {queue:'q_queue', onsite_eligible:'q_onsite', urgency:'q_urgency', tool:'q_tool', run_on_device:'q_run', needs_confirmation:'q_confirm'};
let lang = 'zh', workload = 'support', lastResult = null;
const $ = id => document.getElementById(id);
const t = (k, vars) => { let s = (I18N[lang][k] ?? k); if (vars) for (const [a,b] of Object.entries(vars)) s = s.replace('{'+a+'}', b); return s; };
function applyI18n(){ document.documentElement.lang = lang === 'zh' ? 'zh' : 'en'; document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); }); document.title = t('title'); }
function setLang(l){ lang = l; document.querySelectorAll('.lang button').forEach(b => b.classList.toggle('on', b.id === 'lang-' + l)); const state = $('form').children.length ? readState() : null; const sc = $('scenario') ? $('scenario').value : ''; applyI18n(); renderForm(META[workload].example, state, sc); if (lastResult) render(lastResult); renderRes(lastRes); }
function opt(list, cur){ return list.map(v => `<option ${v===cur?'selected':''}>${v}</option>`).join(''); }
function renderForm(ex, keep, sc){
  const m = META[workload];
  if (workload === 'support'){
    const s = keep || ex.state, d = s.device;
    $('form').innerHTML = `
      <label>${t('message')} <code>message</code><textarea id="message">${s.message}</textarea></label>
      <div class="row">
        <label>${t('channel')} <code>channel</code><select id="channel">${opt(m.fields.channel, s.channel)}</select></label>
        <label>${t('product_line')} <code>product_line</code><select id="product_line">${opt(m.fields.product_line, d.product_line)}</select></label>
        <label>${t('region')} <code>region</code><select id="region">${opt(m.fields.region, d.region)}</select></label>
        <label>${t('warranty_plan')} <code>warranty_plan</code><select id="warranty_plan">${opt(m.fields.warranty_plan, d.warranty_plan)}</select></label>
        <label>${t('days_since_purchase')} <code>days_since_purchase</code><input id="days_since_purchase" type="number" min="0" value="${d.days_since_purchase}"></label>
        <label>${t('battery_cycles')} <code>battery_cycles</code><input id="battery_cycles" type="number" min="0" value="${d.battery_cycles}"></label>
        <label>${t('last_error_code')} <code>last_error_code</code><select id="last_error_code">${opt(m.fields.last_error_code, d.last_error_code)}</select></label>
        <label>${t('bios_version')} <code>bios_version</code><input id="bios_version" value="${d.bios_version}"></label>
      </div>
      <div class="divider"></div>
      <label>${t('scenario_s')}<select id="scenario"><option value="">${t('none')}</option>${Object.entries(m.scenarios).map(([k,v])=>`<option value="${k}" ${k===sc?'selected':''}>${k}: ${v}</option>`).join('')}</select></label>
      <label class="check"><input type="checkbox" id="deadline_today"> ${t('deadline_today')}</label>
      <label class="check"><input type="checkbox" id="legal_deadline"> ${t('legal_deadline')}</label>
      <label class="check"><input type="checkbox" id="has_backup" checked> ${t('has_backup')}</label>`;
  } else {
    const s = keep || ex.state, c = s.context;
    $('form').innerHTML = `
      <label>${t('utterance')} <code>utterance</code><textarea id="utterance">${s.utterance}</textarea></label>
      <div class="row">
        <label>${t('foreground_app')} <code>foreground_app</code><select id="foreground_app">${opt(m.fields.foreground_app, c.foreground_app)}</select></label>
        <label>${t('power_source')} <code>power_source</code><select id="power_source">${opt(m.fields.power_source, c.power_source)}</select></label>
        <label>${t('battery_pct')} <code>battery_pct</code><input id="battery_pct" type="number" min="1" max="100" value="${c.battery_pct}"></label>
        <label>${t('network')} <code>network</code><select id="network">${opt(m.fields.network, c.network)}</select></label>
      </div>
      <label class="check"><input type="checkbox" id="enterprise_managed" ${c.enterprise_managed?'checked':''}> ${t('enterprise_managed')}</label>
      <label class="check"><input type="checkbox" id="camera_in_use" ${c.camera_in_use?'checked':''}> ${t('camera_in_use')}</label>
      <label class="check"><input type="checkbox" id="external_display" ${c.external_display?'checked':''}> ${t('external_display')}</label>
      <div class="divider"></div>
      <label>${t('scenario_a')}<select id="scenario"><option value="">${t('none')}</option>${Object.entries(m.intents).map(([k,v])=>`<option value="${k}" ${k===sc?'selected':''}>${k}: ${v}</option>`).join('')}</select></label>`;
  }
}
function setWorkload(w){ workload = w; lastResult = null; document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('on', b.id === 'tab-' + w)); renderForm(META[w].example); $('out').innerHTML = `<p class="empty">${t('empty')}</p>`; }
function readState(){
  if (workload === 'support') return { channel: $('channel').value, message: $('message').value,
    device: { product_line: $('product_line').value, region: $('region').value, warranty_plan: $('warranty_plan').value,
      days_since_purchase: +$('days_since_purchase').value, battery_cycles: +$('battery_cycles').value,
      last_error_code: $('last_error_code').value, bios_version: $('bios_version').value } };
  return { utterance: $('utterance').value, context: { foreground_app: $('foreground_app').value, power_source: $('power_source').value,
    battery_pct: +$('battery_pct').value, network: $('network').value, enterprise_managed: $('enterprise_managed').checked,
    camera_in_use: $('camera_in_use').checked, external_display: $('external_display').checked } };
}
function readModifiers(){ return workload === 'support' ? { deadline_today: $('deadline_today').checked, legal_deadline: $('legal_deadline').checked, has_backup: $('has_backup').checked } : {}; }
const fmt = p => (100*p).toFixed(1) + '%';
function render(res){
  lastResult = res;
  const m = META[workload], a = res.response.answers, pol = res.policy;
  let html = `<div class="kpis"><div class="kpi"><div class="v">${res.latency_ms}</div><div class="k">${t('latency')} · ${t('latency_k')}</div></div>
    <div class="kpi"><div class="v">${res.response.usage ? res.response.usage.input_tokens : '?'}</div><div class="k">${t('tokens')}</div></div>
    <div class="kpi"><div class="v" style="font-size:14px;word-break:break-all">${res.response.model || '—'}</div><div class="k">${t('model')}</div></div></div>`;
  for (const [qid, q] of Object.entries(m.questions)){
    const ans = a[qid]; let rows = '', pred, probs;
    if (q.type === 'choice'){ probs = ans.probabilities; pred = ans.choice; }
    else if (q.type === 'score'){ probs = ans.probabilities; pred = Object.entries(probs).sort((x,y)=>y[1]-x[1])[0][0]; }
    else { probs = { [t('yes')]: ans.noul, [t('no')]: 1 - ans.noul }; pred = ans.noul >= 0.5; }
    const sorted = Object.entries(probs).sort((x,y)=>y[1]-x[1]); const top = sorted[0][0];
    for (const [k,v] of sorted){
      const name = q.type === 'choice' ? `${k} — ${q.criteria[k]}` : q.type === 'score' ? `${k} — ${q.criteria[+k]}` : k;
      rows += `<div class="bar ${k===top?'top':''}"><span title="${name}">${name}</span><div class="track"><div class="fill" style="width:${Math.max(1,100*v)}%"></div></div><b>${fmt(v)}</b></div>`;
    }
    let verdict = `<div class="verdict"><span>${t('answer')}: <b>${pred}</b></span>`;
    if (pol){ const want = pol[qid]; const ok = String(want) === String(pred); verdict += `<span>${t('policy')}: <b>${want}</b></span><span class="${ok?'ok':'bad'}">${ok?t('match'):t('mismatch')}</span>`; }
    html += `<div class="q"><h3>${t(QKEY[qid]) || qid} <span class="qi">${qid} · ${q.instructions}</span></h3>${rows}${verdict}</div></div>`;
  }
  html += `<details><summary>${t('raw')}</summary><pre>${JSON.stringify({request: res.request, response: res.response}, null, 1)}</pre></details>`;
  $('out').innerHTML = html;
}
let lastRes = null;
function renderRes(r){
  lastRes = r;
  if (!r) return;
  if (!r.available){ $('res').innerHTML = ''; $('reshint').textContent = t('resna', {r: r.reason}); return; }
  const cpu = r.cpu_pct == null ? '—' : r.cpu_pct.toFixed(1) + '%';
  $('res').innerHTML = `
    <div class="kpi"><div class="v">${r.working_set_mib.toLocaleString()} <small>MiB</small></div><div class="k">${t('ws')}</div></div>
    <div class="kpi"><div class="v">${r.peak_working_set_mib.toLocaleString()} <small>MiB</small></div><div class="k">${t('peak')}</div></div>
    <div class="kpi"><div class="v">${r.private_mib.toLocaleString()} <small>MiB</small></div><div class="k">${t('priv')}</div></div>
    <div class="kpi"><div class="v">${cpu}</div><div class="k">${t('cpu')} · PID ${r.pid}</div><div class="meter"><i style="width:${Math.min(100, r.cpu_pct || 0)}%"></i></div></div>
    <div class="kpi"><div class="v">${r.cpu_seconds.toLocaleString()} <small>${t('secs')}</small></div><div class="k">${t('cput')}</div></div>`;
  $('reshint').textContent = t('reshint', {n: r.logical_processors});
}
async function pollRes(){ try { renderRes(await (await fetch('/api/resources')).json()); } catch (e) {} }
async function submit(){
  $('go').disabled = true; $('out').innerHTML = `<p class="empty">${t('busy')}</p>`;
  const timer = setInterval(pollRes, 500);
  try {
    const r = await fetch('/api/ask', { method: 'POST', headers: {'content-type':'application/json'},
      body: JSON.stringify({ workload, state: readState(), scenario: $('scenario').value, modifiers: readModifiers() }) });
    const res = await r.json();
    if (res.error) $('out').innerHTML = `<p class="bad">${res.error}</p>`; else render(res);
  } catch (e) { $('out').innerHTML = `<p class="bad">${e}</p>`; }
  clearInterval(timer); await pollRes();
  $('go').disabled = false;
}
fetch('/api/health').then(r => r.json()).then(h => { const el = $('srv'); el.textContent = (h.ok ? t('ready') : t('notready')) + ' · ' + h.server; el.className = 'pill ' + (h.ok ? 'ok' : 'bad'); });
const params = new URLSearchParams(location.search);
if (params.get('lang') === 'en') { lang = 'en'; document.querySelectorAll('.lang button').forEach(b => b.classList.toggle('on', b.id === 'lang-en')); }
applyI18n();
renderForm(META.support.example);
pollRes(); setInterval(pollRes, 2000);
if (params.get('auto')) {
  if (params.get('workload') === 'assistant') setWorkload('assistant');
  if (params.get('region') && workload === 'support') $('region').value = params.get('region');
  $('scenario').value = params.get('auto');
  submit();
}
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_url = SERVER
    monitor = None

    def log_message(self, *args):
        pass

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/health":
            try:
                with urllib.request.urlopen(self.server_url + "/health", timeout=3) as response:
                    return self.send_json({"ok": response.status == 200, "server": self.server_url})
            except Exception as e:  # noqa: BLE001
                return self.send_json({"ok": False, "server": self.server_url, "error": str(e)[:200]})
        if self.path == "/api/resources":
            return self.send_json(self.monitor.sample())
        body = PAGE.replace("__META__", json.dumps(META, ensure_ascii=False)).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/ask":
            return self.send_json({"error": "not found"}, 404)
        payload = json.loads(self.rfile.read(int(self.headers.get("content-length", "0"))) or b"{}")
        workload, state = payload.get("workload"), payload.get("state")
        if workload not in META or not isinstance(state, dict):
            return self.send_json({"error": "workload must be support or assistant, with a state object"}, 400)
        try:
            response, latency_ms, request_body = ask_model(self.server_url, workload, state)
        except urllib.error.URLError as e:
            return self.send_json({"error": f"llama-server unreachable at {self.server_url}: {e.reason}. Start it with README step A1 or --start-server."})
        except Exception as e:  # noqa: BLE001
            return self.send_json({"error": f"request failed: {str(e)[:300]}"})
        try:
            policy = policy_answer(workload, state, payload.get("scenario") or "", payload.get("modifiers") or {})
        except Exception as e:  # noqa: BLE001
            policy = None
            response.setdefault("_policy_error", str(e)[:200])
        self.send_json({"request": request_body, "response": response, "latency_ms": latency_ms, "policy": policy})


def start_server(engine, model, port):
    args = [engine, "-m", model, "--alias", "contoso-kev-0.8b-ftcf", "--host", "127.0.0.1", "--port", str(port),
            "-c", "8192", "-b", "2048", "-ub", "2048", "-ngl", "0", "--cache-ram", "0", "--offline"]
    log = open(ROOT / "验证结果" / "try_ui_llama_server.log", "ab")
    process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.time() + 300
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"llama-server exited with code {process.returncode}; see {log.name}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                if response.status == 200:
                    return process
        except Exception:  # noqa: BLE001
            time.sleep(1)
    process.kill()
    raise SystemExit("llama-server did not become healthy within 300 s")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8090, help="port of this page on 127.0.0.1")
    ap.add_argument("--server", default=SERVER, help="llama-server base URL")
    ap.add_argument("--start-server", action="store_true", help="start llama-server here and stop it when this page exits")
    ap.add_argument("--engine", default=os.environ.get("KEV_ENGINE", r"C:\Tools\llama.cpp\b11935-cpu\llama-server.exe"))
    ap.add_argument("--model", default=os.environ.get("KEV_MODEL", r"C:\Tools\models\contoso-kev\Contoso-Kev-0.8B-FTcf-Q8_0.gguf"))
    a = ap.parse_args()
    process = None
    server_port = int(a.server.rsplit(":", 1)[-1])
    if a.start_server:
        for path in (a.engine, a.model):
            if not Path(path).is_file():
                raise SystemExit(f"not found: {path}")
        process = start_server(a.engine, a.model, server_port)
        print(f"llama-server started (pid {process.pid}) on {a.server}")
    Handler.server_url = a.server
    Handler.monitor = ProcessMonitor(server_port)
    if process is not None:
        Handler.monitor.pid = process.pid
    httpd = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"open http://127.0.0.1:{a.port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
            print("llama-server stopped")


if __name__ == "__main__":
    main()
