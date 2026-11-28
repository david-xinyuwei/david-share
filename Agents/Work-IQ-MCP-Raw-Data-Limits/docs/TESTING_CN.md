# 测试说明

[English](TESTING.md) · 返回 [README](../README_CN.md)

本页说明每个脚本做什么、一次运行里哪些东西会离开私有文件夹、离线测试检查什么、截图是怎么做出来的，以及这些都证明不了什么。实测结果见 [RESULTS_CN.md](RESULTS_CN.md)。

## 脚本一览

| 脚本 | 做什么 | 是否调用 Work IQ |
|---|---|---|
| `scripts/edge_cdp.py` | 通过 DevTools 协议启动并控制那个独立的 Edge 用户配置：`start`、`targets`、`wake`、`eval`、`shot`、`open`、`close` | 否 |
| `scripts/demo_signin.py` | 可选：点 **Sign in to go live** 和 Windows 给出的账号磁贴。不输入密码；遇到密码、MFA 或授权同意页面，就输出 `NEEDS_USER` 并停下 | 否 |
| `scripts/demo_runner.py` | 库：把工具参数填进页面的 JSON 编辑框，按 **Call tool**，取回这次调用的记录 | 被脚本用到时调用 |
| `scripts/js/fetch_recorder.js` | 在页面内运行：把发往 MCP 端点的每个请求的请求体、状态码、响应头、耗时和响应复制一份。从不读取 `Authorization` 请求头 | 否 |
| `scripts/call_once.py` | 按一个 JSON 参数文件发一次调用，或取工具列表 | 一次调用 |
| `scripts/run_limits.py` | 实测的八个阶段 | 78 次调用，另加指定的每个文件一次 |
| `scripts/summary_table.py` | 从一次运行的汇总里，每次调用输出一行 | 否 |
| `scripts/run_stats.py` | 从一次运行的记录里统计调用次数、耗时、状态码和限流 | 否 |
| `scripts/retrieve_fields.py` | 按结果类型列出 `results[].markdown` 里的字段 | 否 |
| `scripts/build_results.py` | 写出一次运行的公开副本：去掉文件哈希和请求号的汇总，以及用这些汇总算出的 `limits.json` | 否 |
| `scripts/results_tables.py` | 从汇总生成 `docs/RESULTS` 里的明细表，可以打印，也可以直接写进页面 | 否 |
| `scripts/shot_call.py`、`scripts/redact_shot.py`、`scripts/js/redact_rects.js` | 在一次调用进行时给页面截图，并生成遮盖了 ID 的公开副本 | 每张截图一次调用 |
| `scripts/show_tools.py`、`scripts/show_shape.py`、`scripts/show_markdown_layout.py`、`scripts/shape.py` | 查看一条已存的记录而不显示内容：工具列表、结构、打码后的排版 | 否 |

## 哪些东西会离开私有文件夹

| 位置 | 里面有什么 | 能不能给别人 |
|---|---|---|
| `<out>/raw/` | 每次调用的请求、状态码、响应头、耗时和完整响应。`fetch_blob` 的 Base64 内容被换成它的大小和 SHA-256 | 不能：里面有你的邮件、聊天和文件名 |
| `<out>/summary/` 和 `<out>/console_<stage>.txt` | 每次调用的参数、用时、条数、大小、字段名、报错原文和服务返回的请求号。带 ID 或本机路径的参数被换成占位文字 | 先自己看一遍：里面有你发给 `retrieve` 的查询文字 |
| `<out>/public/`，由 `build_results.py --results` 写出 | 去掉了文件 SHA-256 和服务请求号的汇总，以及 `limits.json` | 可以，同样先看一遍 |
| 本仓库的 `results/` | 同上，是本仓库公布的这次运行 | 已公开 |

离线测试 `test_public_files_hold_no_ids_addresses_or_paths` 会在 `results/` 和 `cases/` 里查找邮件 ID、聊天 ID、网盘 ID、GUID（请求号、对象 ID、租户 ID 都是这种形式）、邮箱地址、SharePoint 主机名和本机路径。它只能拦住已知的模式，证明不了文件里没有任何私有内容。

## 离线测试

```powershell
python -m unittest discover -s tests -v
```

这 28 项测试不调用任何服务，也不打开浏览器。它们按测试当天服务返回的结构造出响应喂给脚本，并把公开的文件互相比对。

