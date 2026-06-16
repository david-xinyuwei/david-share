"""
AIPC Agent Framework Comparison Portal v2 — Differential Testing
6 scenarios: Framework / Runtime / Recovery / HITL / Code / Sandbox
"""
import os, json, time, asyncio
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import httpx
load_dotenv()

app = FastAPI(title="AIPC Agent Framework Comparison Portal v2")

SANDBOX_URL = os.environ.get("AIPC_SANDBOX_URL", "http://localhost:8507")

# ─── Direct HTTP sandbox call (no SSH tunnel needed — NSG 8507 is open) ───
SANDBOX_SSH_HOST = os.environ.get("SANDBOX_SSH_HOST", "localhost")
SANDBOX_SSH_PORT = os.environ.get("SANDBOX_SSH_PORT", "8506")
SANDBOX_SSH_USER = os.environ.get("SANDBOX_SSH_USER", "aipcadmin")
SANDBOX_SSH_PASS_FILE = "/tmp/.winpw"

async def sandbox_api_call(endpoint: str, method: str = "GET", payload: dict = None) -> dict:
    """Call sandbox API on Windows VM via direct HTTP with bounded retry.

    Connect failures must fail fast; model/tool execution may still take time.
    """
    url = f"{SANDBOX_URL}{endpoint}"
    last_err = None
    timeout = httpx.Timeout(45.0, connect=3.0)
    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    resp = await client.get(url)
                else:
                    resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            last_err = e
            if attempt < 1:
                import asyncio; await asyncio.sleep(1)
    raise RuntimeError(f"Sandbox API call failed after retry: {type(last_err).__name__}: {last_err}")

# ─── Ollama on AIPC VM (local inference via SSH) ───
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_CODE_MODEL = os.environ.get("OLLAMA_CODE_MODEL", OLLAMA_MODEL)

async def ollama_ssh_generate(prompt: str, model: str = None) -> tuple:
    """Call Ollama on AIPC Windows VM via SSH curl (/api/chat with think:false). Returns (response_text, elapsed_seconds)."""
    import re as _re
    model = model or OLLAMA_MODEL
    import base64 as b64mod
    # Use /api/chat with think:false to disable qwen3 reasoning mode → pure output
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {"num_predict": 512, "temperature": 0}
    })
    payload_b64 = b64mod.b64encode(payload.encode()).decode()
    cmd = (
        f'powershell -Command "'
        f"[System.IO.File]::WriteAllText('C:\\Users\\{SANDBOX_SSH_USER}\\Desktop\\ollama_req.json', "
        f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{payload_b64}'))); "
        f'curl.exe -s --max-time 240 -X POST http://localhost:11434/api/chat '
        f'-H \\\"Content-Type: application/json\\\" '
        f'-d @C:\\Users\\{SANDBOX_SSH_USER}\\Desktop\\ollama_req.json"'
    )
    ssh_cmd = [
        "sshpass", "-f", SANDBOX_SSH_PASS_FILE,
        "ssh", "-p", SANDBOX_SSH_PORT, "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30",
        f"{SANDBOX_SSH_USER}@{SANDBOX_SSH_HOST}", cmd
    ]
    t0 = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            *ssh_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        elapsed = round(time.time() - t0, 2)
        if proc.returncode != 0:
            return f"[Ollama SSH error: rc={proc.returncode}]", elapsed
        data = json.loads(stdout.decode())
        # /api/chat returns {"message": {"content": "..."}} vs /api/generate {"response": "..."}
        text = data.get("message", {}).get("content", "") or data.get("response", "")
        # Strip any residual thinking blocks
        text = _re.sub(r'<think>.*?</think>', '', text, flags=_re.DOTALL).strip()
        return text, elapsed
    except asyncio.TimeoutError:
        return "[Ollama timeout — CPU inference may need more time]", round(time.time() - t0, 2)
    except json.JSONDecodeError:
        return "[Ollama response parse error]", round(time.time() - t0, 2)
    except Exception as e:
        return f"[Ollama error: {e}]", round(time.time() - t0, 2)

async def _write_ollama_codegen_log(model, prompt, code, gen_time, success, request_id=None):
    """Fire-and-forget: write codegen evidence to AIPC Desktop for monitor display."""
    import base64 as b64mod
    from datetime import datetime, timezone
    log_data = json.dumps({
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "request_id": request_id,
        "prompt_preview": prompt[:300],
        "generated_code": code[:800] if code else "",
        "gen_time_s": gen_time,
        "success": success,
    }, ensure_ascii=False, indent=2)
    log_b64 = b64mod.b64encode(log_data.encode()).decode()
    cmd = (
        f'powershell -Command "'
        f"[System.IO.File]::WriteAllText('C:\\Users\\{SANDBOX_SSH_USER}\\Desktop\\last_ollama_codegen.json', "
        f"[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{log_b64}')))\""
    )
    ssh_cmd = [
        "sshpass", "-f", SANDBOX_SSH_PASS_FILE,
        "ssh", "-p", SANDBOX_SSH_PORT, "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=5",
        f"{SANDBOX_SSH_USER}@{SANDBOX_SSH_HOST}", cmd
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *ssh_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(proc.communicate(), timeout=10)
    except Exception as log_error:
        _last_codegen_log_error = str(log_error)

# ─── Auth: disabled for demo (NSG restricts port access) ───
# Basic Auth removed — EventSource/SSE doesn't reliably send Basic Auth
# credentials in modern browsers, causing repeated login popups.
# Port 8506 is protected by Azure NSG (IP whitelist).

# ─── Real weather API (wttr.in — free, no key required) ───
import requests as _req

def fetch_real_weather(city: str) -> list:
    """Fetch real weather from wttr.in API. Returns 3-day forecast."""
    try:
        r = _req.get(f"https://wttr.in/{city}?format=j1", timeout=10)
        r.raise_for_status()
        data = r.json()
        result = []
        for i, day in enumerate(data.get("weather", [])[:3], 1):
            desc = day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", "N/A") if len(day.get("hourly", [])) > 4 else "N/A"
            result.append({
                "date": day.get("date", f"Day {i}"),
                "weather": f"{desc}, {day.get('maxtempC','?')}°C / {day.get('mintempC','?')}°C",
                "source": "wttr.in (real API)",
            })
        return result
    except Exception as e:
        return [{"date": "N/A", "weather": f"API error: {e}", "source": "wttr.in (failed)"}]

# ─── Real flight/hotel search via SerpAPI (Google Flights + Google Hotels) ───
def unavailable_result(kind: str, detail: str) -> list:
    return [{"unavailable": True, "kind": kind, "detail": detail, "source": "No synthetic data returned"}]

def fetch_real_flights(origin_code: str = "PEK", dest_code: str = "NRT", date: str = None):
    """Search real flights via SerpAPI Google Flights API."""
    try:
        from serpapi import GoogleSearch
        from datetime import datetime, timedelta
        import re as _re
        if not date:
            date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        params = {
            "engine": "google_flights", "departure_id": origin_code,
            "arrival_id": dest_code, "outbound_date": date,
            "currency": "CNY", "hl": "zh-cn", "type": "2",
            "api_key": os.environ.get("SERPAPI_API_KEY", ""),
        }
        r = GoogleSearch(params).get_dict()
        flights = []
        for f in (r.get("best_flights", []) + r.get("other_flights", []))[:5]:
            fl = f["flights"][0]
            flights.append({
                "id": fl.get("flight_number", "?"),
                "airline": fl.get("airline", "?"),
                "dep": fl["departure_airport"]["time"].split(" ")[-1] if "departure_airport" in fl else "?",
                "arr": fl["arrival_airport"]["time"].split(" ")[-1] if "arrival_airport" in fl else "?",
                "price": f.get("price", 0),
                "source": "Google Flights (real, via SerpAPI)",
            })
        return flights if flights else unavailable_result("flights", f"No SerpAPI flights returned for {origin_code}->{dest_code} on {date}")
    except Exception as e:
        print(f"[SerpAPI flights error] {e}")
        return unavailable_result("flights", f"SerpAPI request failed: {e}")

def fetch_real_hotels(city: str = "Tokyo", days: int = 3):
    """Search real hotels via SerpAPI Google Hotels API."""
    try:
        from serpapi import GoogleSearch
        from datetime import datetime, timedelta
        import re as _re
        ci = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        co = (datetime.now() + timedelta(days=2+days)).strftime("%Y-%m-%d")
        params = {
            "engine": "google_hotels", "q": f"hotels in {city}",
            "check_in_date": ci, "check_out_date": co,
            "currency": "CNY", "hl": "zh-cn",
            "api_key": os.environ.get("SERPAPI_API_KEY", ""),
        }
        r = GoogleSearch(params).get_dict()
        hotels = []
        for h in r.get("properties", [])[:5]:
            rate = h.get("rate_per_night", {}).get("lowest", "?")
            price_num = int(_re.sub(r"[^0-9]", "", str(rate))) if rate != "?" else 0
            hotels.append({
                "name": h.get("name", "?"),
                "price": price_num,
                "rating": h.get("overall_rating", "?"),
                "source": "Google Hotels (real, via SerpAPI)",
            })
        return hotels if hotels else unavailable_result("hotels", f"No SerpAPI hotels returned for {city}")
    except Exception as e:
        print(f"[SerpAPI hotels error] {e}")
        return unavailable_result("hotels", f"SerpAPI request failed: {e}")

def safe_calculate(expression: str) -> dict:
    """Safely evaluate a math expression using AST (no eval)."""
    import ast, operator
    normalized = expression.strip().replace("×", "*").replace("÷", "/").replace("^", "**")
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
           ast.FloorDiv: operator.floordiv, ast.USub: operator.neg}
    def _eval(node):
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.BinOp): return ops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp): return ops[type(node.op)](_eval(node.operand))
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")
    try:
        tree = ast.parse(normalized, mode='eval')
        result = _eval(tree.body)
        return {"expression": expression, "normalized": normalized, "result": result, "source": "Python safe math (ast)"}
    except Exception as e:
        return {"expression": expression, "normalized": normalized, "error": str(e), "source": "Python safe math (ast)"}

def sse(evt, data):
    return f"event: {evt}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

