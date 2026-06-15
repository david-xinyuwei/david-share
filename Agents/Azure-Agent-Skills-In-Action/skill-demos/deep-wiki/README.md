# deep-wiki Skill — Live Demo

> Generated using the `wiki-page-writer` skill from the
> [deep-wiki plugin](https://github.com/microsoft/skills/tree/main/.github/plugins/deep-wiki).

## What was produced

A sample wiki page ([`wiki-sample-page.md`](wiki-sample-page.md)) documenting our own evaluation pipeline,
following all deep-wiki mandatory requirements:

- ✅ 4 Mermaid diagrams (graph, sequence, flowchart) with dark-mode colors
- ✅ Every claim cites file:line with clickable GitHub links
- ✅ Tables with "Source" column
- ✅ Progressive disclosure: WHY → Architecture → Components → Data Flow
- ✅ VitePress-compatible frontmatter
- ✅ Related Pages section with bidirectional links

## Reproducible prompt

> ```
> Using the deep-wiki wiki-page-writer skill, generate a wiki page documenting
> the Azure MCP evaluation pipeline in this repo.
>
> Hard requirements per the skill:
>   1. Minimum 3-5 dark-mode Mermaid diagrams (fills #2d333b, borders #6d5dfc, text #e6edf3)
>   2. Use at least 2 different diagram types (graph, sequence, flowchart, etc.)
>   3. Every non-trivial claim needs a citation: [file:line](REPO_URL/blob/BRANCH/file#Lline)
>   4. Minimum 5 different source files cited
>   5. Tables with "Source" column for all component listings
>   6. Structure: Overview (WHY) → Architecture → Components → Data Flow → References
>   7. VitePress frontmatter (title + description)
>   8. Related Pages section at the end
>
> Source repo: https://github.com/david-xinyuwei/david-share
> Branch: master
> Target file: scripts/run_full_value_evaluation.js
> ```
