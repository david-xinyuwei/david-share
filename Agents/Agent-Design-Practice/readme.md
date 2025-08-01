# Agent Design Best Practice

想让Agent 既 **跑得快、花得少、还不翻车**，光有“大模型能力”远远不够，更关键的是：你如何给它喂上下文、喂工具、喂反馈。
 这就是所谓 **Context Engineering**。

7 条可立即落地的工程原则：

| #    | 技术关键词                                    | 一句话价值                                                   |
| ---- | --------------------------------------------- | ------------------------------------------------------------ |
| 1    | **KV-Cache 复用**                             | 锁死前缀、只追加，让“历史”一次缓存，处处复用，prefill 花费降低数倍 |
| 2    | **Logits 掩码**                               | 工具不删，只“遮”；缓存不碎，决策不乱                         |
| 3    | **文件系统即上下文**                          | 大文本写文件、上下文留索引，128 K 也装得下整座图书馆         |
| 4    | **Recitation 背诵锚定**                       | 不停把目标写到尾部，模型始终记得自己要干什么                 |
| 5    | **错误留痕**                                  | 把失败痕迹留在上下文，让模型“吃一堑长一智”                   |
| 6    | **反 Few-Shot 同质化**                        | 模板多样化，打破“复制粘贴”节奏锁定                           |
| 7    | **Predicted Outputs——Skip, Don’t Regenerate** | 大文件小改动时，已知文本直接跳过解码，回复快 3-5×            |



## 1. KV-Cache 缓存复用优化

### 🌟 介绍与目的

KV-Cache（Key-Value Cache，键值缓存）是大模型推理过程中的一种加速机制。它的本质是“记住已经算过的东西，不再白白重算一遍”。如果能充分利用KV-Cache，可以极大降低响应时间和服务器成本，直接让AI和用户体验“飞起来”。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/Agent-Design-Practice/images/1.png)

### 🎯 要解决的核心问题

- **上下文越来越长**：Agent带着越来越多“历史”往前推，每一步都要把所有历史喂进大模型。
- **推理单价上升**：每一步的输入token上万，输出却可能只有10个，传一堆历史只为模型“回忆”，成本惊人。
- **缓存失效风险**：只要上下文哪怕一丁点不同（哪怕是时间戳、空格、无关顺序），所有缓存都没了，真金白银的算力全作废。

### 🔎 常见误区与致命陷阱

**最大陷阱就是在系统提示、首条上下文里放“动态内容”**，比如：

- 精确到秒的时间戳
- 会话/用户唯一ID
- 随机种子、顺序号
- 工具描述顺序每次都不一样（JSON无序）

这些都会让“明明99%内容一样”的两个请求，缓存根本无法复用，每次都变成全新长文本推理。

**现实案例**

> 之前有团队为“让AI能说出当天日期”，在system prompt里塞`"当前时间:{datetime.now()}"`，结果缓存命中率从98%→<5%，每月云账多几万美元。

### 🛠️ 正确工程实现

1. **严格锁定提示前缀内容，一字不变**：

   ```
   SYSTEM_PROMPT = "你是专业AI助手。请严格遵循JSON格式回复。"
   # 千万别放时间、session-id等
   ```

   

2. **动态信息用“工具调用”获取**：

   - 用户要时间，像function-calling这样让模型自己发起 get_time 工具调用，再把`{"now": "2025-01-01T12:00:00"}`这样的结果，追加到最后一条上下文里。
   - 这不会影响前缀，不破坏缓存。

3. **所有长内容（如工具JSON、schema）序列化时必须保证顺序唯一**：

   ```
   import json
   tool_schema = json.dumps(tools, sort_keys=True)
   ```

   

4. **上下文只能“追加”，禁止插空、删除、回滚**

   - 永远只能一行一行往后接，不能回到前面“补一刀”。

5. **多并发或分布式时，用session-id让同一请求总是命中同一worker**（不然缓存跨worker无效）。

### ✅ 成功效果

- 有效缓存命中率能从10%提升到95%+
- 基本保证无论历史多长，推理毫秒响应，单步成本降一两个数量级
- 大量并发日常流量不再波动

------

## 2. Logits掩码 控制工具动态

### 🌟 介绍与目的

Logits掩码（Logits Masking）是一种“只让模型在解码时看到允许的选项，其它都相当于‘视而不见’”的技术。**不删除、不裁剪、不干扰物理内容，只在选择分数阶段就干掉不该出现的选项**。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/Agent-Design-Practice/images/2.png)

### 🎯 要解决的核心问题

- 随着Agent能力增强，工具数量爆炸，不同场景其实只应让模型见到一小部分工具。
- 传统“每次把无用工具描述直接在上下文删除/裁剪”，会导致“前文变动”→“缓存失效”。
- 某些历史动作用了“旧工具”，你现在删了描述，模型会懵逼。

### 🔎 常见误区或错误做法

- 每遇到不同场景就先删掉几十个工具的提示，然后拼一个新prompt。这会每次都让cache命中率降到0。
- 直接物理删除内容，忽视前后文实际引用关系。