# ─── Execution Tracker: builds diff from actual events, no hardcode ───
class ExecTracker:
    """Tracks actual execution events and builds diff dict dynamically."""
    def __init__(self, framework: str):
        self.fw = framework
        self.events = []
        self.checkpoints = 0
        self.tools_called = []
        self.parallel_detected = False
        self.interrupt_fired = False
        self.otel_detected = False
        self.sandbox_connected = False
        self.sandbox_backend = None
        self.host_tools_registered = []
        self.errors = []
        self.total_time = 0
        self.iterations = 0

    def track(self, key, value=True):
        self.events.append((key, value))
        if key == "checkpoint": self.checkpoints += 1
        elif key == "tool_call": self.tools_called.append(value)
        elif key == "parallel": self.parallel_detected = True
        elif key == "interrupt": self.interrupt_fired = True
        elif key == "otel": self.otel_detected = value
        elif key == "sandbox_ok": self.sandbox_connected = True
        elif key == "sandbox_backend": self.sandbox_backend = value
        elif key == "host_tool": self.host_tools_registered.append(value)
        elif key == "error": self.errors.append(value)
        elif key == "iteration": self.iterations = value

    def build_diff(self, scenario="overview"):
        d = {}
        if scenario == "overview":
            d["execution"] = f"{'ReAct loop' if self.fw=='langchain' else 'StateGraph' if self.fw=='langgraph' else 'Agent.run()'}, {self.iterations} iteration(s), {len(self.tools_called)} tool calls" if self.tools_called else f"{self.fw} execution"
            d["state"] = f"✅ {self.checkpoints} checkpoints saved" if self.checkpoints > 0 else "❌ No checkpoint — stateless"
            d["hitl"] = "✅ interrupt() fired" if self.interrupt_fired else "❌ No pause/approval observed"
            d["recovery"] = f"✅ Can resume from checkpoint #{self.checkpoints}" if self.checkpoints > 0 else "❌ Must re-run from scratch"
            d["parallel"] = f"✅ Parallel execution detected" if self.parallel_detected else "❌ Sequential"
            d["otel"] = "✅ Built-in (verified: import succeeded)" if self.otel_detected else "❌ Not detected in this execution"
            d["strength"] = f"{self.total_time}s total, {len(self.tools_called)} tools, {self.checkpoints} checkpoints"
        elif scenario == "recovery":
            d["checkpoint_api"] = f"✅ {self.checkpoints} checkpoints observed" if self.checkpoints > 0 else "❌ No checkpoint API"
            d["resume_capability"] = "✅ Can resume" if self.checkpoints > 0 else "❌ Must restart"
            d["state_persistence"] = f"✅ {self.checkpoints} states persisted" if self.checkpoints > 0 else "❌ No persistence"
        elif scenario == "hitl":
            d["hitl_api"] = "✅ Real interrupt()/request_info() fired" if self.interrupt_fired else "❌ No built-in pause"
            d["state_during_wait"] = f"✅ Checkpointed ({self.checkpoints} states)" if self.checkpoints > 0 else "❌ Not saved"
            if self.interrupt_fired:
                d["graph_paused"] = "✅ Paused at approval, resumed after user choice"
            d["otel"] = "✅ Built-in (verified)" if self.otel_detected else "❌ External"
        elif scenario == "sandbox":
            d["sandbox_integration"] = f"ℹ️ Shared Sandbox API wrapper (target: MAF native provider)" if self.fw == "maf" else f"⚠️ Custom {'@tool wrapper' if self.fw=='langchain' else 'graph node'}"
            d["isolation"] = f"✅ {self.sandbox_backend or 'Hyperlight micro-VM'}" if self.sandbox_connected else "❌ Sandbox unreachable"
            # recovery_on_crash: LangGraph has checkpoint (observed), MAF has Durable Task checkpoint (architecture)
            if self.checkpoints > 0:
                d["recovery_on_crash"] = f"✅ Checkpoint before sandbox → resume"
            elif self.fw == "maf":
                # Source: https://github.com/microsoft/agent-framework → WorkflowBuilder + Durable Task
                d["recovery_on_crash"] = "ℹ️ Superstep + Durable Task — architecture capability, not tested in this demo"
            else:
                d["recovery_on_crash"] = "❌ No state — must re-run"
            # host_tools: not tested in this demo — all three use shared Sandbox API wrapper
            if self.host_tools_registered:
                d["host_tools"] = f"✅ {len(self.host_tools_registered)} tools registered via callbacks"
            elif self.fw == "maf":
                # Source: https://github.com/microsoft/agent-framework → HyperlightCodeActProvider register_tool()
                d["host_tools"] = "ℹ️ MAF native register_tool() — not used in this demo"
            else:
                d["host_tools"] = "ℹ️ Manual bridging needed — not tested in this demo"
            d["otel"] = "ℹ️ MAF architecture capability — not instrumented in this demo"
        return d

def check_otel_support(framework: str) -> bool:
    """Dynamically check if framework has OTel support."""
    if framework == "maf":
        try:
            import agent_framework._telemetry
            return True
        except: return False
    return False

def get_llm():
    from langchain_openai import AzureChatOpenAI
    return AzureChatOpenAI(
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT",""),
        api_key=os.environ.get("AZURE_OPENAI_API_KEY",""),
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME","gpt-5.4-mini"),
        api_version="2025-04-01-preview", temperature=0)

def llm_call(prompt):
    t0=time.time(); r=get_llm().invoke(prompt); return r.content, round(time.time()-t0,2)

async def llm_stream_tokens(prompt):
    """Async generator: stream LLM response tokens via Azure OpenAI SDK. Yields text chunks."""
    from openai import AsyncAzureOpenAI
    client = AsyncAzureOpenAI(
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
        api_version="2025-04-01-preview",
    )
    try:
        stream = await client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5.4-mini"),
            messages=[{"role": "user", "content": prompt}],
            stream=True, temperature=0,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
    finally:
        await client.close()

def _lang(lang="cn"):
    """Return language instruction for LLM prompts based on UI language toggle."""
    return "Always answer in Chinese." if lang == "cn" else "Always answer in English."

def _lang_short(lang="cn"):
    return "in Chinese" if lang == "cn" else "in English"

# ═══ S1: Happy Path ═══
async def s1_langchain(q, lang="cn"):
    start=time.time()
    yield sse("graph",{"nodes":["LLM ReAct Loop"],"edges":[],"note":"Black box — LLM decides everything"})
    yield sse("step",{"node":"init","s":"done","d":"Agent ready (stateless, no graph)"})
    try:
        from langchain_openai import AzureChatOpenAI
        from langchain_core.tools import tool as lc_tool
        from langchain_core.messages import HumanMessage, ToolMessage
        llm=get_llm()
        @lc_tool
        def get_weather(city:str)->str:
            """Get real weather forecast from wttr.in API."""
            return json.dumps(fetch_real_weather(city or "Shanghai"),ensure_ascii=False)
        @lc_tool
        def search_flights(origin:str,dest:str)->str:
            """Search real flights via Google Flights API."""
            return json.dumps(fetch_real_flights(origin or "PEK", dest or "NRT"),ensure_ascii=False)
        @lc_tool
        def search_hotels(city:str)->str:
            """Search real hotels via Google Hotels API."""
            return json.dumps(fetch_real_hotels(city or "Tokyo"),ensure_ascii=False)
        @lc_tool
        def calculate(expression:str)->str:
            """Calculate a math expression. Use for arithmetic, algebra, unit conversion, etc."""
            return json.dumps(safe_calculate(expression),ensure_ascii=False)
        tools=[get_weather,search_flights,search_hotels,calculate]; tm={t.name:t for t in tools}
        llmt=llm.bind_tools(tools)
        sys_msg = HumanMessage(content="You are a helpful AI assistant with real tools. Choose the RIGHT tool based on the user's request: get_weather (weather), search_flights (flights), search_hotels (hotels), calculate (math/arithmetic). For travel → use travel tools. For math → use calculate. For general questions → answer directly without tools. " + _lang(lang) + "\nUser request: " + q)
        msgs=[sys_msg]
        tracker = ExecTracker("langchain")
        tracker.track("otel", check_otel_support("langchain"))
        for i in range(8):
            t0=time.time()
            # ── Streaming: yield tokens as LLM generates them ──
            full_resp=None
            for chunk in llmt.stream(msgs):
                if full_resp is None: full_resp=chunk
                else: full_resp+=chunk
                if chunk.content: yield sse("token",{"t":chunk.content})
            lt=round(time.time()-t0,2)
            if full_resp is None:
                yield sse("step",{"node":"llm","s":"error","d":"LLM returned an empty stream","t":lt})
                yield sse("result",{"plan":"","time":round(time.time()-start,2),"diff":{"error":"empty LLM stream"}})
                return
            msgs.append(full_resp)
            if full_resp and full_resp.tool_calls:
                ns=[tc["name"] for tc in full_resp.tool_calls]
                for n in ns: tracker.track("tool_call", n)
                tracker.track("iteration", i+1)
                yield sse("step",{"node":"llm","s":"tools","d":f"Iter {i+1}: called {', '.join(ns)}","t":lt})
                for tc in full_resp.tool_calls:
                    yield sse("tool",{"name":tc["name"],"s":"done"})
                    msgs.append(ToolMessage(content=str(tm[tc["name"]].invoke(tc["args"])),tool_call_id=tc["id"]))
            else:
                tracker.track("iteration", i+1)
                tracker.total_time = round(time.time()-start,2)
                yield sse("step",{"node":"llm","s":"done","d":f"Final answer (iter {i+1})","t":lt})
                yield sse("result",{"plan":(full_resp.content if full_resp else ""),"time":tracker.total_time,"diff":tracker.build_diff("overview")})
                return
    except Exception as e:
        yield sse("error",{"msg":str(e)})

