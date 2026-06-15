"""Demo Web App — Foundry Agents with Hosted Agent + Toolbox.

Each demo Foundry Agent = a name + a model deployment + a tool subset + a
hosted runtime binding. The hosted runtime is separate: it is the containerized
agent process behind a Responses endpoint, not the place where model metadata is
registered in this demo control surface.

When the user sends a message to an agent, the backend constructs a system
prompt that constrains the LLM to only use that agent's selected tools. This lets
the demo compare multiple agent personas while keeping the hosted runtime and
Toolbox MCP endpoint explicit.
"""
import json
import os
import re
import tempfile
import time
import uuid
import copy
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)

# ---- Foundry Agent SDK client (for real agent create/invoke/delete) ----
_FOUNDRY_PROJECT_CLIENT = None


def _get_foundry_client():
    """Lazy-init AIProjectClient for Foundry Agents API."""
    global _FOUNDRY_PROJECT_CLIENT
    if _FOUNDRY_PROJECT_CLIENT is not None:
        return _FOUNDRY_PROJECT_CLIENT
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    if not endpoint:
        return None
    from azure.ai.projects import AIProjectClient
    _FOUNDRY_PROJECT_CLIENT = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
    )
    return _FOUNDRY_PROJECT_CLIENT


# ---- Foundry Agent Management REST API helpers ----
# These call the Foundry control-plane directly to create/get/delete real agents
# (both prompt and hosted). The MCP tool `agent_update` wraps the same REST surface.

FOUNDRY_ACR_IMAGE = os.getenv("FOUNDRY_ACR_IMAGE", "").strip()  # e.g. myacr.azurecr.io/hosted-agent:tag


def _foundry_api_headers() -> dict:
    return {
        "Authorization": f"Bearer {DefaultAzureCredential().get_token('https://ai.azure.com/.default').token}",
        "Content-Type": "application/json",
    }


def _foundry_create_hosted_agent(name: str, model: str, instructions: str,
                                  acr_image: str, toolbox_name: str = "",
                                  env_vars: dict[str, str] | None = None) -> dict:
    """Create a real hosted agent in Foundry via REST API using an existing ACR image."""
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    if not endpoint:
        raise HTTPException(400, "AZURE_AI_PROJECT_ENDPOINT is required to create Foundry agents")
    if not acr_image:
        raise HTTPException(400, "FOUNDRY_ACR_IMAGE env var is required for hosted agent creation")
    env = {
        "AZURE_AI_PROJECT_ENDPOINT": endpoint,
        "FOUNDRY_PROJECT_ENDPOINT": endpoint,
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": model,
    }
    if toolbox_name:
        env["TOOLBOX_NAME"] = toolbox_name
    if env_vars:
        env.update(env_vars)
    definition: dict[str, Any] = {
        "kind": "hosted",
        "image": acr_image,
        "cpu": "0.25",
        "memory": "0.5Gi",
        "container_protocol_versions": [
            {"protocol": "responses", "version": "1.0.0"}
        ],
        "environment_variables": env,
    }
    url = f"{endpoint.rstrip('/')}/agents/{name}?api-version=v1"
    r = httpx.put(url, headers=_foundry_api_headers(), json=definition, timeout=60.0)
    r.raise_for_status()
    return r.json()


def _foundry_get_agent(name: str) -> dict | None:
    """Get a Foundry agent by name. Returns None if not found."""
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    if not endpoint:
        return None
    try:
        r = httpx.get(f"{endpoint.rstrip('/')}/agents/{name}?api-version=v1",
                      headers=_foundry_api_headers(), timeout=15.0)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _foundry_delete_agent(name: str) -> bool:
    """Delete a Foundry agent by name. Returns True on success."""
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    if not endpoint:
        return False
    try:
        r = httpx.delete(f"{endpoint.rstrip('/')}/agents/{name}?api-version=v1",
                         headers=_foundry_api_headers(), timeout=30.0)
        return r.status_code < 400 or r.status_code == 404
    except Exception:
        return False


def _foundry_agent_responses_url(agent_name: str) -> str:
    """Build the hosted agent /responses endpoint URL."""
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
    return f"{endpoint.rstrip('/')}/agents/{agent_name}/endpoint/protocols/openai/v1/responses?api-version=v1"


SKILLS_TREE_API = "https://api.github.com/repos/microsoft/skills/git/trees/main?recursive=1"
SKILLS_RAW_BASE = "https://raw.githubusercontent.com/microsoft/skills/main/"
SKILLS_CACHE_TTL_SECONDS = int(os.getenv("SKILLS_CACHE_TTL_SECONDS", "86400"))
MAX_SKILLS_PER_AGENT = int(os.getenv("MAX_SKILLS_PER_AGENT", "5"))
MAX_SKILL_PROMPT_CHARS = int(os.getenv("MAX_SKILL_PROMPT_CHARS", "12000"))
MAX_TOTAL_SKILL_PROMPT_CHARS = int(os.getenv("MAX_TOTAL_SKILL_PROMPT_CHARS", "30000"))


def _atomic_write_text(path: Path, text: str) -> None:
    tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _save_json(name: str, obj: Any):
    path = DATA_DIR / f"{name}.json"
    backup_path = DATA_DIR / f"{name}.json.bak"
    payload = json.dumps(obj, ensure_ascii=False, indent=2)
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
            if existing.strip():
                _atomic_write_text(backup_path, existing)
        except Exception as exc:
            print(f"[persistence] failed to backup {path.name}: {exc}")
    _atomic_write_text(path, payload)


def _load_json(name: str, default: Any = None) -> Any:
    path = DATA_DIR / f"{name}.json"
    backup_path = DATA_DIR / f"{name}.json.bak"
    for p in (path, backup_path):
        if not p.exists():
            continue
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[persistence] failed to load {p.name}: {exc}")
    return copy.deepcopy(default)


def _parse_skill_frontmatter(content: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if not content.startswith("---"):
        return metadata
    parts = content.split("---", 2)
    if len(parts) < 3:
        return metadata
    for raw_line in parts[1].splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    return metadata


def _skill_category(path: str) -> str:
    if path.startswith(".github/skills/"):
        return "Core"
    if path.startswith(".github/plugins/azure-skills/skills/"):
        return "Foundry"
    plugin_categories = {
        "azure-sdk-python": "Python",
        "azure-sdk-dotnet": ".NET",
        "azure-sdk-typescript": "TypeScript",
        "azure-sdk-java": "Java",
        "azure-sdk-rust": "Rust",
        "deep-wiki": "Plugin",
    }
    for plugin, category in plugin_categories.items():
        if path.startswith(f".github/plugins/{plugin}/skills/"):
            return category
    return "Other"


def _skill_name_from_path(path: str) -> str:
    parts = path.split("/")
    return parts[-2] if len(parts) >= 2 else path.replace("/SKILL.md", "")


def _github_skill_raw_url(path: str) -> str:
    return SKILLS_RAW_BASE + path


def _load_skill_catalog(refresh: bool = False) -> list[dict[str, Any]]:
    cached = _load_json("skills_cache", {}) or {}
    now = time.time()
    if not refresh and cached.get("catalog") and now - cached.get("ts", 0) < SKILLS_CACHE_TTL_SECONDS:
        return cached["catalog"]

    try:
        response = httpx.get(SKILLS_TREE_API, timeout=20.0)
        response.raise_for_status()
        tree = response.json().get("tree", [])
        catalog = []
        for item in tree:
            path = item.get("path", "")
            if item.get("type") != "blob" or not path.endswith("/SKILL.md"):
                continue
            name = _skill_name_from_path(path)
            category = _skill_category(path)
            catalog.append({
                "id": path,
                "name": name,
                "label": name.replace("-", " "),
                "description": f"Microsoft agent skill package: {name}",
                "category": category,
                "source_url": f"https://github.com/microsoft/skills/blob/main/{path}",
                "raw_url": _github_skill_raw_url(path),
            })
        catalog.sort(key=lambda skill: (skill["category"], skill["name"]))
        _save_json("skills_cache", {"ts": now, "catalog": catalog})
        return catalog
    except Exception:
        return cached.get("catalog", [])


def _fetch_skill_content(skill_id: str) -> tuple[dict[str, str], str]:
    if not skill_id.endswith("/SKILL.md") or ".." in skill_id:
        raise HTTPException(400, "Invalid skill id")
    response = httpx.get(_github_skill_raw_url(skill_id), timeout=20.0)
    response.raise_for_status()
    content = response.text
    return _parse_skill_frontmatter(content), content


def _skill_prompt_block(agent: dict[str, Any]) -> str:
    loaded_skills = agent.get("loaded_skills") or []
    if not loaded_skills:
        return ""
    blocks = []
    used_chars = 0
    for skill in loaded_skills[:MAX_SKILLS_PER_AGENT]:
        content = str(skill.get("content", ""))[:MAX_SKILL_PROMPT_CHARS]
        remaining = MAX_TOTAL_SKILL_PROMPT_CHARS - used_chars
        if remaining <= 0:
            break
        content = content[:remaining]
        used_chars += len(content)
        blocks.append(
            f"### Skill: {skill.get('name') or skill.get('id')}\n"
            f"Source: {skill.get('source_url', 'https://github.com/microsoft/skills')}\n"
            f"Description: {skill.get('description', '')}\n\n"
            f"{content}"
        )
    if not blocks:
        return ""
    return (
        "\n\n[LOADED MICROSOFT AGENT SKILLS]\n"
        "Use these SKILL.md files as developer guidance for this agent's behavior and SDK patterns. "
        "They do not grant new external tools or permissions.\n\n"
        + "\n\n".join(blocks)
        + "\n[/LOADED MICROSOFT AGENT SKILLS]\n"
    )

app = FastAPI(title="Foundry Agent Demo")

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8088")
CLOUD_AGENT_URL = os.getenv("CLOUD_AGENT_URL", "")  # Foundry hosted agent /responses URL (with api-version)
DISABLE_LOCAL_ENDPOINT = os.getenv("DISABLE_LOCAL_ENDPOINT", "0") == "1"
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
DEFAULT_AGENT_MODEL = (
    os.getenv("DEFAULT_AGENT_MODEL")
    or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    or "gpt-4-1-mini"
).strip()
EVALUATION_MODEL_DEPLOYMENT = (
    os.getenv("EVALUATION_MODEL_DEPLOYMENT")
    or os.getenv("AZURE_AI_EVALUATION_DEPLOYMENT_NAME")
    or DEFAULT_AGENT_MODEL
).strip()
IMAGE_GENERATION_MODEL = (
    os.getenv("IMAGE_GENERATION_MODEL")
    or os.getenv("AZURE_AI_IMAGE_DEPLOYMENT_NAME")
    or "gpt-image-1"
).strip()
MEMORY_SOURCE_URL = "https://azure.microsoft.com/en-us/updates/?id=560992"
MEMORY_SDK_SOURCE_URL = "https://raw.githubusercontent.com/microsoft/agent-framework/main/python/packages/foundry/agent_framework_foundry/_memory_provider.py"
ENABLE_FOUNDRY_EVAL_API = os.getenv("ENABLE_FOUNDRY_EVAL_API", "0").lower() in {"1", "true", "yes"}

# Endpoint catalog (local microVM-style + Foundry-hosted)
ENDPOINTS: dict[str, dict] = {}
if not DISABLE_LOCAL_ENDPOINT:
    ENDPOINTS["local"] = {
        "id": "local",
        "label": "Local hosted agent (localhost:8088)",
        "url": AGENT_URL.rstrip("/") + "/responses",
        "auth": "none",
        "description": "Locally-running Microsoft Agent Framework container (Dockerfile + main.py).",
    }
if CLOUD_AGENT_URL:
    ENDPOINTS["foundry"] = {
        "id": "foundry",
        "label": "Foundry hosted agent (cloud microVM)",
        "url": CLOUD_AGENT_URL,
        "auth": "bearer",
        "description": "Real Foundry-hosted agent deployed via `azd up` — runs in a managed microVM with isolated state.",
    }
# Default to foundry if available, otherwise local
_default_ep = "foundry" if "foundry" in ENDPOINTS else (next(iter(ENDPOINTS), "local"))
CURRENT_ENDPOINT = {"id": _default_ep}
WHISPER_DEPLOYMENT = os.getenv("WHISPER_DEPLOYMENT", "whisper")
ACCOUNT_BASE = (
    PROJECT_ENDPOINT.split("/api/projects/")[0] if "/api/projects/" in PROJECT_ENDPOINT else PROJECT_ENDPOINT.rstrip("/")
)
STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_TOOLBOX_NAME = (os.getenv("TOOLBOX_NAME", "agent-tools").strip() or "agent-tools")

# ---- All available tools (toolbox + direct) ----
ALL_TOOLS = {
    "code_interpreter":      {"source": "toolbox", "label": "Toolbox · code_interpreter",   "desc": "Execute Python in a managed sandbox"},
    "file_search":           {"source": "toolbox", "label": "Toolbox · file_search",        "desc": "Search uploaded documents (vector store)"},
    "web_search":            {"source": "toolbox", "label": "Toolbox · web_search",         "desc": "Web search via Toolbox (preview, may fall back)"},
    "direct_web_search":     {"source": "direct",  "label": "Direct · direct_web_search",   "desc": "Foundry Responses API web_search (Bing)"},
    "direct_image_generate": {"source": "direct",  "label": "Direct · direct_image_generate","desc": f"Generate image via {IMAGE_GENERATION_MODEL}"},
}

# ---- Hosted Agent Registry (multi-team support) ----
_DEFAULT_HOSTED_AGENTS = {
    "default": {
        "id": "default",
        "name": "hosted-agent-toolbox-demo",
        "team": "Platform Team",
        "language": "Python 3.11",
        "framework": "Microsoft Agent Framework",
        "toolbox": f"{DEFAULT_TOOLBOX_NAME} (code_interpreter, file_search, web_search)",
        "memory_store": os.getenv("MEMORY_STORE_NAME", ""),
        "resources": "CPU 0.25 / Memory 0.5Gi",
        "url": CLOUD_AGENT_URL or AGENT_URL,
        "auth": "bearer" if CLOUD_AGENT_URL else "none",
        "description": "Python agent with Toolbox MCP — supports code execution, document search, and web search.",
        "builtin": True,
    },
}
HOSTED_AGENTS: dict[str, dict] = _load_json("hosted_agents", _DEFAULT_HOSTED_AGENTS)
# Ensure default always exists
if "default" not in HOSTED_AGENTS:
    HOSTED_AGENTS["default"] = _DEFAULT_HOSTED_AGENTS["default"]
_hosted_agents_migrated = False
for hosted in HOSTED_AGENTS.values():
    if "model" in hosted:
        hosted.pop("model", None)
        _hosted_agents_migrated = True
if _hosted_agents_migrated:
    _save_json("hosted_agents", HOSTED_AGENTS)

# ---- Foundry Agent registry (persisted) ----
_DEFAULT_AGENTS = {
    "default": {
        "id": "default",
        "name": "Default agent (all tools)",
        "tools": list(ALL_TOOLS.keys()),
        "instructions": "You are a helpful assistant with access to multiple tools.",
        "model": DEFAULT_AGENT_MODEL,
        "created_at": time.time(),
        "calls": 0,
        "hosted_agent_id": "default",
        "toolbox_name": DEFAULT_TOOLBOX_NAME,
    },
    "math-only": {
        "id": "math-only",
        "name": "Math agent (code_interpreter only)",
        "tools": ["code_interpreter"],
        "instructions": "You are a math assistant. You only have code_interpreter — use it for any computation.",
        "model": DEFAULT_AGENT_MODEL,
        "created_at": time.time(),
        "calls": 0,
        "hosted_agent_id": "default",
        "toolbox_name": DEFAULT_TOOLBOX_NAME,
    },
    "rag-only": {
        "id": "rag-only",
        "name": "Knowledge agent (file_search only)",
        "tools": ["file_search"],
        "instructions": "You are a knowledge-base assistant. You only have file_search — answer strictly from uploaded documents.",
        "model": DEFAULT_AGENT_MODEL,
        "created_at": time.time(),
        "calls": 0,
        "hosted_agent_id": "default",
        "toolbox_name": DEFAULT_TOOLBOX_NAME,
    },
}
AGENTS: dict[str, dict] = _load_json("agents", _DEFAULT_AGENTS)
# Ensure built-in agents always exist
for k, v in _DEFAULT_AGENTS.items():
    if k not in AGENTS:
        AGENTS[k] = v
for agent in AGENTS.values():
    _agent_model_before = agent.get("model")
    agent.setdefault("loaded_skills", [])
    agent.setdefault("model", DEFAULT_AGENT_MODEL)
    if agent.get("model") == "gpt-4.1-mini" and DEFAULT_AGENT_MODEL != "gpt-4.1-mini":
        agent["model"] = DEFAULT_AGENT_MODEL
    if agent.get("model") != _agent_model_before:
        _save_json("agents", AGENTS)


def _get_token(scope: str = "https://cognitiveservices.azure.com/.default") -> str:
    return DefaultAzureCredential().get_token(scope).token


def _ask_agent(prompt: str, agent_id: str, timeout: float = 180.0) -> dict:
    """Route to real Foundry Hosted Agent or demo builtin hosted endpoint."""
    agent = AGENTS.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id!r} not found")

    agent_model = (agent.get("model") or DEFAULT_AGENT_MODEL).strip()
    toolbox_name = (agent.get("toolbox_name") or DEFAULT_TOOLBOX_NAME).strip() or DEFAULT_TOOLBOX_NAME
    foundry_name = agent.get("foundry_agent_name")

    # ---- Path A: Real Foundry Hosted Agent → its own /responses endpoint ----
    if foundry_name:
        return _ask_foundry_hosted_agent(agent, agent_id, foundry_name, prompt, agent_model, toolbox_name, timeout)

    # ---- Path B: Demo builtin agents → shared hosted agent endpoint ----
    return _ask_hosted_agent(agent, agent_id, prompt, agent_model, toolbox_name, timeout)


