const $ = (id) => document.getElementById(id);
const TARGETS = {
  "zh-Hans": "Simplified Chinese",
  "zh-Hant": "Traditional Chinese",
  ja: "Japanese",
  ko: "Korean",
  fr: "French",
  de: "German",
  es: "Spanish",
};

const run = {
  kind: "",
  startedAt: 0,
  timer: null,
  rows: [],
  lanes: new Map(),
  processOrder: [],
  stageCount: 0,
  handoff: null,
  sampleSize: 0,
  target: "",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function shortId(value, length = 10) {
  const text = String(value || "");
  if (!text) return "–";
  if (text.length <= length + 5) return text;
  return `${text.slice(0, length)}…${text.slice(-4)}`;
}

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  window.setTimeout(() => node.classList.remove("show"), 3200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (response.status === 401) {
    showAuth();
    throw new Error(t("Authentication required"));
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return data;
}

async function streamCall(path, payload, onEvent) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (response.status === 401) {
    showAuth();
    throw new Error(t("Authentication required"));
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data));
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const line = block.split("\n").find((entry) => entry.startsWith("data:"));
      if (!line) continue;
      let event;
      try {
        event = JSON.parse(line.slice(5).trim());
      } catch {
        continue;
      }
      if (event.kind === "error") throw new Error(event.message);
      if (event.kind === "done") result = event.result;
      else onEvent(event);
    }
  }
  if (!result) throw new Error(t("Stream ended before a result arrived"));
  return result;
}

function showAuth() {
  $("appView").classList.add("hidden");
  $("authView").classList.remove("hidden");
}

function showApp() {
  $("authView").classList.add("hidden");
  $("appView").classList.remove("hidden");
  refreshIcons();
}

function setBusy(busy) {
  ["safeButton", "faultButton", "detachButton", "approvalButton", "steeringButton"]
    .forEach((id) => { $(id).disabled = busy; });
}

function elapsed() {
  return ((performance.now() - run.startedAt) / 1000).toFixed(1);
}

function stopClock() {
  if (run.timer) {
    window.clearInterval(run.timer);
    run.timer = null;
  }
  if (run.startedAt) $("runClock").textContent = `${elapsed()}s`;
}

function startClock(offset = 0) {
  stopClock();
  run.startedAt = performance.now() - Number(offset || 0) * 1000;
  $("runClock").textContent = `${elapsed()}s`;
  run.timer = window.setInterval(() => { $("runClock").textContent = `${elapsed()}s`; }, 100);
}

function setCheck(name, verdict) {
  const node = document.querySelector(`[data-check="${name}"]`);
  if (!node) return;
  node.classList.remove("pass", "fail", "na");
  if (verdict !== "idle") node.classList.add(verdict);
  const icon = node.querySelector("[data-lucide]");
  if (icon) icon.setAttribute("data-lucide", verdict === "pass" ? "check-circle-2" : verdict === "fail" ? "x-circle" : verdict === "na" ? "minus-circle" : "circle");
  refreshIcons();
}

function resetRun(kind, title) {
  stopClock();
  run.kind = kind;
  run.rows = [];
  run.lanes = new Map();
  run.processOrder = [];
  run.stageCount = 0;
  run.handoff = null;
  run.sampleSize = 0;
  run.target = "";
  ["started", "checkpoint", "interrupted", "recovered", "continued", "completed"]
    .forEach((name) => setCheck(name, "idle"));
  if (kind === "safe") ["interrupted", "recovered"].forEach((name) => setCheck(name, "na"));
  if (kind === "detach") setCheck("recovered", "na");
  $("runType").textContent = t("Live run");
  $("runTitle").textContent = title;
  $("runPhase").textContent = t("starting");
  $("runStatus").textContent = t("Starting the live run…");
  $("decisionPanel").classList.add("hidden");
  $("evidenceView").innerHTML = `<div class="evidence-empty">${escapeHtml(t("Waiting for the first committed section…"))}</div>`;
  $("timeline").innerHTML = "";
  $("runPanel").classList.remove("hidden");
  startClock();
  $("runPanel").scrollIntoView({ behavior: "smooth", block: "start" });
}

function addTimeline(kind, label, detail = "") {
  run.rows.push({ kind, label, detail, at: elapsed() });
  $("timeline").innerHTML = run.rows.map((row) => `
    <div class="timeline-row ${escapeHtml(row.kind)}">
      <span class="timeline-time">+${escapeHtml(row.at)}s</span>
      <div><strong>${escapeHtml(row.label)}</strong><span>${escapeHtml(row.detail)}</span></div>
    </div>`).join("");
  $("timeline").scrollTop = $("timeline").scrollHeight;
}