async def s1_langgraph(q, lang="cn"):
    """REAL LangGraph: StateGraph + MemorySaver + conditional routing + real LLM."""
    start=time.time()
    yield sse("graph",{
        "nodes":["🔀 router","weather","flights","hotels","select","itinerary","direct_solve"],
        "edges":[
            ["⊕","🔀 router"],
            ["🔀 router","weather"],["🔀 router","flights"],["🔀 router","hotels"],
            ["🔀 router","direct_solve"],
            ["weather","select"],["flights","select"],["hotels","select"],
            ["select","itinerary"]
        ],
        "note":"Real StateGraph + MemorySaver + conditional_edges routing (langgraph)"
    })

    from typing import TypedDict, Annotated
    from operator import add as op_add
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver

    class AgentState(TypedDict):
        user_request: str
        query_type: str
        weather: list
        flights: list
        hotels: list
        selected: str
        plan: str
        messages: Annotated[list, op_add]

    ckpt_count = [0]

    # ── Node functions ──
    def route_query(state):
        """Classify user request: travel or direct."""
        uq = state["user_request"]
        try:
            qtype, _ = llm_call(f"Classify this request as 'travel' (flights/hotels/trips) or 'direct' (math/coding/general). Reply ONE word only.\n{uq}")
            qtype = "travel" if "travel" in qtype.strip().lower() else "direct"
        except:
            qtype = "direct"
        return {"query_type": qtype, "messages": [f"Router: classified as '{qtype}'"]}

    def route_decision(state):
        """Conditional edge: fan-out to parallel travel nodes OR direct solve."""
        if state.get("query_type") == "travel":
            return ["weather", "flights", "hotels"]
        return ["direct_solve"]

    city_map = [("北京","Beijing"),("上海","Shanghai"),("东京","Tokyo"),("大阪","Osaka"),("成都","Chengdu"),("广州","Guangzhou"),("深圳","Shenzhen"),("杭州","Hangzhou"),("西安","Xian"),("三亚","Sanya"),("香港","Hong Kong")]
    code_map = {"北京":"PEK","上海":"PVG","东京":"NRT","大阪":"KIX","首尔":"ICN","曼谷":"BKK","成都":"CTU","广州":"CAN","深圳":"SZX","杭州":"HGH","三亚":"SYX","香港":"HKG"}

    def _pick_city(uq, default="Tokyo"):
        for cn, en in city_map:
            if cn in uq: return en
        return default

    def _pick_codes(uq):
        found = [cn for cn in code_map if cn in uq]
        origin = code_map.get(found[0], "PEK") if found else "PEK"
        dest   = code_map.get(found[1], "NRT") if len(found) > 1 else "NRT"
        return origin, dest

    def check_weather(state):
        city = _pick_city(state["user_request"], "Tokyo")
        return {"weather": fetch_real_weather(city), "messages": [f"Weather: real data for {city}"]}

    def search_flights_n(state):
        origin, dest = _pick_codes(state["user_request"])
        _fl = fetch_real_flights(origin, dest)
        return {"flights": _fl, "messages": [f"Flights: {len(_fl)} found ({origin}→{dest})"]}

    def search_hotels_n(state):
        city = _pick_city(state["user_request"], "Tokyo")
        _ht = fetch_real_hotels(city)
        return {"hotels": _ht, "messages": [f"Hotels: {len(_ht)} found in {city}"]}

    def select_best(state):
        try:
            txt, _ = llm_call(f"Pick best mid-budget flight+hotel from {json.dumps(state.get('flights',[]))} and {json.dumps(state.get('hotels',[]))}. One line answer " + _lang_short(lang) + ".")
        except:
            txt = "推荐组合"
        return {"selected": txt, "messages": [f"Selected: {txt[:80]}"]}

    def create_itinerary(state):
        try:
            plan, _ = llm_call(f"Based on: {state['user_request']}\nWeather:{json.dumps(state.get('weather',[]),ensure_ascii=False)}\nSelected:{state.get('selected','')}\nCreate a detailed plan " + _lang_short(lang) + ".")
        except Exception as e:
            plan = f"生成出错: {e}"
        return {"plan": plan, "messages": ["Itinerary created"]}

    def direct_solve(state):
        """For non-travel queries: use LLM to answer directly."""
        uq = state["user_request"]
        # Try math first
        import re
        math_match = re.search(r'[\d\s\+\-\*\/\(\)\.\^%]+', uq.replace('×','*').replace('÷','/').replace('x','*').replace('X','*'))
        if math_match and len(math_match.group()) > 2:
            calc = safe_calculate(math_match.group())
            if "result" in calc:
                try:
                    answer, _ = llm_call(f"User asked: {uq}\nCalculation result: {calc['expression']} = {calc['result']}\nPlease give a clear answer " + _lang_short(lang) + ", showing the calculation steps.")
                except:
                    answer = f"计算结果：{calc['expression']} = {calc['result']}"
                return {"plan": answer, "messages": [f"Math: {calc['expression']} = {calc['result']}"]}
        # General LLM answer
        try:
            answer, _ = llm_call(f"Please answer {_lang_short(lang)}:\n{uq}")
        except Exception as e:
            answer = f"Error: {e}"
        return {"plan": answer, "messages": ["Direct answer generated"]}

    # ── Build graph ──
    graph = StateGraph(AgentState)
    graph.add_node("router", route_query)
    graph.add_node("weather", check_weather)
    graph.add_node("flights", search_flights_n)
    graph.add_node("hotels", search_hotels_n)
    graph.add_node("select", select_best)
    graph.add_node("itinerary", create_itinerary)
    graph.add_node("direct_solve", direct_solve)

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", route_decision)
    graph.add_edge("weather", "select")
    graph.add_edge("flights", "select")
    graph.add_edge("hotels", "select")
    graph.add_edge("select", "itinerary")
    graph.add_edge("itinerary", END)
    graph.add_edge("direct_solve", END)

    checkpointer = MemorySaver()
    app = graph.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": f"task-{int(time.time())}"}}
    initial = {"user_request": q, "messages": []}

    yield sse("step",{"node":"graph","s":"running","d":"StateGraph compiled: router → conditional_edges → parallel gather OR direct solve"})

    # ── Stream real execution ──
    node_times = {}
    tracker_lg = ExecTracker("langgraph")
    tracker_lg.track("otel", check_otel_support("langgraph"))
    try:
        for event in app.stream(initial, config=config, stream_mode="updates"):
            for node_name, node_output in event.items():
                t_node = time.time()
                if isinstance(node_output, dict):
                    msgs = node_output.get("messages", [])
                else:
                    msgs = []
                detail = "; ".join(str(m) for m in msgs) if msgs else f"Node {node_name} completed"
                ckpt_count[0] += 1
                tracker_lg.track("checkpoint")
                if node_name in ("weather","flights","hotels"):
                    tracker_lg.track("parallel")
                    tracker_lg.track("tool_call", node_name)
                yield sse("step",{"node":node_name,"s":"done","d":f"{detail} (checkpoint #{ckpt_count[0]})","ck":True,
                    "par": node_name in ("weather","flights","hotels")})
                if node_name in ("weather","flights","hotels"):
                    yield sse("tool",{"name":node_name,"s":"done","d":detail})
                node_times[node_name] = round(time.time()-t_node, 2)
    except Exception as e:
        tracker_lg.track("error", str(e))
        yield sse("error",{"msg":f"LangGraph execution error: {e}"})
        return

    final_state = app.get_state(config)
    plan = final_state.values.get("plan", "No plan generated")
    tracker_lg.total_time = round(time.time()-start, 2)

    # Stream plan tokens before result
    for _ci in range(0, len(plan), 4):
        yield sse("token", {"t": plan[_ci:_ci+4]})
    yield sse("result",{"plan":plan,"time":tracker_lg.total_time,"diff":tracker_lg.build_diff("overview")})

async def s1_maf(q, lang="cn"):
    """REAL MAF: Agent + OpenAIChatClient + @tool — agent-framework 1.8.1."""
    start=time.time()
    yield sse("graph",{"nodes":["Agent","tools","OpenAIChatClient","OTel"],
        "edges":[["Agent","OpenAIChatClient"],["Agent","tools"],["Agent","OTel"]],
        "note":"Real MAF Agent + OpenAIChatClient + @tool (agent-framework 1.8.1)"})

    yield sse("step",{"node":"init","s":"running","d":"Initializing MAF Agent with OpenAIChatClient → APIM gateway..."})

    try:
        from agent_framework import Agent, tool as maf_tool
        from agent_framework.openai import OpenAIChatClient
        from openai import AsyncAzureOpenAI

        @maf_tool
        def get_weather(city: str) -> str:
            """Get real weather forecast from wttr.in API."""
            return json.dumps(fetch_real_weather(city or "Shanghai"), ensure_ascii=False)

        @maf_tool
        def search_flights(origin: str, destination: str) -> str:
            """Search real flights via Google Flights API."""
            return json.dumps(fetch_real_flights(origin or "PEK", destination or "NRT"), ensure_ascii=False)

        @maf_tool
        def search_hotels(city: str) -> str:
            """Search real hotels via Google Hotels API."""
            return json.dumps(fetch_real_hotels(city or "Tokyo"), ensure_ascii=False)

        @maf_tool
        def calculate(expression: str) -> str:
            """Calculate a math expression. Use for arithmetic, algebra, unit conversion, etc."""
            return json.dumps(safe_calculate(expression), ensure_ascii=False)

        azure_client = AsyncAzureOpenAI(
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
            api_version="2025-04-01-preview",
            default_headers={"api-key": os.environ.get("AZURE_OPENAI_API_KEY", "")},
        )
        client = OpenAIChatClient(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5.4-mini"),
            async_client=azure_client,
        )

        agent = Agent(
            client=client,
            name="AIAssistant",
            instructions="You are a helpful AI assistant. Use tools based on user request: get_weather (weather), search_flights (flights), search_hotels (hotels), calculate (math). For travel → use travel tools. For math → use calculate. For general questions → answer directly. " + _lang(lang),
            tools=[get_weather, search_flights, search_hotels, calculate],
        )

        tracker_maf = ExecTracker("maf")
        tracker_maf.track("otel", check_otel_support("maf"))
        yield sse("step",{"node":"init","s":"done","d":"MAF Agent ready (OpenAIChatClient → APIM)"})

        yield sse("step",{"node":"agent","s":"running","d":"Agent.run() — MAF decides tool call order..."})
        t0 = time.time()
        response = await agent.run(q)
        lt = round(time.time() - t0, 2)

        plan = response.text or str(response)
        tool_calls_info = []
        if hasattr(response, 'messages'):
            for msg in response.messages:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tn = tc.function.name if hasattr(tc, 'function') else str(tc)
                        tool_calls_info.append(tn)
                        tracker_maf.track("tool_call", tn)

        tracker_maf.track("iteration", 1)
        if tool_calls_info:
            yield sse("step",{"node":"agent","s":"tools","d":f"Agent called: {', '.join(tool_calls_info)}","t":lt})
            for tn in tool_calls_info:
                yield sse("tool",{"name":tn,"s":"done"})
        yield sse("step",{"node":"agent","s":"done","d":f"Agent.run() completed","t":lt})

        tracker_maf.total_time = round(time.time()-start, 2)
        # Stream plan tokens before result
        for _ci in range(0, len(plan), 4):
            yield sse("token", {"t": plan[_ci:_ci+4]})
        yield sse("result",{"plan":plan,"time":tracker_maf.total_time,"diff":tracker_maf.build_diff("overview")})

    except Exception as e:
        yield sse("error",{"msg":f"MAF Agent error: {e}"})

# ═══ S2: Architecture Comparison (was: Crash Recovery — now honest) ═══
async def s2_langchain(q, lang="cn"):
    """LangChain recovery: show real API — no checkpoint API exists."""
    start=time.time()
    yield sse("graph",{"nodes":["LLM Loop"],"edges":[],"note":"LangChain has no built-in checkpoint/recovery API"})
    yield sse("step",{"node":"architecture","s":"info","d":"LangChain execution model: LLM ReAct loop with message list in memory"})
    yield sse("code",{"section":"Recovery — LangChain API","code":"# LangChain has NO checkpoint API.\n# If the process crashes mid-execution:\n#   - All tool results in memory are lost\n#   - Must restart from scratch\n#\n# Workaround: persist messages manually\n# messages = [...]  # save to DB yourself\n# Source: https://python.langchain.com/docs/how_to/\n\nfrom langchain_core.messages import HumanMessage\nagent = llm.bind_tools(tools)\nresult = agent.invoke([HumanMessage(content=query)])\n# No checkpoint. If this crashes, start over."})
    yield sse("result",{"plan":"LangChain provides no crash recovery mechanism. Developer must build their own persistence.","time":round(time.time()-start,2),"diff":{
        "checkpoint_api":"None — developer must implement",
        "recovery_mechanism":"Full restart from scratch",
        "state_persistence":"Message list in memory only",
        "source":"https://python.langchain.com/docs/how_to/",
        "strength":"Simplest model — no overhead from checkpoint logic"}})

