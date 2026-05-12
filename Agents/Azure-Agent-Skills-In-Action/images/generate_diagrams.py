"""Generate architecture diagrams for Azure Agent Skills In Action repo."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math

BASE = Path(__file__).resolve().parent
FONT_REGULAR = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"

def font(size, bold=False):
    path = FONT_BOLD if bold and Path(FONT_BOLD).exists() else FONT_REGULAR
    return ImageFont.truetype(path, size=size)

def text_size(d, text, fnt):
    box = d.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]

def center_text(d, text, x, y, w, fnt, fill="#0f172a"):
    tw, _ = text_size(d, text, fnt)
    d.text((x + (w - tw) / 2, y), text, font=fnt, fill=fill)

def draw_card(d, x, y, w, h, title, lines, fill, outline, tf, bf, radius=20):
    d.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=fill, outline=outline, width=3)
    cursor = y + 20
    for t in (title if isinstance(title, list) else [title]):
        tw, th = text_size(d, t, tf)
        d.text((x + (w - tw) / 2, cursor), t, font=tf, fill="#0f172a")
        cursor += th + 6
    cursor += 10
    for line in lines:
        tw, th = text_size(d, line, bf)
        d.text((x + (w - tw) / 2, cursor), line, font=bf, fill="#334155")
        cursor += th + 6

def arrow_down(d, x1, y1, x2, y2, color="#64748b"):
    d.line((x1, y1, x2, y2), fill=color, width=3)
    sz = 14
    angle = math.atan2(y2 - y1, x2 - x1)
    p1 = (x2, y2)
    p2 = (x2 - sz * math.cos(angle - math.pi / 7), y2 - sz * math.sin(angle - math.pi / 7))
    p3 = (x2 - sz * math.cos(angle + math.pi / 7), y2 - sz * math.sin(angle + math.pi / 7))
    d.polygon([p1, p2, p3], fill=color)


# ============================================================
# Diagram 1: Three-Layer Architecture
# ============================================================
def gen_three_layer():
    W, H = 3840, 1500
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    TF = font(44, True); BF = font(30); HF = font(56, True); SF = font(26)

    # Title
    center_text(d, "Azure Skills Plugin — Three-Layer Architecture", 0, 40, W, HF)
    center_text(d, "Skills (Brain) + Azure MCP Server (Hands) + Foundry MCP (AI Specialist)", 0, 110, W, font(34))

    # Layer 1: Skills
    layer_y = 220
    draw_card(d, 120, layer_y, 3600, 180, "Layer 1: Skills — The Brain (26 top-level skills, 31 SKILL.md)",
              ["Decision trees, workflows, guardrails — teach the agent WHEN and HOW to use Azure"],
              "#eaf3ff", "#1d4ed8", TF, BF, radius=24)

    # 6 skill groups
    groups = [
        ("Build & Deploy", ["azure-prepare", "azure-validate", "azure-deploy", "azure-upgrade", "azure-cloud-migrate"], "#ecfdf5", "#059669"),
        ("Platform & Infra", ["azure-compute", "azure-kubernetes", "airunway-aks-setup", "azure-storage", "azure-messaging", "azure-kusto"], "#ecfdf5", "#059669"),
        ("Ops & Cost", ["azure-diagnostics", "appinsights-instrumentation", "azure-cost", "azure-quotas", "azure-compliance"], "#fff7ed", "#ea580c"),
        ("Identity & RBAC", ["azure-rbac", "entra-app-registration", "entra-agent-id"], "#fef3c7", "#d97706"),
        ("Resource & Arch", ["azure-resource-lookup", "azure-resource-visualizer", "azure-enterprise-infra-planner"], "#fef3c7", "#d97706"),
        ("AI & Foundry", ["azure-ai", "azure-aigateway", "azure-hosted-copilot-sdk", "microsoft-foundry"], "#eef2ff", "#4f46e5"),
    ]
    gw = 570; gap = 30; gx = 120
    gy = layer_y + 220
    for title, items, fill, outline in groups:
        draw_card(d, gx, gy, gw, 340, title, items, fill, outline, font(32, True), font(24))
        arrow_down(d, gx + gw // 2, layer_y + 180, gx + gw // 2, gy)
        gx += gw + gap

    # Layer 2: Azure MCP Server
    layer2_y = gy + 390
    draw_card(d, 120, layer2_y, 1750, 160, "Layer 2: Azure MCP Server — The Hands",
              ["200+ structured tools across 40+ Azure services", "Resource inventory, monitoring, pricing, storage, databases, messaging"],
              "#f0fdf4", "#16a34a", TF, BF, radius=24)

    # Layer 3: Foundry MCP
    draw_card(d, 1920, layer2_y, 1800, 160, "Layer 3: Foundry MCP — The AI Specialist",
              ["Model catalog, deployments, agents, evaluations", "Create → Deploy → Invoke → Observe → Trace → Troubleshoot"],
              "#eef2ff", "#4f46e5", TF, BF, radius=24)

    # Arrows from skill groups down to layers
    for i in range(4):
        x = 120 + i * (gw + gap) + gw // 2
        arrow_down(d, x, gy + 340, 120 + 1750 // 2, layer2_y)
    for i in range(4, 6):
        x = 120 + i * (gw + gap) + gw // 2
        arrow_down(d, x, gy + 340, 1920 + 1800 // 2, layer2_y)

    # Execution bar
    bar_y = layer2_y + 210
    draw_card(d, 120, bar_y, 3600, 130, "Execution: Agent acts on LIVE Azure & Foundry resources",
              ["az login → npx @azure/mcp@latest server start → Agent receives 200+ tools + Foundry workflows"],
              "#fefce8", "#ca8a04", TF, BF, radius=24)

    # Multi-host bar
    host_y = bar_y + 175
    draw_card(d, 120, host_y, 3600, 120, "Multi-Host Support",
              ["VS Code Copilot | Copilot CLI | Claude Code | Cursor | Codex CLI | Gemini CLI | IntelliJ IDEA"],
              "#f8fafc", "#64748b", font(36, True), font(30), radius=24)

    # Footer
    d.text((120, H - 50), "Source: microsoft/azure-skills (v1.1.39, 2026-05-11) — 613 files, 31 SKILL.md definitions across 26 top-level skills",
           font=SF, fill="#94a3b8")

    # Add white padding + border per repo standard
    padded = Image.new("RGB", (W + 48, H + 48), "white")
    padded.paste(img, (24, 24))
    d2 = ImageDraw.Draw(padded)
    d2.rectangle((0, 0, W + 47, H + 47), outline="#dcdee2", width=1)
    padded.save(BASE / "architecture-overview.png", quality=95)
    print(f"architecture-overview.png: {W + 48}x{H + 48}")


# ============================================================
# Diagram 2: Deployment Workflow (prepare → validate → deploy)
# ============================================================
def gen_deploy_workflow():
    W, H = 3840, 1100
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    TF = font(44, True); BF = font(28); HF = font(52, True)

    center_text(d, "The Mandatory Deployment Workflow: prepare → validate → deploy", 0, 40, W, HF)
    center_text(d, "Each phase is a hard gate — no shortcuts allowed", 0, 105, W, font(32))

    phases = [
        ("Phase 1: azure-prepare", "#eaf3ff", "#1d4ed8",
         ["Analyze workspace", "Gather requirements", "Select recipe (AZD/Bicep/Terraform)", "Plan architecture",
          "Generate infra code + Dockerfiles", "Write .azure/deployment-plan.md", "Get user approval"]),
        ("Phase 2: azure-validate", "#ecfdf5", "#059669",
         ["Read deployment-plan.md", "Run recipe-specific validation", "Build verification",
          "Static RBAC role check", "Record proof in plan Section 7", "Set status → Validated"]),
        ("Phase 3: azure-deploy", "#fff7ed", "#ea580c",
         ["Check plan status = Validated", "Pre-deploy checklist", "RBAC health check (Container Apps + ACR)",
          "Execute deployment (azd/terraform/bicep)", "Post-deploy SQL + EF migration",
          "Live role verification", "Report endpoint URLs"]),
    ]

    pw = 1100; gap = 80; px = (W - 3 * pw - 2 * gap) // 2
    py = 180
    card_h = 580
    for i, (title, fill, outline, lines) in enumerate(phases):
        x = px + i * (pw + gap)
        draw_card(d, x, py, pw, card_h, title, lines, fill, outline, TF, BF, radius=24)
        if i < 2:
            ax = x + pw
            ay = py + card_h // 2
            arrow_down(d, ax + 10, ay, ax + gap - 10, ay, color="#475569")

    # Gate labels
    gate_font = font(28, True)
    for i, label in enumerate(["Gate: Plan approved", "Gate: Status = Validated"]):
        x = px + (i + 1) * pw + i * gap + gap // 2
        tw, _ = text_size(d, label, gate_font)
        d.text((x + (gap - tw) // 2, py + card_h // 2 + 40), label, font=gate_font, fill="#dc2626")

    # Key artifact
    d.text((px, py + card_h + 40), "Key Artifact: .azure/deployment-plan.md — the single source of truth across all three phases",
           font=font(30, True), fill="#1e40af")
    d.text((px, py + card_h + 85), "Safety: Destructive actions require ask_user | Never delete workspace | SQL: Entra-only auth, no passwords",
           font=font(28), fill="#64748b")

    padded = Image.new("RGB", (W + 48, H + 48), "white")
    padded.paste(img, (24, 24))
    d2 = ImageDraw.Draw(padded)
    d2.rectangle((0, 0, W + 47, H + 47), outline="#dcdee2", width=1)
    padded.save(BASE / "deploy-workflow.png", quality=95)
    print(f"deploy-workflow.png: {W + 48}x{H + 48}")


# ============================================================
# Diagram 3: Platform Stickiness Analysis
# ============================================================
def gen_stickiness():
    W, H = 3840, 1800
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    TF = font(40, True); BF = font(26); HF = font(52, True)

    center_text(d, "Platform Stickiness Analysis — Where Lock-in Actually Happens", 0, 40, W, HF)

    layers = [
        ("Identity Layer (Deepest)", "#fef3c7", "#d97706", 900,
         ["Entra ID + RBAC + Managed Identity + Agent Identity",
          "entra-app-registration / entra-agent-id / azure-rbac / azure-identity-*",
          "Once org identity is on Entra → auth model, permission graph,",
          "and governance all depend on Microsoft — hardest to migrate"]),
        ("AI Runtime Layer", "#eef2ff", "#4f46e5", 700,
         ["Foundry: model deploy + agent lifecycle + eval + observability",
          "microsoft-foundry + 10 sub-skills (hosted agents, toolboxes, memory, etc.)",
          "Agent runtime, evaluation, tracing all on Foundry —",
          "moving agents to another platform = rebuild from scratch"]),
        ("Infra & Deploy Layer", "#ecfdf5", "#059669", 700,
         ["azure-prepare → azure-validate → azure-deploy pipeline",
          "Generates Bicep/Terraform + azure.yaml targeting Azure services",
          "Container Apps / App Service / Functions / AKS / APIM / Storage / Cosmos",
          "Code + infra + deploy scripts all Azure-native — significant refactor to migrate"]),
        ("Dev Experience Layer (Shallowest)", "#f8fafc", "#64748b", 700,
         ["174 SDK skills across Python / .NET / TypeScript / Java / Rust",
          "Agent writes Azure SDK patterns: imports, auth, error handling",
          "Shallowest stickiness — SDK code can be replaced per-file,",
          "but accumulated across a project it becomes significant"]),
    ]

    y = 130; gap = 30
    x_base = 200
    for i, (title, fill, outline, w, lines) in enumerate(layers):
        lw = W - 400 - i * 150  # progressively narrower = pyramid effect
        lx = (W - lw) // 2
        h = 340
        draw_card(d, lx, y, lw, h, title, lines, fill, outline, TF, BF, radius=20)
        y += h + gap

    d.text((200, H - 60), "Stickiness increases from bottom to top: Dev Experience → Infra → AI Runtime → Identity (deepest)",
           font=font(30, True), fill="#475569")

    padded = Image.new("RGB", (W + 48, H + 48), "white")
    padded.paste(img, (24, 24))
    d2 = ImageDraw.Draw(padded)
    d2.rectangle((0, 0, W + 47, H + 47), outline="#dcdee2", width=1)
    padded.save(BASE / "platform-stickiness.png", quality=95)
    print(f"platform-stickiness.png: {W + 48}x{H + 48}")


if __name__ == "__main__":
    gen_three_layer()
    gen_deploy_workflow()
    gen_stickiness()
    print("All diagrams generated.")
