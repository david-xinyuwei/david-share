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
    "A lease is the platform's claim that one process currently owns a unit of work. The owning process renews it periodically, and a process that stops renewing releases its claim.",
    "Take-over is not instant. The platform must notice that the previous owner is gone, schedule replacement capacity, and start a fresh process before any work can continue.",
    "Streaming and durability are independent choices. A stored response can stream every committed result while it runs, and it remains addressable long after the stream itself is gone.",
    "A dropped stream is not a failed job. The caller should reconnect to the same response identifier rather than treat the broken connection as an error worth retrying as new work.",
    "Reconnect attempts should be patient. Cancelling each attempt too early can interrupt the platform's own handshake and delay the recovery it was meant to observe.",
    "Checkpoint granularity is a trade-off. Frequent checkpoints reduce repeated work after a crash, while very fine ones add storage traffic and slow the normal path.",
    "The original request must stay immutable. A recovered process reads exactly the input the caller submitted, so recovery cannot silently change what the job was asked to do.",
    "Recovery should be observable from the outside. Distinct process identities, entry modes, and checkpoint continuity let a reviewer confirm a resume instead of trusting a status field.",
    "Immutable versions make rollback a routing decision. Because deployed code never changes in place, moving traffic between versions does not require rebuilding anything.",
    "Scale-to-zero trades idle cost for a cold start. The first call after an idle period pays for capacity allocation, which also shapes how quickly replacement compute appears.",
    "Concurrent recovery attempts must not duplicate side effects. A stable operation key lets downstream systems recognise a repeated request and return the original outcome.",
    "Some failures are permanent. A job that cannot succeed should reach an explicit terminal state instead of being recovered indefinitely by successive processes.",
    "Every long job needs a deadline. Without an absolute budget, a recovering job can consume capacity long after its business value has expired.",
    "A job may be recovered more than once. The resume logic must therefore be correct for an arbitrary number of interruptions, not just the first one.",
    "Useful metrics include time to detect loss, time to resume, repeated work after resume, and the number of process instances per job. Averages alone hide the worst cases.",
    "Fault injection belongs in a non-production deployment. The ability to end a process on demand is a test affordance and should never ship in a customer-facing configuration.",
    "Recovery consumes real capacity. Repeated work after the last checkpoint is billed like any other execution, so checkpoint placement is a cost decision as well as a correctness one.",
    "Capability is not a service level. Public preview behaviour demonstrated once in one region says nothing about availability targets, and should be described that way to customers.",
)

SECTION_IDS = tuple(
    f"translation_section_{index:02d}"
    for index in range(1, len(SOURCE_SECTIONS) + 1)
)
