import {
  AlertCircle,
  CheckCircle2,
  Circle,
  ClipboardCopy,
  Download,
  FileCode2,
  FileJson,
  FileText,
  ImageDown,
  MailOpen,
  Network,
  LoaderCircle,
  Presentation,
  RefreshCw,
  Sparkles,
  Upload,
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

import {
  artifactUrlFor,
  createRunStream,
  getConfig,
  openOutlook,
} from "./api";
import { jsonlEvents, meetingRecordEvents, recipients, transcriptEvents } from "./input";
import {
  mindMapRichText,
} from "./mind-map-export";
import type {
  HostedArtifact,
  MeetingAnalysis,
  MeetingRun,
  RunStreamEvent,
  StreamAccepted,
  UiConfig,
} from "./types";

type InputMode = "meeting" | "provider" | "transcript";
type StreamStage =
  | "idle"
  | "accepted"
  | "analysis_started"
  | "analysis_ready"
  | "mind_map_ready"
  | "presentation_ready"
  | "complete";

export default function App() {
  const [config, setConfig] = useState<UiConfig | null>(null);
  const [mode, setMode] = useState<InputMode>("transcript");
  const [input, setInput] = useState("");
  const [recipientInput, setRecipientInput] = useState("");
  const [run, setRun] = useState<MeetingRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageKind, setMessageKind] = useState<"success" | "error">("success");
  const [streamStage, setStreamStage] = useState<StreamStage>("idle");
  const [streamText, setStreamText] = useState("");
  const [streamMeta, setStreamMeta] = useState<StreamAccepted | null>(null);
  const [streamAnalysis, setStreamAnalysis] = useState<MeetingAnalysis | null>(null);
  const [streamArtifacts, setStreamArtifacts] = useState<Record<string, HostedArtifact>>({});
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => {
    getConfig().then(setConfig).catch((error: Error) => show(error.message, "error"));
  }, []);

  function show(value: string, kind: "success" | "error") {
    setMessage(value);
    setMessageKind(kind);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const controller = new AbortController();
    activeRequest.current = controller;
    setMessage(null);
    setStreamStage("idle");
    setStreamText("");
    setStreamMeta(null);
    setStreamAnalysis(null);
    setStreamArtifacts({});
    setBusy(true);
    try {
      const events =
        mode === "transcript"
          ? transcriptEvents(input)
          : mode === "meeting"
            ? meetingRecordEvents(input)
            : jsonlEvents(input);
      const result = await createRunStream(
        events,
        recipients(recipientInput),
        handleStreamEvent,
        controller.signal,
      );
      setRun(result);
      show("Meeting artifacts are ready for review.", "success");
    } catch (error) {
      show(error instanceof Error ? error.message : "The meeting request failed.", "error");
    } finally {
      if (activeRequest.current === controller) {
        activeRequest.current = null;
        setBusy(false);
      }
    }
  }

  function handleStreamEvent(event: RunStreamEvent) {
    switch (event.type) {
      case "accepted":
        setRun(null);
        setStreamMeta(event.data);
        setStreamStage("accepted");
        break;
      case "analysis_started":
        setStreamStage("analysis_started");
        break;
      case "model_delta":
        setStreamText((value) => value + event.data.delta);
        break;
      case "analysis_ready":
        setStreamAnalysis(event.data.analysis);
        setStreamStage("analysis_ready");
        break;
      case "mind_map_ready":
        setStreamArtifacts((value) => ({ ...value, ...event.data.artifacts }));
        setStreamStage("mind_map_ready");
        break;
      case "presentation_ready":
        setStreamArtifacts((value) => ({ ...value, presentation: event.data.artifact }));
        setStreamStage("presentation_ready");
        break;
      case "complete":
        setRun(event.data.run);
        setStreamAnalysis(event.data.run.analysis);
        setStreamArtifacts(event.data.run.artifacts);
        setStreamStage("complete");
        break;
      case "error":
        break;
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setMode(file.name.toLowerCase().endsWith(".json") ? "meeting" : "provider");
    setInput(await file.text());
    activeRequest.current?.abort();
    setRun(null);
    setStreamStage("idle");
    setStreamText("");
    setStreamMeta(null);
    setStreamAnalysis(null);
    setStreamArtifacts({});
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

  async function copyMindMap() {
    if (!activeAnalysis) return;
    const payload = mindMapRichText(activeAnalysis.mind_map);
    try {
      if (navigator.clipboard.write && typeof ClipboardItem !== "undefined") {
        await navigator.clipboard.write([
          new ClipboardItem({
            "text/html": new Blob([payload.html], { type: "text/html" }),
            "text/plain": new Blob([payload.text], { type: "text/plain" }),
          }),
        ]);
      } else {
        await navigator.clipboard.writeText(payload.text);
      }
      show("Mind map rich text copied to the clipboard.", "success");
    } catch {
      show("The browser could not copy the mind map to the clipboard.", "error");
    }
  }

  function reset() {
    activeRequest.current?.abort();
    activeRequest.current = null;
    setInput("");
    setRecipientInput("");
    setRun(null);
    setBusy(false);
    setStreamStage("idle");
    setStreamText("");
    setStreamMeta(null);
    setStreamAnalysis(null);
    setStreamArtifacts({});
    setMessage(null);
  }

  const activeAnalysis = run?.analysis || streamAnalysis;
  const activeMeta = run
    ? {
        run_id: run.run_id,
        session_id: run.session_id,
        agent_session_id: run.agent_session_id,
        source_sha256: run.source_sha256,
        event_count: 0,
      }
    : streamMeta;
  const activeArtifacts = run?.artifacts || streamArtifacts;
  const artifact = (name: string) => {
    const item = activeArtifacts[name];
    return activeMeta && item ? artifactUrlFor(activeMeta.agent_session_id, item) : null;
  };
  const mindMap = artifact("mind_map_png");
  const mindMapMermaid = artifact("mind_map_mermaid");
  const presentation = artifact("presentation");
  const eml = artifact("eml");
  const analysisJson = artifact("analysis");

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><Network size={19} /></span>
          <div>
            <h1>Meeting Agent</h1>
            <p>
              {config
                ? `${config.model_name} · reasoning ${config.reasoning_effort} · ${config.authentication} auth`
                : "Connecting"}
            </p>
          </div>
        </div>
        <div className="runtime-badge live">
          <span aria-hidden="true" />
          {!config
            ? "Connecting"
            : "Azure OpenAI Responses API"}
        </div>
      </header>

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
                <FileText size={16} /> Transcript TXT
              </button>
              <button
                type="button"
                className={mode === "provider" ? "selected" : ""}
                onClick={() => setMode("provider")}
              >
                <FileJson size={16} /> ASR JSONL
              </button>
              <button
                type="button"
                className={mode === "meeting" ? "selected" : ""}
                onClick={() => setMode("meeting")}
              >
                <FileJson size={16} /> Meeting JSON
              </button>
            </div>

            <label htmlFor="meeting-input">
              {mode === "transcript"
                ? "Final transcript"
                : mode === "meeting"
                  ? "Structured meeting record"
                  : "Normalized ASR event stream"}
            </label>
            <textarea
              id="meeting-input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={
                mode === "transcript"
                  ? "Paste finalized meeting transcript segments..."
                  : mode === "meeting"
                    ? '{"meeting":{"id":"..."},"transcript":[...]}'
                    : '{"event_id":"...","kind":"transcript.final",...}'
              }
              spellCheck={mode === "transcript"}
              required
            />

            <div className="upload-row">
              <label className="secondary-button" htmlFor="jsonl-upload">
                <Upload size={16} /> Upload JSON / JSONL
              </label>
              <input id="jsonl-upload" className="file-input" type="file" accept=".json,.jsonl,application/json,text/plain" onChange={upload} />
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
              {busy ? (
                <LoaderCircle className="stream-spinner" size={17} />
              ) : (
                <Sparkles size={17} />
              )}
              {busy ? "Agent request in progress" : "Generate meeting package"}
            </button>
          </form>
        </section>

        <section className="result-panel" aria-live="polite">
          {!activeAnalysis && !busy && !activeMeta ? (
            <div className="empty-state">
              <span aria-hidden="true"><Sparkles size={30} /></span>
              <h2>Meeting package</h2>
              <p>Summary, decisions, actions, mind map, PowerPoint, and draft will appear here.</p>
            </div>
          ) : (
            <>
              {streamStage !== "idle" && (
                <StreamProgress stage={streamStage} output={streamText} />
              )}

              {activeAnalysis && (
                <>
                  <div className="result-heading">
                    <div>
                      <p className="eyebrow">Analysis</p>
                      <h2>{activeAnalysis.title}</h2>
                    </div>
                    {activeMeta && (
                      <span className="run-id">Run {activeMeta.run_id.slice(0, 10)}</span>
                    )}
                  </div>

                  {mindMap && (
                    <figure className="mind-map">
                      <img src={mindMap} alt={`Mind map for ${activeAnalysis.title}`} />
                    </figure>
                  )}

                  {mindMap && (
                    <div className="mind-map-actions" aria-label="Mind map exports">
                      <button
                        className="mind-map-action"
                        type="button"
                        onClick={copyMindMap}
                        title="Copy an indented rich-text outline"
                      >
                        <ClipboardCopy size={17} /> Copy rich text
                      </button>
                      <a
                        className="mind-map-action"
                        href={mindMap}
                        download="meeting-mind-map.png"
                        title="Save the displayed card-layout mind map as a PNG image"
                      >
                        <ImageDown size={17} /> Save PNG
                      </a>
                      {mindMapMermaid && (
                        <a
                          className="mind-map-action"
                          href={mindMapMermaid}
                          download="meeting-mind-map.mmd"
                          title="Download the renderer-neutral Mermaid source"
                        >
                          <FileCode2 size={17} /> Mermaid source
                        </a>
                      )}
                    </div>
                  )}

                  <p className="summary">{activeAnalysis.summary}</p>

                  <div className="analysis-grid">
                    <ResultList title="Decisions" items={activeAnalysis.decisions} />
                    <ResultList
                      title="Action items"
                      items={activeAnalysis.action_items.map((item) =>
                        [item.description, item.owner, item.due].filter(Boolean).join(" · "),
                      )}
                    />
                    <ResultList title="Topics" items={activeAnalysis.topics} />
                    <ResultList title="Open questions" items={activeAnalysis.open_questions} />
                  </div>

                  <div className="artifact-bar">
                    {presentation && <ArtifactLink href={presentation} icon={<Presentation size={17} />} label="PowerPoint" />}
                    {eml && <ArtifactLink href={eml} icon={<MailOpen size={17} />} label="EML draft" />}
                    {analysisJson && <ArtifactLink href={analysisJson} icon={<FileJson size={17} />} label="Analysis JSON" />}
                    {run && (
                      <button className="outlook-button" type="button" onClick={openDraft} disabled={!config?.outlook_available}>
                        <MailOpen size={17} /> Open Outlook draft
                      </button>
                    )}
                  </div>

                  <div className="manual-send-boundary">
                    <CheckCircle2 size={17} />
                    <span>Draft only. New Outlook requires a human review and manual send.</span>
                  </div>
                </>
              )}
            </>
          )}
        </section>
      </main>

    </div>
  );
}

