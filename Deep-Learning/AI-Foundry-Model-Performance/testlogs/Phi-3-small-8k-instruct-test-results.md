(aml_env) root@linuxworkvm:~/AIFperformance# python press-phi4-0314.py 
Please enter the API service URL: https://aml-8-1-nc48.polandcentral.inference.ml.azure.com/score
Please enter the API Key: 6d5PFMxmuiI50UqWu2PB8a1uPPL8TA79xY9gVPGmp9G0SS23bPwJJQQJ99BCAAAAAAAAAAAAINFRAZML2MJH
Please enter the full name of the HuggingFace model for tokenizer loading: microsoft/Phi-3-small-8k-instruct
The repository for microsoft/Phi-3-small-8k-instruct contains custom code which must be executed to correctly load the model. You can inspect the repository content at https://hf.co/microsoft/Phi-3-small-8k-instruct.
You can avoid this prompt in future by passing the argument `trust_remote_code=True`.

Do you wish to run the custom code? [y/N] y
Tokenizer loaded successfully: microsoft/Phi-3-small-8k-instruct

Scenario: Text Generation, Concurrency: 1
  Request 1:
    TTFT          : 9.530 s
    Latency       : 9.530 s
    Throughput    : 68.41 tokens/s
    Prompt tokens : 132, Output tokens: 652

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 9.530 s
    Average throughput per req   : 68.41 tokens/s
    Overall throughput (sum)     : 68.41 tokens/s
    Batch duration (wall-clock)  : 9.533 s

Scenario: Text Generation, Concurrency: 2
  Request 1:
    TTFT          : 8.566 s
    Latency       : 8.566 s
    Throughput    : 69.11 tokens/s
    Prompt tokens : 132, Output tokens: 592
  Request 2:
    TTFT          : 16.486 s
    Latency       : 16.486 s
    Throughput    : 35.91 tokens/s
    Prompt tokens : 132, Output tokens: 592

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 12.526 s
    Average throughput per req   : 52.51 tokens/s
    Overall throughput (sum)     : 105.02 tokens/s
    Batch duration (wall-clock)  : 16.488 s

Scenario: Question Answering, Concurrency: 1
  Request 1:
    TTFT          : 6.460 s
    Latency       : 6.460 s
    Throughput    : 65.64 tokens/s
    Prompt tokens : 114, Output tokens: 424

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 6.460 s
    Average throughput per req   : 65.64 tokens/s
    Overall throughput (sum)     : 65.64 tokens/s
    Batch duration (wall-clock)  : 6.461 s

Scenario: Question Answering, Concurrency: 2
  Request 1:
    TTFT          : 6.570 s
    Latency       : 6.570 s
    Throughput    : 64.53 tokens/s
    Prompt tokens : 114, Output tokens: 424
  Request 2:
    TTFT          : 9.994 s
    Latency       : 9.994 s
    Throughput    : 24.62 tokens/s
    Prompt tokens : 114, Output tokens: 246

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 8.282 s
    Average throughput per req   : 44.57 tokens/s
    Overall throughput (sum)     : 89.15 tokens/s
    Batch duration (wall-clock)  : 9.995 s

Scenario: Translation, Concurrency: 1
  Request 1:
    TTFT          : 6.983 s
    Latency       : 6.983 s
    Throughput    : 67.02 tokens/s
    Prompt tokens : 85, Output tokens: 468

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 6.983 s
    Average throughput per req   : 67.02 tokens/s
    Overall throughput (sum)     : 67.02 tokens/s
    Batch duration (wall-clock)  : 6.985 s

Scenario: Translation, Concurrency: 2
  Request 1:
    TTFT          : 2.562 s
    Latency       : 2.562 s
    Throughput    : 44.10 tokens/s
    Prompt tokens : 85, Output tokens: 113
  Request 2:
    TTFT          : 4.271 s
    Latency       : 4.271 s
    Throughput    : 29.04 tokens/s
    Prompt tokens : 85, Output tokens: 124

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 3.416 s
    Average throughput per req   : 36.57 tokens/s
    Overall throughput (sum)     : 73.14 tokens/s
    Batch duration (wall-clock)  : 4.272 s

