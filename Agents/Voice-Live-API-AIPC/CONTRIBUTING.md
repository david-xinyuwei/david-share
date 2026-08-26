# Contributing

1. Create a branch from the latest `master`.
2. Keep credentials and customer data out of commits.
3. Preserve the Windows-local execution boundary for device tools.
4. Add or update deterministic tests for behavioral changes.
5. Run the public gates before opening a pull request:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\pre_delivery_check.py
.\.venv\Scripts\python.exe -m pytest
```

Live Azure, microphone, camera, desktop, power, wallpaper, and email checks are intentionally separate from CI because they require credentials or modify local state. State exactly which live checks you ran in the pull request.
