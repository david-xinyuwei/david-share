---
name: presentation-story
description: Convert evidence-grounded meeting analysis into a strict six-slide DeckPlan without choosing visual layout coordinates.
---

# Presentation Story Skill

## Responsibility

- Convert the meeting analysis into the `deck_plan` object required by the caller's schema.
- Use only facts already supported by the supplied meeting evidence.
- Decide the customer-facing story, information priority, slide titles, and content slots.
- Do not choose fonts, colors, coordinates, template shapes, or file-generation behavior.
- Match the dominant language of the meeting evidence.

## DeckPlan contract

Return exactly six typed sections in this order:

1. `cover`: a specific outcome-oriented title and concise subtitle.
2. `overview`: a 2-4 sentence executive summary covering context, outcome, and follow-up.
3. `topics`: 3-6 distinct topics when supported; never duplicate the summary sentence as filler.
4. `decisions_actions`: completed decisions plus action-oriented follow-ups; preserve explicit owner and due date only.
5. `mind_map`: a concise evidence-backed title for the renderer-supplied mind map.
6. `next_steps`: unresolved questions and one immediate next step when evidence supports it.

The object must satisfy the exact `DeckPlan` JSON Schema supplied by the caller. Do not add slide types, omit sections, or return Markdown.

## Writing quality

- Prefer concrete phrases over generic labels such as "Overview" or "Discussion."
- Keep one idea per topic, decision, action, or question.
- Keep individual strings below 140 characters where possible.
- Phrase decisions as completed choices, actions as verbs, and questions as unresolved asks.
- Do not repeat the same fact on multiple slides unless the repetition is necessary for the executive summary.
- Preserve uncertainty; do not turn proposals into decisions or infer owners and deadlines.

## Empty states

- Keep unsupported lists empty in `DeckPlan`; the deterministic deck contract controls presentation-safe empty-state text.
- Leave `next_step` null when the meeting contains no supported immediate follow-up.
- Never invent content merely to fill a slide.
