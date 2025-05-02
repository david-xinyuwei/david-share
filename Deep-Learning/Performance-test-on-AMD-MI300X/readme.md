## For Deepseek R1 671B on Azure MI300X

Run container:

```
docker run \
  --device=/dev/kfd \
  --device=/dev/dri \
  --security-opt seccomp=unconfined \
  --cap-add=SYS_PTRACE \
  --group-add video \
  --privileged \
  --shm-size 128g \
  --ipc=host \
  -p 30000:30000 \
  -v /mnt/resource_nvme:/mnt/resource_nvme \
  -e HF_HOME=/mnt/resource_nvme/hf_cache \
  -e HSA_NO_SCRATCH_RECLAIM=1 \
  -e GPU_FORCE_BLIT_COPY_SIZE=64 \
  -e DEBUG_HIP_BLOCK_SYN=1024 \
  rocm/sgl-dev:upstream_20250312_v1 \
  python3 -m sglang.launch_server --model deepseek-ai/DeepSeek-R1 --tp 8 --trust-remote-code --chunked-prefill-size 131072  --host 0.0.0.0 
```

Performance test script:

```
# cat deepseek_benchmark_chat_vshow.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek‑R1 benchmark  (TTFT & total tok/s)
随机打印 3 组 {prompt, completion} 便于人工核查
"""

import argparse, asyncio, aiohttp, json, random, statistics, sys, time
from pathlib import Path
from collections import defaultdict
from transformers import AutoTokenizer

SCENARIOS = {
    "focused":   ((256, 512),  ( 50, 150)),
    "analysis":  ((512, 1024), (150, 500)),
    "reasoning": ((256, 512),  (1024, 1024)),
}

DEFAULT_URL, DEFAULT_CONCURRENCY = "http://localhost:30000/v1/chat/completions", 300
TOKENIZER = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-R1", trust_remote_code=True)

def load_buckets(p: Path):
    dat = json.loads(p.read_text())
    bk  = defaultdict(list)
    for rec in dat:
        dlg = "\n".join(rec["dialogue"])
        chs = "\n".join(f"{chr(65+i)}. {c}" for i, c in enumerate(rec["choices"]))
        prompt = ( "你是一位助理，需要阅读一段对话并回答随后的选择题。"
                   "只输出最终答案对应的文字，不要输出多余内容。\n\n"
                   f"{dlg}\n\n问题：{rec['question']}\n\n选项：{chs}\n\n答案：" )
        ptok = len(TOKENIZER.encode(prompt, add_special_tokens=False))
        for name,(pr,_ ) in SCENARIOS.items():
            if pr[0] <= ptok <= pr[1]:
                bk[name].append(prompt); break
    return bk

class Metrics:
    def __init__(self):
        self.ttft=[]; self.tok=0; self.lock=asyncio.Lock()
        self.samples=[]  # reservoir
    async def add(self, ttft, ctok, prompt, reply):
        async with self.lock:
            self.ttft.append(ttft); self.tok+=ctok
            # reservoir size 3
            k=len(self.samples)
            if k<3:
                self.samples.append((prompt, reply))
            else:
                idx=random.randint(0,k)
                if idx<3:
                    self.samples[idx]=(prompt, reply)

async def call(sess, url, prompt, comp_max, m:Metrics):
    payload={"model":"deepseek-r1","stream":True,
             "messages":[{"role":"user","content":prompt}],
             "max_tokens":comp_max,"temperature":0.7,"top_p":0.9}
    st=time.perf_counter(); first=None; ct=0; reply=[]
    async with sess.post(url,json=payload,timeout=900) as r:
        async for b in r.content:
            if not b.startswith(b"data:"): continue
            d=b[5:].strip()
            if d==b"[DONE]":
                if first: await m.add((first-st)*1000, ct, prompt, "".join(reply))
                return
            try:
                j=json.loads(d)
                delta=j["choices"][0]["delta"]
                if delta.get("content"):
                    tok=delta["content"]
                    if first is None: first=time.perf_counter()
                    ct+=1; reply.append(tok)
                if j["choices"][0].get("finish_reason") is not None:
                    if first: await m.add((first-st)*1000, ct, prompt, "".join(reply))
                    return
            except json.JSONDecodeError:
                continue

async def main(a):
    buckets=load_buckets(Path(a.data_file))
    if a.scenario=="reasoning" and not buckets["reasoning"]:
        buckets["reasoning"]=buckets["focused"][:]            # 复用 prompt

    pool=buckets[a.scenario]
    if not pool: print("No prompt"); return
    prompts=random.choices(pool,k=a.concurrency)
    comp_max=SCENARIOS[a.scenario][1][1]

    m=Metrics(); conn=aiohttp.TCPConnector(limit=a.concurrency)
    t0=time.perf_counter()
    async with aiohttp.ClientSession(connector=conn,
            headers={"Content-Type":"application/json"}) as sess:
        await asyncio.gather(*(call(sess,a.url,p,comp_max,m) for p in prompts))
    wall=time.perf_counter()-t0; n=len(m.ttft)
    if n==0: print("All failed"); return
    pct=lambda lst,p:statistics.quantiles(lst,n=100)[p-1]
    print("\n==== DeepSeek‑R1 Benchmark ====")
    print(f"Scenario        : {a.scenario}")
    print(f"Completed req   : {n}")
    print(f"TTFT ms         : avg={sum(m.ttft)/n:.1f} | "
          f"p50={pct(m.ttft,50):.1f} | p90={pct(m.ttft,90):.1f} | p99={pct(m.ttft,99):.1f}")
    print(f"Total tokens/s  : {m.tok/wall:.1f}")
    # 打印随机采样的 3 组结果
    print("\n--- Random 3 samples ---")
    for i,(p,r) in enumerate(m.samples,1):
        print(f"\n[SAMPLE {i}] Prompt excerpt:\n{p[:120]}...")
        print(f"Reply excerpt  :\n{r[:400]}...\n")
    print("================================\n")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--data_file",default="external_dialogue_comprehension.json")
    ap.add_argument("--scenario",choices=SCENARIOS,required=True)
    ap.add_argument("--concurrency",type=int,default=DEFAULT_CONCURRENCY)
    ap.add_argument("--url",default=DEFAULT_URL)
    asyncio.run(main(ap.parse_args()))
```



**Senario1**