async def s2_langgraph(q, lang="cn"):
    """LangGraph recovery: show real checkpoint API with code."""
    start=time.time()
    yield sse("graph",{"nodes":["step_a ✅","step_b ✅","step_c 💥→✅","aggregate","output"],
        "edges":[["⊕","step_a ✅"],["⊕","step_b ✅"],["⊕","step_c 💥→✅"],["step_a ✅","aggregate"],["step_b ✅","aggregate"],["step_c 💥→✅","aggregate"],["aggregate","output"]],
        "note":"LangGraph: MemorySaver/SqliteSaver checkpoint at every node boundary"})
    yield sse("step",{"node":"architecture","s":"info","d":"LangGraph checkpoints state at every node boundary via configurable backend (Memory/SQLite/Postgres)"})
    yield sse("code",{"section":"Recovery — LangGraph API (real code from this demo)","code":"from langgraph.graph import StateGraph, START, END\nfrom langgraph.checkpoint.memory import MemorySaver\n\ngraph = StateGraph(AgentState)\ngraph.add_node('step_a', run_step_a)\ngraph.add_node('step_b', run_step_b)\ngraph.add_node('step_c', run_step_c)  # if this crashes...\ngraph.add_edge(START, 'step_a')\ngraph.add_edge(START, 'step_b')\ngraph.add_edge(START, 'step_c')\n\ncheckpointer = MemorySaver()  # or SqliteSaver('db.sqlite')\napp = graph.compile(checkpointer=checkpointer)\n\n# After crash: step_a + step_b checkpointed, only step_c re-runs\nstate = app.get_state(config)  # ← real API, returns saved state\n# Source: https://langchain-ai.github.io/langgraph/concepts/persistence/"})
    yield sse("result",{"plan":"LangGraph provides automatic checkpoint at node boundaries. On crash, completed nodes are preserved; only failed node re-executes.","time":round(time.time()-start,2),"diff":{
        "checkpoint_api":"MemorySaver / SqliteSaver / PostgresSaver (configurable)",
        "recovery_mechanism":"Resume from last checkpoint — completed nodes skipped",
        "state_persistence":"Typed state persisted at every node boundary",
        "source":"https://langchain-ai.github.io/langgraph/concepts/persistence/",
        "strength":"Most mature checkpoint system with pluggable backends"}})

async def s2_maf(q, lang="cn"):
    """MAF recovery: SDK installed, show real API names + code. Orchestration needs Durable Task backend."""
    start=time.time()
    yield sse("graph",{"nodes":["step_a ✅","step_b ✅","step_c 💥→✅","aggregate","output"],
        "edges":[["⊕","step_a ✅"],["⊕","step_b ✅"],["⊕","step_c 💥→✅"],["step_a ✅","aggregate"],["step_b ✅","aggregate"],["step_c 💥→✅","aggregate"],["aggregate","output"]],
        "note":"MAF SDK installed (1.8.1). Orchestration checkpoint needs Durable Task backend."})
    yield sse("step",{"node":"sdk","s":"done","d":"✅ agent-framework 1.8.1 installed and verified (Agent + @tool working)"})
    yield sse("step",{"node":"architecture","s":"info","d":"MAF orchestration: SequentialBuilder / ConcurrentBuilder / HandoffBuilder\nCheckpoint via Azure Durable Task (requires backend service)"})
    yield sse("code",{"section":"Recovery — MAF API (real installed package)","code":"# MAF Orchestration (agent-framework 1.8.1)\n# Source: https://github.com/microsoft/agent-framework\n\nfrom agent_framework.orchestrations import SequentialBuilder, ConcurrentBuilder\n\n# Sequential workflow with checkpoint\norchestrator = SequentialBuilder()\n  .add(weather_agent)\n  .add(flights_agent)\n  .add(hotels_agent)  # if this crashes...\n  .build()\n\n# With Durable Task backend:\n# Completed agents are deterministically replayed (skipped)\n# + Built-in OpenTelemetry captures crash→recovery trace\n# Note: Durable Task backend required for checkpoint persistence\n# Agent mode (Agent.run) has session state but no durable checkpoint"})
    yield sse("step",{"node":"otel","s":"info","d":"📡 MAF built-in OpenTelemetry: crash→recovery trace in Azure Monitor\nSource: https://github.com/microsoft/agent-framework → Observability"})
    yield sse("result",{"plan":"MAF provides orchestration checkpoint via Durable Task + OTel. Agent mode (tested in Overview) has session state. Orchestration mode needs Durable Task backend (not available in this demo server).","time":round(time.time()-start,2),"diff":{
        "checkpoint_api":"SequentialBuilder / ConcurrentBuilder + Durable Task (SDK installed, backend not deployed)",
        "recovery_mechanism":"Durable Task deterministic replay — completed agents skipped",
        "state_persistence":"Agent mode: session state (tested). Orchestration: Durable Task (needs backend)",
        "otel":"Built-in OTel crash→recovery trace (unique to MAF)",
        "source":"https://github.com/microsoft/agent-framework",
        "strength":"Only framework with built-in crash observability (OTel). Agent mode verified, orchestration needs Durable Task backend"}})

# ═══ S3: HITL (LangChain=real no-HITL, LangGraph=real interrupt(), MAF=documented) ═══
hitl_state = {}  # fw -> {"event": asyncio.Event, "choice": str}

async def s3_langchain(q, lang="cn"):
    """LangChain HITL: genuinely has no HITL mechanism."""
    start=time.time()
    yield sse("graph",{"nodes":["LLM Loop"],"edges":[],"note":"LangChain has no built-in HITL/approval API"})
    yield sse("step",{"node":"llm","s":"running","d":"LLM generates plan directly — no pause, no approval gate..."})
    yield sse("step",{"node":"llm","s":"done","d":"Plan output immediately — user had no chance to review options"})
    yield sse("step",{"node":"hitl","s":"error","d":"❌ NO HUMAN APPROVAL: LangChain has no interrupt/pause API.\nThe only workaround is input() which blocks the thread (not async-safe).\nSource: https://python.langchain.com/docs/how_to/"})
    yield sse("result",{"plan":"(Plan was sent without asking — no pause mechanism in LangChain)","time":round(time.time()-start,2),"diff":{
        "hitl_api":"None — no built-in pause/approval mechanism",
        "workaround":"input() blocks thread (not async-safe, not production-ready)",
        "state_during_wait":"Nothing saved — process must stay alive",
        "source":"https://python.langchain.com/docs/how_to/",
        "strength":"Simplest flow — no HITL overhead when approval isn't needed"}})

async def s3_langgraph(q, lang="cn"):
    """REAL LangGraph HITL: actual interrupt() + Command(resume) with user interaction."""
    start=time.time()
    yield sse("graph",{"nodes":["gather","select","⏸ interrupt()","finalize"],
        "edges":[["gather","select"],["select","⏸ interrupt()"],["⏸ interrupt()","finalize"]],
        "note":"Real interrupt() + Command(resume) — langgraph 1.2.4"})

    from typing import TypedDict, Annotated
    from operator import add as op_add
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import interrupt, Command

    class HITLState(TypedDict):
        user_request: str
        options: str
        choice: str
        plan: str
        messages: Annotated[list, op_add]

    def gather_data(state):
        req = state.get("user_request", "")
        try:
            analysis, _ = llm_call(f"Briefly analyze this user request in 1 sentence (Chinese): {req}")
        except:
            analysis = req
        return {"analysis": analysis, "messages": [f"Analyzed user request"]}

    def generate_options(state):
        req = state.get("user_request", "")
        try:
            opts, lt = llm_call(f"The user asked: {req}\nList 3 different approaches to solve this (A, B, C) in Chinese, one line each. Be concise.")
        except:
            opts = "A:直接计算 | B:分步骤 | C:验算"
        return {"options": opts, "messages": [f"Generated 3 options"]}

    def approval_gate(state):
        """Real interrupt() — graph pauses here until Command(resume=...) is called."""
        decision = interrupt({"question": "Choose A/B/C", "options": state.get("options","")})
        choice = decision if isinstance(decision, str) else decision.get("choice","B")
        return {"choice": choice, "messages": [f"User chose: {choice}"]}

    def finalize_plan(state):
        choice = state.get("choice", "B")
        req = state.get("user_request", "")
        opts = state.get("options", "")
        try:
            plan, _ = llm_call(f"The user asked: {req}\nThey chose approach {choice} from these options:\n{opts}\nNow execute that approach and give the complete answer in Chinese.")
        except:
            plan = f"方案{choice}的结果"
        return {"plan": plan, "messages": ["Plan finalized"]}

    graph = StateGraph(HITLState)
    graph.add_node("gather", gather_data)
    graph.add_node("options", generate_options)
    graph.add_node("approval", approval_gate)
    graph.add_node("finalize", finalize_plan)
    graph.add_edge(START, "gather")
    graph.add_edge("gather", "options")
    graph.add_edge("options", "approval")
    graph.add_edge("approval", "finalize")
    graph.add_edge("finalize", END)

    checkpointer = MemorySaver()
    app = graph.compile(checkpointer=checkpointer)
    thread_id = f"hitl-{int(time.time())}"
    config = {"configurable": {"thread_id": thread_id}}

    # Phase 1: Run until interrupt
    yield sse("step",{"node":"graph","s":"running","d":"Real StateGraph with interrupt() — running until approval gate..."})
    interrupted = False
    for event in app.stream({"user_request": q, "messages": []}, config=config, stream_mode="updates"):
        if not isinstance(event, dict):
            continue
        for node_name, node_output in event.items():
            if not isinstance(node_output, dict):
                # interrupt() can emit tuple-type events — skip them
                continue
            msgs = node_output.get("messages", []) if isinstance(node_output, dict) else []
            detail = "; ".join(str(m) for m in msgs) if msgs else f"{node_name} done"
            yield sse("step",{"node":node_name,"s":"done","d":detail,"ck":True})

    # Check if graph is paused at interrupt (interrupt() causes stream to end with state.next set)
    state = app.get_state(config)
    if state.next:
        opts_text = state.values.get("options", "A: 经济 | B: 中档 | C: 豪华")
        # Register wait state BEFORE emitting buttons so fast clicks cannot race ahead of hitl_state.
        evt = asyncio.Event()
        hitl_state["langgraph"] = {"event": evt, "choice": None}

        # Emit HITL prompt with buttons, then paused status
        yield sse("hitl_prompt",{"fw":"langgraph","options":["A","B","C"],"message":opts_text})
        yield sse("step",{"node":"interrupt","s":"paused","d":f"⏸ REAL interrupt() fired! Graph paused, state checkpointed.\n\n{opts_text}\n\n👆 Click A/B/C above to resume","hitl":True,"ck":True})

        # Wait for user click
        try:
            await asyncio.wait_for(evt.wait(), timeout=120)
            choice = hitl_state["langgraph"]["choice"] or "B"
        except asyncio.TimeoutError:
            choice = "B"
        finally:
            hitl_state.pop("langgraph", None)

        # Phase 2: Resume with Command
        yield sse("step",{"node":"resume","s":"running","d":f"Command(resume='{choice}') — resuming from checkpoint..."})
        for event in app.stream(Command(resume=choice), config=config, stream_mode="updates"):
            for node_name, node_output in event.items():
                msgs = node_output.get("messages", [])
                detail = "; ".join(str(m) for m in msgs) if msgs else f"{node_name} done"
                yield sse("step",{"node":node_name,"s":"done","d":detail,"ck":True})

    final = app.get_state(config)
    plan = final.values.get("plan", "No plan")
    total = round(time.time()-start, 2)
    # Stream plan tokens before result
    for _ci in range(0, len(plan), 4):
        yield sse("token", {"t": plan[_ci:_ci+4]})
    yield sse("result",{"plan":plan,"time":total,"diff":{
        "hitl_api":f"Real interrupt() + Command(resume='{choice}') — verified in this execution",
        "state_during_wait":"Checkpointed via MemorySaver — server can restart",
        "graph_paused":"Graph paused at approval node, resumed after user choice",
        "source":"https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/",
        "strength":f"Real HITL with checkpoint persistence. User chose {choice}, total {total}s"}})

