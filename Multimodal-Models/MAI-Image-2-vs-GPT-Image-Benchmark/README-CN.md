# MAI-Image-2.6 与 GPT-Image-2：全质量档位图像生成对比

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

**补充选例：[联想新品的 MAI 联网开／关对照](data/lenovo-web-grounding-20260908/README-CN.md)。** 展示两个有文字事实改善的场景及全部两轮原图；独立于下方双模型测试，包含选例范围、耗时和超时记录。

## 本轮：两模型与全部质量档位

[English](README.md) | [逐题图片](#并排图片对比) | [测量记录](data/paired-all-quality-20260907/5way_v2_results.json) | [指标](data/paired-all-quality-20260907/summary.json) | [请求记录](data/paired-all-quality-20260907/attempts.jsonl)

**本轮 87/88 个正式样本返回图片，1 个未返回图片；另有 4 次预热，不计入正式分母。** 同一客户端交替调用，提示词、尺寸和轮数相同；部署区域不同，不能把端到端耗时差全部归因于模型。质量是非盲评的具体画面观察，不是官方 benchmark 分数、人类偏好胜率或生产可靠性证明。

### 测试口径

| 配置 | 模型版本 | 质量参数 | 尺寸 | 区域 | 正式样本 |
| --- | --- | --- | --- | --- | --- |
| MAI-Image-2.6 | 2026-07-31 | 未传入 | 1024x1024 | swedencentral | 22 |
| GPT-Image-2 low | 2026-04-21 | low | 1024x1024 | eastus2 | 22 |
| GPT-Image-2 medium | 2026-04-21 | medium | 1024x1024 | eastus2 | 22 |
| GPT-Image-2 high | 2026-04-21 | high | 1024x1024 | eastus2 | 22 |

输入是原报告同一份 11 题 CSV。每组先用 `blue circle` 预热一次；第一轮每题依次调用 MAI、GPT low、medium、high，第二轮反转。并发为 1，每次逻辑调用后间隔 5 秒，最多尝试 3 次，沿用原重试退避。两个 GlobalStandard 部署各配置每分钟 2 次请求；GPT 三档共享同一部署和限额。MAI 请求超时 180 秒，GPT 为 300 秒。

客户端: Windows-11-10.0.26200-SP0, ARM64, Python 3.13.15, requests 2.34.2.

正式起止时间 (UTC): `2026-09-07T12:32:56.332837+00:00` to `2026-09-07T16:24:46.795573+00:00`. 正式窗口含等待: **13,910.46 s**. 四组合计观测完成速率: **0.38 张/分钟** (不是单模型或最大吞吐).

### 调用链与计时边界

```mermaid
flowchart LR
    prompts["Original 11 prompts"] --> runner["Local Windows Python runner"]
    runner --> mai["MAI-Image-2.6 / Sweden Central"]
    runner --> gpt["GPT-Image-2 / East US 2 / low, medium, high"]
    mai --> evidence["PNG, usage, request IDs, timestamps, failures"]
    gpt --> evidence
    evidence --> summary["Offline validation and report"]
```

原创解释图：本项目实际客户端与服务调用关系，不描绘模型内部结构。 [MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image) | [GPT image API](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/dall-e).

### 耗时与请求成功情况

| 指标 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 成功 / 计划样本 | 22 / 22 | 22 / 22 | 22 / 22 | 21 / 22 |
| 首试成功 / 计划样本 | 20 / 22 | 20 / 22 | 20 / 22 | 20 / 22 |
| HTTP 尝试次数 / 429 | 24 / 0 | 24 / 0 | 24 / 0 | 25 / 0 |
| 未成功的 HTTP 尝试 | 2 | 2 | 2 | 4 |
| 未成功尝试累计耗时 (s) | 192.56 | 329.49 | 5,291.35 | 604.30 |
| 平均请求耗时 (s) | 45.33 | 38.69 | 65.09 | 175.17 |
| P50 / 描述性 P95 (s) | 38.03 / 79.77 | 31.19 / 81.41 | 64.64 / 74.82 | 171.26 / 215.09 |
| 样本标准差 (s) | 18.56 | 19.69 | 6.01 | 23.51 |
| 最小 / 最大请求耗时 (s) | 32.19 / 106.81 | 23.61 / 99.08 | 56.04 / 78.13 | 139.24 / 241.38 |
| 第一轮 / 第二轮平均 (s) | 47.57 / 43.09 | 43.30 / 34.09 | 67.27 / 62.90 | 171.91 / 178.14 |
| 全部样本平均任务耗时 (s) | 55.06 | 54.65 | 306.58 | 196.12 |
| 成功图片平均大小 (KiB) | 1,737 | 1,673 | 1,666 | 1,683 |

请求耗时从 `requests.post` 调用前到完整 HTTP 响应返回，只统计有图片的成功尝试，不包含后续 JSON/base64 处理和文件写盘。任务耗时覆盖失败尝试、重试等待和响应处理，按全部计划样本统计。失败不以 0 秒进入速度平均值，也不从成功率分母删除。P95 为每组最多 22 个值的描述性线性插值，不是生产尾延迟保证。

### 异常与等待

最长的未成功尝试是 `gpt-image-2-medium-r1-p09`，客户端记录 4,968.72 秒。这是请求调用的客户端经过时间，不是服务端 GPU 推理时长；底层原因未被这些日志确定。异常保留在任务耗时、请求计数和实际完成速率中，未返回图片的样本仍计入计划分母。

| 样本 | 尝试 | HTTP / 异常类型 | 客户端耗时 (s) | 开始 (UTC) | 结束 (UTC) |
| --- | --- | --- | --- | --- | --- |
| gpt-image-2-high-r1-p01 | 1 | ReadTimeout | 301.99 | 2026-09-07T12:35:59.924543+00:00 | 2026-09-07T12:41:11.917183+00:00 |
| gpt-image-2-high-r1-p01 | 2 | ConnectionError | 0.01 | 2026-09-07T12:41:11.921034+00:00 | 2026-09-07T12:41:21.934816+00:00 |
| gpt-image-2-high-r1-p01 | 3 | ConnectionError | 0.00 | 2026-09-07T12:41:21.937598+00:00 | 2026-09-07T12:41:21.941635+00:00 |
| mai-image-2.6-r1-p02 | 1 | ConnectionError | 0.00 | 2026-09-07T12:41:26.958872+00:00 | 2026-09-07T12:41:36.998889+00:00 |
| gpt-image-2-medium-r1-p09 | 1 | ConnectionError | 4,968.72 | 2026-09-07T13:26:31.695448+00:00 | 2026-09-07T14:49:30.415316+00:00 |
| gpt-image-2-low-r1-p11 | 1 | 400 | 20.50 | 2026-09-07T14:58:49.988889+00:00 | 2026-09-07T14:59:20.487114+00:00 |
| gpt-image-2-high-r2-p08 | 1 | ReadTimeout | 302.29 | 2026-09-07T15:40:22.017096+00:00 | 2026-09-07T15:45:34.310843+00:00 |
| mai-image-2.6-r2-p08 | 1 | ReadTimeout | 192.56 | 2026-09-07T15:52:16.770891+00:00 | 2026-09-07T15:55:39.334382+00:00 |
| gpt-image-2-medium-r2-p09 | 1 | ReadTimeout | 322.63 | 2026-09-07T16:01:37.758367+00:00 | 2026-09-07T16:07:10.387228+00:00 |
| gpt-image-2-low-r2-p09 | 1 | ReadTimeout | 309.00 | 2026-09-07T16:08:16.133855+00:00 | 2026-09-07T16:13:35.129678+00:00 |

### Token 用量

| 配置 | 返回的输出 token | 成功 / 计划样本 |
| --- | --- | --- |
| MAI-Image-2.6 | 1024 | 22/22 |
| GPT-Image-2 low | 196 | 22/22 |
| GPT-Image-2 medium | 1756 | 22/22 |
| GPT-Image-2 high | 7024 | 21/22 |

token 用量取自接口返回的 usage，不从模型或档位推算。没有返回值的样本不补零。输出 token 数和 PNG 文件大小都不能单独证明画质。

### 逐场景两轮耗时

单位为秒；失败格对应原始请求记录，不用其他轮次替换。

| 场景 / 轮次 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 01 / R1 | 38.82 | 51.44 | 78.13 | 失败 |
| 01 / R2 | 33.96 | 26.25 | 63.52 | 182.78 |
| 02 / R1 | 65.12 | 41.67 | 74.93 | 176.78 |
| 02 / R2 | 37.43 | 28.50 | 60.23 | 170.60 |
| 03 / R1 | 32.29 | 82.39 | 68.42 | 170.29 |
| 03 / R2 | 32.19 | 23.61 | 59.58 | 152.75 |
| 04 / R1 | 38.63 | 47.05 | 65.18 | 192.56 |
| 04 / R2 | 34.69 | 23.98 | 59.51 | 171.26 |
| 05 / R1 | 60.09 | 29.09 | 69.86 | 187.57 |
| 05 / R2 | 38.42 | 24.80 | 63.22 | 163.33 |
| 06 / R1 | 80.54 | 62.70 | 71.35 | 190.79 |
| 06 / R2 | 32.25 | 35.88 | 65.19 | 185.09 |
| 07 / R1 | 54.92 | 33.29 | 67.74 | 177.19 |
| 07 / R2 | 37.63 | 35.08 | 66.85 | 170.62 |
| 08 / R1 | 36.49 | 35.03 | 68.73 | 174.50 |
| 08 / R2 | 106.81 | 99.08 | 72.83 | 215.09 |
| 09 / R1 | 49.96 | 37.29 | 61.67 | 169.84 |
| 09 / R2 | 41.92 | 25.10 | 60.62 | 241.38 |
| 10 / R1 | 32.92 | 28.74 | 57.93 | 139.24 |
| 10 / R2 | 42.97 | 25.43 | 64.09 | 153.85 |
| 11 / R1 | 33.49 | 27.58 | 56.04 | 140.32 |
| 11 / R2 | 35.77 | 27.29 | 56.27 | 152.77 |

### 逐场景画面观察

仅为 AI 辅助非盲评。每格记录实际画面差异，不生成数值质量评分。 [检查记录](data/paired-all-quality-20260907/quality-review.json).

| 场景 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 1 | 两轮都有蓝色金属和服、花卉与前景虚化；R1背景明亮，R2转为暗调，均未见额外文字。 | 两轮都以紧凑人像和金属花饰为主，画面偏暗；R2衣料更像银色皱箔，高曝光效果不明显。 | 两轮金属花卉与蓝银服饰清楚，整体偏暗；R2面部较光滑、衣料偏硬壳质感。 | R1未返回图片；R2回眸人物与银色金属花饰清楚，顶部发饰被裁切，未见额外文字。 |
| 2 | 两轮都保留凌乱卧室与入口；R1城堡和瀑布比森林抢眼，两轮均加入较多未请求英文标语。 | 两轮石门、林间小路与散落衣物构成场景，室内暗部较深；R2另有海报文字和门框符号。 | 两轮藤蔓石门与卧室杂物可辨；R1门框有发光符号，R2林中出现鹿，部分海报小字难辨。 | 两轮入口内的森林纵深清楚；R1石环有绿色符号，R2木藤入口底部悬离地面。 |
| 3 | 两轮小宇航员、月面和蛋壳均明确；R1是娃娃脸，R2上半蛋壳悬空，带少量服装标记。 | R1宇航员挥手，R2从斑点蛋壳探身；月面和面罩反光明确，未见明显肢体异常。 | 两轮人物都扶着裂壳边缘，月面细节清楚；服装额外加入NASA或类似徽标。 | R1后方高壳壁突出破壳形态，R2挥手且碎壳落地；未见醒目文字或明显结构异常。 |
| 4 | 两轮红龙、巢、桌面、窗光和蒸汽齐全，书名和纸页额外出现大量可读英文。 | 红龙两轮都蜷卧于巢中，器具与背景虚化符合桌面近景；色调偏深暖棕，纸页字迹难辨。 | 两轮蜷睡红龙、书页、枝巢和杯中蒸汽明确；R2局部窗光泛白，书页有密集字样。 | 两轮近景鳞片、巢和器物清楚；R1卷曲身体遮挡肢体，R2杯子遮住部分巢缘，纸卷有小字。 |
| 5 | 两轮白色长耳毛绒主体与浮岛、城堡呼应幻想主题；R2右上多出未请求的英文标语。 | R1粉色长角生物捧发光球，R2白色双角生物趴在苔丘上；两轮均未见额外文字。 | 两轮大眼毛绒主体坐在云上，周围有小配角和梦幻装饰，未见额外文字。 | R1主体头顶似有另一张脸，产生兜帽或双脸歧义；R2大耳生物、花簇和蘑菇清楚，两轮未见文字。 |
| 6 | 两轮水潭、光束、垂藤、兰花和遗迹均出现；R1水下纹理繁密，R2遗迹半浸水关系不易辨认。 | 两轮石庙临水、兰花和光束呼应提示，R1洞壁阴影较重；未见额外叠字。 | 两轮前景石柱、雕刻与浸水结构较明确，建筑占据较多画面，未见额外叠字。 | 两轮光束、水面、垂藤与右侧遗迹清楚；R1洞口部分高光发白，R2前景石柱部分入水。 |
| 7 | 两轮银发蓝眼与全息工坊明确；R1偏动漫风且小字不规整，R2加入NEXA品牌和多处标语。 | 两轮短银发人物点按全息屏，皮肤与夹克质感清楚；均有PROJECT: AURORA，R2杯身另有标语。 | 两轮人物操作机械部件全息图；R1面板右缘被截断，两轮均加入项目名、品牌或标语。 | 两轮发丝、布料和金属反光清楚；全息屏都增加项目名，R2还有额外标语，细小界面字仍难辨。 |
| 8 | 两轮巨眼、星系与密集卷纹构成宇宙景观，并额外加入冥想人物，未见文字。 | 两轮多只巨眼、星球和重复卷纹覆盖天空，地景内容密集；R1细部有颗粒感，均未见文字。 | 两轮以巨眼、球体、旋涡星系和密集纹理为主，R1暗部较深，R2中央几何球发光。 | R1巨眼融入桥状地景并加入行走人物，R2蓝橙双眼近对称且增加冥想人物；均未见文字。 |
| 9 | 两轮银灰龙形侧脸布满螺旋，表面偏雕刻或骨瓷质感，背景虚化；R2另有月下城堡。 | 两轮蓝金镂空龙形近景有清晰眼部和卷须，R1顶部角被裁切，密集装饰的局部连接难辨。 | 两轮蓝金龙首覆盖大小螺旋，浅景深明确，皮肤更像金属雕饰，未见文字。 | R1蓝紫生物有圆瞳与珠粒状螺旋皮肤，卷须交叠处难辨；R2橙眼和多尺度螺旋清楚，未见文字。 |
| 10 | 两轮猫都露齿持双槌打鼓，握槌明显拟人化；鼓组与海报添加英文，R2底鼓和下方文字被裁切。 | 两轮猫露齿举槌，部分前爪有动作模糊；衣服与鼓面增加英文，R2底鼓下缘被裁切。 | 两轮鼓手居中，毛发和镀铬反光清楚；增加I HATE MONDAYS或PAWS OF FURY等文字，部分爪槌边缘模糊。 | 两轮龇牙表情与双槌姿态明确，前景鼓组被画框裁切，另加HISS OFF或BAD KITTY等文字。 |
| 11 | R1猴子弹梨形弦乐器，R2坐在石板路弹吉他；毛发与木纹清楚，书脊或小费碗另有未请求文字。 | 两轮主体弹吉他并增加演出文字，R1脸型偏幼猿，R2琴头被裁切；R1首次输出审核拦截后重试才返回此图。 | 两轮戴草帽猴子弹吉他，背景增加演出文字；R2拨弦手模糊、琴头右端被裁切。 | R1猴子在复古麦克风旁弹吉他，R2闭眼盘腿演奏；材质清楚，背景均有额外英文。 |

### 本轮实际接口设置

| 接口项目 | MAI-Image-2.6 | GPT-Image-2 |
| --- | --- | --- |
| POST | `/mai/v1/images/generations` | `/openai/deployments/{deployment}/images/generations?api-version=2025-04-01-preview` |
| Payload | `model`, `prompt`, `width=1024`, `height=1024` | `prompt`, `n=1`, `size=1024x1024`, `quality=low/medium/high` |
| Auth | `api-key` | `api-key` |
| Output | `data[0].b64_json`, PNG | `data[0].b64_json`, PNG |
| Usage | `usage.num_input_text_tokens`, `usage.num_output_tokens` | `usage.input_tokens_details`, `usage.output_tokens_details` |

## 复现与测试

需要可用的 MAI-Image-2.6 和 GPT-Image-2 部署。部署身份由您查询确认，不能仅凭 deployment 名称判断底层模型。先克隆仓库、拉取本项目的 Git LFS 文件，并在 Python 环境安装 requests：

```powershell
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark
git lfs install
git lfs pull --include="Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/**"
python -m pip install requests==2.34.2
```

下列两个资源根地址和 GPT deployment 名称由您填写。通过自己的秘密管理机制在当前进程提供 `AZURE_API_KEY`（MAI）和 `AZURE_OPENAI_API_KEY`（GPT），不要把值写入源码或 Git。各模型的版本、区域、SKU 和限额环境变量必须填写实际查询结果；下面展示本次实测元数据，不代表您的资源设置。

```powershell
$env:MAI_ENDPOINT = 'https://<mai-resource>.services.ai.azure.com'
$env:GPT_ENDPOINT = 'https://<openai-resource>.openai.azure.com'
$env:GPT_DEPLOYMENT = '<gpt-image-2-deployment>'
$env:GPT_API_VERSION = '2025-04-01-preview'
$env:MAI_MODEL_VERSION = '2026-07-31'
$env:GPT_MODEL_VERSION = '2026-04-21'
$env:MAI_DEPLOYMENT_SKU = 'GlobalStandard'
$env:GPT_DEPLOYMENT_SKU = 'GlobalStandard'
$env:MAI_DEPLOYMENT_REGION = 'swedencentral'
$env:GPT_DEPLOYMENT_REGION = 'eastus2'
$env:MAI_RATE_LIMIT_RPM = '2.0'
$env:GPT_RATE_LIMIT_RPM = '2.0'
$env:BENCHMARK_CLIENT_LOCATION = 'Describe your actual client location'
python scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --dry-run
```

第一条模型命令只预热四组，第二条从同一输出目录继续正式矩阵；均会消耗 Azure 服务用量。已有结果不会覆盖，已记录样本不会重跑。续跑要求同一脚本、提示词、端点和配置；中断时在途请求可能已被服务接收。新测试应在执行前保存脚本与 CSV，运行期间不得修改。

```powershell
$run = 'runs/paired-all-quality-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --resume
python scripts/summarize_paired_run.py $run
```

以下命令只重算已保存结果，不调用模型。回归覆盖四档请求、失败分母、原始 usage、图片归属和报告覆盖；模拟 HTTP 只用于离线单元测试，不是图像质量证据。新测批次的汇总与发布必须等全部计划样本结束。

```powershell
python scripts/summarize_paired_run.py data/paired-all-quality-20260907
python scripts/render_paired_report.py data/paired-all-quality-20260907 --check
python -m unittest discover -s tests -v
```

执行脚本: [benchmark_5way_v2.py](scripts/benchmark_5way_v2.py); 离线汇总: [summarize_paired_run.py](scripts/summarize_paired_run.py); 报告生成: [render_paired_report.py](scripts/render_paired_report.py); 回归测试: [tests](tests).


### 结论边界

本报告只对比 MAI-Image-2.6 与 GPT-Image-2 的 low、medium、high 三档。范围为 11 个文生图场景与 1024x1024，不包括 2K、图像编辑、多图参考、文字准确率专项、并发压测或其他认证方式。MAI 没有传质量参数，不能称为 GPT high 的等价档位。所有指标只使用本次四组测试的数据。

证据目录: [data/paired-all-quality-20260907](data/paired-all-quality-20260907). 包含原始图片、测量记录、逐次请求、响应元数据及删减后的公开源码副本。非财务测量字段和图片保持不变；原始执行哈希与公开文件哈希分别记录于 [来源说明](data/paired-all-quality-20260907/provenance.json). 提示词 SHA-256: `be3d628c66a1e4d535d06bcc84246a04aad11f35a48f3133d451fe86283782ce`.

## 并排图片对比

每个场景、每一轮只展示 MAI-Image-2.6 与 GPT-Image-2 low、medium、high。图片来自本次四组测试，未返回图片的格子保留失败说明。点击图片查看原始 1024x1024 PNG。

### Test 1: 金属和服少女

> **Prompt**: Chrome kimono, a maiden surrounded by metallic flowers, earrings, ornate, dark blue, exquisite realism, high exposure, Canon 5D, cinematic lighting, metallic luster, blurred foreground, depth of field, light

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 1, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/01_test.png) | ![GPT-Image-2 low, prompt 1, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/01_test.png) | ![GPT-Image-2 medium, prompt 1, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/01_test.png) | 未返回图片 |
| 38.82 s<br>1856 KiB | 51.44 s<br>1636 KiB | 78.13 s<br>1504 KiB | 3 次尝试；任务耗时 322.06 s |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 1, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/01_test.png) | ![GPT-Image-2 low, prompt 1, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/01_test.png) | ![GPT-Image-2 medium, prompt 1, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/01_test.png) | ![GPT-Image-2 high, prompt 1, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/01_test.png) |
| 33.96 s<br>1699 KiB | 26.25 s<br>1641 KiB | 63.52 s<br>1704 KiB | 182.78 s<br>1531 KiB |