```
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 deepseek_benchmark_chat_vshow.py \
        --scenario focused \
        --concurrency 300 \
        --data_file external_dialogue_comprehension.json \
        --url http://172.167.140.16:30000/v1/chat/completions

==== DeepSeek‑R1 Benchmark ====
Scenario        : focused
Completed req   : 300
TTFT ms         : avg=2031.1 | p50=2030.8 | p90=2038.1 | p99=2042.3
Total tokens/s  : 2771.4

--- Random 3 samples ---

[SAMPLE 1] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

女：今天我们非常荣幸地请到了中国体操队的总指导黄玉斌。黄指导曾经是优秀的体操运动员，现在又是一位“金牌教练”。您在结束了运动员生涯之后，就走上...
Reply excerpt  :
好的，我现在需要仔细看一下这段对话，然后回答问题。问题是问在当教练之前，男的曾经做过什么，选项是四个不同的职业。

首先，对话一开始，女的介绍黄指导是中国体操队的总教练，提到他以前是优秀的体操运动员，现在是金牌教练。然后她问黄指导在结束运动员生涯后成为教练是不是人生的转折。男的回应说，退役后努力学习文化知识和训练方法，这些帮助了他的教学。所以这里明显提到他之前是运动员，之后转成教练。所以答案应该是C选项运动员。

再检查其他部分有没有提到其他职业。女的问刚开始当教练时的挑战，男的提到需要团结团队和保持高水平竞技状态，以及让运动员做出更难的动作。后面讨论到...


[SAMPLE 2] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

男：各位网友大家好，现在我们请到的嘉宾是中国有名的跳水队员吴敏霞。
女：大家好，我是吴敏霞。
男：据说很多人都是在年龄很小的时候进入跳水队，几...
Reply excerpt  :
好，我现在要解决这个问题。首先，我需要仔细阅读对话内容，找出与问题相关的部分。问题是：“女的刚进国家队时是什么情况？”选项是B选项“年龄最小”。

在对话中，女嘉宾吴敏霞提到：“一九九八年刚到国家队那会儿，我的年龄是最小的。”这句话直接说明她当时年龄最小，所以答案应该是B选项。其他选项比如A选项“目标远大”，虽然她后面提到有梦想和动力，但刚进队时她只是想着快点进步，并没有明确提到目标远大。C选项“常获得表扬”在对话中没有相关信息。D选项“跟不上训练进度”也不对，因为她只是说想跟上队伍，但并没有说跟不上。

所以正确选项...


[SAMPLE 3] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

女：今天我们非常荣幸地请到了中国体操队的总指导黄玉斌。黄指导曾经是优秀的体操运动员，现在又是一位“金牌教练”。您在结束了运动员生涯之后，就走上...
Reply excerpt  :
嗯，我现在要解决这个问题，题目是“在当教练之前，男的曾经做过什么？”选项是四个职业：裁判、解说员、运动员、体育老师。

首先，我需要仔细听对话内容。对话开始的时候，女主持人介绍黄玉斌是中国体操队的总指导，提到他曾经是优秀的体操运动员，现在成为金牌教练。然后她问，结束运动员生涯后走上教练岗位，是不是人生的转折。男的回应说他愿意当教练，利用专长，但首先要充实文化知识，因为年轻时训练和学习难以兼顾，退役后努力学习文化和训练方法。这些知识对他后来的教学很重要。

从这里可以看出，男的在当教练之前是运动员，因为对话直接提到他“结束运动员生涯之后”成为...
```

**Senario2**

```
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 deepseek_benchmark_chat_vshow.py \
        --scenario analysis \
        --concurrency 300 \
        --data_file external_dialogue_comprehension.json \
        --url http://172.167.140.16:30000/v1/chat/completions

==== DeepSeek‑R1 Benchmark ====
Scenario        : analysis
Completed req   : 300
TTFT ms         : avg=1055.4 | p50=1106.2 | p90=1116.6 | p99=1120.6
Total tokens/s  : 2351.2

--- Random 3 samples ---

[SAMPLE 1] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

男：大家好!我们今天请到的嘉宾是一位漂亮的幼儿教师，网友们都亲切地叫她“幼教美眉”，同时她也是中国红十字会“中国重症儿童爱心天使”。幼教美眉，...
Reply excerpt  :
好的，我现在需要解决这个问题。首先，仔细阅读对话内容，然后分析问题，找出正确的选项。

题目是问女的在做爱心天使之后要做的工作，正确的选项是哪一个。选项包括A照顾病童，B建捐款网站，C为病童捐款，D为病童募捐。

先回忆对话内容。女嘉宾在回答担任爱心天使后的工作时提到，她会在播客网、搜狐网等网站设立爱心专区。进入专区后可以直接捐款，也可以上传需要帮助孩子的资料，让大家了解情况，这样更多孩子可以得到帮助。她还说现在已经有一些白血病孩子的信息和照片，网友可以开始捐款。同时，她还提到会利用业余时间呼吁经济帮助，并多和孩子交流。

这里的关键点是，她并没有直接说建网站，而是设立爱心专区。可能B选项中的“建捐款网站”是否准确？或者设立专区属于建立网站的一部分？不过选项B的说法可能不完全准确，因为设立专区可能是在现有网站上创建页面，而不是新建一个网站。但她的主要工作是设立专区来收集信息和捐款，所以可能...


[SAMPLE 2] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

女：各位网友好!今天我们非常荣幸地请到了深受大家崇拜的新东方教育科技集团董事长俞敏洪老师做客人民网。俞老师，您先和大家打个招呼吧。
男：各位朋...
Reply excerpt  :
好，我现在需要仔细分析对话内容，找出问题的答案。问题是：男的认为创业中最应该积累的东西是什么？选项是A到D四个选项。

首先，回顾对话中男的回答部分。当被问到“对于走在不同行业创业路上的人来说，您觉得我们最应该积累的东西是什么？”时，男的回答说：“我觉得在创业路上要积累的就是整体的成熟度，处理问题的能力、眼光、方法和技巧。” 这里他明确提到处理问题的能力、眼光、方法和技巧，这些都属于处理问题的技巧，所以可能对应选项D。

不过接下来他继续提到创业最忌讳的是心情急躁、心胸狭窄、不能吃亏等，这些需要人品人格的重新铸造和提升。最后他强调，“只有个人全面发展了，整个事业才会伴随你发展”，这可能指向选项C人的全面发展。这里需要确定他重点强调的是处理问题的技巧还是个人的全面发展。

再看问题中的“最应该积累”，男的提到“整体的成熟度，处理问题的能力、眼光、方法和技巧”是积累的对象，而后面提到的“个人的...


[SAMPLE 3] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

女：柳教授，您看我今天特地请您这个大专家来，其实是因为我给我儿子的发展制定了一个宏伟的目标。您看，现在我儿子是十个月，我已经在家里门框上贴一个...
Reply excerpt  :
嗯，我现在需要仔细看看这段对话，然后回答问题。对话是女的和柳教授讨论孩子的早期教育问题。女的希望孩子从小就学习很多知识，比如认字、唐诗、英语、钢琴，而柳教授反对这种做法，认为应该遵循自然法则，前六年不需要学特别的知识。

女的最后提到莫扎特，问如果他没学过钢琴，能否成为大师。柳教授可能会接着这个话题讨论，比如解释莫扎特的例子，或者进一步说明早期教育的时间点。看选项的话，选项C是儿童什么时候开始学习，选项D是何时教知识，而问题问的是接下来会谈的问题。前面柳教授已经说了头六年不需要学知识，女的可能接着问什么时候开始学，或者反驳莫扎特是否从小学习。但莫扎特的问题可能引出学习开始的时间，比如虽然莫扎特小时候学琴，但可能说明某些情况下早期教育有效，或者柳教授会解释即使莫扎特学过，但每个孩子情况不同，应该何时开始学习。或者女的可能继续问什么时候该开始教知识，比如钢琴学习的最佳年龄，所以选项C和D都有可...
```

