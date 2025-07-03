# MCP Server Hands-On Guide and Examples

This repository provides a practical, hands-on guide to using and integrating MCP (Model-Context Protocol) Servers. Through clear step-by-step examples, you will learn how to set up MCP Servers within VS Code, interact with AI models and tools (such as Open-WebUI and GitHub Copilot), and enhance AI workflows by creating custom MCP servers. Additionally, this guide will cover advanced integration patterns, including exposing MCP services securely via Azure API Management (APIM). The security-related scenarios, particularly the use of APIM to safely expose MCP Servers, will be detailed in an upcoming update to this guide.

## Integrating MCP Server into VS Code

There are several simple ways to integrate MCP Servers into VS Code, enabling you to easily connect AI models and custom tools into your IDE workflows. VS Code supports two main methods:

1. **Global Integration**: Configure MCP Servers globally, making them available within any VS Code workspace or project on your machine.
2. **Workspace-level Integration**: Configure MCP Servers specifically within a VS Code workspace (the folder currently opened in VS Code). These MCP Servers will only be available in that specific project.

You can set up your MCP Server integration in VS Code using either of these two approaches:

- **Adding as a Tool**: Directly add via the VS Code Chat Panel using the graphical interface.
- **Adding via Settings**: Manually specify your MCP Server configurations through the VS Code settings UI or by directly editing the configuration JSON file (`settings.json` or `mcp.json`).

Below are step-by-step instructions and examples for both methods.

### Adding MCP Server as a Tool within VS Code

**Using VS Code Chat Panel**
Open the Chat panel in VS Code, click the "**+**" button under the Tools section, and select "**Add MCP Server**":

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/1.png)

**Using VS Code Settings UI**
Alternatively, this configuration can also be done directly from the VS Code settings. Simply open the Settings page (`File` → `Preferences` → `Settings`), search for "**MCP Servers**," and configure your server details accordingly:

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/2.png)

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/4.png)

Below is my current global MCP Server configuration example.

- **Azure MCP Server**: For connecting directly with Azure MCP functionalities.
- **Playwright MCP server**: For automating web-based testing or browser automation scenarios.

```
{
  // Global MCP Server configuration in VS Code settings.json

  "mcp.servers": {
    "Azure MCP Server": {
      "command": "npx",
      "args": [
        "-y",
        "@azure/mcp@latest",
        "server",
        "start"
      ]
    },
    "Playwright MCP Server": {
      "type": "stdio",
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@executeautomation/playwright-mcp-server"
      ],
      "env": {}
    }
  }
}
```

## Manually Creating MCP Server Configuration Files in VS Code Directories

Another convenient approach is to set up MCP Server configurations by manually creating a JSON file within your VS Code workspace directory.

On Windows, for instance, you could create a project directory and add your JSON configuration files there:

Example:

```
C:\learn-mcp\.vscode\
```

**Note:**
VS Code MCP Server configurations may be defined either directly within your project's general settings file (`settings.json`) or as a separate dedicated configuration file (`mcp.json`):

- If you'd prefer combining your MCP Server configurations with other VS Code workspace settings, use `.vscode/settings.json` and define configurations under the fixed key `"mcp.servers"`.
- If you'd like to separate MCP Server configurations into a standalone file (for clarity, sharing, or automatic generation purposes), use `.vscode/mcp.json`.

Be aware that VS Code's Chat / Copilot extensions read configurations from both locations. If the same MCP Server name appears in both files, the definition in the second file loaded will overwrite the previous one.

### Using the `settings.json` file:

- File path: User-specific or workspace-specific `.vscode/settings.json`
- JSON key must be exactly: `"mcp.servers"`
- The corresponding value is an object, with each entry representing an MCP server (server name as key, and configuration details as the value)

Example:

```
{
  // .vscode/settings.json
  "mcp.servers": {
    "weather": {                 // ← 这是你自取的名字
      "type": "stdio",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": [
        "${workspaceFolder}\\mcp_server_weather.py"
      ]
    },
    "learn": {                   // 加一个 SSE 服务器也行
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  },
  "chat.mcp.discovery.enabled": true
}
```

