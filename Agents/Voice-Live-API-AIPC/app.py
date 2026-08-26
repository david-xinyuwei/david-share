"""Voice Live Agent — 本地 GUI。

双击 run.cmd 或 VoiceLiveAgent.exe 启动。
UI 在主线程，语音会话在后台线程跑 asyncio，两者通过队列通信（tkinter 非线程安全）。
"""

from __future__ import annotations

import asyncio
import base64
import logging
import queue
import math
import random
import re
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

from src import camera, config, events, tools
from src.audio import AudioProcessor

# windowed 进程的 stdout 可能不存在或是 cp1252，不先固定编码会让任何中文 print 直接报错
_stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if _stdout_reconfigure is not None:
    _stdout_reconfigure(encoding="utf-8", errors="replace")


def _self_check() -> int:
    """--self-check：让打包后的 exe 自证代码结构，不启动 GUI 或读取设备状态。

    PYZ 里的模块是压缩后的字节码，在 exe 上做明文 grep 必然搜不到，
    因此验证「重新构建是否真的生效」只能让 exe 自己导入并报告。
    构建后跑一次 VoiceLiveAgent.exe --self-check 即可确认版本正确。
    """
    from src import agent_core, confirmation, graph_mail
    from src.tools import registered_names, wallpaper

    report: list[tuple[str, bool, str]] = []

    names = registered_names()
    image_enabled = bool(config.get("AZURE_OPENAI_IMAGE_DEPLOYMENT"))
    expected_count = 25 if image_enabled else 24
    report.append((f"工具注册数为 {expected_count}", len(names) == expected_count, str(len(names))))
    report.append((
        "可选生图工具与配置一致",
        ("generate_wallpaper_image" in names) == image_enabled,
        f"configured={image_enabled}",
    ))
    for required in ("search_wallpaper_image", "set_desktop_wallpaper", "send_email"):
        report.append((f"工具 {required} 已注册", required in names, ""))
    report.append(("高影响操作有代码级确认", confirmation.is_protected("send_email"), ""))
    report.append((
        "运行时系统提示词为英文",
        re.search(r"[\u3400-\u9fff]", agent_core.INSTRUCTIONS) is None
        and "explicit language request is authoritative" in agent_core.INSTRUCTIONS,
        "english-only",
    ))
    model_tools = tools.function_tools()
    report.append((
        "模型工具 schema 为英文",
        len(model_tools) == expected_count
        and all(re.search(r"[\u3400-\u9fff]", str(item)) is None for item in model_tools),
        f"count={len(model_tools)}",
    ))

    # 壁纸修复：候选地址按可下载性排序，避免下载到站点首页
    for fn in ("_download_candidates", "_assert_public_https", "_open_pinned_response"):
        report.append((f"wallpaper.{fn}", callable(getattr(wallpaper, fn, None)), ""))
    ordered = wallpaper._download_candidates(
        type("I", (), {"url": "https://a.com/", "contentUrl": "", "thumbnailUrl": "https://b.com/x.jpg"})()
    )
    report.append(("壁纸候选优先带路径地址", ordered[:1] == ["https://b.com/x.jpg"], str(ordered)))

    # Graph cache 只检查安全持久化代码是否在包内，不读取凭据或账号。
    for fn in ("_read_cache_text", "_write_cache_text", "_restrict_cache_file", "_assert_cache_file_secure"):
        report.append((f"graph_mail.{fn}", callable(getattr(graph_mail, fn, None)), ""))

    # 电源超时必须使用 PowrProf.dll 进程内 API；启动 powercfg.exe 会随机弹
    # 0xC0000142 系统错误框，即使随后重试成功也无法用于客户演示。
    from src.tools import power

    report.append((
        "电源超时使用 PowrProf.dll 且不启动 powercfg",
        callable(getattr(power, "_read_power_value", None))
        and callable(getattr(power, "_write_power_value", None))
        and not hasattr(power, "_powercfg"),
        "in-process",
    ))
    lines = [f"exe frozen = {getattr(sys, 'frozen', False)}", f"PROJECT_ROOT = {config.PROJECT_ROOT}", ""]
    failed = 0
    for name, ok, detail in report:
        if not ok:
            failed += 1
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -> {detail}" if detail else ""))
    lines.append("")
    lines.append(f"SELF_CHECK={'PASS' if failed == 0 else 'FAIL'} failed={failed}")
    text = "\n".join(lines)

    # windowed exe 没有可用控制台，写文件才是可靠的输出通道
    (config.PROJECT_ROOT / "self_check.txt").write_text(text, encoding="utf-8")
    print(text)
    return 1 if failed else 0


