# Measured Results

[README](../README.md) · [Testing](testing.md) · [中文](results_CN.md)

## Inputs and Method

This run asks whether disabling up-front thinking and extending cache coverage changes time to the first visible answer. The five prompts below are verbatim inputs; every configuration uses the same source material and order.

1. Explain the request flow from the desktop client to a Claude model on Azure. Which components are shown in the test target architecture, and which are our prototype implementation choices?

2. Using that flow and the supplied code, where could a timeout or incomplete streamed response originate? Separate what these files establish from what would require additional evidence.

3. Continuing your analysis, propose the smallest checks that preserve the client's /v1/messages interface and the three independent model routes. What must be verified before attributing an error to a model?

4. Turn those checks into a concise five-turn validation checklist. Include conversation-history integrity, actual prompt-cache usage, first visible text, full-response completion, and token accounting; do not invent measurements.

5. Review your checklist against the observer code. Which evidence can it already retain, what additional client evidence is needed, and what sensitive information must not be logged? End with the main limits of this small workflow test.

[Complete material and matrix](../data/matrix.json)

Five valid model/mode combinations, two cache configurations and five dependent turns per cell. Fixed medium, stream=true, max_tokens=4096, no tools, no retries and one in-flight request. System-only ran before conversation caching; no cache flush or extra pre-warming. Both phases used Haiku disabled, Sonnet between_tools, Opus adaptive, Sonnet adaptive, then Haiku adaptive. Later histories come from each cell itself and are not byte-identical across cells.

That order belongs to the recorded experiment. The public runner uses the case order in matrix.json, whose default differs. A new report describes its own run, not an exact replay of the historical execution order.

## Observed Results

<img src="../images/latency-en.svg" width="520" alt="First-text timing of five requests per configuration" />

Generated from the 50 recorded requests: each dot is one request and the horizontal axis is seconds. Small vertical offsets only distinguish turns and carry no metric value. Blue is adaptive; green has no up-front thinking. This is not a quality ranking. [Source](../evidence/requests.json)

First-text and cache summaries are in the README. The following tables retain the other metrics for all ten configurations. Each cell covers five turns. Output rate includes thinking; visible rate subtracts thinking tokens. Both divide by full E2E, not isolated decode time.

**Full completion P50, seconds**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 18.334 | 16.022 |
| Sonnet 5.5<br>adaptive | 15.233 | 8.604 |
| Sonnet 5.5<br>between_tools | 7.991 | 7.874 |
| Haiku 5.5<br>adaptive | 7.160 | 5.917 |
| Haiku 5.5<br>disabled | 3.553 | 3.983 |

**Output P50, tokens/s, including thinking**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 95.78 | 90.86 |
| Sonnet 5.5<br>adaptive | 117.84 | 115.29 |
| Sonnet 5.5<br>between_tools | 114.76 | 112.64 |
| Haiku 5.5<br>adaptive | 183.51 | 172.62 |
| Haiku 5.5<br>disabled | 153.96 | 156.55 |

**Visible output P50, tokens/s**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 55.50 | 58.30 |
| Sonnet 5.5<br>adaptive | 62.56 | 109.48 |
| Sonnet 5.5<br>between_tools | 114.76 | 112.64 |
| Haiku 5.5<br>adaptive | 96.37 | 111.11 |
| Haiku 5.5<br>disabled | 153.96 | 156.55 |

**Estimated model cost, USD**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 0.258394 | 0.193501 |
| Sonnet 5.5<br>adaptive | 0.110115 | 0.081004 |
| Sonnet 5.5<br>between_tools | 0.073466 | 0.060174 |
| Haiku 5.5<br>adaptive | 0.004840 | 0.003642 |
| Haiku 5.5<br>disabled | 0.002472 | 0.002288 |

## Timing Boundaries

Times start at client send. Headers means completed response headers; first body byte is the first response-body byte, not the first byte of the HTTP exchange. First SSE can be metadata/heartbeat, not visible text. A thinking event does not mark the start of model compute; omitted display can defer or group events. Post-SSE wait is computed per request before taking P50, not by subtracting medians.

## Per-Turn Records

Total input, read, written, output and thinking columns are token counts. Total input = uncached + read + written; visible output = output - thinking. Full requests, responses and event timing are in the evidence file. Each P95 is the maximum of five turns.

### Opus 5.5 / adaptive / system

`opus-adaptive-system`

Requests with thinking: 5/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 1.453 | 1.671 |
| First SSE | 1.455 | 1.671 |
| First text | 9.321 | 10.988 |
| Post-SSE wait | 8.027 | 9.960 |
| Full end | 18.334 | 20.904 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 9.171 | 17.495 |
| 2 | 10.773 | 18.334 |
| 3 | 7.071 | 15.864 |
| 4 | 9.321 | 18.717 |
| 5 | 10.988 | 20.904 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 1961 |
| 2 | 3838 | 1961 | 0 |
| 3 | 5654 | 1961 | 0 |
| 4 | 7169 | 1961 | 0 |
| 5 | 9071 | 1961 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1768 | 797 |
| 2 | 1756 | 959 |
| 3 | 1444 | 503 |
| 4 | 1837 | 783 |
| 5 | 1957 | 845 |