#### Using a Dedicated `.vscode/mcp.json` File

When using a dedicated configuration file (`.vscode/mcp.json`), the structure differs slightly from `settings.json`:

- The top-level JSON object contains a single key named `servers`, which must be an array.
- Each array element represents the configuration object for an individual MCP server.

Example:

```
{
  // .vscode/mcp.json
  "servers": [
    {
      "type": "stdio",
      "name": "weather",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": [
        "${workspaceFolder}\\mcp_server_weather.py"
      ]
    },
    {
      "type": "sse",
      "name": "learn",
      "url": "http://localhost:8000/sse"
    }
  ]
}
```



## MCP Server Demonstrations

Below you will find a series of five interactive demos showcasing MCP Server usage in practical scenarios. Each demo highlights unique features and integration patterns, demonstrating how MCP Servers can enhance AI-driven workflows and simplify complex tasks.

1. **Playwright MCP Server Demo:**
   Demonstrates how an MCP Server can automate browser actions using Playwright, allowing AI agents to easily control browser behaviors directly from within VS Code.
2. **Weather and File MCP Server Demo:**
   A practical example illustrating how to create a custom local MCP server (in Python) to fetch weather data and then write this information automatically to local files, seamlessly managing the entire workflow with natural language prompt requests.
3. **SSE-based MCP Server with Microsoft Learn:**
   Introduces how MCP Servers can be connected via Server-Sent Events (SSE), demonstrating an interactive integration with Microsoft Learn's API. Includes examples on filtering content topics and performing keyword searches from within VS Code.
4. **Integrating SSE-based MCP Server with Open-WebUI:**
   Extends the previous scenario by securely exposing the SSE-based MCP Server through MCPO (MCP OpenAPI Proxy), integrating it seamlessly into Open-WebUI as an external tool, enabling AI chat interfaces to invoke custom tools effectively and securely.
5. **MCP Server via HTTP Streams with Open-WebUI:**
   Showcases a more advanced, high-performance integration pattern by demonstrating MCP Server over HTTP Streams, and integrating it with Open-WebUI. Explains how the HTTP Streams integration method offers better performance and improved response times compared to SSE.

Each of these demos is accompanied by practical examples, step-by-step explanations, and thorough illustrations, helping developers quickly understand, replicate, and build upon these capabilities.

#### Note：

Before running the demos below, it's recommended to enable the **"Autoprove"** option in VS Code. Turning on **Autoprove** helps reduce the number of manual confirmations required during MCP Server execution, providing a smoother and uninterrupted demonstration experience.

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/7.png)

#### **Demo1：playwright-mcp-server**

This demonstration showcases how to use MCP Server integrated with Playwright, a modern browser automation tool. In this demo, you will see how MCP enables AI agents (such as GitHub Copilot or other large-language models) to dynamically automate browser tasks—including navigating web pages, executing interactions, and running tests—directly from natural language prompts within VS Code.

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/AG1IBAiCvCk)



#### **Demo2：weather and file mcp server**

This demonstration illustrates how to create and use a custom local MCP Server in Python, integrated seamlessly with VS Code. In the demo, we build a simple MCP server that fetches detailed weather information (such as forecasts or temperature predictions) via open APIs. Then, using natural language prompts, the AI agent invokes this MCP Server to retrieve weather data for multiple cities, compares temperatures, determines which city will have the highest temperature tomorrow, and automatically writes the results into a local file.

First, set up your virtual Python environment and install the required dependencies:

```
# Create a virtual environment using Python 3.12
py -3.12 -m venv .venv

# Activate the virtual environment (in PowerShell)
.\.venv\Scripts\activate

# Install required packages into the virtual environment
pip install --upgrade "modelcontextprotocol[fast]" httpx
```

These commands will create an isolated Python environment named `.venv`, activate it, and then install the necessary dependencies (FastMCP and HTTPX) specifically into that environment.

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/5.png)

Contents of `C:\david-share\.vscode\settings.json`:

```
{
  "mcp.servers": {
    "weather": {
      "type": "stdio",
      "command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
      "args": [
        "${workspaceFolder}\\mcp_server_weather.py"
      ]
    }
  },
  "chat.mcp.discovery.enabled": true
}
```

