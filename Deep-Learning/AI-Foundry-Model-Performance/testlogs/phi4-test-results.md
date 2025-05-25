**Test result for deploy phi4 on 1*NC48 A100 VM:**

```
(aml_env) root@linuxworkvm:~/AIFperformance# python  press-phi4-0314.py
Please enter the API service URL: https://aml-david-1-nc48.polandcentral.inference.ml.azure.com/score
Please enter the API Key: EhVrLXKhMdlkUvvmgrORZDVP1Ki4z10PaOqdnwx3znxqQ3BHyNyqJQQJ99BCAAAAAAAAAAAAINFRAZML06ur
Please enter the full name of the HuggingFace model for tokenizer loading: microsoft/phi-4
Tokenizer loaded successfully: microsoft/phi-4

Scenario: Text Generation, Concurrency: 1
  Request 1:
    TTFT          : 12.473 s
    Latency       : 12.473 s
    Throughput    : 68.07 tokens/s
    Prompt tokens : 132, Output tokens: 849

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 12.473 s
    Average throughput per req   : 68.07 tokens/s
    Overall throughput (sum)     : 68.07 tokens/s
    Batch duration (wall-clock)  : 12.496 s

Scenario: Text Generation, Concurrency: 2
  Request 1:
    TTFT          : 12.482 s
    Latency       : 12.482 s
    Throughput    : 70.90 tokens/s
    Prompt tokens : 132, Output tokens: 885
  Request 2:
    TTFT          : 26.099 s
    Latency       : 26.099 s
    Throughput    : 40.04 tokens/s
    Prompt tokens : 132, Output tokens: 1045

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 19.291 s
    Average throughput per req   : 55.47 tokens/s
    Overall throughput (sum)     : 110.94 tokens/s
    Batch duration (wall-clock)  : 26.129 s

Scenario: Question Answering, Concurrency: 1
  Request 1:
    TTFT          : 11.914 s
    Latency       : 11.914 s
    Throughput    : 72.10 tokens/s
    Prompt tokens : 114, Output tokens: 859

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 11.914 s
    Average throughput per req   : 72.10 tokens/s
    Overall throughput (sum)     : 72.10 tokens/s
    Batch duration (wall-clock)  : 11.935 s

Scenario: Question Answering, Concurrency: 2
  Request 1:
    TTFT          : 9.169 s
    Latency       : 9.169 s
    Throughput    : 70.02 tokens/s
    Prompt tokens : 114, Output tokens: 642
  Request 2:
    TTFT          : 19.162 s
    Latency       : 19.162 s
    Throughput    : 39.92 tokens/s
    Prompt tokens : 114, Output tokens: 765

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 14.165 s
    Average throughput per req   : 54.97 tokens/s
    Overall throughput (sum)     : 109.94 tokens/s
    Batch duration (wall-clock)  : 19.190 s

Scenario: Translation, Concurrency: 1
  Request 1:
    TTFT          : 2.499 s
    Latency       : 2.499 s
    Throughput    : 47.62 tokens/s
    Prompt tokens : 85, Output tokens: 119

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 2.499 s
    Average throughput per req   : 47.62 tokens/s
    Overall throughput (sum)     : 47.62 tokens/s
    Batch duration (wall-clock)  : 2.517 s

Scenario: Translation, Concurrency: 2
  Request 1:
    TTFT          : 2.501 s
    Latency       : 2.501 s
    Throughput    : 47.98 tokens/s
    Prompt tokens : 85, Output tokens: 120
  Request 2:
    TTFT          : 4.181 s
    Latency       : 4.181 s
    Throughput    : 28.46 tokens/s
    Prompt tokens : 85, Output tokens: 119

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 3.341 s
    Average throughput per req   : 38.22 tokens/s
    Overall throughput (sum)     : 76.45 tokens/s
    Batch duration (wall-clock)  : 4.206 s

Scenario: Text Summarization, Concurrency: 1
  Request 1:
    TTFT          : 2.811 s
    Latency       : 2.811 s
    Throughput    : 50.16 tokens/s
    Prompt tokens : 90, Output tokens: 141

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 2.811 s
    Average throughput per req   : 50.16 tokens/s
    Overall throughput (sum)     : 50.16 tokens/s
    Batch duration (wall-clock)  : 2.829 s

Scenario: Text Summarization, Concurrency: 2
  Request 1:
    TTFT          : 2.575 s
    Latency       : 2.575 s
    Throughput    : 48.15 tokens/s
    Prompt tokens : 90, Output tokens: 124
  Request 2:
    TTFT          : 4.413 s
    Latency       : 4.413 s
    Throughput    : 29.23 tokens/s
    Prompt tokens : 90, Output tokens: 129

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 3.494 s
    Average throughput per req   : 38.69 tokens/s
    Overall throughput (sum)     : 77.38 tokens/s
    Batch duration (wall-clock)  : 4.438 s

Scenario: Code Generation, Concurrency: 1
  Request 1:
    TTFT          : 20.441 s
    Latency       : 20.441 s
    Throughput    : 83.12 tokens/s
    Prompt tokens : 79, Output tokens: 1699

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 20.441 s
    Average throughput per req   : 83.12 tokens/s
    Overall throughput (sum)     : 83.12 tokens/s
    Batch duration (wall-clock)  : 20.462 s

Scenario: Code Generation, Concurrency: 2
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 17.370 s
    Latency       : 17.370 s
    Throughput    : 83.36 tokens/s
    Prompt tokens : 79, Output tokens: 1448
  Request 2:
    TTFT          : 16.017 s
    Latency       : 16.017 s
    Throughput    : 79.36 tokens/s
    Prompt tokens : 79, Output tokens: 1271

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 16.693 s
    Average throughput per req   : 81.36 tokens/s
    Overall throughput (sum)     : 162.72 tokens/s
    Batch duration (wall-clock)  : 47.685 s

Scenario: Chatbot, Concurrency: 1
  Request 1:
    TTFT          : 5.035 s
    Latency       : 5.035 s
    Throughput    : 64.55 tokens/s
    Prompt tokens : 60, Output tokens: 325

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 5.035 s
    Average throughput per req   : 64.55 tokens/s
    Overall throughput (sum)     : 64.55 tokens/s
    Batch duration (wall-clock)  : 5.052 s

Scenario: Chatbot, Concurrency: 2
  Request 1:
    TTFT          : 6.337 s
    Latency       : 6.337 s
    Throughput    : 67.39 tokens/s
    Prompt tokens : 60, Output tokens: 427
  Request 2:
    TTFT          : 11.039 s
    Latency       : 11.039 s
    Throughput    : 32.70 tokens/s
    Prompt tokens : 60, Output tokens: 361

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 8.688 s
    Average throughput per req   : 50.04 tokens/s
    Overall throughput (sum)     : 100.09 tokens/s
    Batch duration (wall-clock)  : 11.065 s

Scenario: Sentiment Analysis / Classification, Concurrency: 1
  Request 1:
    TTFT          : 1.009 s
    Latency       : 1.009 s
    Throughput    : 5.95 tokens/s
    Prompt tokens : 82, Output tokens: 6

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 1.009 s
    Average throughput per req   : 5.95 tokens/s
    Overall throughput (sum)     : 5.95 tokens/s
    Batch duration (wall-clock)  : 1.026 s

Scenario: Sentiment Analysis / Classification, Concurrency: 2
  Request 1:
    TTFT          : 1.146 s
    Latency       : 1.146 s
    Throughput    : 14.83 tokens/s
    Prompt tokens : 82, Output tokens: 17
  Request 2:
    TTFT          : 1.356 s
    Latency       : 1.356 s
    Throughput    : 5.16 tokens/s
    Prompt tokens : 82, Output tokens: 7

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 1.251 s
    Average throughput per req   : 9.99 tokens/s
    Overall throughput (sum)     : 19.99 tokens/s
    Batch duration (wall-clock)  : 1.382 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 1
  Request 1:
    TTFT          : 13.148 s
    Latency       : 13.148 s
    Throughput    : 76.44 tokens/s
    Prompt tokens : 99, Output tokens: 1005

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 13.148 s
    Average throughput per req   : 76.44 tokens/s
    Overall throughput (sum)     : 76.44 tokens/s
    Batch duration (wall-clock)  : 13.167 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 2
  Request 1:
    TTFT          : 14.184 s
    Latency       : 14.184 s
    Throughput    : 74.31 tokens/s
    Prompt tokens : 99, Output tokens: 1054
  Request 2:
    TTFT          : 26.283 s
    Latency       : 26.283 s
    Throughput    : 36.53 tokens/s
    Prompt tokens : 99, Output tokens: 960

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 20.233 s
    Average throughput per req   : 55.42 tokens/s
    Overall throughput (sum)     : 110.84 tokens/s
    Batch duration (wall-clock)  : 26.310 s
```