**Senario3:**

```
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 deepseek_benchmark_chat_vshow.py \
        --scenario reasoning \
        --concurrency 300 \
        --data_file external_dialogue_comprehension.json \
        --url http://172.167.140.16:30000/v1/chat/completions

==== DeepSeek‑R1 Benchmark ====
Scenario        : reasoning
Completed req   : 300
TTFT ms         : avg=1075.9 | p50=1119.9 | p90=1129.6 | p99=1132.3
Total tokens/s  : 1652.3

--- Random 3 samples ---

[SAMPLE 1] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

男：小王，其他人中午都回去了吗?
女：没有，他们应该上街逛去了。
男：为什么不在办公室里休息休息?下午的精神也足些呀。
女：(笑)因为你经常在...
Reply excerpt  :
哦，这个问题我得仔细看看。对话里男老板和女员工在讨论为什么其他员工不愿意被老板叫去帮别人做事。女员工解释说，主要是因为那些工作不是他们分内的，做好了没功劳，做不好还要担责任。而且老板也没表扬过他们，所以他们心里不愿意。

首先看选项，C选项是“不是自己分内的事情”，D选项是“做不好责任是自己的”。女员工提到这两点，但问题问的是主要原因。对话里她反复强调不是分内的事，而且责任问题也是因为不属于分内。比如她说“工作本身不是他们分内的……责任就是他们自己的”，还有“有过无功的前提下”不愿意。所以可能这两个选项都有道理。但题目可能选更直接的选项。

再仔细看问题，选项C和D都是原因的一部分。女员工说，因为不是分内的，所以做好了不算成绩，做不好要自己负责。所以这两个原因其实是相关联的。但问题需要选择员工不喜欢的主要原因。女员工在对话中多次强调“分内”这一点，比如直接说“就因为一点，这工作本身不是他们...


[SAMPLE 2] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

女：你好，赵总经理!很高兴您能抽出时间接受我们的访谈。首先请您简单地介绍一下您的职业。
男：我现在是一个网络技术公司的总经理。但是有些不好意思...
Reply excerpt  :
嗯，我现在要解决这个问题，进入互联网行业应具备的能力，哪一项男的没有提到。题目选项是A到D，分别是兴趣、技术、冒险精神、学习能力。

首先，我需要仔细看看对话中男的回答部分。问题是在关于进入互联网行业需要哪些能力的时候，男的提到了哪些点。根据对话内容，男的被问到这个问题时，回答说：

首先，要对这份工作感兴趣，没有兴趣什么都做不好。所以A选项兴趣是提到的。

其次，相关的技术技能是必需的，这里对应B选项技术，所以B也提到了。然后他说，不必太过专业，因为平时工作是在不断学习。这里可能涉及到学习能力吗？不过他说的是工作中会不断学习，所以可能D选项学习能力是否被提到？

接下来，他认为必须要有冒险精神，对应C选项冒险精神，提到了。另外还提到要有奇思妙想，非常规策略。这可能属于冒险精神的一部分？

问题在于选项中是否有他没提到的。问题问的是哪个没有提到。所以D选项学习能力是否被明确提到？

男的说...


[SAMPLE 3] Prompt excerpt:
你是一位助理，需要阅读一段对话并回答随后的选择题。只输出最终答案对应的文字，不要输出多余内容。

女：唐师傅，您好!非常感谢您来做这次节目。首先，我想问问您当时为何丢下女儿和三轮车转身走了呢?
男：其实当时真的是吓着了，早上用5角钱给英英买...
Reply excerpt  :
嗯，我现在需要仔细看看这段对话，然后回答问题。问题是问哪一个不是男的不去申请低保的原因。选项是四个，A到D。首先我得找到对话中关于申请低保的部分。

女问男为什么不去申请低保，男的回答说：“不去申请主要是太麻烦了，据说还要去找熟人才行。再说别人说起你靠低保过日子，不仅面子上过不去，就连心里也咽不下这口气呀。”这里提到了三个原因吗？

首先，男的说的第一点是“太麻烦了”，这对应选项A。然后他说“还要去找熟人”，也就是需要找熟人，对应选项B。接下来是“再说别人说起你靠低保……面子过不去……咽不下这口气”，这里的“面子过不去”应该对应C选项“觉得丢人”，“咽不下这口气”对应D选项“受不了别人的气”。所以男的说他三个原因：太麻烦、需要找熟人、觉得丢人和受不了气。所以问题问的是哪一个不是原因。题目选项里，这四个选项中哪一个没被提到？

题目选项中的四个选项分别是A、B、C、D。根据对话，男的说三个原...
```

## For Qwen 72B 671B on Azure MI300X

```
FROM rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410

# 1. 依赖
RUN python -m pip install --upgrade pip && \
    python -m pip uninstall -y vllm && \
    python -m pip install numpy wheel ninja cmake packaging pyyaml==6.0.1

# 2. 源码装 vLLM main  (显式告诉脚本走 ROCm)
RUN export FORCE_ROCM=1 ROCM_HOME=/opt/rocm && \
    python -m pip install --no-build-isolation \
        "vllm @ git+https://github.com/vllm-project/vllm.git@main"
```

```
docker build -t vllm:rocm6.3.1_v1 .
```

```
root@gbb-ea-vm-uksouth-mi300x-b-01:~# docker build -t vllm:rocm6.3.1_v1 .
[+] Building 823.5s (7/7) FINISHED                                                                       docker:default
 => [internal] load build definition from Dockerfile                                                               0.0s
 => => transferring dockerfile: 486B                                                                               0.0s
 => [internal] load metadata for docker.io/rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410                         0.0s
 => [internal] load .dockerignore                                                                                  0.0s
 => => transferring context: 2B                                                                                    0.0s
 => CACHED [1/3] FROM docker.io/rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410                                    0.0s
 => [2/3] RUN python -m pip install --upgrade pip &&     python -m pip uninstall -y vllm &&     python -m pip ins  2.9s
 => [3/3] RUN export FORCE_ROCM=1 ROCM_HOME=/opt/rocm &&     python -m pip install --no-build-isolation          815.9s
 => exporting to image                                                                                             4.6s
 => => exporting layers                                                                                            4.6s
 => => writing image sha256:73231ec7381780ddd0965eaed7a7f62c245a4303296a4d461aa863f35875d47e                       0.0s
 => => naming to docker.io/library/vllm:rocm6.3.1_v1                                                               0.0s
root@gbb-ea-vm-uksouth-mi300x-b-01:~#
```