This configuration defines a workspace-level MCP server named `"weather"`. It specifies the Python interpreter from the project's virtual environment to execute a custom Python script (`mcp_server_weather.py`), enabling the integration of your custom MCP Server directly into your VS Code environment.



Contents of the file `C:\david-share\mcp_server_weather.py`:

```
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mcp_server_weather.py
────────────────────────────────────────────────────────
An MCP (Model-Context Protocol) provider that exposes three
weather-related tools:

1. get_alerts(state: str)            -> active NWS alerts for a US state
2. get_forecast(lat: float, lon: float)
                                      -> 5-period detailed forecast
3. get_tomorrow_temp(city: str)      -> tomorrow’s forecast high for a city

The file is designed to run in **stdio** mode so that GitHub Copilot
or any other MCP-aware client can spawn it as a subprocess and call the
tools.

Dependencies (install once):
    pip install "modelcontextprotocol[fast]" httpx
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote
import httpx

# --------------------------------------------------------------------------- #
#  Import FastMCP with backward compatibility                                 #
# --------------------------------------------------------------------------- #
try:
    # Older preview releases
    from mcp.server.fastmcp import FastMCP        # type: ignore
except ModuleNotFoundError:                        # pragma: no cover
    # Official package name (newer releases)
    from modelcontextprotocol.server.fastmcp import FastMCP  # type: ignore


# --------------------------------------------------------------------------- #
#  Configuration                                                              #
# --------------------------------------------------------------------------- #
mcp = FastMCP(
    name="weather",           # provider name – must match settings.json
    host="127.0.0.1",
    port=6288,                # only used if you later switch to HTTP mode
    timeout=30
)

NWS_API_BASE   = "https://api.weather.gov"
USER_AGENT     = "weather-mcp/1.0"

GEOCODE_API    = "https://nominatim.openstreetmap.org/search"  # free geocoder
OPEN_METEO_API = "https://api.open-meteo.com/v1/forecast"      # free forecast


# --------------------------------------------------------------------------- #
#  Helpers                                                                    #
# --------------------------------------------------------------------------- #
async def _fetch_json(url: str) -> dict[str, Any] | None:
    """HTTP GET wrapper that returns parsed JSON or None on error."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json, application/json;q=0.9"
    }
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, headers=headers, timeout=30.0)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None


def _fmt_alert(feature: dict[str, Any]) -> str:
    """Pretty-print a single NWS alert feature."""
    p = feature["properties"]
    return (
        f"Event      : {p.get('event')}\n"
        f"Area       : {p.get('areaDesc')}\n"
        f"Severity   : {p.get('severity')}\n"
        f"Description: {p.get('description')}\n"
        f"Instructions: {p.get('instruction') or 'N/A'}"
    )


# --------------------------------------------------------------------------- #
#  MCP tools                                                                  #
# --------------------------------------------------------------------------- #
@mcp.tool()
async def get_alerts(state: str) -> str:
    """
    Return all active National Weather Service alerts for a US state.

    Args:
        state: Two-letter state code, e.g. CA, NY.
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state.upper()}"
    data = await _fetch_json(url)
    if not data or not data.get("features"):
        return "No active alerts."
    return "\n\n---\n\n".join(_fmt_alert(f) for f in data["features"])


@mcp.tool()
async def get_forecast(lat: float, lon: float) -> str:
    """
    Five-period detailed forecast for given coordinates.

    Args:
        lat:  Latitude  in decimal degrees
        lon:  Longitude in decimal degrees
    """
    points = await _fetch_json(f"{NWS_API_BASE}/points/{lat},{lon}")
    if not points:
        return "Point lookup failed."

    forecast_url: str = points["properties"]["forecast"]
    fc = await _fetch_json(forecast_url)
    if not fc:
        return "Forecast fetch failed."

    periods = fc["properties"]["periods"][:5]
    return "\n\n---\n\n".join(
        f"{p['name']}: {p['detailedForecast']} "
        f"({p['temperature']}°{p['temperatureUnit']}, "
        f"wind {p['windSpeed']} {p['windDirection']})"
        for p in periods
    )


@mcp.tool()
async def get_tomorrow_temp(city: str) -> str:
    """
    Tomorrow’s forecast high for a city (°C).

    Args:
        city: City name, e.g. "San Diego" or "Chicago".
    """
    # 1) Geocode city → lat/lon
    geo_url = f"{GEOCODE_API}?q={quote(city)}&format=json&limit=1"
    geo = await _fetch_json(geo_url)
    if not geo:
        return f"Could not geocode {city}"
    lat, lon = geo[0]["lat"], geo[0]["lon"]

    # 2) Fetch daily maximum temperature (metric)
    meteo_url = (
        f"{OPEN_METEO_API}?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max&timezone=auto"
    )
    meteo = await _fetch_json(meteo_url)
    if not meteo:
        return f"Forecast unavailable for {city}"

    try:
        tomorrow_max = meteo["daily"]["temperature_2m_max"][1]  # index 1 = tomorrow
        return f"{city}: {tomorrow_max}°C"
    except Exception:
        return f"Unexpected data format for {city}"


# --------------------------------------------------------------------------- #
#  Entry-point                                                                #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # VS Code (or any MCP client) will start this script in **stdio** mode,
    # so no network port needs to be opened.
    mcp.run(transport="stdio")
```



