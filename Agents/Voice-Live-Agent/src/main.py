"""联想桌面语音助手入口。

两种语音后端：
    --mode voicelive   Azure AI Foundry Voice Live（托管 speech-to-speech，带 Azure 语音增强）
    --mode realtime    Azure OpenAI Realtime（直连 gpt-realtime 部署，模型原生音色）

两者共用同一套工具、同一套音频管线，便于同场对比。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime

from . import config, tools
from .audio import AudioProcessor

LOG_DIR = config.PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
# 管道或非 UTF-8 控制台下 Windows 默认用 cp1252，中文输出会直接抛 UnicodeEncodeError
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
logging.basicConfig(
    filename=str(LOG_DIR / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_voiceagent.log"),
    filemode="w",
    format="%(asctime)s:%(name)s:%(levelname)s:%(message)s",
    level=logging.INFO,
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="联想桌面语音助手")
    parser.add_argument(
        "--mode",
        choices=["voicelive", "realtime"],
        default="voicelive",
        help="语音后端：voicelive=Foundry Voice Live，realtime=Azure OpenAI Realtime",
    )
    parser.add_argument("--endpoint", help="覆盖对应后端的 endpoint")
    parser.add_argument("--model", help="Voice Live 模型名或 Realtime 部署名")
    parser.add_argument("--voice", help="音色。Voice Live 用 Azure 音色，Realtime 用模型原生音色")
    parser.add_argument("--api-key", help="不传则使用 az login 的 Entra 令牌")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def build_agent(args: argparse.Namespace):
    if args.mode == "voicelive":
        from .backends.voicelive import VoiceLiveAgent, build_credential

        endpoint = args.endpoint or config.VOICELIVE_ENDPOINT
        if not endpoint:
            raise SystemExit("缺少 AZURE_VOICELIVE_ENDPOINT，请先复制 .env.example 为 .env 并填写")
        return VoiceLiveAgent(
            endpoint=endpoint,
            credential=build_credential(args.api_key or config.VOICELIVE_API_KEY),
            model=args.model or config.VOICELIVE_MODEL,
            voice=args.voice or config.VOICELIVE_VOICE,
        )

    from .backends.realtime import RealtimeAgent

    endpoint = args.endpoint or config.REALTIME_ENDPOINT
    if not endpoint:
        raise SystemExit("缺少 AZURE_OPENAI_ENDPOINT，请在 .env 中填写 Realtime 所用的资源地址")
    return RealtimeAgent(
        endpoint=endpoint,
        api_key=args.api_key or config.REALTIME_API_KEY,
        deployment=args.model or config.REALTIME_DEPLOYMENT,
        voice=args.voice or config.REALTIME_VOICE,
    )


def main() -> None:
    args = parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        AudioProcessor.check_devices()
    except RuntimeError as exc:
        print(f"音频设备检查失败: {exc}")
        sys.exit(1)

    agent = build_agent(args)
    logger.info("启动模式=%s，工具数=%d", args.mode, len(tools.registered_names()))

    def _on_signal(_sig, _frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        print("\n已退出。")
    except Exception as exc:
        logger.exception("运行失败")
        print(f"运行失败: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
