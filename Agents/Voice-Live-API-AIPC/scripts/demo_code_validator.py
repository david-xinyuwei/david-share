"""Deterministic authenticity gate for the public Voice Live AIPC runtime."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = [ROOT / "app.py", *sorted((ROOT / "src").rglob("*.py"))]
EXPECTED_TOOL_DEFINITIONS = 25
REQUIRED_RUNTIME_MARKERS = {
    "src/tools/weather.py": ("httpx.AsyncClient", "_FORECAST_URL"),
    "src/tools/stocks.py": ("_CHART_URL", "_TENCENT_URL"),
    "src/tools/news.py": ("_DEFAULT_FEEDS", "_search_webiq"),
    "src/tools/websearch.py": ("webiq_client.client().web.search",),
    "src/tools/mailer.py": ("graph_mail.send_mail", "smtp.send_message"),
    "src/tools/wallpaper.py": ("search_with_retry", "SystemParametersInfoW"),
}


def tool_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    result: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                if decorator.func.id == "tool":
                    result.append(node)
    return result


def main() -> int:
    findings: list[str] = []
    tool_count = 0
    for path in PRODUCTION:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        relative = path.relative_to(ROOT).as_posix()

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [alias.name for alias in node.names]
                if any(module.startswith(("unittest.mock", "faker")) for module in modules):
                    findings.append(f"mock library in production: {relative}")
            if isinstance(node, ast.Import) and any(alias.name == "random" for alias in node.names):
                allowed_blink = (
                    relative == "app.py"
                    and text.count("random.") == 1
                    and "random.uniform(2.8, 6.0)" in text
                )
                if not allowed_blink:
                    findings.append(f"random data in production: {relative}")

        for function in tool_functions(tree):
            tool_count += 1
            meaningful = [
                statement
                for statement in function.body
                if not (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str)
                )
            ]
            if not meaningful or all(isinstance(item, ast.Pass) for item in meaningful):
                findings.append(f"empty tool function: {relative}:{function.name}")

    if tool_count != EXPECTED_TOOL_DEFINITIONS:
        findings.append(f"tool definition count {tool_count}, expected {EXPECTED_TOOL_DEFINITIONS}")

    for relative, markers in REQUIRED_RUNTIME_MARKERS.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                findings.append(f"missing live marker {marker}: {relative}")

    scenario = json.loads((ROOT / "scenario-manifest.json").read_text(encoding="utf-8"))
    if "mock external data" not in scenario.get("prohibited_runtime_fallbacks", []):
        findings.append("scenario manifest does not prohibit mock external data")

    if findings:
        raise SystemExit("Demo authenticity gate failed:\n- " + "\n- ".join(findings))
    print(f"PASS: {tool_count} tool definitions have executable bodies and live-service markers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
