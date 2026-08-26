# PyInstaller 目录模式（--onedir）打包配置。
#
# 为什么需要它：单文件 exe 每次启动都要把 80MB 内容解包到 %TEMP%\_MEIxxxxx，
# 在本机（Windows ARM64 + x64 模拟层）实测解包出的 python311.dll 无法加载，
# 报「损坏的映像 / 错误状态 0xc0e90002」。目录模式不做运行时解包，DLL 直接从
# 磁盘按原样加载，规避该失败路径，同时启动明显更快。
#
# 与单文件版共用同一份 datas / hiddenimports，避免两份清单漂移。

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("tzdata") + collect_data_files("certifi")

# 目录模式下 .env 放在 exe 同级目录即可被 src/config.py 读到，
# 因此默认不内嵌；需要内嵌时显式设 BUNDLE_ENV=1。
if os.environ.get("BUNDLE_ENV", "0") == "1" and os.path.isfile(".env"):
    datas += [(".env", ".")]

hiddenimports = (
    collect_submodules("azure.ai.voicelive")
    + collect_submodules("azure.identity")
    + collect_submodules("webiq")
    + [
        "src.tools.briefing",
        "src.tools.clock",
        "src.tools.desktop",
        "src.tools.mailer",
        "src.tools.news",
        "src.tools.power",
        "src.tools.stocks",
        "src.tools.timezone",
        "src.tools.vision",
        "src.tools.wallpaper",
        "src.tools.weather",
        "src.tools.websearch",
        "src.backends.voicelive",
        "src.backends.voicelive_agent",
        "src.backends.realtime",
        "msal",
        "pyaudio",
        "pycaw",
        "comtypes",
        "cv2",
    ]
)

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "pandas", "pytest"],  # numpy 不能排除：OpenCV 依赖它
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 目录模式的关键：二进制留在 _internal，不塞进 exe
    name="VoiceLiveAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 压缩过的 DLL 在模拟层下有加载风险，明确关闭
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VoiceLiveAgent",
)
