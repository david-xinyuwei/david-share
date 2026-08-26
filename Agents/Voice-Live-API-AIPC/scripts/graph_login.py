"""一次性授权 Graph 邮件权限（设备码流程）。

用法：
    .venv\\Scripts\\python.exe -m scripts.graph_login
"""

from __future__ import annotations

import sys

from src import graph_mail

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    existing = graph_mail.signed_in_user()
    if existing:
        print(f"当前已授权账号: {existing}")
        print("如需换账号，删除 .msal_token_cache.json 后重新运行本脚本。")

    try:
        user = graph_mail.device_code_login()
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        sys.exit(1)

    print("-" * 60)
    print(f"[PASS] 授权完成，发件账号: {user}")
    print("token 已缓存到 .msal_token_cache.json，后续发信无需再授权。")


if __name__ == "__main__":
    main()
