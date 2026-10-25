# Measured Results

[README](../README.md) · [Testing](testing.md) · [Other language](results_CN.md)

## Inputs and Method

This run asks whether disabling up-front thinking and extending cache coverage changes time to the first visible answer. The five prompts below are verbatim inputs; every configuration uses the same source material and order.

1. Explain the request flow from the desktop client to a Claude model on Azure. Which components are shown in the test target architecture, and which are our prototype implementation choices?

2. Using that flow and the supplied code, where could a timeout or incomplete streamed response originate? Separate what these files establish from what would require additional evidence.

3. Continuing your analysis, propose the smallest checks that preserve the client's /v1/messages interface and the three independent model routes. What must be verified before attributing an error to a model?

4. Turn those checks into a concise five-turn validation checklist. Include conversation-history integrity, actual prompt-cache usage, first visible text, full-response completion, and token accounting; do not invent measurements.

5. Review your checklist against the observer code. Which evidence can it already retain, what additional client evidence is needed, and what sensitive information must not be logged? End with the main limits of this small workflow test.

[Complete material and matrix](../data/matrix.json)

Five valid model/mode combinations, two cache configurations and five dependent turns per cell. Fixed medium, stream=true, max_tokens=4096, no tools, no retries and one in-flight request. System-only ran before conversation caching; no cache flush or extra pre-warming. Both phases used Haiku disabled, Sonnet between_tools, Opus adaptive, Sonnet adaptive, then Haiku adaptive. Later histories come from each cell itself and are not byte-identical across cells.

## Observed Results

<img src="../images/latency-en.svg" width="880" alt="Measured first visible answer latency" />

Computed from the 50 records in this run. Blue: adaptive. Green: no up-front thinking. This is not a quality ranking.

| Model | Thinking | Cached prefix | N | Cache-read share | First text P50 (s) | E2E P50 (s) | Output P50 (tokens/s) | Model USD |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Opus 5.5 | adaptive | system | 5 | 28.27% | 9.321 | 18.334 | 95.78 | 0.258394 |
| Sonnet 5.5 | adaptive | system | 5 | 33.52% | 8.051 | 15.233 | 117.84 | 0.110115 |
| Sonnet 5.5 | between_tools | system | 5 | 39.96% | 0.954 | 7.991 | 114.76 | 0.073466 |
| Haiku 5.5 | adaptive | system | 5 | 32.81% | 4.235 | 7.160 | 183.51 | 0.004840 |
| Haiku 5.5 | disabled | system | 5 | 47.47% | 0.810 | 3.553 | 153.96 | 0.002472 |
| Opus 5.5 | adaptive | system + history | 5 | 69.25% | 7.293 | 16.022 | 90.86 | 0.193501 |
| Sonnet 5.5 | adaptive | system + history | 5 | 67.68% | 1.434 | 8.604 | 115.29 | 0.081004 |
| Sonnet 5.5 | between_tools | system + history | 5 | 70.68% | 0.893 | 7.874 | 112.64 | 0.060174 |
| Haiku 5.5 | adaptive | system + history | 5 | 71.04% | 2.910 | 5.917 | 172.62 | 0.003642 |
| Haiku 5.5 | disabled | system + history | 5 | 72.44% | 0.781 | 3.983 | 156.55 | 0.002288 |

## Timing Boundaries

Times start at client send. Headers means completed response headers; first body byte is the first response-body byte, not the first byte of the HTTP exchange. First SSE can be metadata/heartbeat, not visible text. A thinking event does not mark the start of model compute; omitted display can defer or group events. Post-SSE wait is computed per request before taking P50, not by subtracting medians.

