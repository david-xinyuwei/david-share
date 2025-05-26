

On Powershell：

```
Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

Install the latest PowerShell for new features and improvements! https://aka.ms/PSWindows

Loading personal and system profiles took 1207ms.


PS C:\Users\xinyuwei> foundry service status
🔴 Model management service is not running!
To start the service, run the following command: foundry service start


PS C:\Users\xinyuwei>  foundry service start
🟢 Service is Started on http://localhost:5273, PID 42864!


PS C:\Users\xinyuwei> foundry service status
🟢 Model management service is running on http://localhost:5273/openai/status
PS C:\Users\xinyuwei> nvidia-smi
Sun May 25 23:54:10 2025
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 538.92                 Driver Version: 538.92       CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                     TCC/WDDM  | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA RTX A2000 Laptop GPU  WDDM  | 00000000:F3:00.0 Off |                  N/A |
| N/A   50C    P0              10W /  39W |    370MiB /  4096MiB |      5%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+

+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A     42864      C   ...3d8bbwe\Inference.Service.Agent.exe    N/A      |
+---------------------------------------------------------------------------------------+
PS C:\Users\xinyuwei> nvidia-smi
Sun May 25 23:54:13 2025
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 538.92                 Driver Version: 538.92       CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                     TCC/WDDM  | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA RTX A2000 Laptop GPU  WDDM  | 00000000:F3:00.0 Off |                  N/A |
| N/A   50C    P0              10W /  39W |   2490MiB /  4096MiB |     21%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+

+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A     42864      C   ...3d8bbwe\Inference.Service.Agent.exe    N/A      |
+---------------------------------------------------------------------------------------+
PS C:\Users\xinyuwei> nvidia-smi
Mon May 26 08:01:36 2025
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 538.92                 Driver Version: 538.92       CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                     TCC/WDDM  | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA RTX A2000 Laptop GPU  WDDM  | 00000000:F3:00.0 Off |                  N/A |
| N/A   60C    P8               3W /  39W |      0MiB /  4096MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+

+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A     42864      C   ...3d8bbwe\Inference.Service.Agent.exe    N/A      |
+---------------------------------------------------------------------------------------+
PS C:\Users\xinyuwei> nvidia-smi
Mon May 26 08:01:37 2025
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 538.92                 Driver Version: 538.92       CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                     TCC/WDDM  | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA RTX A2000 Laptop GPU  WDDM  | 00000000:F3:00.0 Off |                  N/A |
| N/A   60C    P8               3W /  39W |      0MiB /  4096MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+

+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A     42864      C   ...3d8bbwe\Inference.Service.Agent.exe    N/A      |
+---------------------------------------------------------------------------------------+
```

On Linux:

```
  483  open-webui serve
  
  http://localhost:8080/
```

