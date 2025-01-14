# Dify work with Microsoft AI Search

Dify is an open-source platform for developing large language model (LLM) applications. It combines the concepts of Backend as a Service (BaaS) and LLMOps, enabling developers to quickly build production-grade generative AI applications.

Dify offers various types of tools, including first-party and custom tools. These tools can extend the capabilities of LLMs, such as web search, scientific calculations, image generation, and more. On Dify, you can create more powerful AI applications, like intelligent assistant-type applications, which can complete complex tasks through task reasoning, step decomposition, and tool invocation.

In the repo, we are going to show how could Dify work with Azure AI Search and Azure OpenAI to achieve RAG

## Dify works with AI Search Demo

Till now, Dify could not integrate with Microsoft directly via default Dify web portal. Let me show how to achieve it.

***Please click below pictures to see my demo video on Yutube***:
[![dify-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://www.youtube.com/watch?v=20GjS6AtjTo)

## Dify works with AI Search Configuration steps



#### **Configure on AI search**



Create index, make sure you could get the result from AI search index:

<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/1.png" alt="images" style="width:80%;">  



Run dify on VM via docker:

```
root@a100vm:~# docker ps |grep -i dify
5d6c32a94313   langgenius/dify-api:0.8.3          "/bin/bash /entrypoi…"   3 months ago   Up 3 minutes             5001/tcp                                                                   docker-worker-1
264e477883ee   langgenius/dify-api:0.8.3          "/bin/bash /entrypoi…"   3 months ago   Up 3 minutes             5001/tcp                                                                   docker-api-1
2eb90cd5280a   langgenius/dify-sandbox:0.2.9      "/main"                  3 months ago   Up 3 minutes (healthy)                                                                              docker-sandbox-1
708937964fbb   langgenius/dify-web:0.8.3          "/bin/sh ./entrypoin…"   3 months ago   Up 3 minutes             3000/tcp                                                                   docker-web-1
```

Then Access dify portal via the URL of your dify container.

####  **Create customer tool in Dify portal,set schema:**



<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/3.png" alt="images" style="width:80%;">  



#### **schema details:**

```
{
  "openapi": "3.0.0",
  "info": {
    "title": "Azure Cognitive Search Integration",
    "version": "1.0.0"
  },
  "servers": [
    {
      "url": "https://ai-search-eastus-xinyuwei.search.windows.net"
    }
  ],
  "paths": {
    "/indexes/wukong-doc1/docs": {
      "get": {
        "operationId": "getSearchResults",
        "parameters": [
          {
            "name": "api-version",
            "in": "query",
            "required": true,
            "schema": {
              "type": "string",
              "example": "2024-11-01-preview"
            }
          },
          {
            "name": "search",
            "in": "query",
            "required": true,
            "schema": {
              "type": "string"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful response",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "@odata.context": { "type": "string" },
                    "value": {
                      "type": "array",
                      "items": {
                        "type": "object",
                        "properties": {
                          "@search.score": { "type": "number" },
                          "chunk_id": { "type": "string" },
                          "parent_id": { "type": "string" },
                          "title": { "type": "string" },
                          "chunk": { "type": "string" },
                          "text_vector": { "type": "SingleCollection" },
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```



#### **Set AI Search AI key:**

<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/4.png" alt="images" style="width:80%;">  



#### **Do search test:**

<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/5.png" alt="images" style="width:80%;">  



#### **Input words:**



<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/6.png" alt="images" style="width:80%;">  



#### **Create a workflow on dify:**



<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/7.png" alt="images" style="width:80%;">  



#### **Check AI search stage:**



<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/8.png" alt="images" style="width:80%;">  



#### **Check LLM stage:**



<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/9.png" alt="images" style="width:80%;">  



#### **Run workflow:**

<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/10.png" alt="images" style="width:80%;">  



#### **Get workflow result:**

<img src="https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Dify-With-AI-Search/images/11.png" alt="images" style="width:80%;">  
