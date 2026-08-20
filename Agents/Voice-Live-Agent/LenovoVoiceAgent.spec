# PyInstaller 打包配置：单文件 GUI exe。
# tzdata / certifi 是运行期按数据文件读取的，静态分析发现不了，必须显式收集。
# webiq 与 azure.identity 内部有动态导入，同样需要显式声明。

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("tzdata") + collect_data_files("certifi")

hiddenimports = (
    collect_submodules("azure.ai.voicelive")
    + collect_submodules("azure.identity")
    + collect_submodules("webiq")
    + [
        "src.tools.briefing",
        "src.tools.clock",
        "src.tools.mailer",
        "src.tools.news",
        "src.tools.stocks",
        "src.tools.vision",
        "src.tools.wallpaper",
        "src.tools.weather",
        "src.tools.websearch",
        "src.backends.voicelive",
        "src.backends.realtime",
        "msal",
        "pyaudio",
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
    a.binaries,
    a.datas,
    [],
    name="LenovoVoiceAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