```
export VLLM_USE_V1=1
```

```
docker rm -f qwen72b_v1 2>/dev/null

docker run -d --name qwen72b_v1 --device=/dev/kfd --device=/dev/dri --privileged \
  --security-opt seccomp=unconfined --cap-add SYS_PTRACE \
  -p 8080:8080 \
  -v /mnt/resource_nvme:/mnt/resource_nvme \
  -e HF_HOME=/mnt/resource_nvme/hf_cache \
  -e HSA_NO_SCRATCH_RECLAIM=1 \
  -e VLLM_USE_V1=1 \
  -e FLASH_ATTENTION_FORCE_TRITON=1 \
  vllm:rocm6.3.1_v1 \
  bash -lc "python -m vllm.entrypoints.openai.api_server \
      --model Qwen/Qwen2.5-72B-Instruct \
      --dtype bfloat16 \
      --tensor-parallel-size 8 \
      --gpu-memory-utilization 0.7 \
      --port 8080 --host 0.0.0.0 \
      --trust-remote-code"
```

```
docker logs -f qwen72b_v1 | **grep** "V1 LLM engine"

Initializing a V1 LLM engine (flash‑attn‑rocm)
```





```

```



==成功测试==================

```
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen‑2.5‑72B‑Instruct benchmark (专用数据集版本)
数据文件: external_dialogue_comprehension_Qwen2.5-72B-Instruct.json
"""

import argparse, asyncio, aiohttp, json, random, statistics, time
from pathlib import Path
from collections import defaultdict
from transformers import AutoTokenizer

MODEL_ID = "Qwen/Qwen2.5-72B-Instruct"
SCENARIOS = {
    "focused":   ((256, 512),  ( 50, 150)),
    "analysis":  ((512, 1024), (150, 500)),
    "reasoning": ((256, 512),  (1024, 1024)),
}
DEFAULT_URL, DEFAULT_CONCURRENCY = "http://localhost:8080/v1/chat/completions", 300
TOKENIZER = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

# -------- load buckets (dict 结构专用) --------
def load_buckets(path: Path):
    obj = json.loads(path.read_text())
    buckets = defaultdict(list)
    for meta in obj.values():                           # key = "0","1",...
        prompt = "".join(seg["prompt"] for seg in meta["origin_prompt"])
        ptok   = len(TOKENIZER.encode(prompt, add_special_tokens=False))
        for name, (rng, _) in SCENARIOS.items():
            if rng[0] <= ptok <= rng[1]:
                buckets[name].append(prompt)
                break
    return buckets

# -------- metrics --------
class Metrics:
    def __init__(self):
        self.ttft, self.tok, self.samples, self.fail = [], 0, [], 0
    async def ok(self, ttft, ctok, pr, rep):
        self.ttft.append(ttft); self.tok += ctok
        if len(self.samples) < 3:
            self.samples.append((pr, rep))
        else:
            i = random.randint(0, len(self.ttft))
            if i < 3: self.samples[i] = (pr, rep)

# -------- single request --------
async def call_one(sess, url, prompt, cmax, m: Metrics):
    payload = {
        "model": MODEL_ID,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": cmax,
        "temperature": 0.0
    }
    st = time.perf_counter(); first=None; ct=0; rep=[]
    try:
        async with sess.post(url, json=payload, timeout=900) as resp:
            async for line in resp.content:
                if not line.startswith(b"data:"): continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    if first:
                        await m.ok((first-st)*1000, ct, prompt, "".join(rep))
                    return
                try:
                    j = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if "choices" not in j:         # error 行
                    continue
                ch = j["choices"][0]
                delta = ch.get("delta", {})
                if delta.get("content"):
                    if first is None: first = time.perf_counter()
                    ct += 1; rep.append(delta["content"])
                if ch.get("finish_reason"):
                    if first:
                        await m.ok((first-st)*1000, ct, prompt, "".join(rep))
                    return
    except Exception:
        m.fail += 1

# -------- main --------
async def main(a):
    buckets = load_buckets(Path(a.data_file))
    if a.scenario == "reasoning" and not buckets["reasoning"]:
        buckets["reasoning"] = buckets["focused"][:]

    pool = buckets[a.scenario]
    assert pool, "No prompt in this bucket"
    prompts = random.choices(pool, k=a.concurrency)
    cmax = SCENARIOS[a.scenario][1][1]

    m = Metrics()
    connector = aiohttp.TCPConnector(limit=a.concurrency)
    t0 = time.perf_counter()
    async with aiohttp.ClientSession(connector=connector) as s:
        await asyncio.gather(*(call_one(s, a.url, p, cmax, m) for p in prompts))
    wall = time.perf_counter() - t0
    n = len(m.ttft)
    if n == 0:
        print("all requests failed"); return

    pct = lambda arr, p: (statistics.quantiles(arr, n=100)[p-1]
                          if len(arr) >= 2 else float("nan"))
    print("\n===== Qwen 72B =====")
    print(f"Scenario : {a.scenario} | Completed : {n} | Failed : {m.fail}")
    print(f"TTFT ms  : avg={sum(m.ttft)/n:.1f} | "
          f"p50={pct(m.ttft,50):.1f} | p90={pct(m.ttft,90):.1f} | "
          f"p99={pct(m.ttft,99):.1f}")
    print(f"Tok/s    : {m.tok / wall:.1f}")
    print("--- Samples ---")
    for i, (pr, rep) in enumerate(m.samples, 1):
        print(f"[{i}] {pr[:80]} ... -> {rep[:120]} ...")

# -------- CLI --------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_file",
        default="external_dialogue_comprehension_Qwen2.5-72B-Instruct.json")
    ap.add_argument("--scenario", choices=SCENARIOS, required=True)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--url", default=DEFAULT_URL)
    asyncio.run(main(ap.parse_args()))
```