function processOrdinal(process) {
  if (!process) return -1;
  if (!run.processOrder.includes(process)) run.processOrder.push(process);
  return run.processOrder.indexOf(process);
}

function laneName(ordinal) {
  return t("Process {n}", { n: String.fromCharCode(65 + Math.max(0, ordinal)) });
}

function addSection(laneKey, section, meta = {}) {
  const lane = run.lanes.get(laneKey) || { title: laneKey, sections: [], ...meta };
  Object.assign(lane, meta);
  if (!lane.sections.some((item) => item.index === section.index)) {
    lane.sections.push(section);
    lane.sections.sort((left, right) => left.index - right.index);
  }
  run.lanes.set(laneKey, lane);
  renderLanes();
}

function renderLanes() {
  const lanes = [...run.lanes.values()];
  if (!lanes.length) {
    $("evidenceView").innerHTML = `<div class="evidence-empty">${escapeHtml(t("No committed sections yet."))}</div>`;
    return;
  }
  $("evidenceView").innerHTML = lanes.map((lane) => {
    const process = lane.process || lane.sections.find((item) => item.process_sha256)?.process_sha256 || "";
    const ordinal = processOrdinal(process);
    const total = lane.total || run.stageCount || "?";
    const items = lane.sections.map((item) => `
      <li>
        <span class="lane-index">${String((item.index ?? 0) + 1).padStart(2, "0")}</span>
        <div><span class="lane-source">${escapeHtml(item.source || "")}</span><span class="lane-text">${escapeHtml(item.text || "")}</span></div>
      </li>`).join("");
    return `<article class="lane">
      <header><div><h3>${escapeHtml(t(lane.title))}</h3><small>${escapeHtml(t("process {id}", { id: shortId(process, 9) }))}</small></div><span class="lane-mode">${escapeHtml(t(lane.mode || "fresh"))}</span></header>
      <ol class="lane-list">${items}</ol>
      <header><small>${lane.sections.length} / ${escapeHtml(total)} ${escapeHtml(t("Checkpoint committed"))}</small><small>${escapeHtml(laneName(ordinal))}</small></header>
    </article>`;
  }).join("");
  document.querySelectorAll(".lane-list").forEach((node) => { node.scrollTop = node.scrollHeight; });
}

function failRun(error) {
  stopClock();
  setCheck("completed", "fail");
  $("runPhase").textContent = t("run failed");
  $("runStatus").textContent = t("FAIL · {detail}", { detail: error.message });
  $("decisionPanel").classList.add("hidden");
  addTimeline("fault", "RUN_FAILED", error.message);
}

async function loadAgents() {
  const status = $("runtimeStatus");
  status.className = "runtime-status loading";
  status.innerHTML = `<i data-lucide="loader-circle"></i>${escapeHtml(t("Reading Foundry"))}`;
  refreshIcons();
  try {
    const payload = await api("/api/agents");
    const agents = payload.agents || [];
    if (payload.configured === false) {
      status.className = "runtime-status error";
      status.innerHTML = `<i data-lucide="info"></i>${escapeHtml(t("Foundry endpoint not configured"))}`;
      $("agentStrip").innerHTML = `<p class="agent-placeholder">${escapeHtml(t(payload.detail))}</p>`;
      refreshIcons();
      return;
    }
    $("agentStrip").innerHTML = agents.map((agent) => `
      <article class="agent-item">
        <header><strong>${escapeHtml(agent.name || "–")}</strong><span class="agent-state">${escapeHtml(agent.status || "active")}</span></header>
        <p>${escapeHtml(agent.label || t("Live Agent"))} · v${escapeHtml(agent.version || "?")} · ${escapeHtml(agent.runtime || agent.kind || "hosted")}</p>
      </article>`).join("");
    status.className = "runtime-status live";
    status.innerHTML = `<i data-lucide="circle-check"></i>${escapeHtml(t("Foundry returned {n} repository-owned Agents.", { n: agents.length }))}`;
  } catch (error) {
    status.className = "runtime-status error";
    status.innerHTML = `<i data-lucide="circle-x"></i>${escapeHtml(t("Agent status failed"))}`;
    $("agentStrip").innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  }
  refreshIcons();
}