Scenario: Text Summarization, Concurrency: 1
  Request 1:
    TTFT          : 2.570 s
    Latency       : 2.570 s
    Throughput    : 44.36 tokens/s
    Prompt tokens : 90, Output tokens: 114

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 2.570 s
    Average throughput per req   : 44.36 tokens/s
    Overall throughput (sum)     : 44.36 tokens/s
    Batch duration (wall-clock)  : 2.571 s

Scenario: Text Summarization, Concurrency: 2
  Request 1:
    TTFT          : 2.757 s
    Latency       : 2.757 s
    Throughput    : 51.14 tokens/s
    Prompt tokens : 90, Output tokens: 141
  Request 2:
    TTFT          : 4.377 s
    Latency       : 4.377 s
    Throughput    : 23.99 tokens/s
    Prompt tokens : 90, Output tokens: 105

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 3.567 s
    Average throughput per req   : 37.57 tokens/s
    Overall throughput (sum)     : 75.13 tokens/s
    Batch duration (wall-clock)  : 4.378 s

Scenario: Code Generation, Concurrency: 1
  Request 1:
    TTFT          : 5.757 s
    Latency       : 5.757 s
    Throughput    : 74.69 tokens/s
    Prompt tokens : 79, Output tokens: 430

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 5.757 s
    Average throughput per req   : 74.69 tokens/s
    Overall throughput (sum)     : 74.69 tokens/s
    Batch duration (wall-clock)  : 5.758 s

Scenario: Code Generation, Concurrency: 2
  Request 1:
    TTFT          : 11.350 s
    Latency       : 11.350 s
    Throughput    : 85.29 tokens/s
    Prompt tokens : 79, Output tokens: 968
  Request 2:
    TTFT          : 12.490 s
    Latency       : 12.490 s
    Throughput    : 6.57 tokens/s
    Prompt tokens : 79, Output tokens: 82

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 11.920 s
    Average throughput per req   : 45.93 tokens/s
    Overall throughput (sum)     : 91.85 tokens/s
    Batch duration (wall-clock)  : 12.491 s

Scenario: Chatbot, Concurrency: 1
  Request 1:
    TTFT          : 3.691 s
    Latency       : 3.691 s
    Throughput    : 54.46 tokens/s
    Prompt tokens : 60, Output tokens: 201

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 3.691 s
    Average throughput per req   : 54.46 tokens/s
    Overall throughput (sum)     : 54.46 tokens/s
    Batch duration (wall-clock)  : 3.692 s

Scenario: Chatbot, Concurrency: 2
  Request 1:
    TTFT          : 5.142 s
    Latency       : 5.142 s
    Throughput    : 65.35 tokens/s
    Prompt tokens : 60, Output tokens: 336
  Request 2:
    TTFT          : 8.045 s
    Latency       : 8.045 s
    Throughput    : 26.73 tokens/s
    Prompt tokens : 60, Output tokens: 215

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 6.593 s
    Average throughput per req   : 46.04 tokens/s
    Overall throughput (sum)     : 92.07 tokens/s
    Batch duration (wall-clock)  : 8.046 s

Scenario: Sentiment Analysis / Classification, Concurrency: 1
  Request 1:
    TTFT          : 0.957 s
    Latency       : 0.957 s
    Throughput    : 5.22 tokens/s
    Prompt tokens : 82, Output tokens: 5

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 0.957 s
    Average throughput per req   : 5.22 tokens/s
    Overall throughput (sum)     : 5.22 tokens/s
    Batch duration (wall-clock)  : 0.958 s