### Test 2: 森林传送门

> **Prompt**: a portal into a mythical forest on the wall of my small messy bedroom

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 2, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/02_test.png) | ![GPT-Image-2 low, prompt 2, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/02_test.png) | ![GPT-Image-2 medium, prompt 2, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/02_test.png) | ![GPT-Image-2 high, prompt 2, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/02_test.png) |
| 65.12 s<br>1676 KiB | 41.67 s<br>1438 KiB | 74.93 s<br>1477 KiB | 176.78 s<br>1727 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 2, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/02_test.png) | ![GPT-Image-2 low, prompt 2, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/02_test.png) | ![GPT-Image-2 medium, prompt 2, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/02_test.png) | ![GPT-Image-2 high, prompt 2, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/02_test.png) |
| 37.43 s<br>1721 KiB | 28.50 s<br>1491 KiB | 60.23 s<br>1489 KiB | 170.60 s<br>1619 KiB |

### Test 3: 月球宇航员

> **Prompt**: a tiny astronaut hatching from an egg on the moon

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 3, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/03_test.png) | ![GPT-Image-2 low, prompt 3, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/03_test.png) | ![GPT-Image-2 medium, prompt 3, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/03_test.png) | ![GPT-Image-2 high, prompt 3, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/03_test.png) |
| 32.29 s<br>1387 KiB | 82.39 s<br>1354 KiB | 68.42 s<br>1499 KiB | 170.29 s<br>1543 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 3, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/03_test.png) | ![GPT-Image-2 low, prompt 3, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/03_test.png) | ![GPT-Image-2 medium, prompt 3, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/03_test.png) | ![GPT-Image-2 high, prompt 3, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/03_test.png) |
| 32.19 s<br>1539 KiB | 23.61 s<br>1295 KiB | 59.58 s<br>1428 KiB | 152.75 s<br>1457 KiB |