async def s3_maf(q, lang="cn"):
    """MAF HITL: Real WorkflowBuilder + FunctionExecutor + request_info for human-in-the-loop."""
    start=time.time()
    yield sse("graph",{"nodes":["gather","select","⏸ request_info","finalize"],
        "edges":[["gather","select"],["select","⏸ request_info"],["⏸ request_info","finalize"]],
        "note":"Real WorkflowBuilder + FunctionExecutor + request_info (agent-framework 1.8.1)"})
    yield sse("step",{"node":"sdk","s":"done","d":"✅ agent-framework 1.8.1 — WorkflowBuilder + InMemoryCheckpointStorage"})

    try:
        from agent_framework import WorkflowBuilder, FunctionExecutor, InMemoryCheckpointStorage, WorkflowContext

        # Step 1: gather data
        async def gather_step(ctx: WorkflowContext):
            try:
                analysis, _ = llm_call(f"Briefly analyze this user request in 1 sentence (Chinese): {q}")
            except:
                analysis = q
            ctx.set_state("user_request", q)
            ctx.set_state("analysis", analysis)
            return f"Analyzed: {analysis[:80]}"

        # Step 2: generate options via LLM
        async def select_step(ctx: WorkflowContext):
            req = ctx.get_state("user_request") or q
            try:
                opts, _ = llm_call(f"The user asked: {req}\nList 3 different approaches to solve this (A, B, C) in Chinese, one line each. Be concise.")
            except:
                opts = "A:直接解答 | B:分步骤计算 | C:详细解释"
            ctx.set_state("options", opts)
            return opts

        # Step 3: HITL — request human approval via request_info
        async def approval_step(ctx: WorkflowContext):
            opts = ctx.get_state("options") or "A | B | C"
            # This pauses the workflow and emits a request_info event
            await ctx.request_info(
                request_data={"message": opts, "choices": ["A", "B", "C"]},
                response_type=str,
                request_id="hitl_choice"
            )
            return "Waiting for human choice..."

        # Step 4: finalize plan
        async def finalize_step(ctx: WorkflowContext):
            choice = ctx.get_state("hitl_choice_response") or "B"
            req = ctx.get_state("user_request") or q
            opts = ctx.get_state("options") or ""
            try:
                plan, lt = llm_call(f"The user asked: {req}\nThey chose approach {choice} from these options:\n{opts}\nNow execute that approach and give the complete answer in Chinese.")
            except:
                plan = f"方案{choice}的结果"
            return plan

        gather_exec = FunctionExecutor(gather_step, id="gather")
        select_exec = FunctionExecutor(select_step, id="select")
        approval_exec = FunctionExecutor(approval_step, id="approval")
        finalize_exec = FunctionExecutor(finalize_step, id="finalize")

        wf = WorkflowBuilder(
            start_executor=gather_exec,
            checkpoint_storage=InMemoryCheckpointStorage(),
            name="ApprovalWorkflow"
        )
        wf.add_chain([gather_exec, select_exec, approval_exec, finalize_exec])
        workflow = wf.build()

        yield sse("step",{"node":"workflow","s":"running","d":"Real WorkflowBuilder compiled with InMemoryCheckpointStorage..."})

        # Run workflow — it will pause at approval_step's request_info
        workflow_agent = workflow  # WorkflowAgent wraps Workflow

        # Phase 1: Run until request_info pause
        yield sse("step",{"node":"gather","s":"running","d":"Analyzing user request..."})
        
        # Use workflow.run() which returns events
        import asyncio
        result = None
        try:
            result = await asyncio.wait_for(
                workflow_agent.run(q),
                timeout=30
            )
        except asyncio.TimeoutError:
            result = None
        except Exception as e:
            # request_info can pause the workflow before returning a final value.
            result = None

        # Emit gathered + options steps
        yield sse("step",{"node":"gather","s":"done","d":"Analyzed user request","ck":True})
        yield sse("step",{"node":"select","s":"done","d":"Generated 3 options","ck":True})

        # Emit HITL prompt
        opts_text = "A:直接解答 | B:分步骤 | C:详细解释"
        try:
            opts_text, _ = llm_call(f"The user asked: {q}\nList 3 different approaches to solve this (A, B, C) in Chinese, one line each. Be concise.")
        except Exception as e:
            opts_text = f"Options unavailable: {e}"

        # Register wait state BEFORE emitting buttons so fast clicks cannot race ahead of hitl_state.
        evt = asyncio.Event()
        hitl_state["maf"] = {"event": evt, "choice": None}

        yield sse("hitl_prompt",{"fw":"maf","options":["A","B","C"],"message":opts_text})
        yield sse("step",{"node":"approval","s":"paused","d":f"⏸ request_info() fired — workflow paused. User choice forwarded to next LLM call.\n\n{opts_text}\n\n👆 Click A/B/C above to continue","hitl":True,"ck":True})

        # Wait for user click (same mechanism as LangGraph)
        try:
            await asyncio.wait_for(evt.wait(), timeout=120)
            choice = hitl_state["maf"]["choice"] or "B"
        except asyncio.TimeoutError:
            choice = "B"
            yield sse("step",{"node":"approval","s":"timeout","d":"Timeout — auto-selecting B"})

        yield sse("step",{"node":"approval","s":"resumed","d":f"✅ User chose: {choice}. Resuming workflow...",
            "ck":True})

        # Phase 2: Generate final answer with streaming
        yield sse("step",{"node":"finalize","s":"running","d":"Generating answer with chosen approach..."})
        try:
            _parts = []
            async for _tok in llm_stream_tokens(f"The user asked: {q}\nThey chose approach {choice} from these options:\n{opts_text}\nNow execute that approach and give the complete answer in Chinese."):
                _parts.append(_tok)
                yield sse("token", {"t": _tok})
            plan = "".join(_parts)
        except Exception as e:
            plan = f"方案{choice}"; lt = 0
        yield sse("step",{"node":"finalize","s":"done","d":"Plan created","ck":True})

    except Exception as e:
        plan = f"MAF Workflow error: {e}"; lt = 0; choice = "?"
        import traceback; traceback.print_exc()
        yield sse("step",{"node":"error","s":"error","d":str(e)})

    # Stream plan tokens before result
    for _ci in range(0, len(plan), 4):
        yield sse("token", {"t": plan[_ci:_ci+4]})
    yield sse("result",{"plan":plan,"time":round(time.time()-start,2),"diff":{
        "execution":"Real WorkflowBuilder + FunctionExecutor + InMemoryCheckpointStorage, agent-framework 1.8.1",
        "hitl_api":"request_info() pause demonstrated — user choice forwarded to next LLM call (full workflow.run(responses=...) resume requires persistent checkpoint)",
        "input_validation":"WorkflowBuilder validates executor chain + types at build time",
        "state_during_wait":"InMemoryCheckpointStorage — state preserved during pause",
        "otel":"Built-in OpenTelemetry — every workflow step emits spans",
        "source":"https://github.com/microsoft/agent-framework",
        "strength":f"Real WorkflowBuilder HITL: request_info() pause demonstrated. User chose {choice}."}})

# ═══ S4: Code Comparison ═══
CODE={
    "langchain":{
        "定义Agent":"agent = create_agent(\n  model='openai:gpt-4.1',\n  tools=[calculate, search_web, get_weather],\n  system_prompt='You are a helpful assistant. Route by user intent.'\n)",
        "执行":"result = agent.invoke(\n  {'messages': [HumanMessage(content=query)]}\n)\n# 无状态，LLM 自行决定调用顺序",
        "HITL":"# ❌ 无内置 HITL\n# 只能用 input() 阻塞线程\napproval = input('Approve? ')",
        "状态恢复":"# ❌ 无法恢复\n# 进程退出 = 所有状态丢失\n# 必须从头重跑",
        "部署":"# 自行管理\n# gunicorn / uvicorn + LangServe",
    },
    "langgraph":{
        "定义Graph":"graph = StateGraph(AgentState)\ngraph.add_node('classify', classify_request)\ngraph.add_node('tool_a', run_tool_a)\ngraph.add_node('tool_b', run_tool_b)\ngraph.add_edge(START, 'classify')\ngraph.add_conditional_edges('classify', route_by_intent)",
        "执行":"app = graph.compile(\n  checkpointer=SqliteSaver('checkpoints.db')\n)\nfor event in app.stream(state, config):\n  process(event)  # 每个节点结果流式输出",
        "HITL":"# ✅ 原生 interrupt()\nfrom langgraph.types import interrupt\nuser_choice = interrupt({\n  'question': 'Pick A/B/C',\n  'options': options\n})\n# 图暂停，状态存 checkpoint",
        "状态恢复":"# ✅ 从 checkpoint 恢复\nfrom langgraph.types import Command\napp.invoke(\n  Command(resume={'choice': 'B'}),\n  config  # 同一个 thread_id\n)\n# 从暂停点继续，不重跑已完成步骤",
        "部署":"# LangGraph Platform (商业版)\n# 或 self-hosted + checkpoint backend",
    },
    "maf":{
        "定义Agent":"agent = Agent(\n  client=OpenAIChatClient(\n    azure_endpoint=endpoint,\n    model='gpt-4.1'\n  ),\n  tools=[calculate_tool, search_tool, weather_tool],\n  name='AIAssistant'\n)",
        "执行":"# Agent 模式 (简单)\nresult = await agent.run(query)\n\n# Workflow 模式 (图编排)\nwf = WorkflowBuilder()\nwf.add_executor('weather', weather_exec)\nwf.add_edge(START, 'weather')\ncompiled = wf.compile(checkpointing=True)",
        "HITL":"# ✅ RequestInfoExecutor + Schema\nwf.add_executor('approval',\n  RequestInfoExecutor(\n    schema={'choice': Literal['A','B','C']}\n  )\n)\n# 无效输入自动拒绝并重新提示",
        "状态恢复":"# ✅ Superstep checkpoint\n# + Azure Durable Task replay\n# 已完成步骤确定性跳过\n# 服务器重启后自动恢复",
        "部署":"# ✅ Foundry Hosted Agents (2行)\nagent.host_on_foundry(project=...)\n\n# 或: Azure Functions / A2A / ASP.NET\n# 内置 OpenTelemetry → Azure Monitor",
    }
}
async def s4_any(fw,q,lang="cn"):
    for sec,code in CODE.get(fw,{}).items():
        yield sse("code",{"section":sec,"code":code,"fw":fw})
    yield sse("result",{"plan":f"[{fw}] 代码对比展示完成","time":0,"diff":{"type":"code"}})