| 测试类 | 测试数 | 断言什么 |
|---|---|---|
| `Replies` | 4 | 纯 JSON 和事件流两种响应都能读出来，事件流取最后一条完整消息；不完整的响应不取；工具响应被拆成错误标志、文字部分和结构化内容 |
| `Shapes` | 1 | 结构视图保留键名、条数、长度和报错原文，其余文字一律去掉 |
| `FetchAnswers` | 3 | 下一页链接只描述 `$top` 和 `$skip`，不带游标的值；链接发回去之前去掉 Graph 的主机名；一次响应的汇总会数条数、保留失败路径的报错，且不含任何条目内容 |
| `Blobs` | 3 | 合成的测试文件大小与要求的分毫不差，每次生成的字节都相同；Base64 内容不管在响应的哪一层都能找到；记录存盘之前它被换成大小和 SHA-256 |
| `RetrieveAnswers` | 6 | 能读出一条结果的 Markdown 里各字段的长度和 `truncationInfo` 的原文；一次响应的汇总只有条数、月份和字段名，没有结果的文字；`searchMetadata` 的两种形式都能读；长查询的长度与要求的完全一致；比对两段文字时忽略空白和 Markdown 标记；21 个采样的比对能分清全文和半篇 |
| `Throttling` | 1 | 是否限流只看报错原文和状态码 `429`，绝不看成功响应的内容 |
| `PublishedDataset` | 5 | `results/limits.json` 等于 `build_results.py` 从 `results/summary/` 算出来的结果；公开文件里没有上述模式的 ID、地址或路径；一行记录的公开副本去掉了文件哈希、这一行的请求号和报错文本里的请求号；每个阶段的汇总都已公开，调用次数的合计对得上；用例文件就是截图里的那几次调用 |
| `Pages` | 4 | 中英文 README 都引用了数据集里的 17 个数字和 `fetch_blob` 的拒绝原文；七个页面里的本地链接、锚点和图片都存在；中英文页面的图片相同、表格相同、标题数相同；`docs/RESULTS` 里的表格就是 `results_tables.py` 的输出 |
| `Images` | 1 | `images/` 下的每个 PNG 都列在 `images/SOURCES.json` 里，并带它的 SHA-256 |

自己跑完一次之后，`python scripts/results_tables.py <out> --lang zh` 可以打印出你的租户的同样几张表。

## 截图是怎么做的

```powershell
python scripts/shot_call.py --tool fetch --args-file cases/fetch_skip.json --png "$out\shots\skip.png" --case shot_skip --out "$out\raw"
python -m pip install pillow
python scripts/redact_shot.py "$out\shots\skip.png" images/ui_skip.png
```

1. `shot_call.py` 经页面把调用发出去，这是多发的一次调用。然后把页面设成 1,500 × 1,900 CSS 像素、缩放 1.25，让请求和响应同时可见，存下 PNG。它还在旁边存下页面上每一处匹配 ID 模式的文字的位置：邮件 ID、网盘文件 ID、聊天 ID、ETag，以及所有 GUID，用户的对象 ID 和服务的请求号都在其中。
2. `redact_shot.py` 在每个位置上画一个灰块，再把图裁到最后一行有深色像素的地方。图里的其他内容不做任何改动。
3. 原图留在私有文件夹里。[`images/SOURCES.json`](../images/SOURCES.json) 列出每张公开副本、它的原图的 SHA-256 和灰块的个数。

公开之前先看一眼副本。这些模式覆盖的是本仓库四张截图的响应里出现过的 ID，不是所有种类的私有文字；页面右上角登录用户的名字仍然可见。

本仓库有两张截图是在 GUID 模式进入默认值之前拍的：`ui_blob_over_limit.png` 和 `ui_chats_top_101.png`。它们的请求号上的灰块，是 2026 年 11 月 28 日按这些值在原图里的位置补上的，画灰块用的还是同一个 `redact_shot.py`。[`images/SOURCES.json`](../images/SOURCES.json) 里这两张图的条目写明了这一点。

## 这些证明不了什么

- **离线测试不说明服务的任何行为。** 它只说明脚本在已知结构的响应上数得对。
- **一次运行只是一次观测。** 同一个 `retrieve` 调用发两次，结果不同；`fetch` 的限制按租户配置。
- **驱动脚本依赖页面本身。** 它靠页面自己的标记找到工具列表、JSON 编辑框和 **Call tool** 按钮。微软改了页面，调用就会以 `UI_ERROR` 结束，什么也测不到。脚本是对着 2026 年 11 月 27 日的页面跑通的。
- **用时包含页面的开销。** 自己写的客户端测到的时间会不同。
- **`demo_signin.py` 只在一个租户里用过**，那里 Windows 直接给出了账号，没有要求输入密码。
