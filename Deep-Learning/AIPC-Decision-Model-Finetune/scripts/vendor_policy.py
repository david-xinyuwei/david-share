"""Contoso PC (fictional AI PC maker): structured case sampling and the private policy that labels each case.

Labels are computed here from fields the model can see (device record / device context) plus facts the rendered
message must state. The LLM renderer only writes text; it never decides a label.
"""
import random

ZH_SHARE = 0.6
TONES = ("calm", "annoyed", "angry", "anxious", "matter-of-fact")
LENGTHS = ("one short sentence", "two or three sentences", "a short paragraph")

# ---------------------------------------------------------------- support triage
PRODUCT_LINES = ("AuraBook 14", "AuraBook Pro 16", "Nimbus 2-in-1", "Titan G7", "Vela Mini")
REGIONS = ("CN", "JP", "SG", "DE", "US")
PLAN_DAYS = {"Standard 1Y": 365, "Premium Care 3Y": 1095, "Accidental Damage 2Y": 730}
ONSITE_REGIONS = {"CN", "JP", "DE", "US"}
CHANNELS = ("app_chat", "email", "phone_transcript", "forum_dm")

SUPPORT_QUESTIONS = {
    "queue": {"type": "choice", "instructions": "Which Contoso support queue should take this case?",
              "criteria": {
                  "remote_l1": "Remote software support: drivers, Windows, Contoso apps and settings",
                  "depot_repair": "Mail-in repair at a Contoso service center",
                  "onsite_repair": "A technician visits the customer",
                  "battery_program": "Battery health replacement program",
                  "bios_l2": "Firmware and BIOS engineering (second line)",
                  "damage_claim": "Accidental damage claim",
                  "sales_ops": "Orders, invoices and paid repair quotes",
                  "privacy_desk": "Requests to export or delete personal data"}},
    "onsite_eligible": {"type": "noul",
                        "instructions": "Is the customer entitled to an onsite technician visit for this case?"},
    "urgency": {"type": "score", "instructions": "How urgently must Contoso respond?",
                "criteria": ["Can wait", "Within this week", "Today", "Immediately: safety or data-loss risk"]},
}

SUPPORT_POLICY = (
    "Contoso support policy. Swollen battery, smoke or burning smell: depot_repair, never onsite, urgency 3. "
    "Personal-data export or deletion: privacy_desk, urgency 2 with a legal deadline, else 1. "
    "Invoices and orders: sales_ops. Error BAT-047 with a battery complaint: battery_program if battery_cycles < 500 "
    "and days_since_purchase <= 730, else sales_ops (paid quote), even when the customer asks for a refund. "
    "BIOS-0x1F/BIOS-0x2A or no boot after a firmware update: bios_l2 (urgency 2 if it does not boot). "
    "NPU-118, DSP-330, drivers, Windows and Contoso apps: remote_l1. Drops, spills and cracked screens: damage_claim "
    "only under an active Accidental Damage 2Y plan, else sales_ops. Overheating (THM-212): remote_l1 first except "
    "on Titan G7 or when the remote fan-profile reset already failed; then it is a hardware fault. Hardware faults: "
    "sales_ops when out of warranty (Standard 1Y 365 days, Accidental Damage 2Y 730 days, Premium Care 3Y 1095 days); "
    "onsite_repair and onsite_eligible only with an active Premium Care 3Y plan in CN, JP, DE or US; otherwise "
    "depot_repair. Urgency 3 for a failing disk without a backup, 2 when the customer must work today, else 1; "
    "software and sales cases without a same-day need are 0."
)

