# Repository Instructions

- Keep the runtime truthful: unavailable external services must return explicit errors, never mock data or synthetic success.
- Keep Windows device actions local. Do not describe local tool execution as a cloud-side Voice Live capability.
- Never commit `.env`, token caches, resource identifiers, account data, raw runtime logs, camera frames, or generated user content.
- Any new visible capability must update `scenario-manifest.json`, both READMEs, deterministic tests, and sanitized evidence where applicable.
- CI must remain side-effect free: no Azure calls, microphone/camera access, email delivery, wallpaper changes, or power mutations.
- Run `python scripts/pre_delivery_check.py` and `python -m pytest` before proposing a change.
