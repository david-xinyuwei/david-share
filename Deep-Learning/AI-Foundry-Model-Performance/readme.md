# AML and AI Foundry Model Catalog Models performance Evaluation

This repository is designed to test the performance of open-source models from the Azure Machine Learning and AI Foundry Model Catalog, includes:

**Automatically deploy and delete AI models.**

- Quickly deploy open-source AI models on AML/AI Foundry.
- Fast delete Endpoint after PoC

Rapidly evaluate the performance of these models on the corresponding AI infrastructure and AI model inference quota.

- Utilize real prompt models to initiate stress testing across multiple scenarios.
- Evaluate performance metrics from multiple dimensions. 
- To achieve more accurate metrics, use each model's own tokenizer (GPT-2 will be used if not specified).



## Deploying models Methods

In this repository, I focus on the performance of open-source AI models deployed using Managed Compute and Azure AI Model Inference.

| Name                          | Azure OpenAI service                                         | Azure AI model inference                                     | Serverless API                                               | Managed compute                                              |
| :---------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- |
| Which models can be deployed? | [Azure OpenAI models](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models) | [Azure OpenAI models and Models as a Service](https://learn.microsoft.com/en-us/azure/ai-foundry/model-inference/concepts/models) | [Models as a Service](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/model-catalog-overview#content-safety-for-models-deployed-via-serverless-apis) | [Open and custom models](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/model-catalog-overview#availability-of-models-for-deployment-as-managed-compute) |
| Deployment resource           | Azure OpenAI resource                                        | Azure AI services resource                                   | AI project resource                                          | AI project resource                                          |
| Best suited when              | You are planning to use only OpenAI models                   | You are planning to take advantage of the flagship models in Azure AI catalog, including OpenAI. | You are planning to use a single model from a specific provider (excluding OpenAI). | If you plan to use open models and you have enough compute quota available in your subscription. |
| Billing bases                 | Token usage & PTU                                            | Token usage                                                  | Token usage                                                  | Compute core hours                                           |
| Deployment instructions       | [Deploy to Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/deploy-models-openai) | [Deploy to Azure AI model inference](https://learn.microsoft.com/en-us/azure/ai-foundry/model-inference/how-to/create-model-deployments) | [Deploy to Serverless API](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/deploy-models-serverless) | [Deploy to Managed compute](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/deploy-models-managed) |



## Performance test of AI models deployed on Managed Compute in AML and AI Foundry

In this section, we focus on the models deployed on Managed Compute in the Model Catalogue on AML and AI Foundry.

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/19.png)

Next, we will use a Python script to automate the deployment of the model and use another program to evaluate the model's performance.

### Fast Deploy AI Model on Model Catalog via Azure GPU VM

By now, the AML names tested in this repo, their full names on Hugging Face, and the Azure GPU VM SKUs that can be deployed on AML are as follows.

| **Model Name on AML**                         | **Model on HF** (tokenizers name)             | **Azure GPU VM SKU Support in AML**              |
| --------------------------------------------- | --------------------------------------------- | ------------------------------------------------ |
| Phi-4                                         | microsoft/phi-4                               | NC24/48/96 A100                                  |
| Phi-3.5-vision-instruct                       | microsoft/Phi-3.5-vision-instruct             | NC24/48/96 A100                                  |
| financial-reports-analysis                    |                                               | NC24/48/96 A100                                  |
| Llama-3.2-11B-Vision-Instruct                 | meta-llama/Llama-3.2-11B-Vision-Instruct      | NC24/48/96 A100                                  |
| Phi-3-small-8k-instruct                       | microsoft/Phi-3-small-8k-instruct             | NC24/48/96 A100                                  |
| Phi-3-vision-128k-instruct                    | microsoft/Phi-3-vision-128k-instruct          | NC48 A100 or NC96 A100                           |
| microsoft-swinv2-base-patch4-window12-192-22k | microsoft/swinv2-base-patch4-window12-192-22k | NC24/48/96 A100                                  |
| mistralai-Mixtral-8x7B-Instruct-v01           | mistralai/Mixtral-8x7B-Instruct-v0.1          | NC96 A100                                        |
| Muse                                          | microsoft/wham                                | NC24/48/96 A100                                  |
| openai-whisper-large                          | openai/whisper-large                          | NC48 A100 or NC96 A100                           |
| snowflake-arctic-base                         | Snowflake/snowflake-arctic-base               | ND H100V5                                        |
| Nemotron-3-8B-Chat-4k-SteerLM                 | nvidia/nemotron-3-8b-chat-4k-steerlm          | NC24/48/96 A100                                  |
| stabilityai-stable-diffusion-xl-refiner-1-0   | stabilityai/stable-diffusion-xl-refiner-1.0   | Standard_ND96amsr_A100_v4 or Standard_ND96asr_v4 |
| microsoft-Orca-2-7b                           | microsoft/Orca-2-7b                           | NC24/48/96 A100                                  |

This repository primarily focuses on the inference performance of the aforementioned models on 1x NC24 A100, 2 x NC24 A100, 1 x NC48 A100, 1 x NC40 H100, and 1 x NC80 H100. However, these models currently do not support deployment on H100. Therefore, as of March 2025, all validations are conducted based on NC100. 

#### **Clone code and prepare shell environment**

First, you need to create an Azure Machine Learning service in the Azure Portal. When selecting the region for the service, you should choose a region under the AML category in your subscription quota that has a GPU VM quota available.

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/20.png)

Next, find a shell environment where you can execute `az login` to log in to your Azure subscription.

**Install conda：**

For Linux

```
wget https://repo.anaconda.com/archive/Anaconda3-2024.10-1-Linux-x86_64.sh
bash Anaconda3-2024.10-1-Linux-x86_64.sh
source ~/.bashrc
conda init
```

For Windows Powershell:

Download it from Edge and install it directly:

 *https://repo.anaconda.com/archive/Anaconda3-2024.10-1-Windows-x86_64.exe*



**Clone code and do preparation:**

```
#git clone https://github.com/xinyuwei-david/AI-Foundry-Model-Performance.git
#conda create -n aml_env python=3.9 -y
#conda activate aml_env
#cd AI-Foundry-Model-Performance
#pip install -r requirements.txt  
```



#cat requirements.txt  

```
azure-ai-ml  
azure-identity  
requests  
pyyaml  
tabulate  
torch
transformers
tiktoken
```

Login to Azure.

```
#curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash  
#az login --use-device
```

#### **Deploy model Automatically**

Next, you need to execute a script for end-to-end model deployment. This script will: 

- Help you check the GPU VM quota for AML under your subscription
- Prompt you to select the model you want to deploy
- Specify the Azure GPU VM SKU and quantity to be used for deployment. 
- Provide you with the endpoint and key of the successfully deployed model, allowing you to proceed with performance testing. 

Before running the script, you need to check the table above to confirm the types of Azure GPU VMs supported by the AI model you plan to deploy. 

```
#python deploymodels-linux-20250405.py
```

If you do test on powershell,  you should use:

```
#python deploymodels-powershell-20250405.py
```

**Note：**

*The difference between the two scripts, deploymodels-linux.py and deploymodels-powershell.py, is not significant. The only difference is that PowerShell sometimes cannot parse "az" and can only parse "az.cmd," as shown in the following code snippet.* 

```
    "az.cmd", "ml", "compute", "list-usage",  
```

The deploy process:

```
========== Enter Basic Information ==========
Subscription ID: 53039473-****-d046d4fa63b6
Resource Group: AIrg1
AML Workspace Name or AI Foundry Poject Name: aml-david-1

========== Model Name Examples ==========
 - Phi-4
 - Phi-3.5-vision-instruct
 - financial-reports-analysis
 - databricks-dbrx-instruct
 - Llama-3.2-11B-Vision-Instruct
 - Phi-3-small-8k-instruct
 - Phi-3-vision-128k-instruct
 - microsoft-swinv2-base-patch4-window12-192-22k
 - mistralai-Mixtral-8x7B-Instruct-v01
 - Muse
 - openai-whisper-large
 - snowflake-arctic-base
 - Nemotron-3-8B-Chat-4k-SteerLM
 - stabilityai-stable-diffusion-xl-refiner-1-0
 - microsoft-Orca-2-7b
==========================================

Enter the model name to search (e.g., 'Phi-4'): Phi-4

========== Matching Models ==========
Name                       Description    Latest version
-------------------------  -------------  ----------------
Phi-4-multimodal-instruct                 1
Phi-4-mini-instruct                       1
Phi-4                                     7

Note: The above table is for reference only. Enter the exact model name below:
Enter full model name (case-sensitive): Phi-4
Enter model version (e.g., 7): 7
2025-03-13 15:42:02,438 - INFO - User-specified model: name='Phi-4', version='7'

========== GPU Quota (Limit > 1) ==========
Region,ResourceName,LocalizedValue,Usage,Limit
westeurope,standardNCADSH100v5Family,,0,100
polandcentral,standardNCADSA100v4Family,,0,100

========== A100 / H100 SKU Information ==========
SKU Name                            GPU Count  GPU Memory (VRAM)    CPU Cores
----------------------------------- ---------- -------------------- ----------
Standard_NC24ads_A100_v4            1          80 GB                24
Standard_NC48ads_A100_v4            2          1600 GB (2x80 GB)    48
Standard_NC96ads_A100_v4            4          320 GB (4x80 GB)     96
Standard_NC40ads_H100_v5            1          80 GB                40
Standard_NC80ads_H100_v5            2          160 GB (2x80 GB)     80

Available SKUs:
 - Standard_NC24ads_A100_v4
 - Standard_NC48ads_A100_v4
 - Standard_NC96ads_A100_v4
 - Standard_NC40ads_H100_v5
 - Standard_NC80ads_H100_v5

Enter the SKU to use: Standard_NC24ads_A100_v4
Enter the number of instances (integer): 1
2025-03-13 15:52:42,333 - INFO - Model ID: azureml://registries/AzureML/models/Phi-4/versions/7
2025-03-13 15:52:42,333 - INFO - No environment configuration found.
2025-03-13 15:52:42,366 - INFO - ManagedIdentityCredential will use IMDS
2025-03-13 15:52:42,379 - INFO - Creating Endpoint: custom-endpoint-1741852362
2025-03-13 15:52:43,008 - INFO - Request URL: 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=REDACTED&resource=REDACTED'
```

After 3-5 minutes, you will get the final results:

```
----- Deployment Information -----
ENDPOINT_NAME=custom-endpoint-1741863106
SCORING_URI=https://custom-endpoint-1741863106.polandcentral.inference.ml.azure.com/score
PRIMARY_KEY=DRxHMd1jbbSdNoXiYOaWRQ66erYZfejzKhdyDVRuh58v2hXILOcYJQQJ99BCAAAAAAAAAAAAINFRAZML3m1v
SECONDARY_KEY=4dhy3og6WfVzkIijMU7FFUDLpz4WIWEYgIlXMGYUzgwafsW6GPrMJQQJ99BCAAAAAAAAAAAAINFRAZMLxOpO
```



**Fast delete endpoint**

We know that GPU VMs are relatively expensive. Therefore, after completing performance testing, you should make use of the script below to delete the endpoint to avoid incurring excessive costs.

```
#python deplete-endpoint-20250327.py
```

Delete process:

```
lease enter your Azure Subscription ID: aaaaaaaaaaaaaaaa
Please enter your Azure Resource Group name: A100VM_group
Please enter your Azure ML Workspace name: aml-westus

Retrieving the list of online Endpoints in the Workspace...

List of online Endpoints:
1. aml-westus-takfp
2. aml-westus-aflqs

Enter the numbers of the Endpoints you want to delete (e.g., 1, 3, 4). Press Enter to skip: 1, 2

Deleting Endpoint: aml-westus-takfp...
...Endpoint aml-westus-takfp deleted successfully.

Deleting Endpoint: aml-westus-aflqs...
...Endpoint aml-westus-aflqs deleted successfully.

The deletion process for all specified Endpoints has been completed. Exiting the script.
```

#### Maximally exploit the performance of the Endpoint

***If you feel the default performance without adjusting the parameters is sufficient, then there is no need to modify these two settings, every adjustment is a trade-off, and there is no perfect solution.*** 

There is no doubt that AI models deployed using the Managed Compute approach rely on the computational power of the underlying Azure GPU VM. But can we maximize its performance? Once the Endpoint is deployed, it runs as a container on the Azure GPU VM. Take the NC24 A100 as an example, its default `request_settings.max_concurrent_requests_per_instance` is set to 1. This means the model can only handle one concurrent request. If the concurrency exceeds this limit, a 429 error will be reported.