if "--self-check" in sys.argv:
    raise SystemExit(_self_check())

LOG_DIR = config.PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    filename=str(LOG_DIR / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_voiceagent.log"),
    filemode="w",
    format="%(asctime)s:%(name)s:%(levelname)s:%(message)s",
    level=logging.INFO,
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

BG_APP = "#f4f6fc"
BG_PANEL = "#ffffff"
BG_CARD = "#f4f6fd"
BG_USER = "#e1f0ff"
BG_BOT = "#f3f0ff"
BORDER = "#e6eaf5"
FG_MAIN = "#2f3345"
FG_DIM = "#8b91a8"
ACCENT = "#6c5ce7"
ACCENT_SOFT = "#c9c2ff"
BRAND_RED = "#e2231a"
GREEN = "#16a34a"
GREEN_SOFT = "#86efac"
YELLOW = "#e08c00"
RED = "#dc2626"

FONT_UI = "Microsoft YaHei UI"
FONT_MONO = "Consolas"

WAVE_BARS = 26
STAGE_HEIGHT = 132
ROBOT_ZONE = 210
EYE_IDLE = "#b6aeff"

ASSISTANT_NAME = "Aria"

STATES = {
    "idle": ("待命中", FG_DIM),
    "connecting": ("连接中", YELLOW),
    "ready": ("我在听", ACCENT),
    "listening": ("你在说", GREEN),
    "thinking": ("思考中", YELLOW),
    "speaking": (f"{ASSISTANT_NAME} 在说", ACCENT),
}


class ToolCard(tk.Frame):
    """右侧面板里的一张工具调用卡片，从「调用中」原地更新为「完成 / 失败」。"""

    def __init__(self, master: tk.Misc, name: str) -> None:
        super().__init__(master, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
        self.columnconfigure(1, weight=1)

        self.icon = tk.Label(self, text="●", bg=BG_CARD, fg=YELLOW, font=(FONT_UI, 11))
        self.icon.grid(row=0, column=0, sticky="nw", padx=(10, 6), pady=(8, 0))

        self.title = tk.Label(
            self, text=name, bg=BG_CARD, fg=FG_MAIN, font=(FONT_UI, 10, "bold"), anchor="w"
        )
        self.title.grid(row=0, column=1, sticky="ew", pady=(8, 0))

        self.elapsed = tk.Label(self, text="调用中", bg=BG_CARD, fg=FG_DIM, font=(FONT_MONO, 9))
        self.elapsed.grid(row=0, column=2, sticky="ne", padx=(6, 10), pady=(8, 0))

        self.detail = tk.Label(
            self, text="", bg=BG_CARD, fg=FG_DIM, font=(FONT_MONO, 8),
            anchor="w", justify="left", wraplength=260,
        )
        self.detail.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=(2, 8))

    def set_arguments(self, arguments: str | None) -> None:
        if arguments and arguments.strip() not in ("", "{}"):
            self.detail.configure(text=arguments.strip())

    def finish(self, ok: bool, elapsed: float, error: str | None) -> None:
        self.icon.configure(text="✓" if ok else "✕", fg=GREEN if ok else RED)
        self.elapsed.configure(text=f"{elapsed:.2f}s", fg=GREEN if ok else RED)
        if not ok and error:
            self.detail.configure(text=str(error), fg=RED)


class VoiceAgentApp:
    def __init__(self) -> None:
        self.events: queue.Queue[tuple[str, str, dict]] = queue.Queue()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.task: asyncio.Task | None = None
        self.thread: threading.Thread | None = None
        self.running = False
        self.cards: dict[str, ToolCard] = {}
        self._state = "idle"
        self.agent = None
        self._phase = 0.0
        self._levels = [0.0] * WAVE_BARS
        self._blink_until = 0.0
        self._next_blink = time.monotonic() + 3.0
        self._type_queue: list[str] = []
        self._typing = False

        events.subscribe(lambda kind, text, meta: self.events.put((kind, text, meta)))
        self._build_ui()
        self._announce_config()
        self.root.after(80, self._drain)
        self.root.after(40, self._animate)

    def _announce_config(self) -> None:
        # 配置可能来自 exe 内嵌的 .env，因此判据是「关键项有没有值」，不是「文件在不在」
        if not config.get("AZURE_VOICELIVE_ENDPOINT"):
            self.events.put(
                (
                    "error",
                    f"未找到可用配置。请把 .env 放在 {config.PROJECT_ROOT} 后重新启动",
                    {},
                )
            )
            return
        source = "外部 .env" if (config.PROJECT_ROOT / ".env").exists() else "内嵌配置"
        self.events.put(
            ("status", f"配置已加载（{source}）· {len(tools.registered_names())} 个工具就绪", {})
        )

    # ---------- UI ----------

    def _build_ui(self) -> None:
        self.root = tk.Tk()
        self.root.title("Voice Live Agent")
        self.root.geometry("1120x700")
        self.root.minsize(900, 560)
        self.root.configure(bg=BG_APP)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._style_ttk()

        self._build_header()
        self._build_wave()

        body = tk.Frame(self.root, bg=BG_APP)
        body.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        body.columnconfigure(0, weight=62, uniform="col")
        body.columnconfigure(1, weight=38, uniform="col")
        body.rowconfigure(0, weight=1)

        self._build_chat(body)
        self._build_tools(body)

        tk.Label(
            self.root,
            text='试试说：「今天北京天气怎么样」 · 「整理一份今天的科技新闻发到我邮箱」 · 「网上找一张雪山日出的壁纸换成我的桌面」',
            bg=BG_APP, fg=FG_DIM, font=(FONT_UI, 9),
        ).pack(pady=(0, 12))

    def _style_ttk(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox",
            fieldbackground=BG_CARD, background=BG_CARD, foreground=FG_MAIN,
            arrowcolor=FG_DIM, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
            selectbackground=BG_CARD, selectforeground=FG_MAIN,
        )
        style.map("Dark.TCombobox", fieldbackground=[("readonly", BG_CARD)])
        style.configure(
            "Dark.Vertical.TScrollbar",
            background=BG_CARD, troughcolor=BG_PANEL, bordercolor=BG_PANEL,
            arrowcolor=FG_DIM, lightcolor=BG_CARD, darkcolor=BG_CARD,
        )

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=BG_APP)
        header.pack(fill="x", padx=16, pady=(14, 10))

        left = tk.Frame(header, bg=BG_APP)
        left.pack(side="left")
        tk.Frame(left, bg=BRAND_RED, width=4, height=38).pack(side="left", padx=(0, 12))

        titles = tk.Frame(left, bg=BG_APP)
        titles.pack(side="left")
        tk.Label(
            titles, text="Voice Live Agent", bg=BG_APP, fg=FG_MAIN, font=(FONT_UI, 15, "bold")
        ).pack(anchor="w")
        tk.Label(
            titles, text="Azure Voice Live · GPT Realtime · Function Calling",
            bg=BG_APP, fg=FG_DIM, font=(FONT_UI, 9),
        ).pack(anchor="w")

        right = tk.Frame(header, bg=BG_APP)
        right.pack(side="right")

        self.mode = tk.StringVar(value="voicelive")
        combo = ttk.Combobox(
            right, textvariable=self.mode, values=["voicelive", "voicelive-agent", "realtime"],
            width=11, state="readonly", style="Dark.TCombobox", font=(FONT_UI, 9),
        )
        combo.pack(side="left", padx=(0, 12))

        self.start_btn = self._button(right, "开始对话", self._start, ACCENT, "#3d7ae8")
        self.start_btn.pack(side="left")
        self.stop_btn = self._button(right, "停止", self._stop, "#c8ccdb", "#b6bbcd")
        self.stop_btn.configure(state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))

    def _button(self, master: tk.Misc, text: str, command, bg: str, hover: str) -> tk.Button:
        btn = tk.Button(
            master, text=text, command=command, bg=bg, fg="white", relief="flat",
            font=(FONT_UI, 10), padx=20, pady=7, cursor="hand2",
            activebackground=hover, activeforeground="white", borderwidth=0,
            disabledforeground="#5b6270",
        )
        btn.bind("<Enter>", lambda _e: btn["state"] == "normal" and btn.configure(bg=hover))
        btn.bind("<Leave>", lambda _e: btn.configure(bg=bg))
        return btn

    def _panel(self, master: tk.Misc, title: str, column: int) -> tk.Frame:
        wrap = tk.Frame(master, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        wrap.grid(row=0, column=column, sticky="nsew", padx=(0, 12) if column == 0 else (0, 0))
        wrap.rowconfigure(1, weight=1)
        wrap.columnconfigure(0, weight=1)

        head = tk.Frame(wrap, bg=BG_PANEL)
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        tk.Label(head, text=title, bg=BG_PANEL, fg=FG_DIM, font=(FONT_UI, 9, "bold")).pack(side="left")
        return wrap

    def _build_chat(self, body: tk.Frame) -> None:
        wrap = self._panel(body, "对话", 0)

        self.chat = tk.Text(
            wrap, bg=BG_PANEL, fg=FG_MAIN, relief="flat", wrap="word", state="disabled",
            font=(FONT_UI, 11), padx=14, pady=6, spacing1=2, spacing3=2,
            highlightthickness=0, insertbackground=BG_PANEL, cursor="arrow",
        )
        bar = ttk.Scrollbar(wrap, command=self.chat.yview, style="Dark.Vertical.TScrollbar")
        self.chat.configure(yscrollcommand=bar.set)
        self.chat.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        bar.grid(row=1, column=1, sticky="ns", pady=(0, 12), padx=(0, 4))

        self.chat.tag_config("user_label", foreground=GREEN, font=(FONT_UI, 9), justify="right",
                             rmargin=14, spacing1=10)
        self.chat.tag_config("user_body", background=BG_USER, foreground=FG_MAIN, justify="right",
                             rmargin=14, lmargin1=90, lmargin2=90, spacing1=4, spacing3=9)
        self.chat.tag_config("assistant_label", foreground=ACCENT, font=(FONT_UI, 9), lmargin1=14,
                             spacing1=10)
        self.chat.tag_config("assistant_body", background=BG_BOT, foreground=FG_MAIN, lmargin1=14,
                             lmargin2=14, rmargin=90, spacing1=4, spacing3=9)
        self.chat.tag_config("status", foreground=FG_DIM, font=(FONT_UI, 9), justify="center",
                             spacing1=8, spacing3=4)
        self.chat.tag_config("error", foreground=RED, font=(FONT_UI, 10), lmargin1=14, spacing1=6)

    def _build_tools(self, body: tk.Frame) -> None:
        wrap = self._panel(body, "实时工具调用", 1)
        wrap.rowconfigure(1, weight=0)
        wrap.rowconfigure(2, weight=1)

        self.cam_box = tk.Frame(wrap, bg=BG_CARD, highlightthickness=1,
                                highlightbackground=BORDER, highlightcolor=BORDER)
        self.cam_box.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))

        cam_head = tk.Frame(self.cam_box, bg=BG_CARD)
        cam_head.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(cam_head, text="摄像头画面", bg=BG_CARD, fg=FG_DIM,
                 font=(FONT_UI, 9)).pack(side="left")
        self.cam_btn = tk.Button(
            cam_head, text="打开摄像头", command=self._toggle_camera, bg=BG_PANEL, fg=ACCENT,
            relief="flat", font=(FONT_UI, 8), padx=8, pady=1, cursor="hand2", borderwidth=0,
            activebackground=BG_CARD, activeforeground=ACCENT,
        )
        self.cam_btn.pack(side="right")

        self.cam_view = tk.Label(self.cam_box, bg=BG_CARD, fg=FG_DIM, font=(FONT_UI, 9),
                                 text="打开摄像头后这里是实时画面，\n举起物品直接问「这是什么」",
                                 height=4)
        self.cam_view.pack(padx=8, pady=(0, 8))
        self.cam_caption = tk.Label(self.cam_box, text="", bg=BG_CARD, fg=FG_DIM, font=(FONT_UI, 8))
        self.cam_caption.pack(anchor="w", padx=8, pady=(0, 6))
        self._cam_image = None  # PhotoImage 必须保留引用，否则被回收后显示空白

        self.tool_canvas = tk.Canvas(wrap, bg=BG_PANEL, highlightthickness=0)
        bar = ttk.Scrollbar(wrap, command=self.tool_canvas.yview, style="Dark.Vertical.TScrollbar")
        self.tool_canvas.configure(yscrollcommand=bar.set)
        self.tool_canvas.grid(row=2, column=0, sticky="nsew", padx=(10, 0), pady=(0, 12))
        bar.grid(row=2, column=1, sticky="ns", pady=(0, 12), padx=(0, 4))

        self.tool_host = tk.Frame(self.tool_canvas, bg=BG_PANEL)
        self.tool_window = self.tool_canvas.create_window((0, 0), window=self.tool_host, anchor="nw")
        self.tool_host.bind(
            "<Configure>",
            lambda _e: self.tool_canvas.configure(scrollregion=self.tool_canvas.bbox("all")),
        )
        self.tool_canvas.bind(
            "<Configure>",
            lambda e: self.tool_canvas.itemconfigure(self.tool_window, width=e.width - 10),
        )

        self.tool_empty = tk.Label(
            self.tool_host, text="等待语音指令…\n助手调用工具时会实时出现在这里",
            bg=BG_PANEL, fg=FG_DIM, font=(FONT_UI, 9), justify="left",
        )
        self.tool_empty.pack(anchor="w", pady=8)

    def _toggle_camera(self) -> None:
        if camera.stream.running:
            camera.stream.stop()
            self.cam_btn.configure(text="打开摄像头")
            self.cam_view.configure(image="", text="摄像头已关闭", height=4)
            self.cam_caption.configure(text="")
            self._cam_image = None
            self._say("status", "摄像头已关闭")
            return

        try:
            camera.stream.start()
        except Exception as exc:
            self._say("error", f"打开摄像头失败：{exc}")
            return

        self.cam_btn.configure(text="关闭摄像头")
        self._say("status", f"摄像头已打开（{camera.stream.source}），举起物品直接问「这是什么」")
        self._refresh_camera()

    def _refresh_camera(self) -> None:
        """把实时流的当前帧画到界面上，约 12 fps 足够看清并且不抢 CPU。"""
        if not camera.stream.running:
            return

        frame = camera.stream.latest_frame()
        if frame is not None:
            try:
                import cv2

                height, width = frame.shape[:2]
                target_w = 360
                preview = cv2.resize(frame, (target_w, max(1, int(height * target_w / width))))
                ok, buffer = cv2.imencode(".png", preview)
                if ok:
                    # Tk 的 PhotoImage(data=) 只接受 base64，直接喂原始 PNG 字节会报 TclError。
                    image = tk.PhotoImage(data=base64.b64encode(buffer.tobytes()))
                    self._cam_image = image
                    self.cam_view.configure(image=image, text="", height=0)
                    self.cam_caption.configure(
                        text=f"实时画面 · {camera.stream.source} · {datetime.now():%H:%M:%S}"
                    )
            except Exception as exc:
                self.cam_caption.configure(text=f"预览异常：{exc}")

        self.root.after(80, self._refresh_camera)

    def _show_camera_frame(self, png_path: str) -> None:
        """流没开时，识别工具会临时抓拍一张，这里把那一帧显示出来。"""
        if camera.stream.running:
            return
        try:
            image = tk.PhotoImage(file=png_path)
        except tk.TclError as exc:
            self._say("error", f"摄像头画面显示失败：{exc}")
            return
        self._cam_image = image
        self.cam_view.configure(image=image, text="", height=0)
        self.cam_caption.configure(text=f"拍于 {datetime.now():%H:%M:%S}")

    # ---------- 事件渲染 ----------

    def _set_state(self, key: str) -> None:
        self._state = key
        text, color = STATES[key]
        self.state_text.configure(text=text, fg=color)

    def _build_wave(self) -> None:
        shell = tk.Frame(self.root, bg=BG_PANEL, highlightbackground=BORDER, highlightthickness=1)
        shell.pack(fill="x", padx=16, pady=(0, 10))

        self.wave = tk.Canvas(shell, height=STAGE_HEIGHT, bg=BG_PANEL, highlightthickness=0)
        self.wave.pack(fill="x", padx=16, pady=(10, 4))

        self.state_text = tk.Label(
            shell, text="待命中", bg=BG_PANEL, fg=FG_DIM, font=(FONT_UI, 10)
        )
        self.state_text.pack(pady=(0, 10))

    @staticmethod
    def _round_rect(canvas: tk.Canvas, x0, y0, x1, y1, r, **kwargs):
        r = min(r, abs(x1 - x0) / 2, abs(y1 - y0) / 2)
        points = [
            x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
            x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
            x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _draw_robot(self, cx: float, level: float, eye_color: str) -> None:
        c = self.wave
        cy = STAGE_HEIGHT * 0.46
        r = 46

        # \u8033\u673a
        for side in (-1, 1):
            x = cx + side * (r + 9)
            c.create_oval(x - 11, cy - 20, x + 11, cy + 20, fill="#d8dced", outline="#c3c8dd")

        # \u8eab\u4f53\u5148\u753b\uff0c\u8ba9\u5934\u90e8\u538b\u5728\u4e0a\u9762
        self._round_rect(c, cx - 30, cy + r - 8, cx + 30, cy + r + 34, 14,
                         fill="#fbfcff", outline="#d5daea")
        c.create_oval(cx - 7, cy + r + 6, cx - 1, cy + r + 12, fill="#ccd2e6", outline="")
        c.create_oval(cx + 1, cy + r + 6, cx + 7, cy + r + 12, fill="#ccd2e6", outline="")

        # \u5934\u90e8
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#ffffff", outline="#d5daea", width=2)

        # \u62a4\u76ee\u955c\u9762\u7f69
        self._round_rect(c, cx - r * 0.86, cy - r * 0.30, cx + r * 0.86, cy + r * 0.60, 20,
                         fill="#23283a", outline="#171b28")

        # \u773c\u775b\uff1a\u9ad8\u5ea6\u8ddf\u7740\u97f3\u91cf\u8d70\uff0c\u7728\u773c\u65f6\u538b\u6241
        blink = time.monotonic() < self._blink_until
        eye_h = 3 if blink else 8 + level * 13
        eye_w = 15
        eye_y = cy + r * 0.15
        for side in (-1, 1):
            ex = cx + side * 18
            self._round_rect(c, ex - eye_w / 2, eye_y - eye_h / 2, ex + eye_w / 2, eye_y + eye_h / 2,
                             4, fill=eye_color, outline="")

        # \u54c1\u724c\u7ea2\u80f8\u7ae0
        c.create_rectangle(cx - 2, cy + r + 14, cx + 2, cy + r + 24, fill=BRAND_RED, outline="")

    def _draw_wave(self, x0: float, level: float, color: str, soft: str) -> None:
        width = self.wave.winfo_width()
        if width - x0 < 60:
            return

        mid = STAGE_HEIGHT / 2
        span_w = width - x0
        gap = span_w / WAVE_BARS
        bar_w = max(2.0, gap * 0.34)

        for i in range(WAVE_BARS):
            # \u4e2d\u95f4\u9ad8\u3001\u4e24\u7aef\u4f4e\uff0c\u518d\u53e0\u4e00\u5c42\u884c\u8fdb\u6ce2\uff0c\u770b\u8d77\u6765\u50cf\u58f0\u97f3\u5728\u6d41\u52a8
            arc = math.sin(math.pi * (i + 0.5) / WAVE_BARS)
            ripple = 0.55 + 0.45 * math.sin(self._phase * 2.6 + i * 0.55)
            target = level * arc * ripple
            self._levels[i] += (target - self._levels[i]) * 0.45

            h = 3 + self._levels[i] * (STAGE_HEIGHT - 40)
            x = x0 + gap * (i + 0.5)
            self.wave.create_line(
                x, mid - h / 2, x, mid + h / 2,
                fill=color if self._levels[i] > 0.06 else soft,
                width=bar_w, capstyle="round",
            )

    def _render(self, level: float, color: str, soft: str, eye: str) -> None:
        self.wave.delete("all")
        if self.wave.winfo_width() < 80:
            return
        self._draw_robot(ROBOT_ZONE / 2, level, eye)
        self._draw_wave(ROBOT_ZONE, level, color, soft)

    def _animate(self) -> None:
        self._phase += 0.12
        now = time.monotonic()
        if now >= self._next_blink:
            self._blink_until = now + 0.12
            self._next_blink = now + random.uniform(2.8, 6.0)

        audio = getattr(self.agent, "audio", None) if self.agent else None
        out_level = getattr(audio, "output_level", 0.0) if audio else 0.0
        in_level = getattr(audio, "input_level", 0.0) if audio else 0.0

        if out_level > 0.04:
            self._render(out_level, ACCENT, ACCENT_SOFT, ACCENT)
            self._set_state("speaking")
        elif in_level > 0.06:
            self._render(in_level, GREEN, GREEN_SOFT, GREEN)
            self._set_state("listening")
        else:
            idle = 0.05 + 0.03 * math.sin(self._phase * 1.5)
            self._render(idle, ACCENT_SOFT, ACCENT_SOFT, EYE_IDLE)

        self.root.after(40, self._animate)

    def _say(self, who: str, text: str) -> None:
        self.chat.configure(state="normal")
        if who in ("user", "assistant"):
            label = "你" if who == "user" else ASSISTANT_NAME
            self.chat.insert("end", f"{label}\n", f"{who}_label")
            self.chat.insert("end", f"  {text}  \n", f"{who}_body")
        else:
            self.chat.insert("end", f"{text}\n", who)
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _tool_start(self, meta: dict) -> None:
        call_id = meta.get("call_id")
        if not call_id:
            return
        self.tool_empty.pack_forget()

        card = self.cards.get(call_id)
        if card is None:
            card = ToolCard(self.tool_host, meta.get("name", "?"))
            card.pack(fill="x", pady=(0, 8))
            self.cards[call_id] = card
        card.set_arguments(meta.get("argument_summary"))
        self.tool_canvas.update_idletasks()
        self.tool_canvas.yview_moveto(1.0)

    def _tool_done(self, meta: dict) -> None:
        card = self.cards.get(meta.get("call_id", ""))
        if card is not None:
            card.finish(bool(meta.get("ok")), float(meta.get("elapsed", 0.0)), meta.get("error"))

    def _queue_assistant(self, text: str) -> None:
        self._type_queue.append(text)
        if not self._typing:
            self._next_typing()

    def _next_typing(self) -> None:
        if not self._type_queue:
            self._typing = False
            return
        self._typing = True
        text = self._type_queue.pop(0)
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{ASSISTANT_NAME}\n", "assistant_label")
        self.chat.insert("end", "  ", "assistant_body")
        self.chat.configure(state="disabled")
        self._type_step(text, 0)

    def _type_step(self, text: str, index: int) -> None:
        if index >= len(text):
            self.chat.configure(state="normal")
            self.chat.insert("end", "  \n", "assistant_body")
            self.chat.see("end")
            self.chat.configure(state="disabled")
            self._next_typing()
            return

        step = 2
        self.chat.configure(state="normal")
        self.chat.insert("end", text[index : index + step], "assistant_body")
        self.chat.see("end")
        self.chat.configure(state="disabled")
        self.root.after(30, lambda: self._type_step(text, index + step))

    def _drain(self) -> None:
        while True:
            try:
                kind, text, meta = self.events.get_nowait()
            except queue.Empty:
                break

            if kind == "tool_start":
                self._tool_start(meta)
            elif kind == "tool_done":
                self._tool_done(meta)
            elif kind == "camera_frame":
                self._show_camera_frame(text)
            elif kind == "camera_on":
                self.cam_btn.configure(text="关闭摄像头")
                self._refresh_camera()
            elif kind == "camera_off":
                self.cam_btn.configure(text="打开摄像头")
                self.cam_view.configure(image="", text="摄像头已关闭", height=4)
                self.cam_caption.configure(text="")
                self._cam_image = None
            elif kind == "user":
                self._set_state("thinking")
                self._say("user", text)
            elif kind == "assistant":
                self._queue_assistant(text)
            elif kind == "error":
                self._say("error", f"错误：{text}")
            elif kind == "status":
                if text == "[听]":
                    self._set_state("listening")
                    continue
                if text.startswith("已就绪"):
                    self._set_state("ready")
                self._say("status", text)

        self.root.after(80, self._drain)

    def _build_agent(self):
        if self.mode.get() == "voicelive":
            from src.backends.voicelive import VoiceLiveAgent, build_credential

            endpoint = config.VOICELIVE_ENDPOINT
            if not endpoint:
                raise RuntimeError("缺少 AZURE_VOICELIVE_ENDPOINT，请检查 .env")
            return VoiceLiveAgent(
                endpoint=endpoint,
                credential=build_credential(config.VOICELIVE_API_KEY),
                model=config.VOICELIVE_MODEL,
                voice=config.VOICELIVE_VOICE,
            )

        if self.mode.get() == "voicelive-agent":
            from src.backends.voicelive_agent import VoiceLiveFoundryAgent, build_agent_credential

            endpoint = config.VOICELIVE_ENDPOINT
            if not endpoint:
                raise RuntimeError("缺少 AZURE_VOICELIVE_ENDPOINT，请检查 .env")
            agent_name = config.get("AZURE_VOICELIVE_AGENT_NAME")
            project_name = config.get("AZURE_VOICELIVE_PROJECT_NAME")
            if not agent_name or not project_name:
                raise RuntimeError(
                    "缺少 AZURE_VOICELIVE_AGENT_NAME 或 AZURE_VOICELIVE_PROJECT_NAME，"
                    "请先在 Foundry 创建 Agent 并写入 .env"
                )
            return VoiceLiveFoundryAgent(
                endpoint=endpoint,
                credential=build_agent_credential(),
                agent_name=agent_name,
                project_name=project_name,
                voice=config.VOICELIVE_VOICE,
                agent_version=config.get("AZURE_VOICELIVE_AGENT_VERSION"),
            )

        from src.backends.realtime import RealtimeAgent

        endpoint = config.REALTIME_ENDPOINT
        if not endpoint:
            raise RuntimeError("缺少 AZURE_OPENAI_ENDPOINT，请检查 .env")
        return RealtimeAgent(
            endpoint=endpoint,
            api_key=config.REALTIME_API_KEY,
            deployment=config.REALTIME_DEPLOYMENT,
            voice=config.REALTIME_VOICE,
        )

    def _start(self) -> None:
        if self.running:
            return
        try:
            AudioProcessor.check_devices()
            agent = self._build_agent()
        except Exception as exc:
            self.events.put(("error", str(exc), {}))
            return

        self.running = True
        self.agent = agent
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._set_state("connecting")
        self.events.put(("status", f"已注册 {len(tools.registered_names())} 个工具", {}))

        def runner() -> None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.task = self.loop.create_task(agent.start())
            try:
                self.loop.run_until_complete(self.task)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.exception("语音会话异常")
                self.events.put(("error", f"{type(exc).__name__}: {exc}", {}))
            finally:
                self.loop.close()
                self.events.put(("status", "会话已结束", {}))
                self.root.after(0, self._reset_buttons)

        self.thread = threading.Thread(target=runner, daemon=True, name="voice-session")
        self.thread.start()

    def _stop(self) -> None:
        if self.loop and self.task and not self.task.done():
            self.loop.call_soon_threadsafe(self.task.cancel)
        self.stop_btn.configure(state="disabled")

    def _reset_buttons(self) -> None:
        self.running = False
        self.agent = None
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self._set_state("idle")

    def _on_close(self) -> None:
        self._stop()
        camera.stream.stop()
        self.root.after(400, self.root.destroy)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    try:
        VoiceAgentApp().run()
    except Exception as exc:
        logger.exception("启动失败")
        print(f"启动失败: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