Scenario: Sentiment Analysis / Classification, Concurrency: 2
  Request 1:
    TTFT          : 1.118 s
    Latency       : 1.118 s
    Throughput    : 4.47 tokens/s
    Prompt tokens : 82, Output tokens: 5
  Request 2:
    TTFT          : 1.260 s
    Latency       : 1.260 s
    Throughput    : 3.97 tokens/s
    Prompt tokens : 82, Output tokens: 5

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 1.189 s
    Average throughput per req   : 4.22 tokens/s
    Overall throughput (sum)     : 8.44 tokens/s
    Batch duration (wall-clock)  : 1.261 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 1
  Request 1:
    TTFT          : 16.343 s
    Latency       : 16.343 s
    Throughput    : 72.45 tokens/s
    Prompt tokens : 99, Output tokens: 1184

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 16.343 s
    Average throughput per req   : 72.45 tokens/s
    Overall throughput (sum)     : 72.45 tokens/s
    Batch duration (wall-clock)  : 16.345 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 2
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 16.961 s
    Latency       : 16.961 s
    Throughput    : 74.47 tokens/s
    Prompt tokens : 99, Output tokens: 1263
  Request 2:
    TTFT          : 16.655 s
    Latency       : 16.655 s
    Throughput    : 74.63 tokens/s
    Prompt tokens : 99, Output tokens: 1243

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 16.808 s
    Average throughput per req   : 74.55 tokens/s
    Overall throughput (sum)     : 149.10 tokens/s
    Batch duration (wall-clock)  : 48.295 s



(aml_env) root@linuxworkvm:~/AIFperformance# python press-phi4-0314.py 
Please enter the API service URL: https://aml-westus-2-nc24.westus.inference.ml.azure.com/score
Please enter the API Key: 6uIyRD843vrZjlvLdUgxiOVy3DdB1Ma0JNpk8nGa3BRfo3Um44toJQQJ99BCAAAAAAAAAAAAINFRAZML4JqH
Please enter the full name of the HuggingFace model for tokenizer loading: microsoft/Phi-3-small-8k-instruct
The repository for microsoft/Phi-3-small-8k-instruct contains custom code which must be executed to correctly load the model. You can inspect the repository content at https://hf.co/microsoft/Phi-3-small-8k-instruct.
You can avoid this prompt in future by passing the argument `trust_remote_code=True`.

Do you wish to run the custom code? [y/N] y
Tokenizer loaded successfully: microsoft/Phi-3-small-8k-instruct

Scenario: Text Generation, Concurrency: 1
  Request 1:
    TTFT          : 9.070 s
    Latency       : 9.070 s
    Throughput    : 69.79 tokens/s
    Prompt tokens : 132, Output tokens: 633

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 9.070 s
    Average throughput per req   : 69.79 tokens/s
    Overall throughput (sum)     : 69.79 tokens/s
    Batch duration (wall-clock)  : 9.072 s

Scenario: Text Generation, Concurrency: 2
  Request 1:
    TTFT          : 9.700 s
    Latency       : 9.700 s
    Throughput    : 66.50 tokens/s
    Prompt tokens : 132, Output tokens: 645
  Request 2:
    TTFT          : 18.104 s
    Latency       : 18.104 s
    Throughput    : 34.96 tokens/s
    Prompt tokens : 132, Output tokens: 633

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 13.902 s
    Average throughput per req   : 50.73 tokens/s
    Overall throughput (sum)     : 101.46 tokens/s
    Batch duration (wall-clock)  : 18.106 s

Scenario: Question Answering, Concurrency: 1
  Request 1:
    TTFT          : 7.401 s
    Latency       : 7.401 s
    Throughput    : 68.50 tokens/s
    Prompt tokens : 114, Output tokens: 507

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 7.401 s
    Average throughput per req   : 68.50 tokens/s
    Overall throughput (sum)     : 68.50 tokens/s
    Batch duration (wall-clock)  : 7.403 s