**Prompt:**
*"Compare the temperatures of San Diego, Chicago, and Boston for tomorrow to determine which city will have the highest temperature. Then create a file and write the result into it."*

In this demonstration, the AI agent automatically interprets the given natural-language instruction and orchestrates the entire workflow. Specifically, the agent calls the custom Weather MCP Server three times (once for each city) to retrieve weather forecasts. It then compares these temperatures, identifies which city will be the warmest tomorrow, and invokes another MCP server (Filesystem MCP server) to create and write the final result into a local file.



***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/BDVmIdW3H_0)

Chinese version demo:

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/Bo9QH9wJQXk)



### Demo 3: Connecting MCP Server Using Server-Sent Events (SSE)

This demo demonstrates another important integration pattern—connecting MCP Servers using **Server-Sent Events (SSE)**. Utilizing the `learn-mcp` example ([reference repository](https://github.com/softchris/learn-mcp/tree/main)), we build and run an SSE-enabled MCP Server that interacts with the Microsoft Learn platform.

Specifically, this example MCP Server offers useful functionalities such as filtering learning modules, performing targeted keyword searches, and retrieving curated learning resources directly from Microsoft Learn. It demonstrates how smoothly VS Code can leverage MCP Servers via SSE connections, allowing AI agents (e.g., GitHub Copilot) to invoke these capabilities directly through natural-language prompts and retrieve instant, relevant results.

Below, detailed step-by-step procedures, configurations, and demo scenario examples show how easily you can integrate MCP Servers using Server-Sent Events within VS Code.

Refer to: https://github.com/softchris/learn-mcp/tree/main， but I modified some codes.



Prepare test env:

```
root@xinyuwei:~#python -m venv venv
root@xinyuwei:~#source venv/bin/activate 
root@xinyuwei:~#cd mcp-learn
(base) root@xinyuwei:~/learn-mcp# pwd
/root/learn-mcp
root@xinyuwei:~#pip install requests "mcp[cli]"
root@xinyuwei:~#cd src
```

Check server.py

```
from utils.print_filter import print_filter
# from free_text import search_free_text
from search.search import search_learn
from search.free_text import search_free_text
from search.topic import search_topic
# from topic import search_learn_data

from utils.models import Filter, Result

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount, Host


mcp = FastMCP("Microsoft Learn Search", "0.1.0")

class Cache:
    entries: dict[str, Filter | Result] = {}

    def set_entry(self, key: str, data) -> None:
        self.entries[key] = data

    def get_entry(self, key: str) -> Filter | Result | None:
        return self.entries.get(key, None)


cache = Cache()

# TODO: cache response and possibly also filter what comes back

@mcp.tool()
def learn_filter() -> list[Filter]:
    data = cache.get_entry("learn_filters")
    if data is None:
        data = search_learn()
        cache.set_entry("learn_filters", data)
    return data

@mcp.tool()
def free_text(query: str) -> list[Result]:
    print("LOG: free_text called with query:", query)

    data = search_free_text(query)

    return data

@mcp.tool()
def topic_search(category: str, topic: str) -> list[Result]:
    print("LOG: topic_search called with category:", category, "and topic:", topic)

    data = search_topic(topic, category)

    return data

port = 8000

app = Starlette(
    routes=[
        Mount('/', app=mcp.sse_app()),
    ]
)
```

Start MCP Server：

```
(venv) (base) root@xinyuwei:~/learn-mcp/src# uvicorn server:app --host 0.0.0.0 --port 8000 --reload
INFO:     Will watch for changes in these directories: ['/root/learn-mcp/src']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [3123] using WatchFiles
INFO:     Started server process [3125]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     127.0.0.1:37778 - "POST /sse HTTP/1.1" 405 Method Not Allowed
INFO:     127.0.0.1:37794 - "GET /sse HTTP/1.1" 200 OK
INFO:     127.0.0.1:37808 - "POST /messages/?session_id=5c00ae866cc84cfeb4623b6bab8975c7 HTTP/1.1" 202 Accepted
INFO:     127.0.0.1:37818 - "POST /messages/?session_id=5c00ae866cc84cfeb4623b6bab8975c7 HTTP/1.1" 202 Accepted
INFO:     127.0.0.1:37824 - "POST /messages/?session_id=5c00ae866cc84cfeb4623b6bab8975c7 HTTP/1.1" 202 Accepted
INFO:mcp.server.lowlevel.server:Processing request of type ListToolsRequest
INFO:     127.0.0.1:37828 - "POST /messages/?session_id=5c00ae866cc84cfeb4623b6bab8975c7 HTTP/1.1" 202 Accepted
INFO:mcp.server.lowlevel.server:Processing request of type ListPromptsRequest
INFO:     127.0.0.1:35648 - "POST /messages/?session_id=5c00ae866cc84cfeb4623b6bab8975c7 HTTP/1.1" 202 Accepted
INFO:mcp.server.lowlevel.server:Processing request of type CallToolRequest
INFO:     127.0.0.1:48306 - "POST /messages/?session_id=5c00ae866cc84cfeb4623b6bab8975c7 HTTP/1.1" 202 Accepted
INFO:mcp.server.lowlevel.server:Processing request of type CallToolRequest
```

On VScode：

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/8.png)

```
{
  "mcp.servers": {
    "learn-sse": {
      "type": "sse",
      "url": "http://localhost:8000/sse"
    }
  },
  "chat.mcp.discovery.enabled": true
}
```

**Demo in Chinese version：**

Prompt on VScode:

```
请调用 learn_filter 工具，列出它返回的所有过滤类别，并各举 3 个可选值，用表格形式展示。
使用 free_text 工具，用关键词「Kubernetes」在 Microsoft Learn 上做自由搜索，只返回最热门的 5 条结果（只列标题和链接）。
请调用 topic_search 工具，在 category = "levels"、topic = "Beginner" 的条件下检索学习模块，列出 5 条结果（标题 + 链接）。
```

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/3J1gfjeNMuY)