const STREAM_STEPS = [
  "Input validated and run created",
  "GPT-5.4 structured response streaming",
  "Structured analysis ready",
  "Mind map files ready",
  "PowerPoint ready",
  "Draft and evidence ready",
] as const;

const COMPLETED_STEP: Record<StreamStage, number> = {
  idle: -1,
  accepted: 0,
  analysis_started: 0,
  analysis_ready: 2,
  mind_map_ready: 3,
  presentation_ready: 4,
  complete: 5,
};

const ACTIVE_STEP: Partial<Record<StreamStage, number>> = {
  accepted: 1,
  analysis_started: 1,
  analysis_ready: 3,
  mind_map_ready: 4,
  presentation_ready: 5,
};

function StreamProgress({ stage, output }: { stage: StreamStage; output: string }) {
  const completed = COMPLETED_STEP[stage];
  const active = ACTIVE_STEP[stage];
  const finished = stage === "complete";
  return (
    <section className="stream-progress" data-stream-stage={stage} aria-label="Generation progress">
      <div className="stream-progress-heading">
        {finished ? (
          <CheckCircle2 size={20} aria-hidden="true" />
        ) : (
          <LoaderCircle className="stream-spinner" size={20} aria-hidden="true" />
        )}
        <div>
          <p className="eyebrow">Generation trace</p>
          <h2>{finished ? "Meeting package completed" : "Building the meeting package"}</h2>
        </div>
      </div>
      <ol className="stream-steps">
        {STREAM_STEPS.map((label, index) => {
          const done = index <= completed;
          const current = index === active;
          return (
            <li key={label} className={done ? "done" : current ? "active" : "pending"}>
              {done ? (
                <CheckCircle2 size={16} aria-hidden="true" />
              ) : current ? (
                <LoaderCircle className="stream-spinner" size={16} aria-hidden="true" />
              ) : (
                <Circle size={16} aria-hidden="true" />
              )}
              <span>{label}</span>
            </li>
          );
        })}
      </ol>
      {(stage === "analysis_started" || output) && (
        <div className="stream-output">
          <div className="stream-output-label">GPT-5.4 output stream</div>
          <pre>{output || "Waiting for the first model token..."}</pre>
        </div>
      )}
    </section>
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