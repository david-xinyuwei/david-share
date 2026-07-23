import { describe, expect, it } from "vitest";

import { assertMindMapSourceMatches, mindMapRichText } from "./mind-map-export";

describe("mind map rich-text export", () => {
  it("creates the indented icon outline used by meeting applications", () => {
    const payload = mindMapRichText({
      label: "微软2026愿景与承诺",
      children: [
        {
          label: "核心使命与信任",
          children: [
            {
              label: "建立可信技术",
              children: [
                { label: "信任与创新同等重要", children: [] },
                { label: "推动信任商业化", children: [] },
              ],
            },
          ],
        },
      ],
    });

    expect(payload.text).toBe(
      "微软2026愿景与承诺\n" +
        "\t🎯 核心使命与信任\n" +
        "\t\t🤝 建立可信技术\n" +
        "\t\t\t信任与创新同等重要\n" +
        "\t\t\t推动信任商业化",
    );
    expect(payload.html).toContain("margin-left:72px");
    expect(payload.html).toContain("🎯 核心使命与信任");
  });

  it("escapes model-provided labels before creating clipboard HTML", () => {
    const payload = mindMapRichText({
      label: "Research & Development <2026>",
      children: [],
    });

    expect(payload.text).toBe("Research & Development <2026>");
    expect(payload.html).toContain("Research &amp; Development &lt;2026&gt;");
  });

  it("requires the Mermaid source to contain the exact canonical tree", () => {
    const tree = {
      label: "Stargate Review",
      children: [
        {
          label: "Trust & controls",
          children: [{ label: "Human review before send", children: [] }],
        },
      ],
    };
    expect(() =>
      assertMindMapSourceMatches(
        tree,
        "mindmap\n  root((Stargate Review))\n    Trust & controls\n      Human review<br/>before send\n",
      ),
    ).not.toThrow();
    expect(() =>
      assertMindMapSourceMatches(
        tree,
        "mindmap\n  root((Stargate Review))\n    Trust & controls\n",
      ),
    ).toThrow("Mind map exports disagree");
  });
});
