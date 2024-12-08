# Magentic-One Test

In recent years, the field of generative artificial intelligence has been experiencing a surge in "multi-agent" systems, including Microsoft's AutoGen and the latest Magentic-One, OpenAI's Swarm, LangChain's LangGraph, CrewAI, and others. This repository mainly introduces the architecture and implementation effects of Magentic-One.

## Framework Overview

As Microsoft's latest multi-agent framework, Magentic-One is a simplification and optimization based on AutoGen. It aims to lower the threshold for use, allowing more users to conveniently build multi-agent systems.

***Project：***

https://github.com/microsoft/autogen/tree/main/python/packages/autogen-magentic-one

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWPwCzrPKVrpfg6MRD5wYQ5nSa90HoMdjybSIvwoKN4OuiciaJ8LBvlxkyamwxGZqh8QhJOheOoYEOg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**Pre-configured Agent Collection:** The framework comes with an orchestrator agent (Orchestrator) and four functional agents:

- **WebSurfer:** Browse and interact with web content.

- **FileSurfer:** Manage and access local files.

- **Coder:** Focus on code writing and analysis.

- **ComputerTerminal:** Provide a command-line interface to execute programs and install libraries.

  **Based on AutoGen:** Inherits the advantages of AutoGen while simplifying operations.

  **Performance Analysis Tool:** Integrated with AutoGenBench to evaluate the performance and efficiency of agents.



Next, I will showcase three demos, each utilizing the capabilities of different agents in Magentic-One, allowing it to:

**Demo1:** Generate automatically executable Python code.

**Demo2:** Search online for the weather and ticket prices of tourist attractions.

**Demo3:** Write an article and automatically save it as a txt document.



## Demo1: Generating a Christmas Star with Python code

***Please click below pictures to see my demo vedios on Yutube***:
[![Magentic-One-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/UGYW0b8pfV0)



## Demo2:  Search online for the weather and ticket prices of tourist attractions.

***Please click below pictures to see my demo vedios on Yutube***:
[![Magentic-One-demo2](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/UBsulNUiEKM)

**Please click below pictures to see my demo vedios on Yutube***:
[![Magentic-One-demo2](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/fMeDYgLtAU8)

## Demo3: Write an article and automatically save it as a txt document.

***Please click below pictures to see my demo vedios on Yutube***:
[![Magentic-One-demo3](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/wwpWHeMn29M)

When Magentic-One is performing tasks, its operating environment is Docker. 

```
(python) (base) root@davidwei:~/autogen/python/packages/autogen-magentic-one# docker ps
CONTAINER ID   IMAGE           COMMAND     CREATED         STATUS         PORTS     NAMES
40404f16de35   python:3-slim   "/bin/sh"   7 seconds ago   Up 7 seconds             autogen-code-exec-5bc62ef0-70ac-4d72-a5d0-ecffd366741f
```

