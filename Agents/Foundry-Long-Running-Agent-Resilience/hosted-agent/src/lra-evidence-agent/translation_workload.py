"""Public-safe source sections for the repository-owned translation workload."""

from __future__ import annotations


SOURCE_SECTIONS = (
    "A long-running agent should give each logical job a stable identity that outlives any one process. The caller stores that identity before reporting success upstream.",
    "Background execution and crash recovery solve different problems. Background execution survives a disconnected caller, while recovery survives the loss of the process that owns the work.",
    "A durable checkpoint marks completed business progress. It must be written only after the corresponding output or application state is complete and safe to replay.",
    "Recovery starts a new process with empty memory. The handler receives the original persisted input and uses a saved response snapshot or application checkpoint to find its resume point.",
    "The client must reconnect to the original response instead of creating replacement work. A timeout or temporary not-found response is not permission to duplicate the job.",
    "External operations require idempotency. Payments, bookings, email sends, and writes can be repeated after a crash unless the application records a stable operation key.",
    "A terminal event alone is not enough evidence. Acceptance should also verify output completeness, stable work identity, checkpoint continuity, and the expected business result.",
    "The platform preserves task metadata and leases, but the application owns domain state. Large artifacts and workflow state normally belong in application storage or a framework checkpointer.",
    "A recovered handler can safely skip work committed before the last checkpoint. Work performed after that boundary may run again and must therefore be replay safe.",
    "Operational evidence should include timestamps, process identities, status transitions, code hashes, and logs. Screenshots prove deployed objects but do not prove recovery behavior.",
    "Graceful shutdown and hard process loss are different interruption modes. Each mode needs its own trigger, expected result, observed result, and explicit PASS or NOT VERIFIED status.",
    "Production confidence requires repeated trials, workload-specific deadlines, load tests, and side-effect reconciliation. A single successful demonstration proves capability, not reliability.",
)

SECTION_IDS = tuple(
    f"translation_section_{index:02d}"
    for index in range(1, len(SOURCE_SECTIONS) + 1)
)
