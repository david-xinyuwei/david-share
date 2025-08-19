# NLWeb Introduction and tuning

***Refer to: https://github.com/microsoft/NLWeb***



NLWeb (Natural Language Web) wraps a classic Retrieval-Augmented-Generation (RAG) loop in a production-ready service. During ingestion a one-line `tools.db_load` command converts RSS, JSON-LD, or schema.org feeds into vector embeddings and stores them in the configured back-end (Azure AI Search, Qdrant, Milvus, Snowflake Cortex, etc.). At query time the `/mcp/ask` endpoint—defined by the open Model-Context-Protocol—retrieves relevant chunks, passes them to an LLM, and returns a schema.org Answer JSON-LD object, complete with citations and rendering instructions. Additional MCP tools (`list_tools`, `get_sites`, `get_prompt`, …) let agent frameworks discover NLWeb automatically. Out of the box the repo also ships several front-end templates (full chat page, streaming mini-widget, dropdown search bar) that consume the same API and stream answers via Server-Sent Events. With those layers in place, any site that exposes an RSS feed can be turned into a conversational, agent-friendly endpoint in minutes.

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/byfcPxY_Mz0)

Inside AI Search index:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/Web-Agent/images/1.png)

Fields in the Index:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/Web-Agent/images/2.png)

## How to start

Follow this steps to install and config NLWeb, it is very easy:

*https://github.com/microsoft/NLWeb/blob/main/docs/nlweb-hello-world.md*



Configuration file examples.

I use AI search and Azure OpenAI in NLWeb

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

I use Azure OpenAI gpt-4o-mini as backend LLM:

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



## MCP tools in the code

| Tool name    | Purpose (one-liner)                                          | Required / common params                                     | Minimal cURL example                                         |
| ------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| ask          | Core lookup + answer generation. Send a natural-language question, receive a schema.org Answer. | `query` (question text) <br>`site` (optional) <br>`streaming` (optional) | `bash<br>curl -X POST http://<HOST>:8000/mcp/ask \ <br>  -H "Content-Type: application/json" \ <br>  -d '{"function_call":{"name":"ask","arguments":"{\"query\":\"Who directed Blade Runner?\",\"site\":\"Decoder\"}"}}'` |
| ask_nlw      | Alias of **ask** (kept for backward compatibility).          | same as **ask**                                              | just change `"name":"ask"` to `"name":"ask_nlw"`             |
| list_prompts | List all built-in prompt IDs / descriptions—useful for choosing or extending prompts. | none                                                         | `bash<br>curl -X POST http://<HOST>:8000/mcp/ask \ <br>  -H "Content-Type: application/json" \ <br>  -d '{"function_call":{"name":"list_prompts","arguments":"{}"}}'` |
| get_prompt   | Fetch the full text of a specific prompt (`prompt_id`).      | `prompt_id`                                                  | `bash<br>curl -X POST http://<HOST>:8000/mcp/ask \ <br>  -H "Content-Type: application/json" \ <br>  -d '{"function_call":{"name":"get_prompt","arguments":"{ \"prompt_id\":\"technical\" }"}}'` |
| get_sites    | Return the list of sites currently allowed for search (driven by `include_sites` in config.yaml). | none                                                         | `bash<br>curl -X POST http://<HOST>:8000/mcp/ask \ <br>  -H "Content-Type: application/json" \ <br>  -d '{"function_call":{"name":"get_sites","arguments":"{}"}}'` |

## Full 12-step walkthrough that shows how a single MCP request travels through NLWeb

### ① Process start – `app-file.py`

```
code/app-file.py
asyncio.run(
    start_server(
        host='0.0.0.0',
        port=PORT,
        fulfill_request=fulfill_request  # ⇦ hands off to the main router
))
```



`start_server` is defined in `webserver/WebServer.py`.

------

### ② Routing – `WebServer.py`

```
elif path.find("mcp") != -1:          # matches /mcp/**
    if path in ("/mcp/health", "/mcp/healthz"):
        ...   # health probe
    else:
        await handle_mcp_request(     # ⇨ core MCP handler
            query_params, body,
            send_response, send_chunk,
            streaming=use_streaming)
    return
```



- `/mcp/health` → `200 { "status": "ok" }`
- any other `/mcp/*` → handled by `core/mcp_handler.py`.

------

### ③ Entry `handle_mcp_request`

File `core/mcp_handler.py`

```
request_data  = json.loads(body)
function_call = request_data.get("function_call", {})
name          = function_call.get("name")   # ask / list_tools …
```



