# Work IQ MCP：retrieve、fetch、fetch_blob 各返回什么，各自到哪里为止

[![工具](https://img.shields.io/badge/%E5%B7%A5%E5%85%B7-retrieve%20%C2%B7%20fetch%20%C2%B7%20fetch__blob-0078D4)](#实现效果)
[![实测](https://img.shields.io/badge/%E5%AE%9E%E6%B5%8B-2026%20%E5%B9%B4%2011%20%E6%9C%88%2027%20%E6%97%A5%20%C2%B7%20%E4%B8%80%E4%B8%AA%E7%A7%9F%E6%88%B7-0078D4)](docs/RESULTS_CN.md#测试环境)
[![有记录的工具调用](https://img.shields.io/badge/%E6%9C%89%E8%AE%B0%E5%BD%95%E7%9A%84%E5%B7%A5%E5%85%B7%E8%B0%83%E7%94%A8-109%20%E6%AC%A1-0078D4)](results/limits.json)
[![复现](https://img.shields.io/badge/%E5%A4%8D%E7%8E%B0-Python%20%2B%20Microsoft%20Edge-0078D4)](#操作步骤)
[![离线测试](https://img.shields.io/badge/%E7%A6%BB%E7%BA%BF%E6%B5%8B%E8%AF%95-28%20%E9%A1%B9%20unittest-0078D4)](docs/TESTING_CN.md)

作者：魏新宇 · [English](README.md)

## 目的

智能体通过 Work IQ MCP 处理用户的邮件、聊天和文件，通常是先搜索，再去读搜到的内容。动手做之前，团队需要知道每一步到哪里为止：一次搜索返回几条结果，每条结果带回多少文字，之后能不能读到整封邮件或整个文件，文件最大能多大，列表能不能读到第一页之后。

这次测试于 2026 年 11 月 27 日在一个真实的 Microsoft 365 租户里，用 Work IQ MCP 的三个读取工具 `retrieve`、`fetch`、`fetch_blob` 把这些限制实测了一遍，并与 Microsoft Learn 文档写明的限制逐条对照。它回答四个问题：

1. 一个问题发给 `retrieve`，返回几条结果？返回的是全文还是摘录？
2. `fetch` 能不能读到整封邮件？列表能不能读到第一页之后？
3. `fetch_blob` 能返回多大的文件？超过之后会怎样？
4. 实测到的限制与文档写的一致吗？

答案在[实现效果](#实现效果)。测试环境、方法、每一次调用的明细和没有覆盖的范围，见 [`docs/RESULTS_CN.md`](docs/RESULTS_CN.md)。想在自己的租户里测一遍，按[操作步骤](#操作步骤)做。

<img src="images/official_BRK302_slide13.png" width="900" alt="微软的一页幻灯片，标题 Work IQ toolset。左边的框：13 tools，Verbs that stay the same（动词保持不变），列出 retrieve、ask、list_agents、fetch、fetch_blob、create_entity、update_entity、delete_entity、do_action、call_function、search_paths、get_schema、listen。中间的框：Work IQ，tool + path。右边的框：Paths，Nouns that keep growing（名词不断增加）：/me/… 对应 Microsoft 365，/businessapps/… 对应业务应用，/&lt;provider&gt;/… 对应 Memory、连接器和合作伙伴。下面三行示例：fetch /me/messages/{id} 读一封邮件；do_action /me/messages/{id}/forward 转发一个会话；update_entity /businessapps/…/records/{id} 更新一条 CRM 记录。">

微软自己是怎么介绍这些工具的：Ignite 2026 场次 BRK302 “Build personalized AI experiences with Work IQ” 的第 13 页（[场次页面](https://ignite.microsoft.com/en-US/sessions/BRK302)、[幻灯片下载](https://medius.microsoft.com/video/asset/PPT/e241973d-6bc2-4333-8aa4-d78d94c37b2b)），整页原样展示。一次调用就是一个工具加一个路径。这次测试覆盖 13 个工具里的三个：`retrieve`、`fetch`、`fetch_blob`。幻灯片上有一个工具叫 `listen`；测试当天服务返回的工具列表里没有 `listen`，有 `discover`，其余 12 个名字相同（见 [`results/tools_list.json`](results/tools_list.json)）。

<img src="images/limits-overview-zh.png" width="900" alt="从左到右的示意图。你的智能体是一个 MCP 客户端，向 Work IQ MCP 端点发送 tools/call。1，retrieve，跨邮件、文件、聊天和会议做搜索：每次调用返回 0 到 13 条结果，没有“要几条”或“下一页”的参数；每条结果的 snippet 字段最长 9,441 个字符，这是实测到的最长值，长内容只给摘录、不给全文；72 条结果里有 38 条被服务标了 Content has been truncated，这些结果每条只有 1,733 到 1,802 个字符；每条结果都在 entityUrl 里带原件的路径，右边两个工具可以按它去读。2，fetch，按路径读邮件、聊天消息、日程和元数据：返回邮件正文全文，读到的最大一封有 930,551 个字符；$top 每页最多 100 条，聊天消息是 20 条，用 @odata.nextLink 或 $skip 取下一页；每次调用 50 个路径，51 个路径时返回 InternalError。3，fetch_blob，读 OneDrive 或 SharePoint 里的文件：4 MB 以内返回整个文件，逐字节一致，4,117,319 字节的文件读回来与本机副本完全相同；4,194,352 字节起拒绝，报 Payload too large，文件内容一点也不返回。">

图里是什么：三个读取工具，以及这次测试里各自停在哪里。`retrieve` 负责搜索，返回少量结果，每条带一段最长 9,441 个字符的摘录和原件的路径。`fetch` 按这个路径读回整封邮件，读列表时每页最多 100 条。`fetch_blob` 返回 4 MB 以内的整个文件，更大的文件拒绝返回。这是本仓库的原创解释图：上面那页幻灯片没有写任何限制，所以另画了这张；图中每个数字都读自 [`results/limits.json`](results/limits.json)。

引用这里的数字之前，先知道三件事：

- **只代表一个租户、一个用户、一天。** Microsoft Learn 把 `fetch` 读列表的限制称为“per-tenant policy limits”，即按租户配置的策略限制；其中三条在这里与文档写的数值不同（见[结果 4](#结果-4文档写的限制有三条与实测不同)）。按某个数字做设计之前，先在自己的租户里测一遍，[操作步骤](#操作步骤)大约 15 分钟。
- **`retrieve` 还在公开预览。** [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/retrieve#use-markdown-for-model-grounding) 要求客户端不要从它返回的 Markdown 里解析稳定字段，因为格式“can change”。下文的字段名 `snippet` 和 `truncationInfo` 是测试当天服务写出来的。
- **Live 模式的调用读的是真实数据，并消耗 Copilot Credits。** 发出调用的页面自己写着：“Live mode: calls run against your real tenant data and consume Copilot credits.” 完整响应只留在你电脑上的私有文件夹里。本仓库没有任何邮件、聊天、文件或会议的内容，也没有任何条目的 ID：只有每次调用问了什么（ID 已换成占位文字），以及服务返回的条数、大小、用时、字段名和报错原文。

## 实现效果

四个结果：

1. [`retrieve` 返回的是少量摘录，不是全文](#结果-1retrieve-返回的是少量摘录不是全文)：每次调用 0 到 13 条结果，每条最多 9,441 个字符；72 条结果里有 38 条被标了 `Content has been truncated`，这些结果每条只有 1,733 到 1,802 个字符。
2. [`fetch` 返回整封邮件，列表可以一页一页读](#结果-2fetch-返回整封邮件列表可以一页一页读)：930,551 个字符的邮件正文完整返回；`$top` 每页最多 100 条，聊天消息 20 条；用 `@odata.nextLink` 和 `$skip` 能读到后面的页；一次调用带 50 个路径有响应，51 个及以上都失败。
3. [`fetch_blob` 返回整个文件，上限 4 MB](#结果-3fetch_blob-返回整个文件上限-4-mb)：4,117,319 字节的文件读回来与本机文件完全一致；4,194,352 字节的文件被拒绝。
4. [文档写的限制有三条与实测不同](#结果-4文档写的限制有三条与实测不同)：不带 `$top` 时没有默认 25 条，聊天消息每次是 20 条而不是 10 条，`$skip` 没有被屏蔽。

数据来源：2026 年 11 月 27 日的 109 次有记录的工具调用（`fetch` 78 次、`fetch_blob` 9 次、`retrieve` 22 次），都经微软的 [Work IQ MCP Interactive Demo 页面](https://interactivedemo.microsoft.com/work-iq/mcp?server=workiq-remote)在 Live 模式下发出，范围是一个租户、一个登录用户、读他自己的数据。109 个响应的 HTTP 状态码全部是 200，被拒绝的调用也一样：工具把拒绝或报错写在响应内容里，不体现在 HTTP 状态码上。没有一个响应报限流；一分钟内最多 12 次调用，所以这不是压力测试。一次调用的耗时中位数：`fetch` 1.0 秒，`fetch_blob` 2.9 秒，`retrieve` 7.4 秒（在一台电脑的页面里计时，包含这台电脑到服务之间的网络）。截图是这些调用进行时产品自己的页面，ID 已遮盖。

### 结果 1：retrieve 返回的是少量摘录，不是全文

<img src="images/official_BRK302_slide14.png" width="900" alt="微软的一页幻灯片，标题 Retrieve with grounding: cited passages for your agent，副标题 Your model does the reasoning. Work IQ returns the evidence。左边是一个请求：retrieve，strategy 为 grounding，query 为 portal language decision，以登录用户的身份发出。请求下面是响应，标着 passages, no synthesis（只给片段，不做归纳）：片段 1，Legal review, 21 Oct，Launch must be bilingual；片段 2，Requirements.docx §4.2，Two languages at launch。右边四个框：Raw evidence，由你的模型来写答案；Permission-trimmed，只有用户本人能打开的内容；Cited，每个片段都带出处；Your content，Microsoft 365 加上已同步的连接器。">

微软自己说 `retrieve` 返回什么：同一场次的第 14 页，整页原样展示。返回的是一组带出处的片段，不是原件全文，也不是写好的答案。幻灯片没有给出条数和长度。下面的图和表是这次测试量出来的：一次调用返回几个片段，每个片段有多长。

<img src="images/retrieve-snippets-zh.png" width="900" alt="柱状图：20 次调用共返回 72 条结果，其中 70 条带 snippet 字段，图中是这 70 条各自的字符数，按长度排序，纵轴从 0 到 10,000 个字符。被服务标了 Content has been truncated 的 38 条是红色，全部在 1,733 到 1,802 个字符之间。没有这个标记的 32 条是蓝色，从 575 到 9,441 个字符。中位数 1,798，最大 9,441。">

一根柱子是一条结果。红色：Markdown 里带 `truncationInfo: Content has been truncated` 这一行的 38 条，每条 1,733 到 1,802 个字符。蓝色：没有这一行的 32 条，575 到 9,441 个字符。

| `retrieve` 这次调用问了什么 | 返回的结果条数 |
|---|---|
| “What was announced about Work IQ at Microsoft Ignite 2026?”，搜全部来源 | 5 |
| 同一个调用再发一次 | 3 |
| 把问句换成关键词（“Work IQ MCP retrieve tool”），发两次 | 0 和 0 |
| 同一个问题用中文问 | 0 |
| 同一个问题，`strategy: "copilot"`（用时 50.6 秒；其他有响应的调用是 3.9 到 12.1 秒） | 3 |
| 同一个问题，只搜一类来源：Email、OneDriveAndSharePoint、TeamsMessages、Meetings、People | 2、4、2、2、0 |
| 同一个问题，加上工具没有列出的参数 `top: 50` | 4 |
| 问题后面加一句 “Return 50 results.” | 13 |
| 问题后面加一句 “Return 100 results.” | 7 |
| 第二个问题 “What important emails did I receive in the last week?”，英文和中文各问一次 | 7 和 7 |

要点：

- **结果条数很少，而且不由调用方决定。** 有响应的 20 次调用返回 0 到 13 条。工具没有“要几条”或“下一页”的参数，响应里也没有指向更多结果的链接。加上工具没有列出的参数 `top: 50`，没有报错，返回 4 条，介于同一个问题不带这个参数时的 5 条和 3 条之间。在问题里要 50 条，得到 13 条；要 100 条，得到 7 条；其他调用最多返回 7 条。同一个问题发两次，先得到 5 条、再得到 3 条，两次都出现的来源只有 2 个。
- **每条结果带的是摘录。** `results[].markdown` 里是一行标题、若干元数据行和一个 `snippet` 字段。72 条结果里 70 条有这个字段：中位数 1,798 个字符，最长 9,441 个。最长的一条 `markdown` 有 11,599 个字符；一次调用返回的 Markdown 合计最多 43,236 个字符。
- **没有截断标记，不等于给了全文。** 结果里的 16 条邮件和聊天消息，都用 `fetch` 读回原文做了对比。其中 14 条没有截断标记，而这 14 条里有 8 条的摘录比原文还短，不可能是全文。最长的一封邮件正文有 238,687 个字符（不计空白），摘录是 8,978 个字符，没有 `truncationInfo` 这一行。短消息可以完整带回：有 3 条 481 到 1,211 个字符的消息，从正文里抽的 21 个采样片段在结果里全部找到了。
- **原件多大都一样。** 结果里的 14 个文件，大小从 25,915 字节到 817,685,365 字节。最大的是一段会议录像，带回来的摘录是 1,800 个字符。
- **索引里命中的远多于一次调用返回的。** 只搜 OneDriveAndSharePoint 的那次调用，响应自带的元数据写着 “117690 results for File domains”，实际返回 4 条。
- **每条结果都带原件的路径。** `entityUrl`（例如 `/me/messages/{id}` 或 `/drives/{id}/items/{id}`）可以直接当 `fetch` 的路径用：读回的 30 个原件全部成功。14 个文件里有 7 个超过 `fetch_blob` 能返回的 4 MB（见[结果 3](#结果-3fetch_blob-返回整个文件上限-4-mb)）。

每次调用的明细、一条结果有哪些字段、30 个原件的对比，见 [`docs/RESULTS_CN.md`](docs/RESULTS_CN.md#retrieve每一次调用)。

### 结果 2：fetch 返回整封邮件，列表可以一页一页读

<img src="images/ui_skip.png" width="900" alt="Interactive Demo 页面，Live 模式，工具 fetch。请求：entityUrls 里只有一个路径 /me/messages?$select=id&amp;$top=2&amp;$skip=3。响应：results 里有两封邮件，ID 已遮盖；@odata.nextLink 是 /me/messages?%24select=id&amp;%24top=2&amp;%24skip=5；statusCode 200；还有一条提示 Results limited to 2 items per collection. If you need different results, refine your $filter or $search parameters.">

调用 `/me/messages?$select=id&$top=2&$skip=3` 时产品页面的截图：状态码 200，返回两封邮件，`@odata.nextLink` 从 `$skip=5` 接着往下，服务自己加的提示写着 “Results limited to 2 items per collection”。邮件 ID、ETag 和用户的对象 ID 已遮盖。

| 发给 `fetch` 的路径或参数 | 返回了什么 |
|---|---|
| `/me/messages`，不带 `$top` | 10 条 |
| `$top=25`、`$top=26`、`$top=100` | 25、26、100 条 |
| `$top=101`、`$top=1000` | 100 条，并带提示 “Results limited to 100 items per collection” |
| `$top=5&$skip=5` | 列表的第 6 到第 10 条 |
| 把 `$top=100` 那次响应里的 `@odata.nextLink` 当作路径发回去 | 另外 100 封邮件 |
| `$top=5&$skip=5000` | 5 条 |
| 一个聊天里的消息：不带 `$top`、`$top=11`、`$top=50`（各测 3 个聊天），`$top=21`（1 个聊天） | 20、11、20、20 条 |
| 100 封邮件，`$select=id,body` | 100 篇正文共 5,686,377 个字符，一次响应 7,690,363 字节，用时 5.3 秒 |
| 一次调用 50 个路径、一次调用 51 个路径 | 50 个结果、`InternalError` |

<img src="images/ui_51_paths.png" width="900" alt="Interactive Demo 页面，Live 模式，工具 fetch。请求：entityUrls 里重复写着路径 /me?$select=id，列表在输入框可见部分之下还有。响应：error 为 An internal error occurred. Contact support if the problem persists，errorCode 为 InternalError，recoveryAction 为 None。">

51 个路径的那次调用（[`cases/fetch_51_paths.json`](cases/fetch_51_paths.json)）：服务返回 `InternalError`。同样的调用换成 50 个路径，返回 50 个结果。

要点：

- **正文是完整的。** 读到的最大一篇正文有 930,551 个字符。那次 100 封邮件的响应里，96 篇有内容的 HTML 正文全部以 `</html>` 结尾；另有 1 篇正文为空，3 篇是纯文本。短的是 `bodyPreview` 字段，最多 255 个字符。
- **一页最多 100 条，聊天消息是 20 条。** `$top` 超过这个数会被改小，响应的 `note` 里会写明。不带 `$top` 时，每页条数因集合而异：邮件、日程、联系人是 10 条，聊天列表 19 条，聊天消息 20 条，OneDrive 一个文件夹的 163 个子项一次全部返回。
- **列表可以读到第一页之后。** 请求里的 `$skip` 有效；把响应里的 `@odata.nextLink` 当作路径发回去，就得到下一页。这个链接对邮件和日程带的是 `$skip`，对聊天列表、聊天消息、OneDrive 文件夹和 `$search` 带的是 `$skiptoken`。按日期的 `$filter` 和 `$search` 也都能用。
- **没有看到“只能查最近多久”的限制。** 邮件按时间从旧到新排，第一封是 2022 年 10 月的；问 `retrieve` 2023 年的邮件，它返回了 2023 年 3 月和 8 月的邮件。
- **一次调用带 50 个路径有响应，带 51 到 100 个都失败。** 带 2、20、50 个路径的调用，每个路径都返回了结果；结果 1 里读回 30 个原件，就是一次调用完成的。带 51、53、56、62、75、100 个路径的 6 次调用全部返回 `InternalError`。这个报错没有写上限是多少，所以 50 只是这次测试里成功过的最大值，不是服务声明的上限。

### 结果 3：fetch_blob 返回整个文件，上限 4 MB

<img src="images/ui_blob_over_limit.png" width="900" alt="Interactive Demo 页面，Live 模式，工具 fetch_blob。工具说明写着：Download a binary file (document, PDF, image, photo) from a WorkIQ content path, up to 4 MB。请求：path 为 /me/drive/items/、一段已遮盖的文件 ID、/content。响应：error 为 Payload too large; downloads are limited to 4 MB，另有一个 requestId，它的值已遮盖。">

读取一个 4,194,352 字节的文件时产品页面的截图：“Payload too large; downloads are limited to 4 MB.” 文件的 ID 和请求号已遮盖。

| 文件大小（字节） | 文件类型 | 结果 | 用时（秒） | 响应大小（字节） |
|---|---|---|---|---|
| 864 | .json | 与本机文件完全一致 | 2.0 | 1,909 |
| 3,692,641 | .png | 与本机文件完全一致 | 5.4 | 5,313,565 |
| 3,815,774 | .html | 与本机文件完全一致 | 4.1 | 5,094,699 |
| 4,116,808 | .png | 与本机文件完全一致 | 4.2 | 5,926,201 |
| 4,117,319 | .png | 与本机文件完全一致 | 3.9 | 5,931,216 |
| 4,194,352 | .mp4 | 拒绝：“Payload too large; downloads are limited to 4 MB.” | 2.6 | 275 |
| 4,405,081 | .json | 拒绝，报错相同 | 2.2 | 275 |
| 20,050,987 | .pptx | 拒绝，报错相同 | 2.9 | 275 |

要点：

- **上限以内的文件逐字节返回。** “完全一致”指：把响应里的 `base64Content` 解码后算 SHA-256，与本机同一个文件的 SHA-256 相同。
- **上限落在 4,117,319 和 4,194,352 字节之间。** 这与按 1,024 进位的 4 MB，即 `4 × 1,024 × 1,024 = 4,194,304` 字节吻合，排除了 4,000,000。紧挨着 4,194,304 的两个大小没有测，所以上限具体是哪一个字节并不知道。
- **响应比文件大。** 文件是以 Base64 放在 JSON 里传的：4,117,319 字节的文件，响应是 5,931,216 字节。
- **超过上限，什么都不返回。** 这个工具的参数只有 `path`、`format`、`agentId`，没有一个能指定只取文件的一部分。这次测试里，超过上限的文件只能拿到 `retrieve` 返回的那段摘录。`format` 参数按工具说明是下载时转换格式用的，没有测。

### 结果 4：文档写的限制有三条与实测不同

<img src="images/ui_chats_top_101.png" width="900" alt="Interactive Demo 页面，Live 模式，工具 fetch。请求：entityUrls 里只有一个路径 /me/chats?$select=id&amp;$top=101。响应：statusCode 400，报错信息为 The query specified in the URI is not valid. The limit of 50 for Top query has been exceeded. The value from the incoming request is 100。响应里的三个请求号已遮盖。">

调用 `/me/chats?$select=id&$top=101` 时产品页面的截图。发出去的是 101；报错说这个集合的上限是 50，而收到的值是 100。`fetch` 的路径就是 Microsoft Graph 的路径：工具自己的说明写着 “Use well-known Microsoft Graph paths directly”（见 [`results/tools_list.json`](results/tools_list.json)），Microsoft Graph 的 [List chats](https://learn.microsoft.com/en-us/graph/api/chat-list?view=graph-rest-1.0#optional-query-parameters) 文档写着 “Maximum allowed `$top` value is 50”。响应里的请求号已遮盖。

| 限制 | [Microsoft Learn《Work IQ MCP tool reference》](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/tool-reference)（2026 年 11 月 20 日更新） | 2026 年 11 月 27 日实测 | 是否一致 |
|---|---|---|---|
| `fetch`，读集合时不带 `$top` | “the system injects a default $top of 25” | 邮件、日程、联系人 10 条；聊天列表 19 条；聊天消息 20 条；OneDrive 一个文件夹 163 项 | 不一致 |
| `fetch`，`$top` 的最大值 | “a maximum cap of 100” | 100：`$top=101` 和 `$top=1000` 都返回 100 条 | 一致 |
| `fetch`，聊天消息 | “Chat messages are capped at 10 per request.” | 20：`$top=11` 返回 11 条，`$top=21` 和 `$top=50` 返回 20 条 | 不一致 |
| `fetch`，`$skip` 和 `$skiptoken` | “The system blocks the $skip and $skiptoken query parameters.” | `$skip=5` 返回第 6 到第 10 条；带 `$skip` 或 `$skiptoken` 的下一页链接能取到下一页 | 不一致 |
| `fetch_blob`，文件大小 | “The default raw-file limit is 4 MB and can be configured per path.” | 4,117,319 字节返回，4,194,352 字节被拒绝 | 一致 |
| `fetch_blob`，超过上限 | “returns an MCP tool error containing the configured limit; it doesn't return blob content” | 报错 “Payload too large; downloads are limited to 4 MB.” | 一致 |
| `fetch`，一次调用的路径数 | 没有写 | 50 个有响应；51 到 100 个返回 `InternalError` | 文档未写 |
| `retrieve`，每次调用的结果条数和每条结果的文字量 | 没有写 | 0 到 13 条；`snippet` 最长 9,441 个字符 | 文档未写 |

要点：

- **三处不一致里，两处是调用方实际拿到的比文档写的多，另一处是默认值不同。** 聊天消息每次返回 20 条，文档写的是 10 条；`$skip` 能用，文档写的是被屏蔽。默认条数并没有更多：不带 `$top` 时，邮件、日程、联系人返回 10 条，文档写的是 25 条；OneDrive 的一个文件夹则一次返回全部 163 项。同一页文档说这些是按租户配置的策略限制，所以换一个租户，或者同一个租户换一天，表现可能与文档一致。这页文档自己的示例响应里，下一页链接带的就是 `$top=10&$skip=10`，与实测吻合。
- **`$top` 在到达 Microsoft Graph 之前被改成了 100，Graph 自己的限制照样生效。** 上面那次调用发的是 101，报错说收到的值是 100，而 50 是 Microsoft Graph 文档写明的这个集合的最大值。“把值改小的是 Work IQ”是推断，依据是这段报错原文，以及邮件响应里那句 “Results limited to 100 items per collection”；服务的代码没有看到。
- **编造的 `$skiptoken` 返回的是第一页。** 是 Work IQ 去掉了它，还是 Graph 忽略了它，从响应里分辨不出来。

| 想了解 | 看这里 |
|---|---|
| 测试环境、方法、每一次调用、没有测的范围 | [`docs/RESULTS_CN.md`](docs/RESULTS_CN.md) |
| [`scripts/`](scripts/) 下每个脚本做什么、[`tests/`](tests/) 下的离线测试测了什么、证明不了什么 | [`docs/TESTING_CN.md`](docs/TESTING_CN.md) |
| 本页每个数字对应的数据 | [`results/limits.json`](results/limits.json)，每次调用一行的明细在 [`results/summary/`](results/summary/) |
| 测试当天服务返回的工具列表和参数定义 | [`results/tools_list.json`](results/tools_list.json) |
| 五次调用的参数，可以用 `scripts/call_once.py` 原样再发 | [`cases/`](cases/) |
| 图和截图的来源 | [`images/SOURCES.json`](images/SOURCES.json)、[`NOTICE.md`](NOTICE.md) |

## 操作步骤

按下面的步骤，在你自己的租户里、以你自己的身份、对你自己的邮件、聊天和文件，测同样的限制。

| 顺序 | 在哪里 | 做什么 | 命令 | 大约用时 |
|---|---|---|---|---|
| 1 | 你的电脑 | 取代码，装一个包，跑离线测试 | `git clone`、`pip install websocket-client` | 2 分钟 |
| 2 | 你的电脑 | 用独立的 Edge 用户配置打开 Interactive Demo 并登录 | `python scripts/edge_cdp.py start --url <页面地址>` | 1 分钟 |
| 3 | 你的电脑 | 用工具列表确认页面可用 | `python scripts/call_once.py --list-tools --case 00_tools_list --out "$out\raw"` | 几秒 |
| 4 | 你的电脑 | 跑八个阶段：78 次调用，另加你指定的每个文件一次 | `python scripts/run_limits.py <阶段> --out $out --reuse` | 10 分钟 |
| 5 | 你的电脑 | 把记录算成数字 | `python scripts/build_results.py $out --results "$out\public"` | 几秒 |
| 6 | 你的电脑 | 关闭浏览器 | `python scripts/edge_cdp.py close` | 几秒 |

表里的用时是第一次做时的估计。其中有一项是实测的：本仓库公布的这次运行里，第 4 步的 86 次调用等响应合计用了 5.1 分钟；这一步其余的时间是页面发出每次调用所需的操作时间。

前提条件：

- **租户。** 已启用 Work IQ，并且你被分配到一个包含 Work IQ API 的 Copilot Credits 支出策略；这两项是 [Microsoft Learn 列出的前提](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/retrieve#before-you-begin)。发调用的客户端就是 Interactive Demo 页面，所以不需要自己注册应用。租户屏蔽了 Interactive Demo、或登录时要求管理员同意的情况，没有测过。
- **费用。** 八个阶段发出 56 次 `fetch` 和 22 次 `retrieve`，文件测试里你指定几个文件就再加几次 `fetch_blob`；本仓库公布的这次运行指定了 8 个文件，共 86 次调用。微软的 [Work IQ 许可公告](https://www.microsoft.com/en-us/licensing/news/work-iq-general-availability)（2026 年 11 月 28 日读取）把费用分成两部分：查询类用量（grounding、retrieval、reasoning）按量变动计费，Work IQ Tool API 每次调用 0.1 Copilot Credits。三个工具各算哪一部分、这次测试实际扣了多少，没有核实。
- **数据。** 脚本会读：你最新的邮件、日程、联系人、聊天和 OneDrive 根目录各项的 ID；最新 100 封邮件的正文，以及 `retrieve` 返回的那些邮件的正文；3 个聊天里的消息；文件测试里你指定的文件；以及 `retrieve` 针对 `scripts/run_limits.py` 里那些问题搜到的内容。只调用 `retrieve`、`fetch`、`fetch_blob` 三个工具，不会通过 Work IQ 往 Microsoft 365 里写任何东西。
- **工具。** Windows、Microsoft Edge、Python 和 `websocket-client` 包。测试环境是 Windows 11、Microsoft Edge 158、Python 3.13.15、websocket-client 1.9.2。macOS 和 Linux 没有测：`scripts/edge_cdp.py` 是按 Windows 的安装路径找 Edge 的。

### 1. 取代码，跑离线测试

```powershell
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Agents/Work-IQ-MCP-Raw-Data-Limits
cd Agents/Work-IQ-MCP-Raw-Data-Limits

python -m pip install websocket-client
python -m unittest discover -s tests
```

最后一条命令不需要浏览器，也不需要登录。结尾是：

```text
Ran 28 tests in <n>s

OK
```

### 2. 打开 Interactive Demo 并登录

```powershell
python scripts/edge_cdp.py start --url "https://interactivedemo.microsoft.com/work-iq/mcp?server=workiq-remote"
```

```text
EDGE Edg/<version> port 9351 profile C:\Users\<you>\AppData\Local\EdgeAutomation\workiq-demo
```

会打开一个 Edge 窗口，用的是独立的用户配置，你平时用的 Edge 窗口不受影响。在这个窗口里点 **Sign in to go live**，自己完成登录。脚本不输入密码，也不读取令牌：令牌由页面获取，每次调用都由页面发出。

脚本通过这个窗口的 DevTools 端口 9351 来操作它，这个端口只监听 `127.0.0.1`。窗口开着的时候，本机上任何连得上这个端口的程序都能操作这个已登录的页面，所以用完就关掉（见[第 6 步](#6-关闭浏览器)）。

然后确认页面状态：

```powershell
python scripts/edge_cdp.py wake --match interactivedemo
```

```text
sent: ['Page.setWebLifecycleState', 'Emulation.setFocusEmulationEnabled']
{"visibilityState": "visible", "hasFocus": true, "firstTimerMs": 319, "secondTimerMs": 311, "logEntries": 0, "account": "<your name>"}
```

页面处于 Live 模式时，`account` 是你的名字；Demo 模式下它是空的。页面正常时，两个定时器的数值在 `300` 上下。测试期间你可以在别的窗口里工作：每次调用前，脚本都会告诉页面它是活动窗口，否则 Edge 会停掉被遮住的窗口里的定时器。

### 3. 用工具列表确认页面可用

```powershell
$out = "$HOME\workiq-limits\run1"
python scripts/call_once.py --list-tools --case 00_tools_list --out "$out\raw"
```

`$out` 是私有文件夹：完整响应连同你的邮件内容都存在 `$out\raw` 下。不要放进共享文件夹，也不要放进 Git。这条命令会刷新页面，并记录页面请求到的工具列表：

```text
account shown by the page: <your name>
HTTP 200  headers after <n> ms, last byte after <n> ms  <n> bytes  request-id <id>  sent as typed: None
13 tools: retrieve, fetch_blob, ask, list_agents, delete_entity, do_action, discover, create_entity, get_schema, search_paths, call_function, fetch, update_entity
saved <out>\raw\00_tools_list.json
```

你的租户列出的工具可能不同。实测需要的是 `retrieve`、`fetch`、`fetch_blob`。

### 4. 跑实测

```powershell
foreach ($stage in 'mail', 'collections', 'chat', 'multi', 'body', 'retrieve', 'fulltext') {
    python scripts/run_limits.py $stage --out $out --reuse
}
python scripts/run_limits.py blob --out $out --reuse --blob-files "<file 1>" "<file 2>" "<file 3>"
```

每次调用输出一行：参数、HTTP 状态码、用时、响应大小和各种计数；任何一行都不显示邮件或文件的内容。带 `--reuse` 时，`$out\raw` 里已有记录的调用不会再发，所以中断的阶段可以直接重跑，已完成的调用不会发第二次。

`blob` 阶段要指定已经在你 OneDrive 里的文件，从本机的 OneDrive 同步文件夹里选，大小要分布在 4 MB 两侧：比如一个小于 4,000,000 字节，一个在 4,000,000 和 4,194,304 之间，一个更大。这个阶段会在 OneDrive 里找到每个文件，用 `fetch_blob` 读回来，再与本机文件比 SHA-256。不带 `--blob-files` 时，它会往 `$out\blob_test` 里写 7 个固定大小的文本文件，然后等 OneDrive 把它们传上去，这要求 `$out` 在 OneDrive 文件夹里。测试当天 OneDrive 没有把它们传上去，所以公布的这次运行用的是云端已有的文件。

然后把每次调用列成一张表：

```powershell
python scripts/summary_table.py $out mail collections chat multi body blob retrieve fulltext
```

公布的这次运行，开头几行是：

```text
== mail: 14 calls
mail_01_no_top                     HTTP 200 3628 ms 3162 B err=False typed=True :: status 200, 10 items, nextLink($skip=10,$top=10)
mail_02_top_25                     HTTP 200 1047 ms 6946 B err=False typed=True :: status 200, 25 items, nextLink($skip=25,$top=25)
```

你的租户里条数不同，那是结果，不是错误。某一行出现 `UI_ERROR`，说明页面没有把这次调用发出去，见[某一步停住时](#某一步停住时)。

### 5. 把记录算成数字

```powershell
python scripts/run_stats.py $out --json "$out\summary\run_stats.json"
python scripts/retrieve_fields.py $out --json "$out\summary\retrieve_fields.json"
python scripts/build_results.py $out --results "$out\public"
```

`$out\public\limits.json` 里就是你的租户的数值，字段名与本仓库的 [`results/limits.json`](results/limits.json) 相同，可以逐行对比。里面只有条数、大小、字段名和报错原文。旁边 `$out\public\summary` 里的汇总文件还带着你发给 `retrieve` 的查询文字，分享前先自己看一遍。服务的请求号不进这份公开副本，仍留在 `$out\summary` 里，需要提支持工单时到那里找。`$out\raw` 里仍然是你的内容，要保持私有。

### 6. 关闭浏览器

```powershell
python scripts/edge_cdp.py close
```

```text
EDGE_CLOSED
```

登录状态留在那个独立的用户配置文件夹里。要清除，删掉 `%LOCALAPPDATA%\EdgeAutomation\workiq-demo`。

### 某一步停住时

| 你看到 | 怎么办 |
|---|---|
| `EDGE_NOT_RUNNING on port 9351` 或 `NO_DEMO_PAGE` | 重做第 2 步 |
| `account shown by the page: (none` | 页面还在 Demo 模式：在自动化用的 Edge 窗口里点 **Sign in to go live** |
| `the page did not react within 60 s` | Edge 停了页面的定时器；先运行 `python scripts/edge_cdp.py wake --match interactivedemo`，再带 `--reuse` 重跑这个阶段 |
| `wake` 命令输出 `TIMERS_FROZEN` | 把自动化用的 Edge 窗口点到前台一次，再运行 `wake` |
| `no tool named ... in the page` | 你的租户没有列出这个工具；回到第 3 步看工具列表 |
| 某一行 `fetch` 是 `status 403`，或工具报错里提到策略 | 你的租户的 Work IQ MCP 策略屏蔽了这个路径；这一行就是这个路径在你租户里的结果 |
| `is not inside a OneDrive folder of this PC` | 用 `--blob-files` 指定 OneDrive 同步文件夹里的文件 |
| `file of <n> bytes skipped: OneDrive reports size <m>` | OneDrive 存的这个文件大小与本机不同，Office 文件常见；换一个文件 |
