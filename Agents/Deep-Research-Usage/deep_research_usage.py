#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import traceback
from typing import Any, Iterable, List, Optional, Callable
from azure.identity import ClientSecretCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import DeepResearchTool

CREDENTIALS_JSON = "deep_research_credentials.json"

def load_credentials_from_json(path: str = CREDENTIALS_JSON):
    if not os.path.exists(path):
        print(f"凭据文件未找到: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    required = [
        "azure_client_id", "azure_client_secret", "azure_tenant_id",
        "project_endpoint", "bing_resource_name",
        "deep_research_model", "model_deployment",
    ]
    for k in required:
        if not data.get(k):
            print(f"缺少必要键: {k}")
            sys.exit(1)
    os.environ["AZURE_CLIENT_ID"] = data["azure_client_id"]
    os.environ["AZURE_CLIENT_SECRET"] = data["azure_client_secret"]
    os.environ["AZURE_TENANT_ID"] = data["azure_tenant_id"]
    os.environ["AZURE_SUBSCRIPTION_ID"] = data.get("azure_subscription_id", "")
    os.environ["PROJECT_ENDPOINT"] = data["project_endpoint"]
    os.environ["BING_RESOURCE_NAME"] = data["bing_resource_name"]
    os.environ["DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME"] = data["deep_research_model"]
    os.environ["MODEL_DEPLOYMENT_NAME"] = data["model_deployment"]
    print("凭据已从 JSON 加载。")

def _status_name(status: Any) -> str:
    s = str(status)
    if "." in s:
        s = s.split(".")[-1]
    return s.strip().lower()

def _get_message_timestamp(msg: Any) -> float:
    ts = getattr(msg, "created_at", None) or getattr(msg, "created_on", None)
    if ts is None:
        return 0.0
    try:
        return float(getattr(ts, "timestamp", lambda: ts)())
    except Exception:
        try:
            return float(ts)
        except Exception:
            return 0.0

def _extract_text_from_message(msg: Any) -> str:
    parts: Iterable = getattr(msg, "content", []) or []
    texts: List[str] = []
    for c in parts:
        if hasattr(c, "text") and getattr(c.text, "value", None):
            texts.append(c.text.value)
        elif isinstance(c, str):
            texts.append(c)
        elif hasattr(c, "value") and isinstance(getattr(c, "value"), str):
            texts.append(c.value)
    return "".join(texts).strip()

def _try_get_status_code(exc: Exception) -> Optional[int]:
    for attr in ("status_code", "status"):
        v = getattr(exc, attr, None)
        if isinstance(v, int):
            return v
    resp = getattr(exc, "response", None)
    if resp is not None:
        for attr in ("status_code", "status"):
            v = getattr(resp, attr, None)
            if isinstance(v, int):
                return v
    return None

def _headers_get(headers: Any, key: str) -> Optional[str]:
    if headers is None:
        return None
    try:
        if hasattr(headers, "get"):
            val = headers.get(key)
            if val:
                return str(val)
            for k in headers.keys():
                if str(k).lower() == key.lower():
                    return str(headers[k])
    except Exception:
        return None
    return None

def _try_get_request_id(exc: Exception) -> Optional[str]:
    resp = getattr(exc, "response", None)
    if resp is not None:
        headers = getattr(resp, "headers", None)
        for k in ["x-ms-request-id", "apim-request-id", "x-request-id", "x-ms-correlation-request-id"]:
            rid = _headers_get(headers, k)
            if rid:
                return f"{k}={rid}"
    rid = getattr(exc, "request_id", None)
    if rid:
        return str(rid)
    return None

def _is_retryable(exc: Exception) -> bool:
    sc = _try_get_status_code(exc)
    if sc is None:
        return True
    if sc in (408, 409, 425, 429):
        return True
    if 500 <= sc < 600:
        return True
    return False

def _sdk_call(func: Callable, *args, max_attempts: int = 5, base_sleep: float = 1.0, max_sleep: float = 10.0, **kwargs):
    attempt = 0
    delay = base_sleep
    last_exc: Optional[Exception] = None
    while attempt < max_attempts:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            sc = _try_get_status_code(exc)
            rid = _try_get_request_id(exc)
            retryable = _is_retryable(exc)
            print(f"[SDK] 调用 {getattr(func, '__name__', '<lambda>')} 失败 (第 {attempt+1}/{max_attempts} 次) 状态={sc} request-id={rid} retryable={retryable}")
            if not retryable or attempt == max_attempts - 1:
                tb = "".join(traceback.format_exception_only(type(exc), exc)).strip()
                print(f"[SDK] 错误: {tb}")
                raise
            time.sleep(delay)
            delay = min(delay * 2, max_sleep)
            attempt += 1
    if last_exc:
        raise last_exc

