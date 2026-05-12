"""Generate architecture diagrams for Azure Agent Skills In Action repo.

v2: Canvas 1920px wide (not 3840) so text stays readable at width="960" in GitHub.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math

BASE = Path(__file__).resolve().parent
FONT_REGULAR = "/mnt/c/Windows/Fonts/msyh.ttc"
FONT_BOLD = "/mnt/c/Windows/Fonts/msyhbd.ttc"

def font(size, bold=False):
    path = FONT_BOLD if bold and Path(FONT_BOLD).exists() else FONT_REGULAR
    return ImageFont.truetype(path, size=size)

def text_size(d, text, fnt):
    box = d.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]

def center_text(d, text, x, y, w, fnt, fill="#0f172a"):
    tw, _ = text_size(d, text, fnt)
    d.text((x + (w - tw) / 2, y), text, font=fnt, fill=fill)

def draw_card(d, x, y, w, h, title, lines, fill, outline, tf, bf, radius=12):
    d.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=fill, outline=outline, width=2)
    cursor = y + 12
    for t in (title if isinstance(title, list) else [title]):
        tw, th = text_size(d, t, tf)
        d.text((x + (w - tw) / 2, cursor), t, font=tf, fill="#0f172a")
        cursor += th + 4
    cursor += 6
    for line in lines:
        tw, th = text_size(d, line, bf)
        d.text((x + (w - tw) / 2, cursor), line, font=bf, fill="#334155")
        cursor += th + 4

def arrow_right(d, x1, y, x2, color="#64748b"):
    d.line((x1, y, x2, y), fill=color, width=2)
    sz = 8
    d.polygon([(x2, y), (x2 - sz, y - sz//2), (x2 - sz, y + sz//2)], fill=color)

def arrow_down(d, x, y1, y2, color="#64748b"):
    d.line((x, y1, x, y2), fill=color, width=2)
    sz = 8
    d.polygon([(x, y2), (x - sz//2, y2 - sz), (x + sz//2, y2 - sz)], fill=color)

def pad_and_save(img, W, H, path):
    padded = Image.new("RGB", (W + 48, H + 48), "white")
    padded.paste(img, (24, 24))
    d2 = ImageDraw.Draw(padded)
    d2.rectangle((0, 0, W + 47, H + 47), outline="#dcdee2", width=1)
    padded.save(path, quality=95)
    print(f"{path.name}: {W + 48}x{H + 48}")


# ============================================================
# Diagram 1: Three-Layer Architecture
# ============================================================
def gen_three_layer():
    W, H = 1920, 920
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    TF = font(24, True); BF = font(16); HF = font(30, True); SF = font(14)

    center_text(d, "Azure Skills Plugin — Three-Layer Architecture", 0, 20, W, HF)
    center_text(d, "Skills (Brain) + Azure MCP Server (Hands) + Foundry MCP (AI Specialist)", 0, 56, W, font(18))

    # Layer 1: Skills
    ly = 100
    draw_card(d, 60, ly, 1800, 80,
              "Layer 1: Skills — The Brain (26 top-level skills, 31 SKILL.md)",
              ["Decision trees, workflows, guardrails — teach the agent WHEN and HOW to use Azure"],
              "#eaf3ff", "#1d4ed8", TF, BF)

    # 6 skill groups
    groups = [
        ("Build & Deploy", ["azure-prepare", "azure-validate", "azure-deploy", "azure-upgrade", "azure-cloud-migrate"], "#ecfdf5", "#059669"),
        ("Platform & Infra", ["azure-compute", "azure-kubernetes", "airunway-aks-setup", "azure-storage", "azure-messaging", "azure-kusto"], "#ecfdf5", "#059669"),
        ("Ops & Cost", ["azure-diagnostics", "appinsights-instrumentation", "azure-cost", "azure-quotas", "azure-compliance"], "#fff7ed", "#ea580c"),
        ("Identity & RBAC", ["azure-rbac", "entra-app-registration", "entra-agent-id"], "#fef3c7", "#d97706"),
        ("Resource & Arch", ["azure-resource-lookup", "azure-resource-visualizer", "azure-enterprise-infra-planner"], "#fef3c7", "#d97706"),
        ("AI & Foundry", ["azure-ai", "azure-aigateway", "azure-hosted-copilot-sdk", "microsoft-foundry"], "#eef2ff", "#4f46e5"),
    ]
    gw = 285; gap = 15; gx = 60; gy = ly + 105
    for title, items, fill, outline in groups:
        draw_card(d, gx, gy, gw, 210, title, items, fill, outline, font(17, True), font(13))
        gx += gw + gap

    # Layer 2 + 3
    ly2 = gy + 235
    draw_card(d, 60, ly2, 880, 100,
              "Layer 2: Azure MCP Server — The Hands",
              ["200+ structured tools across 40+ Azure services",
               "Resource inventory, monitoring, pricing, storage, databases, messaging"],
              "#f0fdf4", "#16a34a", TF, BF)

    draw_card(d, 970, ly2, 890, 100,
              "Layer 3: Foundry MCP — The AI Specialist",
              ["Model catalog, deployments, agents, evaluations",
               "Create → Deploy → Invoke → Observe → Trace → Troubleshoot"],
              "#eef2ff", "#4f46e5", TF, BF)

    # Execution bar
    by = ly2 + 125
    draw_card(d, 60, by, 1800, 65,
              "Execution: Agent acts on LIVE Azure & Foundry resources",
              ["az login → npx @azure/mcp@latest server start → Agent receives 200+ tools + Foundry workflows"],
              "#fefce8", "#ca8a04", font(20, True), font(15))

    # Multi-host bar
    hy = by + 88
    draw_card(d, 60, hy, 1800, 55,
              "Multi-Host Support",
              ["VS Code Copilot | Copilot CLI | Claude Code | Cursor | Codex CLI | Gemini CLI | IntelliJ IDEA"],
              "#f8fafc", "#64748b", font(20, True), font(15))

    d.text((60, H - 30), "Source: microsoft/azure-skills (v1.1.39, 2026-05-11) — 613 files, 31 SKILL.md definitions across 26 top-level skills",
           font=SF, fill="#94a3b8")

    pad_and_save(img, W, H, BASE / "architecture-overview.png")


# ============================================================
# Diagram 2: Deployment Workflow
# ============================================================
def gen_deploy_workflow():
    W, H = 1920, 680
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    TF = font(22, True); BF = font(15); HF = font(28, True)

    center_text(d, "The Mandatory Deployment Workflow: prepare → validate → deploy", 0, 20, W, HF)
    center_text(d, "Each phase is a hard gate — no shortcuts allowed", 0, 54, W, font(16))

    phases = [
        ("Phase 1: azure-prepare", "#eaf3ff", "#1d4ed8",
         ["Analyze workspace", "Gather requirements", "Select recipe (AZD/Bicep/Terraform)",
          "Plan architecture", "Generate infra code + Dockerfiles",
          "Write .azure/deployment-plan.md", "Get user approval"]),
        ("Phase 2: azure-validate", "#ecfdf5", "#059669",
         ["Read deployment-plan.md", "Run recipe-specific validation",
          "Build verification", "Static RBAC role check",
          "Record proof in plan Section 7", "Set status → Validated"]),
        ("Phase 3: azure-deploy", "#fff7ed", "#ea580c",
         ["Check plan status = Validated", "Pre-deploy checklist",
          "RBAC health check (Container Apps + ACR)",
          "Execute deployment (azd/terraform/bicep)",
          "Post-deploy SQL + EF migration", "Live role verification",
          "Report endpoint URLs"]),
    ]

    pw = 540; gap = 55; px = (W - 3 * pw - 2 * gap) // 2
    py = 95; card_h = 370
    for i, (title, fill, outline, lines) in enumerate(phases):
        x = px + i * (pw + gap)
        draw_card(d, x, py, pw, card_h, title, lines, fill, outline, TF, BF)
        if i < 2:
            arrow_right(d, x + pw + 5, py + card_h // 2, x + pw + gap - 5)

    # Gate labels
    gf = font(15, True)
    for i, label in enumerate(["Gate: Plan approved", "Gate: Status = Validated"]):
        x = px + (i + 1) * pw + i * gap + gap // 2
        tw, _ = text_size(d, label, gf)
        d.text((x + (gap - tw) // 2, py + card_h // 2 + 20), label, font=gf, fill="#dc2626")

    # Key artifact
    d.text((px, py + card_h + 25),
           "Key Artifact: .azure/deployment-plan.md — the single source of truth across all three phases",
           font=font(16, True), fill="#1e40af")
    d.text((px, py + card_h + 50),
           "Safety: Destructive actions require ask_user | Never delete workspace | SQL: Entra-only auth, no passwords",
           font=font(14), fill="#64748b")

    pad_and_save(img, W, H, BASE / "deploy-workflow.png")


# ============================================================
# Diagram 3: Platform Stickiness
# ============================================================
def gen_stickiness():
    W, H = 1920, 1000
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    TF = font(22, True); BF = font(15); HF = font(28, True)

    center_text(d, "Platform Stickiness Analysis — Where Lock-in Actually Happens", 0, 20, W, HF)

    layers = [
        ("Identity Layer (Deepest)", "#fef3c7", "#d97706",
         ["Entra ID + RBAC + Managed Identity + Agent Identity",
          "entra-app-registration / entra-agent-id / azure-rbac / azure-identity-*",
          "Once org identity is on Entra → auth model, permission graph,",
          "and governance all depend on Microsoft — hardest to migrate"]),
        ("AI Runtime Layer", "#eef2ff", "#4f46e5",
         ["Foundry: model deploy + agent lifecycle + eval + observability",
          "microsoft-foundry + 10 sub-skills (hosted agents, toolboxes, memory, etc.)",
          "Agent runtime, evaluation, tracing all on Foundry —",
          "moving agents to another platform = rebuild from scratch"]),
        ("Infra & Deploy Layer", "#ecfdf5", "#059669",
         ["azure-prepare → azure-validate → azure-deploy pipeline",
          "Generates Bicep/Terraform + azure.yaml targeting Azure services",
          "Container Apps / App Service / Functions / AKS / APIM / Storage / Cosmos",
          "Code + infra + deploy scripts all Azure-native — significant refactor to migrate"]),
        ("Dev Experience Layer (Shallowest)", "#f8fafc", "#64748b",
         ["174 SDK skills across Python / .NET / TypeScript / Java / Rust",
          "Agent writes Azure SDK patterns: imports, auth, error handling",
          "Shallowest stickiness — SDK code can be replaced per-file,",
          "but accumulated across a project it becomes significant"]),
    ]

    y = 70; gap = 16
    for i, (title, fill, outline, lines) in enumerate(layers):
        lw = W - 200 - i * 80
        lx = (W - lw) // 2
        h = 200
        draw_card(d, lx, y, lw, h, title, lines, fill, outline, TF, BF)
        y += h + gap

    d.text((100, H - 35),
           "Stickiness increases from bottom to top: Dev Experience → Infra → AI Runtime → Identity (deepest)",
           font=font(16, True), fill="#475569")

    pad_and_save(img, W, H, BASE / "platform-stickiness.png")


if __name__ == "__main__":
    gen_three_layer()
    gen_deploy_workflow()
    gen_stickiness()
    print("All diagrams generated.")