Endpoint Default parameters value

| Parameter                                             | Value |
| ----------------------------------------------------- | ----- |
| instance_count                                        | 1     |
| liveness_probe.failure_threshold                      | 30    |
| liveness_probe.initial_delay                          | 600   |
| liveness_probe.period                                 | 10    |
| liveness_probe.success_threshold                      | 1     |
| liveness_probe.timeout                                | 2     |
| readiness_probe.failure_threshold                     | 30    |
| readiness_probe.initial_delay                         | 10    |
| readiness_probe.period                                | 10    |
| readiness_probe.success_threshold                     | 1     |
| readiness_probe.timeout                               | 2     |
| request_settings.max_concurrent_requests_per_instance | 1     |
| request_settings.request_timeout_ms                   | 90000 |

You can increase this value, for example, to 10. However, at the same time, you also need to increase the `request_settings.request_timeout_ms` (default is 90 seconds), because as concurrency increases, the response time will significantly rise. If the timeout duration is not increased, it may lead to a large number of HTTPError 424 errors. At the same time, you need to ensure that the timeout period set by the client (which is the stress testing script in the repo) is not less than the timeout period set by the server. 

Of course, increasing the values of these two parameters can boost peak throughput to some extent, but it will also increase TTFT (Time to First Token) and the total duration for processing requests. This adjustment depends on the SLA requirements of your business scenario (such as input/output tokens and TTFT requirements). 

Next, I will use Phi4 on Azure NC24 A100 as an example to demonstrate the performance changes after adjusting `request_settings.max_concurrent_requests_per_instance` to 10 and `request_settings.request_timeout_ms` to 180 seconds. 

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/22.png)

Modify 2 parameters:

```
az ml online-deployment update -g <resource-group> -w <workspace-name> -n <deployment-name> -e <endpoint-name> --set request_settings.max_concurrent_requests_per_instance=<value> request_settings.max_concurrent_requests_per_instance=<value> 
```

custom-deployment is fix deployment name value in my deployment script 

```
xinyu [ ~ ]$  az ml online-deployment update -g A100VM_group -w xinyu-workspace-westus -n custom-deployment -e custom-endpoint-1743836288 --set request_settings.request_timeout_ms=180000 request_settings.max_concurrent_requests_per_instance=10
```

Check new parameters:

```
az ml online-deployment show \
--name custom-deployment \
--endpoint-name custom-endpoint-1743836288 \
--resource-group A100VM_group \
--workspace-name xinyu-workspace-westus \
--output json
```



Test rests after parameters modification:

| Scenario  (Concurrency)            | Total Requests | Successful  Requests | Average TTFT  | Total Completion  Time (s) | Tokens/s  (Throughput) |
| ---------------------------------- | -------------- | -------------------- | ------------- | -------------------------- | ---------------------- |
| Text Generation, concurrency=1     | 1  (1+0)       | 1                    | 19.560  s     | 19.587  s                  | 44.63                  |
| Text Generation, concurrency=2     | 2  (2+0)       | 2                    | 30.135  s     | 39.863  s                  | 78.24                  |
| Text Generation, concurrency=3     | 3  (3+0)       | 3                    | 43.461  s     | 67.203  s                  | 86.36                  |
| Text Generation, concurrency=4     | 4  (4+0)       | 4                    | 52.244  s     | 75.882  s                  | 72.48                  |
| Text Generation, concurrency=5     | 5  (5+0)       | 5                    | 64.924  s     | 107.753  s                 | 103.56                 |
| **Text Generation, concurrency=6** | **6  (6+0)**   | **6**                | **71.054  s** | **124.649  s**             | **112.44**             |
| Text Generation, concurrency=7     | 7  (0+7)       | 0                    | nan           | 4.592  s                   | 0                      |
| Text Generation, concurrency=8     | 8  (8+0)       | 8                    | 89.210  s     | 168.429  s                 | 129                    |
| Text Generation, concurrency=9     | 9  (6+3)       | 6                    | 70.181  s     | 138.742  s                 | 111.47                 |
| Text Generation, concurrency=10    | 10  (0+10)     | 0                    | nan           | 5.346  s                   | 0                      |

Test rests before parameters modification:

Concurrency = 2

| Scenario            | VM 1 (1-nc48) Total TTT (s) | VM 2 (2-nc24) Total TTFT (s) | VM 3 (1-nc24) Total TTFT (s) | VM 1 (1-nc48) Total tokens/s | VM 2 (2-nc24) Total tokens/s | VM 3 (1-nc24) Total tokens/s |
| ------------------- | --------------------------- | ---------------------------- | ---------------------------- | ---------------------------- | ---------------------------- | ---------------------------- |
| **Text Generation** | 19.291                      | 19.978                       | **24.576**                   | 110.94                       | 90.13                        | **79.26**                    |

We can see that after modifying the parameters, for the same model and GPU VM—and using the same prompt and completion length—the peak throughput increased by about 40%, but the TTFT is now three times what it was before. Therefore, you need to find a balance among these various performance metrics.

###  Fast Performance Test AI Model on AML Model Catalog

***Note:***

- The test results in this section are for reference only. You need to use my script to conduct tests in your actual environment.

- In my performance testing script, timeout and retry mechanisms are configured. Specifically, if a task fails to complete within the timeout period (default is 90 seconds, which is same as the default value request_settings.request_timeout_ms in Endpoint), it will be marked as failed. Additionally, if a request encounters a 429 error during execution, it will trigger a backoff mechanism. If the 429 error occurs three consecutive times, the request will be marked as failed. When performing tests, you should adjust these parameters according to the requirements of your business scenario.

- When analyzing the test results, you need to consider multiple metrics, including request success rate, TTFT (Time to First Token), tokens/s, and TTFT again. You should not focus solely on a single indicator.

- All the tests in this section are based on the model-deployed Endpoint, without adjusting the `request_settings.max_concurrent_requests_per_instance` and `request_settings.request_timeout_ms` parameters. 

  

The primary goal of performance testing is to verify tokens/s and TTFT during the inference process. To better simulate real-world scenarios, I have set up several common LLM/SLM use cases in the test script. Additionally, to ensure tokens/s performance, the test script needs to load the corresponding model's tokenizer during execution(Refer to upper table of tokenizers name).

Before officially starting the test, you need to log in to HF on your terminal.

```
#huggingface-cli  login
```

#### Phi Text2Text Series (Phi-4/Phi-3-small-8k-instruct)

**Run the test script:**

```
(aml_env) root@pythonvm:~/AIFperformance# python press-phi4-0403.py
Please enter the API service URL: https://david-workspace-westeurop-ldvdq.westeurope.inference.ml.azure.com/score
Please enter the API Key: Ef9DFpATsXs4NiWyoVhEXeR4PWPvFy17xcws5ySCvV2H8uOUfgV4JQQJ99BCAAAAAAAAAAAAINFRAZML3eIO
Please enter the full name of the HuggingFace model for tokenizer loading: microsoft/phi-4
Tokenizer loaded successfully: microsoft/phi-4
```

**Test result analyze：**

**microsoft/phi-4**

Concurrency = 1

| Scenario                 | VM 1 (1-nc48) TTFT (s) | VM 2 (2-nc24) TTFT (s) | VM 3 (1-nc24) TTFT (s) | VM 1 (1-nc48) tokens/s | VM 2 (2-nc24) tokens/s | VM 3 (1-nc24) tokens/s |
| ------------------------ | ---------------------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- |
| **Text Generation**      | 12.473                 | 19.546                 | 19.497                 | 68.07                  | 44.66                  | 44.78                  |
| **Question Answering**   | 11.914                 | 15.552                 | 15.943                 | 72.10                  | 44.56                  | 46.04                  |
| **Translation**          | 2.499                  | 3.241                  | 3.411                  | 47.62                  | 33.32                  | 34.59                  |
| **Text Summarization**   | 2.811                  | 4.630                  | 3.369                  | 50.16                  | 37.36                  | 33.84                  |
| **Code Generation**      | 20.441                 | 27.685                 | 26.504                 | 83.12                  | 51.58                  | 52.26                  |
| **Chatbot**              | 5.035                  | 9.349                  | 8.366                  | 64.55                  | 43.96                  | 41.24                  |
| **Sentiment Analysis**   | 1.009                  | 1.235                  | 1.241                  | 5.95                   | 12.96                  | 12.89                  |
| **Multi-turn Reasoning** | 13.148                 | 20.184                 | 19.793                 | 76.44                  | 47.12                  | 47.29                  |

###### Concurrency = 2

| Scenario                 | VM 1 (1-nc48) Total TTFT (s) | VM 2 (2-nc24) Total TTFT (s) | VM 3 (1-nc24) Total TTFT (s) | VM 1 (1-nc48) Total tokens/s | VM 2 (2-nc24) Total tokens/s | VM 3 (1-nc24) Total tokens/s |
| ------------------------ | ---------------------------- | ---------------------------- | ---------------------------- | ---------------------------- | ---------------------------- | ---------------------------- |
| **Text Generation**      | 19.291                       | 19.978                       | 24.576                       | 110.94                       | 90.13                        | 79.26                        |
| **Question Answering**   | 14.165                       | 15.906                       | 21.774                       | 109.94                       | 90.87                        | 66.67                        |
| **Translation**          | 3.341                        | 4.513                        | 10.924                       | 76.45                        | 53.95                        | 68.54                        |
| **Text Summarization**   | 3.494                        | 3.664                        | 6.317                        | 77.38                        | 69.60                        | 59.45                        |
| **Code Generation**      | 16.693                       | 26.310                       | 27.772                       | 162.72                       | 104.37                       | 53.22                        |
| **Chatbot**              | 8.688                        | 9.537                        | 12.064                       | 100.09                       | 87.67                        | 67.23                        |
| **Sentiment Analysis**   | 1.251                        | 1.157                        | 1.229                        | 19.99                        | 20.09                        | 16.60                        |
| **Multi-turn Reasoning** | 20.233                       | 23.655                       | 22.880                       | 110.84                       | 94.47                        | 88.79                        |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/phi4-test-results.md*

**microsoft/Phi-3-small-8k-instruct**

| Scenario                             | Concurrency | VM 1 (1-nc48) TTFT (s) | VM 2 (2-nc24) TTFT (s) | VM 3 (1-nc24) TTFT (s) | VM 1 (1-nc48) tokens/s | VM 2 (2-nc24) tokens/s | VM 3 (1-nc24) tokens/s |
| ------------------------------------ | ----------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- | ---------------------- |
| Text Generation                      | 1           | 9.530                  | 9.070                  | 9.727                  | 68.41                  | 69.79                  | 66.31                  |
| Text Generation                      | 2           | 12.526                 | 13.902                 | 15.290                 | 105.02                 | 101.46                 | 92.11                  |
| Question Answering                   | 1           | 6.460                  | 7.401                  | 6.041                  | 65.64                  | 68.50                  | 65.22                  |
| Question Answering                   | 2           | 8.282                  | 6.851                  | 10.502                 | 89.15                  | 135.39                 | 103.23                 |
| Translation                          | 1           | 6.983                  | 8.552                  | 5.640                  | 67.02                  | 69.57                  | 66.13                  |
| Translation                          | 2           | 3.416                  | 5.951                  | 7.472                  | 73.14                  | 117.58                 | 82.20                  |
| Text Summarization                   | 1           | 2.570                  | 2.690                  | 2.004                  | 44.36                  | 55.39                  | 42.42                  |
| Text Summarization                   | 2           | 3.567                  | 3.197                  | 3.705                  | 75.13                  | 77.44                  | 81.46                  |
| Code Generation                      | 1           | 5.757                  | 1.991                  | 13.481                 | 74.69                  | 42.19                  | 83.15                  |
| Code Generation                      | 2           | 11.920                 | 14.886                 | 23.472                 | 91.85                  | 162.29                 | 115.73                 |
| Chatbot                              | 1           | 3.691                  | 3.160                  | 4.172                  | 54.46                  | 60.13                  | 62.80                  |
| Chatbot                              | 2           | 6.593                  | 3.633                  | 6.296                  | 92.07                  | 116.56                 | 100.43                 |
| Sentiment Analysis / Classification  | 1           | 0.957                  | 0.792                  | 0.783                  | 5.22                   | 6.31                   | 6.38                   |
| Sentiment Analysis / Classification  | 2           | 1.189                  | 1.015                  | 2.102                  | 8.44                   | 9.90                   | 52.12                  |
| Multi-turn Reasoning / Complex Tasks | 1           | 16.343                 | 26.220                 | 11.602                 | 72.45                  | 73.91                  | 72.23                  |
| Multi-turn Reasoning / Complex Tasks | 2           | 16.808                 | 12.774                 | 18.725                 | 149.10                 | 145.65                 | 136.84                 |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/Phi-3-small-8k-instruct-test-results.md*