### Sonnet 5.5 / adaptive / system

`sonnet-adaptive-system`

Requests with thinking: 3/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 1.187 | 1.621 |
| First SSE | 1.188 | 1.621 |
| First text | 8.051 | 9.531 |
| Post-SSE wait | 7.029 | 8.248 |
| Full end | 15.233 | 16.571 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 1.622 | 8.757 |
| 2 | 1.073 | 9.777 |
| 3 | 8.051 | 15.233 |
| 4 | 8.616 | 16.051 |
| 5 | 9.531 | 16.571 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 1961 |
| 2 | 3106 | 1961 | 0 |
| 3 | 4212 | 1961 | 0 |
| 4 | 6078 | 1961 | 0 |
| 5 | 7990 | 1961 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1038 | 0 |
| 2 | 1048 | 0 |
| 3 | 1795 | 842 |
| 4 | 1847 | 851 |
| 5 | 1995 | 1006 |

### Sonnet 5.5 / between_tools / system

`sonnet-between-system`

Requests with thinking: 0/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.952 | 2.406 |
| First SSE | 0.953 | 2.406 |
| First text | 0.954 | 2.408 |
| Post-SSE wait | 0.001 | 0.001 |
| Full end | 7.991 | 10.073 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 2.408 | 7.808 |
| 2 | 0.700 | 7.991 |
| 3 | 0.995 | 7.783 |
| 4 | 0.865 | 8.285 |
| 5 | 0.954 | 10.073 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 1960 |
| 2 | 2900 | 1960 | 0 |
| 3 | 3877 | 1960 | 0 |
| 4 | 4892 | 1960 | 0 |
| 5 | 5935 | 1960 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 831 | 0 |
| 2 | 917 | 0 |
| 3 | 944 | 0 |
| 4 | 978 | 0 |
| 5 | 1144 | 0 |

### Haiku 5.5 / adaptive / system

`haiku-adaptive-system`

Requests with thinking: 5/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.864 | 1.002 |
| First SSE | 0.865 | 1.003 |
| First text | 4.235 | 4.436 |
| Post-SSE wait | 3.260 | 3.590 |
| Full end | 7.160 | 7.461 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 4.262 | 7.328 |
| 2 | 4.235 | 7.160 |
| 3 | 3.822 | 6.641 |
| 4 | 2.105 | 4.804 |
| 5 | 4.436 | 7.461 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 1961 |
| 2 | 3622 | 1961 | 0 |
| 3 | 4996 | 1961 | 0 |
| 4 | 6198 | 1961 | 0 |
| 5 | 7070 | 1961 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1552 | 791 |
| 2 | 1314 | 680 |
| 3 | 1131 | 549 |
| 4 | 807 | 239 |
| 5 | 1410 | 691 |

### Haiku 5.5 / disabled / system

`haiku-disabled-system`

Requests with thinking: 0/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.808 | 1.538 |
| First SSE | 0.809 | 1.554 |
| First text | 0.810 | 1.563 |
| Post-SSE wait | 0.001 | 0.008 |
| Full end | 3.553 | 4.804 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 1.563 | 4.389 |
| 2 | 0.810 | 3.553 |
| 3 | 0.753 | 3.234 |
| 4 | 0.742 | 3.413 |
| 5 | 0.874 | 4.804 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 1960 |
| 2 | 2753 | 1960 | 0 |
| 3 | 3360 | 1960 | 0 |
| 4 | 3910 | 1960 | 0 |
| 5 | 4477 | 1960 | 0 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 684 | 0 |
| 2 | 547 | 0 |
| 3 | 479 | 0 |
| 4 | 502 | 0 |
| 5 | 741 | 0 |

### Opus 5.5 / adaptive / history

`opus-adaptive-conversation`

Requests with thinking: 5/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 1.435 | 1.677 |
| First SSE | 1.436 | 1.678 |
| First text | 7.293 | 8.749 |
| Post-SSE wait | 6.215 | 7.191 |
| Full end | 16.022 | 18.627 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 7.293 | 16.022 |
| 2 | 8.054 | 18.054 |
| 3 | 6.088 | 13.685 |
| 4 | 4.541 | 13.207 |
| 5 | 8.749 | 18.627 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 2014 |
| 2 | 3817 | 2014 | 1799 |
| 3 | 5513 | 3813 | 1696 |
| 4 | 6748 | 5509 | 1235 |
| 5 | 8013 | 6744 | 1265 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1747 | 697 |
| 2 | 1636 | 653 |
| 3 | 1164 | 390 |
| 4 | 1200 | 299 |
| 5 | 1741 | 655 |

### Sonnet 5.5 / adaptive / history

`sonnet-adaptive-conversation`