### 🛠️ 正确工程实现

1. **全量保留所有工具描述于上下文**，无论何时何地，一字都不删。

2. **用模型API的 logit_bias 功能，对所有处于“禁用状态”的工具名首token，打上极低分数（如-100）**。这样模型即使“看见”它，也不会“选中”它。

3. **正确区分单token工具和多token工具**。一般对“首token”掩码即可，极端严谨可所有token都掩码。

   示例（OpenAI API）：

   ```
   def mask_tools(allowed_prefix="browser_"):
       return {token_id: -100 for tool,token_id in all_tool_token_ids.items()
               if not tool.startswith(allowed_prefix)}
   ```

   

4. 状态切换时，只变更掩码映射表，不更动上下文。

### ✅ 成功效果

- 动态管理工具变成毫秒级，不会破坏历史缓存。
- 系统性能受“工具数量”影响极小。
- 工具引用一致性始终保持。

------

## 3. 文件系统即上下文（外化记忆）

### 🌟 介绍与目的

大模型上下文再大，总有上线（如ChatGPT上下文128K token）。用户的输入和历史、抓取网页、读大PDF很容易突破限制。文件系统即上下文，就是**让模型通过工具主动将大文本存文件、只留下便于索引的路径在上下文里**。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/Agent-Design-Practice/images/3.png)

### 🎯 要解决的核心问题

- 遇到大文本，例如网页、PDF、代码，无法全都塞进prompt。
- 只靠摘要或切片，万一丢掉关键细节，后续任务就挂了。
- 千万不要让模型依赖“自己全记住”，让它也能“查字典”。

### 🔎 常见误区或错误做法

- 直接把长网页全文、十几页PDF塞prompt，导致超窗口或推理慢、压缩成本高。
- 压缩摘要不可逆（删了就找不回），模型忘掉重要信息。

### 🛠️ 正确工程实现

1. **定义 file_write / file_read 工具**，允许模型自己把大文本存盘，然后只生成简短的存储索引（如：“已保存至file-xxx”）。
2. **在上下文只留【路径+简要摘要】，正文本去文件“做记忆”**，几千字只消耗几十token。
3. **后续任何任务，都能通过file_read工具取回原文而不会丢失信息**。

### ✅ 成功效果

- 长链任务的上下文长度保持线性。
- 支持“任意多历史/大文件”零信息丢失。
- 推理代价恒定，体验流畅。

------

## 4. Recitation“背诵锚定”

### 🌟 介绍与目的

LLM做长任务时，注意力主要集中在输入的“尾部”；离输出越远，模型记忆力越差。“Recitation”就是让Agent**反复在上下文末尾“背诵”目标(todo)，把目标时刻推到模型记忆窗口“新鲜区”。**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/Agent-Design-Practice/images/4.png)

### 🎯 要解决的核心问题

- 长流程、复杂规划情况下，模型开始容易后面就丢三落四。
- “lost-in-the-middle”问题，目标记不住，做事完全变成“习惯性搬砖”。

### 🔎 常见误区和失败案例

- 认为“只要目标写在很早的位置就够了”；实际上长prompt超过几千token后前面的内容几乎不起作用。
- 每步执行完不总结当下目标，模型每次只关注局部历史，目标漂移极易发生。

### 🛠️ 正确工程实现

1. **把总目标/当前计划维护到todo.md等固定“外部文件”里**，模型能查能写。
2. **每走一步就自动将todo的最新内容摘要成3-5行再贴到上下文结尾**。
3. 确保无论推进了多少步，模型推理时总能“读到”核心目标。

### ✅ 成功效果

- 目标遗忘率、跑偏率大幅下降。
- 对话长期连贯性稳定提升。
- 批处理/复杂工程流极大降本。

------

## 5. 错误留痕（自适应自我修正）

### 🌟 介绍与目的

大循环、复杂任务一定会犯错。留痕的策略就是**不掩饰失败，而要让模型时刻“看到曾经摔过的坑”——让模型的“记忆”里包含错误与其后果，实现经验累积。**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/Agent-Design-Practice/images/5.png)

### 🎯 要解决的核心问题

- “无脑reset”导致同样的错误一犯再犯；不学习的AI=死板工程。
- 如果每轮错误都被try/except吞掉或清理，模型无法通过上下文学习“这里有坑”。

### 🔎 常见误区和反例

- 每次工具报错只做retry/回滚，不让LM看到真实堆栈/报错内容。
- 担心展示失败让上下文“污染”，反而丢掉最有价值的反馈信号。

### 🛠️ 正确工程实现

1. **遇到任何错误都原样把堆栈、报错、输入、错误类型等详细信息“追加到上下文”**，禁止精简/清理。
2. **复盘日志格式需清晰显示错误状态**，模型看到有“失败”几率会主动避开类似操作。
3. **链路生命周期结束时，保留所有错误，不因重试而清空任何trace**。

### ✅ 成功效果