**Demo in English version:**

Prompt:

```
Please invoke the learn_filter tool, list all filter categories it returns, and provide 3 example values for each category. Display the results in a tabular format.

Use the free_text tool to perform a free search on Microsoft Learn with the keyword "Kubernetes," and return only the top 5 results (titles and links only).

Please invoke the topic_search tool to search for learning modules under the conditions category = "levels" and topic = "Beginner," and list 5 results (titles and links).
```

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/FDT1opfiCQo)



### Demo4: Integrating SSE-based MCP Server with Open-WebUI

This demonstration builds upon the SSE-based MCP Server example from Demo 3, showcasing how to securely integrate the MCP Server with Open-WebUI—a popular conversational AI interface. Specifically, we take the local MCP server (running on your laptop) and expose it using MCPO (MCP OpenAPI Proxy), adding secure API access control via a specified API key. Once wrapped through MCPO, we add this secured MCP endpoint directly into Open-WebUI as an external tool. This integration allows Open-WebUI to seamlessly invoke your custom MCP Server within interactive AI chat sessions, directly via natural language instructions.

Install MCPO  firstly：

```
 pip install -U git+https://github.com/open-webui/mcpo.git@main
```

Wrap your SSE-based MCP Server using **MCPO (MCP OpenAPI Proxy)**. When wrapping your SSE-based MCP server with MCPO, you can specify an API key to enforce secure access and authentication. Below is how you can start MCPO on your local environment, forwarding securely authenticated traffic to your SSE MCP Server.

