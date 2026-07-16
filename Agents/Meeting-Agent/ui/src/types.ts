export type UiConfig = {
  mode: "aoai" | "local";
  agent_name: string;
  model_name: string | null;
  reasoning_effort: "medium" | null;
  authentication: "key" | null;
  outlook_available: boolean;
  automatic_send: false;
};

export type MeetingEvent = {
  event_id: string;
  session_id: string;
  sequence: number;
  timestamp: string;
  kind: "transcript.partial" | "transcript.final" | "visual.frame" | "meeting.end";
  text?: string | null;
  image_uri?: string | null;
  metadata: Record<string, unknown>;
};

export type ActionItem = {
  description: string;
  owner?: string | null;
  due?: string | null;
};

export type MindMapNode = {
  label: string;
  children: MindMapNode[];
};

export type MeetingAnalysis = {
  title: string;
  summary: string;
  topics: string[];
  decisions: string[];
  action_items: ActionItem[];
  open_questions: string[];
  mind_map: MindMapNode;
};

export type HostedArtifact = {
  path: string;
  bytes: number;
  sha256: string;
  media_type: string;
};

export type MeetingRun = {
  schema_version: 1;
  run_id: string;
  session_id: string;
  agent_session_id: string;
  invocation_id?: string | null;
  source_sha256: string;
  analysis: MeetingAnalysis;
  artifacts: Record<string, HostedArtifact>;
  automatic_send: false;
  next_state: "DRAFT_READY_MANUAL_SEND_REQUIRED";
};

export type ApiError = {
  error: string;
  message: string;
  details?: Array<{ path?: string; location?: string; message: string }>;
};

export type StreamAccepted = {
  run_id: string;
  session_id: string;
  agent_session_id: string;
  source_sha256: string;
  event_count: number;
};

export type RunStreamEvent =
  | { type: "accepted"; data: StreamAccepted }
  | { type: "analysis_started"; data: { run_id: string } }
  | { type: "model_delta"; data: { delta: string } }
  | {
      type: "analysis_ready";
      data: {
        analysis: MeetingAnalysis;
        mermaid: string;
        model_response_id: string | null;
      };
    }
  | { type: "mind_map_ready"; data: { artifacts: Record<string, HostedArtifact> } }
  | { type: "presentation_ready"; data: { artifact: HostedArtifact } }
  | { type: "complete"; data: { run: MeetingRun } }
  | { type: "error"; data: ApiError };