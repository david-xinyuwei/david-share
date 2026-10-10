#!/usr/bin/env python3
"""Reference client: how a platform API reads GPU hours from Log Analytics.

    python examples/gpu_hours_client.py --credentials gpu-hours.query.env --view per_vm \
        --start 2026-10-01T00:00:00+08:00 --end 2026-10-02T00:00:00+08:00 [--idle-pct 5] [--tz-offset 8] [--computer <vm>]
    python examples/gpu_hours_client.py --workspace <workspace-guid> --view per_vm --start ... --end ...

Each of the eight views is one file in kql/. The query window is passed as the query timespan, never edited into
the KQL; the `let` defaults at the top of a file (IdlePct, TzOffset, Computers) can be overridden.
Sign-in: with --credentials, the app registration written by scripts/create-query-identity.sh
(AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, WORKSPACE_GUID) through ClientSecretCredential;
without it, DefaultAzureCredential: the AZURE_* environment variables, a managed identity where the platform
runs, or the Azure CLI login on a workstation. The identity needs "Log Analytics Reader" on the workspace.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

KQL_DIR = Path(__file__).resolve().parents[1] / "kql"
VIEWS = ("summary", "per_vm", "per_hour", "per_day", "per_user", "per_job", "per_submitter", "live")
_LET = {
    "IdlePct": (re.compile(r"^let IdlePct = \d+;", re.M), lambda v: f"let IdlePct = {int(v)};"),
    "TzOffset": (re.compile(r"^let TzOffset = -?\d+h;", re.M), lambda v: f"let TzOffset = {int(v)}h;"),
    "Computers": (re.compile(r"^let Computers = dynamic\(\[[^\]]*\]\);", re.M),
                  lambda v: "let Computers = dynamic(" + json.dumps(list(v)) + ");"),
}


def build_query(view: str, idle_pct: int | None = None, tz_offset_hours: int | None = None,
                computers: list[str] | None = None) -> str:
    """Return the KQL of a view with the requested `let` defaults replaced (fail closed)."""
    if view not in VIEWS:
        raise ValueError(f"unknown view {view!r}; expected one of {VIEWS}")
    text = (KQL_DIR / f"{view}.kql").read_text(encoding="utf-8")
    for name, value in (("IdlePct", idle_pct), ("TzOffset", tz_offset_hours), ("Computers", computers)):
        if value is None:
            continue
        pattern, line = _LET[name]
        text, count = pattern.subn(line(value).replace("\\", "\\\\"), text)
        if count != 1:
            raise ValueError(f"view {view} has {count} '{name}' defaults; cannot override")
    return text


def _plain(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    return value


CREDENTIAL_KEYS = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "WORKSPACE_GUID")


def read_credentials(path: str | Path) -> dict[str, str]:
    """Read the KEY=value file written by scripts/create-query-identity.sh; fail if a key is missing."""
    values = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and not key.startswith("#"):
            values[key] = value.strip().strip('"')
    missing = [k for k in CREDENTIAL_KEYS if not values.get(k)]
    if missing:
        raise ValueError(f"{path} lacks {', '.join(missing)}")
    return values


def credential_from(values: dict[str, str] | None):
    """ClientSecretCredential for an app registration, else DefaultAzureCredential."""
    if values:
        from azure.identity import ClientSecretCredential

        return ClientSecretCredential(values["AZURE_TENANT_ID"], values["AZURE_CLIENT_ID"], values["AZURE_CLIENT_SECRET"])
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(exclude_interactive_browser_credential=True, process_timeout=60)


class GpuHoursClient:
    def __init__(self, workspace_id: str, logs_client=None, credential=None):
        self.workspace_id = workspace_id
        if logs_client is None:
            from azure.monitor.query import LogsQueryClient

            logs_client = LogsQueryClient(credential or credential_from(None))
        self._logs = logs_client

    def run_kql(self, kql: str, start: datetime, end: datetime) -> list[dict]:
        from azure.monitor.query import LogsQueryStatus

        result = self._logs.query_workspace(self.workspace_id, kql, timespan=(start, end))
        if result.status != LogsQueryStatus.SUCCESS:
            raise RuntimeError(f"partial result: {getattr(result, 'partial_error', None)}")
        table = result.tables[0]
        return [{c: _plain(v) for c, v in zip(table.columns, row)} for row in table.rows]

    def query_view(self, view: str, start: datetime, end: datetime, **overrides) -> list[dict]:
        return self.run_kql(build_query(view, **overrides), start, end)


def _dt(text: str) -> datetime:
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise argparse.ArgumentTypeError("give a UTC offset, for example 2026-10-01T00:00:00+08:00")
    return value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--credentials", help="gpu-hours.query.env from scripts/create-query-identity.sh")
    ap.add_argument("--workspace", help="Log Analytics workspace GUID (customerId); default WORKSPACE_GUID from --credentials")
    ap.add_argument("--view", required=True, choices=VIEWS)
    ap.add_argument("--start", required=True, type=_dt)
    ap.add_argument("--end", required=True, type=_dt)
    ap.add_argument("--idle-pct", type=int)
    ap.add_argument("--tz-offset", type=int, help="UTC offset in hours for per_hour/per_day")
    ap.add_argument("--computer", action="append", help="VM name to include (repeatable); default all")
    args = ap.parse_args(argv)
    values = read_credentials(args.credentials) if args.credentials else None
    workspace = args.workspace or (values or {}).get("WORKSPACE_GUID")
    if not workspace:
        ap.error("give --workspace or --credentials")
    rows = GpuHoursClient(workspace, credential=credential_from(values)).query_view(args.view, args.start, args.end, idle_pct=args.idle_pct,
                                                     tz_offset_hours=args.tz_offset, computers=args.computer)
    json.dump(rows, sys.stdout, indent=1, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