If `name` is `ask` / `ask_nlw` / `query` / `search` → call `handle_ask_function()`.

------

### ④ Parse arguments & validate site

```
arguments = json.loads(function_call["arguments"])
query     = arguments.get("query")   # required
site      = arguments.get("site")    # optional

validated_query_params = handle_site_parameter(query_params)
# ↑  compares with CONFIG.get_allowed_sites() / include_sites
```



- If `site` is missing → fall back to `allowed_sites`.
- If `site` not allowed → warn and also fall back.

------

### ⑤ Branch: non-stream vs stream

- streaming == False
  - `result = await NLWebHandler(...).runQuery()`
  - Wrap once:

```
mcp_response = {
  "type"  : "function_response",
  "status": "success",
  "response": result    # result contains nlws / Answer
}
```



- streaming == True
  - `send_response()` writes SSE headers
  - Build `MCPFormatter(send_chunk)`
  - Pass formatter to `NLWebHandler`; each step sends `type:"function_stream_event"`, final chunk `type:"function_stream_end"`.

------

### ⑥ NLWebHandler → GenerateAnswer

If `generate_mode=generate`, WebServer instantiates

```
GenerateAnswer(query_params, handler)   # see core/generate_answer.py
```



- `prepare()` – query analysis, memory, missing-info checks
- `retrieve()` – vector search (retrieval/retriever.py)
- `rankItem()` – low-tier LLM scores each item
- `synthesizeAnswer()` – high-tier LLM writes the final answer

Output:

```
{
  "message_type": "nlws",
  "answer": "…",
  "items": [ { url, name, description, site, schema_object } ]
}
```



------

### ⑦ Embed chatbot instructions

`add_chatbot_instructions()` pulls
`CONFIG.chatbot_instructions.search_results` and, in non-stream mode, appends guidance for the front-end (e.g., Markdown card formatting).

------

### ⑧ Wrap as MCP `function_response`

```
await send_response(200, {"Content-Type":"application/json"})
await send_chunk(json.dumps({
   "type"  : "function_response",
   "status": "success",
   "response": result_with_instructions
}), end_response=True)
```



Stream mode emits many
`data: { "type":"function_stream_event", … }\n\n`
and ends with `function_stream_end`.

------

### ⑨ Other MCP tools

- `handle_list_tools_function()` – returns JSON list of ask / list_prompts …
- `handle_list_prompts_function()` – demo prompt list
- `handle_get_prompt_function()` – returns one prompt’s text
- `handle_get_sites_function()` – lists the `include_sites` collections

All use the same wrapper
`{ "type":"function_response","status":"success","response":{…} }`.

------

### ⑩ Dataclass / Pydantic models

```
code/api/mcp_models.py
class AskRequest:  question:str  site:str | list[str] | None …
class AskResponse: answer:str    items:list[dict]     # schema.org objects
```



Imported elsewhere for static typing.

------

### ⑪ Config & extension points

- `include_sites` – which collections can MCP query
- `chatbot_instructions.search_results` – tells the LLM how to format output
- `llm_timeout`, `max_parallel` – tune 429 / timeout handling
- Add new tools: create another `elif function_name == "your_tool": …` block in `mcp_handler.py`.

------

### ⑫ Minimal cURL examples

**Non-stream**

```
curl -X POST http://<HOST>:8000/mcp/ask \
  -H "Content-Type: application/json" \
  -d '{
        "function_call":{
          "name":"ask",
          "arguments":"{\"query\":\"Who directed Blade Runner?\",\"site\":\"Decoder\"}"
        }
      }'
```



Returns

```
{
  "type":"function_response",
  "status":"success",
  "response":{
    "message_type":"nlws",
    "answer":"Blade Runner (1982) was directed by Ridley Scott.",
    "items":[ { …schema.org PodcastEpisode… } ]
  }
}
```



**Streaming**

```
curl -N -H "Accept:text/event-stream" \
     -X POST http://<HOST>:8000/mcp/ask \
     -H "Content-Type: application/json" \
     -d '{
           "function_call":{
             "name":"ask",
             "arguments":"{\"query\":\"List 3 latest episodes\",\"streaming\":true}"
           }
         }'
```



You will receive
`data: {"type":"function_stream_event", "content":{"partial_response": …}}`
and finally
`data: {"type":"function_stream_end","status":"success"}`.

With that, the entire MCP path—WebServer routing → mcp_handler dispatch → GenerateAnswer RAG → schema.org Answer → MCP wrap (streaming or not)—is fully traced across the files you just inspected.