### Test 4: LOTR 小红龙

> **Prompt**: Photo realistic scene inspired by LOTR: [A tiny red dragon in a nest on a medieval wizard's table]. Shot with a macro lens (f/2.8, 50mm) and a Canon EOSR5, the soft focus captures [the cozy morning light filtering through a near by window]. The pastel colors and whimsical steam shapes enhance the serene atmosphere, evoking a DnD RPG setting. The image is rendered in 16K and 8K, highlighting [the intricate details and medieval charm].

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 4, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/04_test.png) | ![GPT-Image-2 low, prompt 4, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/04_test.png) | ![GPT-Image-2 medium, prompt 4, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/04_test.png) | ![GPT-Image-2 high, prompt 4, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/04_test.png) |
| 38.63 s<br>1589 KiB | 47.05 s<br>1382 KiB | 65.18 s<br>1457 KiB | 192.56 s<br>1443 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 4, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/04_test.png) | ![GPT-Image-2 low, prompt 4, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/04_test.png) | ![GPT-Image-2 medium, prompt 4, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/04_test.png) | ![GPT-Image-2 high, prompt 4, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/04_test.png) |
| 34.69 s<br>1585 KiB | 23.98 s<br>1366 KiB | 59.51 s<br>1485 KiB | 171.26 s<br>1402 KiB |

