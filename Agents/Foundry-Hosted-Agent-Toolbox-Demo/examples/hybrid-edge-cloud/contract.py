"""Task contract data model for hybrid edge-cloud demo.

The contract is a small JSON document shared between the edge agent and the cloud
hosted agent. See docs/hybrid-edge-cloud.md for the full design.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Step:
    step_id: int
    owner: str  # "edge" or "cloud"
    description: str
    status: str = "pending"  # pending | in_progress | done | failed
    result: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskContract:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    intent: str = ""
    current_owner: str = "edge"
    plan: list[Step] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)
    version: int = 0
    last_updated_by: str = "init"
    last_updated_at: float = field(default_factory=time.time)

    def bump(self, who: str) -> None:
        self.version += 1
        self.last_updated_by = who
        self.last_updated_at = time.time()

    def to_json(self) -> str:
        return json.dumps(
            {**asdict(self), "plan": [asdict(s) for s in self.plan]},
            indent=2,
            ensure_ascii=False,
        )

    @classmethod
    def load(cls, path: Path) -> "TaskContract":
        data = json.loads(path.read_text(encoding="utf-8"))
        plan = [Step(**s) for s in data.pop("plan", [])]
        return cls(plan=plan, **data)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")
