# Continual-Learning Skill — Live Demo

> Generated using the `continual-learning` skill from
> [microsoft/skills](https://github.com/microsoft/skills/tree/main/.github/skills/continual-learning).

## What was produced

A `.copilot-memory/learnings.md` file ([learnings.md](learnings.md)) that captures the
hard-won lessons from this entire Azure Agent Skills evaluation + slide-generation effort,
in the format the `continual-learning` skill specifies (project-local, version-controlled,
human-readable). When a coding agent (Copilot CLI, Claude Code) opens this repo, the
hook surfaces these learnings at session start so the agent doesn't re-learn the same lessons.

## Reproducible prompt

> ```
> Using the continual-learning skill, extract lessons learned from this evaluation
> session and write them as a project-local learnings.md file.
>
> Requirements per the skill:
>   1. Two-tier memory: write to LOCAL (.copilot-memory/) — these are repo-specific.
>   2. Categories: pattern | mistake | preference | tool_insight
>   3. Be SPECIFIC: "Use scope='ai.azure.com/.default' for Foundry auth" not "use right scope"
>   4. Each learning has: category, source (user_correction/observed/auto), content
>   5. Compact format — agent can scan quickly at session start
>
> Output: skill-demos/continual-learning/learnings.md
> ```

## Skill guidance enforced

| Skill rule | Where applied |
|------------|---------------|
| "One step to install" | This file is just `.copilot-memory/learnings.md` — agent picks it up automatically |
| "Scope correctly — local for project conventions" | All entries are repo-specific (Azure MCP, Foundry, this evaluation) |
| "Be specific" | Each lesson has exact tool name, parameter, or URL |
| Categories: pattern / mistake / preference / tool_insight | All 4 categories used |
| Compaction (60-day decay) | Each entry has `date` for the hook to reason about freshness |

## Source

- Skill: https://github.com/microsoft/skills/blob/main/.github/skills/continual-learning/SKILL.md
- Hook installer: https://github.com/microsoft/skills/tree/main/hooks/continual-learning