def _ask_foundry_hosted_agent(agent: dict, agent_id: str, foundry_name: str,
                               prompt: str, agent_model: str, toolbox_name: str,
                               timeout: float) -> dict:
    """Call a real Foundry Hosted Agent via its /responses endpoint."""
    url = _foundry_agent_responses_url(foundry_name)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DefaultAzureCredential().get_token('https://ai.azure.com/.default').token}",
    }
    t0 = time.time()
    resp = httpx.post(url, json={"input": prompt}, headers=headers, timeout=timeout)
    elapsed_ms = int((time.time() - t0) * 1000)
    resp.raise_for_status()
    payload = resp.json()

    text_parts, tool_calls = [], []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for c in item.get("content", []):
                if isinstance(c, dict) and c.get("type") == "output_text" and c.get("text"):
                    text_parts.append(c["text"])
        if item.get("type") == "function_call_output":
            tool_calls.append({"name": item.get("name", ""), "output": str(item.get("output", ""))[:500]})

    text = "\n".join(text_parts)
    chain = ["You", f"Foundry Hosted Agent → {foundry_name}",
             f"Toolbox [{toolbox_name}]", f"{agent_model} (planning+answer)"]
    for tc in tool_calls:
        chain.append(f"Tool: {tc.get('name') or 'unknown'}")

    usage = payload.get("usage", {})
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)

    agent["calls"] = agent.get("calls", 0) + 1
    _save_json("agents", AGENTS)

    result = {
        "text": text or "(no text response)",
        "tool_calls": tool_calls,
        "image_b64": None,
        "status": payload.get("status", "unknown"),
        "elapsed_ms": elapsed_ms,
        "call_chain": chain,
        "agent_id": agent_id,
        "agent_name": agent["name"],
        "model": agent_model,
        "model_source": "foundry_hosted_agent",
        "toolbox_name": toolbox_name,
        "agent_tools": agent.get("tools", []),
        "foundry_agent_name": foundry_name,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "token_source": "api_usage" if total_tokens else "not_returned",
    }
    _record_history({
        "ts": time.time(),
        "agent_id": agent_id,
        "agent_name": agent["name"],
        "prompt": prompt[:120],
        "elapsed_ms": elapsed_ms,
        "tools_used": [tc.get("name") or "?" for tc in tool_calls],
        "answer_preview": (result["text"] or "")[:120],
    })
    return result