| Case | N | Headers P50 s | First SSE P50 s | First text P50 s | Post-SSE wait P50 s | First text P95 s | Thinking requests |
|---|---:|---:|---:|---:|---:|---:|---:|
| opus-adaptive-system | 5 | 1.453 | 1.455 | 9.321 | 8.027 | 10.988 | 5/5 |
| sonnet-adaptive-system | 5 | 1.187 | 1.188 | 8.051 | 7.029 | 9.531 | 3/5 |
| sonnet-between-system | 5 | 0.952 | 0.953 | 0.954 | 0.001 | 2.408 | 0/5 |
| haiku-adaptive-system | 5 | 0.864 | 0.865 | 4.235 | 3.260 | 4.436 | 5/5 |
| haiku-disabled-system | 5 | 0.808 | 0.809 | 0.810 | 0.001 | 1.563 | 0/5 |
| opus-adaptive-conversation | 5 | 1.435 | 1.436 | 7.293 | 6.215 | 8.749 | 5/5 |
| sonnet-adaptive-conversation | 5 | 1.154 | 1.155 | 1.434 | 0.002 | 8.586 | 2/5 |
| sonnet-between-conversation | 5 | 0.879 | 0.881 | 0.893 | 0.001 | 0.986 | 0/5 |
| haiku-adaptive-conversation | 5 | 0.969 | 0.970 | 2.910 | 2.002 | 4.020 | 5/5 |
| haiku-disabled-conversation | 5 | 0.773 | 0.778 | 0.781 | 0.001 | 1.216 | 0/5 |

## Per-Turn Records

Token columns are token counts. Full requests, visible responses and event timing are in the evidence file.

