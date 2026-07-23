import type { MindMapNode } from "./types";

const PRIMARY_ICONS = ["🎯", "🏘️", "🌍", "⚖️", "🤖", "🚀"];
const SECONDARY_ICONS = ["🤝", "📋", "🛡️", "🛰️", "🏛️", "🔒", "💡", "💼", "🛠️", "🌐"];

export type MindMapClipboardPayload = {
  text: string;
  html: string;
};

export function mindMapRichText(root: MindMapNode): MindMapClipboardPayload {
  const lines: string[] = [];
  const html: string[] = [];
  appendNode(root, 0, 0, lines, html);
  return {
    text: lines.join("\n"),
    html: `<div>${html.join("")}</div>`,
  };
}

export function assertMindMapSourceMatches(
  root: MindMapNode,
  definition: string,
): void {
  const expected = flattenLabels(root).map(normalizeMermaidLabel);
  const actual = definition
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/^root\(\((.*)\)\)$/, "$1"))
    .map((line) => line.replaceAll("<br/>", " "));
  if (actual.length !== expected.length || actual.some((label, index) => label !== expected[index])) {
    throw new Error(
      `Mind map exports disagree: tree=${expected.length} nodes, Mermaid=${actual.length} nodes.`,
    );
  }
}

function flattenLabels(root: MindMapNode): string[] {
  return [root.label, ...root.children.flatMap(flattenLabels)];
}

function normalizeMermaidLabel(value: string): string {
  return value.replace(/[()[\]{}"`]/g, "").replace(/\s+/g, " ").trim() || "Meeting";
}

function appendNode(
  node: MindMapNode,
  depth: number,
  siblingIndex: number,
  lines: string[],
  html: string[],
): void {
  const icon = node.children.length ? iconFor(depth, siblingIndex) : "";
  const prefix = `${"\t".repeat(depth)}${icon ? `${icon} ` : ""}`;
  lines.push(`${prefix}${node.label}`);

  const weight = depth <= 2 && node.children.length ? "font-weight:600;" : "";
  html.push(
    `<div style="margin-left:${depth * 24}px;${weight}">` +
      `${icon ? `${icon} ` : ""}${escapeHtml(node.label)}</div>`,
  );
  node.children.forEach((child, index) => appendNode(child, depth + 1, index, lines, html));
}

function iconFor(depth: number, siblingIndex: number): string {
  if (depth === 1) return PRIMARY_ICONS[siblingIndex % PRIMARY_ICONS.length];
  if (depth >= 2) return SECONDARY_ICONS[siblingIndex % SECONDARY_ICONS.length];
  return "";
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