function recoveryEvent(event) {
  if (event.kind === "created") {
    setCheck("started", "pass");
    addTimeline("created", "RESPONSE_CREATED", `store=true · background=true · ${shortId(event.response_id_sha256)}`);
  } else if (event.kind === "checkpoint") {
    run.stageCount = event.stage_count || run.stageCount;
    const key = `process-${event.process_ordinal ?? 0}`;
    addSection(key, event, {
      title: t("Process {n}", { n: String.fromCharCode(65 + (event.process_ordinal ?? 0)) }),
      process: event.process_sha256,
      mode: event.entry_mode,
      total: run.stageCount,
    });
    const done = [...run.lanes.values()].reduce((total, lane) => total + lane.sections.length, 0);
    setCheck("checkpoint", "pass");
    if (done > 1) setCheck("continued", "pass");
    $("runStatus").textContent = t("section {done}/{total} committed", { done, total: run.stageCount || "?" });
  } else if (event.kind === "fault_window") {
    setCheck("interrupted", "pass");
    $("runPhase").textContent = t("waiting for replacement compute");
    addTimeline("fault", "STREAM_CLOSED", t("Process A became unreachable"));
  } else if (event.kind === "waiting") {
    $("runStatus").textContent = t(event.detail || "waiting for replacement compute");
  } else if (event.kind === "recovered") {
    setCheck("recovered", "pass");
    $("runPhase").textContent = t("Process B entered as recovered");
    addTimeline("recovered", "HANDLER_RECOVERED", `resume_from=${event.resume_from || "?"}`);
  } else if (event.kind === "detached") {
    setCheck("interrupted", "pass");
    $("runPhase").textContent = t("caller disconnected for {s}s", { s: event.seconds });
    addTimeline("fault", "CALLER_DETACHED", `${event.sections_before_detach} sections`);
  } else if (event.kind === "reattached") {
    $("runPhase").textContent = t("caller reattached to the original response");
    addTimeline("recovered", "CALLER_REATTACHED", "same response");
  }
}

async function runRecovery(kind) {
  const titles = { safe: "Safe baseline", fault: "Hard process loss", detach: "Observer disconnect" };
  resetRun(kind, t(titles[kind]));
  setBusy(true);
  try {
    const mode = kind === "detach" ? "detach" : "crash";
    const result = await streamCall(
      "/api/run",
      {
        mode,
        inject: kind === "fault",
        crash_after_stage: 3,
        stage_delay_ms: 300,
        detach_after_sections: 3,
        detach_seconds: 8,
      },
      recoveryEvent,
    );
    run.stageCount = result.stage_count;
    setCheck("continued", result.checkpoints_ordered_once ? "pass" : "fail");
    setCheck("completed", result.acceptance?.passed ? "pass" : "fail");
    if (kind === "fault") {
      setCheck("recovered", result.recovery_proven ? "pass" : "fail");
    }
    stopClock();
    $("runPhase").textContent = result.status === "completed" ? t("completed") : result.status;
    $("runStatus").textContent = result.acceptance?.passed
      ? t("PASS in {s}s", { s: result.elapsed_seconds })
      : t("FAIL · {detail}", { detail: result.acceptance?.verdict || result.status });
    addTimeline(result.acceptance?.passed ? "done" : "fault", "TERMINAL_ACCEPTANCE", `${result.status} · ${result.process_count} process(es) · ${result.stage_count} checkpoints`);
    renderLanes();
  } catch (error) {
    failRun(error);
  } finally {
    setBusy(false);
  }
}

function steeringEvent(event) {
  if (event.kind === "scenario_started") {
    setCheck("started", "pass");
    addTimeline("created", "SCENARIO_STARTED", `${event.agent} v${event.version}`);
  } else if (event.kind === "objective_started") {
    const title = event.lane === "original" ? "Original target" : "New target";
    const lane = run.lanes.get(event.lane) || { title, sections: [] };
    lane.target = event.target;
    run.lanes.set(event.lane, lane);
    addTimeline("created", event.lane === "original" ? "LANGUAGE_A_STARTED" : "LANGUAGE_B_STARTED", TARGETS[event.target]);
    renderLanes();
  } else if (event.kind === "entry") {
    const lane = run.lanes.get(event.lane) || { title: event.lane === "original" ? "Original target" : "New target", sections: [] };
    lane.mode = event.entry_mode;
    lane.process = event.process_sha256;
    run.lanes.set(event.lane, lane);
    renderLanes();
  } else if (event.kind === "checkpoint") {
    run.stageCount = event.stage_count || run.stageCount;
    addSection(event.lane, event, {
      title: event.lane === "original" ? "Original target" : "New target",
      mode: event.entry_mode,
      process: event.process_sha256,
      total: run.stageCount,
    });
    setCheck("checkpoint", "pass");
    if (event.entry_mode === "recovered" || event.entry_mode === "steered") setCheck("continued", "pass");
    $("runStatus").textContent = t("section {done}/{total} committed", { done: event.index + 1, total: run.stageCount || "?" });
  } else if (event.kind === "process_lost") {
    setCheck("interrupted", "pass");
    addTimeline("fault", "PROCESS_LOST", `os._exit(86) · ${event.committed_sections} sections`);
  } else if (event.kind === "waiting") {
    $("runStatus").textContent = t(event.detail);
  } else if (event.kind === "recovered") {
    setCheck("recovered", "pass");
    addTimeline("recovered", "LANGUAGE_A_RECOVERED", `resume_from=${event.resume_from ?? "?"}`);
  } else if (event.kind === "steer_issued") {
    setCheck("continued", "pass");
    addTimeline("recovered", "DIRECTION_CHANGED", t("direction changed from {from} to {to}", { from: TARGETS[event.from_target], to: TARGETS[event.to_target] }));
  }
}