```
docker run -d --name qwen72b_8x --device=/dev/kfd --device=/dev/dri --privileged --security-opt seccomp=unconfined --cap-add SYS_PTRACE -p 8080:8080 -v /mnt/resource_nvme:/mnt/resource_nvme -e HF_HOME=/mnt/resource_nvme/hf_cache -e HSA_NO_SCRATCH_RECLAIM=1 rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410 python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-72B-Instruct --dtype bfloat16 --tensor-parallel-size 8 --max-num-batched-tokens 60000 --tokenizer-pool-size 8 --tokenizer-pool-type ray --swap-space 4 --gpu-memory-utilization 0.9 --port 8080 --host 0.0.0.0 --trust-remote-code


```



```
python3 qwen_benchmark_8080.py --scenario focused   --concurrency 300
python3 qwen_benchmark_8080.py --scenario analysis  --concurrency 300
python3 qwen_benchmark_8080.py --scenario reasoning --concurrency 300
```



```
```



```
===== Qwen 72B =====
Scenario : focused | Completed : 300 | Failed : 0
TTFT ms  : avg=11102.9 | p50=9924.8 | p90=15128.6 | p99=15138.0
Tok/s    : 134.5
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"小丽的学校不太好"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"李老师"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> Answer:{"answer":"女的的妹妹"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario focused --concurrency 300 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : focused | Completed : 300 | Failed : 0
TTFT ms  : avg=9841.3 | p50=9659.1 | p90=12032.5 | p99=12042.9
Tok/s    : 166.4
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"男的买了一辆汽车"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"需要加点儿醋"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"北京"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario focused --concurrency 300 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : focused | Completed : 300 | Failed : 0
TTFT ms  : avg=8048.3 | p50=6514.9 | p90=11964.6 | p99=11974.0
Tok/s    : 168.9
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"聚会"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"气候变化"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> Answer:{"answer":"司机"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario focused --concurrency 100 --data_file ex
ternal_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : focused | Completed : 100 | Failed : 0
TTFT ms  : avg=4126.4 | p50=3904.1 | p90=4602.5 | p99=4604.2
Tok/s    : 141.7
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"她妈妈对花粉过敏"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"一楼"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"收入不高"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario focused --concurrency 100 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : focused | Completed : 100 | Failed : 0
TTFT ms  : avg=6237.1 | p50=6128.0 | p90=6605.1 | p99=6607.5
Tok/s    : 100.8
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"机场"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"嫉妒"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"质量不好"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario focused --concurrency 50 --data_file ext
ernal_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : focused | Completed : 50 | Failed : 0
TTFT ms  : avg=5175.7 | p50=5127.1 | p90=5349.7 | p99=5350.6
Tok/s    : 63.9
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"丢钱包了"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"很好"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"系统的训练"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario focused --concurrency 5 --data_file exte
rnal_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : focused | Completed : 5 | Failed : 0
TTFT ms  : avg=2161.0 | p50=2161.0 | p90=2161.6 | p99=2161.8
Tok/s    : 16.9
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"没钱"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"有了女儿"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"挫折对他不见得是坏事"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario focused --concurrency 1 --data_file exte
rnal_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : focused | Completed : 1 | Failed : 0
TTFT ms  : avg=2086.7 | p50=nan | p90=nan | p99=nan
Tok/s    : 2.8
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"解说员"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario analysis --concurrency 300 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : analysis | Completed : 300 | Failed : 0
TTFT ms  : avg=15427.6 | p50=15263.0 | p90=23528.2 | p99=24357.6
Tok/s    : 92.2
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"有社会责任感"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"脚踏实地做事"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"开始回到自己的国家"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario analysis --concurrency 300 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : analysis | Completed : 300 | Failed : 0
TTFT ms  : avg=9942.5 | p50=8526.9 | p90=16275.9 | p99=16957.1
Tok/s    : 130.1
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"树立了不服输的信念"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"戴普通眼镜"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"奶奶"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario analysis --concurrency 300 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : analysis | Completed : 300 | Failed : 0
TTFT ms  : avg=10097.7 | p50=7943.7 | p90=15666.6 | p99=16398.8
Tok/s    : 136.4
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"对理想要非常坚定"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"当志愿者"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"休息"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario analysis --concurrency 100 --data_file e
xternal_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : analysis | Completed : 100 | Failed : 0
TTFT ms  : avg=5740.0 | p50=5220.6 | p90=6667.7 | p99=6670.2
Tok/s    : 104.5
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"东部沿海地区"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"独立自主"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"与当地政府的关系"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario analysis --concurrency 100 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : analysis | Completed : 100 | Failed : 0
TTFT ms  : avg=3722.3 | p50=3228.6 | p90=4643.6 | p99=4645.8
Tok/s    : 155.8
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"发动机"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"茶的文化科学"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"深圳资金来源丰富，潜力很大"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario analysis --concurrency 50 --data_file ex
ternal_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : analysis | Completed : 50 | Failed : 0
TTFT ms  : avg=3896.4 | p50=3581.1 | p90=4371.8 | p99=4373.1
Tok/s    : 78.6
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"游戏部门"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"受到其他媒介的冲击"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"推广精神快乐"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario analysis --concurrency 10 --data_file ex
ternal_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : analysis | Completed : 10 | Failed : 0
TTFT ms  : avg=2531.9 | p50=2531.8 | p90=2621.4 | p99=2622.0
Tok/s    : 25.6
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"树立了不服输的信念"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"兴趣爱好"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"无法超越自己时"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario reasoning --concurrency 300 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : reasoning | Completed : 300 | Failed : 0
TTFT ms  : avg=5768.2 | p50=4531.0 | p90=7967.6 | p99=7978.7
Tok/s    : 253.7
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> Answer:{"answer":"邻居"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"参加聚会"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> Answer:{"answer":"同事"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario reasoning --concurrency 300 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : reasoning | Completed : 300 | Failed : 0
TTFT ms  : avg=8075.8 | p50=6537.7 | p90=11983.6 | p99=11994.3
Tok/s    : 168.7
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"下星期"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"办公室"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> Answer:{"answer":"邻居"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~# python3 qwen_benchmark_8080.py --scenario reasoning --concurrency 300 --data_file external_dialogue_comprehension_Qwen2.5-72B-Instruct.json --url http://localhost:8080/v1/chat/completions

===== Qwen 72B =====
Scenario : reasoning | Completed : 300 | Failed : 0
TTFT ms  : avg=5981.3 | p50=5004.6 | p90=10054.1 | p99=10062.5
Tok/s    : 198.1
--- Samples ---
[1]
Based on your understanding of the following text, please respond in JSON forma ... -> Answer:{"answer":"公共汽车上"} ...
[2]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"运动"} ...
[3]
Based on your understanding of the following text, please respond in JSON forma ... -> {"answer":"衬衫"} ...
root@gbb-ea-vm-uksouth-mi300x-b-01:~#
```





## Use evalscope