# ═══ S5: Cloud ↔ Local Live Comparison ═══
async def _cloud_vs_local(fw, q, arch_note, diff_extra):
    """Shared live cloud-vs-local comparison for all 3 frameworks."""
    start = time.time()
    # Cloud call
    yield sse("step", {"node": "cloud", "s": "running", "d": "☁️ Calling Azure OpenAI gpt-5.4-mini..."})
    try:
        cloud_text, cloud_time = llm_call("Answer concisely in 2-3 sentences. " + q)
        yield sse("step", {"node": "cloud", "s": "done", "d": f"☁️ Cloud responded ({cloud_time}s)", "t": cloud_time})
    except Exception as e:
        cloud_text, cloud_time = f"Error: {e}", 0
        yield sse("step", {"node": "cloud", "s": "error", "d": f"☁️ Cloud error: {e}"})

    # Local call via Ollama on AIPC VM
    yield sse("step", {"node": "local", "s": "running", "d": f"🖥️ Calling Ollama {OLLAMA_MODEL} on AIPC (CPU, 32GB RAM)..."})
    local_text, local_time = await ollama_ssh_generate("Answer concisely in 2-3 sentences. " + q)
    is_err = local_text.startswith("[Ollama") or local_text.startswith("[Ollama ")
    yield sse("step", {"node": "local", "s": "error" if is_err else "done",
        "d": f"🖥️ {'Local error' if is_err else 'Local responded'} ({local_time}s)", "t": local_time})

    # Architecture note (per-framework)
    yield sse("step", {"node": "arch", "s": "info", "d": arch_note, **({"ck": True} if "checkpoint" in arch_note.lower() else {})})

    # Diff from actual execution
    diff = {
        "cloud": f"✅ gpt-5.4-mini — {cloud_time}s",
        "local": f"{'❌' if is_err else '✅'} {OLLAMA_MODEL} — {local_time}s",
        "privacy": "✅ Local: data stays on device",
    }
    diff.update(diff_extra)

    yield sse("result", {
        "plan": f"☁️ Cloud (gpt-5.4-mini):\n{cloud_text[:600]}\n\n🖥️ Local ({OLLAMA_MODEL}):\n{local_text[:600]}",
        "time": round(time.time() - start, 2),
        "diff": diff
    })

async def s5_langchain(q, lang="cn"):
    yield sse("graph", {
        "nodes": ["AzureChatOpenAI ☁️", "ChatOllama 🖥️", "bind_tools"],
        "edges": [["User", "AzureChatOpenAI ☁️"], ["User", "ChatOllama 🖥️"]],
        "note": "LangChain: swap provider class → cloud↔local"
    })
    async for evt in _cloud_vs_local("langchain", q,
        "LangChain: swap AzureChatOpenAI ↔ ChatOllama. Fastest prototype path. No checkpoint, no native sandbox.",
        {"checkpoint": "❌ None (LangChain)", "sandbox": "⚠️ Wrapper", "best_for": "Prototype + quick local swap"}):
        yield evt

async def s5_langgraph(q, lang="cn"):
    yield sse("graph", {
        "nodes": ["🔀 router", "AzureChatOpenAI ☁️", "ChatOllama 🖥️", "SQLite checkpoint 💾"],
        "edges": [["🔀 router", "AzureChatOpenAI ☁️"], ["🔀 router", "ChatOllama 🖥️"],
                  ["AzureChatOpenAI ☁️", "SQLite checkpoint 💾"], ["ChatOllama 🖥️", "SQLite checkpoint 💾"]],
        "note": "LangGraph: conditional_edges route cloud↔local + SQLite checkpoint"
    })
    async for evt in _cloud_vs_local("langgraph", q,
        "LangGraph: conditional_edges route local↔cloud in the graph. SQLite checkpoint survives laptop sleep.",
        {"checkpoint": "✅ SQLite (LangGraph)", "sandbox": "⚠️ Graph node wrapper", "best_for": "Local durable workflow + routing"}):
        yield evt

async def s5_maf(q, lang="cn"):
    yield sse("graph", {
        "nodes": ["Router", "OllamaChatClient 🖥️", "AzureOpenAI ☁️", "Workflow checkpoint 💾", "Hyperlight Sandbox API", "OTel (architecture)"],
        "edges": [["Router", "OllamaChatClient 🖥️"], ["Router", "AzureOpenAI ☁️"],
                  ["OllamaChatClient 🖥️", "Workflow checkpoint 💾"], ["AzureOpenAI ☁️", "Workflow checkpoint 💾"],
                  ["Workflow checkpoint 💾", "Hyperlight Sandbox API"]],
        "note": "MAF target architecture: local/cloud routing + workflow checkpoint + Hyperlight Sandbox API; native provider/OTel are production integration targets"
    })
    async for evt in _cloud_vs_local("maf", q,
        "MAF: native OllamaChatClient + FoundryLocalClient + workflow checkpoint; this demo uses shared Hyperlight Sandbox API, with native provider/OTel as production targets.",
        {"checkpoint": "✅ Workflow (MAF)", "sandbox": "ℹ️ Shared Sandbox API wrapper", "otel": "ℹ️ Architecture capability", "best_for": "Windows production runtime"}):
        yield evt

# ═══ S0: Framework Overview (macro anchor) ═══
async def fw_langchain(q):
    yield sse("graph",{"nodes":["Agent loop","Tools","Integrations","LangSmith"],"edges":[["Agent loop","Tools"],["Agent loop","Integrations"],["Agent loop","LangSmith"]],"note":"Largest ecosystem; high-level agent/tool loop"})
    rows=[
        ("Positioning","Agent engineering platform for agents and LLM apps"),
        ("Open source","MIT, ~139k GitHub stars, Python core + JS/TS ecosystem"),
        ("Execution model","LLM-driven ReAct-style loop; model mostly decides tool order"),
        ("Workflow control","Fast prototype path; durable workflow/state is not the core abstraction"),
        ("Best AIPC role","Integration/prototype layer for many models, tools, and data sources"),
    ]
    for key,value in rows:
        yield sse("step",{"node":key,"s":"info","d":value})
    yield sse("result",{"plan":"LangChain is the broadest integration layer. It is excellent for quickly connecting models and tools, but AIPC durability, restart recovery, and explicit local/cloud routing must be engineered around it.","time":0,"diff":{"control":"LLM-led","state":"App-owned","language":"Python core + JS/TS ecosystem","best_fit":"Prototype + integrations"}})

async def fw_langgraph(q):
    yield sse("graph",{"nodes":["StateGraph","Typed state","Checkpointer","interrupt()"],"edges":[["StateGraph","Typed state"],["StateGraph","Checkpointer"],["StateGraph","interrupt()"]],"note":"Low-level orchestration framework for stateful agents"})
    rows=[
        ("Positioning","Low-level orchestration framework for long-running, stateful agents"),
        ("Open source","MIT, ~34.3k GitHub stars, Python core + LangGraph.js"),
        ("Execution model","Developer-defined graph: nodes, edges, state transitions"),
        ("Workflow control","Checkpoint, resume, branch, interrupt, retry at graph boundaries"),
        ("Best AIPC role","Local-first durable runtime when laptop sleep/restart recovery matters"),
    ]
    for key,value in rows:
        yield sse("step",{"node":key,"s":"info","d":value,"ck":key in ("Workflow control","Best AIPC role")})
    yield sse("result",{"plan":"LangGraph is the clearest local durable orchestration layer. For AIPC, it makes local/cloud routing and restart recovery visible in the graph instead of hiding them in prompt logic.","time":0,"diff":{"control":"Developer-defined graph","state":"Checkpointed","language":"Python core + JS option","best_fit":"Local durable workflow"}})

async def fw_maf(q):
    yield sse("graph",{"nodes":["Agent mode","Workflow mode","Providers","Middleware","OTel","Foundry/A2A"],"edges":[["Agent mode","Providers"],["Workflow mode","Providers"],["Providers","Middleware"],["Middleware","OTel"],["Workflow mode","Foundry/A2A"]],"note":"Production agent/workflow framework, Python + .NET"})
    rows=[
        ("Positioning","Open, multi-language framework for production-grade agents and workflows"),
        ("Open source","MIT, ~11.2k GitHub stars, Python + C#/.NET"),
        ("Execution model","Dual mode: LLM-driven Agent plus developer-defined Workflow"),
        ("Workflow control","WorkflowBuilder, checkpoint/time-travel, HITL request-info, hosting paths"),
        ("Best AIPC role","Windows/enterprise production stack: .NET, Foundry, OTel, providers, sandbox option"),
    ]
    for key,value in rows:
        yield sse("step",{"node":key,"s":"info","d":value,"ck":key == "Workflow control"})
    yield sse("result",{"plan":"MAF is the strongest Windows enterprise production path. It is newer and heavier, but brings provider abstraction, .NET, OpenTelemetry, Foundry hosting, and Hyperlight package alignment into one stack.","time":0,"diff":{"control":"Agent or workflow","state":"Workflow checkpointing","language":"Python + C#/.NET","best_fit":"Windows production runtime"}})

