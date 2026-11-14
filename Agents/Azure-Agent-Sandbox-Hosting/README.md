# Five Ways to Host an Agent Sandbox on Azure: ACA Sandboxes, Foundry Hosted Agent, AKS + agent-sandbox, BYO-AKS, E2B on Azure VM

[![Paths](https://img.shields.io/badge/paths-A%20%C2%B7%20B%20%C2%B7%20C%20%C2%B7%20D%20%C2%B7%20E-0078D4)](#purpose)
[![Measured](https://img.shields.io/badge/measured-East%20US%202%2C%202026--09--22%20to%2010--18-0078D4)](#results)
[![Docs CI](https://github.com/david-xinyuwei/david-share/actions/workflows/agent-sandbox-hosting-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/agent-sandbox-hosting-ci.yml)

Author: Xinyu Wei — Microsoft AI Lead Senior System Engineer · [中文](README_CN.md)

## Purpose

There are two ways to isolate an AI agent in micro-VMs (lightweight VMs with their own kernel) on Azure: run the whole stateful agent inside the session's own micro-VM (paths A–D), or run the agent in Foundry and put only the code its tools execute into a micro-VM sandbox (path E). Either way, you have to pick who runs that micro-VM and its lifecycle: a managed service, Foundry, or you on your own AKS nodes or Azure VM. The five paths make different trade-offs, and their seconds are hard to compare from product pages alone—especially when sandbox boot, private storage volume mounts, and model turns are lumped into one number. This repository applies one comparable stateful interaction contract to all five paths, compares only the sandbox's own lifecycle seconds (create → ready, resume → ready, lost → ready), gives the steps to reproduce each path, and shows what we measured. A and C share the workshop reflection agent; B uses its distinct Agent Framework agent with ResponsesHostServer; D uses the product group's private-preview sample; E uses a Foundry Prompt Agent whose function tool runs the agent's code with E2B's Code Interpreter in a Firecracker sandbox on an Azure VM, so this is not an identical-container benchmark:

| Question | A · ACA Sandboxes | B · Foundry hosted agent | C · AKS + agent-sandbox | D · BYO-AKS | E · E2B on Azure VM |
|---|---|---|---|---|---|
| Status | GA (2026-09-23) | GA (2026-06) | Pod Sandboxing GA (2025-11-18); agent-sandbox v0.5.2 is open source | **Private preview** | E2B Embed open source (`588e5b9`) on Azure Gen2 VM |
| Who runs the session lifecycle | The ACA service | Foundry | You: controller, gateway, idle sweeper | Foundry, on your cluster | You: E2B orchestrator on your VM, called as a Foundry agent tool |
| Where the session's micro-VM runs | Service-managed compute | Microsoft-managed compute | Your Kata node pool | Your Kata node pool | Your Azure VM with nested virtualization (`/dev/kvm`) |
| Suspend with memory snapshot | Yes | No: idle releases compute, `$HOME` and `/files` are restored | No memory snapshot: you patch `operatingMode`; the pod goes, file state comes back from Blob | No memory snapshot: the session API's `:stop` ends the session pod; the next request starts a new pod and the file written before the stop is still there (2026-10-18) | Yes: `beta_pause` saves Firecracker memory and disk (`vm_state` + `mem_file`) |
| External storage to keep data across suspend and resume | Not needed (optional): the Memory snapshot keeps memory and disk; without a volume the conversation was kept 3/3 (2026-10-18) | Not needed (optional): the platform keeps `$HOME` and `/files`; the file written before the stop was read back 3/3 | **Required**: suspend deletes the pod and keeps no memory snapshot; with the Blob PVC the conversation went on 3/3. Without a volume the state goes with the pod (inferred from Kubernetes, not tested) | Not needed (optional): `:stop` ends the session pod, and the file written before it was read back on the new pod 3/3 (2026-10-18) | Not needed (optional): the pause snapshot stays on the host VM's OS disk and could not resume on a second host (`e-2026-10-18-ci-multi`); the sandbox history kept growing 3/3 |
| Selectable size / node SKU (docs) | XS: 0.25 vCPU / 0.5 GiB<br>S: 0.5 vCPU / 1 GiB<br>M (default): 1 vCPU / 2 GiB<br>L: 2 vCPU / 4 GiB<br>XL: 4 vCPU / 8 GiB<br>2XL: 8 vCPU / 16 GiB<br>3XL: 16 vCPU / 32 GiB | 0.5 vCPU / 1 GiB<br>1 vCPU / 2 GiB<br>2 vCPU / 4 GiB<br>No VM SKU to choose | Kata-compatible Gen2 VM SKUs, such as the Dsv3 series; Azure Linux and nested virtualization required | Kata node SKUs within the approved preview requirements; confirm the selectable list with the product group | Gen2 VM SKUs with nested virtualization, such as `Standard_D4ds_v7` or `Standard_D8ds_v7`; E2B's `code-interpreter-v1` template is 2 vCPU / 2 GiB, and each sandbox takes 2 GiB of the VM's hugepage pool |
| Choose it when | You want per-user micro-VMs, snapshots and no cluster | You want Foundry to run everything and its limits do not bite | You must own the node, the network and the control plane | You need Foundry's agent platform **and** sessions on nodes you own | You want sub-second Firecracker creation and memory snapshots on a VM you own, called as a Foundry agent tool |

The external-storage row covers suspend and resume of the same sandbox or session. To keep data after the sandbox or session is deleted, or to share it across sandboxes, plan external storage or a database on all five paths; we did not test deleting a sandbox or session.

Product capabilities come from Microsoft Learn and status from the official announcements linked below; measured claims come from our runs; the last row is our selection guidance. Start with B for a general managed enterprise agent when its limits fit. For a long-running, per-user workload that needs memory snapshots without a cluster, start with A. Use C, D or E when owning the execution nodes is non-negotiable; choose D when Foundry must run the session pods on your AKS cluster, or E when a Foundry Prompt Agent calls self-hosted Firecracker sandboxes on a single Azure VM. E2B Embed is [one machine by design](https://github.com/e2b-dev/runtime/blob/588e5b9500b0987bc5a700d91483b03f0ae7d2a2/embed/README.md#when-one-node-is-not-enough): more VMs are more independent installs that your client spreads sessions over (`e-2026-10-18-ci-multi`), and E2B's multi-node offer in your own cloud account is Bring Your Own Cloud, operated by E2B, which we did not test.

The selectable row separates four categories: [A's sandbox resource tiers](https://learn.microsoft.com/azure/container-apps/sandboxes-overview#resource-tiers), [B's sandbox sizes](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents#sandbox-sizes), [C/D's node VM SKUs](https://learn.microsoft.com/azure/aks/use-pod-sandboxing), and [E's host Azure Gen2 VM SKU plus E2B template quota](https://github.com/e2b-dev/runtime/tree/588e5b9500b0987bc5a700d91483b03f0ae7d2a2). A node or host VM SKU is not a per-session allocation; Kata pod requests, limits and overhead also constrain each session in C/D, and the E2B template (`code-interpreter-v1`: `2` vCPU / `2048` MB) constrains each Firecracker sandbox in E, which takes its whole memory from the host's hugepage pool when it is created. Path E serves as a self-hosted open-source Firecracker reference baseline on an Azure VM to cross-check sandbox startup and memory-snapshot resume against the Azure-native options (A–D). Node availability and quota vary by region and subscription, and D has additional preview requirements.

Status sources: [A GA announcement](https://techcommunity.microsoft.com/blog/appsonazureblog/azure-container-apps-sandboxes-now-generally-available/4559125), [B GA announcement](https://azure.microsoft.com/updates?id=563596), [C Pod Sandboxing GA](https://azure.microsoft.com/updates?id=526237), and [E open-source E2B Embed runtime (`588e5b9`)](https://github.com/e2b-dev/runtime/tree/588e5b9500b0987bc5a700d91483b03f0ae7d2a2); agent-sandbox and E2B Embed themselves are open-source projects, not Azure services. For C/D, [Kata provides compute isolation only](https://learn.microsoft.com/azure/aks/concepts-pod-sandboxing), not isolation of the control plane, storage/data paths or cluster-admin actions. For E, Firecracker (`v1.14-0.2.0`) on `/dev/kvm` isolates each sandbox micro-VM, while you own the host VM OS, Docker daemon, E2B API authentication and subnet NSG rules.

<img src="images/architecture-en.png" width="900" alt="Five columns A to E. Each shows the client entry, the Microsoft-managed zone and your subscription. A: ACA Sandboxes service and a sandbox micro-VM, with sandbox group, registry and Blob volume in your subscription. B: Foundry Agent Service and a per-session sandbox, with project and Application Insights in your subscription. C: AKS control plane, then controller, Kata pod VM, Kata node pool and Blob PVC in your subscription. D: Foundry Agent Service, then subnet NSG, foundry-system, Kata pod VM per session and registry and storage in your subscription. E: Foundry Agent Service, then Azure VM with E2B Embed Compose stack, Firecracker per sandbox and the VM's OS disk holding templates and snapshots in your subscription.">

What the figure shows: who owns each component and where the micro-VM boundary sits. A, C, D and E placement comes from our read-backs; B's VM-isolated boundary comes from Learn. It does not show networking detail, identity flows or the model gateway.

**Execution models and official concurrency quotas (agent container in sandbox vs tool sandbox).** Paths A–D run the entire stateful agent container inside the session's micro-VM, whereas path E runs the agent in Foundry's control plane and calls an isolated micro-VM sandbox only when executing code or tools:

| Execution pattern | Where the agent process runs | What runs in the micro-VM | Documented concurrency & quota limits | Micro-VM active for whole session? | Idle pause & scale-to-zero |
|---|---|---|---|---|---|
| **A / B / C / D (stateful agent container in sandbox)** | Inside the micro-VM sandbox (`1:1` bound to the session) | The whole agent container (ACA Cloud Hypervisor / Foundry sandbox / AKS Kata) | **A**: [500 concurrent active cores](https://sandboxes.azure.com/docs/sandboxes/limits) default ([2,000 cores standard limit](https://learn.microsoft.com/azure/container-apps/quotas#sandboxes-and-express-quotas), `20,000` cores verified in our subscription; `3,000` requests/min; stopped sandboxes do not count)<br>**B**: [1:1 per active session](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents#scaling-and-right-sizing) (`20` GiB disk, `50` MB per uploaded file)<br>**C / D**: bounded by your AKS Kata node-pool vCPU/RAM quota; D's preview build placed at most <!--v:d.capacity.per_node-->5<!--/v--> sessions per `Standard_D4s_v5` node, so plan by sessions opened, not only requests active | **Yes** — the micro-VM stays Running for the active session | **A**: memory snapshot suspend (resume → `Running` <!--v:a.nv.resume.median-->1.22<!--/v--> s median without a volume)<br>**B**: idle timeout or `:stop` releases compute and keeps `$HOME`<br>**C**: patch `operatingMode` deletes pod and restores from Blob<br>**D**: session `:stop` ends the session pod; the next request starts a new one |
| **E (Foundry Agent Service + E2B on Azure VM tool sandbox)** | Foundry managed control plane (serverless, billed by model tokens) | Only the code the agent's tools run: Firecracker on your Azure Gen2 VM (`/dev/kvm`) | One Embed install is one VM, bounded by its hugepage pool: each 2 GiB `code-interpreter-v1` sandbox takes <!--v:e.h.reserve.per_sandbox-->1024<!--/v--> hugepages when it is created, so `HUGEPAGES=4096` on a `Standard_D4ds_v7` held <!--v:e.h.reserve.fit-->3<!--/v--> and `HUGEPAGES=8448` on a `Standard_D8ds_v7` held <!--v:e.s.reserve.fit-->8<!--/v--> (probes with no model, 2026-10-18); a second, independent VM adds its own pool; there is no shared scheduler between installs | **On demand** — only during `run_in_e2b_sandbox` tool calls; can `beta_pause` between turns | Per-sandbox memory snapshot (resume <!--v:e.ci.resume.median-->0.64<!--/v--> s median in the 2026-10-17 agent runs; <!--v:e.h.resume.range-->0.38–10.24<!--/v--> s over 20 cycles in turn on 2026-10-18), while the host Azure VM (`0.344` USD/h) stays running |

**Consumer-facing (ToC) and high-concurrency selection trade-offs: cold start, warm pools, and cost (ACA vs AKS Spot vs E2B):**
- **Cold-start speed and warm pools:** For interactive ToC workloads, cold-start latency and unit cost are the two primary criteria. Without a prewarmed pool, Kubernetes-based sandboxes (C/D) incur image-pull or volume-mount latency on new nodes unless you maintain your own warm pool (such as `SandboxWarmPool` in `agent-sandbox`). ACA Sandboxes (A, without a private Blob volume: Running in <!--v:a.nv.create.median-->1.35<!--/v--> s median) start from a platform-managed warm pool, while E2B on a running Azure VM (E) boots a 2 GiB `code-interpreter-v1` Firecracker sandbox from a local template snapshot in <!--v:e.ci.create.median-->0.08<!--/v--> s median (<!--v:e.ci.d_sandbox_ready.range-->0.069–0.13<!--/v--> s in the 5 cold sessions), and in <!--v:e.h.create.range-->0.088–0.56<!--/v--> s over 20 creates in turn on the same host (2026-10-18).
- **Cost structure — lifecycle + state + resume speed (ACA strength) vs Spot nodes (AKS/VM strength):** Across bursty user sessions with long idle tails, **ACA (A) is stronger on lifecycle management, state preservation and resume speed**: stopped sandboxes preserve full memory and disk state (resume → Running <!--v:a.nv.resume.median-->1.22<!--/v--> s median without a volume) while billing zero CPU/memory and consuming zero active-core quota. Conversely, **AKS (C) and self-hosted VMs (E) can use [Azure Spot node pools / Spot VMs](https://learn.microsoft.com/azure/aks/spot-node-pool)** (or Reserved Instances / Savings Plans) to lower raw vCPU-hour compute cost for sustained high-utilization or eviction-tolerant workloads—an option serverless ACA does not expose. When using AKS Spot for stateful sandboxes, your application must handle Spot eviction and state recovery from external storage.

## Results

Words used in the results:

| Term | Meaning |
|---|---|
| Ready | The state a platform reports when the sandbox is usable: A `Running`, B session `active`, C Sandbox `Ready`, D session pod `Ready`, E `Sandbox.create` or `Sandbox.connect` has returned. It is not the agent's first answer |
| Create → ready | A new sandbox, session or pod, from the create request until it is ready |
| Resume → ready | A suspended sandbox, from the resume request until it is ready again; stop and idle waiting are excluded |
| Pod lost | Delete the session's pod or sandbox; Kubernetes or the caller creates a replacement |
| Micro-VM | A lightweight VM with its own guest kernel per sandbox, session or pod (Kata Containers on AKS; Cloud Hypervisor read back inside ACA; Firecracker on KVM in E2B) |

**Where each path's micro-VM runs.** Measured read-backs for A, C, D and E, plus Learn's documented boundary for B:

| | A · ACA Sandboxes | B · Foundry hosted agent | C · AKS + agent-sandbox | D · BYO-AKS | E · E2B on Azure VM |
|---|---|---|---|---|---|
| Boundary | One micro-VM per sandbox | Per-session VM-isolated sandbox (Learn) | One Kata pod VM per Sandbox | One Kata pod VM per session | One Firecracker per sandbox |
| VMM and hypervisor | `vmm_type` <!--v:a.vmm.value-->cloudhypervisor<!--/v--> from the API; the docs name no hypervisor | Not published; only VM isolation is documented | Cloud Hypervisor on Microsoft Hyper-V (Learn) | Same as C | <!--v:e.h.isolation.vmm_type-->firecracker<!--/v--> (<!--v:e.h.isolation.firecracker_version-->v1.14-0.2.0<!--/v-->) on Linux KVM (`/dev/kvm`), from the host's process list |
| Kernel read | Guest <!--v:a.isolation.guest_kernel-->6.12.8+<!--/v--> | Not exposed; not read back | Pod <!--v:c.isolation.guest_kernel-->6.6.137.mshv1-1.azl3<!--/v-->, runc pod <!--v:c.isolation.system_node_kernel-->6.8.0-1067-azure<!--/v--> | Kata pool nodes <!--v:d.node_kernel.value-->6.6.137.mshv2-2.azl3<!--/v-->; not read inside a session pod | Guest <!--v:e.h.isolation.guest_kernel-->6.1.177+<!--/v--> on host VMs running <!--v:e.h.isolation.host_kernel-->7.0.0-1017-azure<!--/v--> and <!--v:e.s.isolation.host_kernel-->6.17.0-1022-azure<!--/v--> |
| Who owns the node | Microsoft | Microsoft | You | You | You |

B's per-session VM-isolated boundary is a `SOURCE_FACT`, not a local VMM or kernel read-back. C and D use the same Kata runtime class, so isolation does not separate them: who runs the platform does. E runs Firecracker directly on `/dev/kvm` inside your Azure Gen2 VM.

**Only the sandbox's own seconds.** The comparison below times how long each platform takes to create a sandbox, session or pod until it is ready, to resume a suspended one until it is ready again, and to replace a lost one. It leaves out answer times: they mostly measure the model, the agent and the network path, which differ between the five paths, and a question such as "Where is Bangkok?" needs no code to run in the sandbox, so its answer time says nothing about the sandbox. The runs still asked the agent questions to check that its state survived (the history kept growing, a file written before a stop was read back); those checks and every answer time are in [VALIDATION.md](VALIDATION.md#measured-runs). A's full workshop specification attaches a private Blob volume that A does not need to keep state across suspend; in one attribution run create → Running took <!--v:a.attr.vnetvolume.range-->15.79–25.12<!--/v--> s with it and <!--v:a.attr.small.range-->1.6–2.7<!--/v--> s without, so the table shows both. A is three runs without the Blob volume on 2026-10-18, and three runs with it plus the attribution matrix on 2026-10-09; B is three session-API runs on 2026-10-15 and the idle-wait runs of 2026-10-18; C is three runs without and three with the Blob PVC on 2026-10-18 plus the single run of 2026-09-27; D is one benchmark campaign on 2026-09-29 plus three session-API runs on 2026-10-18; E is one benchmark campaign with `code-interpreter-v1` on 2026-10-17 plus three runs with it on 2026-10-18 (20 create/pause/resume cycles and a hugepage probe, two hosts, and a `Standard_D8ds_v7`); the runs of 2026-10-14 and 2026-10-15 used the superseded executor (`base` template, `python3` through `commands.run`) and stay in the run table below. A and C use the workshop reflection agent; B uses its Agent Framework agent with ResponsesHostServer; D uses the private-preview sample; E uses a Foundry Prompt Agent whose function tool runs its code with E2B's Code Interpreter. All use the same model and a stateful interaction, but not the same container. A's, B's and C's ready clocks run on the client, D's come from Kubernetes timestamps and E's run on the E2B host VM; where each client was is in [VALIDATION.md](VALIDATION.md#measured-runs). Compare within a row as a field report, not as a controlled product benchmark:

**How each clock is timed, and the scripts.** Every clock below runs from the request or event on the left of the arrow to the state on the right; no model call falls inside it. The questions the runs asked to check state are quoted verbatim in [VALIDATION.md](VALIDATION.md#measured-runs):

| Path | Create → ready | Resume → ready | Lost → ready | Script |
|---|---|---|---|---|
| **A** | SDK `_do_create_sandbox` → `get_sandbox` state `Running` | `sandbox.resume()` → `Running` | not exercisable | [`tools/measure_aca.py`](tools/measure_aca.py) |
| **B** | `POST .../endpoint/sessions` → `active` | no separate step: the next request wakes the session | not exercisable | [`tools/measure_sessions.py`](tools/measure_sessions.py) |
| **C** | `kubectl apply` → Sandbox `Ready` | `operatingMode: Running` → Sandbox `Ready` | `kubectl delete pod` → new pod `Ready` | [`tools/measure_c.py`](tools/measure_c.py) |
| **D** | pod `creationTimestamp` → `Ready` condition | no separate step: the next request starts a new session pod | pod deleted → replacement `Ready` | [`tools/measure_responses.py`](tools/measure_responses.py) (`--observe`, `--recovery`)<br>[`tools/measure_sessions.py`](tools/measure_sessions.py) (`--path D`) |
| **E** | Code Interpreter `Sandbox.create()` (template `code-interpreter-v1`) → it returns | `Sandbox.connect` → it returns | `kill`, then a replacement sandbox → ready | [`tools/measure_e2b.py`](tools/measure_e2b.py) (`agent`, `perf` and `host` modes) |

Resume starts after suspension has finished; stop and idle waiting are excluded. Every clock, its start and end, and where it runs are in [VALIDATION.md](VALIDATION.md#architecture-and-metrics).

**Do not rank the five products by these seconds.** Clock locations, what each platform reports as ready, sandbox sizes, image cache and sample sizes differ across paths. Numerical sanity checks can reject invalid timings; they cannot establish product performance or fill missing instrumentation.

<!-- BEGIN GENERATED: comparison -->
| Observed or docu&shy;mented | A · ACA Sand&shy;boxes | B · Foundry hosted agent | C · AKS + agent-sandbox | D · BYO-AKS | E · E2B on Azure VM |
|---|---|---|---|---|---|
| **Create → ready, no external volume** | **1.35 s** median (1.22–&#8203;2.15; n=3), SDK create → `Running`, image + VNet + port (2026-10-18); image only 2.31 s median (1.6–&#8203;2.7; n=3) (2026-10-09) | **6.69 s** median (6.51–&#8203;6.87; n=3), <code>POST </code><br><code>.../</code><br><code>endpoint/</code><br><code>sessions</code>&#8203; → `active` | **16.45 s** median (15.32–&#8203;18.9; n=3), <code>kubectl </code><br><code>apply</code>&#8203; → Sandbox `Ready` | **8–&#8203;10 s** (n=6), pod created → `Ready` with the image cached; 25 s on a fresh node (n=2) | **0.08 s** median (0.07–&#8203;0.22; n=3) in the agent runs, <code>Sandbox.create()</code>&#8203; → it returns; 0.073 s median (0.069–&#8203;0.13; n=5) in the D-protocol new sessions; 0.088–&#8203;0.56 s over 20 creates in turn, 4 of them under 0.1 s (2026-10-18) |
| **Create → ready with a private Blob volume**<br>Optional: to keep data across suspend and resume, only C needs a volume | **24.25 s** median (24.12–&#8203;44.86; n=3), SDK create → `Running`, image + VNet + port + volume (2026-10-09) | not needed: the platform restores `$HOME` and `/files` | **required** to keep data; **16.46 s** median (16.26–&#8203;16.81; n=3), <code>kubectl </code><br><code>apply</code>&#8203; → Sandbox `Ready`; 2026-09-27: 44.9 s (n=1) | not needed: the file written before `:stop` is kept | not needed: tem&shy;plates and snap&shy;shots stay on the host VM's OS disk |
| └ volume overhead | create → Running in one attribution run (2026-10-09): 1.6–&#8203;2.7 s without the volume (image, VNet or port alone; n=7), 15.79–&#8203;25.12 s with it (image + VNet + volume; n=2) | none | none measurable: apply → Ready 16.46 s median (16.26–&#8203;16.81; n=3) with the PVC, 16.45 s median (15.32–&#8203;18.9; n=3) without | none | none |
| **Resume → ready** | **1.22 s** median (0.82–&#8203;4.46; n=3), resume → `Running`, without the Blob volume (2026-10-18) | not timed sep&shy;arately: after `:stop` the session wakes on its next request, and that request's time includes a model turn; `$HOME` kept, no memory snapshot | **15.93 s** median (15.87–&#8203;17.28; n=3), <code>operatingMode: </code><br><code>Running</code>&#8203; → Sandbox `Ready`, with the Blob PVC that C needs to keep data; no memory snapshot | not timed sep&shy;arately: after `:stop` the next request starts a new session pod, and that request's time includes a model turn; the file written before is kept, no memory snapshot | **0.64 s** median (0.63–&#8203;1.43; n=3) in the agent runs, <code>Sandbox.connect</code>&#8203; → it returns; 0.38–&#8203;10.24 s over 20 cycles in turn with no model, 17 of 20 over 1 s (2026-10-18) |
| **Pod or sandbox lost → ready again** | not exer&shy;cisable: no API injects host loss, and deleting a sandbox ends it | not exer&shy;cisable: no API kills only a session's sandbox; explicit stop and resume are above | 24.79 s median (23.25–&#8203;25.24; n=3); with the Blob PVC that C needs to keep data, the conversation went on 3/3 (2026-09-27: 23.4 s, n=1) | 23.9 s (n=1); deleted session con&shy;tinuity not tested | 0.12 s (n=1): after `kill`, a replacement sandbox until it is ready |

<!-- END GENERATED: comparison -->

What stands out:
- **Without the private Blob volume, A is fast and keeps the session through its Memory snapshot:** with the image, VNet and port but no volume (2026-10-18), a new sandbox was Running in <!--v:a.nv.create.median-->1.35<!--/v--> s median (<!--v:a.nv.create.range-->1.22–2.15<!--/v--> s, n=<!--v:a.nv.create.n-->3<!--/v-->) and resumed to Running in <!--v:a.nv.resume.median-->1.22<!--/v--> s median (<!--v:a.nv.resume.range-->0.82–4.46<!--/v--> s); after stop and resume the conversation continued in <!--v:a.nv.state_kept.count-->3<!--/v-->/<!--v:a.nv.state_kept.n-->3<!--/v--> runs. The private Blob volume of the workshop specification is optional; with it (2026-10-09) create → Running took <!--v:a.create.median-->24.25<!--/v--> s median (<!--v:a.create.range-->24.12–44.86<!--/v--> s). So A needs no external volume just to keep a session across suspend; the state then lives only in that sandbox (deleting the sandbox, or reading the state from another one, was not tested).
- **E (E2B on Azure VM) runs the agent's code with E2B's Code Interpreter in a 2 GiB Firecracker sandbox, usually created in a fraction of a second; how many fit at once is set by the VM's hugepage pool:** with `code-interpreter-v1`, sandbox creation took <!--v:e.ci.create.median-->0.08<!--/v--> s median in the agent runs and <!--v:e.h.create.range-->0.088–0.56<!--/v--> s over 20 creates in turn (<!--v:e.h.create.under_0_1-->4<!--/v--> of them under 0.1 s). Resume is not always that fast: <!--v:e.ci.resume.median-->0.64<!--/v--> s median in the agent runs, but over 20 back-to-back cycles on the same host it took <!--v:e.h.resume.range-->0.38–10.24<!--/v--> s, <!--v:e.h.resume.over_1-->17<!--/v--> of them over 1 s. Each sandbox took <!--v:e.h.reserve.per_sandbox-->1024<!--/v--> hugepages, its whole 2 GiB, as soon as it was created, so the pool, not the CPU, set how many fit: <!--v:e.h.reserve.fit-->3<!--/v--> on a `Standard_D4ds_v7` with `HUGEPAGES=4096` and <!--v:e.s.reserve.fit-->8<!--/v--> on a `Standard_D8ds_v7` with `HUGEPAGES=8448`, both probed with no model. Embed is one machine by design: you own the VM OS, Docker Compose stack, network rules, hugepage sizing and any spreading over several VMs, and a paused sandbox can only resume on the VM that paused it.
- **D (BYO-AKS) keeps files across an explicit stop in the measured private-preview build:** the session pod was Ready in <!--v:d.pod_ready.range-->8–10<!--/v--> s with the image cached, and `:stop` ends the session pod: the next request starts a new one, and the file written before the stop was read back <!--v:d.sess.state_kept.files-->3<!--/v-->/<!--v:d.sess.state_kept.n-->3<!--/v--> (2026-10-18). This records the tested build's behavior, not a future performance commitment.
- **C's Blob PVC adds no measurable startup time (2026-10-18):** `kubectl apply` → Ready took <!--v:c.n.apply_ready.median-->16.45<!--/v--> s median without an external volume and <!--v:c.p.apply_ready.median-->16.46<!--/v--> s with the already-bound Blob PVC; with the PVC the conversation survived pod loss and suspend/resume in <!--v:c.p.state_kept.count-->3<!--/v-->/<!--v:c.p.state_kept.n-->3<!--/v--> runs, and resume → Ready took <!--v:c.p.resume_ready.median-->15.93<!--/v--> s median.

**Measured runs.** Grouped A–E, then by date from oldest to newest within each path, in the same order as [VALIDATION.md](VALIDATION.md), which records each run's input, procedure, result and boundary:

<!-- BEGIN GENERATED: runs -->
| Run | Path | Scenario | Result |
|---|---|---|---|
| `a-2026-09-27-setup` | A | first deployment, wake on request | kernel `6.12.8+`; deploy and wake times in VALIDATION |
| `a-2026-10-09-agent` | A | full agent, 3 runs | create → Running 24.25 s with the Blob volume (median); vmm `cloudhypervisor` in 3/3; history grew 3/3 |
| `a-2026-10-09-attribution` | A | create time by configuration | image, VNet or port alone 1.6–2.7 s; adding the private Blob volume 15.79–25.12 s |
| `a-2026-10-09-late-mount` | A | start first, mount Blob later | start 3.99–7.2 s, then mount 12.4–20.29 s (n=2) |
| `a-2026-10-18-scale` | A | 4 and 8 agent sandboxes at once | create → Running 15.49–24.55 s with the full specification, 4 and 8 at once; none left |
| `a-2026-10-18-novolume` | A | full agent without the Blob volume, 3 runs | create → Running 1.35 s, resume → Running 1.22 s (medians); conversation kept across stop and resume 3/3; none left |
| `b-2026-09-27` | B | deploy, new session, follow-ups; gateway model route | deploy and answer times only; see VALIDATION |
| `b-2026-10-15-sessions` | B | explicit session lifecycle, 3 runs | create → active 6.69 s (median); file kept across stop and resume 3/3 |
| `b-2026-10-18-perf` | B | D's protocol through the gateway: cold, warm, 4 and 8 at once | answer times and at-once answers only; see VALIDATION |
| `b-2026-10-18-idle` | B | next turn after 17 min without requests, and after 5 min; 3 runs each | status after 17 min `active` 1/3, `idle` 2/3; file kept 3/3 |
| `c-2026-09-27` | C | Kata Sandbox, pod loss, suspend/resume | pod kernel `6.6.137.mshv1-1.azl3` vs runc pod on the Ubuntu system pool `6.8.0-1067-azure`; pod lost → Ready 23.4 s; resume → Ready 17.1 s |
| `c-2026-10-18-perf` | C | cold without and with the Blob PVC, pod loss, suspend/resume, 4 and 8 at once | apply → Ready 16.45 s without the volume, 16.46 s with the PVC; pod lost → Ready 24.79 s, resume → Ready 15.93 s (medians, with the PVC); conversation kept 3/3 |
| `d-2026-09-29-placement` | D | where a session runs | every session pod `kata-vm-isolation` on your node pool after NSG rule `Allow-AzureCloud-FoundryRouter-443` |
| `d-2026-09-29-perf` | D | cold, warm, 4 and 8 at once | session pod created → Ready 8–10 s with the image cached, 25 s on a fresh node |
| `d-2026-09-29-recovery` | D | delete a session pod | replacement Ready in 23.9 s; deleted session continuity not tested |
| `d-2026-10-18-sessions` | D | explicit session lifecycle, 3 runs | create → active 9.32 s (median); file kept 3/3; a new session pod after each stop |
| `e-2026-10-14-agent` | E | superseded executor (`base` template, `python3` through `commands.run`): Prompt Agent + E2B, 3 runs + 20-run microbench | create 0.07 s (on host 0.051–0.089 s), resume 0.09 s (medians); VMM `firecracker` in the host's process list; history grew 3/3 |
| `e-2026-10-14-perf` | E | superseded executor (`base` template, `python3` through `commands.run`): cold, warm, 4 and 8 at once, replacement | replacement Ready in 0.1 s |
| `e-2026-10-15-latest` | E | newest SDK (superseded executor (`base` template, `python3` through `commands.run`)); E2B's official code-interpreter template | e2b 2.56.0: history grew 3/3, create 0.06 s, resume 0.08 s (medians); code-interpreter built only after raising three host defaults; 10/11 checks passed in 4/4 runs, JavaScript failed in all |
| `e-2026-10-15-multi` | E | superseded executor (`base` template, `python3` through `commands.run`): two independent E2B hosts: second host, at once, idle, host stop | host b: history grew 3/3, create 0.06 s; with host a's stack stopped, host b kept serving and host a's paused sandbox could not resume on host b |
| `e-2026-10-17-ci-agent` | E | E2B Code Interpreter (`run_code`) in `code-interpreter-v1`, 3 runs; template build on host c | create 0.08 s, resume 0.64 s (medians); history grew 3/3; template built on attempt 3 of 3 |
| `e-2026-10-17-ci-perf` | E | cold, warm, 4 and 8 at once, replacement, idle capacity; `code-interpreter-v1` | create 0.073 s (median of the 5 new sessions); replacement Ready in 0.12 s; idle at `HUGEPAGES=4096`: 3 `code-interpreter-v1` or 15 `base` sandboxes |
| `e-2026-10-18-ci-host` | E | host mode on host c, no model: 20 create → pause → resume cycles, hugepages per sandbox | create 0.088–0.56 s (4 of 20 under 0.1 s), resume 0.38–10.24 s; `x` kept 20/20; 1024 pages per sandbox, 3 fit at `HUGEPAGES=4096`, the next refused |
| `e-2026-10-18-ci-multi` | E | two hosts with `code-interpreter-v1`: agent runs on host a, at once on one and on two hosts, host stop | host a: history grew 3/3, create 10.53, 0.09, 0.22 s, resume 0.39 s (median); with host a's stack stopped, host c kept serving and host a's paused sandbox could not resume on host c |
| `e-2026-10-18-ci-scale` | E | new `Standard_D8ds_v7` with `HUGEPAGES=8448`: README step 7, cold, warm, 4 and 8 at once, replacement, hugepages | template built on the first attempt; replacement Ready in 0.063 s; 8 sandboxes fit at `HUGEPAGES=8448`, the next refused |
<!-- END GENERATED: runs -->

**Limits.**
- One region (East US 2). Behind the comparison: A n=3 without the Blob volume (2026-10-18) and n=3 with it (2026-10-09); B n=3 session-API runs (2026-10-15); C n=3 without and n=3 with the Blob PVC, pod loss and resume n=3 with it (2026-10-18), plus one run on 2026-09-27; D n=<!--v:d.pod_ready.n-->6<!--/v--> pods with the image cached, n=<!--v:d.pod_ready_fresh.n-->2<!--/v--> on a fresh node and one pod deletion (2026-09-29); E n=3 agent runs, n=5 new sessions and one replacement with `code-interpreter-v1` (2026-10-17), and 20 create/pause/resume cycles with no model (2026-10-18). The runs of 2026-10-14 and 2026-10-15 used the superseded executor (`base` template, `python3` through `commands.run`); they stay in the run table. Repeat them with the live measurement commands in VALIDATION before you rely on a number.
- These are implementation observations, not product benchmarks or SLAs. The docs state sub-second sandbox start for A from prewarmed pools; our full specification with a private Blob volume did not get there; without the volume, create took <!--v:a.nv.create.median-->1.35<!--/v--> s median (image only: <!--v:a.attr.image.median-->2.31<!--/v--> s).
- Ready is where a platform reports the sandbox usable, not where the agent answers. In D's preview build the first answer came <!--v:d.first_after_ready.median-->15.49<!--/v--> s (median, derived) after the session pod was Ready, of which the agent's own response took <!--v:d.agent_turn.range-->2–5<!--/v--> s; the remainder was not separately instrumented and is not a measured gateway latency.
- D is a private preview; its behaviour (placement, idle reclaim, limits and latency) may change, and its onboarding needs the product group's sample and enablement.
- Not measured: when B's platform reclaims an idle session (the status was read once, after the wait), A's and B's pod or host loss (neither service offers a way to inject it), the Foundry-governed agent calling an ACA sandbox per task (the pattern Microsoft describes since GA), E2B Bring Your Own Cloud and private cloud (E2B's multi-node offers), the official Azure Terraform module's scale-set replacement from a fresh disk (blocked in our subscription by a storage-account policy), and the loss of a whole E2B VM or its disk.
- Cost: D's two-node floor is <!--v:d.cost_floor.value-->0.484<!--/v--> USD/h for two `Standard_D4s_v5` nodes and the AKS Standard tier; E's single-VM floor is <!--v:e.cost_floor.value-->0.344<!--/v--> USD/h for one `Standard_D4ds_v7` VM, one Standard static public IP and a 50 GB Premium SSD P6 disk at East US 2 retail prices. Building `code-interpreter-v1` needed a larger OS disk than 50 GB (we used 128 GB), which costs more; that price is not included. The `Standard_D8ds_v7` of `e-2026-10-18-ci-scale` lists at 0.653 USD/h for the VM alone (East US 2, 2026-10-18). Check your own prices.

## Steps

**Deploy first, then use the agent.** These steps follow the [pinned colleague workshop](https://github.com/oxcp/ainotes/tree/905f2c2/agenthost): shared foundation, the selected hosting path, and an actual application call. Benchmarking and evidence replay are optional and live in VALIDATION, not on the deployment path.

**Execution boundary:** the original deployments produced the retained historical results, but this parameterized sequence has not been re-run end to end in a fresh subscription. D also requires the product group's private sample and approval. Offline CI does not certify a successful cloud deployment.

| Order | Where | Action | Entry |
|---|---|---|---|
| 1 | Workstation | Clone, configure and sign in | `config/.env.example` |
| 2 | Azure subscription | Create the shared foundation | workshop `module-01/setup.sh` |
| 3 | C | Build the image, create AKS, deploy the Sandbox and open the app | workshop `module-03` |
| 4 | A | Create the sandbox group and deploy the agent sandbox | workshop `module-04` + `tools/aca_sandbox.py` |
| 5 | B | Deploy the hosted agent and invoke it | workshop `module-02` |
| 6 | D | Bind an existing AKS, deploy and invoke the private-preview agent | product-group sample |
| 7 | E | Deploy E2B Embed on an Azure Gen2 VM, build E2B's Code Interpreter template and invoke it from a Foundry Prompt Agent | `e2b-dev/runtime` + `e2b-dev/code-interpreter` |

**A = ACA Sandboxes, B = Foundry hosted agent, C = AKS + agent-sandbox, D = BYO-AKS, E = E2B on Azure VM**. Upstream calls module-02 Solution A, module-03 Solution B and module-04 Solution C. Use module numbers when reading it. Run only the path you need: B needs steps 1–2; the full A example reuses the image and network created in step 3. ACA itself does not require AKS. D uses an existing cluster and its own approved sample, not an automatically created cluster from this page. E runs the open-source E2B Embed Docker Compose stack on a single nested-virtualization Azure VM.

**Prerequisites.** Bash, Git, curl, Python 3.10+ with the venv module (on Ubuntu/Debian install `python3-venv`), Azure CLI 2.80+, kubectl and azd 1.34+; install the Foundry extension with `azd ext install microsoft.foundry`. You need subscription Owner, or Contributor plus Role Based Access Control Administrator, and model quota in your selected region. For A, your identity also needs the `Container Apps SandboxGroup Data Owner` role ([Learn](https://learn.microsoft.com/azure/container-apps/sandboxes-overview#prerequisites)); the workshop's `sandbox-deploy.sh` assigns it when it can resolve your signed-in user and otherwise only prints a warning. Use a non-production subscription. For C, provide your actual public egress CIDR; this HTTP workshop app is not a production HTTPS/login deployment.

**1. Clone and configure.** Clone into new directories, then edit `.env`: set `SUBSCRIPTION_ID`, `LOCATION` and `RESOURCE_GROUP`; set `C_ALLOW_CIDR` if using C. Leave `SN` until step 2.

```bash
git clone --filter=blob:none --sparse --depth=1 https://github.com/david-xinyuwei/david-share.git
git -C david-share sparse-checkout set Agents/Azure-Agent-Sandbox-Hosting
cd david-share/Agents/Azure-Agent-Sandbox-Hosting
export HOSTING_REPO="$PWD"
git clone https://github.com/oxcp/ainotes.git "$HOME/ainotes"
git -C "$HOME/ainotes" checkout 905f2c2
cp config/.env.example .env
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

After editing `.env`, sign in and run the upstream prerequisite checker. Resolve failed tool, permission or quota prerequisites before creating resources. Keep this shell open: it holds `HOSTING_REPO`, the stable return directory, and the activated `.venv`.

```bash
az login
set -a && . "$HOSTING_REPO/.env" && set +a
az account set --subscription "$SUBSCRIPTION_ID"
(cd "$WORKSHOP_DIR/agenthost" && chmod +x check-prerequisites.sh && ./check-prerequisites.sh)
```

**2. Create the shared foundation.** [Module 1](https://github.com/oxcp/ainotes/blob/905f2c2/agenthost/module-01/README.md) creates the Foundry project/model, APIM, ACR, Storage and identity.

```bash
(cd "$WORKSHOP_DIR/agenthost/module-01" && chmod +x setup.sh && ./setup.sh)
az group show -g "$RESOURCE_GROUP" --query tags.deploymentSN -o tsv
```

Success: `Template deployed successfully.` and a non-empty suffix from the second command. Paste that suffix into `SN` in `.env`, then reload it so the derived resource names change together. Do not continue with `YOUR-DEPLOYMENT-SUFFIX`.

```bash
set -a && . "$HOSTING_REPO/.env" && set +a
```

**3. C — Deploy the AKS application.** Follow [Module 3](https://github.com/oxcp/ainotes/blob/905f2c2/agenthost/module-03/README.md). Preparation creates AKS/Kata, controller, image and PVC; it does not deploy the application. The separate `kubectl apply` creates the Sandbox and its Service.

```bash
cd "$WORKSHOP_DIR/agenthost/module-03"
chmod +x prepare-agent-sandbox.sh deploy-storage-private-link.sh
./prepare-agent-sandbox.sh
if [ "$(az storage account show -g "$RESOURCE_GROUP" -n "$ACA_STORAGE_ACCOUNT" --query publicNetworkAccess -o tsv)" = "Disabled" ]; then
  ./deploy-storage-private-link.sh
fi
kubectl apply -f agent-sandbox.yaml
kubectl wait sandbox agent-host -n "$NAMESPACE" --for=condition=Ready --timeout=5m
```

Success: the Sandbox reaches `Ready`. Now allow only your configured egress CIDR, obtain the actual application URL, and make a real request:

```bash
if [ -z "$C_ALLOW_CIDR" ] || [[ "$C_ALLOW_CIDR" == YOUR-* ]]; then
  echo "C_ALLOW_CIDR is not set: put your public egress CIDR in .env, reload it and run this block again" >&2
else
  kubectl patch service agent-host-lb -n "$NAMESPACE" --type merge \
    -p "{\"spec\":{\"loadBalancerSourceRanges\":[\"$C_ALLOW_CIDR\"]}}"
  kubectl wait service agent-host-lb -n "$NAMESPACE" --for=jsonpath='{.status.loadBalancer.ingress[0].ip}' --timeout=5m
  C_AGENT_HOST=$(kubectl get service agent-host-lb -n "$NAMESPACE" -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
  C_AGENT_URL="http://${C_AGENT_HOST}"
  printf 'C application: %s\n' "$C_AGENT_URL"
  curl --fail-with-body --show-error --max-time 30 "$C_AGENT_URL/ready"
  curl --fail-with-body --show-error --max-time 180 \
    -H 'Content-Type: application/json' \
    -d '{"query":"Where is Bangkok? Answer in one short sentence."}' "$C_AGENT_URL/reflect" | \
    python -c 'import json,sys; body=json.load(sys.stdin); answer=body.get("response"); print(json.dumps(body,ensure_ascii=False)); sys.exit(0 if isinstance(answer,str) and answer.strip() else "C invocation failed: non-empty response missing")'
fi
cd "$HOSTING_REPO"
```

If the first line prints the `C_ALLOW_CIDR` message, nothing else ran: set it, reload `.env` and run the block again. 
Open the printed URL in a browser to use the chat page. `/ready` must succeed and `/reflect` must return a non-empty `response`; a Ready pod alone is not an answering application. On failure inspect `kubectl get pods`, `kubectl describe pod` and `kubectl logs` in `NAMESPACE`; for unreachable HTTP also check the egress CIDR, Service address and network rules.

**4. A — Deploy the ACA sandbox agent.** [Module 4](https://github.com/oxcp/ainotes/blob/905f2c2/agenthost/module-04/README.md) creates the sandbox group. Its disk-image and sandbox steps are separate; the SDK commands below perform those operations rather than replay measurements. This full example reuses step 3's image/network. Choose a free `ACA_SUBNET_PREFIX` inside that VNet. Following the workshop, `aca-subnet` goes into the VNet of the AKS node resource group; [AKS documents modifying resources there as unsupported](https://learn.microsoft.com/azure/aks/faq) and deletes that group with the cluster. Treat this as a workshop shortcut; outside the workshop, give the sandbox group a delegated subnet in a VNet you own.

```bash
(cd "$WORKSHOP_DIR/agenthost/module-04" && chmod +x sandbox-deploy.sh && ./sandbox-deploy.sh)
NODE_RG=$(az aks show -g "$RESOURCE_GROUP" -n "$AKS_NAME" --query nodeResourceGroup -o tsv)
VNET=$(az network vnet list -g "$NODE_RG" --query "[0].name" -o tsv)
az network vnet subnet create -g "$NODE_RG" --vnet-name "$VNET" -n aca-subnet \
  --address-prefixes "$ACA_SUBNET_PREFIX" --delegations Microsoft.App/environments --query id -o tsv
```

Paste the printed subnet ID into `ACA_SUBNET_ID` in `.env`, then run from this repository:

```bash
cd "$HOSTING_REPO"
set -a && . ./.env && set +a
python tools/aca_sandbox.py vnet
python tools/aca_sandbox.py image
python tools/aca_sandbox.py volume
python tools/aca_sandbox.py create
python tools/aca_sandbox.py ask "Where is Bangkok? Answer in one short sentence."
```

Success: `create` reports Running and `ask` returns an actual answer. The answer is requested through sandbox exec; direct browser ingress is not implied. For the browser-port deployment use Module 4's port/IP configuration. If a setting is missing, fill it before retrying; image access failures require ACR permission, and private Blob access requires the VNet and private endpoint.

**5. B — Deploy and call the hosted agent.** Use [Module 2](https://github.com/oxcp/ainotes/blob/905f2c2/agenthost/module-02/README.md) from a new working directory outside the source clone. Bind the existing project, then deploy; do not run `azd provision` for B.

```bash
mkdir -p "$HOME/workshop-b" && cd "$HOME/workshop-b"
azd auth login
azd ai agent init -m "$WORKSHOP_DIR/agenthost/module-02/azure.yaml" --project-id "$PROJECT_ID"
cd maf-agent
sed -i "s/<SN>/$SN/g" azure.yaml
azd env set AZURE_SUBSCRIPTION_ID "$SUBSCRIPTION_ID"
azd env set AZURE_LOCATION "$LOCATION"
azd env set AZURE_RESOURCE_GROUP "$RESOURCE_GROUP"
azd env set AZURE_AI_PROJECT_ID "$PROJECT_ID"
azd env set FOUNDRY_PROJECT_ENDPOINT "$PROJECT_ENDPOINT"
azd env set AI_MODEL_DEPLOYMENT_NAME gpt-5.4-mini
azd env set AZURE_TENANT_ID "$(az account show --query tenantId -o tsv)"
azd deploy
azd ai agent invoke "Hi"
azd ai agent show
cd "$HOSTING_REPO"
```

Success: deployment finishes and `invoke` returns a real answer. `show` provides the deployed endpoint for API clients; the Foundry agent playground can also invoke it. Keep the default gateway route unless intentionally changing it. If deployment remains creating, inspect `azd ai agent monitor` and the portal status rather than treating timeout as success or automatically deleting the agent.

**6. D — Private-preview deployment.** This path is blocked without the product group's sample and subscription approval. Before running it, fill the BYOAKS values in `.env`, including `BYOAKS_SAMPLE_DIR`, and configure the sample's `AKS_RESOURCE_ID`, `HOSTING_IDENTITY_RESOURCE_ID`, `WORKLOAD_IDENTITY_RESOURCE_ID`, `STORAGE_ACCOUNT_RESOURCE_ID`, `ACR_RESOURCE_ID` and `APPLICATIONINSIGHTS_RESOURCE_ID` using its current guide. Feature registration alone is not approval.

**D1. Prepare the existing cluster's Kata pool.** Confirm this node SKU is available for your subscription/region and meets the approved preview requirements; do not recreate an existing pool of the same name.

```bash
az aks nodepool add -g "$BYOAKS_RESOURCE_GROUP" --cluster-name "$BYOAKS_CLUSTER" -n "$BYOAKS_KATA_POOL" \
  --os-sku AzureLinux --workload-runtime KataVmIsolation --node-vm-size "$BYOAKS_KATA_VM_SIZE" --node-count 1
```

**D2. Provision the binding from the approved sample directory.** Success means provision completes and foundry-system components become Ready; their count is not a success contract.

```bash
cd "$BYOAKS_SAMPLE_DIR"
azd config set auth.useAzCliAuth true
azd auth login
azd provision
az aks get-credentials -g "$BYOAKS_RESOURCE_GROUP" -n "$BYOAKS_CLUSTER" --overwrite-existing
kubectl get pods -n foundry-system
```

**D3. Configure the router network path only when needed.** The following subnet-NSG rule is the retained workshop recipe, not a universal production rule. Run it only if the product group confirms this ingress/source applies to your preview build and your subnet NSG blocks that route; otherwise use the approved network configuration.

```bash
ROUTER_IP=$(kubectl get svc foundry-router -n foundry-system -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
if [ -z "$ROUTER_IP" ]; then
  echo "foundry-router has no LoadBalancer address; resolve provisioning before deploying the agent" >&2
else
  az network nsg rule create -g "$BYOAKS_SUBNET_NSG_RG" --nsg-name "$BYOAKS_SUBNET_NSG" \
    -n Allow-AzureCloud-FoundryRouter-443 --priority 500 --direction Inbound --access Allow --protocol Tcp \
    --source-address-prefixes AzureCloud --destination-address-prefixes "$ROUTER_IP" --destination-port-ranges 443 \
    --query provisioningState -o tsv
fi
```

**D4. Deploy and invoke the application.** These commands remain in the sample directory. Success: deployment completes, invoke answers, and show displays the endpoint. On failures inspect the sample/controller logs and the approved storage, identity and network settings; do not automatically purge resources.

```bash
azd deploy
azd ai agent invoke "Hi"
azd ai agent show
cd "$HOSTING_REPO"
```

**7. E — Deploy E2B Embed on an Azure VM and build E2B's Code Interpreter template.** Use an Ubuntu 24.04 LTS Gen2 VM that exposes `/dev/kvm` (such as `Standard_D4ds_v7`) with a 128 GB OS disk and Docker Engine 27+ with Compose 2.24+, with your user in the `docker` group ([E2B host requirements](https://github.com/e2b-dev/runtime/blob/588e5b9500b0987bc5a700d91483b03f0ae7d2a2/embed/compose/README.md#requirements)). The template build needs the larger disk: on a 50 GB disk it had to be stopped with too little space left for the E2B database (`e-2026-10-15-latest`). Restrict the E2B ports to your client CIDR in the subnet NSG. The Compose stack lives in `embed/compose/`, not in the repository root. On the VM (over SSH), download its two files from the measured commit `588e5b9`, check their SHA-256 against our run's record, give the stack a hugepage pool of 4096 pages (8 GiB; the downloaded `.env` has no `HUGEPAGES` line, so Compose would use 2048, which holds one `code-interpreter-v1` sandbox), and start it. Each sandbox takes 1024 pages when it is created, so 4096 holds 3 at once; for more, raise the pool by 1024 per sandbox on a VM with the memory (8448 held 8 on a `Standard_D8ds_v7` in `e-2026-10-18-ci-scale`):

```bash
mkdir -p "$HOME/e2b" && cd "$HOME/e2b"
curl -fsSL --remote-name-all "https://raw.githubusercontent.com/e2b-dev/runtime/588e5b9500b0987bc5a700d91483b03f0ae7d2a2/embed/compose/{compose.yaml,.env}"
printf '%s  %s\n' \
  658429e02665fa9e1cc23411e0897b1e2db1867e6fa9c47fb551ac5a313b6b74 compose.yaml \
  484510816c685a4d6d24bff34d00b05c46306146c0be397507dc215390a182fa .env \
  | sha256sum -c - && printf '\nHUGEPAGES=4096\n' >> .env && docker compose up -d --wait
```

Success: `sha256sum` prints `compose.yaml: OK` and `.env: OK`, then `docker compose up` exits 0, which it does only after the `base` template is built (failures: [If `up` fails](https://github.com/e2b-dev/runtime/blob/588e5b9500b0987bc5a700d91483b03f0ae7d2a2/embed/compose/README.md#if-up-fails)). If a hash differs, nothing starts; run the whole block again, which downloads both files anew.

Then raise the test team's build workspace to 8192 MiB, wait 5 minutes, and build `code-interpreter-v1` with E2B's unchanged build script from the measured commit `162a2a2`. The workspace is a row in Embed's internal `project_limits` table, which E2B does not document: with the default 512 MiB the build ran out of space at step 8 (`e-2026-10-15-latest`), and so did a build started 16 s after the row was added, while one started 5 minutes later passed that step (`e-2026-10-17-ci-agent`):

```bash
cd "$HOME/e2b"
docker compose exec -T postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 -c "insert into public.project_limits (team_id, max_length_hours, concurrent_sandboxes, concurrent_template_builds, max_vcpu, max_ram_mb, disk_mb, events_ttl_days, default_free_disk_size_mb, max_disk_size_mb, max_free_disk_size_mb, api_team_rps_list) select id, max_length_hours, concurrent_sandboxes, concurrent_template_builds, max_vcpu, max_ram_mb, 8192, events_ttl_days, default_free_disk_size_mb, max_disk_size_mb, max_free_disk_size_mb, api_team_rps_list from public.team_limits where id = (select id from public.teams where name = 'local-dev team')"
sleep 300
sudo apt-get update && sudo apt-get install -y python3-venv
git clone --filter=blob:none https://github.com/e2b-dev/code-interpreter.git
git -C code-interpreter fetch origin 162a2a25b6a5ea5806749a437b96cbdc5bfc087e
git -C code-interpreter checkout 162a2a25b6a5ea5806749a437b96cbdc5bfc087e
python3 -m venv venv-build
venv-build/bin/pip install -r code-interpreter/template/requirements-dev.txt
docker compose exec -T ready cat /run/e2b/sdk.env > sdk.env && chmod 600 sdk.env
(set -a && . ./sdk.env && set +a && cd code-interpreter/template && ../../venv-build/bin/python build_prod.py)
```

Success: `psql` prints `INSERT 0 1`, and the build's last line is `Build finished, took …` after 30 steps: 15m26s on a new VM in `e-2026-10-18-ci-scale`, where these steps built it on the first attempt; 7m3s on host a in `e-2026-10-15-latest`, which reused cached steps. If a step fails with `error setting fc metrics`, run the last line again: in `e-2026-10-17-ci-agent` the next attempt passed (the VM had been restarted in between). `sdk.env` holds the stack's API key; keep it on the VM.

Back in the shell you kept open in step 1, set `E2B_API_URL` and `E2B_SANDBOX_URL` in `.env` to the VM's address and reload it. Install the E2B SDKs of the measured run, `e2b==2.56.0` and `e2b-code-interpreter==2.11.0` (Python 3.11+), check the health endpoint, enter the stack's API key without echoing it (`E2B_API_KEY` in `$HOME/e2b/sdk.env` on the VM), and ask the Prompt Agent one question:

```bash
cd "$HOSTING_REPO"
set -a && . "$HOSTING_REPO/.env" && set +a
python -m pip install e2b==2.56.0 e2b-code-interpreter==2.11.0
curl --fail-with-body --show-error --max-time 30 "$E2B_API_URL/health"
read -rsp "E2B_API_KEY: " E2B_API_KEY && export E2B_API_KEY && echo
python tools/e2b_agent.py "Where is Bangkok? Answer in one short sentence."
```

Success: `/health` returns HTTP 200 with the body `Health check successful`, and `tools/e2b_agent.py` prints the answer, such as `Bangkok is the capital city of Thailand in Southeast Asia.`, then one line on stderr with the tool calls and their `run_code` time, and exits 0 after deleting the sandbox, the conversation and the agent version it created. It uses `PROJECT_ENDPOINT` and `ACA_MODEL` from `.env` and your `az` sign-in for the Foundry token; exit code 2 names a missing setting, 1 a failure or a resource it could not delete.

**Done.** The selected path has an actual answering application and its usable entry, not merely a completed measurement command. Optional cold/warm tests, isolation checks and historical-number replay are in [VALIDATION.md](VALIDATION.md#tests-and-offline-checks).

**Offboard only after explicit owner approval; not part of deployment.** Each command below is its own block: run only the ones for resources you intend to remove. Stopping AKS saves compute charges, not all retained-resource charges.

Delete the A sandbox:

```bash
python tools/aca_sandbox.py delete
```

Stop the C cluster:

```bash
az aks stop -g "$RESOURCE_GROUP" -n "$AKS_NAME"
```

Stop the D cluster:

```bash
az aks stop -g "$BYOAKS_RESOURCE_GROUP" -n "$BYOAKS_CLUSTER"
```

Deallocate the E VM:

```bash
az vm deallocate -g "$E2B_RESOURCE_GROUP" -n "$E2B_VM_NAME"
```

Delete the resource group. This removes the shared foundation and A/B/C, and `az` asks you to confirm first:

```bash
az group delete -n "$RESOURCE_GROUP" --no-wait
```

**Repository.** [`tools/`](tools/) setup, measurement and checks · [`evidence/claims.json`](evidence/claims.json) canonical A–E claims · [`evidence/`](evidence/) redacted run records and `measurements.json` · [`images/`](images/) figures and icon ledger · [`config/`](config/) settings template · [`tests/`](tests/) offline tests (`python -m pytest -q`, run by CI on every push).