```
evalscope perf --url http://localhost:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --api openai --stream --parallel 300 --number 2000 --dataset "longalpaca"  --min-prompt-length 256 --min-tokens 50 --max-tokens 150

evalscope perf --url http://localhost:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --api openai --stream --parallel 300 --number 400 --dataset "longalpaca" --min-prompt-length 512 --min-tokens 150 --max-tokens 500

evalscope perf --url http://localhost:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --api openai --stream --parallel 300 --number 400 --dataset "longalpaca" --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024
```





```
evalscope perf --url http://localhost:8080/v1/chat/completions --model "Qwen/Qwen2.5-72B-Instruct" --api openai --stream --parallel 300 --number 2000 --dataset "longalpaca" --min-prompt-length 256 --min-tokens 50 --max-tokens 150
evalscope perf --url http://localhost:8080/v1/chat/completions --model "Qwen/Qwen2.5-72B-Instruct" --api openai --stream --parallel 300 --number 2000 --dataset "longalpaca" --min-prompt-length 512 --min-tokens 150 --max-tokens 500
evalscope perf --url http://localhost:8080/v1/chat/completions --model "Qwen/Qwen2.5-72B-Instruct" --api openai --stream --parallel 300 --number 2000 --dataset longalpaca --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024
```







```
Benchmarking summary:
+-----------------------------------+-------------------------------------------------------+
| Key                               | Value                                                 |
+===================================+=======================================================+
| Time taken for tests (s)          | 1908.7585                                             |
+-----------------------------------+-------------------------------------------------------+
| Number of concurrency             | 300                                                   |
+-----------------------------------+-------------------------------------------------------+
| Total requests                    | 2000                                                  |
+-----------------------------------+-------------------------------------------------------+
| Succeed requests                  | 2000                                                  |
+-----------------------------------+-------------------------------------------------------+
| Failed requests                   | 0                                                     |
+-----------------------------------+-------------------------------------------------------+
| Output token throughput (tok/s)   | 157.1702                                              |
+-----------------------------------+-------------------------------------------------------+
| Total token throughput (tok/s)    | 8428.545                                              |
+-----------------------------------+-------------------------------------------------------+
| Request throughput (req/s)        | 1.0478                                                |
+-----------------------------------+-------------------------------------------------------+
| Average latency (s)               | 261.8574                                              |
+-----------------------------------+-------------------------------------------------------+
| Average time to first token (s)   | 192.1444                                              |
+-----------------------------------+-------------------------------------------------------+
| Average time per output token (s) | 0.4648                                                |
+-----------------------------------+-------------------------------------------------------+
| Average input tokens per request  | 7894.0285                                             |
+-----------------------------------+-------------------------------------------------------+
| Average output tokens per request | 150.0                                                 |
+-----------------------------------+-------------------------------------------------------+
| Average package latency (s)       | 0.4647                                                |
+-----------------------------------+-------------------------------------------------------+
| Average package per request       | 150.003                                               |
+-----------------------------------+-------------------------------------------------------+
| Expected number of requests       | 2000                                                  |
+-----------------------------------+-------------------------------------------------------+
| Result DB path                    | outputs/20250502_155121/DeepSeek-R1/benchmark_data.db |
+-----------------------------------+-------------------------------------------------------+
2025-05-02 16:23:50,294 - evalscope - INFO -
Percentile results:
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 125.2711 | 0.0611  |  0.1415  |  239.5102   |     6220     |      150      |          0.435           |         22.6209         |
|    25%     | 147.5032 | 0.0666  |  0.2565  |  240.2333   |     6661     |      150      |          0.5193          |         26.9221         |
|    50%     | 185.1756 | 0.0709  |  0.4476  |  240.7587   |     7195     |      150      |          0.623           |         29.8891         |
|    66%     | 208.934  | 0.0726  |  0.5645  |  241.9315   |     7583     |      150      |          0.6243          |         31.8673         |
|    75%     | 221.5459 | 0.0737  |  0.6394  |  288.8619   |     7854     |      150      |          0.6244          |         33.3623         |
|    80%     | 229.0159 | 0.0744  |  0.6823  |  321.1012   |     8040     |      150      |          0.6255          |         34.6574         |
|    90%     | 298.5819 | 0.0787  |  0.7653  |  344.8243   |    12765     |      150      |          0.6263          |         48.7416         |
|    95%     | 346.7225 | 0.0828  |  0.8836  |  434.1349   |    14279     |      150      |          1.2317          |         57.478          |
|    98%     | 380.0461 | 0.1565  |  1.158   |  474.2577   |    15300     |      150      |          1.2319          |         64.6744         |
|    99%     | 392.8557 | 0.8745  |  1.2514  |  490.0534   |    15812     |      150      |          1.232           |         66.9624         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```



```
Benchmarking summary:
+-----------------------------------+-------------------------------------------------------+
| Key                               | Value                                                 |
+===================================+=======================================================+
| Time taken for tests (s)          | 396.5486                                              |
+-----------------------------------+-------------------------------------------------------+
| Number of concurrency             | 300                                                   |
+-----------------------------------+-------------------------------------------------------+
| Total requests                    | 400                                                   |
+-----------------------------------+-------------------------------------------------------+
| Succeed requests                  | 400                                                   |
+-----------------------------------+-------------------------------------------------------+
| Failed requests                   | 0                                                     |
+-----------------------------------+-------------------------------------------------------+
| Output token throughput (tok/s)   | 504.1274                                              |
+-----------------------------------+-------------------------------------------------------+
| Total token throughput (tok/s)    | 7704.4835                                             |
+-----------------------------------+-------------------------------------------------------+
| Request throughput (req/s)        | 1.0087                                                |
+-----------------------------------+-------------------------------------------------------+
| Average latency (s)               | 228.0638                                              |
+-----------------------------------+-------------------------------------------------------+
| Average time to first token (s)   | 145.5601                                              |
+-----------------------------------+-------------------------------------------------------+
| Average time per output token (s) | 0.1651                                                |
+-----------------------------------+-------------------------------------------------------+
| Average input tokens per request  | 7138.2275                                             |
+-----------------------------------+-------------------------------------------------------+
| Average output tokens per request | 499.7775                                              |
+-----------------------------------+-------------------------------------------------------+
| Average package latency (s)       | 0.1651                                                |
+-----------------------------------+-------------------------------------------------------+
| Average package per request       | 499.785                                               |
+-----------------------------------+-------------------------------------------------------+
| Expected number of requests       | 400                                                   |
+-----------------------------------+-------------------------------------------------------+
| Result DB path                    | outputs/20250502_162645/DeepSeek-R1/benchmark_data.db |
+-----------------------------------+-------------------------------------------------------+
2025-05-02 16:33:56,913 - evalscope - INFO -
Percentile results:
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 33.4355  | 0.0603  |  0.0831  |   142.122   |     6180     |      500      |          1.7833          |         24.8043         |
|    25%     | 77.9315  | 0.0622  |  0.1128  |  142.1716   |     6615     |      500      |          1.7837          |         27.1727         |
|    50%     | 167.9003 | 0.0656  |  0.1618  |  254.3657   |     7090     |      500      |          1.9657          |         30.6316         |
|    66%     | 191.4027 | 0.0672  |  0.1941  |  280.3073   |     7445     |      500      |          3.5165          |         44.7478         |
|    75%     | 204.3268 | 0.0699  |  0.2123  |  280.3209   |     7642     |      500      |          3.5169          |         50.4143         |
|    80%     | 211.4103 | 0.0718  |  0.2236  |  280.3322   |     7776     |      500      |          3.5177          |         52.0564         |
|    90%     | 225.9042 | 0.0734  |  0.2481  |  280.3818   |     8025     |      500      |          3.5181          |         57.0637         |
|    95%     | 241.6131 | 0.0745  |  0.2617  |  280.3932   |     8249     |      500      |          3.5183          |         58.5389         |
|    98%     | 283.4446 | 0.0763  |  0.2732  |  396.4733   |     8749     |      500      |          3.5184          |         61.139          |
|    99%     | 285.9595 | 0.0812  |  0.2758  |  396.4834   |     9038     |      500      |          3.5186          |         64.8766         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```