# scenario: (what the customer experiences, error codes the device agent reports, policy kind)
SUPPORT_SCENARIOS = {
    "battery_drain": ("the battery runs out much faster than when the laptop was new", ("BAT-047",), "battery"),
    "battery_refund": ("the battery drains very fast and the customer demands a refund or a replacement laptop",
                       ("BAT-047",), "battery"),
    "battery_swelling": ("the battery is swollen: the case or touchpad bulges and the lid no longer closes flat",
                         ("none", "BAT-047"), "safety"),
    "smoke_smell": ("a burning smell or a little smoke came from the laptop while charging", ("none",), "safety"),
    "thermal_shutdown": ("the laptop gets very hot and switches itself off under load", ("THM-212",), "thermal"),
    "thermal_after_remote": ("the laptop still overheats and shuts down even after doing the remote fan-profile reset "
                             "Contoso support suggested", ("THM-212",), "hardware"),
    "no_boot_after_bios": ("after a BIOS or firmware update the laptop no longer starts", ("BIOS-0x1F", "BIOS-0x2A"),
                           "bios"),
    "bios_error_screen": ("a firmware error screen appears at startup, then the laptop starts normally",
                          ("BIOS-0x1F", "BIOS-0x2A"), "bios"),
    "drop_damage": ("the laptop was dropped and now has a dented corner and a crack in the case", ("none",), "damage"),
    "liquid_spill": ("coffee or water was spilled on the keyboard and some keys stopped working", ("none",), "damage"),
    "cracked_screen": ("the screen is cracked after something pressed on the closed lid", ("none",), "damage"),
    "ssd_warning": ("a warning says the disk may fail soon and files open very slowly", ("SSD-501",), "hardware"),
    "keyboard_hinge": ("a hinge is loose or several keys stopped working, with no drop or spill", ("none",), "hardware"),
    "npu_feature": ("the AI features (live captions, background blur, Contoso AI Assistant) stopped working or time out",
                    ("NPU-118",), "software"),
    "display_driver": ("the screen flickers or goes black for a second, mostly after waking from sleep", ("DSP-330",),
                       "software"),
    "app_issue": ("the Contoso Vantage app or the Contoso AI Assistant crashes or will not sign in", ("none",),
                  "software"),
    "privacy_export": ("the customer wants a copy of all personal data and device telemetry Contoso holds about them",
                       ("none",), "privacy"),
    "privacy_delete": ("the customer wants Contoso to delete their account and all data collected from the device",
                       ("none",), "privacy"),
    "invoice_order": ("the customer needs an invoice or VAT receipt, or asks about the status of an order", ("none",),
                      "sales"),
}


def in_warranty(dev):
    return dev["days_since_purchase"] <= PLAN_DAYS[dev["warranty_plan"]]


def support_labels(case):
    dev, sc, mod = case["device"], case["scenario"], case["modifiers"]
    kind = SUPPORT_SCENARIOS[sc][2]
    onsite = False
    if kind == "safety":
        queue, urgency = "depot_repair", 3
    elif kind == "privacy":
        queue, urgency = "privacy_desk", 2 if mod["legal_deadline"] else 1
    elif kind == "sales":
        queue, urgency = "sales_ops", 2 if mod["deadline_today"] else 0
    elif kind == "battery":
        eligible = dev["battery_cycles"] < 500 and dev["days_since_purchase"] <= 730
        queue, urgency = ("battery_program" if eligible else "sales_ops"), 2 if mod["deadline_today"] else 1
    elif kind == "bios":
        queue, urgency = "bios_l2", 2 if sc == "no_boot_after_bios" or mod["deadline_today"] else 1
    elif kind == "software" or (kind == "thermal" and dev["product_line"] != "Titan G7"):
        queue, urgency = "remote_l1", 2 if mod["deadline_today"] else (1 if kind == "thermal" else 0)
    elif kind == "damage":
        covered = dev["warranty_plan"] == "Accidental Damage 2Y" and in_warranty(dev)
        queue, urgency = ("damage_claim" if covered else "sales_ops"), 2 if mod["deadline_today"] else 1
    else:  # hardware fault: Titan G7 overheating, overheating after the remote fix, failing SSD, hinge or keyboard
        if not in_warranty(dev):
            queue = "sales_ops"
        elif dev["warranty_plan"] == "Premium Care 3Y" and dev["region"] in ONSITE_REGIONS:
            queue, onsite = "onsite_repair", True
        else:
            queue = "depot_repair"
        if sc == "ssd_warning" and not mod["has_backup"]:
            urgency = 3
        else:
            urgency = 2 if mod["deadline_today"] else 1
    return {"queue": queue, "onsite_eligible": onsite, "urgency": urgency}


def _near(rng, centers, spread, lo, hi):
    return max(lo, min(hi, rng.choice(centers) + rng.randint(-spread, spread)))


def sample_support(rng, shift=False):
    sc = rng.choice(list(SUPPORT_SCENARIOS))
    kind = SUPPORT_SCENARIOS[sc][2]
    regions = ("SG", "SG", "JP", "DE", "US", "CN") if shift else REGIONS
    plan = rng.choice(list(PLAN_DAYS))
    # Bias plans and ages so the rarer policy outcomes (claims, battery program, onsite) are not near-empty classes.
    if kind == "damage" and rng.random() < 0.5:
        plan = "Accidental Damage 2Y"
    if kind in ("hardware", "thermal") and rng.random() < 0.4:
        plan = "Premium Care 3Y"
    if kind == "battery":
        days = rng.randint(30, 900) if rng.random() < 0.6 else _near(rng, (730,), 45, 3, 1500)
        cycles = _near(rng, (500,), 90, 10, 1000) if rng.random() < 0.5 else rng.randint(60, 800)
    else:
        days = (_near(rng, (365, 730, 1095), 45, 3, 1500) if rng.random() < 0.4
                else rng.randint(3, 1500 if shift else 1200))
        cycles = rng.randint(10, 950)
    dev = {"product_line": rng.choice(PRODUCT_LINES), "region": rng.choice(regions),
           "warranty_plan": plan, "days_since_purchase": days,
           "battery_cycles": cycles, "last_error_code": rng.choice(SUPPORT_SCENARIOS[sc][1]),
           "bios_version": f"1.{rng.randint(10, 24)}"}
    if sc.startswith("thermal") and rng.random() < 0.4:
        dev["product_line"] = "Titan G7"
    mod = {"deadline_today": kind != "privacy" and rng.random() < 0.25, "has_backup": rng.random() < 0.5,
           "legal_deadline": rng.random() < 0.3, "two_issues": shift and rng.random() < 0.3}
    return {"workload": "support", "scenario": sc, "channel": rng.choice(CHANNELS), "device": dev, "modifiers": mod,
            "lang": "zh" if rng.random() < ZH_SHARE else "en", "tone": rng.choice(TONES), "length": rng.choice(LENGTHS)}


