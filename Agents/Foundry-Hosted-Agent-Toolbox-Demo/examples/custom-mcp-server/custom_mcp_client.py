from __future__ import annotations

import json


def device_health_check(cpu_pct: float, mem_pct: float, temp_c: float) -> dict:
    if cpu_pct >= 90 or temp_c >= 85:
        return {"status": "critical", "advice": "page on-call"}
    if cpu_pct >= 75 or mem_pct >= 85 or temp_c >= 75:
        return {"status": "warning", "advice": "reduce workload"}
    return {"status": "healthy", "advice": "continue monitoring"}


def policy_evaluate(role: str, action: str, sensitivity: str) -> dict:
    if action in {"delete", "export"} and sensitivity in {"internal", "restricted"}:
        return {"decision": "needs_approval", "reason": "write/delete on sensitive data needs approval"}
    if role not in {"operator", "engineer", "admin"}:
        return {"decision": "deny", "reason": "unknown role"}
    return {"decision": "allow", "reason": "policy passed"}


def main() -> None:
    print("Tools found: 2")
    print("  - device_health_check")
    print("  - policy_evaluate")
    print("\n[invoke] device_health_check(cpu_pct=92, mem_pct=70, temp_c=88)")
    print(json.dumps(device_health_check(cpu_pct=92, mem_pct=70, temp_c=88)))
    print("\n[invoke] policy_evaluate(role=engineer, action=delete, sensitivity=internal)")
    print(json.dumps(policy_evaluate(role="engineer", action="delete", sensitivity="internal")))


if __name__ == "__main__":
    main()