```
(venv) (base) root@xinyuwei:~/learn-mcp/src# mcpo --port 9000 --api-key top-secret      --server-type sse      -- http://127.0.0.1:8000/sse
Starting MCP OpenAPI Proxy on 0.0.0.0:9000 with command: http://127.0.0.1:8000/sse
INFO:mcpo.main:Starting MCPO Server...
INFO:mcpo.main:  Name: MCP OpenAPI Proxy
INFO:mcpo.main:  Version: 1.0
INFO:mcpo.main:  Description: Automatically generated API from MCP Tool Schemas
INFO:mcpo.main:  Hostname: xinyuwei
INFO:mcpo.main:  Port: 9000
INFO:mcpo.main:  API Key: Provided
INFO:mcpo.main:  CORS Allowed Origins: ['*']
INFO:mcpo.main:  Path Prefix: /
INFO:mcpo.main:Configuring for a single SSE MCP Server with URL http://127.0.0.1:8000/sse
INFO:mcpo.main:Uvicorn server starting...
INFO:     Started server process [7803]
INFO:     Waiting for application startup.
INFO:httpx:HTTP Request: GET http://127.0.0.1:8000/sse "HTTP/1.1 200 OK"
INFO:httpx:HTTP Request: POST http://127.0.0.1:8000/messages/?session_id=17dd92619f224ee3a0d1752146aab852 "HTTP/1.1 202 Accepted"
INFO:httpx:HTTP Request: POST http://127.0.0.1:8000/messages/?session_id=17dd92619f224ee3a0d1752146aab852 "HTTP/1.1 202 Accepted"
INFO:httpx:HTTP Request: POST http://127.0.0.1:8000/messages/?session_id=17dd92619f224ee3a0d1752146aab852 "HTTP/1.1 202 Accepted"
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C t
```

After wrapping your SSE MCP server using MCPO, you can integrate it securely into Open-WebUI as an external tool by entering the MCPO endpoint URL along with the specified API key in the Open-WebUI settings.



Install and start Open-WebUI by following these steps:

```
# On WSL (Windows Subsystem for Linux) on my laptop:
pip install open-webui
open-webui serve
```

After the Open-WebUI server is running, access the web interface by navigating to:
http://localhost:8080/



Next, you can securely connect and authenticate using the MCPO-generated URL as follows:

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/9.png)

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/10.png)

Then, add this MCP server URL as an external tool within Open-WebUI. Input the MCPO URL and the previously set API key ("top-secret") into the tool configuration in Open-WebUI:

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/11.png)

Once configured, your custom MCP Server becomes available as a callable tool during interactive conversations with large language models (LLMs) inside Open-WebUI:

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/14.png)

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/12.png)

![images](https://github.com/xinyuwei-david/Backend-of-david-share/blob/main/LLMs/MCP-Server/images/13.png)

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/n0IjzgnrNHM)

### Demo5: Integrating MCP Server via HTTP Streams with Open-WebUI