Scenario: Question Answering, Concurrency: 2
  Request 1:
    TTFT          : 6.252 s
    Latency       : 6.252 s
    Throughput    : 67.34 tokens/s
    Prompt tokens : 114, Output tokens: 421
  Request 2:
    TTFT          : 7.450 s
    Latency       : 7.450 s
    Throughput    : 68.05 tokens/s
    Prompt tokens : 114, Output tokens: 507

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 6.851 s
    Average throughput per req   : 67.70 tokens/s
    Overall throughput (sum)     : 135.39 tokens/s
    Batch duration (wall-clock)  : 7.451 s

Scenario: Translation, Concurrency: 1
  Request 1:
    TTFT          : 8.552 s
    Latency       : 8.552 s
    Throughput    : 69.57 tokens/s
    Prompt tokens : 85, Output tokens: 595

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 8.552 s
    Average throughput per req   : 69.57 tokens/s
    Overall throughput (sum)     : 69.57 tokens/s
    Batch duration (wall-clock)  : 8.553 s

Scenario: Translation, Concurrency: 2
  Request 1:
    TTFT          : 2.433 s
    Latency       : 2.433 s
    Throughput    : 48.10 tokens/s
    Prompt tokens : 85, Output tokens: 117
  Request 2:
    TTFT          : 9.470 s
    Latency       : 9.470 s
    Throughput    : 69.48 tokens/s
    Prompt tokens : 85, Output tokens: 658

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 5.951 s
    Average throughput per req   : 58.79 tokens/s
    Overall throughput (sum)     : 117.58 tokens/s
    Batch duration (wall-clock)  : 9.472 s

Scenario: Text Summarization, Concurrency: 1
  Request 1:
    TTFT          : 2.690 s
    Latency       : 2.690 s
    Throughput    : 55.39 tokens/s
    Prompt tokens : 90, Output tokens: 149

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 2.690 s
    Average throughput per req   : 55.39 tokens/s
    Overall throughput (sum)     : 55.39 tokens/s
    Batch duration (wall-clock)  : 2.691 s

Scenario: Text Summarization, Concurrency: 2
  Request 1:
    TTFT          : 2.360 s
    Latency       : 2.360 s
    Throughput    : 47.45 tokens/s
    Prompt tokens : 90, Output tokens: 112
  Request 2:
    TTFT          : 4.034 s
    Latency       : 4.034 s
    Throughput    : 29.99 tokens/s
    Prompt tokens : 90, Output tokens: 121

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 3.197 s
    Average throughput per req   : 38.72 tokens/s
    Overall throughput (sum)     : 77.44 tokens/s
    Batch duration (wall-clock)  : 4.035 s

Scenario: Code Generation, Concurrency: 1
  Request 1:
    TTFT          : 1.991 s
    Latency       : 1.991 s
    Throughput    : 42.19 tokens/s
    Prompt tokens : 79, Output tokens: 84

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 1.991 s
    Average throughput per req   : 42.19 tokens/s
    Overall throughput (sum)     : 42.19 tokens/s
    Batch duration (wall-clock)  : 1.992 s

Scenario: Code Generation, Concurrency: 2
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 14.576 s
    Latency       : 14.576 s
    Throughput    : 80.89 tokens/s
    Prompt tokens : 79, Output tokens: 1179
  Request 2:
    TTFT          : 15.196 s
    Latency       : 15.196 s
    Throughput    : 81.40 tokens/s
    Prompt tokens : 79, Output tokens: 1237

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 14.886 s
    Average throughput per req   : 81.14 tokens/s
    Overall throughput (sum)     : 162.29 tokens/s
    Batch duration (wall-clock)  : 46.708 s

Scenario: Chatbot, Concurrency: 1
  Request 1:
    TTFT          : 3.160 s
    Latency       : 3.160 s
    Throughput    : 60.13 tokens/s
    Prompt tokens : 60, Output tokens: 190

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 3.160 s
    Average throughput per req   : 60.13 tokens/s
    Overall throughput (sum)     : 60.13 tokens/s
    Batch duration (wall-clock)  : 3.161 s