#### Phi vision series (Phi-3.5-vision-instruct/Phi-3-vision-128k-instruct)

```
# python press-phi35and0v-20250323.py
```

**Phi-3.5-vision-instruct with single image input test result analyze:**

**on NC24 A100 VM:**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.117            | 57.17                                 | 57.17                       | 2.126              |
| 2           | 2                   | 0               | 4.348            | 18.85                                 | 37.71                       | 7.722              |
| 3           | 3                   | 0               | 3.389            | 49.50                                 | 148.50                      | 6.354              |
| **4**       | **4**               | **0**           | **2.898**        | **49.22**                             | **196.86**                  | **7.207**          |
| 5           | 4                   | 1               | 2.708            | 41.63                                 | 166.53                      | 8.942              |
| 6           | 5                   | 1               | 2.095            | 32.30                                 | 161.52                      | 8.951              |
| 7           | 5                   | 2               | 2.774            | 48.95                                 | 244.75                      | 8.966              |
| 8           | 4                   | 4               | 2.841            | 48.30                                 | 193.21                      | 8.953              |
| 9           | 4                   | 5               | 2.996            | 41.86                                 | 167.43                      | 8.960              |
| 10          | 4                   | 6               | 2.874            | 45.60                                 | 182.38                      | 8.958              |

**Phi-3-vision-128k-instruct with single image input test result analyze：**

**On NC48 VM：**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.124            | 46.13                                 | 46.13                       | 2.130              |
| 2           | 2                   | 0               | 2.828            | 44.21                                 | 88.41                       | 3.858              |
| 3           | 3                   | 0               | 3.432            | 47.35                                 | 142.04                      | 6.437              |
| **4**       | **4**               | **0**           | **2.497**        | **42.99**                             | **171.96**                  | **7.060**          |
| 5           | 4                   | 1               | 3.447            | 47.35                                 | 189.39                      | 8.948              |
| 6           | 5                   | 1               | 2.291            | 38.98                                 | 194.92                      | 8.964              |
| 7           | 4                   | 3               | 3.099            | 41.58                                 | 166.34                      | 8.956              |
| 8           | 4                   | 4               | 2.247            | 34.58                                 | 138.31                      | 8.960              |
| 9           | 5                   | 4               | 2.321            | 36.79                                 | 183.96                      | 8.952              |
| 10          | 5                   | 5               | 2.466            | 36.55                                 | 182.77                      | 8.950              |

#### **financial-reports-analysis Series test**

```
#python press.financial-reports-analysis-20250321.py
```

**1-nc48**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 8.347            | 74.76                                 | 74.76                       | 8.352              |
| **2**       | **2**               | **0**           | **16.248**       | **63.78**                             | **127.56**                  | **21.386**         |
| 3           | 2                   | 1               | 13.939           | 65.47                                 | 130.95                      | 18.746             |
| 4           | 2                   | 2               | 17.377           | 60.21                                 | 120.42                      | 22.402             |
| 5           | 2                   | 3               | 14.266           | 65.39                                 | 130.77                      | 18.840             |
| 1           | 1                   | 0               | 8.835            | 79.23                                 | 79.23                       | 8.839              |
| 2           | 2                   | 0               | 14.554           | 62.45                                 | 124.91                      | 19.864             |
| 3           | 2                   | 1               | 15.182           | 60.29                                 | 120.58                      | 19.113             |
| 4           | 2                   | 2               | 17.206           | 62.18                                 | 124.37                      | 20.955             |
| 5           | 2                   | 3               | 15.526           | 61.92                                 | 123.84                      | 19.806             |
| 1           | 1                   | 0               | 13.329           | 86.73                                 | 86.73                       | 13.334             |
| 2           | 2                   | 0               | 14.185           | 63.47                                 | 126.93                      | 19.196             |
| 3           | 2                   | 1               | 15.376           | 61.93                                 | 123.86                      | 20.004             |
| 4           | 2                   | 2               | 15.405           | 64.14                                 | 128.29                      | 20.872             |
| 5           | 2                   | 3               | 14.909           | 63.94                                 | 127.89                      | 19.572             |
| 1           | 1                   | 0               | 8.002            | 81.48                                 | 81.48                       | 8.006              |
| 2           | 2                   | 0               | 16.834           | 64.28                                 | 128.56                      | 21.731             |
| 3           | 2                   | 1               | 11.225           | 60.16                                 | 120.33                      | 14.274             |
| 4           | 2                   | 2               | 13.520           | 64.58                                 | 129.16                      | 17.599             |
| 5           | 2                   | 3               | 13.541           | 59.00                                 | 118.00                      | 16.613             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/output-financial-reports-analysis-1-nc48.txt*

```
(base) root@linuxworkvm:~/AIFperformance# cat output-financial-reports-analysis-1-nc48.txt |grep -A 7 
```

**2-nc24**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 9.659            | 62.63                                 | 62.63                       | 9.664              |
| 2           | 2                   | 0               | 11.663           | 65.23                                 | 130.46                      | 13.617             |
| 3           | 3                   | 0               | 20.658           | 55.25                                 | 165.74                      | 28.926             |
| 1           | 1                   | 0               | 16.593           | 53.76                                 | 53.76                       | 16.597             |
| 2           | 2                   | 0               | 20.202           | 50.54                                 | 101.09                      | 26.650             |
| **3**       | **3**               | **0**           | **19.131**       | **58.53**                             | **175.59**                  | **29.766**         |
| 1           | 1                   | 0               | 12.825           | 66.27                                 | 66.27                       | 12.829             |
| 2           | 2                   | 0               | 12.664           | 67.27                                 | 134.54                      | 13.328             |
| 3           | 3                   | 0               | 17.639           | 59.10                                 | 177.30                      | 25.248             |
| 1           | 1                   | 0               | 10.546           | 68.65                                 | 68.65                       | 10.550             |
| 2           | 2                   | 0               | 16.594           | 48.65                                 | 97.31                       | 20.664             |
| 3           | 3                   | 0               | 16.779           | 56.99                                 | 170.98                      | 23.796             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/output-financial-reports-analysis-2-nc24.txt*

```
(base) root@linuxworkvm:~/AIFperformance# cat output-financial-reports-analysis-2-nc24.txt |grep -A 7 

```

**1-nc24**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 13.339           | 71.15                                 | 71.15                       | 13.344             |
| 2           | 2                   | 0               | 21.675           | 49.30                                 | 98.61                       | 27.741             |
| 3           | 2                   | 1               | 19.226           | 52.44                                 | 104.88                      | 26.149             |
| 1           | 1                   | 0               | 14.241           | 69.38                                 | 69.38                       | 14.245             |
| **2**       | **2**               | **0**           | **17.212**       | **51.91**                             | **103.82**                  | **23.023**         |
| 3           | 2                   | 1               | 19.061           | 52.79                                 | 105.58                      | 25.372             |
| 1           | 1                   | 0               | 10.762           | 65.88                                 | 65.88                       | 10.765             |
| 2           | 2                   | 0               | 20.992           | 52.80                                 | 105.59                      | 28.139             |
| 3           | 2                   | 1               | 19.811           | 47.85                                 | 95.71                       | 24.749             |
| 1           | 1                   | 0               | 10.182           | 66.19                                 | 66.19                       | 10.187             |
| 2           | 2                   | 0               | 18.303           | 52.05                                 | 104.10                      | 24.445             |
| 3           | 2                   | 1               | 11.118           | 48.83                                 | 97.65                       | 14.555             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/output-financial-reports-analysis-1-nc24.txt*

```
(base) root@linuxworkvm:~/AIFperformance# cat output-financial-reports-analysis-1-nc24.txt |grep -A 7 "Summary for concurrency"
      
```

#### Llama-3.2-11B-Vision-Instruct (meta-llama/Llama-3.2-11B-Vision-Instruct)

**Run the test script:**

```\
#python press-llama3.211bv-20250407.py
```

Test result analyze：

| Scenario           | Concurrency | VM Type       | Successful Requests | Failed Requests (429 errors) | Avg TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ------------------ | ----------- | ------------- | ------------------- | ---------------------------- | ------------ | ------------------------------------- | --------------------------- | ------------------ |
| Text Generation    | 1           | VM1 (1-NC-24) | 1                   | 0                            | 17.439       | 52.98                                 | 52.98                       | 17.477             |
| Text Generation    | 1           | VM2 (2-NC-24) | 1                   | 0                            | 17.400       | 53.10                                 | 53.10                       | 17.432             |
| Text Generation    | 1           | VM3 (1-NC-48) | 1                   | 0                            | 16.988       | 54.39                                 | 54.39                       | 17.019             |
| Text Generation    | 2           | VM1 (1-NC-24) | 2                   | 0                            | 21.813       | 40.63                                 | 81.26                       | 28.467             |
| Text Generation    | 2           | VM2 (2-NC-24) | 2                   | 0                            | 22.046       | 40.25                                 | 80.50                       | 28.810             |
| Text Generation    | 2           | VM3 (1-NC-48) | 2                   | 0                            | 21.544       | 41.16                                 | 82.31                       | 28.132             |
| Text Generation    | 3           | VM1 (1-NC-24) | 2                   | 1                            | 21.969       | 40.09                                 | 80.18                       | 28.545             |
| Text Generation    | 3           | VM2 (2-NC-24) | 2                   | 1                            | 22.135       | 39.84                                 | 79.68                       | 28.813             |
| Text Generation    | 3           | VM3 (1-NC-48) | 2                   | 1                            | 21.531       | 41.05                                 | 82.10                       | 28.096             |
| Question Answering | 1           | VM1 (1-NC-24) | 1                   | 0                            | 2.952        | 24.73                                 | 24.73                       | 2.977              |
| Question Answering | 1           | VM2 (2-NC-24) | 1                   | 0                            | 2.967        | 24.60                                 | 24.60                       | 2.992              |
| Question Answering | 1           | VM3 (1-NC-48) | 1                   | 0                            | 2.953        | 24.72                                 | 24.72                       | 2.978              |
| Question Answering | 2           | VM1 (1-NC-24) | 2                   | 0                            | 4.100        | 18.98                                 | 37.97                       | 4.946              |
| Question Answering | 2           | VM2 (2-NC-24) | 2                   | 0                            | 4.078        | 19.13                                 | 38.25                       | 4.933              |
| Question Answering | 2           | VM3 (1-NC-48) | 2                   | 0                            | 4.037        | 19.24                                 | 38.49                       | 4.863              |
| Question Answering | 3           | VM1 (1-NC-24) | 3                   | 0                            | 13.402       | 23.74                                 | 71.21                       | 20.676             |
| Question Answering | 3           | VM2 (2-NC-24) | 3                   | 0                            | 13.592       | 23.48                                 | 70.45                       | 20.966             |
| Question Answering | 3           | VM3 (1-NC-48) | 3                   | 0                            | 13.274       | 23.96                                 | 71.89                       | 20.488             |
| Translation        | 1           | VM1 (1-NC-24) | 1                   | 0                            | 4.005        | 35.21                                 | 35.21                       | 4.029              |
| Translation        | 1           | VM2 (2-NC-24) | 1                   | 0                            | 4.096        | 34.42                                 | 34.42                       | 4.123              |
| Translation        | 1           | VM3 (1-NC-48) | 1                   | 0                            | 3.999        | 35.26                                 | 35.26                       | 4.026              |
| Translation        | 2           | VM1 (1-NC-24) | 2                   | 0                            | 6.270        | 29.04                                 | 58.08                       | 8.055              |
| Translation        | 2           | VM2 (2-NC-24) | 2                   | 0                            | 6.347        | 28.83                                 | 57.65                       | 8.211              |
| Translation        | 2           | VM3 (1-NC-48) | 2                   | 0                            | 6.143        | 29.77                                 | 59.54                       | 7.938              |
| Translation        | 3           | VM1 (1-NC-24) | 3                   | 0                            | 8.659        | 31.32                                 | 93.97                       | 15.831             |
| Translation        | 3           | VM2 (2-NC-24) | 3                   | 0                            | 8.679        | 31.26                                 | 93.78                       | 15.833             |
| Translation        | 3           | VM3 (1-NC-48) | 3                   | 0                            | 8.561        | 31.59                                 | 94.78                       | 15.623             |

