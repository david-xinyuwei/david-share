"""连通性预检：不开麦克风，只验证认证、模型、音色和工具 schema 能否被服务端接受。

用法：
    .venv\\Scripts\\python.exe -m scripts.preflight --dry-run              # 不联网，只检查会话配置
    .venv\\Scripts\\python.exe -m scripts.preflight --mode voicelive       # 真实连接 Voice Live
    .venv\\Scripts\\python.exe -m scripts.preflight --mode realtime        # 真实连接 Azure OpenAI Realtime
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Mapping
from enum import Enum
from typing import Any

from src import config, tools

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TIMEOUT_SECONDS = 30


def _json_default(obj: Any) -> Any:
    # SDK 的 Model 是嵌套 MutableMapping，逐层展开才能看到真实 wire payload
    if isinstance(obj, Mapping):
        return dict(obj)
    if isinstance(obj, Enum):
        return obj.value
    return str(obj)


def _session_payload(mode: str) -> dict[str, Any]:
    if mode == "voicelive":
        from src.backends.voicelive import build_session

        session = build_session(config.VOICELIVE_VOICE or "zh-CN-XiaoxiaoMultilingualNeural")
        return json.loads(json.dumps(dict(session), ensure_ascii=False, default=_json_default))

    from src.backends.realtime import build_session

    return json.loads(
        json.dumps(build_session(config.REALTIME_VOICE), ensure_ascii=False, default=_json_default)
    )


def dry_run(mode: str) -> int:
    payload = _session_payload(mode)
    declared = [t["name"] for t in payload.get("tools", [])]
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:900])
    print("-" * 60)
    print(f"[PASS] {mode} 会话配置可序列化，已声明 {len(declared)} 个工具")
    missing = set(tools.registered_names()) - set(declared)
    if missing:
        print(f"[FAIL] 以下工具未进入 payload: {', '.join(sorted(missing))}")
        return 1
    return 0


async def probe_voicelive() -> int:
    from azure.ai.voicelive.aio import connect
    from azure.ai.voicelive.models import ServerEventType

    from src.backends.voicelive import build_credential, build_session

    endpoint = config.VOICELIVE_ENDPOINT
    if not endpoint:
        print("[FAIL] 未配置 AZURE_VOICELIVE_ENDPOINT")
        return 1

    voice = config.VOICELIVE_VOICE or "zh-CN-XiaoxiaoMultilingualNeural"
    print(f"endpoint : {endpoint}")
    print(f"model    : {config.VOICELIVE_MODEL}")
    print(f"voice    : {voice}")
    print(f"auth     : {'API key' if config.VOICELIVE_API_KEY else 'Azure CLI 令牌'}")
    print("-" * 60)

    async with connect(
        endpoint=endpoint,
        credential=build_credential(config.VOICELIVE_API_KEY),
        model=config.VOICELIVE_MODEL,
    ) as conn:
        print("[PASS] WebSocket 已建立")
        await conn.session.update(session=build_session(voice))
        print("[..] 已发送 session.update，等待服务端确认")

        async for event in conn:
            if event.type == ServerEventType.SESSION_UPDATED:
                accepted = [t.name for t in (event.session.tools or [])]
                print(f"[PASS] session.updated, id={event.session.id}")
                return _check_accepted(accepted)
            if event.type == ServerEventType.ERROR:
                print(f"[FAIL] 服务端返回错误: {event.error.message}")
                return 1
    print("[FAIL] 连接结束但未收到 session.updated")
    return 1


async def probe_realtime() -> int:
    from src.backends.realtime import build_client, build_session

    endpoint = config.REALTIME_ENDPOINT
    if not endpoint:
        print("[FAIL] 未配置 AZURE_OPENAI_ENDPOINT")
        return 1

    print(f"endpoint  : {endpoint.rstrip('/')}/openai/v1/")
    print(f"deployment: {config.REALTIME_DEPLOYMENT}")
    print(f"voice     : {config.REALTIME_VOICE}")
    print(f"auth      : {'API key' if config.REALTIME_API_KEY else 'Azure CLI 令牌'}")
    print("-" * 60)

    client, extra_headers = await build_client(endpoint, config.REALTIME_API_KEY)
    try:
        async with client.realtime.connect(
            model=config.REALTIME_DEPLOYMENT, extra_headers=extra_headers
        ) as conn:
            print("[PASS] WebSocket 已建立")
            await conn.session.update(session=build_session(config.REALTIME_VOICE))
            print("[..] 已发送 session.update，等待服务端确认")

            async for event in conn:
                if event.type == "session.updated":
                    accepted = [t.name for t in (event.session.tools or [])]
                    print(f"[PASS] session.updated, id={getattr(event.session, 'id', '')}")
                    return _check_accepted(accepted)
                if event.type == "error":
                    print(f"[FAIL] 服务端返回错误: {getattr(event.error, 'message', event.error)}")
                    return 1
    finally:
        await client.close()
    print("[FAIL] 连接结束但未收到 session.updated")
    return 1


def _check_accepted(accepted: list[str]) -> int:
    print(f"[PASS] 服务端已接受 {len(accepted)} 个工具: {', '.join(accepted)}")
    missing = set(tools.registered_names()) - set(accepted)
    if missing:
        print(f"[FAIL] 以下工具未被服务端接受: {', '.join(sorted(missing))}")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="语音后端预检")
    parser.add_argument("--mode", choices=["voicelive", "realtime"], default="voicelive")
    parser.add_argument("--dry-run", action="store_true", help="不联网，只检查会话配置")
    args = parser.parse_args()

    if args.dry_run:
        code = dry_run(args.mode)
        print("dry-run 通过" if code == 0 else "dry-run 未通过")
        sys.exit(code)

    probe = probe_voicelive if args.mode == "voicelive" else probe_realtime
    try:
        code = asyncio.run(asyncio.wait_for(probe(), timeout=TIMEOUT_SECONDS))
    except asyncio.TimeoutError:
        print(f"[FAIL] {TIMEOUT_SECONDS} 秒内未收到 session.updated")
        code = 1
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        code = 1

    print("-" * 60)
    print(
        f"预检通过，可以运行 python -m src.main --mode {args.mode}"
        if code == 0
        else "预检未通过，请按上面的错误排查"
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
