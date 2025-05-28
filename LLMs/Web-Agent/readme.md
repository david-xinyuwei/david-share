# Agent Web: NLWeb

*Refer to https://github.com/microsoft/NLWeb*

The essential implementation principle of NLweb is Retrieval-Augmented Generation (RAG). It constructs embedding data using content from website RSS feeds within AI Search, enabling users or customers to conversationally query the website's content through a chat interface. Additionally, NLWeb provides a wealth of web interfaces. For an overview of the overall effect, please refer to my demo video below.

***Please click below pictures to see my demo video on Youtube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/byfcPxY_Mz0)

## How to start

Follow this steps to install and config NLWeb, it is very easy:

*https://github.com/microsoft/NLWeb/blob/main/docs/nlweb-hello-world.md*

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