| Scenario           | Concurrency | VM Type       | Successful Requests | Failed Requests (429 errors) | Avg TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ------------------ | ----------- | ------------- | ------------------- | ---------------------------- | ------------ | ------------------------------------- | --------------------------- | ------------------ |
| Text Summarization | 1           | VM1 (1-NC-24) | 1                   | 0                            | 2.134        | 8.91                                  | 8.91                        | 2.158              |
| Text Summarization | 1           | VM2 (2-NC-24) | 1                   | 0                            | 2.061        | 9.22                                  | 9.22                        | 2.086              |
| Text Summarization | 1           | VM3 (1-NC-48) | 1                   | 0                            | 2.057        | 9.24                                  | 9.24                        | 2.080              |
| Text Summarization | 2           | VM1 (1-NC-24) | 2                   | 0                            | 2.632        | 7.53                                  | 15.05                       | 3.198              |
| Text Summarization | 2           | VM2 (2-NC-24) | 2                   | 0                            | 2.640        | 7.52                                  | 15.04                       | 3.222              |
| Text Summarization | 2           | VM3 (1-NC-48) | 2                   | 0                            | 2.568        | 7.73                                  | 15.45                       | 3.132              |
| Text Summarization | 3           | VM1 (1-NC-24) | 3                   | 0                            | 2.947        | 12.87                                 | 38.62                       | 5.140              |
| Text Summarization | 3           | VM2 (2-NC-24) | 3                   | 0                            | 3.009        | 12.62                                 | 37.85                       | 5.249              |
| Text Summarization | 3           | VM3 (1-NC-48) | 3                   | 0                            | 2.973        | 12.76                                 | 38.29                       | 5.211              |
| Code Generation    | 1           | VM1 (1-NC-24) | 1                   | 0                            | 32.118       | 64.76                                 | 64.76                       | 32.146             |
| Code Generation    | 1           | VM2 (2-NC-24) | 1                   | 0                            | 32.268       | 64.46                                 | 64.46                       | 32.298             |
| Code Generation    | 1           | VM3 (1-NC-48) | 1                   | 0                            | 31.698       | 65.62                                 | 65.62                       | 31.726             |
| Code Generation    | 2           | VM1 (1-NC-24) | 2                   | 0                            | 42.762       | 44.21                                 | 88.42                       | 53.003             |
| Code Generation    | 2           | VM2 (2-NC-24) | 2                   | 0                            | 42.834       | 44.11                                 | 88.23                       | 53.065             |
| Code Generation    | 2           | VM3 (1-NC-48) | 2                   | 0                            | 41.980       | 45.02                                 | 90.05                       | 52.024             |
| Code Generation    | 3           | VM1 (1-NC-24) | 2                   | 1                            | 21.515       | 47.86                                 | 95.72                       | 29.578             |
| Code Generation    | 3           | VM2 (2-NC-24) | 2                   | 1                            | 21.605       | 47.72                                 | 95.44                       | 29.735             |
| Code Generation    | 3           | VM3 (1-NC-48) | 2                   | 1                            | 21.152       | 48.81                                 | 97.63                       | 29.160             |
| Chatbot            | 1           | VM1 (1-NC-24) | 1                   | 0                            | 10.092       | 49.94                                 | 49.94                       | 10.117             |
| Chatbot            | 1           | VM2 (2-NC-24) | 1                   | 0                            | 10.101       | 49.90                                 | 49.90                       | 10.126             |
| Chatbot            | 1           | VM3 (1-NC-48) | 1                   | 0                            | 9.761        | 51.63                                 | 51.63                       | 9.787              |
| Chatbot            | 2           | VM1 (1-NC-24) | 2                   | 0                            | 18.097       | 38.82                                 | 77.64                       | 22.841             |
| Chatbot            | 2           | VM2 (2-NC-24) | 2                   | 0                            | 18.149       | 38.75                                 | 77.50                       | 22.930             |
| Chatbot            | 2           | VM3 (1-NC-48) | 2                   | 0                            | 17.827       | 39.34                                 | 78.68                       | 22.455             |
| Chatbot            | 3           | VM1 (1-NC-24) | 2                   | 1                            | 14.984       | 38.19                                 | 76.38                       | 19.321             |
| Chatbot            | 3           | VM2 (2-NC-24) | 2                   | 1                            | 15.016       | 38.02                                 | 76.03                       | 19.312             |
| Chatbot            | 3           | VM3 (1-NC-48) | 2                   | 1                            | 14.847       | 38.43                                 | 76.85                       | 19.080             |

#### microsoft-swinv2-base-patch4-window12-192-22k Series 

```
#python press-swinv2-20250322.py
```

Test result analyze：

**1-NC48**

| **Concurrency** | **Successful Requests** | **Failed Requests** | **Average TTFT (s)** | **Avg Throughput per Request (tokens/s)** | **Total Throughput (tokens/s)** | **Batch Duration (s)** |
| --------------- | ----------------------- | ------------------- | -------------------- | ----------------------------------------- | ------------------------------- | ---------------------- |
| 1               | 1                       | 0                   | 0.910                | 27.46                                     | 27.46                           | 0.911                  |
| 2               | 2                       | 0                   | 1.055                | 24.12                                     | 48.25                           | 1.198                  |
| 3               | 3                       | 0                   | 1.073                | 23.80                                     | 71.41                           | 2.600                  |
| 4               | 4                       | 0                   | 1.198                | 21.98                                     | 87.93                           | 2.983                  |
| 5               | 5                       | 0                   | 1.031                | 24.69                                     | 123.45                          | 5.209                  |
| **6**           | **6**                   | **0**               | **1.309**            | **20.39**                                 | **122.32**                      | **5.506**              |
| 7               | 6                       | 1                   | 1.059                | 24.04                                     | 144.25                          | 8.957                  |
| 8               | 6                       | 2                   | 1.110                | 23.16                                     | 138.99                          | 8.965                  |
| 9               | 6                       | 3                   | 1.084                | 23.59                                     | 141.56                          | 8.956                  |
| 10              | 6                       | 4                   | 1.108                | 23.07                                     | 138.40                          | 8.963                  |



**2-NC24**

| **Concurrency** | **Successful Requests** | **Failed Requests** | **Average TTFT (s)** | **Avg Throughput per Request (tokens/s)** | **Batch Duration (s)** | **Total Throughput (tokens/s)** |
| --------------- | ----------------------- | ------------------- | -------------------- | ----------------------------------------- | ---------------------- | ------------------------------- |
| 1               | 1                       | 0                   | 1.002                | 24.94                                     | 1.004                  | 24.94                           |
| 2               | 2                       | 0                   | 1.272                | 19.91                                     | 1.421                  | 39.83                           |
| 3               | 3                       | 0                   | 1.093                | 23.22                                     | 1.292                  | 69.65                           |
| 4               | 4                       | 0                   | 1.151                | 22.22                                     | 1.357                  | 88.86                           |
| 5               | 5                       | 0                   | 1.042                | 24.43                                     | 2.582                  | 122.16                          |
| 6               | 6                       | 0                   | 1.047                | 24.33                                     | 2.610                  | 145.98                          |
| 7               | 7                       | 0                   | 1.067                | 23.90                                     | 2.859                  | 167.27                          |
| 8               | 8                       | 0                   | 1.227                | 21.08                                     | 2.881                  | 168.63                          |
| 9               | 9                       | 0                   | 1.074                | 23.82                                     | 5.212                  | 214.39                          |
| **10**          | **10**                  | **0**               | **1.234**            | **21.25**                                 | **5.506**              | **212.51**                      |

**1-NC24**

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 1.015            | 24.64                                 | 24.64                       | 1.016              |
| 2           | 2                   | 0               | 1.068            | 23.88                                 | 47.75                       | 1.220              |
| 3           | 3                   | 0               | 1.074            | 23.73                                 | 71.18                       | 2.602              |
| 4           | 4                   | 0               | 1.105            | 23.08                                 | 92.31                       | 2.872              |
| 5           | 5                   | 0               | 1.096            | 23.29                                 | 116.43                      | 5.226              |
| **6**       | **6**               | **0**           | **1.130**        | **22.79**                             | **136.74**                  | **5.571**          |
| 7           | 6                   | 1               | 1.100            | 23.19                                 | 139.16                      | 8.958              |
| 8           | 6                   | 2               | 1.101            | 23.16                                 | 138.96                      | 8.951              |
| 9           | 6                   | 3               | 1.079            | 23.63                                 | 141.81                      | 8.951              |
| 10          | 6                   | 4               | 1.075            | 23.71                                 | 142.28                      | 8.946              |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/swinv2-base-results.txt*



#### mistralai-Mixtral-8x7B-Instruct-v01 Series 

```
#python press-Mixtral-8x7B-20250323.py
```

Test result analyze：

**1-NC96 mistralai-Mixtral-8x7B-Instruct-v01**

Scenario: Text Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.828            | 73.19                                 | 73.19                       | 2.838              |
| 2           | 2                   | 0               | 3.884            | 57.69                                 | 115.38                      | 4.978              |
| 3           | 3                   | 0               | 3.541            | 62.94                                 | 188.81                      | 7.155              |
| **4**       | **4**               | **0**           | **3.861**        | **58.24**                             | **232.98**                  | **9.253**          |
| 5           | 4                   | 1               | 3.875            | 58.14                                 | 232.55                      | 9.312              |
| 6           | 4                   | 2               | 3.875            | 57.95                                 | 231.78                      | 9.279              |
| 7           | 4                   | 3               | 3.867            | 58.19                                 | 232.76                      | 9.281              |
| 8           | 4                   | 4               | 3.881            | 57.92                                 | 231.68                      | 9.310              |
| 9           | 4                   | 5               | 3.877            | 57.85                                 | 231.41                      | 9.298              |
| 10          | 4                   | 6               | 3.865            | 58.28                                 | 233.13                      | 9.297              |

Scenario: Question Answering

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.803            | 73.50                                 | 73.50                       | 2.810              |
| 2           | 2                   | 0               | 3.850            | 58.13                                 | 116.25                      | 4.935              |
| 3           | 3                   | 0               | 3.514            | 63.13                                 | 189.38                      | 7.126              |
| **4**       | **4**               | **0**           | **3.871**        | **57.83**                             | **231.31**                  | **9.270**          |
| 5           | 3                   | 2               | 3.523            | 63.33                                 | 189.98                      | 8.973              |
| 6           | 4                   | 2               | 3.859            | 58.28                                 | 233.13                      | 9.264              |
| 7           | 4                   | 3               | 3.871            | 57.89                                 | 231.56                      | 9.289              |
| 8           | 4                   | 4               | 3.705            | 57.79                                 | 231.18                      | 8.989              |
| 9           | 4                   | 5               | 3.865            | 57.71                                 | 230.86                      | 9.264              |
| 10          | 4                   | 6               | 3.895            | 57.47                                 | 229.87                      | 9.321              |

Scenario: Translation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.780            | 73.39                                 | 73.39                       | 2.786              |
| 2           | 2                   | 0               | 3.703            | 55.23                                 | 110.46                      | 4.614              |
| **3**       | **3**               | **0**           | **3.435**        | **62.87**                             | **188.60**                  | **7.108**          |
| 4           | 3                   | 1               | 3.529            | 62.62                                 | 187.86                      | 8.966              |
| 5           | 4                   | 1               | 3.542            | 56.86                                 | 227.43                      | 8.967              |
| 6           | 4                   | 2               | 3.804            | 57.82                                 | 231.29                      | 9.168              |
| 7           | 4                   | 3               | 3.836            | 57.28                                 | 229.12                      | 9.266              |
| 8           | 4                   | 4               | 3.419            | 57.01                                 | 228.02                      | 8.983              |
| 9           | 4                   | 5               | 3.735            | 57.41                                 | 229.63                      | 9.272              |
| 10          | 4                   | 6               | 3.876            | 57.53                                 | 230.10                      | 9.266              |

Scenario: Text Summarization

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.787            | 74.27                                 | 74.27                       | 2.794              |
| 2           | 2                   | 0               | 3.530            | 57.45                                 | 114.90                      | 4.620              |
| 3           | 3                   | 0               | 1.848            | 29.89                                 | 89.68                       | 2.625              |
| **4**       | **4**               | **0**           | **3.802**        | **56.54**                             | **226.17**                  | **8.967**          |
| 5           | 4                   | 1               | 2.569            | 54.29                                 | 217.14                      | 8.962              |
| 6           | 4                   | 2               | 2.766            | 49.01                                 | 196.03                      | 8.997              |
| 7           | 4                   | 3               | 3.839            | 56.88                                 | 227.54                      | 9.447              |
| 8           | 5                   | 3               | 2.704            | 47.66                                 | 238.31                      | 9.007              |
| 9           | 4                   | 5               | 3.621            | 58.02                                 | 232.07                      | 8.990              |
| 10          | 4                   | 6               | 3.820            | 56.86                                 | 227.45                      | 9.038              |

