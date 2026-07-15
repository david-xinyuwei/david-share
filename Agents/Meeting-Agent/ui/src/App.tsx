import {
  AlertCircle,
  CheckCircle2,
  Download,
  FileJson,
  FileText,
  MailOpen,
  Network,
  Presentation,
  RefreshCw,
  Sparkles,
  Upload,
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import { artifactUrl, createRun, getConfig, openOutlook } from "./api";
import { jsonlEvents, recipients, transcriptEvents } from "./input";
import type { MeetingRun, UiConfig } from "./types";

type InputMode = "transcript" | "provider";

export default function App() {
  const [config, setConfig] = useState<UiConfig | null>(null);
  const [mode, setMode] = useState<InputMode>("transcript");
  const [input, setInput] = useState("");
  const [recipientInput, setRecipientInput] = useState("");
  const [run, setRun] = useState<MeetingRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageKind, setMessageKind] = useState<"success" | "error">("success");

  useEffect(() => {
    getConfig().then(setConfig).catch((error: Error) => show(error.message, "error"));
  }, []);

  function show(value: string, kind: "success" | "error") {
    setMessage(value);
    setMessageKind(kind);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setBusy(true);
    try {
      const events = mode === "transcript" ? transcriptEvents(input) : jsonlEvents(input);
      const result = await createRun(events, recipients(recipientInput));
      setRun(result);
      show("Meeting artifacts are ready for review.", "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "The meeting request failed.", "error");
    } finally {
      setBusy(false);
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setMode("provider");
    setInput(await file.text());
    setRun(null);
    setMessage(null);
    event.target.value = "";
  }

  async function openDraft() {
    if (!run) return;
    try {
      await openOutlook(run);
      show("Draft opened in New Outlook. Review it and send manually.", "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "New Outlook could not be opened.", "error");
    }
  }

  function reset() {
    setInput("");
    setRecipientInput("");
    setRun(null);
    setMessage(null);
  }

  const mindMap = run ? artifactUrl(run, "mind_map_png") : null;
  const presentation = run ? artifactUrl(run, "presentation") : null;
  const eml = run ? artifactUrl(run, "eml") : null;
  const analysisJson = run ? artifactUrl(run, "analysis") : null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><Network size={19} /></span>
          <div>
            <h1>Meeting Agent</h1>
            <p>{config?.agent_name || "Connecting to agent"}</p>
          </div>
        </div>
        <div className={`runtime-badge ${config?.mode === "local" ? "test" : "live"}`}>
          <span aria-hidden="true" />
          {config?.mode === "local" ? "Offline contract test" : "Microsoft Foundry"}
        </div>
      </header>

      {config?.mode === "local" && (
        <div className="truth-banner" role="note">
          Offline contract mode validates integration and artifacts; it does not evaluate model quality.
        </div>
      )}

      {message && (
        <div className={`toast ${messageKind}`} role={messageKind === "error" ? "alert" : "status"}>
          {messageKind === "error" ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{message}</span>
        </div>
      )}

      <main className="workspace">
        <section className="input-panel" aria-labelledby="meeting-input-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Input</p>
              <h2 id="meeting-input-heading">Meeting evidence</h2>
            </div>
            <button className="icon-button" type="button" onClick={reset} title="Reset meeting">
              <RefreshCw size={17} />
              <span className="sr-only">Reset meeting</span>
            </button>
          </div>

          <form onSubmit={submit}>
            <div className="segmented" aria-label="Meeting input type">
              <button
                type="button"
                className={mode === "transcript" ? "selected" : ""}
                onClick={() => setMode("transcript")}
              >
                <FileText size={16} /> Transcript
              </button>
              <button
                type="button"
                className={mode === "provider" ? "selected" : ""}
                onClick={() => setMode("provider")}
              >
                <FileJson size={16} /> Provider JSONL
              </button>
            </div>

            <label htmlFor="meeting-input">
              {mode === "transcript" ? "Final transcript" : "Provider event stream"}
            </label>
            <textarea
              id="meeting-input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={
                mode === "transcript"
                  ? "Paste finalized meeting transcript segments..."
                  : '{"event_id":"...","kind":"transcript.final",...}'
              }
              spellCheck={mode === "transcript"}
              required
            />

            <div className="upload-row">
              <label className="secondary-button" htmlFor="jsonl-upload">
                <Upload size={16} /> Upload JSONL
              </label>
              <input id="jsonl-upload" className="file-input" type="file" accept=".jsonl,text/plain" onChange={upload} />
              <span>{input ? `${input.length.toLocaleString()} characters` : "No input loaded"}</span>
            </div>

            <label htmlFor="recipients">Draft recipients</label>
            <input
              id="recipients"
              type="text"
              value={recipientInput}
              onChange={(event) => setRecipientInput(event.target.value)}
              placeholder="name@example.com; another@example.com"
              autoComplete="off"
            />

            <button className="primary-button" type="submit" disabled={busy || !input.trim()}>
              <Sparkles size={17} />
              {busy ? "Agent request in progress" : "Generate meeting package"}
            </button>
          </form>
        </section>

        <section className="result-panel" aria-live="polite">
          {!run ? (
            <div className="empty-state">
              <span aria-hidden="true"><Sparkles size={30} /></span>
              <h2>Meeting package</h2>
              <p>Summary, decisions, actions, mind map, PowerPoint, and draft will appear here.</p>
            </div>
          ) : (
            <>
              <div className="result-heading">
                <div>
                  <p className="eyebrow">Analysis</p>
                  <h2>{run.analysis.title}</h2>
                </div>
                <span className="run-id">Run {run.run_id.slice(0, 10)}</span>
              </div>

              {mindMap && (
                <figure className="mind-map">
                  <img src={mindMap} alt={`Mind map for ${run.analysis.title}`} />
                </figure>
              )}

              <p className="summary">{run.analysis.summary}</p>

              <div className="analysis-grid">
                <ResultList title="Decisions" items={run.analysis.decisions} />
                <ResultList
                  title="Action items"
                  items={run.analysis.action_items.map((item) =>
                    [item.description, item.owner, item.due].filter(Boolean).join(" · "),
                  )}
                />
                <ResultList title="Topics" items={run.analysis.topics} />
                <ResultList title="Open questions" items={run.analysis.open_questions} />
              </div>

              <div className="artifact-bar">
                {presentation && <ArtifactLink href={presentation} icon={<Presentation size={17} />} label="PowerPoint" />}
                {eml && <ArtifactLink href={eml} icon={<MailOpen size={17} />} label="EML draft" />}
                {analysisJson && <ArtifactLink href={analysisJson} icon={<FileJson size={17} />} label="Analysis JSON" />}
                <button className="outlook-button" type="button" onClick={openDraft} disabled={!config?.outlook_available}>
                  <MailOpen size={17} /> Open Outlook draft
                </button>
              </div>

              <div className="manual-send-boundary">
                <CheckCircle2 size={17} />
                <span>Draft only. New Outlook requires a human review and manual send.</span>
              </div>
            </>
          )}
        </section>
      </main>

    </div>
  );
}

function ResultList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="result-list">
      <h3>{title}</h3>
      {items.length ? (
        <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
      ) : (
        <p>None recorded</p>
      )}
    </section>
  );
}

function ArtifactLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  return (
    <a className="artifact-link" href={href} download>
      {icon}<span>{label}</span><Download size={15} />
    </a>
  );
}