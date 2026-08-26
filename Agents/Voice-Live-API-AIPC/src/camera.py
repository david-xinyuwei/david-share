"""实时摄像头流。

后台线程持续抓帧，UI 实时预览，识别工具直接取当前帧——用户举起物品就能立刻问，
不需要现场再打开一次摄像头。摄像头设备只能被一个进程独占，所以全局共用一条流。
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

_MAX_CAMERA_INDEX = 3
_OPEN_WARMUP_SECONDS = 3.0
_BRIGHT_ENOUGH = 18.0
_OPEN_RETRIES = 2  # 上一次释放后设备不会立即可用，失败一次不代表真的没摄像头
_RETRY_DELAY_SECONDS = 0.8


class CameraStream:
    """一条常开的摄像头流，随时可取最新一帧。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._capture = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._frame = None
        self._source = ""
        self._error = ""
        self._preferred: tuple[str, int] | None = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def source(self) -> str:
        return self._source

    @property
    def error(self) -> str:
        return self._error

    def start(self) -> None:
        if self._running:
            return

        for attempt in range(_OPEN_RETRIES):
            attempts: list[str] = []
            if self._try_open(attempts):
                return
            # 设备刚被释放时会短暂不可用，实测重试一次就能成功，不必让用户重说一遍
            if attempt + 1 < _OPEN_RETRIES:
                logger.info("摄像头打开失败，%.1fs 后重试: %s", _RETRY_DELAY_SECONDS, "; ".join(attempts))
                time.sleep(_RETRY_DELAY_SECONDS)

        self._error = "; ".join(attempts)
        raise RuntimeError(
            f"打不开摄像头（{self._error}）。远程桌面下需在连接设置勾选「视频捕获设备」，"
            "本机使用时请检查镜头遮挡和相机隐私开关。"
        )

    def _try_open(self, attempts: list[str]) -> bool:
        import cv2

        # 顺序按实测可用性排：本机与 RDP 重定向下 DirectShow 都能开，MSMF 常常整组超时。
        candidates = [("DSHOW", cv2.CAP_DSHOW, i) for i in range(_MAX_CAMERA_INDEX)]
        candidates += [("MSMF", cv2.CAP_MSMF, i) for i in range(_MAX_CAMERA_INDEX)]
        if self._preferred is not None:
            name, index = self._preferred
            candidates.sort(key=lambda c: (c[0], c[2]) != (name, index))

        for backend_name, backend, index in candidates:
            capture = cv2.VideoCapture(index, backend)
            if not capture.isOpened():
                capture.release()
                attempts.append(f"{backend_name}[{index}]:打不开")
                continue

            frame = None
            deadline = time.monotonic() + _OPEN_WARMUP_SECONDS
            while time.monotonic() < deadline:
                ok, candidate = capture.read()
                if ok and candidate is not None:
                    frame = candidate
                    if float(candidate.mean()) >= _BRIGHT_ENOUGH:
                        break
                time.sleep(0.05)

            if frame is None:
                capture.release()
                attempts.append(f"{backend_name}[{index}]:读不到画面")
                continue

            self._capture = capture
            self._frame = frame
            self._source = f"{backend_name}[{index}]"
            self._error = ""
            self._preferred = (backend_name, index)
            self._running = True
            self._thread = threading.Thread(target=self._loop, name="camera-stream", daemon=True)
            self._thread.start()
            logger.info("摄像头流已开启: %s", self._source)
            return True
        return False

    def _loop(self) -> None:
        while self._running and self._capture is not None:
            ok, frame = self._capture.read()
            if ok and frame is not None:
                with self._lock:
                    self._frame = frame
            else:
                time.sleep(0.02)

    def latest_frame(self):
        """返回最新一帧的副本；流未开启时返回 None。"""
        with self._lock:
            frame = self._frame
        return None if frame is None else frame.copy()

    def stop(self) -> None:
        self._running = False
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=1.5)
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        with self._lock:
            self._frame = None
        self._source = ""
        logger.info("摄像头流已关闭")


stream = CameraStream()