Scenario: Code Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.796            | 79.76                                 | 79.76                       | 2.803              |
| 2           | 2                   | 0               | 3.867            | 63.29                                 | 126.58                      | 4.950              |
| 3           | 3                   | 0               | 3.501            | 68.61                                 | 205.84                      | 7.104              |
| **4**       | **4**               | **0**           | **3.873**        | **62.14**                             | **248.56**                  | **9.270**          |
| 5           | 4                   | 1               | 3.853            | 62.60                                 | 250.39                      | 9.261              |
| 6           | 4                   | 2               | 3.857            | 62.19                                 | 248.77                      | 9.250              |
| 7           | 4                   | 3               | 3.885            | 62.52                                 | 250.10                      | 9.301              |
| 8           | 4                   | 4               | 3.858            | 63.46                                 | 253.84                      | 9.258              |
| 9           | 4                   | 5               | 3.870            | 62.59                                 | 250.36                      | 9.289              |
| 10          | 4                   | 6               | 3.874            | 62.66                                 | 250.63                      | 9.272              |

Scenario: Chatbot

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.787            | 75.00                                 | 75.00                       | 2.793              |
| 2           | 2                   | 0               | 3.853            | 58.82                                 | 117.65                      | 4.935              |
| **3**       | **3**               | **0**           | **3.506**        | **63.76**                             | **191.28**                  | **7.129**          |
| 4           | 3                   | 1               | 3.535            | 63.32                                 | 189.95                      | 8.969              |
| 5           | 4                   | 1               | 3.888            | 58.03                                 | 232.12                      | 9.302              |
| 6           | 4                   | 2               | 3.888            | 58.06                                 | 232.26                      | 9.309              |
| 7           | 4                   | 3               | 3.880            | 58.18                                 | 232.73                      | 9.285              |
| 8           | 4                   | 4               | 3.876            | 58.17                                 | 232.70                      | 9.278              |
| 9           | 4                   | 5               | 3.884            | 58.09                                 | 232.38                      | 9.313              |
| 10          | 4                   | 6               | 3.874            | 58.20                                 | 232.78                      | 9.281              |

Scenario: Sentiment Analysis / Classification

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 0.960            | 27.10                                 | 27.10                       | 0.966              |
| 2           | 2                   | 0               | 1.036            | 18.06                                 | 36.13                       | 1.131              |
| 3           | 3                   | 0               | 0.861            | 12.88                                 | 38.63                       | 2.469              |
| 4           | 4                   | 0               | 1.000            | 17.96                                 | 71.85                       | 2.630              |
| **5**       | **5**               | **0**           | **0.945**        | **16.28**                             | **81.41**                   | **5.125**          |
| 6           | 6                   | 0               | 0.887            | 12.51                                 | 75.05                       | 5.294              |
| 7           | 6                   | 1               | 1.051            | 20.55                                 | 123.31                      | 8.978              |
| 8           | 6                   | 2               | 0.923            | 13.88                                 | 83.28                       | 8.986              |
| 9           | 6                   | 3               | 0.945            | 16.33                                 | 97.96                       | 8.991              |
| 10          | 6                   | 4               | 0.915            | 14.43                                 | 86.57                       | 8.988              |

Scenario: Multi-turn Reasoning / Complex Tasks

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 2.810            | 74.38                                 | 74.38                       | 2.817              |
| 2           | 2                   | 0               | 3.884            | 58.24                                 | 116.49                      | 4.977              |
| 3           | 3                   | 0               | 3.472            | 64.50                                 | 193.50                      | 7.070              |
| **4**       | **4**               | **0**           | **3.824**        | **59.01**                             | **236.03**                  | **9.204**          |
| 5           | 4                   | 1               | 3.824            | 58.98                                 | 235.94                      | 9.215              |
| 6           | 4                   | 2               | 3.610            | 55.76                                 | 223.05                      | 8.976              |
| 7           | 4                   | 3               | 3.857            | 58.33                                 | 233.32                      | 9.250              |
| 8           | 4                   | 4               | 3.867            | 58.45                                 | 233.81                      | 9.261              |
| 9           | 4                   | 5               | 3.844            | 58.83                                 | 235.30                      | 9.244              |
| 10          | 4                   | 6               | 3.846            | 58.59                                 | 234.35                      | 9.284              |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/Mixtral-8x7B-Instruct-v0.1-result.txt*

#### openai-whisper-large Series

**On NC48 VM**

```
#python press-whisper-20250323.py
```

Test result analyze：

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) | Output Text                        |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ | ---------------------------------- |
| 1           | 1                   | 0               | 2.037            | 4.91                                  | 4.91                        | 2.040              | This is a test for speech to text. |
| 2           | 2                   | 0               | 2.555            | 4.08                                  | 8.16                        | 3.073              | This is a test for speech to text. |
| 3           | 3                   | 0               | 2.509            | 4.05                                  | 12.14                       | 4.279              | This is a test for speech to text. |
| 4           | 4                   | 0               | 2.273            | 4.46                                  | 17.85                       | 6.849              | This is a test for speech to text. |
| **5**       | **5**               | **0**           | **2.328**        | **4.40**                              | **22.00**                   | **7.471**          | This is a test for speech to text. |
| 6           | 5                   | 1               | 2.310            | 4.43                                  | 22.17                       | 9.533              | This is a test for speech to text. |
| 7           | 5                   | 2               | 2.415            | 4.25                                  | 21.27                       | 9.533              | This is a test for speech to text. |
| 8           | 5                   | 3               | 2.317            | 4.42                                  | 22.11                       | 9.550              | This is a test for speech to text. |
| 9           | 5                   | 4               | 2.408            | 4.26                                  | 21.32                       | 9.536              | This is a test for speech to text. |
| 10          | 5                   | 5               | 2.368            | 4.37                                  | 21.83                       | 9.536              | This is a test for speech to text. |

Check eveny request's TTFT and completion time.

| Concurrency | Request # | TTFT (s) | Completion Time (s) |
| ----------- | --------- | -------- | ------------------- |
| 1           | 1         | 2.037    | 2.037               |
| 2           | 1         | 2.038    | 2.038               |
| 2           | 2         | 3.071    | 3.071               |
| 3           | 1         | 2.167    | 2.167               |
| 3           | 2         | 2.929    | 2.929               |
| 3           | 3         | 2.432    | 2.432               |
| 4           | 1         | 2.006    | 2.006               |
| 4           | 2         | 2.755    | 2.755               |
| 4           | 3         | 2.167    | 2.167               |
| 4           | 4         | 2.165    | 2.165               |
| 5           | 1         | 2.034    | 2.034               |
| 5           | 2         | 2.783    | 2.783               |
| 5           | 3         | 2.027    | 2.027               |
| 5           | 4         | 2.014    | 2.014               |
| 5           | 5         | 2.780    | 2.780               |
| 6           | 1         | 1.996    | 1.996               |
| 6           | 2         | 2.746    | 2.746               |
| 6           | 3         | 2.005    | 2.005               |
| 6           | 4         | 2.029    | 2.029               |
| 6           | 5         | 2.774    | 2.774               |
| 7           | 1         | 2.259    | 2.259               |
| 7           | 2         | 3.018    | 3.018               |
| 7           | 3         | 2.019    | 2.019               |
| 7           | 4         | 2.018    | 2.018               |
| 7           | 5         | 2.762    | 2.762               |
| 8           | 1         | 2.053    | 2.053               |
| 8           | 2         | 2.797    | 2.797               |
| 8           | 3         | 2.006    | 2.006               |
| 8           | 4         | 1.994    | 1.994               |
| 8           | 5         | 2.734    | 2.734               |
| 9           | 1         | 2.172    | 2.172               |
| 9           | 2         | 3.024    | 3.024               |
| 9           | 3         | 2.096    | 2.096               |
| 9           | 4         | 2.001    | 2.001               |
| 9           | 5         | 2.747    | 2.747               |
| 10          | 1         | 2.012    | 2.012               |
| 10          | 2         | 3.054    | 3.054               |
| 10          | 3         | 2.007    | 2.007               |
| 10          | 4         | 2.009    | 2.009               |
| 10          | 5         | 2.755    | 2.755               |

#### Nemotron-3-8B-Chat-4k-SteerLM  Series

```
#python press-nemotron-3-8b-chat-4k-steerlm-20250324.py
```

**On 1 NC24 A100 VM**

Text Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.822            | 95.27                                 | 95.27                       | 6.836              |
| 2           | **2**               | **0**           | **9.903**        | **72.69**                             | **145.38**                  | **13.002**         |
| 3           | 2                   | 1               | 9.902            | 72.73                                 | 145.45                      | 13.006             |
| 4           | 2                   | 2               | 10.024           | 71.66                                 | 143.32                      | 13.139             |
| 5           | 2                   | 3               | 9.930            | 72.49                                 | 144.97                      | 13.047             |
| 6           | 2                   | 4               | 9.941            | 72.43                                 | 144.87                      | 13.059             |
| 7           | 2                   | 5               | 9.960            | 72.30                                 | 144.60                      | 13.086             |
| 8           | 2                   | 6               | 9.969            | 72.23                                 | 144.45                      | 13.100             |
| 9           | 2                   | 7               | 9.984            | 72.11                                 | 144.22                      | 13.117             |
| 10          | 2                   | 8               | 9.993            | 72.05                                 | 144.10                      | 13.130             |

Question Answering

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.858            | 92.15                                 | 92.15                       | 6.869              |
| **2**       | **2**               | **0**           | **9.970**        | **70.24**                             | **140.47**                  | **13.095**         |
| 3           | 2                   | 1               | 9.979            | 70.17                                 | 140.35                      | 13.109             |
| 4           | 2                   | 2               | 9.993            | 70.06                                 | 140.11                      | 13.124             |
| 5           | 2                   | 3               | 9.984            | 70.13                                 | 140.26                      | 13.116             |
| 6           | 2                   | 4               | 9.983            | 70.13                                 | 140.27                      | 13.119             |
| 7           | 2                   | 5               | 9.989            | 70.09                                 | 140.18                      | 13.122             |
| 8           | 2                   | 6               | 9.988            | 70.11                                 | 140.21                      | 13.119             |
| 9           | 2                   | 7               | 9.985            | 70.14                                 | 140.28                      | 13.117             |
| 10          | 2                   | 8               | 9.983            | 70.12                                 | 140.23                      | 13.116             |

Translation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.850            | 114.30                                | 114.30                      | 6.860              |
| **2**       | **2**               | **0**           | **9.955**        | **87.14**                             | **174.29**                  | **13.075**         |
| 3           | 2                   | 1               | 9.958            | 87.10                                 | 174.20                      | 13.080             |
| 4           | 2                   | 2               | 9.956            | 87.13                                 | 174.26                      | 13.080             |
| 5           | 2                   | 3               | 10.064           | 86.00                                 | 172.00                      | 13.187             |
| 6           | 2                   | 4               | 9.970            | 87.03                                 | 174.06                      | 13.099             |
| 7           | 2                   | 5               | 9.965            | 87.04                                 | 174.09                      | 13.091             |
| 8           | 2                   | 6               | 9.965            | 87.03                                 | 174.05                      | 13.087             |
| 9           | 2                   | 7               | 9.957            | 87.11                                 | 174.21                      | 13.078             |
| 10          | 2                   | 8               | 9.968            | 86.99                                 | 173.97                      | 13.091             |

Text Summarization

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.861            | 87.01                                 | 87.01                       | 6.871              |
| **2**       | **2**               | **0**           | **9.972**        | **66.32**                             | **132.64**                  | **13.095**         |
| 3           | 2                   | 1               | 9.966            | 66.37                                 | 132.74                      | 13.093             |
| 4           | 2                   | 2               | 9.963            | 66.38                                 | 132.76                      | 13.087             |
| 5           | 2                   | 3               | 9.969            | 66.32                                 | 132.65                      | 13.101             |
| 6           | 2                   | 4               | 9.963            | 66.36                                 | 132.72                      | 13.093             |
| 7           | 2                   | 5               | 9.980            | 66.26                                 | 132.52                      | 13.107             |
| 8           | 2                   | 6               | 9.971            | 66.29                                 | 132.58                      | 13.103             |
| 9           | 2                   | 7               | 9.974            | 66.31                                 | 132.62                      | 13.108             |
| 10          | 2                   | 8               | 9.969            | 66.35                                 | 132.69                      | 13.102             |