async function runSteering() {
  const original = $("steeringOriginalTarget").value;
  const replacement = $("steeringReplacementTarget").value;
  if (original === replacement) {
    toast(t("Choose two different languages so the change of mind is visible"));
    return;
  }
  resetRun("steering", t("Recovery + change of target"));
  setBusy(true);
  try {
    const result = await streamCall(
      "/api/steering",
      { original_target: original, replacement_target: replacement, steer_after_sections: 4, crash_after_stage: 9, stage_delay_ms: 300 },
      steeringEvent,
    );
    setCheck("completed", result.verdict === "PASS" ? "pass" : "fail");
    stopClock();
    $("runPhase").textContent = t("completed");
    $("runStatus").textContent = t("PASS in {s}s", { s: result.elapsed_seconds });
    addTimeline("done", "TERMINAL_ACCEPTANCE", `A=${result.original_status} (${result.original_sections}) · B=${result.replacement_status} (${result.replacement_sections}) · ${result.checkpoint_continuity}`);
  } catch (error) {
    failRun(error);
  } finally {
    setBusy(false);
  }
}

function approvalEvent(event) {
  if (event.kind === "scenario_started") {
    setCheck("started", "pass");
    run.target = event.target;
    run.sampleSize = event.sample_size;
    addTimeline("created", "SCENARIO_STARTED", `${event.agent} v${event.version} · ${TARGETS[event.target]}`);
  } else if (event.kind === "section") {
    run.stageCount = event.total_sections || run.stageCount;
    const laneKey = event.batch === "sample" ? "sample" : "remaining";
    addSection(laneKey, event, {
      title: event.batch === "sample" ? "Sample for review" : "Remaining after approval",
      mode: event.entry_mode,
      process: event.process_sha256,
      total: event.batch === "sample" ? run.sampleSize : Math.max(0, run.stageCount - run.sampleSize),
    });
    setCheck("checkpoint", "pass");
    if (event.batch !== "sample") setCheck("continued", "pass");
    $("runStatus").textContent = t("section {done}/{total} committed", { done: event.index + 1, total: run.stageCount || "?" });
  } else if (event.kind === "review_ready") {
    setCheck("checkpoint", "pass");
    run.stageCount = event.total_sections || run.stageCount;
    addTimeline("recovered", "AWAITING_REVIEW", t("review sample committed"));
  } else if (event.kind === "fault_armed") {
    addTimeline("fault", "FAULT_ARMED", event.detail);
  } else if (event.kind === "process_lost") {
    setCheck("interrupted", "pass");
    addTimeline("fault", "PROCESS_LOST", t("instance lost while approval was pending"));
  } else if (event.kind === "waiting") {
    $("runStatus").textContent = t(event.detail);
  } else if (event.kind === "recovered") {
    setCheck("recovered", "pass");
    addTimeline("recovered", "REPLACEMENT_READY", t("replacement instance is serving"));
  } else if (event.kind === "awaiting_human") {
    run.handoff = event;
    addTimeline("recovered", "YOUR_DECISION", t("waiting for your decision"));
  } else if (event.kind === "approval_submitted") {
    $("decisionPanel").classList.add("hidden");
    addTimeline("recovered", "APPROVAL_SUBMITTED", `${event.decision} · ${event.actor}`);
  }
}

function finishApproval(result) {
  setCheck("completed", result.verdict === "PASS" ? "pass" : "fail");
  stopClock();
  if (result.status === "rejected") {
    $("runPhase").textContent = t("completed");
    $("runStatus").textContent = t("sample rejected; remaining work did not run");
    addTimeline("done", "TERMINAL_ACCEPTANCE", "rejected");
    return;
  }
  setCheck("continued", result.total_sections > result.sample_sections ? "pass" : "fail");
  $("runPhase").textContent = t("completed");
  $("runStatus").textContent = t("PASS in {s}s", { s: elapsed() });
  addTimeline("done", "TERMINAL_ACCEPTANCE", `${result.total_sections} sections · sample unchanged · Process B`);
}