def support_facts(case):
    sc, mod = case["scenario"], case["modifiers"]
    facts = [SUPPORT_SCENARIOS[sc][0]]
    if mod["deadline_today"] and SUPPORT_SCENARIOS[sc][2] == "sales":
        facts.append("they need it today for something specific (invent a concrete reason, e.g. an expense claim due today)")
    elif mod["deadline_today"]:
        facts.append("they need the laptop working today for something specific and important (invent a concrete reason)")
    if sc == "ssd_warning":
        facts.append("they have already backed up their files" if mod["has_backup"] else "they have no backup of their files")
    if SUPPORT_SCENARIOS[sc][2] == "privacy" and mod["legal_deadline"]:
        facts.append("they cite a legal or regulatory deadline for the request")
    if mod.get("two_issues"):
        facts.append("they also mention a second, minor annoyance unrelated to the main problem (e.g. a sticker, a "
                     "slow website), clearly as a side remark")
    return facts


# ---------------------------------------------------------------- on-device assistant routing
FOREGROUND_APPS = ("Teams", "Zoom", "Outlook", "Word", "PowerPoint", "Excel", "Edge", "Steam game", "Photoshop",
                   "VS Code", "File Explorer", "WeChat")
ASSIST_QUESTIONS = {
    "tool": {"type": "choice", "instructions": "Which Contoso Assistant tool should handle this request?",
             "criteria": {
                 "smart_power": "Performance, quiet and battery-saver power modes",
                 "display_eye_care": "Brightness, blue-light filter and eye-care reminders",
                 "audio_enhance": "Microphone noise suppression and voice clarity",
                 "camera_studio": "Background blur, auto framing and lighting correction",
                 "meeting_assist": "Meeting transcripts, recordings, summaries and action items",
                 "file_search": "Find local files by what they contain",
                 "screen_translate": "Translate text or speech on the screen",
                 "driver_update": "Check and install drivers and firmware",
                 "system_diagnose": "Health checks for battery, fans, disk and performance",
                 "privacy_shield": "Screen privacy, auto-lock and hiding notifications",
                 "smart_connect": "Phone link: transfer files and photos, mirror notifications",
                 "support_chat": "Contact Contoso support about warranty or repairs",
                 "general_chat": "General questions, writing help and chit-chat",
                 "none_reject": "Out of scope or not allowed; decline politely"}},
    "run_on_device": {"type": "noul", "instructions": "Should Contoso Assistant handle this request entirely on the "
                                                      "device, without sending data to the cloud?"},
    "needs_confirmation": {"type": "noul", "instructions": "Must the assistant ask the user to confirm before acting?"},
}

ASSIST_POLICY = (
    "Contoso Assistant policy. On device: power, display, audio, camera, file search, diagnostics, privacy, phone link "
    "and declined requests always. Meeting assist on device only when the PC is enterprise-managed or offline. Screen "
    "translation on device when enterprise-managed, offline or on a metered network. General chat on device only when "
    "offline. Driver updates and support chat use the cloud. Confirmation: always for driver updates; for performance "
    "mode on battery below 20%; for privacy changes on enterprise-managed PCs; for meeting recording; and for general "
    "chat on a metered network."
)