Code Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.874            | 117.84                                | 117.84                      | 6.884              |
| **2**       | **2**               | **0**           | **9.958**        | **90.11**                             | **180.23**                  | **13.078**         |
| 3           | 2                   | 1               | 9.966            | 90.03                                 | 180.06                      | 13.089             |
| 4           | 2                   | 2               | 9.966            | 90.03                                 | 180.06                      | 13.089             |
| 5           | 2                   | 3               | 9.957            | 90.11                                 | 180.21                      | 13.087             |
| 6           | 2                   | 4               | 10.068           | 88.91                                 | 177.81                      | 13.189             |
| 7           | 2                   | 5               | 9.964            | 90.05                                 | 180.10                      | 13.087             |
| 8           | 2                   | 6               | 9.960            | 90.10                                 | 180.19                      | 13.082             |
| 9           | 2                   | 7               | 9.966            | 90.01                                 | 180.02                      | 13.091             |
| 10          | 2                   | 8               | 9.958            | 90.11                                 | 180.22                      | 13.081             |

Chatbot

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.856            | 82.55                                 | 82.55                       | 6.866              |
| **2**       | **2**               | **0**           | **9.950**        | **63.03**                             | **126.05**                  | **13.069**         |
| 3           | 2                   | 1               | 9.954            | 62.99                                 | 125.97                      | 13.077             |
| 4           | 2                   | 2               | 9.950            | 63.02                                 | 126.04                      | 13.064             |
| 5           | 2                   | 3               | 9.955            | 62.97                                 | 125.95                      | 13.075             |
| 6           | 2                   | 4               | 9.955            | 62.99                                 | 125.99                      | 13.072             |
| 7           | 2                   | 5               | 9.952            | 63.01                                 | 126.02                      | 13.072             |
| 8           | 2                   | 6               | 9.952            | 62.99                                 | 125.98                      | 13.074             |
| 9           | 2                   | 7               | 9.956            | 62.97                                 | 125.93                      | 13.077             |
| 10          | 2                   | 8               | 9.948            | 63.03                                 | 126.05                      | 13.067             |

Sentiment Analysis / Classification

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.857            | 77.14                                 | 77.14                       | 6.866              |
| **2**       | **2**               | **0**           | **9.968**        | **58.79**                             | **117.58**                  | **13.086**         |
| 3           | 2                   | 1               | 9.964            | 58.82                                 | 117.64                      | 13.090             |
| 4           | 2                   | 2               | 9.959            | 58.85                                 | 117.70                      | 13.088             |
| 5           | 2                   | 3               | 9.969            | 58.78                                 | 117.56                      | 13.096             |
| 6           | 2                   | 4               | 9.972            | 58.76                                 | 117.51                      | 13.097             |
| 7           | 2                   | 5               | 10.067           | 58.09                                 | 116.17                      | 13.193             |
| 8           | 2                   | 6               | 9.974            | 58.75                                 | 117.50                      | 13.099             |
| 9           | 2                   | 7               | 9.968            | 58.79                                 | 117.58                      | 13.090             |
| 10          | 2                   | 8               | 9.971            | 58.77                                 | 117.53                      | 13.096             |

Multi-turn Reasoning / Complex Tasks

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.861            | 82.35                                 | 82.35                       | 6.871              |
| **2**       | **2**               | **0**           | **9.970**        | **62.78**                             | **125.56**                  | **13.095**         |
| 3           | 2                   | 1               | 9.973            | 62.77                                 | 125.53                      | 13.103             |
| 4           | 2                   | 2               | 9.978            | 62.74                                 | 125.48                      | 13.106             |
| 5           | 2                   | 3               | 9.968            | 62.82                                 | 125.65                      | 13.098             |
| 6           | 2                   | 4               | 9.962            | 62.84                                 | 125.69                      | 13.092             |
| 7           | 2                   | 5               | 9.966            | 62.83                                 | 125.66                      | 13.100             |
| 8           | 2                   | 6               | 9.958            | 62.87                                 | 125.74                      | 13.085             |
| 9           | 2                   | 7               | 9.966            | 62.83                                 | 125.66                      | 13.098             |
| 10          | 2                   | 8               | 9.951            | 62.88                                 | 125.75                      | 13.098             |

**On 2-NC24 VM**

Text Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.918            | 93.96                                 | 93.96                       | 6.931              |
| **2**       | **2**               | **0**           | **6.954**        | **93.47**                             | **186.93**                  | **7.004**          |
| 3           | 3                   | 0               | 9.062            | 78.70                                 | 236.09                      | 13.311             |
| 4           | 4                   | 0               | 9.977            | 72.17                                 | 288.70                      | 13.192             |
| 5           | 4                   | 1               | 9.976            | 72.19                                 | 288.76                      | 13.190             |
| 6           | 4                   | 2               | 9.966            | 72.27                                 | 289.07                      | 13.175             |
| 7           | 4                   | 3               | 9.972            | 72.23                                 | 288.93                      | 13.171             |
| 8           | 4                   | 4               | 9.974            | 72.20                                 | 288.80                      | 13.176             |
| 9           | 4                   | 5               | 9.981            | 72.17                                 | 288.67                      | 13.184             |
| 10          | 4                   | 6               | 9.991            | 72.11                                 | 288.44                      | 13.206             |

Question Answering

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.852            | 92.24                                 | 92.24                       | 6.862              |
| **2**       | **2**               | **0**           | **6.859**        | **92.15**                             | **184.29**                  | **6.887**          |
| 3           | 3                   | 0               | 8.978            | 77.23                                 | 231.70                      | 13.185             |
| 4           | 4                   | 0               | 9.987            | 70.12                                 | 280.49                      | 13.191             |
| 5           | 4                   | 1               | 10.001           | 70.01                                 | 280.05                      | 13.196             |
| 6           | 4                   | 2               | 9.992            | 70.11                                 | 280.43                      | 13.187             |
| 7           | 4                   | 3               | 9.994            | 70.06                                 | 280.23                      | 13.193             |
| 8           | 4                   | 4               | 9.996            | 70.07                                 | 280.28                      | 13.206             |
| 9           | 4                   | 5               | 10.004           | 70.01                                 | 280.02                      | 13.231             |
| 10          | 4                   | 6               | 10.006           | 69.99                                 | 279.98                      | 13.204             |

Translation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.845            | 114.40                                | 114.40                      | 6.854              |
| 2           | 2                   | 0               | 9.952            | 87.14                                 | 174.27                      | 13.067             |
| 3           | 3                   | 0               | 8.957            | 95.92                                 | 287.75                      | 13.156             |
| **4**       | **4**               | **0**           | **9.970**        | **87.01**                             | **348.05**                  | **13.163**         |
| 5           | 4                   | 1               | 9.998            | 86.87                                 | 347.50                      | 13.163             |
| 6           | 4                   | 2               | 10.004           | 86.79                                 | 347.18                      | 13.267             |
| 7           | 4                   | 3               | 9.989            | 86.82                                 | 347.28                      | 13.186             |
| 8           | 4                   | 4               | 9.992            | 86.81                                 | 347.25                      | 13.204             |
| 9           | 4                   | 5               | 9.998            | 86.74                                 | 346.94                      | 13.199             |
| 10          | 4                   | 6               | 9.992            | 86.84                                 | 347.36                      | 13.192             |

Text Summarization

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.849            | 87.16                                 | 87.16                       | 6.859              |
| 2           | 2                   | 0               | 6.876            | 86.83                                 | 173.66                      | 6.916              |
| 3           | 3                   | 0               | 8.952            | 73.17                                 | 219.50                      | 13.154             |
| **4**       | **4**               | **0**           | **9.982**        | **66.27**                             | **265.08**                  | **13.171**         |
| 5           | 4                   | 1               | 9.991            | 66.19                                 | 264.76                      | 13.186             |
| 6           | 4                   | 2               | 9.995            | 66.17                                 | 264.69                      | 13.196             |
| 7           | 4                   | 3               | 9.998            | 66.16                                 | 264.63                      | 13.200             |
| 8           | 4                   | 4               | 9.990            | 66.22                                 | 264.87                      | 13.180             |
| 9           | 4                   | 5               | 9.994            | 66.18                                 | 264.71                      | 13.191             |
| 10          | 4                   | 6               | 9.990            | 66.19                                 | 264.78                      | 13.195             |

Code Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.905            | 117.31                                | 117.31                      | 6.916              |
| 2           | 2                   | 0               | 6.881            | 117.71                                | 235.43                      | 6.925              |
| 3           | 3                   | 0               | 8.911            | 99.51                                 | 298.54                      | 13.042             |
| **4**       | **4**               | **0**           | **9.967**        | **90.05**                             | **360.20**                  | **13.160**         |
| 5           | 4                   | 1               | 9.973            | 90.03                                 | 360.12                      | 13.165             |
| 6           | 4                   | 2               | 9.989            | 89.85                                 | 359.42                      | 13.177             |
| 7           | 4                   | 3               | 9.981            | 89.89                                 | 359.56                      | 13.184             |
| 8           | 4                   | 4               | 10.005           | 89.84                                 | 359.35                      | 13.186             |
| 9           | 4                   | 5               | 10.003           | 89.85                                 | 359.42                      | 13.264             |
| 10          | 4                   | 6               | 9.984            | 89.87                                 | 359.49                      | 13.168             |

Chatbot

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.890            | 82.15                                 | 82.15                       | 6.900              |
| 2           | 2                   | 0               | 6.873            | 82.35                                 | 164.70                      | 6.923              |
| 3           | 3                   | 0               | 8.905            | 69.59                                 | 208.76                      | 13.029             |
| **4**       | **4**               | **0**           | **9.972**        | **62.88**                             | **251.50**                  | **13.157**         |
| 5           | 4                   | 1               | 9.964            | 62.93                                 | 251.70                      | 13.143             |
| 6           | 4                   | 2               | 9.983            | 62.82                                 | 251.27                      | 13.168             |
| 7           | 4                   | 3               | 9.973            | 62.87                                 | 251.47                      | 13.158             |
| 8           | 4                   | 4               | 9.978            | 62.85                                 | 251.41                      | 13.165             |
| 9           | 4                   | 5               | 9.976            | 62.84                                 | 251.36                      | 13.165             |
| 10          | 4                   | 6               | 9.982            | 62.80                                 | 251.18                      | 13.175             |

Sentiment Analysis / Classification

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.839            | 77.35                                 | 77.35                       | 6.848              |
| 2           | 2                   | 0               | 6.882            | 76.87                                 | 153.75                      | 6.923              |
| 3           | 3                   | 0               | 8.937            | 64.78                                 | 194.33                      | 13.069             |
| **4**       | **4**               | **0**           | **9.981**        | **58.71**                             | **234.84**                  | **13.162**         |
| 5           | 4                   | 1               | 9.994            | 58.65                                 | 234.59                      | 13.180             |
| 6           | 4                   | 2               | 9.990            | 58.67                                 | 234.68                      | 13.183             |
| 7           | 4                   | 3               | 9.984            | 58.69                                 | 234.75                      | 13.173             |
| 8           | 4                   | 4               | 9.988            | 58.68                                 | 234.73                      | 13.176             |
| 9           | 4                   | 5               | 9.989            | 58.68                                 | 234.72                      | 13.179             |
| 10          | 4                   | 6               | 9.987            | 58.68                                 | 234.73                      | 13.187             |

Multi-turn Reasoning / Complex Tasks

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.914            | 81.72                                 | 81.72                       | 6.923              |
| 2           | 2                   | 0               | 10.031           | 62.28                                 | 124.57                      | 13.146             |
| 3           | 3                   | 0               | 8.983            | 68.98                                 | 206.93                      | 13.189             |
| **4**       | **4**               | **0**           | **10.014**       | **62.58**                             | **250.33**                  | **13.274**         |
| 5           | 4                   | 1               | 9.990            | 62.65                                 | 250.62                      | 13.181             |
| 6           | 4                   | 2               | 10.000           | 62.63                                 | 250.50                      | 13.201             |
| 7           | 4                   | 3               | 9.998            | 62.63                                 | 250.50                      | 13.191             |
| 8           | 4                   | 4               | 10.004           | 62.56                                 | 250.23                      | 13.203             |
| 9           | 4                   | 5               | 10.003           | 62.58                                 | 250.33                      | 13.203             |
| 10          | 4                   | 6               | 9.995            | 62.65                                 | 250.61                      | 13.200             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/motron-3-8b-chat-4k-steerlm-result.txt*



#### microsoft-Orca-2-7b  Series

```
#python  press-orca-20250324.py
```

**On 1 NC24 A100 VM**