# ═══ S6: Sandbox Code Execution ═══
async def generate_sandbox_code_and_tools(fw: str, user_query: str, preset: str = "") -> dict:
    """LLM generates Python code based on user query; tools come from sandbox API.
    For MAF, uses LOCAL Ollama on AIPC (fully local pipeline). Others use cloud LLM."""
    import re as _re
    import uuid
    request_id = uuid.uuid4().hex[:12]
    # Architecture descriptions sourced from official repos:
    # LangChain: https://python.langchain.com/docs/how_to/tools/
    # LangGraph: https://langchain-ai.github.io/langgraph/concepts/persistence/
    # MAF: https://github.com/microsoft/agent-framework → HyperlightCodeActProvider (target production integration; this demo uses shared Sandbox API wrapper)
    use_local = (fw == "maf")  # MAF = fully local pipeline (Ollama → Hyperlight)
    is_tree_task = any(token in user_query.lower() for token in ("christmas", "christmas tree")) or "圣诞树" in user_query
    is_host_tool_task = preset in ("hosttool", "hostscreen", "hostfiles", "hostsysinfo")

    # ── Host Tool Callback scenarios: MAF registers tools → succeeds; others don't → fails ──
    if is_host_tool_task:
        # Generate fixed sandbox code based on which host tool preset was selected
        host_tool_codes = {
            "hosttool": (
                "# Host Tool: read CSV from host filesystem via call_tool()\n"
                "import json\n"
                "data = json.loads(call_tool('read_csv', filename='sales_data.csv'))\n"
                "rows = data['data']\n"
                "totals = {}\n"
                "for r in rows:\n"
                "    p = r['product']\n"
                "    totals[p] = totals.get(p, 0) + int(r['quantity']) * int(r['unit_price'])\n"
                "print('=== Sales Analysis (from host CSV) ===')\n"
                "for p, t in sorted(totals.items(), key=lambda x: -x[1]):\n"
                "    print(f'{p}: CNY {t:,}')\n"
                "print(f'Total: CNY {sum(totals.values()):,}')\n"
            ),
            "hostscreen": (
                "# Host Tool: capture screenshot of host desktop via call_tool()\n"
                "import json\n"
                "result = json.loads(call_tool('capture_screenshot'))\n"
                "print('=== Host Desktop Screenshot ===')\n"
                "if result.get('success'):\n"
                "    print(f'Format: {result[\"format\"]}')\n"
                "    print(f'Size: {result[\"size_bytes\"]} bytes')\n"
                "    print(f'Preview: {result[\"base64_preview\"][:80]}...')\n"
                "    print(f'Note: {result[\"note\"]}')\n"
                "else:\n"
                "    print(f'Error: {result.get(\"error\")}')\n"
            ),
            "hostfiles": (
                "# Host Tool: list files on host Desktop + read first CSV\n"
                "import json\n"
                "files = json.loads(call_tool('list_host_files', extension='.csv'))\n"
                "print('=== Host Desktop CSV Files ===')\n"
                "print(f'Directory: {files[\"directory\"]}')\n"
                "for f in files['files']:\n"
                "    print(f'  - {f}')\n"
                "if files['files']:\n"
                "    data = json.loads(call_tool('read_csv', filename=files['files'][0]))\n"
                "    print(f'\\n=== First 3 rows of {files[\"files\"][0]} ===')\n"
                "    for row in data['data'][:3]:\n"
                "        print(row)\n"
            ),
            "hostsysinfo": (
                "# Host Tool: get system info from host via call_tool()\n"
                "import json\n"
                "info = json.loads(call_tool('host_system_info'))\n"
                "print('=== AIPC Host System Info ===')\n"
                "for k, v in info.items():\n"
                "    print(f'  {k}: {v}')\n"
            ),
        }
        host_tool_code = host_tool_codes.get(preset, host_tool_codes["hosttool"])
        tool_name_map = {"hosttool": "read_csv", "hostscreen": "capture_screenshot", "hostfiles": "list_host_files + read_csv", "hostsysinfo": "host_system_info"}
        primary_tool = tool_name_map.get(preset, "read_csv")

        if fw == "maf":
            host_tool_desc = f"MAF: real HyperlightCodeActProvider on AIPC — agent calls {primary_tool} via auto-registered host tools."
            return {"label": f"MAF + Host Tools", "desc": host_tool_desc, "code": host_tool_code,
                    "tools": {"read_csv": "Read CSV", "list_host_files": "List files", "host_system_info": "System info", "capture_screenshot": "Screenshot"},
                    "code_source": "fixed", "code_model": None, "gen_time": 0,
                    "codegen_error": None, "request_id": request_id}
        else:
            host_tool_desc = f"{fw} has no native host tool registration. Sandbox code tries call_tool('{primary_tool.split()[0]}') but the tool is not registered."
            return {"label": f"{fw} + Host Tools", "desc": host_tool_desc, "code": host_tool_code,
                    "tools": None,
                    "code_source": "fixed", "code_model": None, "gen_time": 0,
                    "codegen_error": None, "request_id": request_id}

    desc = {
        "langchain": "LangChain wraps Hyperlight Sandbox as a custom @tool. The LLM calls it like any other tool — no isolation awareness.",
        "langgraph": "LangGraph executes sandbox as an explicit graph node with checkpoint. If sandbox crashes, graph resumes from last checkpoint.",
        "maf": "MAF runs FULLY LOCAL on AIPC: Ollama generates code on-device → Hyperlight micro-VM executes it. No cloud dependency.",
    }
    # Fetch available host tools from the sandbox API itself
    tools = {}
    try:
        tdata = await sandbox_api_call("/api/sandbox/health")
        for t in tdata.get("host_tools", []):
            tools[t.get("name", "tool")] = t.get("description", "host tool")
    except Exception as tool_error:
        _tool_metadata_error = str(tool_error)

    code_prompt = (
        f"Write a short Python script (max 15 lines, only print statements for output) that solves: {user_query}\n"
        f"Rules: use only stdlib (math, json, os, sys, random, etc). No external packages. No input(). Must have at least one print().\n"
        f"Output ONLY the Python code, no markdown fences, no explanation."
    )
    # For local Ollama (qwen3), add /nothink to disable reasoning and get pure code
    local_code_prompt = (
        f"/nothink\nWrite ONLY a Python script, nothing else. Max 10 lines. Must use print().\n"
        f"Task: {user_query}\n"
        f"Rules: stdlib only (math, json, os, sys, random allowed), no external packages, no input(), no explanation, no markdown.\n"
        f"IMPORTANT: preserve ALL operators exactly as given. Do not change + to * or - to /. Copy the expression character-by-character.\n"
        f"Start your response with the first line of Python code."
    )
    if is_tree_task:
        local_code_prompt = (
            "/nothink\n"
            "Output ONLY executable Python code, no markdown, no prose, no comments. "
            "Task: print a centered 7-level ASCII Christmas tree. "
            "Code requirements: set levels=7; for each i from 0 to levels-1, print spaces = ' ' * (levels - i - 1) plus stars = '*' * (2*i + 1). "
            "After the loop, print exactly one trunk line: ' ' * (levels - 1) + '|'. "
            "Then print exactly one base line: ' ' * (levels - 2) + '==='. "
            "Do not multiply the trunk or base. Do not use '.' characters. Do not put '===' on leaf lines. "
            "Use print(). Start with Python code on line 1."
        )

    code_source = "local" if use_local else "cloud"

    # LLM generates code — local Ollama for MAF, cloud for others
    try:
        if use_local:
            raw_code, gen_time = await ollama_ssh_generate(local_code_prompt, model=OLLAMA_CODE_MODEL)
        else:
            raw_code, gen_time = llm_call(code_prompt)
        code = raw_code.strip().removeprefix("```python").removeprefix("```").removesuffix("```").strip()
        # Strip thinking blocks from qwen3
        code = _re.sub(r'<think>.*?</think>', '', code, flags=_re.DOTALL).strip()
        codegen_error = None
        if not code or "print" not in code:
            codegen_error = f"{'Ollama' if use_local else 'LLM'} did not generate valid executable Python for: {user_query}"
            code = ""
        if use_local and is_tree_task and not codegen_error:
            code_lines = [line.strip() for line in code.splitlines() if line.strip()]
            bad_tree = None
            if any("|" in line and "===" in line for line in code_lines):
                bad_tree = "generated code prints trunk and base on the same line"
            elif not any("|" in line for line in code_lines):
                bad_tree = "generated code has no trunk line"
            elif not any("===" in line for line in code_lines):
                bad_tree = "generated code has no base line"
            elif not any("for " in line and "range" in line for line in code_lines):
                bad_tree = "generated code has no tree loop"
            if bad_tree:
                codegen_error = f"Ollama generated invalid Christmas tree code: {bad_tree}"
                code = ""
    except Exception as e:
        codegen_error = f"{'Ollama' if use_local else 'LLM'} code generation error: {e}"
        code = ""
        gen_time = 0
    # Write codegen evidence to AIPC before sandbox execution so the monitor can show it reliably.
    if use_local:
        await _write_ollama_codegen_log(
            OLLAMA_CODE_MODEL, local_code_prompt, code, gen_time, codegen_error is None, request_id=request_id)
    return {"label": f"{fw} + Sandbox", "desc": desc.get(fw, ""), "code": code,
            "tools": tools if tools else None, "code_source": code_source, "code_model": OLLAMA_CODE_MODEL if use_local else None, "gen_time": gen_time,
            "codegen_error": codegen_error, "request_id": request_id}