In this demo, we expose a locally running MCP Server via HTTP Streams. We utilize **MCPO (MCP OpenAPI Proxy)** ([available here](https://github.com/open-webui/mcpo)) to wrap and securely expose the MCP Server over HTTP Streams.

When configuring MCPO, you can set a secure API key for accessing the MCP Server. Afterward, add the generated MCPO URL as an external tool in Open-WebUI, entering the previously configured API key during setup for secure authentication.

Once set up, you can easily invoke your MCP Server directly within Open-WebUI as a native tool. This HTTP Streams integration method delivers much faster response times and better overall performance compared to SSE-based approaches.

The demonstration below illustrates the full workflow and integration steps, highlighting the improved responsiveness and ease-of-use provided by MCP Servers running over HTTP Streams with Open-WebUI.

```
root@xinyuwei:~#python -m venv venv
root@xinyuwei:~#source venv/bin/activate 
root@xinyuwei:~#cd mcp-learn
(base) root@xinyuwei:~/learn-mcp# pwd
/root/learn-mcp
root@xinyuwei:~#pip install requests "mcp[cli]"
root@xinyuwei:~#cd src
```

Check source MCP Server code:

```
(base) root@xinyuwei:~/learn-mcp/src# cat server1.py
# server1.py  —— 运行 Streamable-HTTP 的 Microsoft-Learn MCP Server

from utils.print_filter import print_filter
from search.search import search_learn
from search.free_text import search_free_text
from search.topic import search_topic
from utils.models import Filter, Result

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Microsoft Learn Search", "0.1.0")

class Cache:
    entries: dict[str, Filter | Result] = {}

    def set_entry(self, key: str, data) -> None:
        self.entries[key] = data

    def get_entry(self, key: str) -> Filter | Result | None:
        return self.entries.get(key, None)

cache = Cache()

@mcp.tool()
def learn_filter() -> list[Filter]:
    data = cache.get_entry("learn_filters")
    if data is None:
        data = search_learn()
        cache.set_entry("learn_filters", data)
    return data

@mcp.tool()
def free_text(query: str) -> list[Result]:
    print("LOG: free_text called with query:", query)
    return search_free_text(query)

@mcp.tool()
def topic_search(category: str, topic: str) -> list[Result]:
    print("LOG: topic_search called with category:", category, "and topic:", topic)
    return search_topic(topic, category)

# 关键：直接把 streamable_http_app 暴露为顶层 ASGI App
app = mcp.streamable_http_app()   # 端点自动位于  /mcp

# 仅供 “python server1.py” 调试用；生产可用 systemd / supervisor 等
if __name__ == "__main__":
    # 用外部 uvicorn 启动
    import uvicorn
    uvicorn.run("server1:app", host="0.0.0.0", port=8000, reload=True)
```

Start MCP server:

```
(base) root@xinyuwei:~/learn-mcp/src# uvicorn server1:app --host 0.0.0.0 --port 8000 --reload
INFO:     Will watch for changes in these directories: ['/root/learn-mcp/src']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [3399] using WatchFiles
INFO:     Started server process [3401]
INFO:     Waiting for application startup.
[07/03/25 05:37:41] INFO     StreamableHTTP session manager started                   streamable_http_manager.py:109
INFO:     Application startup complete.
```

Wrap your SSE-based MCP Server using **MCPO (MCP OpenAPI Proxy)**. When wrapping your SSE-based MCP server with MCPO, you can specify an API key to enforce secure access and authentication. Below is how you can start MCPO on your local environment, forwarding securely authenticated traffic to your SSE MCP Server.

```
ERROR:    Application startup failed. Exiting.
(venv) (base) root@xinyuwei:~# mcpo --port 9000 --api-key "top-secret" \
     --server-type "streamable_http"    \
     -- http://127.0.0.1:8000/mcp
Starting MCP OpenAPI Proxy on 0.0.0.0:9000 with command: http://127.0.0.1:8000/mcp
INFO:mcpo.main:Starting MCPO Server...
INFO:mcpo.main:  Name: MCP OpenAPI Proxy
INFO:mcpo.main:  Version: 1.0
INFO:mcpo.main:  Description: Automatically generated API from MCP Tool Schemas
```

Then, add this MCP server URL as an external tool within Open-WebUI. Input the MCPO URL and the previously set API key ("top-secret") into the tool configuration in Open-WebUI:

![images](https://github.com/xinyuwei-david/Azure-MCP-Solution/blob/main/images/15.png)

As shown clearly in this demonstration, integrating the MCP server via HTTP Streams provides significantly faster response times and a more responsive user experience compared to the SSE-based integration method.

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/DI32kB1iuAs)