### Test 5: 梦幻生物

> **Prompt**: Cute and adorable fluffy cute creature fantasy, dreamlike, surrealism, super cute, trending on artstation

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 5, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/05_test.png) | ![GPT-Image-2 low, prompt 5, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/05_test.png) | ![GPT-Image-2 medium, prompt 5, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/05_test.png) | ![GPT-Image-2 high, prompt 5, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/05_test.png) |
| 60.09 s<br>1435 KiB | 29.09 s<br>1673 KiB | 69.86 s<br>1450 KiB | 187.57 s<br>1526 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 5, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/05_test.png) | ![GPT-Image-2 low, prompt 5, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/05_test.png) | ![GPT-Image-2 medium, prompt 5, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/05_test.png) | ![GPT-Image-2 high, prompt 5, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/05_test.png) |
| 38.42 s<br>1417 KiB | 24.80 s<br>1622 KiB | 63.22 s<br>1437 KiB | 163.33 s<br>1586 KiB |

### Test 6: 丛林天坑

> **Prompt**: A hidden cenote in the heart of a lush jungle beckons with crystalline turquoise waters. Vibrant emerald vines cascade down weathered limestone walls, their tendrils barely kissing the water's surface. Shafts of golden sunlight pierce through a natural skylight above, creating a mystical interplay of light and shadow on the cavern walls. Iridescent butterflies flit between exotic orchids clinging to rocky outcrops. A partially submerged Mayan ruin, its intricate carvings softened by time, stand

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 6, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/06_test.png) | ![GPT-Image-2 low, prompt 6, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/06_test.png) | ![GPT-Image-2 medium, prompt 6, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/06_test.png) | ![GPT-Image-2 high, prompt 6, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/06_test.png) |
| 80.54 s<br>2149 KiB | 62.70 s<br>2088 KiB | 71.35 s<br>2110 KiB | 190.79 s<br>2024 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 6, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/06_test.png) | ![GPT-Image-2 low, prompt 6, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/06_test.png) | ![GPT-Image-2 medium, prompt 6, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/06_test.png) | ![GPT-Image-2 high, prompt 6, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/06_test.png) |
| 32.25 s<br>2131 KiB | 35.88 s<br>2042 KiB | 65.19 s<br>2151 KiB | 185.09 s<br>1979 KiB |