Scenario: Chatbot, Concurrency: 2
  Request 1:
    TTFT          : 3.468 s
    Latency       : 3.468 s
    Throughput    : 56.52 tokens/s
    Prompt tokens : 60, Output tokens: 196
  Request 2:
    TTFT          : 3.798 s
    Latency       : 3.798 s
    Throughput    : 60.04 tokens/s
    Prompt tokens : 60, Output tokens: 228

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 3.633 s
    Average throughput per req   : 58.28 tokens/s
    Overall throughput (sum)     : 116.56 tokens/s
    Batch duration (wall-clock)  : 3.799 s

Scenario: Sentiment Analysis / Classification, Concurrency: 1
  Request 1:
    TTFT          : 0.792 s
    Latency       : 0.792 s
    Throughput    : 6.31 tokens/s
    Prompt tokens : 82, Output tokens: 5

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 0.792 s
    Average throughput per req   : 6.31 tokens/s
    Overall throughput (sum)     : 6.31 tokens/s
    Batch duration (wall-clock)  : 0.793 s

Scenario: Sentiment Analysis / Classification, Concurrency: 2
  Request 1:
    TTFT          : 0.946 s
    Latency       : 0.946 s
    Throughput    : 5.29 tokens/s
    Prompt tokens : 82, Output tokens: 5
  Request 2:
    TTFT          : 1.083 s
    Latency       : 1.083 s
    Throughput    : 4.62 tokens/s
    Prompt tokens : 82, Output tokens: 5

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 1.015 s
    Average throughput per req   : 4.95 tokens/s
    Overall throughput (sum)     : 9.90 tokens/s
    Batch duration (wall-clock)  : 1.084 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 1
  Request 1:
    TTFT          : 26.220 s
    Latency       : 26.220 s
    Throughput    : 73.91 tokens/s
    Prompt tokens : 99, Output tokens: 1938

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 26.220 s
    Average throughput per req   : 73.91 tokens/s
    Overall throughput (sum)     : 73.91 tokens/s
    Batch duration (wall-clock)  : 26.222 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 2
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 13.815 s
    Latency       : 13.815 s
    Throughput    : 72.53 tokens/s
    Prompt tokens : 99, Output tokens: 1002
  Request 2:
    TTFT          : 11.734 s
    Latency       : 11.734 s
    Throughput    : 73.12 tokens/s
    Prompt tokens : 99, Output tokens: 858

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 12.774 s
    Average throughput per req   : 72.83 tokens/s
    Overall throughput (sum)     : 145.65 tokens/s
    Batch duration (wall-clock)  : 43.245 s





(aml_env) root@linuxworkvm:~/AIFperformance# python press-phi4-0314.py
Please enter the API service URL: https://aml-westus-1-nc24.westus.inference.ml.azure.com/score
Please enter the API Key: AQmp1nQw9UzjrBwprK1U4FNaMrJZgrJaGAXzx1hRwv1XuNHMkSYEJQQJ99BCAAAAAAAAAAAAINFRAZML1SSd
Please enter the full name of the HuggingFace model for tokenizer loading: microsoft/Phi-3-small-8k-instruct
The repository for microsoft/Phi-3-small-8k-instruct contains custom code which must be executed to correctly load the model. You can inspect the repository content at https://hf.co/microsoft/Phi-3-small-8k-instruct.
You can avoid this prompt in future by passing the argument `trust_remote_code=True`.

Do you wish to run the custom code? [y/N] y
Tokenizer loaded successfully: microsoft/Phi-3-small-8k-instruct

Scenario: Text Generation, Concurrency: 1
  Request 1:
    TTFT          : 9.727 s
    Latency       : 9.727 s
    Throughput    : 66.31 tokens/s
    Prompt tokens : 132, Output tokens: 645

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 9.727 s
    Average throughput per req   : 66.31 tokens/s
    Overall throughput (sum)     : 66.31 tokens/s
    Batch duration (wall-clock)  : 9.729 s

