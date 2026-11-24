# 测试说明

[English](TESTING.md) · 返回 [README](../README_CN.md)

本页说明仓库里每项检查证明了什么、回答怎么判分、README 里的数字是怎么测的，以及哪些没有测。

## 四种检查

| 检查 | 命令 | 需要什么 | 证明了什么 | 证明不了什么 |
|---|---|---|---|---|
| 离线测试 | `python -m unittest discover -s tests -v` | 只要 Python | 脚本自己的判断：哪些训练任务有可部署的适配器、用 `--adapter-model` 指定的模型哪些会被部署、适配器部署怎么命名、会话保存的检查点和训练日志怎么读、回答怎么判分、回执什么时候算 PASS | Azure 是否接受这些请求 |
| Programmed Training 的本地准备 | `<cookbook python> training/programmed_training_sft.py --resource-group <name> --prepare` | cookbook 的 Python 环境；不登录 Azure，约 3 分钟 | 两个示例文件的 SHA-256 与固定值一致；每一行渲染后不超过 2,048 个 token，并且有可训练的回答 token；会话的训练计划：每个 epoch 28 批、每批 16 行，共 56 个优化步；目录价 | 你的订阅能不能开会话；训练出的适配器怎么样 |
| 部署检查 | `python infra/verify.py --resource-group <name>` | 一个已部署的环境（存在期间 GPU 一直计费） | 从公网端点看：目标部署和适配器部署都是 `Succeeded`，基础模型能回答，每个适配器能回答、且提供服务的模型与基础模型不同，不存在的名称会被拒绝 | 适配器是否带来改进 |
| 完整对比 | `python infra/verify.py --resource-group <name> --full` | 同一个部署；在部署检查之外再发 100 次对比调用和 6 次流式调用，约 5 分钟 | 在 50 行验证数据上，适配器给出的回答与基础模型不同；回答长度；流式速度 | 准确率，见[回答怎么判分](#回答怎么判分) |

## 离线测试

```powershell
python -m unittest discover -s tests -v
```

30 个测试不调用任何服务。它们把真实服务响应的结构（任务对象、项目里的模型）喂给脚本，检查脚本做出的判断。

| 测试类 | 数量 | 断言的内容 |
|---|---|---|
| `DeployableAdapters` | 7 | 任务成功但没有登记适配器时，不算可部署；通过任务能找到适配器；任务指向项目里不存在的模型时跳过；运行中和失败的任务跳过；同名时取最新的任务；别的基础模型的适配器被排除；一个目标最多 8 个适配器 |
| `AdapterNames` | 3 | 门户里的显示名优先于任务后缀；字母、数字、`.`、`_`、`-` 之外的字符被替换；没有名称时退回到任务 ID，且不超过 64 个字符 |
| `NamedAdapters` | 7 | 用 `--adapter-model` 指定的项目模型按标签部署，不需要训练任务；不给标签时用模型名称；名称不存在、或者不是 LoRA 模型时脚本停下；基础模型不同的模型也会让脚本停下；指定的适配器排在任务的适配器前面；被指定的模型只列一次；两个适配器得到同一个部署名称时脚本停下 |
| `Sessions` | 2 | 会话最后一个检查点是按项目模型上的会话标签找到的，没有这个标签的模型不会被取；训练日志的汇总数出优化步、训练 token 和验证次数 |
| `Scoring` | 5 | 能读出示例数据的参考答案格式；有 `####` 标记时以标记后的数字为准；没有标记时取最后一个数字；回答里没有数字不算对；正确答案后面还有别的数字时会被判错（下面说的已知缺陷） |
| `Receipts` | 2 | 每一步都通过，回执才是 PASS；空回执不算 PASS |
| `Endpoints` | 4 | chat 路由在账户端点上；Azure Resource Manager 的 URL 带着测试过的 API 版本；适配器 ID 取自任务的 Managed compute 选项；列表第一页为空时，会顺着 `nextLink` 读到它指向的那一页 |

## Programmed Training 脚本

`training/programmed_training_sft.py` 在 Programmed Training cookbook 的 Python 环境里运行。加 `--prepare` 时，它在 2/5 之后停下：不登录任何服务，也不开会话。

| 步骤 | 做什么 | 通过条件 |
|---|---|---|
| 1/5 Sample data | 下载两个固定版本的 GSM8K 文件；`up.py` 已经下载过的，直接用 | 每个文件的 SHA-256 与固定值一致 |
| 2/5 Local preparation | 用 cookbook 为这个模型提供的渲染器渲染每一行，分好批，读取目录价 | 每一行训练数据和验证数据渲染后都不超过 2,048 个 token、都有可训练的回答 token，批数与计划一致 |
| 3/5 Project | 找到 `up.py` 在这个资源组里创建的账户和项目 | 两者都存在 |
| 4/5 Training session | 开一个会话，运行循环，保存最后一个检查点，关闭会话 | 循环记录了计划中的每一个优化步，并且至少算了 2 次验证损失 |
| 5/5 Saved adapter | 列出项目里的模型，最多 12 次，每次间隔 10 秒 | 列表里有一个 LoRA 模型，标签里记着这个会话，名称以 `-final` 结尾 |

没有哪一步会因为损失的数值而失败。损失会打印出来，方便和 README 里的数字对照。

这个脚本和 README 里报告的那次会话是什么关系：

- **训练代码相同。** 渲染数据和运行会话的函数（`prepare_custom_sft`、`run_custom_sft`，以及它们用到的 5 个定义），就是第二次测试里跑的那个驱动脚本。两个文件按语法树做过比较：7 个定义全部相同，模型、渲染器和各项设置也相同。
- **训练计划相同。** `--prepare` 已经在测试客户端的 cookbook 环境里、从本仓库运行过。它给出的计划，与第二次测试保存的计划在所有不含目录名的字段上都一致：两个文件的 SHA-256、449 行和 50 行、每个 epoch 28 批、计划 56 步、计划 219,768 个训练 token。会话实际数到的是 219,652 个：449 行一共 110,106 个 token，每个 epoch 训练其中 448 行，而且每个 epoch 都重新打乱，漏掉的那一行不一样。
- **读取服务返回的结果。** `infra/foundry.py` 里的 `session_adapter`、`named_adapters` 和 `session_summary`，已经用第二次测试保存的模型记录和训练日志跑过。它们给出了最后一个检查点对应的模型、那次测试的适配器部署所用的模型 ID，以及 README 里报告的 56 步、219,652 个训练 token 和各个损失值。
- **完整运行过。** 2026 年 11 月 24 日，这个脚本在一个新资源组里跑完了全部五步：一个会话，全部 56 个优化步，219,652 个训练 token，验证损失从 0.91 降到 0.41，5/5 这一步在项目里找到了最后一个检查点；随后 `up.py --deploy --adapter-model` 部署了它。见[按操作步骤完整运行一遍](RESULTS_CN.md#按操作步骤完整运行一遍)。

## 部署检查

`infra/verify.py` 先从 Azure Resource Manager 读回部署状态，再像应用那样调用账户端点：使用面向 `https://ai.azure.com` 的 Microsoft Entra 令牌，`model` 填部署名。

| 检查 | 发送的内容 | 通过条件 |
|---|---|---|
| Target deployment is Succeeded | 读取目标部署 | 预配状态是 `Succeeded` |
| Adapter deployments are Succeeded | 列出适配器部署 | 目标部署上至少挂着一个，且全部是 `Succeeded` |
| The base model answers under the target's name | “Tom has 3 apples and buys 5 more. How many apples does he have? Answer with a number.” | HTTP 200，回答里有 8 |
| Adapter `<name>` answers under its own name | 同一个问题，`model` 填适配器部署的名称 | HTTP 200，回答里有 8，且响应的 `model` 与基础模型的不同 |
| An unknown deployment name is rejected | 同一个问题，`model` 填一个编造的名称 | HTTP 404 |

`--full` 增加：

| 检查 | 发送的内容 | 通过条件 |
|---|---|---|
| Held-out rows through `<deployment>`，基础模型和适配器各一次 | 50 行验证数据，同时发 4 个，`temperature` 为 0，`reasoning_effort` 为 `"none"`，`max_tokens` 为 800，每行最多尝试 3 次 | 50 行全部得到回答 |
| The adapter changes the answers | 不发请求，比较两组回答 | 完全相同的回答少于 50 个 |
| Streaming speed of `<deployment>`，每边一次 | 3 个流式请求，一次发 1 个，最多 600 个 token，思考保持默认 | 每个请求都算出了速度 |

没有任何检查会因为答对的数量而失败。自动判分的结果会打印并保存，每个回答都写入状态目录下的 `verify-rows-<time>.jsonl`，可以逐行读。

## 回答怎么判分

示例数据的每个参考答案都以 `#### <数字>!!!` 结尾。自动判分的做法是：回答里有 `####` 标记时取标记后面的数字，否则取回答里的最后一个数字，再和参考答案的数字比较。

正确答案后面如果还有别的数字，这种判分就会出错。验证文件第 5 行问的是一只变形虫分裂成 16 只需要几天，参考答案是 8。基础模型的回答以 `It will take **8** days for one amoeba to divide into 16 amoebae.` 结尾。这个回答是对的，但最后一个数字是 16。基础模型常用这样的句子收尾；适配器的回答大多以答案数字结尾。

因此，README 里的对比把自动检查对任意一边判错的行都读了一遍，共 12 行（总共 50 行）。

| | 基础模型 | 基础模型 + GSM8K 适配器 |
|---|---|---|
| 自动判分答对 | 50 行中的 39 行 | 50 行中的 45 行 |
| 自动判分漏掉的正确回答 | 5 | 1 |
| 人工读过之后答对 | 50 行中的 44 行 | 50 行中的 46 行 |
| 仍然答错的行（行号从 0 开始） | 9、13、24、27、33、36；其中第 13、27 行在 800 token 上限处被截断 | 9、11、13、24 |

两边结论不同的有 4 行：只有适配器答对的是第 27、33、36 行，只有基础模型答对的是第 11 行。3 对 1 的双侧符号检验 p = 0.625，所以这 50 行看不出准确率有差别。另一种自动检查会去找“最终答案”（标记、boxed 数字、最后一个加粗数字、“the answer is”），它只用来挑选要人工读的行。

想给自己的对比判分，读 `verify-rows-<time>.jsonl`：每行有行号、部署名、回答、判分取到的数字和参考答案的数字。

## README 里的数字是怎么测的

两次测试的测试拓扑图都在 [RESULTS_CN.md](RESULTS_CN.md)：第一次测试见[适配器 A](RESULTS_CN.md#适配器-a用-managed-training-训练第一次测试)，第二次见[适配器 B](RESULTS_CN.md#适配器-b用-programmed-training-训练第二次测试)。计时都在测试客户端上。

| 数字 | 取法 |
|---|---|
| 训练设置 | 从任务对象读回：seed 42（在向导里填的），`n_epochs` 2、`batch_size` 128、学习率倍数 1（服务默认值；向导里的 **Number of epochs** 和 **Learning rate multiplier** 保持 Default） |
| 训练任务时长 | 任务对象的 `finished_at` 减 `created_at`；包含排队和预处理 |
| 训练步数和训练时长 | 任务的结果文件：共 6 行，取最后一行的 `train_runtime` |
| 计费的训练 token | 任务事件 “Training tokens billed”；任务对象的 `trained_tokens` 字段是另一个更小的数（163,164） |
| 目标部署和适配器部署的时长 | 从请求被接受到第一次读到 `Succeeded`，由轮询的客户端观察 |
| 两边的先后顺序 | 依次测量，先基础模型、后适配器，在同一个目标部署上一次做完；两边没有交替进行 |
| 回答长度 | 每个非流式回答的 `usage.completion_tokens`；取 50 行的平均值 |
| 首 token 时间 | 从发出请求到收到第一个流式 token（思考或正文）；包含网络传输和提示词处理 |
| 每秒 token 数 | （completion tokens − 1）÷（最后一个数据块的时间 − 首 token 的时间）；completion tokens 包含思考 token |
| 价格 | 公开的 Azure Retail Prices API，计量项 `Mngd H100_80GB Gl` 和 `Qwen38 27b SFT Gl 1M Tokens`，单位美元 |
| 第二次测试：Programmed Training 的设置 | 取自循环在第一步之前保存的配置：batch size 16，2 个 epoch，学习率 0.0001、线性变化，LoRA rank 32，种子 42，每行最多 2,048 个 token。449 行数据每个 epoch 分成 28 批，所以每个 epoch 训练 448 行，剩下 1 行不参与 |
| 第二次测试：两次训练的学习率 | 每个优化步记录的值：任务结果文件里的 6 个值和循环指标文件里的 56 个值，都落在一条直线上：第一步是 0.0001，最后一步的下一步降到零 |
| 第二次测试：验证损失 | 由循环计算：50 行验证数据（6,170 个回答 token）上每个回答 token 的平均负对数似然；只做前向计算，不更新适配器；在第一步之前、28 步之后和全部 56 步之后各算一次。Managed Training 的数值取自在门户提交的那个任务（训练出适配器 A）的结果文件的 `eval_loss` 列 |
| 第二次测试：token 数和费用 | 由循环按它发送的批次统计：56 步共 219,652 个训练 token，3 次验证共 36,042 个 token。费用是训练 token 乘以计量项 `Qwen38 27b Train Gl 1M Tokens` 的目录价。实际用的是不是这个计量项、验证怎么计费、账单本身，都没有核对 |
| 第二次测试：训练用时 | 循环自己记录的 56 步加 3 次验证的用时（363 秒），以及从启动脚本到退出的时间（532 秒），后者还包括准备数据、创建会话和关闭会话 |
| 第二次测试：`Succeeded` 之后的第一次调用 | 测试客户端上的一个进程大约每 30 秒发一次 chat 调用，第一次在首次读到 `Succeeded` 之后 6 秒。有 25 次调用返回 HTTP 404 `The specified endpoint does not exist`（17 次在 `/openai/v1/chat/completions` 上，8 次在顺带尝试的另外两条路由上）；第 553 秒的那次调用返回 HTTP 200 |
| 第二次测试：基础模型的判分 | 自动判分把 11 个回答判为错。其中 8 个的文本与第一次测试里读过的回答完全相同，沿用当时的结论；另外 3 个重新读过：2 个在 800 token 上限处被截断，1 个给出的数字与参考答案不同 |
| 端到端运行 | 脚本自己的输出，每一步单独保存：每条命令的开始和退出时间，`Succeeded (<n> min)`、`Succeeded (<n> s)` 和 `gone (<n> s)` 这几行，以及 `verify.py --full` 的输出行；回答的计数取自 `verify.py --full` 保存的逐行答案。门户任务的数字取自它的任务对象、事件和结果文件，会话的数字取自它的指标文件 |

README 里的测速用的是这条中文提示词：“请用中文写一段约 300 字的说明：企业在 Azure 上用 Managed Compute 部署开源模型时，怎样根据业务量选择 GPU 型号和实例数。” `verify.py --full` 发送的是同一条。

## 与文档不一致、或原因不明的现象

- **响应里的 `model` 字段。** [操作文档](https://learn.microsoft.com/en-us/azure/foundry/how-to/deploy-lora-managed-compute)说响应的 `model` 会返回适配器部署的名称。实际上适配器的响应里是形如 `rp-<hash>-1` 的内部 ID。所以 `verify.py` 只检查它与基础模型的值不同。
- **在新项目里通过 API 提交的任务。** 在两个区域里，项目从未有过门户提交的任务时，通过 API 提交的 3 个任务全部成功，却都没有在项目里登记适配器。在门户提交的任务都登记了（2 个中的 2 个），之后在同一项目里通过 API 提交的任务也都登记了（3 个中的 3 个）。原因不明。
- **`Succeeded` 之后返回 HTTP 404。** 有两个目标部署分别是在一次删除把账户清空之后 23 秒和 33 秒创建的，它们都到了 `Succeeded`，模型调用却返回 HTTP 404。直到删除它们之前的最后一次调用仍是如此，那时距 `Succeeded` 已经 18 分钟和 23 分钟。另一个在删除 8 小时之后创建的，8 秒后就能回答。第二次测试里，目标部署建在一个没有任何部署的账户里，测试本身也没有在这个账户里删除过东西。它在 `Succeeded` 之后同样返回 HTTP 404，持续 553 秒，之后每次调用都正常。可见 `Succeeded` 之后的 404 可能只是暂时的，也不一定要有紧挨着的删除。前面那两个目标部署如果多等一会儿能不能回答，不知道。这个故障没有特意去复现，两种间隔之间的情况也没有测；`up.py` 里的 60 分钟等待是预防措施。`up.py` 会把第一次调用重复 10 分钟才停下；第二次测试的 553 秒已经接近这个时限。端到端运行时，目标部署建在一个新账户里，`Succeeded` 之后 68 秒发出的第一次调用直接得到了回答。
- **第一页为空的列表。** 在端到端运行所用的订阅里，Azure Resource Manager 列出资源组里的账户时，第一页是空的，带一个 `nextLink`，账户在它指向的那一页上。当时 `infra/foundry.py` 只读第一页，所以 `training/programmed_training_sft.py` 在 3/5 停下，报 `No Foundry account created by this repository in resource group`。现在脚本会顺着 `nextLink` 读到最后一页，并有离线测试覆盖；这次运行的会话是在修复之后开始的。
- **训练任务列表里的 Programmed Training 会话。** 端到端运行时，这个会话以 `session_<id>` 出现在项目的训练任务列表里，状态 `succeeded`，它的 Managed compute 选项指向最后一个检查点。用保存下来的这份列表离线运行 `up.py` 的选取逻辑：不加 `--adapter-model` 时它也会选中这个检查点，部署名称是 `qwen38-lora-<会话 ID 的最后 8 个字符>`；加上这个选项时只按标签部署。
- **一次较慢的适配器部署。** 适配器部署变为 `Succeeded` 的用时：第一次测试 64 秒（2 个适配器），第二次测试 78 秒，端到端运行的第一个适配器 68 秒。端到端运行的第二个适配器用了 338 秒。原因不明。
- **目标部署的基础模型版本。** 一个在模型版本 3 上训练的适配器，它的适配器部署请求被一个运行版本 7 的目标部署接受了。那个目标部署从未成功回答过模型调用，所以这种搭配的实际效果未知。`up.py` 按适配器记录的版本创建目标部署，并设置 `NoAutoUpgrade`。

## 没有测试的内容

- 对着 Azure 运行 `infra/up.py --train-api`。操作步骤里的其他命令已于 2026 年 11 月 24 日从头到尾跑过一遍，见[按操作步骤完整运行一遍](RESULTS_CN.md#按操作步骤完整运行一遍)。
- Linux 和 macOS；3.13 以外的 Python 版本。
- East US 2 以外的区域的部署。
- 只在账户上拥有 Foundry User 的用户。测试时用的是订阅 Owner，Foundry User 也在订阅范围上。
- 一个目标部署上超过 2 个适配器、超过 1 个实例、并发用户。
- 人工阅读端到端运行的回答：那次运行的答对数只有自动判分。
- 在没有 Programmed Training 访问权限的订阅里运行 `training/programmed_training_sft.py`，以及由只有 Foundry User 角色的用户来运行。第二次测试用的是订阅 Owner，在账户上有 Foundry User 和 Azure AI Developer。
- README 第 3 步里照原样写的 cookbook 安装命令。这些命令取自 cookbook 的快速入门；测试客户端上的 cookbook 环境是之前就有的，没有按这些命令重建。
- cookbook 自带的 Programmed Training 检查点部署路线（`scripts/deploy_to_foundry.py`，部署目标 `Fireworks`）。
- Managed Training 默认值以外的设置，包括 batch size 16；Programmed Training 上表以外的设置；两套示例数据以外的数据。
