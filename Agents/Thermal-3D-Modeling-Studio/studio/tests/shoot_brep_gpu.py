"""Render the pre-generated B-rep scenes with the local GPU (headless Edge, D3D11) and save before/after screenshots.

Not part of the acceptance suite: a visual-comparison helper. Uses the isolated localhost preview (127.0.0.1:8015) and
the cached CAD results only — no model call. Usage:
    python tests/shoot_brep_gpu.py --output <dir> [--ids coldplate exv] [--quad]
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

TITLES = {"coldplate": "电池水冷板", "mchx": "微通道换热器", "exv": "电子膨胀阀阀体", "aidc": "AIDC GPU 液冷冷板",
          "fourway": "四通换向阀", "module": "热管理集成模块", "drawing2d": "2D 图纸", "thermal_sim": "AI 辅助仿真估算",
          "aps": "APS 智能排程推理", "vehicle_tms": "整车热管理系统回路", "cdu": "AIDC CDU 液冷分配单元",
          "nb_chassis_mold": "镁合金 A 壳", "nb_thermal": "笔记本双风扇散热模组", "nb_assembly_line": "笔记本总装产线数字孪生",
          "nb_packing": "包装与集装箱装载优化"}

ap = argparse.ArgumentParser()
ap.add_argument("--output", type=Path, required=True)
ap.add_argument("--ids", nargs="*", default=list(TITLES))
ap.add_argument("--quad", action="store_true")
ap.add_argument("--url", default="http://127.0.0.1:8015")
a = ap.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)          # real GPU (ANGLE/D3D11), like the user's browser
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    page = ctx.new_page()
    page.set_default_timeout(120000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)[:200]))
    assert ctx.request.post(f"{a.url}/api/login", data={"username": "preview", "password": "local-ui-test-only"}).ok
    page.add_init_script("window.__aoStates = []; addEventListener('message', e => { const d = e.data || {}; if (d.type === 'workspace-state' && d.ao) window.__aoStates.push(`${d.ao} mode=${d.aoMode}` + (d.aoCoverage ? ` occluded=${d.aoCoverage.occluded} mean=${d.aoCoverage.mean}` : '')); });")
    page.goto(f"{a.url}/?lang=zh", wait_until="domcontentloaded")
    gpu = page.evaluate("""() => { const gl = document.createElement('canvas').getContext('webgl2'); const d = gl && gl.getExtension('WEBGL_debug_renderer_info'); return d ? gl.getParameter(d.UNMASKED_RENDERER_WEBGL) : 'n/a'; }""")
    shots = []
    for sid in a.ids:
        notebook = page.locator("#industryTabs button.active").inner_text().startswith("笔记本")
        if sid.startswith("nb_") and not notebook:
            page.locator("#industryTabs button").filter(has_text="笔记本").click(force=True)
            page.wait_for_timeout(500)
        elif not sid.startswith("nb_") and notebook:
            page.locator("#industryTabs button").filter(has_text="热管理").click(force=True)
            page.wait_for_timeout(500)
        page.locator(".scenario").filter(has_text=TITLES[sid]).first.click(force=True)
        page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep")')
        page.evaluate("() => document.querySelector('[data-workspace-layout=\"single\"]').click()")
        page.wait_for_timeout(600)
        page.evaluate("() => document.getElementById('viewFit').click()")
        page.wait_for_timeout(1800)
        box = page.locator("#viewportBody").bounding_box()
        clip = {"x": box["x"], "y": box["y"], "width": min(box["width"], 1600 - box["x"]), "height": box["height"]}
        f = a.output / f"{sid}-persp.png"
        page.screenshot(path=str(f), clip=clip)
        shots.append(str(f))
        if a.quad:
            page.evaluate("() => document.querySelector('[data-workspace-layout=\"quad\"]').click()")
            page.wait_for_function('document.querySelector("[data-workspace-layout=quad]").getAttribute("aria-pressed") === "true"')
            page.wait_for_timeout(1800)
            f = a.output / f"{sid}-quad.png"
            page.screenshot(path=str(f), clip=clip)
            shots.append(str(f))
    ao_states = sorted(set(page.evaluate("() => window.__aoStates")))
    browser.close()
print(json.dumps({"gpu": gpu, "ao": ao_states, "shots": shots, "pageErrors": errors}, ensure_ascii=False))