Scenario: Text Generation, Concurrency: 2
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 9.091 s
    Latency       : 9.091 s
    Throughput    : 69.63 tokens/s
    Prompt tokens : 132, Output tokens: 633
  Request 2:
    TTFT          : 21.489 s
    Latency       : 21.489 s
    Throughput    : 22.48 tokens/s
    Prompt tokens : 132, Output tokens: 483

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 15.290 s
    Average throughput per req   : 46.05 tokens/s
    Overall throughput (sum)     : 92.11 tokens/s
    Batch duration (wall-clock)  : 53.003 s

Scenario: Question Answering, Concurrency: 1
  Request 1:
    TTFT          : 6.041 s
    Latency       : 6.041 s
    Throughput    : 65.22 tokens/s
    Prompt tokens : 114, Output tokens: 394

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 6.041 s
    Average throughput per req   : 65.22 tokens/s
    Overall throughput (sum)     : 65.22 tokens/s
    Batch duration (wall-clock)  : 6.042 s

Scenario: Question Answering, Concurrency: 2
  Request 1:
    TTFT          : 7.444 s
    Latency       : 7.444 s
    Throughput    : 69.45 tokens/s
    Prompt tokens : 114, Output tokens: 517
  Request 2:
    TTFT          : 13.559 s
    Latency       : 13.559 s
    Throughput    : 33.78 tokens/s
    Prompt tokens : 114, Output tokens: 458

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 10.502 s
    Average throughput per req   : 51.61 tokens/s
    Overall throughput (sum)     : 103.23 tokens/s
    Batch duration (wall-clock)  : 13.560 s

Scenario: Translation, Concurrency: 1
  Request 1:
    TTFT          : 5.640 s
    Latency       : 5.640 s
    Throughput    : 66.13 tokens/s
    Prompt tokens : 85, Output tokens: 373

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 5.640 s
    Average throughput per req   : 66.13 tokens/s
    Overall throughput (sum)     : 66.13 tokens/s
    Batch duration (wall-clock)  : 5.642 s

Scenario: Translation, Concurrency: 2
  Request 1:
    TTFT          : 6.501 s
    Latency       : 6.501 s
    Throughput    : 65.38 tokens/s
    Prompt tokens : 85, Output tokens: 425
  Request 2:
    TTFT          : 8.442 s
    Latency       : 8.442 s
    Throughput    : 16.82 tokens/s
    Prompt tokens : 85, Output tokens: 142

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 7.472 s
    Average throughput per req   : 41.10 tokens/s
    Overall throughput (sum)     : 82.20 tokens/s
    Batch duration (wall-clock)  : 8.444 s

Scenario: Text Summarization, Concurrency: 1
  Request 1:
    TTFT          : 2.004 s
    Latency       : 2.004 s
    Throughput    : 42.42 tokens/s
    Prompt tokens : 90, Output tokens: 85

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 2.004 s
    Average throughput per req   : 42.42 tokens/s
    Overall throughput (sum)     : 42.42 tokens/s
    Batch duration (wall-clock)  : 2.005 s

Scenario: Text Summarization, Concurrency: 2
  Request 1:
    TTFT          : 2.855 s
    Latency       : 2.855 s
    Throughput    : 57.09 tokens/s
    Prompt tokens : 90, Output tokens: 163
  Request 2:
    TTFT          : 4.556 s
    Latency       : 4.556 s
    Throughput    : 24.37 tokens/s
    Prompt tokens : 90, Output tokens: 111

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 3.705 s
    Average throughput per req   : 40.73 tokens/s
    Overall throughput (sum)     : 81.46 tokens/s
    Batch duration (wall-clock)  : 4.557 s

Scenario: Code Generation, Concurrency: 1
  Request 1:
    TTFT          : 13.481 s
    Latency       : 13.481 s
    Throughput    : 83.15 tokens/s
    Prompt tokens : 79, Output tokens: 1121

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 13.481 s
    Average throughput per req   : 83.15 tokens/s
    Overall throughput (sum)     : 83.15 tokens/s
    Batch duration (wall-clock)  : 13.483 s