Scenario: Text Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 0.823            | 123.97                                | 123.97                      | 0.824              |
| 2           | 2                   | 0               | 0.910            | 113.26                                | 226.53                      | 1.001              |
| 3           | 3                   | 0               | 0.934            | 110.67                                | 332.02                      | 2.552              |
| 4           | 4                   | 0               | 0.905            | 113.79                                | 455.15                      | 2.645              |
| 5           | 5                   | 0               | 0.891            | 115.60                                | 577.99                      | 5.122              |
| **6**       | **6**               | **0**           | **0.905**        | **113.90**                            | **683.38**                  | **5.294**          |
| 7           | 6                   | 1               | 0.903            | 114.13                                | 684.80                      | 8.956              |
| 8           | 6                   | 2               | 0.905            | 113.86                                | 683.14                      | 8.948              |
| 9           | 6                   | 3               | 0.901            | 114.40                                | 686.38                      | 8.954              |
| 10          | 6                   | 4               | 0.905            | 113.79                                | 682.73                      | 8.956              |

Scenario: Question Answering

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 12.923           | 36.91                                 | 36.91                       | 12.924             |
| **2**       | **2**               | **0**           | **18.866**       | **22.66**                             | **45.31**                   | **20.737**         |
| 3           | 2                   | 1               | 19.062           | 24.36                                 | 48.71                       | 21.826             |
| 4           | 2                   | 2               | 21.389           | 24.91                                 | 49.82                       | 26.283             |
| 5           | 2                   | 3               | 15.754           | 23.12                                 | 46.23                       | 17.297             |
| 6           | 3                   | 3               | 16.937           | 31.15                                 | 93.44                       | 30.978             |
| 7           | 2                   | 5               | 15.743           | 32.16                                 | 64.32                       | 43.801             |
| 8           | 2                   | 6               | 13.908           | 32.28                                 | 64.57                       | 21.131             |
| 9           | 2                   | 7               | 18.433           | 27.64                                 | 55.28                       | 24.266             |
| 10          | 2                   | 8               | 21.777           | 24.86                                 | 49.72                       | 27.765             |

Scenario: Translation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 0.770            | 85.77                                 | 85.77                       | 0.770              |
| 2           | 2                   | 0               | 0.823            | 80.64                                 | 161.29                      | 0.888              |
| 3           | 3                   | 0               | 0.803            | 82.60                                 | 247.81                      | 2.404              |
| 4           | 4                   | 0               | 0.824            | 80.60                                 | 322.41                      | 2.532              |
| 5           | 5                   | 0               | 0.812            | 81.77                                 | 408.87                      | 5.071              |
| **6**       | **6**               | **0**           | **0.825**        | **80.45**                             | **482.68**                  | **5.191**          |
| 7           | 6                   | 1               | 0.819            | 81.11                                 | 486.69                      | 8.939              |
| 8           | 6                   | 2               | 0.823            | 80.69                                 | 484.14                      | 8.947              |
| 9           | 6                   | 3               | 0.824            | 80.57                                 | 483.39                      | 8.958              |
| 10          | 6                   | 4               | 0.825            | 80.48                                 | 482.88                      | 9.004              |

Scenario: Text Summarization

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 10.704           | 34.29                                 | 34.29                       | 42.212             |
| **2**       | **2**               | **0**           | **12.568**       | **37.60**                             | **75.20**                   | **54.005**         |
| 3           | 2                   | 1               | 23.313           | 16.57                                 | 33.14                       | 24.345             |
| 4           | 2                   | 2               | 13.207           | 21.73                                 | 43.46                       | 14.209             |
| 5           | 2                   | 3               | 18.537           | 17.78                                 | 35.57                       | 46.308             |
| 6           | 2                   | 4               | 9.554            | 30.59                                 | 61.18                       | 13.468             |
| 7           | 2                   | 5               | 20.801           | 17.35                                 | 34.70                       | 21.731             |
| 8           | 2                   | 6               | 4.968            | 31.03                                 | 62.05                       | 37.485             |
| 9           | 2                   | 7               | 20.703           | 28.43                                 | 56.85                       | 49.412             |
| 10          | 2                   | 8               | 13.531           | 30.99                                 | 61.97                       | 34.817             |

Scenario: Code Generation

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 1.120            | 58.94                                 | 58.94                       | 1.120              |
| 2           | 2                   | 0               | 23.088           | 14.04                                 | 28.07                       | 23.142             |
| 3           | 3                   | 0               | 5.674            | 63.65                                 | 190.96                      | 17.093             |
| 4           | 4                   | 0               | 10.720           | 46.86                                 | 187.44                      | 22.350             |
| 5           | 5                   | 0               | 0.786            | 84.26                                 | 421.29                      | 5.050              |
| 6           | 6                   | 0               | 0.795            | 83.34                                 | 500.05                      | 5.158              |
| **7**       | **7**               | **0**           | **0.817**        | **81.53**                             | **570.71**                  | **5.148**          |
| 8           | 6                   | 2               | 0.789            | 83.98                                 | 503.90                      | 8.952              |
| 9           | 6                   | 3               | 0.782            | 84.77                                 | 508.61                      | 8.961              |
| 10          | 3                   | 7               | 5.550            | 35.41                                 | 106.23                      | 40.336             |

Scenario: Chatbot

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 9.625            | 32.83                                 | 32.83                       | 9.626              |
| 2           | 2                   | 0               | 2.157            | 33.40                                 | 66.81                       | 2.210              |
| 3           | 3                   | 0               | 2.292            | 47.40                                 | 142.20                      | 4.802              |
| 4           | 4                   | 0               | 4.011            | 38.16                                 | 152.66                      | 9.513              |
| **5**       | **5**               | **0**           | **6.584**        | **47.29**                             | **236.47**                  | **19.182**         |
| 6           | 3                   | 3               | 3.557            | 29.73                                 | 89.18                       | 8.957              |
| 7           | 4                   | 3               | 2.018            | 48.57                                 | 194.28                      | 8.957              |
| 8           | 2                   | 6               | 17.099           | 25.50                                 | 50.99                       | 22.971             |
| 9           | 4                   | 5               | 2.291            | 43.31                                 | 173.23                      | 8.963              |
| 10          | 6                   | 4               | 1.361            | 52.53                                 | 315.18                      | 8.955              |

Scenario: Sentiment Analysis / Classification

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 3.386            | 40.46                                 | 40.46                       | 3.386              |
| 2           | 2                   | 0               | 6.789            | 29.99                                 | 59.98                       | 9.033              |
| **3**       | **3**               | **0**           | **6.738**        | **27.11**                             | **81.32**                   | **11.781**         |
| 4           | 3                   | 1               | 6.793            | 27.84                                 | 83.52                       | 12.151             |
| 5           | 3                   | 2               | 6.138            | 29.22                                 | 87.66                       | 11.415             |
| 6           | 3                   | 3               | 6.546            | 27.69                                 | 83.06                       | 11.782             |
| 7           | 3                   | 4               | 6.961            | 26.49                                 | 79.46                       | 11.991             |
| 8           | 3                   | 5               | 6.760            | 27.82                                 | 83.47                       | 12.118             |
| 9           | 3                   | 6               | 7.486            | 26.17                                 | 78.52                       | 12.986             |
| 10          | 3                   | 7               | 7.258            | 26.31                                 | 78.93                       | 13.033             |

Scenario: Multi-turn Reasoning / Complex Tasks

| Concurrency | Successful Requests | Failed Requests | Average TTFT (s) | Avg Throughput per Request (tokens/s) | Total Throughput (tokens/s) | Batch Duration (s) |
| ----------- | ------------------- | --------------- | ---------------- | ------------------------------------- | --------------------------- | ------------------ |
| 1           | 1                   | 0               | 6.145            | 36.78                                 | 36.78                       | 6.145              |
| **2**       | **2**               | **0**           | **22.034**       | **23.67**                             | **47.35**                   | **46.358**         |
| 3           | 2                   | 1               | 17.041           | 22.51                                 | 45.01                       | 19.796             |
| 4           | 2                   | 2               | 21.611           | 23.69                                 | 47.38                       | 54.751             |
| 5           | 2                   | 3               | 14.438           | 33.82                                 | 67.64                       | 40.398             |
| 6           | 2                   | 4               | 22.884           | 21.02                                 | 42.03                       | 29.314             |
| 7           | 2                   | 5               | 8.214            | 27.26                                 | 54.52                       | 10.223             |
| 8           | 2                   | 6               | 8.298            | 29.74                                 | 59.49                       | 11.067             |
| 9           | 2                   | 7               | 23.508           | 30.74                                 | 61.47                       | 59.669             |
| 10          | 2                   | 8               | 21.661           | 22.80                                 | 45.60                       | 25.310             |

Full original test results are here:

*https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/testlogs/orca-result.txt*



## Performance test on Azure AI model inference

Currently, an increasing number of new flagship models in the Azure AI Foundry model catalog, including OpenAI, will be deployed using the Azure AI model inference method. 

*https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/deployments-overview*

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/23.png)

Models deployed in this way can be accessed via the AI Inference SDK,which now supports stream mode. Open-source models include DeepSeek R1, V3, Phi, Mistral, and more. 

*https://learn.microsoft.com/en-us/python/api/overview/azure/ai-inference-readme?view=azure-python-preview*

Azure AI model inference has a default quota. If you feel that the quota for the model is insufficient, you can apply for an increase separately. 

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/14.png)

***https://learn.microsoft.com/en-us/azure/ai-foundry/model-inference/quotas-limits#request-increases-to-the-default-limits***

| Limit name              | Applies to          | Limit value                                                  |
| ----------------------- | ------------------- | ------------------------------------------------------------ |
| Tokens per minute       | Azure OpenAI models | Varies per model and SKU. See [limits for Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits). |
| Requests per minute     | Azure OpenAI models | Varies per model and SKU. See [limits for Azure OpenAI](https://learn.microsoft.com/en-us/azure/ai-services/openai/quotas-limits). |
| **Tokens per minute**   | **DeepSeek models** | **5.000.000**                                                |
| **Requests per minute** | **DeepSeek models** | **5.000**                                                    |
| **Concurrent requests** | **DeepSeek models** | **300**                                                      |
| Tokens per minute       | Rest of models      | 200.000                                                      |
| Requests per minute     | Rest of models      | 1.000                                                        |
| Concurrent requests     | Rest of models      | 300                                                          |

After you have deployed models on Azure AI model inference, you can check their invocation methods：

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/11.png)

Prepare test env:

```
#conda create -n AImodelinference python=3.11 -y
#conda activate AImodelinference
#pip install azure-ai-inference
```

Run test script, after entering the following three variables, the stress test will begin:

```
#python callaiinference-20250406.py 
```

```
Please enter the Azure AI endpoint URL, such as https://xinyu.services.ai.azure.com/models format: https://ai-hubeastus869020590911.services.ai.azure.com/models

Please enter the Azure AI key: 4TSBez23vMtPSLPIXgye84oRznpvuYSTDKTr72t***RazJQQJ99BBACYeBjFXJ3w3AAAAACOGmXdu

Please enter the deployment name: DeepSeek-R1 

Please enter concurrency levels separated by commas (e.g. 1,2,3): 10,300
Received concurrency levels: [10, 300]
```



### Performance on DS 671B

I will use the test results of DeeSeek R1 on Azure AI model inference  as an example:

  **Max performance:**

• When the concurrency is 300 and the prompt length is 1024, TPS = 2110.77, TTFT = 2.201s.
 • When the concurrency is 300 and the prompt length is 2048, TPS = 1330.94, TTFT = 1.861s.

**Overall performance:** 

The overall throughput averages 735.12 tokens/s, with a P90 of 1184.06 tokens/s, full test result is as following:

