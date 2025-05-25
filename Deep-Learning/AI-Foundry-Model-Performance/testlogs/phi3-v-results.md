**Test result for deploy phi3-v on 1*NC24 A100 VM:**

```
(aml_env) root@linuxworkvm:~/AIFperformance# python  press-phi3v-20250315.py
Please enter the API service URL (default: https://custom-endpoint-1742021907.polandcentral.inference.ml.azure.com/score): 
Please enter the API Key (default is configured): 
Please enter the HuggingFace model name for loading the tokenizer (default: gpt2, leave blank to skip loading): microsoft/Phi-3.5-vision-instruct
Tokenizer loaded successfully: microsoft/Phi-3.5-vision-instruct

Starting load test: Concurrency=1, Total Requests=1
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=4.029s, TTFT=4.029s, Throughput=37.23 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 4.029 s
    Latency       : 4.029 s
    Throughput    : 37.23 tokens/s
    Prompt tokens : 34, Output tokens: 150

Summary for concurrency=1:
  Successful requests          : 1
  Failed requests              : 0
  Average TTFT per request     : 4.029 s
  Average throughput per req   : 37.23 tokens/s
  Overall throughput (sum)     : 37.23 tokens/s
  Batch duration (wall-clock)  : 4.037 s


Starting load test: Concurrency=2, Total Requests=2
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.986s, TTFT=3.986s, Throughput=36.38 tokens/s
Iteration 1: HTTPError 408: Request Timeout
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.802s, TTFT=3.802s, Throughput=33.66 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 3.986 s
    Latency       : 3.986 s
    Throughput    : 36.38 tokens/s
    Prompt tokens : 34, Output tokens: 145
  Request 2:
    TTFT          : 3.802 s
    Latency       : 3.802 s
    Throughput    : 33.66 tokens/s
    Prompt tokens : 34, Output tokens: 128

Summary for concurrency=2:
  Successful requests          : 2
  Failed requests              : 0
  Average TTFT per request     : 3.894 s
  Average throughput per req   : 35.02 tokens/s
  Overall throughput (sum)     : 70.05 tokens/s
  Batch duration (wall-clock)  : 10.621 s
```

