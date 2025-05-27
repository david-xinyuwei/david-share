# Foundry Local Functionality Verification

**Refer to： **https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/get-started

Your system must meet the following requirements to run Foundry Local:
Operating System: Windows 10 (x64), Windows 11 (x64/ARM), Windows Server 2025, macOS.
Hardware: Minimum 8GB RAM, 3GB free disk space. Recommended 16GB RAM, 15GB free disk space.
Network: Internet connection for initial model download (optional for offline use)
Acceleration (optional): NVIDIA GPU (2,000 series or newer), AMD GPU (6,000 series or newer), Qualcomm Snapdragon X Elite (8GB or more of memory), or Apple silicon.



### Install and Run Foundry Local on my Surface Laptop

On Powershell to install

```
winget install Microsoft.FoundryLocal
```

Start foundry service for open-webui  connection:

```
PS C:\Users\xinyuwei> foundry service status
🔴 Model management service is not running!
To start the service, run the following command: foundry service start


PS C:\Users\xinyuwei>  foundry service start
🟢 Service is Started on http://localhost:5273, PID 42864!


PS C:\Users\xinyuwei> foundry service status
🟢 Model management service is running on http://localhost:5273/openai/status

```

On  WLS of my Laptop:

```
pip install open-webui
open-webui serve
```

Access  http://localhost:8080/ of open-webui

**Connect Open Web UI to Foundry Local**:

1. Select **Settings** in the navigation menu
2. Select **Connections**
3. Select **Manage Direct Connections**
4. Select the **+** icon to add a connection
5. For the **URL**, enter `http://localhost:PORT/v1` where `PORT` is replaced with the port of the Foundry Local endpoint, which you can find using the CLI command `foundry service status`. Note, that Foundry Local dynamically assigns a port, so it's not always the same.
6. Type any value (like `test`) for the API Key, since it can't be empty.
7. Save your connection

**Note:** The local models visible on Open-WebUI are models that have already been pulled locally using Foundry through PowerShell.



***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/NpYDsGXFrAU)
