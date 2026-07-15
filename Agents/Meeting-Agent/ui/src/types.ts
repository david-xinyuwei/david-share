export type UiConfig = {
  mode: "aoai" | "foundry" | "local";
  agent_name: string;
  model_name: string | null;
  reasoning_effort: "medium" | null;
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

export type MeetingAnalysis = {
  title: string;
  summary: string;
  topics: string[];
  decisions: string[];
  action_items: ActionItem[];
  open_questions: string[];
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