**Test result for deploy phi4 on 2*NC24 A100 VM( (When concurrency exceeds 2, a 429 error will occur.):**

```
(aml_env) root@linuxworkvm:~/AIFperformance# python  press-phi3v-20250315.py
Please enter the API service URL (default: https://custom-endpoint-1742021907.polandcentral.inference.ml.azure.com/score): https://aml-david-2-nc24.polandcentral.inference.ml.azure.com/score
Please enter the API Key (default is configured): EhKkIvwTiKCZkrmdIlTyqYlbypDWiikA2SSpNX5GBfGmNK1Xc5CGJQQJ99BCAAAAAAAAAAAAINFRAZML2etY
Please enter the HuggingFace model name for loading the tokenizer (default: gpt2, leave blank to skip loading): microsoft/Phi-3.5-vision-instruct
Tokenizer loaded successfully: microsoft/Phi-3.5-vision-instruct

Starting load test: Concurrency=1, Total Requests=1
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.963s, TTFT=3.963s, Throughput=34.82 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 3.963 s
    Latency       : 3.963 s
    Throughput    : 34.82 tokens/s
    Prompt tokens : 34, Output tokens: 138

Summary for concurrency=1:
  Successful requests          : 1
  Failed requests              : 0
  Average TTFT per request     : 3.963 s
  Average throughput per req   : 34.82 tokens/s
  Overall throughput (sum)     : 34.82 tokens/s
  Batch duration (wall-clock)  : 3.972 s


Starting load test: Concurrency=2, Total Requests=2
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.772s, TTFT=3.772s, Throughput=31.82 tokens/s
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=6.834s, TTFT=6.834s, Throughput=19.32 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 3.772 s
    Latency       : 3.772 s
    Throughput    : 31.82 tokens/s
    Prompt tokens : 34, Output tokens: 120
  Request 2:
    TTFT          : 6.834 s
    Latency       : 6.834 s
    Throughput    : 19.32 tokens/s
    Prompt tokens : 34, Output tokens: 132

Summary for concurrency=2:
  Successful requests          : 2
  Failed requests              : 0
  Average TTFT per request     : 5.303 s
  Average throughput per req   : 25.57 tokens/s
  Overall throughput (sum)     : 51.13 tokens/s
  Batch duration (wall-clock)  : 6.840 s


Starting load test: Concurrency=3, Total Requests=3
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.944s, TTFT=3.944s, Throughput=34.99 tokens/s
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=4.316s, TTFT=4.316s, Throughput=40.54 tokens/s
Iteration 3: Success | Desired tokens=3000 | Temp=1.0 | Latency=7.511s, TTFT=7.511s, Throughput=19.17 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 3.944 s
    Latency       : 3.944 s
    Throughput    : 34.99 tokens/s
    Prompt tokens : 34, Output tokens: 138
  Request 2:
    TTFT          : 4.316 s
    Latency       : 4.316 s
    Throughput    : 40.54 tokens/s
    Prompt tokens : 34, Output tokens: 175
  Request 3:
    TTFT          : 7.511 s
    Latency       : 7.511 s
    Throughput    : 19.17 tokens/s
    Prompt tokens : 34, Output tokens: 144

Summary for concurrency=3:
  Successful requests          : 3
  Failed requests              : 0
  Average TTFT per request     : 5.257 s
  Average throughput per req   : 31.57 tokens/s
  Overall throughput (sum)     : 94.71 tokens/s
  Batch duration (wall-clock)  : 7.519 s


Starting load test: Concurrency=4, Total Requests=4
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.738s, TTFT=3.738s, Throughput=31.57 tokens/s
Iteration 3: Success | Desired tokens=3000 | Temp=1.0 | Latency=4.282s, TTFT=4.282s, Throughput=40.87 tokens/s
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=6.725s, TTFT=6.725s, Throughput=18.29 tokens/s
Iteration 4: Success | Desired tokens=3000 | Temp=1.0 | Latency=7.466s, TTFT=7.466s, Throughput=19.29 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 3.738 s
    Latency       : 3.738 s
    Throughput    : 31.57 tokens/s
    Prompt tokens : 34, Output tokens: 118
  Request 2:
    TTFT          : 4.282 s
    Latency       : 4.282 s
    Throughput    : 40.87 tokens/s
    Prompt tokens : 34, Output tokens: 175
  Request 3:
    TTFT          : 6.725 s
    Latency       : 6.725 s
    Throughput    : 18.29 tokens/s
    Prompt tokens : 34, Output tokens: 123
  Request 4:
    TTFT          : 7.466 s
    Latency       : 7.466 s
    Throughput    : 19.29 tokens/s
    Prompt tokens : 34, Output tokens: 144

Summary for concurrency=4:
  Successful requests          : 4
  Failed requests              : 0
  Average TTFT per request     : 5.553 s
  Average throughput per req   : 27.50 tokens/s
  Overall throughput (sum)     : 110.02 tokens/s
  Batch duration (wall-clock)  : 7.474 s


Starting load test: Concurrency=5, Total Requests=5
Iteration 2: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 2: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 4: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.740s, TTFT=3.740s, Throughput=31.55 tokens/s
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.750s, TTFT=3.750s, Throughput=32.26 tokens/s
Iteration 5: Success | Desired tokens=3000 | Temp=1.0 | Latency=6.712s, TTFT=6.712s, Throughput=18.32 tokens/s
Iteration 3: Success | Desired tokens=3000 | Temp=1.0 | Latency=7.260s, TTFT=7.260s, Throughput=24.24 tokens/s
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=7.652s, TTFT=7.652s, Throughput=43.65 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 3.740 s
    Latency       : 3.740 s
    Throughput    : 31.55 tokens/s
    Prompt tokens : 34, Output tokens: 118
  Request 2:
    TTFT          : 3.750 s
    Latency       : 3.750 s
    Throughput    : 32.26 tokens/s
    Prompt tokens : 34, Output tokens: 121
  Request 3:
    TTFT          : 6.712 s
    Latency       : 6.712 s
    Throughput    : 18.32 tokens/s
    Prompt tokens : 34, Output tokens: 123
  Request 4:
    TTFT          : 7.260 s
    Latency       : 7.260 s
    Throughput    : 24.24 tokens/s
    Prompt tokens : 34, Output tokens: 176
  Request 5:
    TTFT          : 7.652 s
    Latency       : 7.652 s
    Throughput    : 43.65 tokens/s
    Prompt tokens : 34, Output tokens: 334

Summary for concurrency=5:
  Successful requests          : 5
  Failed requests              : 0
  Average TTFT per request     : 5.823 s
  Average throughput per req   : 30.01 tokens/s
  Overall throughput (sum)     : 150.03 tokens/s
  Batch duration (wall-clock)  : 12.301 s
```



**Test result for deploy phi4 on 1*NC48 A100 VM( (When concurrency exceeds 2, a 429 error will occur.):**

```
(aml_env) root@linuxworkvm:~/AIFperformance# python  press-phi3v-20250315.py
Please enter the API service URL (default: https://custom-endpoint-1742021907.polandcentral.inference.ml.azure.com/score): https://aml-david-1-nc48.polandcentral.inference.ml.azure.com/score
Please enter the API Key (default is configured): 57GzZXHoZrTSurmU9ZuvA9gxmeo20Ee7jOHumXDb6KfnYlN1XAvMJQQJ99BCAAAAAAAAAAAAINFRAZML4DCW
Please enter the HuggingFace model name for loading the tokenizer (default: gpt2, leave blank to skip loading): microsoft/Phi-3.5-vision-instruct
Tokenizer loaded successfully: microsoft/Phi-3.5-vision-instruct

Starting load test: Concurrency=1, Total Requests=1
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=5.687s, TTFT=5.687s, Throughput=40.62 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 5.687 s
    Latency       : 5.687 s
    Throughput    : 40.62 tokens/s
    Prompt tokens : 34, Output tokens: 231

Summary for concurrency=1:
  Successful requests          : 1
  Failed requests              : 0
  Average TTFT per request     : 5.687 s
  Average throughput per req   : 40.62 tokens/s
  Overall throughput (sum)     : 40.62 tokens/s
  Batch duration (wall-clock)  : 5.696 s


Starting load test: Concurrency=2, Total Requests=2
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=5.173s, TTFT=5.172s, Throughput=44.66 tokens/s
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=8.410s, TTFT=8.410s, Throughput=17.12 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 5.172 s
    Latency       : 5.173 s
    Throughput    : 44.66 tokens/s
    Prompt tokens : 34, Output tokens: 231
  Request 2:
    TTFT          : 8.410 s
    Latency       : 8.410 s
    Throughput    : 17.12 tokens/s
    Prompt tokens : 34, Output tokens: 144

Summary for concurrency=2:
  Successful requests          : 2
  Failed requests              : 0
  Average TTFT per request     : 6.791 s
  Average throughput per req   : 30.89 tokens/s
  Overall throughput (sum)     : 61.78 tokens/s
  Batch duration (wall-clock)  : 8.416 s


Starting load test: Concurrency=3, Total Requests=3
Iteration 3: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 3: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=4.057s, TTFT=4.057s, Throughput=35.50 tokens/s
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=6.953s, TTFT=6.953s, Throughput=16.40 tokens/s
Iteration 3: Success | Desired tokens=3000 | Temp=1.0 | Latency=5.217s, TTFT=5.217s, Throughput=21.85 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 4.057 s
    Latency       : 4.057 s
    Throughput    : 35.50 tokens/s
    Prompt tokens : 34, Output tokens: 144
  Request 2:
    TTFT          : 6.953 s
    Latency       : 6.953 s
    Throughput    : 16.40 tokens/s
    Prompt tokens : 34, Output tokens: 114
  Request 3:
    TTFT          : 5.217 s
    Latency       : 5.217 s
    Throughput    : 21.85 tokens/s
    Prompt tokens : 34, Output tokens: 114

Summary for concurrency=3:
  Successful requests          : 3
  Failed requests              : 0
  Average TTFT per request     : 5.409 s
  Average throughput per req   : 24.58 tokens/s
  Overall throughput (sum)     : 73.74 tokens/s
  Batch duration (wall-clock)  : 9.866 s


Starting load test: Concurrency=4, Total Requests=4
Iteration 1: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 2: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 2: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 1: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 3: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.565s, TTFT=3.565s, Throughput=27.77 tokens/s
Iteration 1: Attempt 3 received 429 Too Many Requests, backing off for 4 seconds.
Iteration 4: Success | Desired tokens=3000 | Temp=1.0 | Latency=6.319s, TTFT=6.319s, Throughput=15.67 tokens/s
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=5.605s, TTFT=5.605s, Throughput=38.18 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 3.565 s
    Latency       : 3.565 s
    Throughput    : 27.77 tokens/s
    Prompt tokens : 34, Output tokens: 99
  Request 2:
    TTFT          : 6.319 s
    Latency       : 6.319 s
    Throughput    : 15.67 tokens/s
    Prompt tokens : 34, Output tokens: 99
  Request 3:
    TTFT          : 5.605 s
    Latency       : 5.605 s
    Throughput    : 38.18 tokens/s
    Prompt tokens : 34, Output tokens: 214

Summary for concurrency=4:
  Successful requests          : 3
  Failed requests              : 0
  Average TTFT per request     : 5.163 s
  Average throughput per req   : 27.21 tokens/s
  Overall throughput (sum)     : 81.62 tokens/s
  Batch duration (wall-clock)  : 10.241 s


Starting load test: Concurrency=5, Total Requests=5
Iteration 1: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 5: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 3: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 3: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 1: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 5: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 4: Success | Desired tokens=3000 | Temp=1.0 | Latency=4.713s, TTFT=4.713s, Throughput=45.41 tokens/s
Iteration 1: Attempt 3 received 429 Too Many Requests, backing off for 4 seconds.
Iteration 3: Attempt 3 received 429 Too Many Requests, backing off for 4 seconds.
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=8.020s, TTFT=8.020s, Throughput=18.95 tokens/s
Iteration 5: Success | Desired tokens=3000 | Temp=1.0 | Latency=6.664s, TTFT=6.664s, Throughput=22.81 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 4.713 s
    Latency       : 4.713 s
    Throughput    : 45.41 tokens/s
    Prompt tokens : 34, Output tokens: 214
  Request 2:
    TTFT          : 8.020 s
    Latency       : 8.020 s
    Throughput    : 18.95 tokens/s
    Prompt tokens : 34, Output tokens: 152
  Request 3:
    TTFT          : 6.664 s
    Latency       : 6.664 s
    Throughput    : 22.81 tokens/s
    Prompt tokens : 34, Output tokens: 152

Summary for concurrency=5:
  Successful requests          : 3
  Failed requests              : 0
  Average TTFT per request     : 6.466 s
  Average throughput per req   : 29.06 tokens/s
  Overall throughput (sum)     : 87.17 tokens/s
  Batch duration (wall-clock)  : 11.309 s

(aml_env) root@linuxworkvm:~/AIFperformance# python  press-phi3v-20250315.py
Please enter the API service URL (default: https://custom-endpoint-1742021907.polandcentral.inference.ml.azure.com/score): https://aml-david-1-nc48.polandcentral.inference.ml.azure.com/score
Please enter the API Key (default is configured): 57GzZXHoZrTSurmU9ZuvA9gxmeo20Ee7jOHumXDb6KfnYlN1XAvMJQQJ99BCAAAAAAAAAAAAINFRAZML4DCW
Please enter the HuggingFace model name for loading the tokenizer (default: gpt2, leave blank to skip loading): microsoft/Phi-3.5-vision-instruct
Tokenizer loaded successfully: microsoft/Phi-3.5-vision-instruct

Starting load test: Concurrency=1, Total Requests=1
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=4.687s, TTFT=4.687s, Throughput=47.15 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 4.687 s
    Latency       : 4.687 s
    Throughput    : 47.15 tokens/s
    Prompt tokens : 34, Output tokens: 221

Summary for concurrency=1:
  Successful requests          : 1
  Failed requests              : 0
  Average TTFT per request     : 4.687 s
  Average throughput per req   : 47.15 tokens/s
  Overall throughput (sum)     : 47.15 tokens/s
  Batch duration (wall-clock)  : 4.695 s


Starting load test: Concurrency=2, Total Requests=2
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=4.701s, TTFT=4.701s, Throughput=47.01 tokens/s
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=8.340s, TTFT=8.340s, Throughput=22.42 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 4.701 s
    Latency       : 4.701 s
    Throughput    : 47.01 tokens/s
    Prompt tokens : 34, Output tokens: 221
  Request 2:
    TTFT          : 8.340 s
    Latency       : 8.340 s
    Throughput    : 22.42 tokens/s
    Prompt tokens : 34, Output tokens: 187

Summary for concurrency=2:
  Successful requests          : 2
  Failed requests              : 0
  Average TTFT per request     : 6.520 s
  Average throughput per req   : 34.72 tokens/s
  Overall throughput (sum)     : 69.44 tokens/s
  Batch duration (wall-clock)  : 8.346 s


Starting load test: Concurrency=3, Total Requests=3
Iteration 1: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 1: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=4.421s, TTFT=4.421s, Throughput=42.30 tokens/s
Iteration 3: Success | Desired tokens=3000 | Temp=1.0 | Latency=7.436s, TTFT=7.436s, Throughput=16.14 tokens/s
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=5.763s, TTFT=5.763s, Throughput=20.82 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 4.421 s
    Latency       : 4.421 s
    Throughput    : 42.30 tokens/s
    Prompt tokens : 34, Output tokens: 187
  Request 2:
    TTFT          : 7.436 s
    Latency       : 7.436 s
    Throughput    : 16.14 tokens/s
    Prompt tokens : 34, Output tokens: 120
  Request 3:
    TTFT          : 5.763 s
    Latency       : 5.763 s
    Throughput    : 20.82 tokens/s
    Prompt tokens : 34, Output tokens: 120

Summary for concurrency=3:
  Successful requests          : 3
  Failed requests              : 0
  Average TTFT per request     : 5.873 s
  Average throughput per req   : 26.42 tokens/s
  Overall throughput (sum)     : 79.26 tokens/s
  Batch duration (wall-clock)  : 10.395 s


Starting load test: Concurrency=4, Total Requests=4
Iteration 2: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 4: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 4: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 2: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 3: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.898s, TTFT=3.898s, Throughput=33.86 tokens/s
Iteration 4: Attempt 3 received 429 Too Many Requests, backing off for 4 seconds.
Iteration 1: Success | Desired tokens=3000 | Temp=1.0 | Latency=6.985s, TTFT=6.985s, Throughput=18.90 tokens/s
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=5.476s, TTFT=5.476s, Throughput=25.20 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 3.898 s
    Latency       : 3.898 s
    Throughput    : 33.86 tokens/s
    Prompt tokens : 34, Output tokens: 132
  Request 2:
    TTFT          : 6.985 s
    Latency       : 6.985 s
    Throughput    : 18.90 tokens/s
    Prompt tokens : 34, Output tokens: 132
  Request 3:
    TTFT          : 5.476 s
    Latency       : 5.476 s
    Throughput    : 25.20 tokens/s
    Prompt tokens : 34, Output tokens: 138

Summary for concurrency=4:
  Successful requests          : 3
  Failed requests              : 0
  Average TTFT per request     : 5.453 s
  Average throughput per req   : 25.99 tokens/s
  Overall throughput (sum)     : 77.96 tokens/s
  Batch duration (wall-clock)  : 10.116 s


Starting load test: Concurrency=5, Total Requests=5
Iteration 5: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 1: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 2: Attempt 1 received 429 Too Many Requests, backing off for 1 seconds.
Iteration 1: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 5: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 2: Attempt 2 received 429 Too Many Requests, backing off for 2 seconds.
Iteration 4: Success | Desired tokens=3000 | Temp=1.0 | Latency=3.940s, TTFT=3.940s, Throughput=35.03 tokens/s
Iteration 1: Attempt 3 received 429 Too Many Requests, backing off for 4 seconds.
Iteration 5: Attempt 3 received 429 Too Many Requests, backing off for 4 seconds.
Iteration 3: Success | Desired tokens=3000 | Temp=1.0 | Latency=7.452s, TTFT=7.452s, Throughput=23.48 tokens/s
Iteration 2: Success | Desired tokens=3000 | Temp=1.0 | Latency=6.296s, TTFT=6.295s, Throughput=27.80 tokens/s

Detailed Results:
  Request 1:
    TTFT          : 3.940 s
    Latency       : 3.940 s
    Throughput    : 35.03 tokens/s
    Prompt tokens : 34, Output tokens: 138
  Request 2:
    TTFT          : 7.452 s
    Latency       : 7.452 s
    Throughput    : 23.48 tokens/s
    Prompt tokens : 34, Output tokens: 175
  Request 3:
    TTFT          : 6.295 s
    Latency       : 6.296 s
    Throughput    : 27.80 tokens/s
    Prompt tokens : 34, Output tokens: 175

Summary for concurrency=5:
  Successful requests          : 3
  Failed requests              : 0
  Average TTFT per request     : 5.896 s
  Average throughput per req   : 28.77 tokens/s
  Overall throughput (sum)     : 86.31 tokens/s
  Batch duration (wall-clock)  : 10.937 s

(aml_env) root@linuxworkvm:~/AIFperformance# 
```