**Test result for deploy phi4 on 2*NC24 A100 VM( (When concurrency exceeds 2, a 429 error will occur.):**

```
  (aml_env) root@linuxworkvm:~/AIFperformance# python  press-phi4-0314.py
Please enter the API service URL: https://aml-david-2-nc24.polandcentral.inference.ml.azure.com/score
Please enter the API Key: 4s9oKys5yetlZnmP1hMcYXNUOUj5rIDIl2tJfX1ULebvgxFotfulJQQJ99BCAAAAAAAAAAAAINFRAZML1pQg
Please enter the full name of the HuggingFace model for tokenizer loading: microsoft/phi-4
tokenizer_config.json: 100%|█████████████████████████| 17.7k/17.7k [00:00<00:00, 7.65MB/s]
vocab.json: 100%|████████████████████████████████████| 1.61M/1.61M [00:00<00:00, 3.91MB/s]
merges.txt: 100%|██████████████████████████████████████| 917k/917k [00:00<00:00, 4.51MB/s]
tokenizer.json: 100%|████████████████████████████████| 4.25M/4.25M [00:00<00:00, 6.69MB/s]
added_tokens.json: 100%|█████████████████████████████| 2.50k/2.50k [00:00<00:00, 2.51MB/s]
special_tokens_map.json: 100%|█████████████████████████| 95.0/95.0 [00:00<00:00, 96.1kB/s]
Tokenizer loaded successfully: microsoft/phi-4

Scenario: Text Generation, Concurrency: 1
  Request 1:
    TTFT          : 19.546 s
    Latency       : 19.546 s
    Throughput    : 44.66 tokens/s
    Prompt tokens : 132, Output tokens: 873

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 19.546 s
    Average throughput per req   : 44.66 tokens/s
    Overall throughput (sum)     : 44.66 tokens/s
    Batch duration (wall-clock)  : 19.569 s

Scenario: Text Generation, Concurrency: 2
  Request 1:
    TTFT          : 19.542 s
    Latency       : 19.542 s
    Throughput    : 44.67 tokens/s
    Prompt tokens : 132, Output tokens: 873
  Request 2:
    TTFT          : 20.414 s
    Latency       : 20.414 s
    Throughput    : 45.46 tokens/s
    Prompt tokens : 132, Output tokens: 928

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 19.978 s
    Average throughput per req   : 45.07 tokens/s
    Overall throughput (sum)     : 90.13 tokens/s
    Batch duration (wall-clock)  : 20.444 s

Scenario: Question Answering, Concurrency: 1
  Request 1:
    TTFT          : 15.552 s
    Latency       : 15.552 s
    Throughput    : 44.56 tokens/s
    Prompt tokens : 114, Output tokens: 693

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 15.552 s
    Average throughput per req   : 44.56 tokens/s
    Overall throughput (sum)     : 44.56 tokens/s
    Batch duration (wall-clock)  : 15.573 s

Scenario: Question Answering, Concurrency: 2
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 15.207 s
    Latency       : 15.207 s
    Throughput    : 45.77 tokens/s
    Prompt tokens : 114, Output tokens: 696
  Request 2:
    TTFT          : 16.606 s
    Latency       : 16.606 s
    Throughput    : 45.10 tokens/s
    Prompt tokens : 114, Output tokens: 749

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 15.906 s
    Average throughput per req   : 45.44 tokens/s
    Overall throughput (sum)     : 90.87 tokens/s
    Batch duration (wall-clock)  : 48.279 s

Scenario: Translation, Concurrency: 1
  Request 1:
    TTFT          : 3.241 s
    Latency       : 3.241 s
    Throughput    : 33.32 tokens/s
    Prompt tokens : 85, Output tokens: 108

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 3.241 s
    Average throughput per req   : 33.32 tokens/s
    Overall throughput (sum)     : 33.32 tokens/s
    Batch duration (wall-clock)  : 3.258 s

Scenario: Translation, Concurrency: 2
  Request 1:
    TTFT          : 3.170 s
    Latency       : 3.170 s
    Throughput    : 33.12 tokens/s
    Prompt tokens : 85, Output tokens: 105
  Request 2:
    TTFT          : 5.856 s
    Latency       : 5.856 s
    Throughput    : 20.83 tokens/s
    Prompt tokens : 85, Output tokens: 122

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 4.513 s
    Average throughput per req   : 26.98 tokens/s
    Overall throughput (sum)     : 53.95 tokens/s
    Batch duration (wall-clock)  : 5.879 s

Scenario: Text Summarization, Concurrency: 1
  Request 1:
    TTFT          : 4.630 s
    Latency       : 4.630 s
    Throughput    : 37.36 tokens/s
    Prompt tokens : 90, Output tokens: 173

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 4.630 s
    Average throughput per req   : 37.36 tokens/s
    Overall throughput (sum)     : 37.36 tokens/s
    Batch duration (wall-clock)  : 4.647 s

Scenario: Text Summarization, Concurrency: 2
  Request 1:
    TTFT          : 3.650 s
    Latency       : 3.650 s
    Throughput    : 34.80 tokens/s
    Prompt tokens : 90, Output tokens: 127
  Request 2:
    TTFT          : 3.678 s
    Latency       : 3.678 s
    Throughput    : 34.81 tokens/s
    Prompt tokens : 90, Output tokens: 128

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 3.664 s
    Average throughput per req   : 34.80 tokens/s
    Overall throughput (sum)     : 69.60 tokens/s
    Batch duration (wall-clock)  : 3.700 s

Scenario: Code Generation, Concurrency: 1
  Request 1:
    TTFT          : 27.685 s
    Latency       : 27.685 s
    Throughput    : 51.58 tokens/s
    Prompt tokens : 79, Output tokens: 1428

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 27.685 s
    Average throughput per req   : 51.58 tokens/s
    Overall throughput (sum)     : 51.58 tokens/s
    Batch duration (wall-clock)  : 27.704 s

Scenario: Code Generation, Concurrency: 2
Attempt 1 failed: The read operation timed out
Attempt 2 failed: The read operation timed out
  Request 1:
    TTFT          : 25.714 s
    Latency       : 25.714 s
    Throughput    : 52.19 tokens/s
    Prompt tokens : 79, Output tokens: 1342
  Request 2:
    TTFT          : 26.907 s
    Latency       : 26.907 s
    Throughput    : 52.18 tokens/s
    Prompt tokens : 79, Output tokens: 1404

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 26.310 s
    Average throughput per req   : 52.18 tokens/s
    Overall throughput (sum)     : 104.37 tokens/s
    Batch duration (wall-clock)  : 90.229 s

Scenario: Chatbot, Concurrency: 1
  Request 1:
    TTFT          : 9.349 s
    Latency       : 9.349 s
    Throughput    : 43.96 tokens/s
    Prompt tokens : 60, Output tokens: 411

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 9.349 s
    Average throughput per req   : 43.96 tokens/s
    Overall throughput (sum)     : 43.96 tokens/s
    Batch duration (wall-clock)  : 9.367 s

Scenario: Chatbot, Concurrency: 2
  Request 1:
    TTFT          : 8.554 s
    Latency       : 8.554 s
    Throughput    : 43.37 tokens/s
    Prompt tokens : 60, Output tokens: 371
  Request 2:
    TTFT          : 10.521 s
    Latency       : 10.521 s
    Throughput    : 44.29 tokens/s
    Prompt tokens : 60, Output tokens: 466

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 9.537 s
    Average throughput per req   : 43.83 tokens/s
    Overall throughput (sum)     : 87.67 tokens/s
    Batch duration (wall-clock)  : 10.545 s

Scenario: Sentiment Analysis / Classification, Concurrency: 1
  Request 1:
    TTFT          : 1.235 s
    Latency       : 1.235 s
    Throughput    : 12.96 tokens/s
    Prompt tokens : 82, Output tokens: 16

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 1.235 s
    Average throughput per req   : 12.96 tokens/s
    Overall throughput (sum)     : 12.96 tokens/s
    Batch duration (wall-clock)  : 1.252 s

Scenario: Sentiment Analysis / Classification, Concurrency: 2
  Request 1:
    TTFT          : 1.045 s
    Latency       : 1.045 s
    Throughput    : 6.70 tokens/s
    Prompt tokens : 82, Output tokens: 7
  Request 2:
    TTFT          : 1.270 s
    Latency       : 1.270 s
    Throughput    : 13.39 tokens/s
    Prompt tokens : 82, Output tokens: 17

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 1.157 s
    Average throughput per req   : 10.04 tokens/s
    Overall throughput (sum)     : 20.09 tokens/s
    Batch duration (wall-clock)  : 1.293 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 1
  Request 1:
    TTFT          : 20.184 s
    Latency       : 20.184 s
    Throughput    : 47.12 tokens/s
    Prompt tokens : 99, Output tokens: 951

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 20.184 s
    Average throughput per req   : 47.12 tokens/s
    Overall throughput (sum)     : 47.12 tokens/s
    Batch duration (wall-clock)  : 20.202 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 2
  Request 1:
    TTFT          : 22.688 s
    Latency       : 22.688 s
    Throughput    : 47.56 tokens/s
    Prompt tokens : 99, Output tokens: 1079
  Request 2:
    TTFT          : 24.621 s
    Latency       : 24.621 s
    Throughput    : 46.91 tokens/s
    Prompt tokens : 99, Output tokens: 1155

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 23.655 s
    Average throughput per req   : 47.23 tokens/s
    Overall throughput (sum)     : 94.47 tokens/s
    Batch duration (wall-clock)  : 24.648 s
```



**Test result for deploy phi4 on 1*NC24 A100 VM( (When concurrency exceeds 2, a 429 error will occur.):**

```
(aml_env) root@linuxworkvm:~/AIFperformance# python  press-phi4-0314.py
Please enter the API service URL: https://aml-david-1-nc24.polandcentral.inference.ml.azure.com/score
Please enter the API Key: 76WXPsoTlX02RIrijwJdUQtDL5K1iIuOqT9vRhOMtC4p2zwRlP9IJQQJ99BCAAAAAAAAAAAAINFRAZMLjTTD
Please enter the full name of the HuggingFace model for tokenizer loading: microsoft/phi-4
Tokenizer loaded successfully: microsoft/phi-4

Scenario: Text Generation, Concurrency: 1
  Request 1:
    TTFT          : 19.497 s
    Latency       : 19.497 s
    Throughput    : 44.78 tokens/s
    Prompt tokens : 132, Output tokens: 873

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 19.497 s
    Average throughput per req   : 44.78 tokens/s
    Overall throughput (sum)     : 44.78 tokens/s
    Batch duration (wall-clock)  : 19.521 s

Scenario: Text Generation, Concurrency: 2
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 20.401 s
    Latency       : 20.401 s
    Throughput    : 45.49 tokens/s
    Prompt tokens : 132, Output tokens: 928
  Request 2:
    TTFT          : 28.750 s
    Latency       : 28.750 s
    Throughput    : 33.77 tokens/s
    Prompt tokens : 132, Output tokens: 971

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 24.576 s
    Average throughput per req   : 39.63 tokens/s
    Overall throughput (sum)     : 79.26 tokens/s
    Batch duration (wall-clock)  : 60.422 s

Scenario: Question Answering, Concurrency: 1
  Request 1:
    TTFT          : 15.943 s
    Latency       : 15.943 s
    Throughput    : 46.04 tokens/s
    Prompt tokens : 114, Output tokens: 734

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 15.943 s
    Average throughput per req   : 46.04 tokens/s
    Overall throughput (sum)     : 46.04 tokens/s
    Batch duration (wall-clock)  : 15.962 s

Scenario: Question Answering, Concurrency: 2
  Request 1:
    TTFT          : 16.011 s
    Latency       : 16.011 s
    Throughput    : 47.09 tokens/s
    Prompt tokens : 114, Output tokens: 754
  Request 2:
    TTFT          : 27.537 s
    Latency       : 27.537 s
    Throughput    : 19.57 tokens/s
    Prompt tokens : 114, Output tokens: 539

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 21.774 s
    Average throughput per req   : 33.33 tokens/s
    Overall throughput (sum)     : 66.67 tokens/s
    Batch duration (wall-clock)  : 27.563 s

Scenario: Translation, Concurrency: 1
  Request 1:
    TTFT          : 3.411 s
    Latency       : 3.411 s
    Throughput    : 34.59 tokens/s
    Prompt tokens : 85, Output tokens: 118

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 3.411 s
    Average throughput per req   : 34.59 tokens/s
    Overall throughput (sum)     : 34.59 tokens/s
    Batch duration (wall-clock)  : 3.429 s

Scenario: Translation, Concurrency: 2
  Request 1:
    TTFT          : 6.052 s
    Latency       : 6.052 s
    Throughput    : 39.99 tokens/s
    Prompt tokens : 85, Output tokens: 242
  Request 2:
    TTFT          : 15.796 s
    Latency       : 15.796 s
    Throughput    : 28.55 tokens/s
    Prompt tokens : 85, Output tokens: 451

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 10.924 s
    Average throughput per req   : 34.27 tokens/s
    Overall throughput (sum)     : 68.54 tokens/s
    Batch duration (wall-clock)  : 15.822 s

Scenario: Text Summarization, Concurrency: 1
  Request 1:
    TTFT          : 3.369 s
    Latency       : 3.369 s
    Throughput    : 33.84 tokens/s
    Prompt tokens : 90, Output tokens: 114

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 3.369 s
    Average throughput per req   : 33.84 tokens/s
    Overall throughput (sum)     : 33.84 tokens/s
    Batch duration (wall-clock)  : 3.387 s

Scenario: Text Summarization, Concurrency: 2
  Request 1:
    TTFT          : 4.376 s
    Latency       : 4.376 s
    Throughput    : 36.56 tokens/s
    Prompt tokens : 90, Output tokens: 160
  Request 2:
    TTFT          : 8.259 s
    Latency       : 8.259 s
    Throughput    : 22.88 tokens/s
    Prompt tokens : 90, Output tokens: 189

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 6.317 s
    Average throughput per req   : 29.72 tokens/s
    Overall throughput (sum)     : 59.45 tokens/s
    Batch duration (wall-clock)  : 8.283 s

Scenario: Code Generation, Concurrency: 1
  Request 1:
    TTFT          : 26.504 s
    Latency       : 26.504 s
    Throughput    : 52.26 tokens/s
    Prompt tokens : 79, Output tokens: 1385

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 26.504 s
    Average throughput per req   : 52.26 tokens/s
    Overall throughput (sum)     : 52.26 tokens/s
    Batch duration (wall-clock)  : 26.523 s

Scenario: Code Generation, Concurrency: 2
Attempt 1 failed: The read operation timed out
Attempt 2 failed: The read operation timed out
Attempt 3 failed: The read operation timed out
  Request 1:
    TTFT          : 27.772 s
    Latency       : 27.772 s
    Throughput    : 53.22 tokens/s
    Prompt tokens : 79, Output tokens: 1478

  Summary for concurrency 2:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 27.772 s
    Average throughput per req   : 53.22 tokens/s
    Overall throughput (sum)     : 53.22 tokens/s
    Batch duration (wall-clock)  : 93.942 s

Scenario: Chatbot, Concurrency: 1
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 8.366 s
    Latency       : 8.366 s
    Throughput    : 41.24 tokens/s
    Prompt tokens : 60, Output tokens: 345

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 8.366 s
    Average throughput per req   : 41.24 tokens/s
    Overall throughput (sum)     : 41.24 tokens/s
    Batch duration (wall-clock)  : 40.031 s

Scenario: Chatbot, Concurrency: 2
  Request 1:
    TTFT          : 7.972 s
    Latency       : 7.972 s
    Throughput    : 43.15 tokens/s
    Prompt tokens : 60, Output tokens: 344
  Request 2:
    TTFT          : 16.156 s
    Latency       : 16.156 s
    Throughput    : 24.08 tokens/s
    Prompt tokens : 60, Output tokens: 389

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 12.064 s
    Average throughput per req   : 33.61 tokens/s
    Overall throughput (sum)     : 67.23 tokens/s
    Batch duration (wall-clock)  : 16.182 s

Scenario: Sentiment Analysis / Classification, Concurrency: 1
  Request 1:
    TTFT          : 1.241 s
    Latency       : 1.241 s
    Throughput    : 12.89 tokens/s
    Prompt tokens : 82, Output tokens: 16

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 1.241 s
    Average throughput per req   : 12.89 tokens/s
    Overall throughput (sum)     : 12.89 tokens/s
    Batch duration (wall-clock)  : 1.258 s

Scenario: Sentiment Analysis / Classification, Concurrency: 2
  Request 1:
    TTFT          : 1.035 s
    Latency       : 1.035 s
    Throughput    : 6.76 tokens/s
    Prompt tokens : 82, Output tokens: 7
  Request 2:
    TTFT          : 1.423 s
    Latency       : 1.423 s
    Throughput    : 9.84 tokens/s
    Prompt tokens : 82, Output tokens: 14

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 1.229 s
    Average throughput per req   : 8.30 tokens/s
    Overall throughput (sum)     : 16.60 tokens/s
    Batch duration (wall-clock)  : 1.447 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 1
  Request 1:
    TTFT          : 19.793 s
    Latency       : 19.793 s
    Throughput    : 47.29 tokens/s
    Prompt tokens : 99, Output tokens: 936

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 19.793 s
    Average throughput per req   : 47.29 tokens/s
    Overall throughput (sum)     : 47.29 tokens/s
    Batch duration (wall-clock)  : 19.812 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 2
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 19.782 s
    Latency       : 19.782 s
    Throughput    : 46.76 tokens/s
    Prompt tokens : 99, Output tokens: 925
  Request 2:
    TTFT          : 25.978 s
    Latency       : 25.978 s
    Throughput    : 42.04 tokens/s
    Prompt tokens : 99, Output tokens: 1092

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 22.880 s
    Average throughput per req   : 44.40 tokens/s
    Overall throughput (sum)     : 88.79 tokens/s
    Batch duration (wall-clock)  : 57.649 s
```