| **Concurrency** | **Prompt Length** | **Total Requests** | **Success Count** | **Fail Count** | **Average latency (s)** | **Average TTFT (s)** | **Average token throughput (tokens/s)** | **Overall throughput (tokens/s)** |
| --------------- | ----------------- | ------------------ | ----------------- | -------------- | ----------------------- | -------------------- | --------------------------------------- | --------------------------------- |
| 300             | 1024              | 110                | 110               | 0              | 75.579                  | 2.580                | 22.54                                   | 806.84                            |
| 300             | 1024              | 110                | 110               | 0              | 71.378                  | 71.378               | 24.53                                   | 1028.82                           |
| 300             | 1024              | 110                | 110               | 0              | 76.622                  | 2.507                | 23.24                                   | 979.97                            |
| 300             | 1024              | 120                | 120               | 0              | 68.750                  | 68.750               | 24.91                                   | 540.66                            |
| 300             | 1024              | 120                | 120               | 0              | 72.164                  | 2.389                | 22.71                                   | 1094.90                           |
| 300             | 1024              | 130                | 130               | 0              | 72.245                  | 72.245               | 23.68                                   | 1859.91                           |
| 300             | 1024              | 130                | 130               | 0              | 82.714                  | 2.003                | 20.18                                   | 552.08                            |
| 300             | 1024              | 140                | 140               | 0              | 71.458                  | 71.458               | 23.79                                   | 642.92                            |
| 300             | 1024              | 140                | 140               | 0              | 71.565                  | 2.400                | 22.93                                   | 488.49                            |
| 300             | 1024              | 150                | 150               | 0              | 71.958                  | 71.958               | 24.21                                   | 1269.10                           |
| 300             | 1024              | 150                | 150               | 0              | 73.712                  | 2.201                | 22.35                                   | 2110.77                           |
| 300             | 2048              | 10                 | 10                | 0              | 68.811                  | 68.811               | 24.24                                   | 196.78                            |
| 300             | 2048              | 10                 | 10                | 0              | 70.189                  | 1.021                | 23.18                                   | 172.92                            |
| 300             | 2048              | 20                 | 20                | 0              | 73.138                  | 73.138               | 24.14                                   | 390.96                            |
| 300             | 2048              | 20                 | 20                | 0              | 69.649                  | 1.150                | 24.22                                   | 351.31                            |
| 300             | 2048              | 30                 | 30                | 0              | 66.883                  | 66.883               | 26.13                                   | 556.12                            |
| 300             | 2048              | 30                 | 30                | 0              | 68.918                  | 1.660                | 23.46                                   | 571.63                            |
| 300             | 2048              | 40                 | 40                | 0              | 72.485                  | 72.485               | 23.85                                   | 716.53                            |
| 300             | 2048              | 40                 | 40                | 0              | 65.228                  | 1.484                | 24.87                                   | 625.16                            |
| 300             | 2048              | 50                 | 50                | 0              | 68.223                  | 68.223               | 25.12                                   | 887.64                            |
| 300             | 2048              | 50                 | 50                | 0              | 66.288                  | 1.815                | 24.38                                   | 976.17                            |
| 300             | 2048              | 60                 | 60                | 0              | 66.736                  | 66.736               | 25.85                                   | 547.70                            |
| 300             | 2048              | 60                 | 60                | 0              | 69.355                  | 2.261                | 23.94                                   | 615.81                            |
| 300             | 2048              | 70                 | 70                | 0              | 66.689                  | 66.689               | 25.66                                   | 329.90                            |
| 300             | 2048              | 70                 | 70                | 0              | 67.061                  | 2.128                | 23.89                                   | 1373.11                           |
| 300             | 2048              | 80                 | 80                | 0              | 68.091                  | 68.091               | 25.68                                   | 1516.27                           |
| 300             | 2048              | 80                 | 80                | 0              | 67.413                  | 1.861                | 24.01                                   | 1330.94                           |
| 300             | 2048              | 90                 | 90                | 0              | 66.603                  | 66.603               | 25.51                                   | 418.81                            |
| 300             | 2048              | 90                 | 90                | 0              | 70.072                  | 2.346                | 23.41                                   | 1047.53                           |
| 300             | 2048              | 100                | 100               | 0              | 70.516                  | 70.516               | 24.29                                   | 456.66                            |
| 300             | 2048              | 100                | 100               | 0              | 86.862                  | 2.802                | 20.03                                   | 899.38                            |
| 300             | 2048              | 110                | 110               | 0              | 84.602                  | 84.602               | 21.16                                   | 905.59                            |
| 300             | 2048              | 110                | 110               | 0              | 77.883                  | 2.179                | 21.17                                   | 803.93                            |
| 300             | 2048              | 120                | 120               | 0              | 73.814                  | 73.814               | 23.73                                   | 541.03                            |
| 300             | 2048              | 120                | 120               | 0              | 86.787                  | 4.413                | 20.32                                   | 650.57                            |
| 300             | 2048              | 130                | 130               | 0              | 78.222                  | 78.222               | 22.61                                   | 613.27                            |
| 300             | 2048              | 130                | 130               | 0              | 83.670                  | 2.131                | 20.16                                   | 1463.81                           |
| 300             | 2048              | 140                | 140               | 0              | 77.429                  | 77.429               | 22.74                                   | 1184.06                           |
| 300             | 2048              | 140                | 140               | 0              | 77.234                  | 3.891                | 21.90                                   | 821.34                            |
| 300             | 2048              | 150                | 150               | 0              | 72.753                  | 72.753               | 23.69                                   | 698.50                            |
| 300             | 2048              | 150                | 150               | 0              | 73.674                  | 2.425                | 22.74                                   | 1012.25                           |
| 300             | 4096              | 10                 | 10                | 0              | 83.003                  | 83.003               | 25.52                                   | 221.28                            |
| 300             | 4096              | 10                 | 10                | 0              | 89.713                  | 1.084                | 24.70                                   | 189.29                            |
| 300             | 4096              | 20                 | 20                | 0              | 82.342                  | 82.342               | 26.65                                   | 337.85                            |
| 300             | 4096              | 20                 | 20                | 0              | 84.526                  | 1.450                | 24.81                                   | 376.17                            |
| 300             | 4096              | 30                 | 30                | 0              | 87.979                  | 87.979               | 24.46                                   | 322.62                            |
| 300             | 4096              | 30                 | 30                | 0              | 84.767                  | 1.595                | 24.28                                   | 503.01                            |
| 300             | 4096              | 40                 | 40                | 0              | 85.231                  | 85.231               | 26.03                                   | 733.50                            |
| 300             | 4096              | 40                 | 40                | 0              | 81.514                  | 1.740                | 24.17                                   | 710.79                            |
| 300             | 4096              | 50                 | 50                | 0              | 91.253                  | 91.253               | 24.53                                   | 279.55                            |



### Performance Phi-4

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/12.png)

![images](https://github.com/xinyuwei-david/AI-Foundry-Model-Performance/blob/main/images/13.png)

```
(AIF) root@pythonvm:~/AIFperformance# python callaiinference-20250406.py
Please enter the Azure AI key: G485wnXwMrAYQKMQPSYpzf7PNLm3sui8qgsXcYFv5Yd3HOmvzZ2GJQQJ99BCACPV0roXJ3w3AAAAACOG9kt1
Please enter the Azure AI endpoint URL: https://xinyu-m7zxv3ow-germanywestcentra.services.ai.azure.com/models
Please enter the deployment name: Phi-4
```

**Max performance:**

• When the concurrency is 300 and the prompt length is 1024, TPS = 1473.44, TTFT = 30.861s (Non-Stream Mode).
• When the concurrency is 300 and the prompt length is 2048, TPS = 849.75, TTFT = 50.730s (Non-Stream Mode).

**Overall performance:**

The overall throughput averages 735.12 tokens/s, with a P90 of 1184.06 tokens/s. Full test results are as follows:

| Concurrency | Prompt Length | Total Requests | Mode       | Success Count | Fail Count | Average Latency (s) | Average TTFT (s) | Average Token Throughput (tokens/s) | Overall Throughput (tokens/s) |
| ----------- | ------------- | -------------- | ---------- | ------------- | ---------- | ------------------- | ---------------- | ----------------------------------- | ----------------------------- |
| 300         | 128           | 20             | Non-Stream | 20            | 0          | 42.786              | 42.786           | 16.25                               | 259.47                        |
| 300         | 128           | 20             | Stream     | 20            | 0          | 41.799              | 0.971            | 15.86                               | 215.46                        |
| 300         | 128           | 30             | Non-Stream | 30            | 0          | 36.526              | 36.526           | 18.79                               | 464.05                        |
| 300         | 128           | 30             | Stream     | 30            | 0          | 29.335              | 1.016            | 22.19                               | 404.16                        |
| 300         | 128           | 40             | Non-Stream | 40            | 0          | 34.573              | 34.573           | 19.98                               | 635.16                        |
| 300         | 128           | 40             | Stream     | 40            | 0          | 37.575              | 1.096            | 17.29                               | 609.03                        |
| 300         | 128           | 50             | Non-Stream | 50            | 0          | 25.340              | 25.340           | 26.43                               | 1092.32                       |
| 300         | 128           | 50             | Stream     | 50            | 0          | 54.118              | 1.994            | 11.59                               | 438.72                        |
| 300         | 256           | 10             | Non-Stream | 10            | 0          | 31.659              | 31.659           | 26.99                               | 217.86                        |
| 300         | 256           | 10             | Stream     | 10            | 0          | 48.118              | 0.411            | 18.50                               | 90.95                         |
| 300         | 256           | 20             | Non-Stream | 20            | 0          | 23.250              | 23.250           | 34.82                               | 623.39                        |
| 300         | 256           | 20             | Stream     | 20            | 0          | 48.669              | 0.887            | 15.52                               | 259.49                        |
| 300         | 256           | 30             | Non-Stream | 30            | 0          | 41.130              | 41.130           | 20.32                               | 456.73                        |
| 300         | 256           | 30             | Stream     | 30            | 0          | 57.212              | 1.548            | 13.65                               | 323.89                        |
| 300         | 256           | 40             | Non-Stream | 40            | 0          | 57.891              | 57.891           | 14.17                               | 496.40                        |
| 300         | 256           | 40             | Stream     | 40            | 0          | 52.031              | 2.474            | 14.83                               | 435.96                        |
| 300         | 256           | 50             | Non-Stream | 50            | 0          | 45.228              | 45.228           | 17.69                               | 725.04                        |
| 300         | 256           | 50             | Stream     | 50            | 0          | 43.595              | 1.257            | 16.95                               | 712.82                        |
| 300         | 512           | 10             | Non-Stream | 10            | 0          | 32.092              | 32.092           | 26.78                               | 242.20                        |
| 300         | 512           | 10             | Stream     | 10            | 0          | 25.930              | 0.568            | 31.35                               | 245.37                        |
| 300         | 512           | 20             | Non-Stream | 20            | 0          | 34.330              | 34.330           | 26.04                               | 444.89                        |
| 300         | 512           | 20             | Stream     | 20            | 0          | 34.694              | 1.629            | 23.48                               | 408.55                        |
| 300         | 512           | 30             | Non-Stream | 30            | 0          | 34.773              | 34.773           | 25.91                               | 632.48                        |
| 300         | 512           | 30             | Stream     | 30            | 0          | 31.973              | 0.970            | 25.72                               | 632.10                        |
| 300         | 512           | 40             | Non-Stream | 40            | 0          | 36.616              | 36.616           | 24.19                               | 851.76                        |
| 300         | 512           | 40             | Stream     | 40            | 0          | 34.922              | 1.091            | 23.83                               | 783.17                        |
| 300         | 512           | 50             | Non-Stream | 50            | 0          | 36.638              | 36.638           | 24.40                               | 1003.91                       |
| 300         | 512           | 50             | Stream     | 50            | 0          | 34.217              | 1.433            | 23.82                               | 940.82                        |
| 300         | 1024          | 10             | Non-Stream | 10            | 0          | 28.029              | 28.029           | 36.46                               | 305.37                        |
| 300         | 1024          | 10             | Stream     | 10            | 0          | 30.585              | 0.428            | 31.08                               | 246.82                        |
| 300         | 1024          | 20             | Non-Stream | 20            | 0          | 31.945              | 31.945           | 32.23                               | 559.50                        |
| 300         | 1024          | 20             | Stream     | 20            | 0          | 24.585              | 0.949            | 37.25                               | 595.32                        |
| 300         | 1024          | 30             | Non-Stream | 30            | 0          | 30.950              | 30.950           | 33.02                               | 852.51                        |
| 300         | 1024          | 30             | Stream     | 30            | 0          | 25.622              | 1.014            | 36.02                               | 951.37                        |
| 300         | 1024          | 40             | Non-Stream | 40            | 0          | 31.642              | 31.642           | 32.85                               | 1198.05                       |
| 300         | 1024          | 40             | Stream     | 40            | 0          | 28.190              | 1.099            | 33.01                               | 1099.36                       |
| 300         | 1024          | 50             | Non-Stream | 50            | 0          | 30.861              | 30.861           | 32.97                               | 1473.44                       |
| 300         | 1024          | 50             | Stream     | 50            | 0          | 31.885              | 1.121            | 29.28                               | 1238.09                       |
| 300         | 2048          | 10             | Non-Stream | 10            | 0          | 27.862              | 27.862           | 42.47                               | 348.38                        |
| 300         | 2048          | 10             | Stream     | 10            | 0          | 27.356              | 0.439            | 36.49                               | 329.59                        |