Requests with thinking: 2/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 1.154 | 1.432 |
| First SSE | 1.155 | 1.433 |
| First text | 1.434 | 8.586 |
| Post-SSE wait | 0.002 | 7.282 |
| Full end | 8.604 | 17.257 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 1.434 | 7.260 |
| 2 | 1.029 | 8.604 |
| 3 | 0.998 | 8.385 |
| 4 | 6.170 | 13.774 |
| 5 | 8.586 | 17.257 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 2014 |
| 2 | 2905 | 2014 | 887 |
| 3 | 3905 | 2901 | 1000 |
| 4 | 4954 | 3901 | 1049 |
| 5 | 6559 | 4950 | 1605 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 837 | 0 |
| 2 | 942 | 0 |
| 3 | 980 | 0 |
| 4 | 1540 | 610 |
| 5 | 2021 | 846 |

### Sonnet 5.5 / between_tools / history

`sonnet-between-conversation`

Requests with thinking: 0/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.879 | 0.984 |
| First SSE | 0.881 | 0.985 |
| First text | 0.893 | 0.986 |
| Post-SSE wait | 0.001 | 0.012 |
| Full end | 7.874 | 8.552 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 0.986 | 7.066 |
| 2 | 0.749 | 8.552 |
| 3 | 0.830 | 7.874 |
| 4 | 0.937 | 6.643 |
| 5 | 0.893 | 8.524 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 2013 |
| 2 | 2958 | 2013 | 941 |
| 3 | 3972 | 2954 | 1014 |
| 4 | 4930 | 3968 | 958 |
| 5 | 5735 | 4926 | 805 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 889 | 0 |
| 2 | 954 | 0 |
| 3 | 887 | 0 |
| 4 | 740 | 0 |
| 5 | 972 | 0 |

### Haiku 5.5 / adaptive / history

`haiku-adaptive-conversation`

Requests with thinking: 5/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.969 | 1.123 |
| First SSE | 0.970 | 1.124 |
| First text | 2.910 | 4.020 |
| Post-SSE wait | 2.002 | 2.895 |
| Full end | 5.917 | 7.702 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 4.020 | 7.702 |
| 2 | 2.910 | 6.552 |
| 3 | 2.972 | 5.917 |
| 4 | 1.752 | 4.492 |
| 5 | 2.829 | 5.739 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2018 | 0 | 2014 |
| 2 | 3557 | 2014 | 1539 |
| 3 | 4748 | 3553 | 1191 |
| 4 | 5787 | 4744 | 1039 |
| 5 | 6545 | 5783 | 758 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 1487 | 687 |
| 2 | 1131 | 403 |
| 3 | 968 | 361 |
| 4 | 693 | 175 |
| 5 | 1044 | 370 |

### Haiku 5.5 / disabled / history

`haiku-disabled-conversation`

Requests with thinking: 0/5.

| Timing point | P50 s | P95 s |
|---|---:|---:|
| Headers | 0.773 | 1.204 |
| First SSE | 0.778 | 1.205 |
| First text | 0.781 | 1.216 |
| Post-SSE wait | 0.001 | 0.011 |
| Full end | 3.983 | 4.276 |

| Turn | First text s | E2E s |
|---:|---:|---:|
| 1 | 1.216 | 4.276 |
| 2 | 0.755 | 3.983 |
| 3 | 0.781 | 3.603 |
| 4 | 0.759 | 3.354 |
| 5 | 0.942 | 4.184 |

| Turn | Total input | Read | Written |
|---:|---:|---:|---:|
| 1 | 2017 | 0 | 2013 |
| 2 | 2867 | 2013 | 850 |
| 3 | 3516 | 2863 | 649 |
| 4 | 4151 | 3512 | 635 |
| 5 | 4754 | 4147 | 603 |

| Turn | Output | Thinking |
|---:|---:|---:|
| 1 | 798 | 0 |
| 2 | 589 | 0 |
| 3 | 564 | 0 |
| 4 | 538 | 0 |
| 5 | 644 | 0 |

## Limits and Sources

This is one fixed source-review workload, not customer production traffic. There is no answer-quality score, concurrent load test, AWS comparison or effort-level ranking. The no-up-front-thinking modes produced zero thinking tokens in this tool-free workload. Sonnet between_tools is not a universal full-off switch; Opus 5.5 cannot disable thinking. With five samples, P95 is the maximum, not a production-tail estimate.

Sonnet adaptive produced thinking in 3/5 and 2/5 requests in the two cache groups. Its latency difference cannot all be attributed to caching. Shorter answers or reduced reasoning can also affect timing; quality equivalence was not established.

[Requests and responses](../evidence/requests.json) · [Summary](../evidence/summary.json) · [Provenance and hashes](../evidence/provenance.json)

[Claude thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) · [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [LiteLLM v1.106.2 source](https://github.com/BerriAI/litellm/blob/v1.106.2/litellm/llms/anthropic/chat/transformation.py)