```
2025-05-02 16:46:30,910 - evalscope - INFO -                                                                                                                                        Benchmarking summary:                                                                                                                                                               +-----------------------------------+-------------------------------------------------------+                                                                                       | Key                               | Value                                                 |                                                                                       +===================================+=======================================================+                                                                                       | Time taken for tests (s)          | 510.2013                                              |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Number of concurrency             | 300                                                   |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Total requests                    | 400                                                   |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Succeed requests                  | 400                                                   |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Failed requests                   | 0                                                     |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Output token throughput (tok/s)   | 802.8203                                              |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Total token throughput (tok/s)    | 6399.2207                                             |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Request throughput (req/s)        | 0.784                                                 |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Average latency (s)               | 296.915                                               |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Average time to first token (s)   | 177.9161                                              |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Average time per output token (s) | 0.1162                                                |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Average input tokens per request  | 7138.2275                                             |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Average output tokens per request | 1024.0                                                |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Average package latency (s)       | 0.1162                                                |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Average package per request       | 1024.0125                                             |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Expected number of requests       | 400                                                   |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       | Result DB path                    | outputs/20250502_163726/DeepSeek-R1/benchmark_data.db |                                                                                       +-----------------------------------+-------------------------------------------------------+                                                                                       2025-05-02 16:46:31,084 - evalscope - INFO -                                                                                                                                        Percentile results:                                                                                                                                                                 +------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+                                    | Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |                                    +------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+                                    |    10%     | 37.6685  | 0.0636  |  0.0753  |  175.6955   |     6180     |     1024      |          2.9991          |         20.3847         |                                    |    25%     | 81.5646  | 0.0651  |  0.0895  |  175.7176   |     6615     |     1024      |          2.9999          |         22.7964         |                                    |    50%     | 207.0302 | 0.0667  |  0.1139  |  334.4339   |     7090     |     1024      |          3.0619          |         25.472          |                                    |    66%     | 230.9126 | 0.0678  |  0.1293  |  341.3319   |     7445     |     1024      |          3.0623          |         32.6671         |                                    |    75%     | 244.6862 | 0.0686  |  0.1375  |  341.3469   |     7642     |     1024      |          5.8275          |         43.3419         |                                    |    80%     | 251.8305 |  0.069  |  0.1439  |  341.4147   |     7776     |     1024      |          5.8278          |         44.8389         |                                    |    90%     | 266.3631 | 0.0701  |  0.155   |  341.4345   |     8025     |     1024      |          5.8283          |         48.1986         |                                    |    95%     | 348.8776 | 0.0712  |  0.1592  |  510.2014   |     8249     |     1024      |          5.8285          |         50.6913         |                                    |    98%     | 356.9199 | 0.0728  |  0.1634  |  510.2079   |     8749     |     1024      |          5.8287          |         52.4331         |                                    |    99%     | 359.9374 | 0.0746  |  0.2555  |  510.2104   |     9038     |     1024      |          5.8288          |         55.3024         |                                    +------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```



Processing: 100%|███████████████████████████████████████████████████████████████████| 2000/2000 [30:10<00:00,  1.10it/s]
2025-05-02 13:00:58,600 - evalscope - INFO -

```
Benchmarking summary:
+-----------------------------------+----------------------------------------------------------------+
| Key                               | Value                                                          |
+===================================+================================================================+
| Time taken for tests (s)          | 1810.7969                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Number of concurrency             | 300                                                            |
+-----------------------------------+----------------------------------------------------------------+
| Total requests                    | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Succeed requests                  | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Failed requests                   | 0                                                              |
+-----------------------------------+----------------------------------------------------------------+
| Output token throughput (tok/s)   | 165.2129                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Total token throughput (tok/s)    | 9190.5007                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Request throughput (req/s)        | 1.1045                                                         |
+-----------------------------------+----------------------------------------------------------------+
| Average latency (s)               | 260.9651                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Average time to first token (s)   | 128.1664                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Average time per output token (s) | 0.8881                                                         |
+-----------------------------------+----------------------------------------------------------------+
| Average input tokens per request  | 8171.4815                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Average output tokens per request | 149.5835                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Average package latency (s)       | 0.8878                                                         |
+-----------------------------------+----------------------------------------------------------------+
| Average package per request       | 149.5835                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Expected number of requests       | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Result DB path                    | outputs/20250502_122438/Qwen2.5-72B-Instruct/benchmark_data.db |
+-----------------------------------+----------------------------------------------------------------+
2025-05-02 13:00:58,766 - evalscope - INFO -
Percentile results:
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 50.0377  | 0.0829  |  0.3512  |  200.6691   |     6429     |      150      |          0.3611          |         17.9766         |
|    25%     | 74.7061  | 0.0847  |  0.5382  |  209.3805   |     6885     |      150      |          0.4958          |         29.1994         |
|    50%     | 123.0922 | 0.0871  |  0.8697  |   220.316   |     7435     |      150      |          0.6808          |         34.1403         |
|    66%     | 152.6436 | 0.0888  |  1.0786  |   228.496   |     7838     |      150      |          0.6983          |         36.5236         |
|    75%     | 170.2323 | 0.0907  |  1.2006  |   302.52    |     8121     |      150      |          0.7164          |         38.1459         |
|    80%     | 181.5637 | 0.1029  |  1.258   |  302.6109   |     8346     |      150      |          0.7295          |         39.3196         |
|    90%     |  223.22  | 0.5089  |  1.4175  |  415.0705   |    13155     |      150      |          0.7475          |         44.2413         |
|    95%     | 234.9383 |  2.125  |  1.6208  |  448.3035   |    14847     |      150      |          0.7476          |         54.0722         |
|    98%     | 265.0679 |  2.21   |  1.8875  |   530.326   |    15954     |      150      |          0.7478          |         64.6721         |
|    99%     | 301.6214 | 3.0639  |  1.9901  |  530.6473   |    16321     |      150      |          0.7478          |         67.3814         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```