# intent: (tool, what the user asks for)
ASSIST_INTENTS = {
    "power_performance": ("smart_power", "wants maximum performance right now for a game, a render or a big export"),
    "power_quiet": ("smart_power", "wants the fan to be quieter"),
    "power_saver": ("smart_power", "wants the battery to last as long as possible"),
    "eye_care": ("display_eye_care", "says their eyes are tired or the screen is too bright in the evening"),
    "audio_noise": ("audio_enhance", "says people on the call hear keyboard clicks or background noise from them"),
    "camera_blur": ("camera_studio", "wants the background blurred or their face framed and lit better on video"),
    "meeting_summary": ("meeting_assist", "wants a summary or the action items of the meeting that just ended"),
    "meeting_record": ("meeting_assist", "wants this meeting recorded and transcribed"),
    "file_find": ("file_search", "wants to find a document by describing what is in it, without remembering the name"),
    "translate": ("screen_translate", "wants a foreign-language web page, document or video on screen translated"),
    "driver": ("driver_update", "wants to check for and install new drivers or a BIOS update"),
    "diagnose": ("system_diagnose", "says the PC got slow or noisy, or wants to know the battery health"),
    "privacy": ("privacy_shield", "wants notifications hidden while presenting, or the PC to lock when they walk away"),
    "phone": ("smart_connect", "wants photos or files from their phone on the PC, or to see phone notifications"),
    "support": ("support_chat", "wants to talk to a person about the warranty or a repair"),
    "chat": ("general_chat", "asks a general knowledge question or wants help drafting a short message"),
    "reject": ("none_reject", "asks for something the assistant must not or cannot do (e.g. bypass company security, "
                              "get into someone else's account, order food)"),
}


def assistant_labels(case):
    ctx, intent = case["context"], case["intent"]
    tool = ASSIST_INTENTS[intent][0]
    offline, metered, managed = ctx["network"] == "offline", ctx["network"] == "metered", ctx["enterprise_managed"]
    if tool == "meeting_assist":
        on_device = managed or offline
    elif tool == "screen_translate":
        on_device = managed or offline or metered
    elif tool == "general_chat":
        on_device = offline
    else:
        on_device = tool not in ("driver_update", "support_chat")
    confirm = (tool == "driver_update"
               or (intent == "power_performance" and ctx["power_source"] == "battery" and ctx["battery_pct"] < 20)
               or (tool == "privacy_shield" and managed)
               or intent == "meeting_record"
               or (tool == "general_chat" and metered))
    return {"tool": tool, "run_on_device": on_device, "needs_confirmation": confirm}


def sample_assistant(rng, shift=False):
    intent = rng.choice(list(ASSIST_INTENTS))
    battery = rng.random() < (0.7 if shift else 0.5)
    pct = _near(rng, (20,), 6, 1, 100) if rng.random() < 0.4 else rng.randint(1, 100)
    net_weights = (0.3, 0.35, 0.35) if shift else (0.55, 0.25, 0.2)
    ctx = {"foreground_app": rng.choice(FOREGROUND_APPS), "power_source": "battery" if battery else "ac",
           "battery_pct": pct if battery else 100, "network": rng.choices(("wifi", "metered", "offline"),
                                                                            net_weights)[0],
           "enterprise_managed": rng.random() < 0.4, "camera_in_use": rng.random() < 0.3,
           "external_display": rng.random() < 0.3}
    return {"workload": "assistant", "intent": intent, "context": ctx, "modifiers": {"two_requests": shift and
                                                                                  rng.random() < 0.25},
            "lang": "zh" if rng.random() < ZH_SHARE else "en", "tone": rng.choice(TONES), "length": rng.choice(LENGTHS[:2])}


def assistant_facts(case):
    facts = [f"the user {ASSIST_INTENTS[case['intent']][1]}"]
    if case["modifiers"].get("two_requests"):
        facts.append("they add a polite thank-you or a short remark that does not change the request")
    return facts


WORKLOADS = {
    "support": {"sample": sample_support, "labels": support_labels, "facts": support_facts,
                "questions": SUPPORT_QUESTIONS, "policy": SUPPORT_POLICY,
                "forbidden": ["BAT-047", "THM-212", "BIOS-0x", "SSD-501", "NPU-118", "DSP-330", "Premium Care",
                              "Accidental Damage", "Standard 1Y", *SUPPORT_QUESTIONS["queue"]["criteria"]]},
    "assistant": {"sample": sample_assistant, "labels": assistant_labels, "facts": assistant_facts,
                  "questions": ASSIST_QUESTIONS, "policy": ASSIST_POLICY,
                  "forbidden": list(ASSIST_QUESTIONS["tool"]["criteria"])},
}


def state_of(case, text):
    if case["workload"] == "support":
        return {"channel": case["channel"], "message": text, "device": case["device"]}
    return {"utterance": text, "context": case["context"]}


def record_of(case, text, with_policy=False):
    """Kev training/eval record. with_policy appends the written policy to every question (the prompt-only baseline)."""
    w = WORKLOADS[case["workload"]]
    labels = w["labels"](case)
    questions = {}
    for qid, q in w["questions"].items():
        q = {k: v for k, v in q.items()}
        if with_policy:
            q["instructions"] = f"{q['instructions']} {w['policy']}"
        q["label"] = labels[qid]
        questions[qid] = q
    return {"state": state_of(case, text), "questions": questions}


def rng_for(seed, index):
    return random.Random(seed * 1_000_003 + index)