def _ask_hosted_agent(agent: dict, agent_id: str, prompt: str,
                      agent_model: str, toolbox_name: str,
                      timeout: float) -> dict:
    """Forward to hosted agent /responses with agent-specific constraint preamble (demo builtin path)."""
    allowed_tools = ", ".join(agent["tools"]) or "(no tools)"
    base_instructions = agent.get("instructions") or "You are a helpful assistant."
    skills_context = _skill_prompt_block(agent)
    constraint = (
        f"[AGENT: {agent['name']}]\n"
        f"Instructions:\n{base_instructions}\n"
        f"{skills_context}\n"
        f"Selected governed Toolbox: {toolbox_name}.\n"
        f"For this request you may ONLY use these tools: {allowed_tools}.\n"
        f"If a needed tool is not in this list, politely say you cannot help with this query "
        f"because the required tool is not available to this agent.\n\n"
        f"User request: {prompt}"
    )

    ep = ENDPOINTS.get(CURRENT_ENDPOINT["id"]) or next(iter(ENDPOINTS.values()))
    # If agent has a specific hosted agent binding, use its URL
    ha_id = agent.get("hosted_agent_id", "default")
    ha = HOSTED_AGENTS.get(ha_id)
    if ha and ha.get("url"):
        ep = {"url": ha["url"], "auth": ha.get("auth", "bearer"), "label": ha["name"]}
    headers = {"Content-Type": "application/json"}
    if ep["auth"] == "bearer":
        headers["Authorization"] = f"Bearer {_get_token('https://ai.azure.com/.default')}"
    t0 = time.time()
    resp = httpx.post(
        ep["url"],
        json={"input": constraint},
        headers=headers,
        timeout=timeout,
    )
    elapsed_ms = int((time.time() - t0) * 1000)
    resp.raise_for_status()
    payload = resp.json()

    text_parts, image_b64, tool_calls = [], None, []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for c in item.get("content", []):
                if isinstance(c, dict) and c.get("type") == "output_text" and c.get("text"):
                    text_parts.append(c["text"])
        if item.get("type") == "function_call_output":
            tool_calls.append({"name": item.get("name", ""), "output": str(item.get("output", ""))[:500]})

    text = "\n".join(text_parts)

    chain = ["You", f"Hosted Agent [{ep['label']}]", f"Foundry Agent: {agent['name']}", f"Toolbox [{toolbox_name}]", f"{agent_model} (planning)"]
    for tc in tool_calls:
        sig = (tc.get("output", "") + " " + tc.get("name", "")).lower()
        if "execution_output" in sig or "code_interpreter" in sig:
            chain.append("Toolbox MCP → code_interpreter (sandbox executed)")
            tc["name"] = tc["name"] or "code_interpreter"
        elif "file_search" in sig or "vector_store" in sig or "document_chunk" in sig:
            chain.append("Toolbox MCP → file_search (vector store)")
            tc["name"] = tc["name"] or "file_search"
        elif "direct_image" in sig or "b64_json" in sig:
            chain.append("direct_image_generate (Foundry Image API)")
            tc["name"] = tc["name"] or "direct_image_generate"
        elif "direct_web" in sig:
            chain.append("direct_web_search (Foundry Responses API + Bing)")
            tc["name"] = tc["name"] or "direct_web_search"
        elif "url_citation" in sig or "web_search" in sig:
            chain.append("Toolbox MCP → web_search (Bing grounding)")
            tc["name"] = tc["name"] or "web_search"
        else:
            chain.append(f"Tool: {tc.get('name') or 'unknown'}")
    chain.append(f"{agent_model} (final answer)")

    agent["calls"] = agent.get("calls", 0) + 1
    _save_json("agents", AGENTS)

    # Extract token usage from response
    usage = payload.get("usage", {})
    input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    output_tokens = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    total_tokens = usage.get("total_tokens") or (input_tokens + output_tokens)
    token_source = "api_usage" if total_tokens else "not_returned"

    result = {
        "text": text or "(no text response)",
        "tool_calls": tool_calls,
        "image_b64": image_b64,
        "status": payload.get("status", "unknown"),
        "elapsed_ms": elapsed_ms,
        "call_chain": chain,
        "agent_id": agent_id,
        "agent_name": agent["name"],
        "model": agent_model,
        "model_source": "selected agent registry",
        "toolbox_name": toolbox_name,
        "agent_tools": agent["tools"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "token_source": token_source,
    }

    # Record history
    _record_history({
        "ts": time.time(),
        "agent_id": agent_id,
        "agent_name": agent["name"],
        "prompt": prompt[:120],
        "elapsed_ms": elapsed_ms,
        "tools_used": [tc.get("name") or "?" for tc in tool_calls],
        "answer_preview": (result["text"] or "")[:120],
    })
    return result


def _agent_exception_message(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}: {e.response.text[:700]}"
    return f"{type(e).__name__}: {e}"


def _agent_error_response(agent_id: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({
        "ok": False,
        "error": message,
        "text": message,
        "tool_calls": [],
        "call_chain": ["You", "ERROR"],
        "elapsed_ms": 0,
        "agent_id": agent_id,
        "agent_name": AGENTS.get(agent_id, {}).get("name", "?"),
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }, status_code=status_code)


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(os.getenv(name, str(default)).strip() or str(default))
    except ValueError:
        parsed = default
    return max(minimum, min(maximum, parsed))


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _normalize_toolbox_name(raw_name: str) -> str:
    name = re.sub(r"[^a-z0-9-]+", "-", raw_name.strip().lower()).strip("-")
    if not name:
        raise HTTPException(400, "Name is required")
    if len(name) > 64:
        raise HTTPException(400, "Toolbox name must be 64 characters or fewer")
    return name


def _normalize_agent_registry() -> None:
    changed = False
    for aid, agent in list(AGENTS.items()):
        if not isinstance(agent, dict):
            del AGENTS[aid]
            changed = True
            continue
        raw_tools = agent.get("tools", [])
        if not isinstance(raw_tools, list):
            raw_tools = []
        normalized_tools = _dedupe_preserve_order([tool for tool in raw_tools if tool in ALL_TOOLS])
        if normalized_tools != agent.get("tools"):
            agent["tools"] = normalized_tools
            changed = True
        if agent.get("hosted_agent_id") not in HOSTED_AGENTS:
            agent["hosted_agent_id"] = "default"
            changed = True
        if not isinstance(agent.get("toolbox_name"), str) or not agent.get("toolbox_name", "").strip():
            agent["toolbox_name"] = DEFAULT_TOOLBOX_NAME
            changed = True
        if not isinstance(agent.get("loaded_skills"), list):
            agent["loaded_skills"] = []
            changed = True
        try:
            agent["calls"] = int(agent.get("calls", 0))
        except (TypeError, ValueError):
            agent["calls"] = 0
            changed = True
    if changed:
        _save_json("agents", AGENTS)


_normalize_agent_registry()


def _memory_semantic_hit(text: str) -> tuple[bool, list[str]]:
    normalized = text.lower()
    checks = {
        "enterprise or agent context": any(term in normalized for term in ("enterprise", "agent", "platform")),
        "memory preference": "memory" in normalized,
        "Microsoft Foundry": "foundry" in normalized,
    }
    matched = [name for name, ok in checks.items() if ok]
    return len(matched) == len(checks), matched


def _memory_project_endpoint() -> str:
    return os.getenv("MEMORY_PROJECT_ENDPOINT", "").strip() or PROJECT_ENDPOINT


def _memory_store_search(memory_store: str, query: str, scope: str = "default") -> dict:
    endpoint = _memory_project_endpoint()
    if not endpoint:
        return {
            "status": "not_configured",
            "remembered": False,
            "query": query,
            "error": "MEMORY_PROJECT_ENDPOINT or AZURE_AI_PROJECT_ENDPOINT is required.",
        }

    t0 = time.time()
    try:
        from azure.ai.projects import AIProjectClient

        with AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential(), allow_preview=True) as client:
            result = client.beta.memory_stores.search_memories(
                name=memory_store,
                scope=scope,
                items=query,
            )

        memories = getattr(result, "memories", []) or []
        evidence_items = []
        for memory in memories[:5]:
            item = getattr(memory, "memory_item", None)
            memory_id = getattr(item, "memory_id", None) if item else getattr(memory, "memory_id", None)
            content = getattr(item, "content", None) if item else getattr(memory, "content", None)
            item_scope = getattr(item, "scope", None) if item else getattr(memory, "scope", None)
            item_kind = getattr(item, "kind", None) if item else getattr(memory, "kind", None)
            updated_at = getattr(item, "updated_at", None) if item else getattr(memory, "updated_at", None)
            if content is None:
                content = str(memory)

            evidence = {
                "id": str(memory_id or ""),
                "scope": str(item_scope or scope),
                "kind": str(item_kind or ""),
                "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at or ""),
                "content": str(content)[:900],
            }
            for attr in ("score", "similarity_score", "relevance_score"):
                score = getattr(memory, attr, None)
                if score is not None:
                    try:
                        evidence["score"] = round(float(score), 4)
                    except (TypeError, ValueError):
                        evidence["score"] = str(score)
                    break
            evidence_items.append(evidence)

        combined_text = "\n".join(item["content"] for item in evidence_items)
        remembered, matched_signals = _memory_semantic_hit(combined_text)
        usage = getattr(result, "usage", None)
        return {
            "status": "completed",
            "evidence_found": bool(evidence_items),
            "remembered": remembered,
            "matched_signals": matched_signals,
            "query": query,
            "api": "client.beta.memory_stores.search_memories",
            "search_id": str(getattr(result, "search_id", "") or ""),
            "endpoint": endpoint,
            "scope": scope,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "count": len(memories),
            "returned": len(evidence_items),
            "usage": {
                "input_tokens": getattr(usage, "input_tokens", None),
                "embedding_tokens": getattr(usage, "embedding_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            } if usage else None,
            "memories": evidence_items,
        }
    except Exception as e:
        return {
            "status": "error",
            "remembered": False,
            "query": query,
            "endpoint": endpoint,
            "scope": scope,
            "elapsed_ms": int((time.time() - t0) * 1000),
            "error": _agent_exception_message(e),
        }


# ---------- API: hosted agents (multi-team registry) ----------

class HostedAgentCreate(BaseModel):
    name: str
    team: str = ""
    language: str = ""
    framework: str = ""
    toolbox: str = ""
    memory_store: str = ""
    resources: str = ""
    url: str = ""
    auth: str = "bearer"
    description: str = ""


@app.get("/api/hosted-agents")
def list_hosted_agents():
    return JSONResponse({"hosted_agents": list(HOSTED_AGENTS.values())})


@app.post("/api/hosted-agents")
def create_hosted_agent(body: HostedAgentCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    auth = body.auth.strip().lower() or "bearer"
    if auth not in {"bearer", "none"}:
        raise HTTPException(400, "auth must be 'bearer' or 'none'")
    # Reject duplicate names (case-insensitive)
    for ha in HOSTED_AGENTS.values():
        if ha.get("name", "").strip().lower() == name.lower():
            raise HTTPException(409, f"Hosted agent named {name!r} already exists (id={ha['id']})")
    hid = "ha-" + uuid.uuid4().hex[:8]
    HOSTED_AGENTS[hid] = {
        "id": hid,
        "name": name,
        "team": body.team,
        "language": body.language,
        "framework": body.framework,
        "toolbox": body.toolbox,
        "memory_store": body.memory_store,
        "resources": body.resources,
        "url": body.url,
        "auth": auth,
        "description": body.description,
        "builtin": False,
    }
    _save_json("hosted_agents", HOSTED_AGENTS)
    return JSONResponse(HOSTED_AGENTS[hid])


@app.delete("/api/hosted-agents/{hid}")
def delete_hosted_agent(hid: str):
    if hid == "default":
        raise HTTPException(400, "Default hosted agent cannot be deleted")
    if hid not in HOSTED_AGENTS:
        raise HTTPException(404, f"Hosted agent {hid!r} not found")
    del HOSTED_AGENTS[hid]
    # Reset any agents that were bound to this hosted agent
    for a in AGENTS.values():
        if a.get("hosted_agent_id") == hid:
            a["hosted_agent_id"] = "default"
    _save_json("hosted_agents", HOSTED_AGENTS)
    _save_json("agents", AGENTS)
    return JSONResponse({"ok": True})


# ---------- API: Foundry Agents ----------

class AgentCreate(BaseModel):
    name: str
    tools: list[str]
    instructions: str = "You are a helpful assistant."
    hosted_agent_id: str = "default"
    model: str | None = None
    toolbox_name: str | None = None


class AgentUpdate(BaseModel):
    tools: list[str]
    hosted_agent_id: str | None = None
    model: str | None = None
    toolbox_name: str | None = None


class AgentSkillReq(BaseModel):
    skill_id: str


@app.get("/api/agents")
def list_agents():
    return JSONResponse({"agents": list(AGENTS.values())})


def _sanitize_foundry_agent_name(name: str) -> str:
    """Convert display name to Foundry-safe agent name (lowercase, hyphens, no spaces)."""
    safe = re.sub(r"[^a-z0-9-]+", "-", name.strip().lower()).strip("-")
    return safe[:64] or "agent"


@app.post("/api/agents")
def create_agent(body: AgentCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    for a in AGENTS.values():
        if a.get("name", "").strip().lower() == name.lower():
            raise HTTPException(409, f"Agent named {name!r} already exists (id={a['id']})")
    tools = _dedupe_preserve_order(body.tools)
    bad = [t for t in tools if t not in ALL_TOOLS]
    if bad:
        raise HTTPException(400, f"Unknown tools: {bad}")
    if body.hosted_agent_id not in HOSTED_AGENTS:
        raise HTTPException(400, f"Hosted agent {body.hosted_agent_id!r} not found")
    toolbox_name = _resolve_agent_toolbox_name(body.toolbox_name)
    _validate_agent_tools_for_toolbox(tools, toolbox_name)
    agent_model = (body.model or DEFAULT_AGENT_MODEL).strip() or DEFAULT_AGENT_MODEL
    instructions = body.instructions or "You are a helpful assistant."
    foundry_name = _sanitize_foundry_agent_name(name)

    if not FOUNDRY_ACR_IMAGE:
        raise HTTPException(
            400,
            "FOUNDRY_ACR_IMAGE env var is required. Set it to your ACR image URL "
            "(e.g. myacr.azurecr.io/hosted-agent-toolbox-demo:latest) so the app "
            "can create real Foundry hosted agents.",
        )

    # ---- Create real Foundry Hosted Agent via REST API ----
    try:
        foundry_result = _foundry_create_hosted_agent(
            name=foundry_name,
            model=agent_model,
            instructions=instructions,
            acr_image=FOUNDRY_ACR_IMAGE,
            toolbox_name=toolbox_name,
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            max(e.response.status_code, 400),
            f"Foundry API error creating hosted agent: {e.response.text[:500]}",
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to create Foundry hosted agent: {type(e).__name__}: {e}")

    aid = "agent-" + uuid.uuid4().hex[:8]
    AGENTS[aid] = {
        "id": aid,
        "name": name,
        "tools": tools,
        "instructions": instructions,
        "model": agent_model,
        "created_at": time.time(),
        "calls": 0,
        "hosted_agent_id": body.hosted_agent_id,
        "toolbox_name": toolbox_name,
        "loaded_skills": [],
        "foundry_agent_name": foundry_name,
        "foundry_agent_kind": "hosted",
        "foundry_agent_id": foundry_result.get("name", foundry_name),
    }
    _save_json("agents", AGENTS)
    return JSONResponse(AGENTS[aid])


@app.put("/api/agents/{aid}")
def update_agent(aid: str, body: AgentUpdate):
    if aid not in AGENTS:
        raise HTTPException(404)
    tools = _dedupe_preserve_order(body.tools)
    bad = [t for t in tools if t not in ALL_TOOLS]
    if bad:
        raise HTTPException(400, f"Unknown tools: {bad}")
    if body.hosted_agent_id and body.hosted_agent_id not in HOSTED_AGENTS:
        raise HTTPException(400, f"Hosted agent {body.hosted_agent_id!r} not found")
    toolbox_name = _resolve_agent_toolbox_name(body.toolbox_name or AGENTS[aid].get("toolbox_name"))
    _validate_agent_tools_for_toolbox(tools, toolbox_name)
    AGENTS[aid]["tools"] = tools
    AGENTS[aid]["toolbox_name"] = toolbox_name
    if body.hosted_agent_id:
        AGENTS[aid]["hosted_agent_id"] = body.hosted_agent_id
    if body.model is not None:
        model = body.model.strip()
        if not model:
            raise HTTPException(400, "Model deployment is required")
        AGENTS[aid]["model"] = model
    _save_json("agents", AGENTS)
    return JSONResponse(AGENTS[aid])


@app.delete("/api/agents/{aid}")
def delete_agent(aid: str):
    if aid in {"default", "math-only", "rag-only"}:
        raise HTTPException(400, "Built-in agents cannot be deleted")
    if aid not in AGENTS:
        raise HTTPException(404, f"Agent {aid!r} not found")

    # Delete real Foundry Agent via REST API
    foundry_name = AGENTS[aid].get("foundry_agent_name")
    foundry_delete_error = None
    if foundry_name:
        try:
            ok = _foundry_delete_agent(foundry_name)
            if not ok:
                foundry_delete_error = f"Failed to delete Foundry agent {foundry_name!r}"
        except Exception as e:
            foundry_delete_error = f"{type(e).__name__}: {e}"

    del AGENTS[aid]
    _save_json("agents", AGENTS)
    result = {"ok": True}
    if foundry_delete_error:
        result["foundry_delete_error"] = foundry_delete_error
    return JSONResponse(result)


@app.get("/api/skills")
def list_skills(refresh: bool = False):
    catalog = _load_skill_catalog(refresh=refresh)
    return JSONResponse({
        "source": "https://github.com/microsoft/skills",
        "count": len(catalog),
        "skills": catalog,
    })


@app.post("/api/agents/{aid}/skills")
def load_agent_skill(aid: str, body: AgentSkillReq):
    if aid not in AGENTS:
        raise HTTPException(404, f"Agent {aid!r} not found")
    catalog = _load_skill_catalog(refresh=False)
    catalog_item = next((item for item in catalog if item.get("id") == body.skill_id), None)
    if not catalog_item:
        raise HTTPException(404, f"Skill {body.skill_id!r} not found in microsoft/skills catalog")
    agent = AGENTS[aid]
    loaded_skills = agent.setdefault("loaded_skills", [])
    if any(skill.get("id") == body.skill_id for skill in loaded_skills):
        return JSONResponse(agent)
    if len(loaded_skills) >= MAX_SKILLS_PER_AGENT:
        raise HTTPException(400, f"An agent can load at most {MAX_SKILLS_PER_AGENT} skills in this demo")

    metadata, content = _fetch_skill_content(body.skill_id)
    loaded_skills.append({
        "id": body.skill_id,
        "name": metadata.get("name") or catalog_item["name"],
        "label": catalog_item.get("label") or catalog_item["name"],
        "description": metadata.get("description") or catalog_item.get("description", ""),
        "category": catalog_item.get("category", "Other"),
        "source_url": catalog_item.get("source_url", "https://github.com/microsoft/skills"),
        "content": content,
        "loaded_at": time.time(),
    })
    _save_json("agents", AGENTS)
    return JSONResponse(agent)


@app.post("/api/agents/{aid}/skills/remove")
def remove_agent_skill(aid: str, body: AgentSkillReq):
    if aid not in AGENTS:
        raise HTTPException(404, f"Agent {aid!r} not found")
    agent = AGENTS[aid]
    agent["loaded_skills"] = [skill for skill in agent.get("loaded_skills", []) if skill.get("id") != body.skill_id]
    _save_json("agents", AGENTS)
    return JSONResponse(agent)


# ---------- API: tools / system info ----------

_toolbox_cache: dict[str, Any] = {"tools": None, "ts": 0}

@app.get("/api/toolbox-info")
def toolbox_info():
    """Live Toolbox tool list from MCP + the static direct tool list. Cached 60s."""
    now = time.time()
    toolbox_tools = _toolbox_cache.get("tools")
    if toolbox_tools and (now - _toolbox_cache["ts"]) < 60:
        pass  # use cache
    else:
        toolbox_tools = []
        try:
            token = _get_token("https://ai.azure.com/.default")
            # Use the azd-deployed project's Toolbox
            cloud_base = CLOUD_AGENT_URL.split("/agents/")[0] if "/agents/" in CLOUD_AGENT_URL else PROJECT_ENDPOINT.rstrip("/")
            url = f"{cloud_base}/toolboxes/agent-tools/mcp?api-version=v1"
            headers = {
                "Authorization": f"Bearer {token}",
                "Foundry-Features": "Toolboxes=V1Preview",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            httpx.post(url, headers=headers, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                           "clientInfo": {"name": "demo-app", "version": "0.2"}}
            }, timeout=8.0)
            r = httpx.post(url, headers=headers, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
            }, timeout=8.0)
            toolbox_tools = [
                {"name": t.get("name", ""), "description": t.get("description", "")[:120]}
                for t in r.json().get("result", {}).get("tools", [])
            ]
            _toolbox_cache["tools"] = toolbox_tools
            _toolbox_cache["ts"] = now
        except Exception as e:
            toolbox_tools = _toolbox_cache.get("tools") or [{"name": "error", "description": str(e)[:120]}]

    return JSONResponse({
        "agent_endpoint": AGENT_URL,
        "project_endpoint": PROJECT_ENDPOINT,
        "toolbox_name": "agent-tools",
        "toolbox_endpoint": f"{PROJECT_ENDPOINT.rstrip('/')}/toolboxes/agent-tools/mcp?api-version=v1",
        "toolbox_tools": toolbox_tools,
        "toolbox_catalog": _toolbox_tool_catalog(),
        "all_tools": ALL_TOOLS,
        "default_agent_model": DEFAULT_AGENT_MODEL,
        "evaluation_model_deployment": EVALUATION_MODEL_DEPLOYMENT,
        "image_generation_model": IMAGE_GENERATION_MODEL,
        "endpoints": ENDPOINTS,
        "current_endpoint": CURRENT_ENDPOINT["id"],
    })


# ---------- API: Model Deployments (dynamic from Foundry) ----------

_model_cache: dict[str, Any] = {"deployments": None, "ts": 0}


@app.get("/api/model-deployments")
def model_deployments():
    """List model deployments available in the Foundry project. Cached 120s."""
    now = time.time()
    cached = _model_cache.get("deployments")
    if cached and now - _model_cache.get("ts", 0) < 120:
        return JSONResponse({"deployments": cached, "source": "cache", "default_model": DEFAULT_AGENT_MODEL})

    if not ACCOUNT_BASE:
        return JSONResponse({
            "deployments": [{"id": DEFAULT_AGENT_MODEL, "model": DEFAULT_AGENT_MODEL, "status": "unknown"}],
            "source": "fallback",
            "default_model": DEFAULT_AGENT_MODEL,
            "error": "No project endpoint configured.",
        })

    try:
        token = _get_token("https://ai.azure.com/.default")
        # Source: Foundry project-level deployments API
        # Path: {project_endpoint}/deployments?api-version=v1
        url = f"{PROJECT_ENDPOINT.rstrip('/')}/deployments?api-version=v1"
        r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
        r.raise_for_status()
        raw = r.json().get("value", [])
        deployments = []
        for d in raw:
            dep_name = d.get("name", "")
            model_name = d.get("modelName", "")
            model_version = d.get("modelVersion", "")
            dep_type = d.get("type", "")
            deployments.append({
                "id": dep_name,
                "model": model_name,
                "version": model_version,
                "type": dep_type,
            })
        deployments.sort(key=lambda x: x["id"])
        _model_cache["deployments"] = deployments
        _model_cache["ts"] = now
        return JSONResponse({"deployments": deployments, "source": "live", "default_model": DEFAULT_AGENT_MODEL})
    except Exception as e:
        # Fallback: return env var deployment name so the UI is never empty
        fallback = DEFAULT_AGENT_MODEL
        return JSONResponse({
            "deployments": [{"id": fallback, "model": fallback, "status": "unknown"}],
            "source": "fallback",
            "default_model": DEFAULT_AGENT_MODEL,
            "error": str(e)[:200],
        })


@app.get("/api/memory-status")
def memory_status():
    """Return Foundry Memory configuration status."""
    memory_store = os.getenv("MEMORY_STORE_NAME", "").strip()
    update_delay = os.getenv("MEMORY_UPDATE_DELAY_SECONDS", "0").strip() or "0"
    last_probe = _load_json("memory_proof", None)
    return JSONResponse({
        "enabled": bool(memory_store),
        "store_name": memory_store or None,
        "project_endpoint": os.getenv("MEMORY_PROJECT_ENDPOINT", "").strip() or PROJECT_ENDPOINT,
        "scope": "default",
        "update_delay_seconds": update_delay,
        "last_probe": last_probe,
        "description": "Foundry Memory — managed long-term cross-session memory (preview)." if memory_store else "Memory not configured. Set MEMORY_STORE_NAME to enable.",
        "source": MEMORY_SOURCE_URL,
        "sdk_source": MEMORY_SDK_SOURCE_URL,
    })


@app.post("/api/memory-demo/run")
def run_memory_demo(agent_id: str = Form("default")):
    """Run a two-call Memory proof: write a durable preference, then recall it without chat history."""
    memory_store = os.getenv("MEMORY_STORE_NAME", "").strip()
    if not memory_store:
        return JSONResponse({
            "enabled": False,
            "remembered": False,
            "verdict": "disabled",
            "message": "MEMORY_STORE_NAME is not configured.",
            "source": MEMORY_SOURCE_URL,
        })
    if agent_id not in AGENTS:
        raise HTTPException(404, f"Agent {agent_id!r} not found")

    proof_id = f"MEM-{int(time.time())}-{uuid.uuid4().hex[:6]}"
    value = "The enterprise platform should keep agent memory on Microsoft Foundry"
    write_prompt = (
        "This is a Foundry Memory proof. Remember this durable enterprise preference for future conversations: "
        "The enterprise platform's agent memory should remain on Microsoft Foundry. "
        f"Tracking id: {proof_id}. Reply exactly MEMORY_SAVED and nothing else."
    )
    recall_prompt = (
        "Memory recall check. Without relying on chat history, what platform should the enterprise platform keep "
        "enterprise agent memory on? Answer with the platform and one short reason from long-term memory. "
        "If long-term memory has no relevant platform preference, answer UNKNOWN. Do not make a guess."
    )
    retry_count = _env_int("MEMORY_PROOF_RETRY_COUNT", 6, 1, 12)
    retry_interval = _env_int("MEMORY_PROOF_RETRY_INTERVAL_SECONDS", 8, 1, 30)
    store_query = "What platform should the enterprise platform keep agent memory on?"
    proof = {
        "enabled": True,
        "store_name": memory_store,
        "scope": "default",
        "update_delay_seconds": os.getenv("MEMORY_UPDATE_DELAY_SECONDS", "0").strip() or "0",
        "retry_count": retry_count,
        "retry_interval_seconds": retry_interval,
        "proof_id": proof_id,
        "expected_value": value,
        "expected_signals": ["enterprise platform", "enterprise agent memory", "Microsoft Foundry"],
        "agent_id": agent_id,
        "agent_name": AGENTS[agent_id].get("name", "?"),
        "source": MEMORY_SOURCE_URL,
        "sdk_source": MEMORY_SDK_SOURCE_URL,
        "created_at": time.time(),
    }

    try:
        write_result = _ask_agent(write_prompt, agent_id, timeout=45.0)
        proof["write"] = {
            "status": write_result.get("status", "unknown"),
            "elapsed_ms": write_result.get("elapsed_ms", 0),
            "response": write_result.get("text", "")[:700],
        }
    except Exception as e:
        proof.update({
            "remembered": False,
            "verdict": "write_failed",
            "message": f"Memory write call failed: {_agent_exception_message(e)}",
        })
        _save_json("memory_proof", proof)
        return JSONResponse(proof)

    store_attempts = []
    store_evidence = {}
    for attempt in range(1, retry_count + 1):
        if attempt > 1:
            time.sleep(retry_interval)
        store_evidence = _memory_store_search(memory_store, store_query, scope="default")
        store_evidence["attempt"] = attempt
        store_attempts.append(store_evidence)
        if store_evidence.get("remembered"):
            break

    recall_attempts = []
    hosted_remembered = False
    hosted_recall_limit = 1 if store_evidence.get("remembered") else retry_count
    for attempt in range(1, hosted_recall_limit + 1):
        if attempt > 1:
            time.sleep(retry_interval)
        try:
            recall_result = _ask_agent(recall_prompt, agent_id, timeout=45.0)
            recall_text = recall_result.get("text", "")
            hosted_remembered, matched_signals = _memory_semantic_hit(recall_text)
            recall_attempt = {
                "attempt": attempt,
                "remembered": hosted_remembered,
                "matched_signals": matched_signals,
                "status": recall_result.get("status", "unknown"),
                "elapsed_ms": recall_result.get("elapsed_ms", 0),
                "response": recall_text[:900],
            }
        except Exception as e:
            recall_attempt = {
                "attempt": attempt,
                "remembered": False,
                "status": "error",
                "elapsed_ms": 0,
                "response": _agent_exception_message(e),
            }
        recall_attempts.append(recall_attempt)
        if hosted_remembered:
            break

    last_recall = recall_attempts[-1] if recall_attempts else {}
    store_remembered = bool(store_evidence.get("remembered"))
    remembered = hosted_remembered or store_remembered
    memory_path = "hosted_recall" if hosted_remembered else ("store_search" if store_remembered else "not_observed")
    proof.update({
        "remembered": remembered,
        "verdict": "passed" if remembered else "not_observed",
        "memory_path": memory_path,
        "message": (
            "A stateless recall request retrieved the durable enterprise preference after Foundry Memory indexing."
            if hosted_remembered else
            "Foundry Memory store search returned the durable enterprise preference. Hosted recall is shown separately as model-level retrieval evidence."
            if store_remembered else
            "Neither Hosted recall nor direct Memory store search returned the durable enterprise preference within the retry window."
        ),
        "store_evidence": store_evidence,
        "store_attempts": store_attempts,
        "recall": last_recall,
        "recall_attempts": recall_attempts,
    })

    _save_json("memory_proof", proof)
    return JSONResponse(proof)


@app.get("/api/endpoints")
def list_endpoints():
    return JSONResponse({"endpoints": ENDPOINTS, "current": CURRENT_ENDPOINT["id"]})


class EndpointSwitchReq(BaseModel):
    id: str


@app.post("/api/endpoints/select")
def select_endpoint(req: EndpointSwitchReq):
    if req.id not in ENDPOINTS:
        raise HTTPException(404, f"Endpoint {req.id!r} not found. Available: {list(ENDPOINTS)}")
    CURRENT_ENDPOINT["id"] = req.id
    return JSONResponse({"ok": True, "current": req.id, "endpoint": ENDPOINTS[req.id]})


# ---------- API: hosted agent health + history ----------

# Persisted request history of last 50 requests. This keeps the Fleet view useful after service restarts.
HISTORY: list[dict] = _load_json("history", [])
if not isinstance(HISTORY, list):
    HISTORY = []


def _record_history(entry: dict):
    HISTORY.append(entry)
    if len(HISTORY) > 50:
        del HISTORY[:-50]
    _save_json("history", HISTORY)


@app.get("/api/agent-health")
def agent_health():
    """Live health of the hosted agent — Foundry cloud or local process."""
    import socket
    import subprocess
    cur = CURRENT_ENDPOINT["id"]
    ep = ENDPOINTS.get(cur) or next(iter(ENDPOINTS.values()))

    # Foundry cloud mode — no local process, show cloud agent info
    if cur == "foundry":
        info = {
            "endpoint": ep["url"][:80] + "...",
            "alive": True,
            "mode": "foundry",
            "agent_name": "hosted-agent-toolbox-demo",
            "description": ep.get("description", ""),
            "pid": None, "uptime_s": None, "rss_mb": None,
            "probe_latency_ms": None, "last_error": None,
        }
        # Quick probe the cloud endpoint
        try:
            t0 = time.time()
            r = httpx.get(ep["url"].replace("/responses", "/readiness").split("?")[0],
                          headers={"Authorization": f"Bearer {_get_token('https://ai.azure.com/.default')}"},
                          timeout=3.0)
            info["probe_latency_ms"] = int((time.time() - t0) * 1000)
            info["alive"] = r.status_code < 500
        except Exception as e:
            info["last_error"] = str(e)[:100]
            info["alive"] = False
        return JSONResponse(info)

    # Local mode
    info = {
        "endpoint": AGENT_URL,
        "alive": False, "mode": "local",
        "pid": None,
        "uptime_s": None,
        "rss_mb": None,
        "probe_latency_ms": None,
        "last_error": None,
    }
    # Probe port
    try:
        host = AGENT_URL.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
        port = int(AGENT_URL.split(":")[-1].split("/")[0])
        t0 = time.time()
        with socket.create_connection((host, port), timeout=2) as s:
            info["probe_latency_ms"] = int((time.time() - t0) * 1000)
            info["alive"] = True
    except Exception as e:
        info["last_error"] = str(e)
        return JSONResponse(info)

    # Find the python process listening on that port
    try:
        out = subprocess.run(
            ["ss", "-tlnp"], capture_output=True, text=True, timeout=3
        ).stdout
        for line in out.splitlines():
            if f":{port} " in line and "python" in line:
                # extract pid=NNN
                import re
                m = re.search(r"pid=(\d+)", line)
                if m:
                    info["pid"] = int(m.group(1))
                    break
    except Exception:
        pass

    # Get process info
    if info["pid"]:
        try:
            ps = subprocess.run(
                ["ps", "-p", str(info["pid"]), "-o", "etimes=,rss="],
                capture_output=True, text=True, timeout=3
            ).stdout.strip().split()
            if len(ps) >= 2:
                info["uptime_s"] = int(ps[0])
                info["rss_mb"] = round(int(ps[1]) / 1024, 1)
        except Exception:
            pass

    return JSONResponse(info)


@app.get("/api/agent-logs")
def agent_logs():
    """Tail logs for the currently-selected hosted agent (local file or Foundry App Insights)."""
    cur = CURRENT_ENDPOINT["id"]
    if cur == "foundry":
        # Query Application Insights AppTraces table via Log Analytics REST API
        ws_id = os.getenv("CLOUD_LOG_WORKSPACE_ID", "")
        if not ws_id:
            return JSONResponse({"log_path": "(CLOUD_LOG_WORKSPACE_ID env not set)",
                                 "lines": [], "endpoint": "foundry",
                                 "hint": "Set CLOUD_LOG_WORKSPACE_ID to the Log Analytics workspace customerId"})
        try:
            tok = _get_token("https://api.loganalytics.io/.default")
            kql = ("AppTraces | where TimeGenerated > ago(1h) "
                   "| top 50 by TimeGenerated desc "
                   "| project TimeGenerated, SeverityLevel, Message")
            r = httpx.post(f"https://api.loganalytics.io/v1/workspaces/{ws_id}/query",
                           headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                           json={"query": kql}, timeout=8.0)
            r.raise_for_status()
            data = r.json()
            rows = data.get("tables", [{}])[0].get("rows", [])
            sev_map = {0: "VERB", 1: "INFO", 2: "WARN", 3: "ERR ", 4: "CRIT"}
            # Reverse so oldest is first (so tail appearance matches local logs)
            lines = [f"{ts[:19]} [{sev_map.get(sev,'INFO')}] {msg}\n" for ts, sev, msg in reversed(rows)]
            return JSONResponse({"log_path": f"AppTraces (workspace {ws_id[:8]}...)",
                                 "lines": lines, "endpoint": "foundry",
                                 "hint": "Live tail of Foundry hosted agent via Application Insights (last 1h, 50 lines)."})
        except Exception as e:
            return JSONResponse({"log_path": "(error querying Log Analytics)",
                                 "lines": [f"ERROR: {e}\n"], "endpoint": "foundry", "hint": ""})

    # ---- local hosted agent: tail file ----
    candidates = [
        "/tmp/agent_server.log",
        "/tmp/server_final.log",
        "/tmp/server_3tools2.log",
        "/tmp/foundry_host_image4.log",
    ]
    log_lines = []
    log_path = None
    for p in candidates:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                if len(lines) > 10:
                    log_path = p
                    log_lines = lines[-50:]
                    break
        except Exception:
            continue

    return JSONResponse({
        "log_path": log_path or "(no log file found — agent stdout not captured)",
        "lines": log_lines,
        "endpoint": "local",
        "hint": "Restart with: python -u main.py 2>&1 | tee /tmp/agent_server.log",
    })


@app.get("/api/history")
def history():
    return JSONResponse({"history": list(reversed(HISTORY))})


# ---------- API: chat / voice / image / edge ----------

@app.post("/api/chat")
def chat(message: str = Form(...), agent_id: str = Form("default")):
    try:
        return JSONResponse(_ask_agent(message, agent_id))
    except HTTPException as e:
        return _agent_error_response(agent_id, str(e.detail), e.status_code)
    except httpx.HTTPStatusError as e:
        return _agent_error_response(
            agent_id,
            f"Hosted agent returned {e.response.status_code}: {e.response.text[:300]}",
            max(e.response.status_code, 400),
        )
    except Exception as e:
        return _agent_error_response(agent_id, f"Error: {type(e).__name__}: {e}", 500)


@app.post("/api/voice")
def voice(audio: UploadFile = File(...), agent_id: str = Form("default")):
    if agent_id not in AGENTS:
        return _agent_error_response(agent_id, f"Agent {agent_id!r} not found", 404)

    tmp_path = ""
    try:
        suffix = ".webm" if "webm" in (audio.content_type or "") else ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio.file.read())
            tmp_path = tmp.name

        token = _get_token()
        url = f"{ACCOUNT_BASE}/openai/deployments/{WHISPER_DEPLOYMENT}/audio/transcriptions?api-version=2024-06-01"
        with open(tmp_path, "rb") as f:
            r = httpx.post(url, headers={"Authorization": f"Bearer {token}"},
                           files={"file": ("audio" + suffix, f, audio.content_type or "audio/webm")},
                           data={"response_format": "text"}, timeout=60.0)
        r.raise_for_status()
        transcript = r.text.strip() or "(silence)"

        if transcript == "(silence)":
            return JSONResponse({"transcript": transcript, "text": "I didn't catch that. Try again.",
                                 "tool_calls": [], "call_chain": [], "elapsed_ms": 0,
                                 "agent_id": agent_id, "agent_name": AGENTS[agent_id]["name"]})

        res = _ask_agent(transcript, agent_id)
        res["transcript"] = transcript
        return JSONResponse(res)
    except httpx.HTTPStatusError as e:
        return _agent_error_response(
            agent_id,
            f"Voice request returned {e.response.status_code}: {e.response.text[:300]}",
            max(e.response.status_code, 400),
        )
    except HTTPException as e:
        return _agent_error_response(agent_id, str(e.detail), e.status_code)
    except Exception as e:
        return _agent_error_response(agent_id, f"Voice request failed: {type(e).__name__}: {e}", 500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/api/image")
def image_gen(prompt: str = Form(...), agent_id: str = Form("default")):
    if agent_id not in AGENTS:
        return _agent_error_response(agent_id, f"Agent {agent_id!r} not found", 404)
    if "direct_image_generate" not in AGENTS.get(agent_id, {}).get("tools", []):
        return _agent_error_response(agent_id, f"Agent {agent_id!r} does not have direct_image_generate enabled.", 403)
    try:
        token = _get_token("https://ai.azure.com/.default")
        url = f"{ACCOUNT_BASE}/openai/v1/images/generations"
        t0 = time.time()
        r = httpx.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                   json={"model": IMAGE_GENERATION_MODEL, "prompt": prompt, "n": 1, "size": "1024x1024"}, timeout=180.0)
        elapsed_ms = int((time.time() - t0) * 1000)
        r.raise_for_status()
        data = r.json().get("data", [])
        b64 = data[0].get("b64_json", "") if data else ""
        revised = data[0].get("revised_prompt", prompt) if data else prompt
        AGENTS[agent_id]["calls"] += 1
        _save_json("agents", AGENTS)
        return JSONResponse({
            "text": f"Image generated. Revised prompt: {revised[:200]}",
            "image_b64": b64,
            "tool_calls": [{"name": "direct_image_generate", "output": f"b64_json length: {len(b64)}"}],
            "call_chain": ["You", "Direct Foundry Image API", f"Foundry Agent: {AGENTS[agent_id]['name']}",
                           "direct_image_generate", f"Foundry Image API ({IMAGE_GENERATION_MODEL})"],
            "elapsed_ms": elapsed_ms,
            "agent_id": agent_id, "agent_name": AGENTS[agent_id]["name"],
            "model": IMAGE_GENERATION_MODEL,
            "model_source": "IMAGE_GENERATION_MODEL or AZURE_AI_IMAGE_DEPLOYMENT_NAME",
            "agent_tools": AGENTS[agent_id]["tools"],
        })
    except httpx.HTTPStatusError as e:
        return _agent_error_response(
            agent_id,
            f"Image generation returned {e.response.status_code}: {e.response.text[:300]}",
            max(e.response.status_code, 400),
        )
    except Exception as e:
        return _agent_error_response(agent_id, f"Image generation failed: {type(e).__name__}: {e}", 500)


@app.post("/api/edge-cloud")
def edge_cloud(agent_id: str = Form("default")):
    import random
    random.seed(42)
    readings = {
        "temperature_c": [round(20 + 5 * random.random(), 1) for _ in range(24)],
        "humidity_pct": [round(40 + 20 * random.random(), 1) for _ in range(24)],
        "co2_ppm": [round(400 + 600 * random.random(), 0) for _ in range(24)],
    }
    prompt = (
        "I have 24 hourly indoor air quality sensor readings from a gaming room:\n"
        f"{json.dumps(readings, indent=2)}\n\n"
        "Use code_interpreter to compute mean/max/min for each sensor and give a "
        "2-sentence ventilation recommendation."
    )
    res = _ask_agent(prompt, agent_id)
    res["sensor_data"] = readings
    return JSONResponse(res)


# ---------- API: Toolbox Management (Lifecycle Step 1: Build) ----------

TOOLBOX_API_BASE = PROJECT_ENDPOINT.rstrip("/") + "/toolboxes" if PROJECT_ENDPOINT else ""


def _configured_vector_store_ids() -> list[str]:
    raw_values = [os.getenv("VECTOR_STORE_ID", ""), os.getenv("FILE_SEARCH_VECTOR_STORE_IDS", "")]
    ids: list[str] = []
    for raw in raw_values:
        for item in raw.replace(";", ",").split(","):
            value = item.strip()
            if value and value not in ids:
                ids.append(value)
    return ids


def _env_value(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


# Configuration fields for each Toolbox tool that requires setup.
# READY tools (code_interpreter, web_search, etc.) have no fields.
# Frontend renders these as inline forms when a PLAN card is checked.
TOOL_CONFIG_FIELDS: dict[str, list[dict[str, Any]]] = {
    "file_search": [
        {"key": "vector_store_id", "label": "Vector Store ID", "placeholder": "vs_abc123", "required": True, "env_keys": ["VECTOR_STORE_ID", "FILE_SEARCH_VECTOR_STORE_IDS"]},
    ],
    "web_search_custom": [
        {"key": "connection_id", "label": "Bing Custom Search Connection ID", "placeholder": "Project connection ID", "required": True, "env_keys": ["BING_CUSTOM_SEARCH_PROJECT_CONNECTION_ID"]},
        {"key": "instance_name", "label": "Instance Name", "placeholder": "my-custom-search", "required": True, "env_keys": ["BING_CUSTOM_SEARCH_INSTANCE_NAME"]},
    ],
    "azure_ai_search": [
        {"key": "connection_id", "label": "Search Connection ID", "placeholder": "Project connection ID", "required": True, "env_keys": ["AZURE_AI_SEARCH_CONNECTION_ID"]},
        {"key": "index_name", "label": "Index Name", "placeholder": "my-search-index", "required": True, "env_keys": ["AZURE_AI_SEARCH_INDEX"]},
    ],
    "custom_mcp": [
        {"key": "server_url", "label": "MCP Server URL", "placeholder": "https://my-mcp-server.com/mcp", "required": True, "env_keys": ["MCP_SERVER_URL"]},
        {"key": "connection_id", "label": "Project Connection ID", "placeholder": "Connection ID for auth", "required": True, "env_keys": ["MCP_PROJECT_CONNECTION_ID"]},
    ],
    "foundry_iq": [
        {"key": "mcp_endpoint", "label": "Foundry IQ MCP Endpoint", "placeholder": "https://...", "required": True, "env_keys": ["FOUNDRY_IQ_MCP_ENDPOINT"]},
        {"key": "connection_id", "label": "Project Connection ID", "placeholder": "Connection ID", "required": True, "env_keys": ["FOUNDRY_IQ_PROJECT_CONNECTION_ID"]},
    ],
    "azure_devops_mcp": [
        {"key": "server_url", "label": "Azure DevOps MCP Server URL", "placeholder": "https://...", "required": True, "env_keys": ["AZURE_DEVOPS_MCP_SERVER_URL"]},
        {"key": "connection_id", "label": "Project Connection ID", "placeholder": "Connection ID", "required": True, "env_keys": ["AZURE_DEVOPS_PROJECT_CONNECTION_ID"]},
    ],
    "custom_code_interpreter": [
        {"key": "mcp_url", "label": "MCP Endpoint URL", "placeholder": "https://...", "required": True, "env_keys": ["CUSTOM_CODE_INTERPRETER_MCP_URL"]},
        {"key": "connection_id", "label": "Connection ID (optional)", "placeholder": "Leave blank if no auth needed", "required": False, "env_keys": ["CUSTOM_CODE_INTERPRETER_CONNECTION_ID"]},
    ],
    "openapi": [
        {"key": "spec_url", "label": "OpenAPI Spec URL or JSON", "placeholder": "https://petstore.swagger.io/v2/swagger.json", "required": True, "env_keys": ["OPENAPI_SPEC_PATH", "OPENAPI_SPEC_JSON"]},
        {"key": "auth_type", "label": "Auth Type", "placeholder": "anonymous", "required": False, "env_keys": ["OPENAPI_AUTH_TYPE"]},
        {"key": "connection_id", "label": "Connection ID (if auth needed)", "placeholder": "Project connection ID", "required": False, "env_keys": ["OPENAPI_PROJECT_CONNECTION_ID"]},
    ],
    "agent_to_agent": [
        {"key": "base_url", "label": "A2A Agent Base URL", "placeholder": "https://my-agent.endpoint/", "required": False, "env_keys": ["A2A_AGENT_BASE_URL"]},
        {"key": "connection_id", "label": "Project Connection ID", "placeholder": "Connection ID", "required": False, "env_keys": ["A2A_PROJECT_CONNECTION_ID"]},
    ],
}


def _catalog_item(
    tool_id: str,
    label: str,
    kind: str,
    surface: str,
    enabled: bool,
    default_selected: bool,
    description: str,
    config_hint: str,
    source_url: str,
) -> dict[str, Any]:
    return {
        "id": tool_id,
        "label": label,
        "kind": kind,
        "surface": surface,
        "enabled": enabled,
        "default_selected": enabled and default_selected,
        "description": description,
        "config_hint": config_hint,
        "source_url": source_url,
        "status": "Ready" if enabled else ("Needs config" if surface == "Toolbox" else "Agent-level"),
        "config_fields": [
            {**f, "value": next((v for k in f.get("env_keys", []) if (v := _env_value(k))), "")}
            for f in TOOL_CONFIG_FIELDS.get(tool_id, [])
        ],
    }


def _toolbox_tool_catalog() -> list[dict[str, Any]]:
    # Sources:
    # - Toolbox createable tools: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/toolbox#configure-tools
    # - Full Foundry agent tool catalog: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/tool-catalog#all-built-in-tools
    vector_store_ids = _configured_vector_store_ids()
    search_ready = bool(_env_value("AZURE_AI_SEARCH_CONNECTION_ID") and _env_value("AZURE_AI_SEARCH_INDEX"))
    mcp_ready = bool(_env_value("MCP_SERVER_URL") and _env_value("MCP_PROJECT_CONNECTION_ID"))
    bing_custom_ready = bool(_env_value("BING_CUSTOM_SEARCH_PROJECT_CONNECTION_ID") and _env_value("BING_CUSTOM_SEARCH_INSTANCE_NAME"))
    openapi_ready = bool(_env_value("OPENAPI_SPEC_PATH") or _env_value("OPENAPI_SPEC_JSON"))
    a2a_ready = bool(_env_value("A2A_AGENT_BASE_URL") or _env_value("A2A_PROJECT_CONNECTION_ID"))
    foundry_iq_ready = bool(_env_value("FOUNDRY_IQ_MCP_ENDPOINT") and _env_value("FOUNDRY_IQ_PROJECT_CONNECTION_ID"))
    azure_devops_ready = bool(_env_value("AZURE_DEVOPS_MCP_SERVER_URL") and _env_value("AZURE_DEVOPS_PROJECT_CONNECTION_ID"))
    custom_code_ready = bool(_env_value("CUSTOM_CODE_INTERPRETER_MCP_URL"))
    return [
        _catalog_item("code_interpreter", "Code Interpreter", "built-in", "Toolbox", True, True, "Execute Python code for calculations, data analysis, and chart generation.", "No extra project connection required.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/code-interpreter"),
        _catalog_item("file_search", "File Search", "built-in", "Toolbox", bool(vector_store_ids), bool(vector_store_ids), "Search uploaded files stored in a Foundry vector store.", "Requires VECTOR_STORE_ID or FILE_SEARCH_VECTOR_STORE_IDS.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/file-search"),
        _catalog_item("web_search", "Web Search", "built-in", "Toolbox", True, True, "Ground answers with current public web results and citations.", "No project connection required; review Grounding with Bing terms before production use.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/web-search"),
        _catalog_item("web_search_custom", "Web Search · Bing Custom Search", "built-in", "Toolbox", bing_custom_ready, False, "Restrict public web grounding to configured domains through Bing Custom Search.", "Requires BING_CUSTOM_SEARCH_PROJECT_CONNECTION_ID and BING_CUSTOM_SEARCH_INSTANCE_NAME.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/web-search#domain-restricted-search-with-bing-custom-search"),
        _catalog_item("azure_ai_search", "Azure AI Search", "connection", "Toolbox", search_ready, False, "Search a customer-owned Azure AI Search index through a project connection.", "Requires AZURE_AI_SEARCH_CONNECTION_ID and AZURE_AI_SEARCH_INDEX.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/ai-search"),
        _catalog_item("custom_mcp", "Custom MCP Server", "connection", "Toolbox", mcp_ready, False, "Expose tools from a remote MCP server through the governed Toolbox endpoint.", "Requires MCP_SERVER_URL and MCP_PROJECT_CONNECTION_ID.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol"),
        _catalog_item("foundry_iq", "Foundry IQ Knowledge Base", "MCP", "Toolbox", foundry_iq_ready, False, "Use an Azure AI Search knowledge base MCP endpoint for agentic retrieval.", "Requires FOUNDRY_IQ_MCP_ENDPOINT and FOUNDRY_IQ_PROJECT_CONNECTION_ID.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/foundry-iq-connect"),
        _catalog_item("azure_devops_mcp", "Azure DevOps MCP Server", "MCP", "Toolbox", azure_devops_ready, False, "Add the Azure DevOps MCP catalog tool through a governed project connection.", "Requires AZURE_DEVOPS_MCP_SERVER_URL and AZURE_DEVOPS_PROJECT_CONNECTION_ID.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol#connect-to-azure-devops-mcp-server"),
        _catalog_item("custom_code_interpreter", "Custom Code Interpreter", "MCP", "Toolbox", custom_code_ready, False, "Bring a custom Python runtime through an MCP server when built-in Code Interpreter is not enough.", "Requires CUSTOM_CODE_INTERPRETER_MCP_URL; add CUSTOM_CODE_INTERPRETER_CONNECTION_ID if the endpoint needs auth.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/custom-code-interpreter"),
        _catalog_item("openapi", "OpenAPI Tool", "custom", "Toolbox", openapi_ready, False, "Expose a REST API from an OpenAPI 3.0 or 3.1 specification.", "Requires OPENAPI_SPEC_PATH or OPENAPI_SPEC_JSON plus OPENAPI_AUTH_TYPE.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/openapi"),
        _catalog_item("agent_to_agent", "Agent-to-Agent Tool", "custom", "Toolbox", a2a_ready, False, "Call another A2A-compatible agent endpoint as a tool.", "Requires A2A_AGENT_BASE_URL or A2A_PROJECT_CONNECTION_ID.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/agent-to-agent"),
        _catalog_item("bing_grounding", "Grounding with Bing Search", "built-in", "Agent", False, False, "Agent-level Bing grounding with an explicit Bing project connection.", "Configure on an agent definition, or use Web Search in Toolbox for the no-connection path.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/bing-tools"),
        _catalog_item("sharepoint", "SharePoint", "built-in", "Agent", False, False, "Retrieve private SharePoint documents with identity passthrough.", "Agent-level preview tool; requires SHAREPOINT_PROJECT_CONNECTION_ID and user identity.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/sharepoint"),
        _catalog_item("fabric", "Microsoft Fabric Data Agent", "built-in", "Agent", False, False, "Query a published Fabric data agent with user identity passthrough.", "Agent-level preview tool; requires FABRIC_PROJECT_CONNECTION_ID.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/fabric"),
        _catalog_item("azure_functions", "Azure Functions", "built-in", "Agent", False, False, "Call queue-based Azure Functions for custom asynchronous enterprise actions.", "Agent-level tool; use MCP or OpenAPI to expose function apps through Toolbox.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/azure-functions"),
        _catalog_item("function_calling", "Function Calling", "built-in", "Agent", False, False, "Let the model request app-local functions and return tool outputs through Responses API.", "Agent/app runtime pattern, not a Toolbox-managed remote tool.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/function-calling"),
        _catalog_item("image_generation", "Image Generation", "built-in", "Agent", False, False, "Generate images in agent conversations using a GPT Image deployment.", "Agent-level preview tool; requires gpt-image-1 plus an orchestrator model.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/image-generation"),
        _catalog_item("browser_automation", "Browser Automation", "built-in", "Agent", False, False, "Run browser tasks through a Playwright workspace connection.", "Agent-level preview tool; requires a Playwright workspace project connection.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/browser-automation"),
        _catalog_item("computer_use", "Computer Use", "built-in", "Agent", False, False, "Interact with desktop/browser UIs through screenshots and action loops.", "Agent-level preview tool; requires the computer-use-preview model and sandboxing.", "https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/computer-use"),
    ]


def _load_openapi_spec_from_env() -> dict[str, Any]:
    raw_spec = _env_value("OPENAPI_SPEC_JSON")
    if raw_spec:
        return json.loads(raw_spec)
    spec_path = _env_value("OPENAPI_SPEC_PATH")
    if not spec_path:
        raise HTTPException(400, "OpenAPI requires OPENAPI_SPEC_PATH or OPENAPI_SPEC_JSON before creating a toolbox.")
    try:
        if spec_path.startswith("http://") or spec_path.startswith("https://"):
            response = httpx.get(spec_path, timeout=15.0)
            response.raise_for_status()
            return response.json()
        return json.loads(Path(spec_path).read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(400, f"Failed to load OpenAPI spec from OPENAPI_SPEC_PATH: {exc}") from exc


def _load_toolbox_registry() -> list[str]:
    names = _load_json("toolboxes", [DEFAULT_TOOLBOX_NAME])
    if not isinstance(names, list):
        names = [DEFAULT_TOOLBOX_NAME]
    normalized: list[str] = []
    for name in [DEFAULT_TOOLBOX_NAME, "agent-tools", *names]:
        if isinstance(name, str):
            value = name.strip()
            if value and value not in normalized:
                normalized.append(value)
    return normalized


def _save_toolbox_registry() -> None:
    _save_json("toolboxes", _known_toolboxes)


_known_toolboxes: list[str] = _load_toolbox_registry()
_toolbox_blueprints: dict[str, Any] = _load_json("toolbox_blueprints", {}) or {}


def _save_toolbox_blueprints() -> None:
    _save_json("toolbox_blueprints", _toolbox_blueprints)


def _known_toolbox_names() -> set[str]:
    return {name for name in [DEFAULT_TOOLBOX_NAME, "agent-tools", *_known_toolboxes, *_toolbox_blueprints.keys()] if name}


def _resolve_agent_toolbox_name(raw_name: str | None) -> str:
    toolbox_name = (raw_name or DEFAULT_TOOLBOX_NAME).strip() or DEFAULT_TOOLBOX_NAME
    if toolbox_name not in _known_toolbox_names():
        raise HTTPException(400, f"Toolbox {toolbox_name!r} not found. Create it in Step 1 first.")
    return toolbox_name


def _live_tool_ids_for_toolbox(toolbox_name: str) -> list[str]:
    blueprint = _toolbox_blueprints.get(toolbox_name, {}) or {}
    live_tool_ids = blueprint.get("live_tool_ids", [])
    if not isinstance(live_tool_ids, list):
        return []
    return [tool_id for tool_id in live_tool_ids if isinstance(tool_id, str) and tool_id in ALL_TOOLS]


def _validate_agent_tools_for_toolbox(tools: list[str], toolbox_name: str) -> None:
    live_tool_ids = _live_tool_ids_for_toolbox(toolbox_name)
    if not live_tool_ids:
        return
    invalid = [
        tool_id for tool_id in tools
        if ALL_TOOLS.get(tool_id, {}).get("source") == "toolbox" and tool_id not in live_tool_ids
    ]
    if invalid:
        raise HTTPException(400, f"Tools {invalid} are not live in toolbox {toolbox_name!r}")


class ToolboxCreateReq(BaseModel):
    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    tool_configs: dict[str, dict[str, str]] = Field(default_factory=dict)


def _tb_headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token('https://ai.azure.com/.default')}",
        "Content-Type": "application/json",
        "Foundry-Features": "Toolboxes=V1Preview",
    }


@app.get("/api/toolboxes")
def list_toolboxes():
    """List known toolboxes with MCP tool counts."""
    results = []
    catalog_items = {item["id"]: item for item in _toolbox_tool_catalog()}
    names = []
    for item in [*_known_toolboxes, *_toolbox_blueprints.keys()]:
        if item not in names:
            names.append(item)
    for name in names:
        blueprint = _toolbox_blueprints.get(name, {}) or {}
        cached_live_tools = [
            {
                "name": tool_id,
                "description": catalog_items.get(tool_id, {}).get("description", ""),
            }
            for tool_id in blueprint.get("live_tool_ids", [])
        ]
        entry = {
            "name": name,
            "tools": cached_live_tools,
            "planned_tools": blueprint.get("planned_tools", []),
            "requested_tools": blueprint.get("requested_tools", []),
            "default_version": blueprint.get("default_version"),
            "mcp_endpoint": blueprint.get("mcp_endpoint", ""),
            "status": blueprint.get("status", "live"),
        }
        if blueprint:
            results.append(entry)
            continue
        entry["status"] = "registered"
        if PROJECT_ENDPOINT:
            entry["mcp_endpoint"] = (
                f"{PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{name}/mcp?api-version=v1"
            )
        results.append(entry)
    return JSONResponse({"toolboxes": results})


@app.post("/api/toolboxes")
def create_toolbox(body: ToolboxCreateReq):
    """Create a new toolbox version with selected tools."""
    name = _normalize_toolbox_name(body.name)
    if not body.tools:
        raise HTTPException(400, "Select at least one tool")
    if not TOOLBOX_API_BASE:
        raise HTTPException(400, "AZURE_AI_PROJECT_ENDPOINT is required to create toolboxes")

    catalog_items = {item["id"]: item for item in _toolbox_tool_catalog()}
    allowed_toolbox_tools = set(catalog_items)
    unknown_tools = [t for t in body.tools if t not in allowed_toolbox_tools]
    if unknown_tools:
        raise HTTPException(400, f"Unknown toolbox tools: {unknown_tools}")

    tools_payload = []
    planned_tools = []
    live_tool_ids = []
    for t in body.tools:
        catalog_item = catalog_items[t]
        # Agent-level tools cannot be published to a Toolbox version at all.
        if catalog_item.get("surface") != "Toolbox":
            planned_tools.append(catalog_item)
            continue
        cfg = body.tool_configs.get(t, {})
        if t == "code_interpreter":
            tools_payload.append({
                "type": "code_interpreter",
                "name": "code_interpreter",
                "description": "Execute Python code for calculations and data analysis.",
            })
            live_tool_ids.append(t)
        elif t == "web_search":
            tools_payload.append({
                "type": "web_search",
                "name": "web_search",
                "description": "Search the public web for current factual information with citations.",
                "search_context_size": "medium",
            })
            live_tool_ids.append(t)
        elif t == "web_search_custom":
            custom_connection_id = cfg.get("connection_id") or _env_value("BING_CUSTOM_SEARCH_PROJECT_CONNECTION_ID")
            custom_instance_name = cfg.get("instance_name") or _env_value("BING_CUSTOM_SEARCH_INSTANCE_NAME")
            if not custom_connection_id or not custom_instance_name:
                planned_tools.append(catalog_item)
                continue
            tools_payload.append({
                "type": "web_search",
                "name": "web_search_custom",
                "description": "Search only the configured public web domains through Bing Custom Search.",
                "search_context_size": "medium",
                "web_search": {
                    "custom_search_configuration": {
                        "project_connection_id": custom_connection_id,
                        "instance_name": custom_instance_name,
                    }
                },
            })
            live_tool_ids.append(t)
        elif t == "file_search":
            user_vs = cfg.get("vector_store_id", "").strip()
            vector_store_ids = [user_vs] if user_vs else _configured_vector_store_ids()
            if not vector_store_ids:
                planned_tools.append(catalog_item)
                continue
            obj: dict = {
                "type": "file_search",
                "name": "file_search",
                "description": "Search uploaded files in a vector store for relevant passages.",
                "vector_store_ids": vector_store_ids,
            }
            tools_payload.append(obj)
            live_tool_ids.append(t)
        elif t == "azure_ai_search":
            search_connection_id = cfg.get("connection_id") or os.getenv("AZURE_AI_SEARCH_CONNECTION_ID", "").strip()
            search_index = cfg.get("index_name") or os.getenv("AZURE_AI_SEARCH_INDEX", "").strip()
            if not search_connection_id or not search_index:
                planned_tools.append(catalog_item)
                continue
            tools_payload.append({
                "type": "azure_ai_search",
                "name": "azure_ai_search",
                "description": "Search the configured Azure AI Search index.",
                "azure_ai_search": {
                    "indexes": [{
                        "index_name": search_index,
                        "project_connection_id": search_connection_id,
                    }]
                },
            })
            live_tool_ids.append(t)
        elif t == "custom_mcp":
            mcp_server_url = cfg.get("server_url") or os.getenv("MCP_SERVER_URL", "").strip()
            mcp_connection_id = cfg.get("connection_id") or os.getenv("MCP_PROJECT_CONNECTION_ID", "").strip()
            if not mcp_server_url or not mcp_connection_id:
                planned_tools.append(catalog_item)
                continue
            approval = os.getenv("MCP_REQUIRE_APPROVAL", os.getenv("TOOLBOX_APPROVAL_MODE", "never")).strip().lower()
            tools_payload.append({
                "type": "mcp",
                "server_label": os.getenv("MCP_SERVER_LABEL", "custom_mcp"),
                "server_url": mcp_server_url,
                "require_approval": "always" if approval.startswith("always") else "never",
                "project_connection_id": mcp_connection_id,
                "description": "Remote MCP server exposed through Foundry Toolbox.",
            })
            live_tool_ids.append(t)
        elif t == "foundry_iq":
            mcp_endpoint = cfg.get("mcp_endpoint") or _env_value("FOUNDRY_IQ_MCP_ENDPOINT")
            connection_id = cfg.get("connection_id") or _env_value("FOUNDRY_IQ_PROJECT_CONNECTION_ID")
            if not mcp_endpoint or not connection_id:
                planned_tools.append(catalog_item)
                continue
            tools_payload.append({
                "type": "mcp",
                "server_label": _env_value("FOUNDRY_IQ_SERVER_LABEL") or "foundry_iq",
                "server_url": mcp_endpoint,
                "require_approval": "never",
                "allowed_tools": ["knowledge_base_retrieve"],
                "project_connection_id": connection_id,
                "description": "Foundry IQ knowledge base retrieval through MCP.",
            })
            live_tool_ids.append(t)
        elif t == "azure_devops_mcp":
            mcp_endpoint = cfg.get("server_url") or _env_value("AZURE_DEVOPS_MCP_SERVER_URL")
            connection_id = cfg.get("connection_id") or _env_value("AZURE_DEVOPS_PROJECT_CONNECTION_ID")
            if not mcp_endpoint or not connection_id:
                planned_tools.append(catalog_item)
                continue
            approval = _env_value("AZURE_DEVOPS_MCP_REQUIRE_APPROVAL") or "always"
            tools_payload.append({
                "type": "mcp",
                "server_label": _env_value("AZURE_DEVOPS_MCP_SERVER_LABEL") or "azure_devops",
                "server_url": mcp_endpoint,
                "require_approval": "never" if approval.lower().startswith("never") else "always",
                "project_connection_id": connection_id,
                "description": "Azure DevOps MCP Server from the Foundry Add Tools catalog.",
            })
            live_tool_ids.append(t)
        elif t == "custom_code_interpreter":
            mcp_endpoint = cfg.get("mcp_url") or _env_value("CUSTOM_CODE_INTERPRETER_MCP_URL")
            if not mcp_endpoint:
                planned_tools.append(catalog_item)
                continue
            tools_payload.append({
                "type": "mcp",
                "server_label": _env_value("CUSTOM_CODE_INTERPRETER_SERVER_LABEL") or "custom_code_interpreter",
                "server_url": mcp_endpoint,
                "require_approval": "never",
                "project_connection_id": cfg.get("connection_id") or _env_value("CUSTOM_CODE_INTERPRETER_CONNECTION_ID") or None,
                "description": "Custom Code Interpreter MCP runtime.",
            })
            live_tool_ids.append(t)
        elif t == "openapi":
            spec_url = cfg.get("spec_url", "").strip()
            if spec_url:
                try:
                    if spec_url.startswith("http"):
                        response = httpx.get(spec_url, timeout=15.0)
                        response.raise_for_status()
                        spec = response.json()
                    else:
                        spec = json.loads(spec_url)
                except Exception:
                    planned_tools.append(catalog_item)
                    continue
            elif _env_value("OPENAPI_SPEC_PATH") or _env_value("OPENAPI_SPEC_JSON"):
                spec = _load_openapi_spec_from_env()
            else:
                planned_tools.append(catalog_item)
                continue
            auth_type = (cfg.get("auth_type") or _env_value("OPENAPI_AUTH_TYPE") or "anonymous").lower()
            if auth_type == "anonymous":
                auth: dict[str, Any] = {"type": "anonymous"}
            elif auth_type in {"project_connection", "api_key", "bearer"}:
                connection_id = cfg.get("connection_id") or _env_value("OPENAPI_PROJECT_CONNECTION_ID")
                if not connection_id:
                    raise HTTPException(400, "OpenAPI project_connection auth requires OPENAPI_PROJECT_CONNECTION_ID.")
                auth = {"type": "project_connection", "security_scheme": {"project_connection_id": connection_id}}
            elif auth_type in {"managed_identity", "mi"}:
                audience = _env_value("OPENAPI_MANAGED_IDENTITY_AUDIENCE")
                if not audience:
                    raise HTTPException(400, "OpenAPI managed_identity auth requires OPENAPI_MANAGED_IDENTITY_AUDIENCE.")
                auth = {"type": "managed_identity", "security_scheme": {"audience": audience}}
            else:
                raise HTTPException(400, "OPENAPI_AUTH_TYPE must be anonymous, project_connection, api_key, bearer, or managed_identity.")
            openapi_name = _env_value("OPENAPI_TOOL_NAME") or "openapi_api"
            tools_payload.append({
                "type": "openapi",
                "name": openapi_name,
                "description": _env_value("OPENAPI_TOOL_DESCRIPTION") or "External REST API exposed through OpenAPI.",
                "openapi": {
                    "name": openapi_name,
                    "description": _env_value("OPENAPI_TOOL_DESCRIPTION") or "External REST API exposed through OpenAPI.",
                    "spec": spec,
                    "auth": auth,
                },
            })
            live_tool_ids.append(t)
        elif t == "agent_to_agent":
            base_url = cfg.get("base_url") or _env_value("A2A_AGENT_BASE_URL")
            connection_id = cfg.get("connection_id") or _env_value("A2A_PROJECT_CONNECTION_ID")
            if not base_url and not connection_id:
                planned_tools.append(catalog_item)
                continue
            tools_payload.append({
                "type": "a2a",
                "name": _env_value("A2A_AGENT_NAME") or "remote_agent",
                "description": _env_value("A2A_AGENT_DESCRIPTION") or "Remote A2A-compatible agent endpoint.",
                "base_url": base_url or None,
                "project_connection_id": connection_id or None,
            })
            live_tool_ids.append(t)
        else:
            planned_tools.append(catalog_item)

    tools_payload = [{k: v for k, v in tool.items() if v is not None} for tool in tools_payload]

    _toolbox_blueprints[name] = {
        "status": "live_plus_plan" if tools_payload and planned_tools else ("live" if tools_payload else "plan_only"),
        "default_version": None,
        "requested_tools": [catalog_items[t] for t in body.tools],
        "live_tool_ids": live_tool_ids,
        "planned_tools": planned_tools,
        "description": body.description or f"Toolbox {name}",
        "updated_at": time.time(),
    }
    _save_toolbox_blueprints()

    if not tools_payload:
        if name not in _known_toolboxes:
            _known_toolboxes.append(name)
            _save_toolbox_registry()
        return JSONResponse({
            "ok": True,
            "name": name,
            "status": "plan_only",
            "version": None,
            "mcp_endpoint": "",
            "tools_count": 0,
            "planned_tools_count": len(planned_tools),
            "message": "Saved as a toolbox design plan. Add the required project connections/env vars to publish these tools live.",
        })

    try:
        r = httpx.post(
            f"{TOOLBOX_API_BASE}/{name}/versions?api-version=v1",
            headers=_tb_headers(),
            json={"description": body.description or f"Toolbox {name}", "tools": tools_payload},
            timeout=30.0,
        )
        r.raise_for_status()
        result = r.json()
        _toolbox_blueprints[name]["default_version"] = result.get("version", "1")
        _toolbox_blueprints[name]["mcp_endpoint"] = f"{TOOLBOX_API_BASE}/{name}/mcp?api-version=v1"
        _save_toolbox_blueprints()
        if name not in _known_toolboxes:
            _known_toolboxes.append(name)
            _save_toolbox_registry()
        return JSONResponse({
            "ok": True, "name": name,
            "status": _toolbox_blueprints[name]["status"],
            "version": result.get("version", "1"),
            "mcp_endpoint": f"{TOOLBOX_API_BASE}/{name}/mcp?api-version=v1",
            "tools_count": len(tools_payload),
            "planned_tools_count": len(planned_tools),
        })
    except httpx.HTTPStatusError as e:
        _toolbox_blueprints[name].update({
            "status": "error",
            "default_version": None,
            "live_tool_ids": [],
            "error": f"Foundry API {e.response.status_code}: {e.response.text[:300]}",
            "updated_at": time.time(),
        })
        _save_toolbox_blueprints()
        return JSONResponse(
            {"error": f"Foundry API {e.response.status_code}: {e.response.text[:300]}"},
            status_code=max(e.response.status_code, 400),
        )


@app.delete("/api/toolboxes/{name}")
def delete_toolbox(name: str):
    """Delete a toolbox from local registry and optionally from Foundry."""
    name = _normalize_toolbox_name(name)
    deleted_local = False
    if name in _toolbox_blueprints:
        del _toolbox_blueprints[name]
        _save_toolbox_blueprints()
        deleted_local = True
    if name in _known_toolboxes:
        _known_toolboxes.remove(name)
        _save_toolbox_registry()
        deleted_local = True
    if not deleted_local:
        raise HTTPException(404, f"Toolbox {name!r} not found")
    # Best-effort remote delete (non-blocking if it fails)
    if TOOLBOX_API_BASE:
        try:
            httpx.delete(
                f"{TOOLBOX_API_BASE}/{name}?api-version=v1",
                headers=_tb_headers(),
                timeout=15.0,
            )
        except Exception:
            pass
    return JSONResponse({"ok": True, "name": name})


# ---------- API: Evaluation (Lifecycle Step 4: Evaluate) ----------

# Test dataset for quick agent evaluation.
_EVAL_TEST_QUERIES = [
    {"query": "What is machine learning? Answer in one sentence.", "required_tool": None},
    {"query": "Use code_interpreter to compute the factorial of 10.", "required_tool": "code_interpreter"},
]


@app.post("/api/evaluation/run")
def run_evaluation(agent_id: str = Form("default")):
    """Run quick evaluation: send test queries, collect responses, compute scores."""
    agent = AGENTS.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent {agent_id!r} not found")

    query_timeout = _env_int("EVALUATION_QUERY_TIMEOUT_SECONDS", 30, 10, 90)
    test_results = []
    for item in _EVAL_TEST_QUERIES:
        q = item["query"]
        required_tool = item.get("required_tool")
        t0 = time.time()
        try:
            res = _ask_agent(q, agent_id, timeout=float(query_timeout))
            text = res.get("text", "")
            tools_used = [tc.get("name", "?") for tc in res.get("tool_calls", [])]
            missing_required_tool = bool(required_tool and required_tool not in tools_used)
            failure_reason = ""
            if not text or text.startswith("Error"):
                failure_reason = "empty_or_error_response"
            elif missing_required_tool:
                failure_reason = f"required_tool_not_observed:{required_tool}"
            test_results.append({
                "query": q, "response": text[:500],
                "elapsed_ms": res.get("elapsed_ms", 0),
                "tools_used": tools_used,
                "tokens": res.get("total_tokens", 0),
                "required_tool": required_tool,
                "status": "pass" if not failure_reason else "fail",
                "failure_reason": failure_reason,
            })
        except Exception as e:
            test_results.append({
                "query": q, "response": f"Error: {e}",
                "elapsed_ms": int((time.time() - t0) * 1000),
                "tools_used": [], "tokens": 0, "required_tool": required_tool, "status": "fail",
                "failure_reason": _agent_exception_message(e),
            })

    # Compute local quality metrics
    passed = sum(1 for r in test_results if r["status"] == "pass")
    total = len(test_results)
    avg_latency = int(sum(r["elapsed_ms"] for r in test_results) / max(total, 1))
    token_values = [r["tokens"] for r in test_results if r.get("tokens")]
    avg_tokens = int(sum(token_values) / len(token_values)) if token_values else None
    tool_usage = sum(1 for r in test_results if r["tools_used"])
    avg_resp_len = int(sum(len(r["response"]) for r in test_results) / max(total, 1))

    # Try Foundry Evaluation API only when explicitly enabled. The local quick
    # evaluation is the deterministic demo gate; cloud evaluation can take
    # longer and should not block the live UI by default.
    # Source: https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk
    foundry_eval = {
        "status": "optional",
        "message": "Local quick evaluation completed. Set ENABLE_FOUNDRY_EVAL_API=1 to submit an optional cloud evaluation run.",
        "source": "https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk",
    }
    if ENABLE_FOUNDRY_EVAL_API:
        try:
            token = _get_token("https://ai.azure.com/.default")
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            base = PROJECT_ENDPOINT.rstrip("/")
            eval_payload = {
                "name": f"demo-{agent_id}-{int(time.time())}",
                "data_source_config": {
                    "type": "custom",
                    "item_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}, "response": {"type": "string"}},
                        "required": ["query", "response"],
                    },
                },
                "testing_criteria": [
                    {
                        "type": "azure_ai_evaluator",
                        "name": "coherence",
                        "evaluator_name": "builtin.coherence",
                        "initialization_parameters": {"deployment_name": EVALUATION_MODEL_DEPLOYMENT},
                        "data_mapping": {"query": "{{item.query}}", "response": "{{item.response}}"},
                    },
                    {
                        "type": "azure_ai_evaluator",
                        "name": "violence",
                        "evaluator_name": "builtin.violence",
                        "data_mapping": {"query": "{{item.query}}", "response": "{{item.response}}"},
                    },
                ],
            }
            request_timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
            er = httpx.post(f"{base}/openai/v1/evals", headers=headers, json=eval_payload, timeout=request_timeout)
            if er.status_code in (200, 201):
                eval_obj = er.json()
                eval_id = eval_obj.get("id")
                run_data = {
                    "name": f"demo-run-{int(time.time())}",
                    "data_source": {
                        "type": "jsonl",
                        "source": {
                            "type": "file_content",
                            "content": [
                                {"item": {"query": r["query"], "response": r["response"]}}
                                for r in test_results
                                if r["status"] == "pass"
                            ],
                        },
                    },
                }
                rr = httpx.post(f"{base}/openai/v1/evals/{eval_id}/runs", headers=headers, json=run_data, timeout=request_timeout)
                if rr.status_code in (200, 201):
                    run_obj = rr.json()
                    foundry_eval = {
                        "status": run_obj.get("status", "submitted"),
                        "message": "Cloud evaluation run submitted. The demo returns immediately; open the Foundry portal for the full report when processing completes.",
                        "eval_id": eval_id,
                        "run_id": run_obj.get("id", ""),
                        "source": "https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk",
                    }
                else:
                    foundry_eval = {
                        "status": "not_available",
                        "message": f"Cloud evaluation run returned {rr.status_code}: {rr.text[:240]}",
                        "source": "https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk",
                    }
            else:
                foundry_eval = {
                    "status": "not_available",
                    "message": f"Cloud evaluation creation returned {er.status_code}: {er.text[:240]}",
                    "source": "https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk",
                }
        except httpx.TimeoutException:
            foundry_eval = {
                "status": "not_available",
                "message": "Cloud evaluation API did not respond within 30 seconds. Local quick evaluation remains complete.",
                "source": "https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk",
            }
        except Exception as e:
            foundry_eval = {
                "status": "not_available",
                "message": str(e)[:240],
                "source": "https://learn.microsoft.com/en-us/azure/foundry-classic/how-to/develop/evaluate-sdk",
            }

    return JSONResponse({
        "agent_id": agent_id,
        "agent_name": agent.get("name", "?"),
        "test_results": test_results,
        "summary": {
            "pass_rate": f"{passed}/{total}",
            "avg_latency_ms": avg_latency,
            "avg_tokens": avg_tokens,
            "tool_usage_rate": f"{tool_usage}/{total}",
            "avg_response_length": avg_resp_len,
            "query_timeout_seconds": query_timeout,
            "evaluator_model_deployment": EVALUATION_MODEL_DEPLOYMENT,
            "evaluator_model_source": "EVALUATION_MODEL_DEPLOYMENT or AZURE_AI_EVALUATION_DEPLOYMENT_NAME or DEFAULT_AGENT_MODEL",
        },
        "foundry_eval": foundry_eval,
        "foundry_evaluators": [
            "coherence", "fluency", "violence", "self_harm",
            "task_adherence", "tool_call_accuracy", "intent_resolution",
            "groundedness", "relevance", "protected_materials",
        ],
        "portal_url": "https://ai.azure.com",
    })


# ---------- API: Control Plane — Fleet Overview (Lifecycle Step 6: Govern) ----------

@app.get("/api/control-plane")
def control_plane():
    """Fleet overview: all agents + hosted agents + metrics from AppInsights."""
    fleet = []
    for aid, agent in AGENTS.items():
        ha = HOSTED_AGENTS.get(agent.get("hosted_agent_id", "default"), {})
        toolbox_name = agent.get("toolbox_name", DEFAULT_TOOLBOX_NAME)
        configured_tools = agent.get("tools", [])
        agent_history = [h for h in HISTORY if h.get("agent_id") == aid]
        history_calls = len(agent_history)
        registry_calls = int(agent.get("calls", 0) or 0)
        total_calls = max(history_calls, registry_calls)
        errors = sum(1 for h in agent_history if "error" in str(h.get("answer_preview", "")).lower())
        avg_latency = int(sum(h.get("elapsed_ms", 0) for h in agent_history) / max(history_calls, 1)) if agent_history else 0
        tools_used_flat = [t for h in agent_history for t in h.get("tools_used", [])]
        live_tool_ids = _live_tool_ids_for_toolbox(toolbox_name)
        toolbox_tools = [t for t in configured_tools if ALL_TOOLS.get(t, {}).get("source") == "toolbox"]
        toolbox_drift = [t for t in toolbox_tools if live_tool_ids and t not in live_tool_ids]
        checks = []
        if not configured_tools:
            checks.append({"label": "No tools selected", "severity": "critical"})
        if toolbox_drift:
            checks.append({"label": "Toolbox drift", "severity": "critical", "detail": ", ".join(toolbox_drift)})
        if not ha:
            checks.append({"label": "Hosted runtime missing", "severity": "critical"})
        if errors:
            checks.append({"label": f"{errors} failed calls", "severity": "warning"})
        if avg_latency >= 15000:
            checks.append({"label": "High latency", "severity": "warning"})
        if configured_tools and total_calls and not tools_used_flat:
            checks.append({"label": "Tools not observed", "severity": "warning"})
        if not total_calls:
            checks.append({"label": "No traffic yet", "severity": "info"})
        if not checks:
            checks.append({"label": "Ready", "severity": "ok"})

        severities = {check.get("severity") for check in checks}
        if "critical" in severities:
            status = "needs review"
            status_tone = "red"
            recommended_action = "Fix tool/runtime binding before evaluation or handoff."
        elif "warning" in severities:
            status = "watch"
            status_tone = "amber"
            recommended_action = "Inspect traces and recent calls before scaling usage."
        elif severities == {"info"}:
            status = "not exercised"
            status_tone = "blue"
            recommended_action = "Run a smoke prompt or evaluation to create evidence."
        else:
            status = "ready"
            status_tone = "green"
            recommended_action = "Ready for demo traffic; continue monitoring."
        fleet.append({
            "agent_id": aid, "agent_name": agent.get("name", "?"),
            "hosted_agent": ha.get("name", "default"),
            "toolbox_name": toolbox_name,
            "model": agent.get("model", DEFAULT_AGENT_MODEL),
            "model_source": "selected agent registry, not live Foundry inventory",
            "tools": configured_tools,
            "calls": total_calls,
            "error_rate": f"{errors}/{total_calls}" if total_calls else "0/0",
            "avg_latency_ms": avg_latency,
            "top_tools": list(set(tools_used_flat))[:5],
            "memory": ha.get("memory_store", ""),
            "status": status,
            "status_tone": status_tone,
            "governance_checks": checks,
            "recommended_action": recommended_action,
            "status_source": "derived from registry, recent calls, toolbox binding, and telemetry availability",
            "metrics_source": "persisted registry counters + recent demo history",
        })

    # AppInsights metrics (best-effort)
    app_insights_metrics = None
    ws_id = os.getenv("CLOUD_LOG_WORKSPACE_ID", "")
    if ws_id:
        try:
            tok = _get_token("https://api.loganalytics.io/.default")
            kql = ("AppTraces | where TimeGenerated > ago(24h) "
                   "| summarize runs=count(), errors=countif(SeverityLevel >= 3) by bin(TimeGenerated, 1h) "
                   "| order by TimeGenerated desc | take 24")
            r = httpx.post(f"https://api.loganalytics.io/v1/workspaces/{ws_id}/query",
                           headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                           json={"query": kql}, timeout=8.0)
            if r.status_code == 200:
                rows = r.json().get("tables", [{}])[0].get("rows", [])
                app_insights_metrics = {
                    "total_runs_24h": sum(row[1] for row in rows) if rows else 0,
                    "total_errors_24h": sum(row[2] for row in rows) if rows else 0,
                    "hourly": [{"time": row[0][:16], "runs": row[1], "errors": row[2]} for row in rows[:12]],
                    "source": "Application Insights AppTraces, last 24h",
                }
        except Exception:
            pass

    total_agents = len(fleet)
    total_hosted = len(HOSTED_AGENTS)
    total_calls_all = sum(a["calls"] for a in fleet)
    governance_summary = {
        "ready": sum(1 for a in fleet if a.get("status") == "ready"),
        "needs_review": sum(1 for a in fleet if a.get("status") in {"needs review", "watch"}),
        "not_exercised": sum(1 for a in fleet if a.get("status") == "not exercised"),
        "empty_tools": sum(1 for a in fleet if not a.get("tools")),
        "toolboxes": len({a.get("toolbox_name") for a in fleet if a.get("toolbox_name")}),
        "telemetry": "live" if app_insights_metrics else "not configured",
    }

    return JSONResponse({
        "fleet": fleet,
        "governance_summary": governance_summary,
        "hosted_agents_count": total_hosted,
        "agents_count": total_agents,
        "total_calls": total_calls_all,
        "app_insights": app_insights_metrics,
        "data_sources": {
            "fleet": "Local demo registry, persisted call counters, and recent request history; not a full Foundry inventory API.",
            "telemetry": "Application Insights workspace query when CLOUD_LOG_WORKSPACE_ID is configured.",
            "roles_and_compliance": "Static Foundry capability reference for demo narration.",
        },
        "rbac_roles": [
            {"role": "Azure AI User", "scope": "Project", "desc": "Build agents, run traces"},
            {"role": "Azure AI Project Manager", "scope": "Resource", "desc": "Create projects, manage agents"},
            {"role": "Azure AI Account Owner", "scope": "Resource", "desc": "Full resource management"},
            {"role": "Azure AI Owner", "scope": "Resource", "desc": "Full access + project building"},
        ],
        "compliance_features": [
            "Azure Policy integration", "Microsoft Defender alerts",
            "Microsoft Purview data governance", "Continuous evaluation",
            "Scheduled red teaming", "Token usage & cost tracking",
        ],
        "portal_url": "https://ai.azure.com",
    })


# ---------- API: Tracing — Span Detail (Lifecycle Step 5: Trace) ----------

@app.get("/api/tracing/recent")
def tracing_recent(agent_id: str = ""):
    """Get recent traces with span-level breakdown from AppInsights."""
    selected_agent = None
    if agent_id:
        selected_agent = AGENTS.get(agent_id)
        if not selected_agent:
            raise HTTPException(404, f"Agent {agent_id!r} not found")
    history_rows = [entry for entry in HISTORY if not agent_id or entry.get("agent_id") == agent_id]
    agent_context = {
        "agent_id": agent_id or None,
        "agent_name": selected_agent.get("name") if selected_agent else None,
        "history": history_rows[-10:],
        "history_source": "local persisted demo request history",
    }
    ws_id = os.getenv("CLOUD_LOG_WORKSPACE_ID", "")
    if not ws_id:
        return JSONResponse({"traces": [], "agent_context": agent_context, "hint": "Set CLOUD_LOG_WORKSPACE_ID to enable Application Insights traces."})

    try:
        tok = _get_token("https://api.loganalytics.io/.default")
        headers = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
        url = f"https://api.loganalytics.io/v1/workspaces/{ws_id}/query"
        diagnostics = []

        # Workspace-based Application Insights tables/columns.
        # Sources:
        # - https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/appdependencies
        # - https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/apptraces
        dep_kql = ("AppDependencies "
                   "| where TimeGenerated > ago(1h) "
                   "| project OperationId, Name, DurationMs, ResultCode, Target, TimeGenerated "
                   "| order by TimeGenerated desc "
                   "| take 30")
        dep_resp = httpx.post(url, headers=headers, json={"query": dep_kql}, timeout=8.0)
        traces: dict = {}
        if dep_resp.status_code == 200:
            rows = dep_resp.json().get("tables", [{}])[0].get("rows", [])
            for row in rows:
                op_id = row[0] or "?"
                if op_id not in traces:
                    traces[op_id] = {"trace_id": op_id, "spans": [], "total_duration_ms": 0}
                dur = round(float(row[2] or 0), 1)
                traces[op_id]["spans"].append({
                    "name": row[1] or "dependency",
                    "duration_ms": dur,
                    "status": row[3] or "?",
                    "model": row[4] or "",
                    "tokens": 0,
                })
                traces[op_id]["total_duration_ms"] = max(traces[op_id]["total_duration_ms"], dur)
            if traces:
                return JSONResponse({
                    "traces": list(traces.values())[:10],
                    "agent_context": agent_context,
                    "hint": "Foundry Tracing — AppDependencies spans from Application Insights",
                    "source": "AppDependencies",
                })
            diagnostics.append("AppDependencies query succeeded but returned no rows for the last 1h.")
        else:
            diagnostics.append(f"AppDependencies returned {dep_resp.status_code}: {dep_resp.text[:180]}")

        trace_kql = ("AppTraces "
                     "| where TimeGenerated > ago(1h) "
                     "| project OperationId, OperationName, Message, SeverityLevel, TimeGenerated "
                     "| order by TimeGenerated desc "
                     "| take 30")
        trace_resp = httpx.post(url, headers=headers, json={"query": trace_kql}, timeout=8.0)
        if trace_resp.status_code == 200:
            rows = trace_resp.json().get("tables", [{}])[0].get("rows", [])
            for row in rows:
                op_id = row[0] or "?"
                if op_id not in traces:
                    traces[op_id] = {"trace_id": op_id, "spans": [], "total_duration_ms": 0}
                message = (row[2] or row[1] or "trace")[:120]
                traces[op_id]["spans"].append({
                    "name": message,
                    "duration_ms": 0,
                    "status": f"severity={row[3]}" if row[3] is not None else "trace",
                    "model": "",
                    "tokens": 0,
                })
            return JSONResponse({
                "traces": list(traces.values())[:10],
                "agent_context": agent_context,
                "hint": "Dependency spans were not available yet; showing AppTraces fallback for the last 1h.",
                "source": "AppTraces",
                "diagnostics": diagnostics,
            })

        diagnostics.append(f"AppTraces returned {trace_resp.status_code}: {trace_resp.text[:180]}")
        return JSONResponse({
            "traces": [],
            "agent_context": agent_context,
            "hint": "No Application Insights trace rows were returned for the last 1h.",
            "diagnostics": diagnostics,
        })
    except Exception as e:
        return JSONResponse({"traces": [], "agent_context": agent_context, "error": str(e)[:200]})


# ---------- Static ----------
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