```
Benchmarking summary:
+-----------------------------------+----------------------------------------------------------------+
| Key                               | Value                                                          |
+===================================+================================================================+
| Time taken for tests (s)          | 1575.5161                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Number of concurrency             | 300                                                            |
+-----------------------------------+----------------------------------------------------------------+
| Total requests                    | 1000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Succeed requests                  | 1000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Failed requests                   | 0                                                              |
+-----------------------------------+----------------------------------------------------------------+
| Output token throughput (tok/s)   | 258.3611                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Total token throughput (tok/s)    | 4937.1365                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Request throughput (req/s)        | 0.6347                                                         |
+-----------------------------------+----------------------------------------------------------------+
| Average latency (s)               | 465.8562                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Average time to first token (s)   | 96.5871                                                        |
+-----------------------------------+----------------------------------------------------------------+
| Average time per output token (s) | 0.9068                                                         |
+-----------------------------------+----------------------------------------------------------------+
| Average input tokens per request  | 7371.486                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Average output tokens per request | 407.052                                                        |
+-----------------------------------+----------------------------------------------------------------+
| Average package latency (s)       | 0.9072                                                         |
+-----------------------------------+----------------------------------------------------------------+
| Average package per request       | 407.052                                                        |
+-----------------------------------+----------------------------------------------------------------+
| Expected number of requests       | 1000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Result DB path                    | outputs/20250502_140130/Qwen2.5-72B-Instruct/benchmark_data.db |
+-----------------------------------+----------------------------------------------------------------+
2025-05-02 14:28:25,590 - evalscope - INFO -
Percentile results:
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 52.4965  | 0.0783  |   0.42   |  250.2315   |     6397     |      299      |          0.6767          |         11.6492         |
|    25%     | 78.0104  | 0.0859  |  0.7675  |  361.4854   |     6810     |      349      |          0.7509          |         13.5258         |
|    50%     | 87.7938  | 0.0905  |  0.9939  |  478.3213   |     7318     |      407      |          0.8811          |         16.3032         |
|    66%     | 93.5391  | 0.5942  |  1.0807  |  549.0423   |     7646     |      475      |          0.9031          |         18.908          |
|    75%     | 100.222  | 2.0894  |  1.118   |  556.7161   |     7868     |      500      |          0.9787          |         21.5699         |
|    80%     | 108.6323 | 2.1255  |  1.1366  |  587.2937   |     7995     |      500      |          1.0402          |         23.3121         |
|    90%     | 154.3641 |  2.195  |  1.1954  |  655.2437   |     8311     |      500      |          1.4314          |         30.8714         |
|    95%     | 184.9905 | 3.3221  |  1.2291  |   700.129   |     8586     |      500      |          2.0466          |         41.3329         |
|    98%     | 268.8557 | 3.8601  |  1.348   |  747.0711   |     9180     |      500      |          2.7861          |         51.4136         |
|    99%     | 295.0391 | 4.1128  |  1.4306  |   838.265   |     9631     |      500      |          3.3498          |         56.2532         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```











```
Benchmarking summary:
+-----------------------------------+----------------------------------------------------------------+
| Key                               | Value                                                          |
+===================================+================================================================+
| Time taken for tests (s)          | 2191.3567                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Number of concurrency             | 300                                                            |
+-----------------------------------+----------------------------------------------------------------+
| Total requests                    | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Succeed requests                  | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Failed requests                   | 0                                                              |
+-----------------------------------+----------------------------------------------------------------+
| Output token throughput (tok/s)   | 934.5808                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Total token throughput (tok/s)    | 8392.5007                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Request throughput (req/s)        | 0.9127                                                         |
+-----------------------------------+----------------------------------------------------------------+
| Average latency (s)               | 312.777                                                        |
+-----------------------------------+----------------------------------------------------------------+
| Average time to first token (s)   | 128.5064                                                       |
+-----------------------------------+----------------------------------------------------------------+
| Average time per output token (s) | 0.18                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Average input tokens per request  | 8171.4815                                                      |
+-----------------------------------+----------------------------------------------------------------+
| Average output tokens per request | 1024.0                                                         |
+-----------------------------------+----------------------------------------------------------------+
| Average package latency (s)       | 0.18                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Average package per request       | 1024.0                                                         |
+-----------------------------------+----------------------------------------------------------------+
| Expected number of requests       | 2000                                                           |
+-----------------------------------+----------------------------------------------------------------+
| Result DB path                    | outputs/20250502_144944/Qwen2.5-72B-Instruct/benchmark_data.db |
+-----------------------------------+----------------------------------------------------------------+
2025-05-02 15:27:04,805 - evalscope - INFO -
Percentile results:
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     | 41.3834  | 0.0871  |  0.1108  |  218.1732   |     6429     |     1024      |          2.2751          |         18.3404         |
|    25%     | 65.6466  | 0.0909  |  0.1343  |   221.82    |     6885     |     1024      |          2.5992          |         25.8683         |
|    50%     | 103.9827 | 0.0956  |  0.1726  |  280.8245   |     7435     |     1024      |          3.6464          |         33.5236         |
|    66%     | 132.7753 | 0.0984  |  0.1946  |  344.4832   |     7838     |     1024      |          4.6139          |         37.0172         |
|    75%     | 170.3912 | 0.1015  |  0.2084  |  393.9659   |     8121     |     1024      |          4.6164          |         38.6355         |
|    80%     | 206.7594 | 0.1038  |  0.2216  |  394.0702   |     8346     |     1024      |          4.6545          |         39.6021         |
|    90%     | 244.5239 |  0.117  |  0.261   |  450.0822   |    13155     |     1024      |          4.6935          |         41.9353         |
|    95%     | 300.2397 | 0.1237  |  0.3054  |  564.1507   |    14847     |     1024      |          4.6949          |         44.1926         |
|    98%     | 403.7368 | 0.1278  |  0.3406  |  738.5439   |    15954     |     1024      |          4.6959          |         46.9588         |
|    99%     | 431.8423 | 0.2345  |  0.3603  |  738.5612   |    16321     |     1024      |          4.6963          |         50.2519         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```































































Backup