- 系统性错误大幅减少同一位置重试次数。
- 工具调用越智能，后续整体成功率越高。
- 工程师debug更容易定位根因。

------

## 6. 反Few-Shot同质化（多样化防模式陷阱）

### 🌟 介绍与目的

Few-Shot本是模型“示范学习”。但批处理或流水线任务中，**过于统一/标准的上下文样例其实是给模型挖坑——它会过度模仿而忘了自我决策。**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/Agent-Design-Practice/images/6.png)

### 🎯 要解决的核心问题

- AI容易产生“顺拐模式”，看到前面都是一样的样板行为，就无脑复制粘贴，不考虑个体差异。
- “节奏锁定”一旦发生，后面的20条输出翻车概率极高。

### 🔎 常见误区

- 追求极致规范导致上下文示例高度复制粘贴。
- 没有主动引入“模板多样化”“同义词变换”“顺序扰动”。

### 🛠️ 正确工程实现

1. **准备3-5套不同的模板，记录观测和动作时随机选用。**

2. **对于JSON等结构体要定期扰动key顺序（或补充冗余字段使格式不能死板）。**

3. **动作命令/解释里可以安排轻度“语义漂移”，比如用“取得”替代“获取”，让模型学会分辨而非机械套壳。**

   示例代码：

   ```
   templates = ["输出如下:\n{obs}", ">> {obs}", "[RESULT]\n{obs}"]
   def obs_record(obs):
       return random.choice(templates).format(obs=obs)
   ```

   

### ✅ 成功效果

- 集合稳定度显著提升，极大降低“第二次起幻觉”风险。
- 长链任务不再出现中后程“格式溃散”。



## 7. Predicted Outputs 快速跳过已知文本

### 🌟 介绍与目的

Predicted Outputs 是 OpenAI（gpt-4o / 4.1 系列）提供的推理期加速能力：
 当你**已知**结果里有一大段文字必然原封不动出现时，把它作为 `prediction` 传给模型；模型逐 token 校验，一致即“直接采用”，从而**跳过重打**。典型收益场景是“**大文件小改动**”。

### 🎯 要解决的核心问题

- **重复解码浪费**：修改 3 行，模型却又把 3 000 行旧代码重新生成一遍。
- **带宽与首字节延迟**：大段回显拖慢流式首 token。
- **前缀已靠 KV-Cache，但 decode 仍长**：Prefill 省下了，生成阶段还得再省。

### 🔎 常见误区 / 致命陷阱

| 误区                                       | 后果                                                         |
| ------------------------------------------ | ------------------------------------------------------------ |
| “所有调用一刀切开 PO”                      | 普通对话或工具调用命中率<30%，rejected token 多 → 反而更慢更贵 |
| 把**整份**预测传上去又不设 `search_length` | 预测稍有错，几百 token 被集体标记 rejected，白付费           |
| 在 function-calling 场景开启 PO            | 目前不兼容，直接 400/失败                                    |
| 不监控 `accepted / rejected`               | 命中率骤降无人知，账单爆炸                                   |

### 🛠️ 正确工程实现

**满足三条件再启用**

- 输出 ≥ 80 % 可提前确定；
- 本轮不需要 tools / n>1 / presence_penalty；
- 模型为 gpt-4o / 4.1 系列。

**示例简述：**
 下面的 Python 代码调用 OpenAI GPT-4o-mini，并在 `prediction` 字段中直接提交整份旧 TypeScript 文件。模型先逐 token 校验这段代码；凡与预测一致的部分直接复用，仅生成把 `username` 改为 `email` 的少量新行，因此大幅缩短解码时间。执行后可通过 `accepted_prediction_tokens / rejected_prediction_tokens` 字段看到有多少预测 token 被采纳或打回。

```
import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

# 原始代码文件（大部分将被复用）
code = """
class User {
  firstName: string = "";
  lastName:  string = "";
  username:  string = "";
}

export default User;
""".strip()

# 提示：告诉模型只是把 username 改成 email，且只返回代码
refactor_prompt = (
    'Replace the "username" property with an "email" property. '
    "Respond only with code, and with no markdown formatting."
)

response = openai.chat.completions.create(
    model="gpt-4o-mini",        # 仅 gpt-4o / 4o-mini / 4.1 系列支持 PO
    messages=[
        {"role": "user", "content": refactor_prompt},
        {"role": "user", "content": code}
    ],
    # ★ 核心：把整份旧文件当作预测文本
    prediction={
        "type": "content",
        "content": code
    }
)

print("=== 新文件 ===")
print(response.choices[0].message.content)

usage = response.usage.completion_tokens_details
print("\naccepted_prediction_tokens :", usage.accepted_prediction_tokens)
print("rejected_prediction_tokens :", usage.rejected_prediction_tokens)
```

***Refer to：***

***https://medium.com/@peakji/context-engineering-for-ai-agents-lessons-from-building-manus-71883f0a67f2***

***https://platform.openai.com/docs/guides/predicted-outputs***
