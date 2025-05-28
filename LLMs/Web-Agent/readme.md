# Agent Web: NLWeb Introduction and tuning

*Refer to https://github.com/microsoft/NLWeb*

The essential implementation principle of NLweb is Retrieval-Augmented Generation (RAG). It constructs embedding data using content from website RSS feeds within AI Search, enabling users or customers to conversationally query the website's content through a chat interface. Additionally, NLWeb provides a wealth of web interfaces. For an overview of the overall effect, please refer to my demo video below.

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/byfcPxY_Mz0)

Inside AI Search index:

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Web-Agent/images/1.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/Web-Agent/images/2.png)

## How to start

Follow this steps to install and config NLWeb, it is very easy:

*https://github.com/microsoft/NLWeb/blob/main/docs/nlweb-hello-world.md*



Configuration file examples:

(NLWeb) root@linuxworkvm:~/NLWeb/code# cat .env

```
AZURE_VECTOR_SEARCH_ENDPOINT="https://aisearch-xinyu.search.windows.net" 
AZURE_VECTOR_SEARCH_API_KEY="C*"

AZURE_OPENAI_ENDPOINT="https://aoai1-xinyu.openai.azure.com/"
AZURE_OPENAI_API_KEY="B*"
AZURE_OPENAI_API_VERSION="2025-01-01-preview"
ANTHROPIC_API_KEY="<TODO>"

INCEPTION_ENDPOINT="https://api.inceptionlabs.ai/v1/chat/completions"
INCEPTION_API_KEY="<TODO>"

OPENAI_ENDPOINT="https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY="<TODO>"

SNOWFLAKE_ACCOUNT_URL="<TODO>"
SNOWFLAKE_PAT="<TODO>"
# One of https://docs.snowflake.com/en/user-guide/snowflake-cortex/vector-embeddings#text-embedding-models
SNOWFLAKE_EMBEDDING_MODEL=snowflake-arctic-embed-l-v2.0

# Fully qualified name of the cortex search service in your snowflake account
# For example TEMP.NLWEB.NLWEB_SAMPLE
# if you used snowflake.sql with --database TEMP --schema NLWEB
SNOWFLAKE_CORTEX_SEARCH_SERVICE=TODO


# IF USING QDRANT FOR RETRIEVAL
QDRANT_URL="http://localhost:6333"
QDRANT_API_KEY="<OPTIONAL>"

# Local Directory for file writes
#NLWEB_OUTPUT_DIR=/home/sites/data/nlweb

# NLWeb Logging profile (production, development, testing)
# This is used to set the logging level and other configurations in config/config_logging.py
NLWEB_LOGGING_PROFILE=production
```

(NLWeb) root@linuxworkvm:~/NLWeb/code# cat config/config_llm.yaml 

```
preferred_provider: azure_openai

providers:
  inception:
    api_key_env: INCEPTION_API_KEY
    api_endpoint_env: INCEPTION_ENDPOINT
    models:
      high: mercury-small
      low: mercury-small

  openai:
    api_key_env: OPENAI_API_KEY
    api_endpoint_env: OPENAI_ENDPOINT
    models:
      high: gpt-4.1
      low: gpt-4.1-mini

  anthropic:
    api_key_env: ANTHROPIC_API_KEY
    models:
      high: claude-3-5-sonnet-20241022
      low: claude-3-haiku-20240307

  gemini:
    api_key_env: GCP_PROJECT
    models:
      high: chat-bison@001
      low: chat-bison-lite@001

  azure_openai:
    api_key_env: AZURE_OPENAI_API_KEY
    api_endpoint_env: AZURE_OPENAI_ENDPOINT
    api_version_env: "2025-01-01-preview"
    models:
      high: gpt-4o-mini
      low: gpt-4o-mini

  llama_azure:
    api_key_env: LLAMA_AZURE_API_KEY
    api_endpoint_env: LLAMA_AZURE_ENDPOINT
    api_version_env: "2024-12-01-preview"
    models:
      high: llama-2-70b
      low: llama-2-13b

  deepseek_azure:
    api_key_env: DEEPSEEK_AZURE_API_KEY
    api_endpoint_env: DEEPSEEK_AZURE_ENDPOINT
    api_version_env: "2024-12-01-preview"
    models:
      high: deepseek-coder-33b
      low: deepseek-coder-7b

      
  snowflake:
    api_key_env: SNOWFLAKE_PAT
    api_endpoint_env: SNOWFLAKE_ACCOUNT_URL
    api_version_env: "2024-12-01"
    models:
      high: claude-3-5-sonnet
      low: llama3.1-8b
```



After that, you will get 7 access points:

| #    | URL (http://<HOST>:8000/…) | File name         | Purpose / what you get                                       |
| ---- | -------------------------- | ----------------- | ------------------------------------------------------------ |
| 1    | / ‑or- /static/index.html  | index.html        | Full-featured chat UI (text box, streaming bubbles, citation cards). Ready to use out of the box. |
| 2    | /static/nlws.html          | nlws.html         | Bare-bones template (input box only). Ships **without** JS wiring; add `nlweb.js` or your own script if you need a minimal, skinnable shell. |
| 3    | /static/nlwebsearch.html   | nlwebsearch.html  | “Search-bar” style interface: single input at the top, results listed below. Good demo of list-style output. |
| 4    | /static/str_chat.html      | str_chat.html     | Streaming-chat demo. Shows tokens appearing live as the answer streams back; includes a site-selector drop-down. |
| 5    | /static/small_orange.html  | small_orange.html | Mini chat window with an orange color theme—demonstrates how to embed NLWeb as a small branded widget. |
| 6    | /static/debug.html         | debug.html        | Developer view. Displays the raw JSON payloads that NLWeb sends / receives alongside the rendered answer—useful for troubleshooting prompts, embeddings, etc. |
| 7    | /static/mcp_test.html      | mcp_test.html     | Simple form to manually POST to `/mcp/ask`. Lets you experiment with the Model Context Protocol by filling method, question, site, etc., and seeing the raw JSON response. |