Scenario: Code Generation, Concurrency: 2
  Request 1:
    TTFT          : 16.920 s
    Latency       : 16.920 s
    Throughput    : 77.66 tokens/s
    Prompt tokens : 79, Output tokens: 1314
  Request 2:
    TTFT          : 30.023 s
    Latency       : 30.023 s
    Throughput    : 38.07 tokens/s
    Prompt tokens : 79, Output tokens: 1143

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 23.472 s
    Average throughput per req   : 57.86 tokens/s
    Overall throughput (sum)     : 115.73 tokens/s
    Batch duration (wall-clock)  : 30.025 s

Scenario: Chatbot, Concurrency: 1
  Request 1:
    TTFT          : 4.172 s
    Latency       : 4.172 s
    Throughput    : 62.80 tokens/s
    Prompt tokens : 60, Output tokens: 262

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 4.172 s
    Average throughput per req   : 62.80 tokens/s
    Overall throughput (sum)     : 62.80 tokens/s
    Batch duration (wall-clock)  : 4.173 s

Scenario: Chatbot, Concurrency: 2
  Request 1:
    TTFT          : 4.314 s
    Latency       : 4.314 s
    Throughput    : 64.67 tokens/s
    Prompt tokens : 60, Output tokens: 279
  Request 2:
    TTFT          : 8.277 s
    Latency       : 8.277 s
    Throughput    : 35.76 tokens/s
    Prompt tokens : 60, Output tokens: 296

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 6.296 s
    Average throughput per req   : 50.21 tokens/s
    Overall throughput (sum)     : 100.43 tokens/s
    Batch duration (wall-clock)  : 8.279 s

Scenario: Sentiment Analysis / Classification, Concurrency: 1
  Request 1:
    TTFT          : 0.783 s
    Latency       : 0.783 s
    Throughput    : 6.38 tokens/s
    Prompt tokens : 82, Output tokens: 5

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 0.783 s
    Average throughput per req   : 6.38 tokens/s
    Overall throughput (sum)     : 6.38 tokens/s
    Batch duration (wall-clock)  : 0.784 s

Scenario: Sentiment Analysis / Classification, Concurrency: 2
  Request 1:
    TTFT          : 2.027 s
    Latency       : 2.027 s
    Throughput    : 49.83 tokens/s
    Prompt tokens : 82, Output tokens: 101
  Request 2:
    TTFT          : 2.177 s
    Latency       : 2.177 s
    Throughput    : 2.30 tokens/s
    Prompt tokens : 82, Output tokens: 5

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 2.102 s
    Average throughput per req   : 26.06 tokens/s
    Overall throughput (sum)     : 52.12 tokens/s
    Batch duration (wall-clock)  : 2.178 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 1
  Request 1:
    TTFT          : 11.602 s
    Latency       : 11.602 s
    Throughput    : 72.23 tokens/s
    Prompt tokens : 99, Output tokens: 838

  Summary for concurrency 1:
    Successful requests          : 1
    Failed requests              : 0
    Average TTFT per request     : 11.602 s
    Average throughput per req   : 72.23 tokens/s
    Overall throughput (sum)     : 72.23 tokens/s
    Batch duration (wall-clock)  : 11.603 s

Scenario: Multi-turn Reasoning / Complex Tasks, Concurrency: 2
Attempt 1 failed: The read operation timed out
  Request 1:
    TTFT          : 25.050 s
    Latency       : 25.050 s
    Throughput    : 73.61 tokens/s
    Prompt tokens : 99, Output tokens: 1844
  Request 2:
    TTFT          : 12.400 s
    Latency       : 12.400 s
    Throughput    : 63.22 tokens/s
    Prompt tokens : 99, Output tokens: 784

  Summary for concurrency 2:
    Successful requests          : 2
    Failed requests              : 0
    Average TTFT per request     : 18.725 s
    Average throughput per req   : 68.42 tokens/s
    Overall throughput (sum)     : 136.84 tokens/s
    Batch duration (wall-clock)  : 43.912 s