| Case | Turn | First text s | E2E s | Input | Cache read | Cache write | Output | Thinking |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| opus-adaptive-system | 1 | 9.171 | 17.495 | 2018 | 0 | 1961 | 1768 | 797 |
| opus-adaptive-system | 2 | 10.773 | 18.334 | 3838 | 1961 | 0 | 1756 | 959 |
| opus-adaptive-system | 3 | 7.071 | 15.864 | 5654 | 1961 | 0 | 1444 | 503 |
| opus-adaptive-system | 4 | 9.321 | 18.717 | 7169 | 1961 | 0 | 1837 | 783 |
| opus-adaptive-system | 5 | 10.988 | 20.904 | 9071 | 1961 | 0 | 1957 | 845 |
| sonnet-adaptive-system | 1 | 1.622 | 8.757 | 2018 | 0 | 1961 | 1038 | 0 |
| sonnet-adaptive-system | 2 | 1.073 | 9.777 | 3106 | 1961 | 0 | 1048 | 0 |
| sonnet-adaptive-system | 3 | 8.051 | 15.233 | 4212 | 1961 | 0 | 1795 | 842 |
| sonnet-adaptive-system | 4 | 8.616 | 16.051 | 6078 | 1961 | 0 | 1847 | 851 |
| sonnet-adaptive-system | 5 | 9.531 | 16.571 | 7990 | 1961 | 0 | 1995 | 1006 |
| sonnet-between-system | 1 | 2.408 | 7.808 | 2017 | 0 | 1960 | 831 | 0 |
| sonnet-between-system | 2 | 0.700 | 7.991 | 2900 | 1960 | 0 | 917 | 0 |
| sonnet-between-system | 3 | 0.995 | 7.783 | 3877 | 1960 | 0 | 944 | 0 |
| sonnet-between-system | 4 | 0.865 | 8.285 | 4892 | 1960 | 0 | 978 | 0 |
| sonnet-between-system | 5 | 0.954 | 10.073 | 5935 | 1960 | 0 | 1144 | 0 |
| haiku-adaptive-system | 1 | 4.262 | 7.328 | 2018 | 0 | 1961 | 1552 | 791 |
| haiku-adaptive-system | 2 | 4.235 | 7.160 | 3622 | 1961 | 0 | 1314 | 680 |
| haiku-adaptive-system | 3 | 3.822 | 6.641 | 4996 | 1961 | 0 | 1131 | 549 |
| haiku-adaptive-system | 4 | 2.105 | 4.804 | 6198 | 1961 | 0 | 807 | 239 |
| haiku-adaptive-system | 5 | 4.436 | 7.461 | 7070 | 1961 | 0 | 1410 | 691 |
| haiku-disabled-system | 1 | 1.563 | 4.389 | 2017 | 0 | 1960 | 684 | 0 |
| haiku-disabled-system | 2 | 0.810 | 3.553 | 2753 | 1960 | 0 | 547 | 0 |
| haiku-disabled-system | 3 | 0.753 | 3.234 | 3360 | 1960 | 0 | 479 | 0 |
| haiku-disabled-system | 4 | 0.742 | 3.413 | 3910 | 1960 | 0 | 502 | 0 |
| haiku-disabled-system | 5 | 0.874 | 4.804 | 4477 | 1960 | 0 | 741 | 0 |
| opus-adaptive-conversation | 1 | 7.293 | 16.022 | 2018 | 0 | 2014 | 1747 | 697 |
| opus-adaptive-conversation | 2 | 8.054 | 18.054 | 3817 | 2014 | 1799 | 1636 | 653 |
| opus-adaptive-conversation | 3 | 6.088 | 13.685 | 5513 | 3813 | 1696 | 1164 | 390 |
| opus-adaptive-conversation | 4 | 4.541 | 13.207 | 6748 | 5509 | 1235 | 1200 | 299 |
| opus-adaptive-conversation | 5 | 8.749 | 18.627 | 8013 | 6744 | 1265 | 1741 | 655 |
| sonnet-adaptive-conversation | 1 | 1.434 | 7.260 | 2018 | 0 | 2014 | 837 | 0 |
| sonnet-adaptive-conversation | 2 | 1.029 | 8.604 | 2905 | 2014 | 887 | 942 | 0 |
| sonnet-adaptive-conversation | 3 | 0.998 | 8.385 | 3905 | 2901 | 1000 | 980 | 0 |
| sonnet-adaptive-conversation | 4 | 6.170 | 13.774 | 4954 | 3901 | 1049 | 1540 | 610 |
| sonnet-adaptive-conversation | 5 | 8.586 | 17.257 | 6559 | 4950 | 1605 | 2021 | 846 |
| sonnet-between-conversation | 1 | 0.986 | 7.066 | 2017 | 0 | 2013 | 889 | 0 |
| sonnet-between-conversation | 2 | 0.749 | 8.552 | 2958 | 2013 | 941 | 954 | 0 |
| sonnet-between-conversation | 3 | 0.830 | 7.874 | 3972 | 2954 | 1014 | 887 | 0 |
| sonnet-between-conversation | 4 | 0.937 | 6.643 | 4930 | 3968 | 958 | 740 | 0 |
| sonnet-between-conversation | 5 | 0.893 | 8.524 | 5735 | 4926 | 805 | 972 | 0 |
| haiku-adaptive-conversation | 1 | 4.020 | 7.702 | 2018 | 0 | 2014 | 1487 | 687 |
| haiku-adaptive-conversation | 2 | 2.910 | 6.552 | 3557 | 2014 | 1539 | 1131 | 403 |
| haiku-adaptive-conversation | 3 | 2.972 | 5.917 | 4748 | 3553 | 1191 | 968 | 361 |
| haiku-adaptive-conversation | 4 | 1.752 | 4.492 | 5787 | 4744 | 1039 | 693 | 175 |
| haiku-adaptive-conversation | 5 | 2.829 | 5.739 | 6545 | 5783 | 758 | 1044 | 370 |
| haiku-disabled-conversation | 1 | 1.216 | 4.276 | 2017 | 0 | 2013 | 798 | 0 |
| haiku-disabled-conversation | 2 | 0.755 | 3.983 | 2867 | 2013 | 850 | 589 | 0 |
| haiku-disabled-conversation | 3 | 0.781 | 3.603 | 3516 | 2863 | 649 | 564 | 0 |
| haiku-disabled-conversation | 4 | 0.759 | 3.354 | 4151 | 3512 | 635 | 538 | 0 |
| haiku-disabled-conversation | 5 | 0.942 | 4.184 | 4754 | 4147 | 603 | 644 | 0 |

## Limits and Sources

This is one fixed source-review workload, not customer production traffic. There is no answer-quality score, concurrent load test, AWS comparison or effort-level ranking. The no-up-front-thinking modes produced zero thinking tokens in this tool-free workload. Sonnet between_tools is not a universal full-off switch; Opus 5.5 cannot disable thinking. With five samples, P95 is the maximum, not a production-tail estimate.

Sonnet adaptive produced thinking in 3/5 and 2/5 requests in the two cache groups. Its latency difference cannot all be attributed to caching. Shorter answers or reduced reasoning can also affect timing; quality equivalence was not established.

[Requests and responses](../evidence/requests.json) · [Summary](../evidence/summary.json) · [Provenance and hashes](../evidence/provenance.json)

[Claude thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) · [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [LiteLLM v1.106.2 source](https://github.com/BerriAI/litellm/blob/v1.106.2/litellm/llms/anthropic/chat/transformation.py)
