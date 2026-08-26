# Changelog

## 1.1.0 - 2026-08-26

- Convert runtime instructions, Vision and briefing prompts, and all model-facing tool schemas to English while preserving explicit response-language selection.
- Add an evidence-linked technology inventory and architecture for Voice Live, direct Azure OpenAI Realtime, Foundry Agent, WebIQ, Microsoft Graph, Azure OpenAI vision/image, public data providers, and Windows APIs.
- Use Azure Translator for the Chinese README update, followed by native Chinese editing, back-translation review, and deterministic bilingual parity checks.
- Add four evidence-linked scenario screenshots for medication recognition, Graph email receipt, volume control, and wallpaper change; each image uses scenario-specific cropping or irreversible pixel replacement to remove people, account identities, desktop metadata, and local paths.

## 1.0.1 - 2026-08-26

- Honor the user's explicit response-language selection and keep it active until the user explicitly changes languages.
- Add an English recording prompt and bilingual usage guidance.

## 1.0.0 - 2026-08-26

- Publish the Windows Voice Live AIPC application with 24 default local tools.
- Add Voice Live, Foundry Agent, and direct Azure OpenAI Realtime connection modes.
- Add camera perception, Windows device and power controls, live information, wallpaper, briefing, and allowlisted email workflows.
- Add sanitized runtime evidence, bilingual documentation, deterministic authenticity/security gates, Windows CI, and PyInstaller onedir packaging.