def build_project_client() -> AIProjectClient:
    cred = ClientSecretCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
    )
    endpoint = os.environ["PROJECT_ENDPOINT"]
    return AIProjectClient(endpoint=endpoint, credential=cred)

def create_agent_and_thread(pc: AIProjectClient):
    conn = _sdk_call(pc.connections.get, name=os.environ["BING_RESOURCE_NAME"])
    conn_id = conn.id
    dr_tool = DeepResearchTool(
        bing_grounding_connection_id=conn_id,
        deep_research_model=os.environ["DEEP_RESEARCH_MODEL_DEPLOYMENT_NAME"],
    )
    ac = pc.agents
    agent = _sdk_call(
        ac.create_agent,
        model=os.environ["MODEL_DEPLOYMENT_NAME"],
        name=f"deep-research-{int(time.time())}",
        instructions=(
            "You are a helpful agent. Use the Deep Research tool when needed and keep conversational context. "
            "If no time range specified, assume the most recent available quarter. Avoid unnecessary clarifications."
        ),
        tools=dr_tool.definitions,
    )
    thread = _sdk_call(ac.threads.create)
    return agent, thread

def _list_messages_with_retry(ac, thread_id: str, run_id: Optional[str] = None) -> List[Any]:
    if run_id:
        return _sdk_call(lambda: list(ac.messages.list(thread_id=thread_id, run_id=run_id)))
    return _sdk_call(lambda: list(ac.messages.list(thread_id=thread_id)))

def send_and_wait(ac, thread_id: str, agent_id: str, content: str, timeout: int = 1800) -> str:
    _sdk_call(ac.messages.create, thread_id=thread_id, role="user", content=content)
    run = _sdk_call(ac.runs.create, thread_id=thread_id, agent_id=agent_id)
    waited = 0
    while _status_name(run.status) in {"queued", "in_progress", "requires_action"} and waited < timeout:
        print(f"状态: {run.status} – {waited}s", end="\r")
        sys.stdout.flush()
        time.sleep(5)
        waited += 5
        run = _sdk_call(ac.runs.get, thread_id=thread_id, run_id=run.id)
    print(f"\n最终状态: {run.status}")
    if _status_name(run.status) != "completed":
        raise RuntimeError(f"运行结束: {run.status}")
    msgs: List[Any] = []
    try:
        msgs = _list_messages_with_retry(ac, thread_id=thread_id, run_id=run.id)
    except:
        msgs = []
    if not msgs:
        msgs = _list_messages_with_retry(ac, thread_id=thread_id)
    assistant_msgs = [m for m in msgs if getattr(m, "role", None) == "assistant"]
    same_run_msgs = [m for m in assistant_msgs if getattr(m, "run_id", None) == run.id]
    if same_run_msgs:
        assistant_msgs = same_run_msgs
    if not assistant_msgs:
        raise RuntimeError("未找到助手回复")
    reply = max(assistant_msgs, key=_get_message_timestamp)
    return _extract_text_from_message(reply)

def chat(pc: AIProjectClient, agent, thread):
    ac = pc.agents
    print("\n💬 Deep-Research 多轮对话，输入 'exit' 退出\n")
    while True:
        try:
            user_input = input("你: ").strip()
        except KeyboardInterrupt:
            print("\n会话已终止。")
            break
        if user_input.lower() in {"exit", "quit"}:
            break
        try:
            answer = send_and_wait(ac, thread.id, agent.id, user_input)
            print("\n助手:", answer, "\n")
        except Exception as exc:
            print(f"\n错误: {exc}\n")
            time.sleep(2)

def main():
    load_credentials_from_json(CREDENTIALS_JSON)
    pc = build_project_client()
    agent, thread = create_agent_and_thread(pc)
    try:
        chat(pc, agent, thread)
    finally:
        try:
            pc.agents.delete_agent(agent.id)
            print("已删除临时 Agent。")
        except:
            pass

if __name__ == "__main__":
    main()