### Test 7: 科技少女

> **Prompt**: A charming, tech-savvy [girl with short, silver pixie-cut] hair and vibrant [blue] eyes, wearing a casual yet futuristic outfit. She's focused on a holographic interface while working in a sleek, high-tech workshop.

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 7, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/07_test.png) | ![GPT-Image-2 low, prompt 7, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/07_test.png) | ![GPT-Image-2 medium, prompt 7, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/07_test.png) | ![GPT-Image-2 high, prompt 7, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/07_test.png) |
| 54.92 s<br>1556 KiB | 33.29 s<br>1543 KiB | 67.74 s<br>1520 KiB | 177.19 s<br>1538 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 7, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/07_test.png) | ![GPT-Image-2 low, prompt 7, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/07_test.png) | ![GPT-Image-2 medium, prompt 7, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/07_test.png) | ![GPT-Image-2 high, prompt 7, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/07_test.png) |
| 37.63 s<br>1495 KiB | 35.08 s<br>1548 KiB | 66.85 s<br>1529 KiB | 170.62 s<br>1648 KiB |

### Test 8: 迷幻宇宙

> **Prompt**: Universe, LSD, Fractal Worlds, Giant Eyes

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 8, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/08_test.png) | ![GPT-Image-2 low, prompt 8, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/08_test.png) | ![GPT-Image-2 medium, prompt 8, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/08_test.png) | ![GPT-Image-2 high, prompt 8, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/08_test.png) |
| 36.49 s<br>2305 KiB | 35.03 s<br>2175 KiB | 68.73 s<br>2270 KiB | 174.50 s<br>2250 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 8, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/08_test.png) | ![GPT-Image-2 low, prompt 8, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/08_test.png) | ![GPT-Image-2 medium, prompt 8, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/08_test.png) | ![GPT-Image-2 high, prompt 8, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/08_test.png) |
| 106.81 s<br>2356 KiB | 99.08 s<br>2441 KiB | 72.83 s<br>2337 KiB | 215.09 s<br>2270 KiB |