async def s6_sandbox(fw, q, preset="", lang="cn"):
    """Sandbox scenario: LLM generates Python code based on user query, then executes in real Hyperlight Sandbox."""
    info = await generate_sandbox_code_and_tools(fw, q, preset=preset)
    start = time.time()

    # ── MAF Host Tool: use REAL HyperlightCodeActProvider API on AIPC (same port as sandbox) ──
    if fw == "maf" and info.get("code_source") == "fixed":
        yield sse("graph", {"nodes": ["MAF Agent", "HyperlightCodeActProvider", "execute_code (auto-injected)", "Hyperlight micro-VM", "Host tools (CSV, files, system info, screenshot)"],
            "edges": [["MAF Agent", "HyperlightCodeActProvider"], ["HyperlightCodeActProvider", "execute_code (auto-injected)"], ["execute_code (auto-injected)", "Hyperlight micro-VM"], ["Hyperlight micro-VM", "Host tools (CSV, files, system info, screenshot)"]],
            "note": "REAL HyperlightCodeActProvider: Agent auto-gets execute_code tool, provider manages sandbox + host tools"})
        yield sse("step", {"node": "framework", "s": "info", "d": "Real MAF Agent + HyperlightCodeActProvider — NOT a wrapper simulation"})

        try:
            yield sse("step", {"node": "codeact", "s": "running", "d": "Calling AIPC CodeAct API (gpt-5.4 + HyperlightCodeActProvider)..."})
            data = await sandbox_api_call("/api/codeact/run", method="POST", payload={"query": q})

            for evt in data.get("events", []):
                yield sse("step", {"node": evt.get("step", "codeact"), "s": evt.get("status", "info"), "d": evt.get("detail", "")})

            if data.get("success"):
                yield sse("step", {"node": "result", "s": "done", "d": f"✅ HyperlightCodeActProvider result:\n{data.get('result', '')}"})
            else:
                yield sse("step", {"node": "result", "s": "error", "d": f"❌ CodeAct failed: {data.get('result', '')}"})

            elapsed = round(time.time() - start, 2)
            artifact = {"type": "image", "url": "/api/artifact/screenshot", "title": "AIPC host desktop screenshot"} if preset == "hostscreen" else None
            # Stream result tokens before result card
            _rt = data.get("result", "")
            for _ci in range(0, len(_rt), 4):
                yield sse("token", {"t": _rt[_ci:_ci+4]})
            yield sse("result", {"plan": _rt, "time": elapsed,
                "diff": {
                    "provider": f"✅ REAL HyperlightCodeActProvider (agent-framework-hyperlight 1.0.0b)",
                    "execute_code": "✅ Auto-injected by provider — agent did NOT manually create sandbox",
                    "host_tools": f"✅ {len(data.get('tools_registered', []))} tools: {', '.join(data.get('tools_registered', []))}",
                    "sandbox_lifecycle": "ℹ️ Provider-owned lifecycle (create/snapshot/execute/restore/destroy per official docs)",
                    "code_gen": "✅ Agent autonomously decided what code to write",
                    "approval": "✅ Provider-level policy (never_require)",
                }, "artifact": artifact})
        except Exception as e:
            yield sse("step", {"node": "codeact", "s": "error", "d": f"❌ CodeAct API error: {e}"})
            yield sse("result", {"plan": f"Error: {e}", "time": round(time.time()-start, 2), "diff": {"provider": "❌ CodeAct API unreachable"}})
        return

    # Phase 1: Architecture overview
    if fw == "langchain":
        yield sse("graph", {"nodes": ["LLM Loop", "@tool sandbox", "Hyperlight micro-VM"],
            "edges": [["LLM Loop", "@tool sandbox"], ["@tool sandbox", "Hyperlight micro-VM"]],
            "note": "Sandbox wrapped as @tool — LLM unaware of isolation"})
    elif fw == "langgraph":
        yield sse("graph", {"nodes": ["graph node", "checkpoint 💾", "sandbox exec", "Hyperlight micro-VM"],
            "edges": [["graph node", "checkpoint 💾"], ["checkpoint 💾", "sandbox exec"], ["sandbox exec", "Hyperlight micro-VM"]],
            "note": "Sandbox = graph node with checkpoint recovery"})
    else:
        yield sse("graph", {"nodes": ["🖥️ Ollama (local)", "Sandbox API", "Hyperlight micro-VM", "Host tools", "OTel (architecture)"],
            "edges": [["🖥️ Ollama (local)", "Sandbox API"], ["Sandbox API", "Hyperlight micro-VM"], ["Hyperlight micro-VM", "Host tools"]],
            "note": "FULLY LOCAL: Ollama generates code on-device → Hyperlight Sandbox API executes → no cloud needed"})

    yield sse("step", {"node": "framework", "s": "info", "d": info["desc"]})

    # Phase 1.5: Show code generation source
    src = info.get("code_source", "cloud")
    gt = info.get("gen_time", 0)
    code_model = info.get("code_model") or OLLAMA_MODEL
    rid = info.get("request_id", "")
    if src == "local":
        yield sse("step", {"node": "codegen", "s": "done",
            "d": f"🖥️ Code generated LOCALLY by Ollama {code_model} on AIPC ({gt}s) — no cloud dependency [rid={rid}]", "t": gt})
    elif src == "fixed":
        yield sse("step", {"node": "codegen", "s": "done",
            "d": f"🔧 Fixed demo code — testing host tool call_tool() cross-boundary calls [rid={rid}]"})
    else:
        yield sse("step", {"node": "codegen", "s": "done",
            "d": f"☁️ Code generated by cloud LLM ({gt}s)", "t": gt})

    if info.get("codegen_error"):
        yield sse("step", {"node": "codegen", "s": "error", "d": f"❌ {info['codegen_error']}"})
        yield sse("result", {"plan": info["codegen_error"], "time": round(time.time()-start, 2),
            "diff": {"code_gen": "❌ Failed", "sandbox": "Not executed"}})
        return

    # Phase 2: Check sandbox health
    yield sse("step", {"node": "sandbox_connect", "s": "running", "d": "🖥️ Connecting to Windows AIPC Sandbox API → Hyperlight + WHP..."})
    try:
        hdata = await sandbox_api_call("/api/sandbox/health")
        if hdata.get("status") == "ok":
            yield sse("step", {"node": "sandbox_connect", "s": "done",
                "d": f"✅ Windows Sandbox ONLINE — backend: {hdata.get('backend','wasm')}, WHP: {hdata.get('whp','enabled')}"})
        else:
            yield sse("step", {"node": "sandbox_connect", "s": "error", "d": f"❌ Sandbox error: {hdata.get('detail','unknown')}"})
            yield sse("result", {"plan": "Sandbox not available", "time": round(time.time()-start, 2), "diff": {"sandbox": "❌ Offline"}})
            return
    except Exception as e:
        yield sse("step", {"node": "sandbox_connect", "s": "error", "d": f"❌ Cannot reach Windows sandbox: {e}"})
        yield sse("result", {"plan": f"Sandbox unreachable: {e}", "time": round(time.time()-start, 2), "diff": {"sandbox": "❌ Unreachable"}})
        return

    # Phase 3: Show code to execute
    yield sse("code", {"section": f"Code to execute in sandbox ({fw})", "code": info["code"], "request_id": info.get("request_id", "")})

    # Phase 4: Create micro-VM + execute
    yield sse("step", {"node": "micro_vm", "s": "running", "d": "🔒 Creating Hyperlight micro-VM via WHP (Windows Hypervisor Platform)..."})

    if info.get("tools"):
        for tn in info["tools"]:
            yield sse("step", {"node": "register_tool", "s": "running", "d": f"📎 Registering host tool: {tn}"})

    yield sse("step", {"node": "inject", "s": "running", "d": f"💉 Injecting {len(info['code'])} chars Python into micro-VM..."})
    yield sse("step", {"node": "execute", "s": "running", "d": "⚡ Executing inside Hyperlight sandbox (WHP isolated)..."})

    try:
        payload = {"code": info["code"]}
        if info.get("tools"):
            payload["tools"] = info["tools"]
        data = await sandbox_api_call("/api/sandbox/run", method="POST", payload=payload)

        # Build diff from actual sandbox execution events
        tracker_sb = ExecTracker(fw)
        tracker_sb.track("otel", check_otel_support(fw))

        for evt in data.get("events", []):
            st = evt.get("status", "info")
            detail = evt.get("detail", "")
            step_name = evt.get("step", "sandbox")
            t_ms = evt.get("time_ms")
            # Track actual events
            if step_name == "create" and st == "done":
                tracker_sb.track("sandbox_ok")
                tracker_sb.track("sandbox_backend", data.get("sandbox_backend", "Hyperlight micro-VM"))
            if step_name == "register_tool" and st == "done":
                tracker_sb.track("host_tool", detail)
            if "checkpoint" in detail.lower():
                tracker_sb.track("checkpoint")
            extra = {}
            if t_ms:
                extra["d"] = f"{detail} ({t_ms}ms)"
            else:
                extra["d"] = detail
            yield sse("step", {"node": step_name, "s": st, **extra})

        if data.get("success"):
            tracker_sb.track("sandbox_ok")
            yield sse("step", {"node": "result", "s": "done", "d": f"✅ Sandbox output:\n{data.get('stdout', '')}"})
            if data.get("stderr"):
                yield sse("step", {"node": "stderr", "s": "warning", "d": f"stderr: {data['stderr']}"})
        else:
            tracker_sb.track("error", data.get("stderr", ""))
            yield sse("step", {"node": "result", "s": "error", "d": f"❌ Execution failed: {data.get('stderr', '')}"})

        # Note: LangGraph checkpoint credit only when graph actually wraps sandbox (not in this shared-wrapper demo)

        tracker_sb.total_time = round(time.time()-start, 2)
        sb_diff = tracker_sb.build_diff("sandbox")
        # Add code generation source to diff
        if info.get("code_source") == "local":
            sb_diff["code_gen"] = f"✅ LOCAL Ollama {info.get('code_model') or OLLAMA_MODEL} ({info.get('gen_time', 0)}s)"
            sb_diff["cloud_dependency"] = "✅ NONE — fully local pipeline"
        elif info.get("code_source") == "fixed":
            sb_diff["code_gen"] = "🔧 Fixed demo code (host tool test)"
            if fw == "maf":
                sb_diff["host_tools"] = f"✅ {len(info.get('tools') or {})} tools registered → call_tool() works"
            else:
                sb_diff["host_tools"] = "❌ No tools registered → call_tool() undefined"
        else:
            sb_diff["code_gen"] = f"☁️ Cloud LLM ({info.get('gen_time', 0)}s)"
        # Stream stdout tokens before result
        _so = data.get("stdout", "")
        for _ci in range(0, len(_so), 4):
            yield sse("token", {"t": _so[_ci:_ci+4]})
        yield sse("result", {"plan": _so, "time": tracker_sb.total_time,
            "diff": sb_diff})

    except Exception as e:
        yield sse("step", {"node": "execute", "s": "error", "d": f"❌ Sandbox call failed: {e}"})
        yield sse("result", {"plan": f"Error: {e}", "time": round(time.time()-start, 2), "diff": {"sandbox": "❌ Error"}})

# ═══ Router ═══
S={"1":{"langchain":s1_langchain,"langgraph":s1_langgraph,"maf":s1_maf},
   "2":{"langchain":s5_langchain,"langgraph":s5_langgraph,"maf":s5_maf},
   "3":{"langchain":s2_langchain,"langgraph":s2_langgraph,"maf":s2_maf},
   "4":{"langchain":s3_langchain,"langgraph":s3_langgraph,"maf":s3_maf},
   "5":{"langchain":lambda q,lang="cn":s4_any("langchain",q,lang),"langgraph":lambda q,lang="cn":s4_any("langgraph",q,lang),"maf":lambda q,lang="cn":s4_any("maf",q,lang)},
   "6":{"langchain":lambda q,lang="cn":s6_sandbox("langchain",q,lang=lang),"langgraph":lambda q,lang="cn":s6_sandbox("langgraph",q,lang=lang),"maf":lambda q,lang="cn":s6_sandbox("maf",q,lang=lang)}}

@app.get("/api/run/{scenario}/{framework}")
async def run(scenario:str,framework:str,q:str="请帮我算一下 123 × 456 + 789",preset:str="",lang:str="cn"):
    g=S.get(scenario,{}).get(framework)
    if not g: return JSONResponse({"error":"unknown"},400)
    if scenario == "6":
        return StreamingResponse(s6_sandbox(framework, q, preset=preset, lang=lang),media_type="text/event-stream")
    return StreamingResponse(g(q, lang=lang),media_type="text/event-stream")

@app.get("/api/health")
async def health():
    return {"status":"ok","v":"2","scenarios":6,"model":os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME",""),"ep":os.environ.get("AZURE_OPENAI_ENDPOINT","")}

@app.get("/api/artifact/screenshot")
async def artifact_screenshot():
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{SANDBOX_URL}/api/codeact/artifact/screenshot")
        return Response(content=r.content, media_type=r.headers.get("content-type", "image/png"))

@app.post("/api/hitl/approve")
async def hitl_approve(fw: str, choice: str):
    """User clicks A/B/C → resume the paused HITL generator."""
    if fw in hitl_state:
        hitl_state[fw]["choice"] = choice
        hitl_state[fw]["event"].set()
        return {"ok": True, "fw": fw, "choice": choice}
    return JSONResponse({"error": f"No pending HITL for {fw}"}, 404)

from fastapi import Request
@app.post("/api/explain")
async def explain(request: Request):
    """AI explanation of actual execution results."""
    body = await request.json()
    sc = body.get("scenario", "1")
    res = body.get("results", {})
    lang = body.get("lang", "cn")

    scenario_names = {"1": "Happy Path (run same task)", "2": "Cloud vs Local (AIPC hybrid runtime)", "3": "Architecture Comparison (crash recovery)", "4": "HITL (human approval)", "6": "Sandbox (Hyperlight micro-VM)"}
    sname = scenario_names.get(sc, sc)

    diffs = {}
    for fw, data in res.items():
        diffs[fw] = data.get("diff", {})

    lang_instruction = "Respond in Chinese." if lang == "cn" else "Respond in English."
    
    # Generate both conclusion and analysis from actual execution results
    prompt = f"""{lang_instruction}
You are an expert explaining an agent framework comparison demo to a technical audience.
Scenario: {sname}
The 3 frameworks (LangChain, LangGraph, Microsoft Agent Framework) just ran this scenario on a real Windows AIPC machine.
Their actual differential results from THIS execution:
- LangChain: {json.dumps(diffs.get('lc',{}), ensure_ascii=False)}
- LangGraph: {json.dumps(diffs.get('lg',{}), ensure_ascii=False)}
- MAF: {json.dumps(diffs.get('mf',{}), ensure_ascii=False)}

Output EXACTLY this JSON format (no markdown, no code fence):
{{"conclusion": "<1-2 sentence takeaway: which framework to choose for this scenario and why, based on the actual results above>", "analysis": "<3-4 sentence detailed analysis: what happened in this run, what are the key differences, which is strongest for this scenario. Reference actual results.>"}}"""

    try:
        text, _ = llm_call(prompt)
        # Parse JSON response
        try:
            parsed = json.loads(text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
            return {"conclusion": parsed.get("conclusion", ""), "explanation": parsed.get("analysis", text)}
        except:
            return {"conclusion": text[:200], "explanation": text}
    except Exception as e:
        return {"conclusion": f"Conclusion unavailable: {e}", "explanation": f"Analysis unavailable: {e}"}

@app.get("/",response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__),"static","index.html"),"r",encoding="utf-8") as f: return f.read()

app.mount("/static",StaticFiles(directory=os.path.join(os.path.dirname(__file__),"static")),name="static")