async function runApproval() {
  resetRun("approval", t("Review gate + instance loss"));
  setBusy(true);
  try {
    const result = await streamCall(
      "/api/approval",
      { target: $("approvalTarget").value, sample_size: 10, stage_delay_ms: 300, auto_approve: $("autoApprove").checked, approver: "demo operator" },
      approvalEvent,
    );
    if (result.status === "awaiting_approval") {
      run.handoff = result;
      stopClock();
      $("runPhase").textContent = t("awaiting approval");
      $("runStatus").textContent = t("waiting for your decision");
      $("decisionPanel").classList.remove("hidden");
      $("decisionPanel").scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    finishApproval(result);
  } catch (error) {
    failRun(error);
  } finally {
    setBusy(false);
  }
}

async function decideApproval(decision) {
  if (!run.handoff) {
    toast(t("Run the approval scenario first"));
    return;
  }
  setBusy(true);
  $("approveButton").disabled = true;
  $("rejectButton").disabled = true;
  startClock(run.handoff.elapsed_seconds || 0);
  try {
    const result = await streamCall(
      "/api/approval/decide",
      {
        session_id: run.handoff.session_id,
        decision,
        approver: "demo operator",
        task_id_sha256: run.handoff.task_id_sha256,
        process_a_sha256: run.handoff.process_a_sha256,
        sample_hashes: run.handoff.sample_hashes || [],
      },
      approvalEvent,
    );
    finishApproval(result);
  } catch (error) {
    failRun(error);
  } finally {
    setBusy(false);
    $("approveButton").disabled = false;
    $("rejectButton").disabled = false;
  }
}

async function runValidator() {
  $("validatorButton").disabled = true;
  try {
    const result = await api("/api/validator-check", { method: "POST", body: "{}" });
    const passed = (result.cases || []).filter((item) => item.behaved).length;
    $("validatorResult").textContent = t("Checks behaved correctly: {passed}/{total}.", { passed, total: (result.cases || []).length });
  } catch (error) {
    $("validatorResult").textContent = `${t("Validator failed")}: ${error.message}`;
  } finally {
    $("validatorButton").disabled = false;
  }
}

function populateTargets() {
  for (const id of ["approvalTarget", "steeringOriginalTarget", "steeringReplacementTarget"]) {
    $(id).innerHTML = Object.entries(TARGETS).map(([code, name]) => `<option value="${code}">${escapeHtml(t(name))} (${code})</option>`).join("");
  }
  $("approvalTarget").value = "zh-Hans";
  $("steeringOriginalTarget").value = "zh-Hans";
  $("steeringReplacementTarget").value = "zh-Hant";
}

function bindEvents() {
  $("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("loginError").textContent = "";
    try {
      await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: $("username").value, password: $("password").value }),
      });
      showApp();
      await loadAgents();
    } catch (error) {
      $("loginError").textContent = error.message;
    }
  });
  $("logoutButton").addEventListener("click", async () => {
    await api("/auth/logout", { method: "POST", body: "{}" }).catch(() => {});
    const status = await api("/api/auth/status").catch(() => ({ auth_required: true }));
    if (status.auth_required) showAuth();
  });
  $("refreshButton").addEventListener("click", loadAgents);
  $("themeButton").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    window.localStorage.setItem("lra-demo.theme", next);
  });
  $("safeButton").addEventListener("click", () => runRecovery("safe"));
  $("faultButton").addEventListener("click", () => runRecovery("fault"));
  $("detachButton").addEventListener("click", () => runRecovery("detach"));
  $("approvalButton").addEventListener("click", runApproval);
  $("steeringButton").addEventListener("click", runSteering);
  $("approveButton").addEventListener("click", () => decideApproval("approve"));
  $("rejectButton").addEventListener("click", () => decideApproval("reject"));
  $("validatorButton").addEventListener("click", runValidator);
}

async function boot() {
  document.documentElement.dataset.theme = window.localStorage.getItem("lra-demo.theme") || "light";
  populateTargets();
  bindEvents();
  refreshIcons();
  try {
    const status = await api("/api/auth/status");
    if (!status.authenticated) {
      showAuth();
      return;
    }
    showApp();
    await loadAgents();
  } catch {
    showAuth();
  }
}

document.addEventListener("DOMContentLoaded", boot);