### Test 9: 分形生物

> **Prompt**: close up dof render of a mythical creature made of detailed spiraling fractals and tendrils, detailed recursive skin texture

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 9, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/09_test.png) | ![GPT-Image-2 low, prompt 9, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/09_test.png) | ![GPT-Image-2 medium, prompt 9, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/09_test.png) | ![GPT-Image-2 high, prompt 9, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/09_test.png) |
| 49.96 s<br>1767 KiB | 37.29 s<br>1871 KiB | 61.67 s<br>1731 KiB | 169.84 s<br>1686 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 9, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/09_test.png) | ![GPT-Image-2 low, prompt 9, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/09_test.png) | ![GPT-Image-2 medium, prompt 9, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/09_test.png) | ![GPT-Image-2 high, prompt 9, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/09_test.png) |
| 41.92 s<br>1737 KiB | 25.10 s<br>1840 KiB | 60.62 s<br>1747 KiB | 241.38 s<br>1666 KiB |

### Test 10: 愤怒猫鼓手

> **Prompt**: an angry cat playing drums

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 10, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/10_test.png) | ![GPT-Image-2 low, prompt 10, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/10_test.png) | ![GPT-Image-2 medium, prompt 10, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/10_test.png) | ![GPT-Image-2 high, prompt 10, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/10_test.png) |
| 32.92 s<br>1606 KiB | 28.74 s<br>1460 KiB | 57.93 s<br>1603 KiB | 139.24 s<br>1511 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 10, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/10_test.png) | ![GPT-Image-2 low, prompt 10, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/10_test.png) | ![GPT-Image-2 medium, prompt 10, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/10_test.png) | ![GPT-Image-2 high, prompt 10, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/10_test.png) |
| 42.97 s<br>1652 KiB | 25.43 s<br>1611 KiB | 64.09 s<br>1581 KiB | 153.85 s<br>1592 KiB |

### Test 11: 猴子音乐家

> **Prompt**: A monkey playing music

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 11, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/11_test.png) | ![GPT-Image-2 low, prompt 11, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/11_test.png) | ![GPT-Image-2 medium, prompt 11, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/11_test.png) | ![GPT-Image-2 high, prompt 11, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/11_test.png) |
| 33.49 s<br>1833 KiB | 27.58 s<br>1671 KiB | 56.04 s<br>1612 KiB | 140.32 s<br>1632 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 11, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/11_test.png) | ![GPT-Image-2 low, prompt 11, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/11_test.png) | ![GPT-Image-2 medium, prompt 11, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/11_test.png) | ![GPT-Image-2 high, prompt 11, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/11_test.png) |
| 35.77 s<br>1725 KiB | 27.29 s<br>1615 KiB | 56.27 s<br>1541 KiB | 152.77 s<br>1715 KiB |
