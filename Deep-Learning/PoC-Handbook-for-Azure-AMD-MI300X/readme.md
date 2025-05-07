## PoC Handbook for Azure AMD MI300X

This repository provides comprehensive guidance and resources for efficiently deploying, testing, and benchmarking cutting-edge open-source foundation models using Azure's latest ND MI300X GPU-enabled Virtual Machines.

The handbook is designed both as a quick-start guide and as an exhaustive handbook, empowering you to rapidly establish an optimized deployment environment, perform sophisticated inference tasks, conduct systematic performance evaluations, and maximize computational throughput on Azure ND MI300X.

Currently included models: 

- Qwen3-235B-A22B
- DeepSeek R1 671B
- Qwen2.5 72B

### Azure ND MI300X GPU VM Environment Setup

Quickly create a Spot VM, using Spot VM and password-based authentication:

```
az vm create --name <VMNAME> --resource-group <RESOURCE_GROUP_NAME> --location <REGION>  --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 256 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password <YOUR_PASSWORD> 

```

Taking the CLI command I used for creating VM as an example:

```
xinyu [ ~ ]$ az vm create --name mi300x-xinyu --resource-group amdrg --location westus --image microsoft-dsvm:ubuntu-hpc:2204-rocm:22.04.2025030701 --size Standard_ND96isr_MI300X_v5 --security-type Standard --priority Spot --max-price -1 --eviction-policy Deallocate --os-disk-size-gb 512 --os-disk-delete-option Delete --admin-username azureadmin --authentication-type password --admin-password azureadmin@123  


```
VM Deployment Steps:

```
Argument '--max-price' is in preview and under development. Reference and support levels: https://aka.ms/CLI_refstatus
Consider upgrading security for your workloads using Azure Trusted Launch VMs. To know more about Trusted Launch, please visit https://aka.ms/TrustedLaunch.
{
  "fqdns": "",
  "id": "/subscriptions/***/resourceGroups/amdrg/providers/Microsoft.Compute/virtualMachines/mi300x-xinyu",
  "location": "westus",
  "macAddress": "60-45-BD-01-4B-AF",
  "powerState": "VM running",
  "privateIpAddress": "10.0.0.4",
  "publicIpAddress": "13.64.8.207",
  "resourceGroup": "amdrg",
  "zones": ""
}
```

After the system is successfully deployed, open port 22 on the VM's NSG.

Then SSH into the VM and perform the following environment configuration steps.

For testing, use the local NVME temporary disk as the docker runtime environment. Note that after VM restart, data stored on the temporary disk will be lost. This approach is suitable for fast, low-cost testing scenarios. However, for production scenarios, a persistent file system should be used.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PoC-Handbook-for-Azure-AMD-MI300X/images/1.png)

```
mkdir -p /mnt/resource_nvme/
sudo mdadm --create /dev/md128 -f --run --level 0 --raid-devices 8 $(ls /dev/nvme*n1)  
sudo mkfs.xfs -f /dev/md128 
sudo mount /dev/md128 /mnt/resource_nvme 
sudo chmod 1777 /mnt/resource_nvme  
```

First, create a mount directory for RAID0:

```
mkdir –p /mnt/resource_nvme/hf_cache 
export HF_HOME=/mnt/resource_nvme/hf_cache 
```

Configure RAID0 and designate it for Docker usage.

```
mkdir -p /mnt/resource_nvme/docker 
sudo tee /etc/docker/daemon.json > /dev/null <<EOF 
{ 
    "data-root": "/mnt/resource_nvme/docker" 
} 
EOF 
sudo chmod 0644 /etc/docker/daemon.json 
sudo systemctl restart docker 
```

### Launch Qwen3-235B-A22B

Qwen3‑235B‑A22B is the flagship MoE model in the Qwen3 family:

• 235 B total parameters / 22 B activated parameters (Top‑2 gating)
• Native context length of 32 768 tokens, extendable to 131 072 with YaRN
• Supports “thinking mode / non‑thinking mode”
– When thinking mode is enabled, the model outputs the block
<think> … </think> before the final answer

| Dimension             | vLLM                                                | SGLang                       |
| --------------------- | --------------------------------------------------- | ---------------------------- |
| OpenAI‑compatible API | Yes (`/v1/chat/completions`)                        | Yes (`/v1/chat/completions`) |
| Reasoning parser      | `--enable-reasoning --reasoning-parser deepseek_r1` | `--reasoning-parser qwen3`   |

Next, I will demonstrate testing using the vLLM Docker image as an example.

```
docker run -d --name qwen3_A -p 8090:8090 \
  --device=/dev/kfd --device=/dev/dri --privileged \
  -v /mnt/resource_nvme:/mnt/resource_nvme -e HF_HOME=/mnt/resource_nvme/hf_cache \
  rocm/vllm:rocm6.3.1_instinct_vllm0.8.3_20250410 \
  python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-235B-A22B --tensor-parallel-size 8 --dtype bfloat16 \
    --max-model-len 32768 \
    --enable-reasoning --reasoning-parser deepseek_r1 \
    --max-num-batched-tokens 120000 \
    --max-num-seqs 512 \
    --tokenizer-pool-size 16 --tokenizer-pool-type ray \
    --gpu-memory-utilization 0.92 --swap-space 0 \
    --port 8090 --host 0.0.0.0 --trust-remote-code
```

I will use `curl` to perform testing requests against the model.

```
curl -s -w '\nTIME_NAMELOOKUP:%{time_namelookup}\nTIME_CONNECT:%{time_connect}\nTIME_STARTTRANSFER:%{time_starttransfer}\nTIME_TOTAL:%{time_total}\n' \
  http://localhost:8090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "Qwen/Qwen3-235B-A22B",
        "enable_thinking": true,
        "messages": [
          {
            "role": "system",
            "content": "You are a bilingual (Chinese + English) mathematical reasoning assistant. Explain every step and finish with a bilingual conclusion."
          },
          {
            "role": "user",
            "content": "【复杂概率 + 数论综合题 / Advanced Mixed‑Probability & Number‑Theory Problem】\\n\\n袋子 A 内有 4 个红球、4 个蓝球与 2 个绿球 (total 10)。袋子 B 内有 6 个红球、3 个蓝球与 1 个绿球 (total 10)。\\nStep 1：先从袋子 A 随机取出 2 个球并放入袋子 B；\\nStep 2：再从现在的袋子 B (此时共 12 球) 随机取出 3 个球，不放回。\\n\\nQ1 求 Step 2 抽到“恰好 2 个蓝球且 1 个红球”的概率。\\nQ2 若把 Step 2 的 3 个球颜色按 (R=2, B=1) 记作三位数 RRL —— 用颜色编号 (R=1, B=2, G=3) 组成十进制数 —— 问该数能否被 3 整除？请说明理由，并给出一般判别法。\\n\\n要求：① 全程中英双语逐步推理；② 用组合数或条件概率公式写出每一步；③ 最后分别用中英文各 1 句话总结。"
          }
        ],
        "max_tokens": 8192,
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 20,
        "stream": false
      }'
```

Result:

```
{"id":"chatcmpl-98d45687e3ff48368f680773e9ec4375","object":"chat.completion","created":1746347332,"model":"Qwen/Qwen3-235B-A22B","choices":[{"index":0,"message":{"role":"assistant","reasoning_content":"\nOkay, let's tackle this problem step by step. First, I need to understand what's being asked here. There are two bags, A and B. Bag A has 4 red, 4 blue, and 2 green balls, totaling 10. Bag B has 6 red, 3 blue, and 1 green, also 10 balls. The process is: first, transfer two balls from A to B, then from the new B (now 12 balls), draw 3 balls without replacement. \n\nQuestion 1 asks for the probability of drawing exactly 2 blue and 1 red in step 2. Question 2 is about whether the number formed by the colors (with R=1, B=2, G=3) in the three drawn balls, written as RRL (so the number is 112?), is divisible by 3. And to give a general method for checking divisibility by 3 for such numbers.\n\nStarting with Q1. Since the first step affects the composition of bag B, we need to consider all possible ways two balls can be transferred from A to B, calculate the probability for each scenario, then compute the probability of getting 2 blue and 1 red from the modified B in each case, and sum them all up using the law of total probability.\n\nSo, first, figure out the possible combinations of balls transferred from A to B. The original bag A has 4R, 4B, 2G. When transferring two balls, possible combinations are:\n\nCase 1: Two reds (RR)\nCase 2: One red and one blue (RB)\nCase 3: One red and one green (RG)\nCase 4: Two blues (BB)\nCase 5: One blue and one green (BG)\nCase 6: Two greens (GG)\n\nWait, but the green ones are only 2 in total. So possible transfers include any two from A. Let me check how many cases there are. Since the colors are red (R), blue (B), green (G), the possible pairs are:\n\n- RR\n- RB\n- RG\n- BB\n- BG\n- GG\n\nSo six cases. However, some of these might not be possible. Since there are 4 reds, 4 blues, 2 greens. So for example, RR is possible (4C2=6 ways), RB is possible (4*4=16), RG (4*2=8), BB (4C2=6), BG (4*2=8), GG (2C2=1). Total ways to transfer two balls: 10C2=45. So each case's probability is the number of ways divided by 45.\n\nSo the probabilities for each case:\n\nP(RR) = 6/45 = 2/15\n\nP(RB) = 16/45\n\nP(RG) = 8/45\n\nP(BB) = 6/45 = 2/15\n\nP(BG) = 8/45\n\nP(GG) = 1/45\n\nNow, after transferring each case, the composition of bag B changes. Original B has 6R, 3B, 1G. So adding two balls depending on the case:\n\nCase 1: RR added → B becomes 6+2=8R, 3B, 1G. Total 12.\n\nCase 2: RB added → 6+1=7R, 3+1=4B, 1G. Total 12.\n\nCase 3: RG added → 7R, 3B, 1+1=2G. Total 12.\n\nCase 4: BB added → 6R, 3+2=5B, 1G. Total 12.\n\nCase 5: BG added → 6R, 3+1=4B, 1+1=2G. Total 12.\n\nCase 6: GG added → 6R, 3B, 1+2=3G. Total 12.\n\nThen, for each case, we need to compute the probability of drawing 2B and 1R from the modified B. The number of ways to choose 3 balls with 2B and 1R is (number of B choose 2) * (number of R choose 1). The total possible ways is 12C3.\n\nSo for each case, compute:\n\nP(2B,1R | transfer case) = [C(B_count,2) * C(R_count,1)] / C(12,3)\n\nThen total probability is sum over all cases [P(case) * P(2B,1R | case)]\n\nLet me compute each case:\n\nCase 1: RR transferred. So B has 8R, 3B, 1G. Wait, wait, original B had 6R, adding 2R makes 8R. B count is 3B, G is 1G.\n\nWait, no. Wait, original B is 6R, 3B, 1G. After adding two R, then R=8, B=3, G=1. So number of B is 3, R is 8.\n\nSo to get 2B and 1R: C(3,2)*C(8,1) / C(12,3)\n\nC(3,2) is 3, C(8,1) is 8. So 3*8=24. C(12,3)=220. So 24/220 = 6/55 ≈ 0.1091\n\nCase 2: RB transferred. So R becomes 6+1=7, B becomes 3+1=4, G remains 1. So B=4, R=7.\n\nSo P(2B,1R) = C(4,2)*C(7,1)/220. C(4,2)=6, 6*7=42. 42/220 = 21/110 ≈ 0.1909\n\nCase 3: RG transferred. R=7, B=3, G=2. So B=3, R=7. Same as case 1? Wait, no. Because in this case, after adding R and G, the B count is still 3. So same as case 1: P= C(3,2)*C(7,1)/220 = 3*7=21. 21/220 ≈ 0.0955\n\nCase 4: BB transferred. So B becomes 3+2=5. R=6, G=1. So P(2B,1R) = C(5,2)*C(6,1)/220. C(5,2)=10, 10*6=60. 60/220 = 3/11 ≈ 0.2727\n\nCase 5: BG transferred. So B becomes 3+1=4, G=1+1=2, R=6. So B=4, R=6. So P(2B,1R) = C(4,2)*C(6,1)/220. Same as case 2: 6*6=36? Wait, no: C(4,2)=6, C(6,1)=6, so 6*6=36. 36/220= 9/55 ≈ 0.1636\n\nCase 6: GG transferred. So G becomes 1+2=3. B remains 3, R 6. So P(2B,1R) = C(3,2)*C(6,1)/220 = 3*6=18. 18/220=9/110 ≈ 0.0818\n\nNow, each case's probability multiplied by its conditional probability, then sum all.\n\nSo:\n\nCase 1: (2/15) * (6/55) = (12/825)\n\nCase 2: (16/45)*(21/110) = (16*21)/(45*110) = 336/4950 = simplify by 6: 56/825\n\nCase 3: (8/45)*(21/220) = (8*21)/(45*220) = 168/9900 = divide numerator and denominator by 12: 14/825\n\nWait, wait, 45*220 = 9900. 8*21=168. 168/9900 = divide numerator and denominator by 12: 14/825. Yes.\n\nCase 4: (2/15)*(3/11) = (6/165) = 2/55 = 30/825 (since 2*15=30, 15*55=825?)\n\nWait, 2/15 * 3/11 = 6/165 = 2/55. To convert to denominator 825, multiply numerator and denominator by 15: 30/825.\n\nCase 5: (8/45)*(9/55) = (72/2475) = multiply numerator and denominator by (something?), but let's compute 8*9=72, 45*55=2475. 72/2475 = divide numerator and denominator by 3: 24/825.\n\nCase 6: (1/45)*(9/110) = 9/(45*110) = 1/(5*110) = 1/550 = let's convert to denominator 825: 1.5/825? Hmm, maybe better to convert all fractions to have same denominator. Alternatively, compute each decimal and sum.\n\nAlternatively, let's compute each term:\n\nCase 1: (2/15)*(6/55) = (2*6)/(15*55) = 12/825 ≈ 0.014545\n\nCase 2: (16/45)*(21/110) = (16*21)/(45*110) = 336/4950 ≈ 0.067878\n\nCase 3: (8/45)*(21/220) = 168/9900 ≈ 0.01697\n\nCase 4: (2/15)*(3/11) = 6/165 ≈ 0.03636\n\nCase 5: (8/45)*(9/55) = 72/2475 ≈ 0.02909\n\nCase 6: (1/45)*(9/110) = 9/4950 ≈ 0.001818\n\nAdding all these decimals:\n\n≈ 0.014545 + 0.067878 = 0.082423\n\n+0.01697 ≈ 0.099393\n\n+0.03636 ≈ 0.135753\n\n+0.02909 ≈ 0.164843\n\n+0.001818 ≈ 0.166661\n\nSo total ≈ 0.16666, which is approximately 1/6. But 1/6 is about 0.166666..., so maybe exactly 1/6?\n\nWait, let's check fractions:\n\nCase 1: 12/825\n\nCase 2: 336/4950 = 336 ÷ 6 = 56; 4950 ÷6=825 → 56/825\n\nCase 3: 168/9900 = 168 ÷ 12 =14; 9900 ÷12=825 →14/825\n\nCase 4: 6/165 = 30/825\n\nCase 5: 72/2475 = 72 ÷ 3 =24; 2475 ÷3=825 →24/825\n\nCase 6: 9/4950 = 9 ÷ 6=1.5; 4950 ÷6=825 →1.5/825, but fractions shouldn't have decimals. Alternatively, 9/4950 = 3/1650 = 1/550. Let's convert to 825 denominator:\n\n825 is 550*(3/2). So 1/550 = (1.5)/825. Hmm, messy. Maybe better to convert all to 825 denominator:\n\nCase 1: 12/825\n\nCase 2: 56/825\n\nCase 3:14/825\n\nCase 4:30/825\n\nCase 5:24/825\n\nCase 6: (1/45)*(9/110) = (1*9)/(45*110) = 1/(5*110) = 1/550 = 1.5/825. But since we can't have fractions, maybe find a common denominator. Alternatively, sum all numerators:\n\n12 + 56 +14 +30 +24 + (9/(45*110)*825) ?\n\nWait, maybe there's an error in calculation here. Let me recompute the exact fractions:\n\nTotal probability = sum over each case [P(case) * P(2B1R | case)]\n\nCase 1: (6/45) * [C(3,2)*C(8,1)/C(12,3)] = ?\n\nWait, earlier I considered P(case) as 6/45 for RR, which is 2/15. Then multiplied by 24/220. So 6/45 * 24/220 = (6*24)/(45*220) = 144/(9900) = simplifying numerator and denominator by 12: 12/825. Which matches previous.\n\nSimilarly for all cases:\n\nCase 1: 12/825\n\nCase 2: (16/45)*(42/220) = (16*42)/(45*220) = 672/(9900) = 672 ÷ 12=56; 9900 ÷12=825 → 56/825\n\nCase3: (8/45)*(21/220)= (8*21)/(45*220)= 168/9900=14/825\n\nCase4: (6/45)*(60/220)= (6*60)/(45*220)=360/9900= 3.6/99= 36/990= 12/330= 4/110= 2/55= 30/825.\n\nCase5: (8/45)*(36/220)= (8*36)/(45*220)=288/9900= 24/825\n\nCase6: (1/45)*(18/220)= 18/(45*220)= 18/(9900)= 1/550= 1.5/825. Hmm, but fractions must be integer numerators. Alternatively, maybe I made a mistake in calculation here.\n\nWait, let's recompute case6:\n\nP(case6) = 1/45\n\nAfter adding GG, B has 3B, 6R, 3G.\n\nP(2B1R) = [C(3,2)*C(6,1)] / C(12,3) = 3*6 / 220 = 18/220 = 9/110.\n\nTherefore, the term is (1/45)*(9/110) = 9/(45*110) = 1/(5*110) = 1/550.\n\nSo converting all terms to denominator 825:\n\nCase1: 12/825\n\nCase2:56/825\n\nCase3:14/825\n\nCase4:30/825\n\nCase5:24/825\n\nCase6: 1/550 = (825/550)=1.5, so multiply numerator and denominator by 1.5: 1.5/825. Not possible. Alternatively, find a common denominator. The LCM of 825 and 550 is?\n\n825 factors: 5^2 * 3 * 11\n\n550: 5^2 * 2 * 11\n\nLCM is 5^2 *3 *11 *2= 550*3=1650? Wait 825 is 5^2*3*11, so LCM(825,550)= 5^2*3*11*2= 1650.\n\nSo convert all fractions to denominator 1650:\n\nCase1: 12/825 =24/1650\n\nCase2:56/825=112/1650\n\nCase3:14/825=28/1650\n\nCase4:30/825=60/1650\n\nCase5:24/825=48/1650\n\nCase6:1/550=3/1650\n\nSum all numerators:24+112=136; +28=164; +60=224; +48=272; +3=275.\n\nTotal:275/1650 = divide numerator and denominator by 25: 11/66 = 1/6. \n\nAh! So total probability is 1/6. That's a clean answer. Therefore, Q1's answer is 1/6.\n\nWait, so all those decimal approximations adding up to ≈0.16666 is exactly 1/6. That's a nice result. So the total probability is 1/6. That must be the answer.\n\nNow, moving to Q2. The question says that if in step 2, the three drawn balls are of colors (R=2, B=1), which is written as RRL. Wait, the problem says: \"记作三位数 RRL —— 用颜色编号 (R=1, B=2, G=3) 组成十进制数\". Wait, original statement says that if the three drawn balls in step 2 are of colors (R=2, B=1), then we record this as a three-digit number RRL. Wait, maybe the colors are arranged in some order? Or is the number formed by the counts? Wait, no, probably the colors of the three balls drawn are arranged in some order, and each color is assigned a digit: R=1, B=2, G=3. Then the three-digit number is formed by these digits. The question says if this number, when the colors are (R=2, B=1), which I think means that among the three balls, there are two reds and one blue. But the exact wording says: \"若把 Step 2 的 3 个球颜色按 (R=2, B=1) 记作三位数 RRL —— 用颜色编号 (R=1, B=2, G=3) 组成十进制数 —— 问该数能否被 3 整除？\" Hmm, maybe there's a mistranslation here. The original Chinese says: \"若把 Step 2 的 3 个球颜色按 (R=2, B=1) 记作三位数 RRL —— 用颜色编号 (R=1, B=2, G=3) 组成十进制数 —— 问该数能否被 3 整除？请说明理由，并给出一般判别法。\"\n\nSo, \"按 (R=2, B=1)\" means according to the combination of 2 reds and 1 blue. So when you draw exactly two reds and one blue, you form a three-digit number RRL. But RRL would be the digits 1,1,2 (since R=1, B=2). But the problem says \"组成十进制数\", so the number would be 112, 121, or 211, depending on the order. But the question says \"记作三位数 RRL\", which suggests the order is RRL, i.e., first two reds then one blue? But since the drawing is without replacement and unordered? Or does it consider the order?\n\nWait, this is a bit ambiguous. But in probability, when we draw without replacement, the order usually doesn't matter unless specified. However, the question is forming a three-digit number from the colors, which implies that the order matters. But the problem states that if the colors are two reds and one blue, then we write it as RRL. Maybe RRL is just a placeholder for any arrangement of two Rs and one B, but the exact wording says \"记作三位数 RRL\", which could mean that regardless of the actual order, it's written as RRL. But that might not make sense. Alternatively, perhaps it's a typo, and they mean the counts correspond to R=2, B=1, but the number is formed by the three colors in the order drawn. But since there are two Rs and one B, the number could be any permutation. However, the question is whether such a number (in any order) can be divisible by 3, or whether the specific number RRL (which would be 112) is divisible by 3. The problem says \"该数能否被3整除？\" and \"用颜色编号...组成十进制数\". \n\nAssuming that the three balls are arranged in some order to form a three-digit number. But since the problem says \"记作三位数 RRL\", which is a specific arrangement: two Rs followed by an L (which I think should be B here? Maybe a translation error). Alternatively, maybe \"RRL\" is meant to represent two Rs and one other color, but the problem states \"(R=2, B=1)\", so two reds and one blue. Then forming a three-digit number using their codes: each R is 1, B is 2. So the digits are two 1s and one 2. The number could be 112, 121, or 211. The question is asking whether this number can be divisible by 3. And to provide a general method.\n\nWell, numbers divisible by 3 have the sum of digits divisible by 3. So regardless of the permutation, the sum of the digits would be 1+1+2=4. Since 4 mod 3 is 1, none of the permutations (112, 121, 211) will have a digit sum divisible by 3. Therefore, the number cannot be divisible by 3. The general method is to check if the sum of the digits (each representing the color's code) is divisible by 3.\n\nBut wait, the problem states \"(R=2, B=1)\" — wait, wait! Wait the question says: \"(R=2, B=1) 记作三位数 RRL\". Wait, maybe there's confusion here. If the count is R=2 and B=1, then the colors are two reds and one blue. But the numbering is R=1, B=2, G=3. So each red is 1, blue is 2. So the digits are two 1s and one 2. The sum is 1+1+2=4, not divisible by 3. Hence, no such number formed is divisible by 3. So answer is no, and the general rule is sum of digits divisible by 3.\n\nBut let me confirm the problem statement again. The user wrote:\n\n\"Q2 若把 Step 2 的 3 个球颜色按 (R=2, B=1) 记作三位数 RRL —— 用颜色编号 (R=1, B=2, G=3) 组成十进制数 —— 问该数能否被 3 整除？请说明理由，并给出一般判别法。\"\n\nSo \"(R=2, B=1)\" means that in the three drawn balls, there are 2 reds and 1 blue. Then记作三位数 RRL. The term RRL might be a typo, since the colors are R, B, G. If it's RRL, maybe L is a typo for B or another color. Assuming it's a three-digit number composed of two reds and one other color, but given the counts are R=2 and B=1, it should be two reds and one blue. So the three-digit number uses two 1s and one 2. Regardless of the order, the sum is 4, not divisible by 3. Therefore, the number cannot be divisible by 3. The general test is sum of digits.\n\nTherefore, the answer to Q2 is no, and the general method is checking the sum of the digits.\n\nSo summarizing:\n\nQ1: Probability is 1/6.\n\nQ2: No, the number cannot be divisible by 3. The general method is checking if the sum of the digits (colors coded) is divisible by 3.\n\n**Final Answer**\n\nQ1: The probability is \\boxed{\\dfrac{1}{6}}.\n\nQ2: The number cannot be divisible by 3. A number formed by the color codes is divisible by 3 if and only if the sum of its digits is divisible by 3.\n\nQ1: 概率为 \\boxed{\\dfrac{1}{6}}。\n\nQ2: 该数不能被3整除。一般判别法是该数各位数字之和能被3整除。\n","content":"\n\n### Step-by-Step Explanation\n\n#### **Question 1: Probability of Drawing Exactly 2 Blue and 1 Red in Step 2**\n\n1. **Initial Setup:**\n   - **Bag A:** 4 red (R), 4 blue (B), 2 green (G) → Total 10 balls.\n   - **Bag B:** 6 red (R), 3 blue (B), 1 green (G) → Total 10 balls.\n   - **Step 1:** Transfer 2 balls from A to B. Possible combinations and their probabilities:\n     - RR: $\\frac{6}{45} = \\frac{2}{15}$\n     - RB: $\\frac{16}{45}$\n     - RG: $\\frac{8}{45}$\n     - BB: $\\frac{6}{45} = \\frac{2}{15}$\n     - BG: $\\frac{8}{45}$\n     - GG: $\\frac{1}{45}$\n\n2. **Updated Bag B Composition:**\n   - After transferring 2 balls, Bag B now has 12 balls. The composition depends on the transferred balls.\n\n3. **Probability of Drawing 2 Blue and 1 Red:**\n   - For each transfer case, compute the probability of drawing 2 blue and 1 red from the updated Bag B.\n   - Use combinations to calculate the number of favorable outcomes and total outcomes.\n\n4. **Total Probability Calculation:**\n   - Use the law of total probability to sum the probabilities for each transfer case.\n   - After detailed calculations, the total probability is found to be $\\frac{1}{6}$.\n\n#### **Question 2: Divisibility by 3 of the Formed Number**\n\n1. **Color to Number Mapping:**\n   - R = 1, B = 2, G = 3.\n\n2. **Forming the Number:**\n   - Drawing 2 reds and 1 blue results in digits 1, 1, and 2.\n   - Possible permutations: 112, 121, 211.\n\n3. **Divisibility by 3:**\n   - A number is divisible by 3 if the sum of its digits is divisible by 3.\n   - Sum of digits: $1 + 1 + 2 = 4$, which is not divisible by 3.\n   - Therefore, none of the permutations are divisible by 3.\n\n4. **General Rule:**\n   - A number formed by color codes is divisible by 3 if and only if the sum of its digits is divisible by 3.\n\n### Final Answers\n\n**Q1:** The probability of drawing exactly 2 blue and 1 red in Step 2 is $\\boxed{\\dfrac{1}{6}}$。\n\n**Q2:** The number formed by the colors cannot be divisible by 3. A number formed by the color codes is divisible by 3 if and only if the sum of its digits is divisible by 3.\n\n**Q1:** 概率为 $\\boxed{\\dfrac{1}{6}}$。\n\n**Q2:** 该数不能被3整除。一般判别法是该数各位数字之和能被3整除。","tool_calls":[]},"logprobs":null,"finish_reason":"stop","stop_reason":null}],"usage":{"prompt_tokens":339,"total_tokens":7014,"completion_tokens":6675,"prompt_tokens_details":null},"prompt_logprobs":null}
TIME_NAMELOOKUP:0.000032
TIME_CONNECT:0.000149
TIME_STARTTRANSFER:150.380720
TIME_TOTAL:150.380917
```

The answer is correct.

Performance metrics observed on the server side.

```
INFO 05-04 08:28:59 [metrics.py:489] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 45.2 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.0%, CPU KV cache usage: 0.0%.
INFO 05-04 08:29:04 [metrics.py:489] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 45.1 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.0%, CPU KV cache usage: 0.0%.
INFO 05-04 08:29:09 [metrics.py:489] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 44.8 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.0%, CPU KV cache usage: 0.0%.
INFO 05-04 08:29:14 [metrics.py:489] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 44.3 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
INFO 05-04 08:29:19 [metrics.py:489] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 44.3 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
INFO 05-04 08:29:24 [metrics.py:489] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 44.3 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
INFO 05-04 08:29:29 [metrics.py:489] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 44.3 tokens/s, Running: 1 reqs, Swapped: 0 reqs, Pending: 0 reqs, GPU KV cache usage: 0.1%, CPU KV cache usage: 0.0%.
```

### Stress test Qwen3-235B-A22B with EvalScope's default dataset.

install the evalscope stress-testing tool:

```
pip install --upgrade "evalscope[perf,dataset] @ git+https://github.com/modelscope/evalscope.git@main"
pip install gradio
```

Perform stress testing against the running model.

```
#evalscope perf --url http://172.167.140.16:8090/v1/chat/completions   --model Qwen/Qwen3-235B-A22B --api openai --stream   --parallel 256 --number 1024   --dataset random   --tokenizer-path Qwen/Qwen3-235B-A22B   --min-prompt-length 64 --max-prompt-length 64   --min-tokens 64 --max-tokens 128
```

Logs from the server during inference：

```
reqs, GPU KV cache usage: 98.9%, CPU KV cache usage: 0.0%.
INFO 05-04 13:53:57 [metrics.py:489] Avg prompt throughput: 7760.5 tokens/s, Avg generation throughput: 442.4 tokens/s, Running: 207 reqs, Swapped: 0 reqs, Pending: 274 reqs, GPU KV cache usage: 98.9%, CPU KV cache usage: 0.0%.
INFO 05-04 13:54:02 [metrics.py:489] Avg prompt throughput: 2562.4 tokens/s, Avg generation throughput: 1099.7 tokens/s, Running: 207 reqs, Swapped: 0 reqs, Pending: 274 reqs, GPU KV cache usage: 99.2%, CPU KV cache usage: 0.0%.
INFO 05-04 13:54:07 [metrics.py:489] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 1283.4 tokens/s, Running: 207 reqs, Swapped: 0 reqs, Pending: 274 reqs, GPU KV cache usage: 99.4%, CPU KV cache usage: 0.0%.
INFO 05-04 13:54:12 [metrics.py:489] Avg prompt throughput: 0.0 tokens/s, Avg generation throughput: 1282.8 tokens/s, Running: 207 reqs, Swapped: 0 reqs, Pending: 274 reqs, GPU KV cache usage: 99.7%, CPU KV cache usage: 0.0%.
```

Final result:

```
Benchmarking summary:
+-----------------------------------+-----------------------------------------------------------+
| Key                               | Value                                                     |
+===================================+===========================================================+
| Time taken for tests (s)          | 69.8914                                                   |
+-----------------------------------+-----------------------------------------------------------+
| Number of concurrency             | 256                                                       |
+-----------------------------------+-----------------------------------------------------------+
| Total requests                    | 1024                                                      |
+-----------------------------------+-----------------------------------------------------------+
| Succeed requests                  | 1024                                                      |
+-----------------------------------+-----------------------------------------------------------+
| Failed requests                   | 0                                                         |
+-----------------------------------+-----------------------------------------------------------+
| Output token throughput (tok/s)   | 1865.8519                                                 |
+-----------------------------------+-----------------------------------------------------------+
| Total token throughput (tok/s)    | 2850.9516                                                 |
+-----------------------------------+-----------------------------------------------------------+
| Request throughput (req/s)        | 14.6513                                                   |
+-----------------------------------+-----------------------------------------------------------+
| Average latency (s)               | 17.3582                                                   |
+-----------------------------------+-----------------------------------------------------------+
| Average time to first token (s)   | 5.7435                                                    |
+-----------------------------------+-----------------------------------------------------------+
| Average time per output token (s) | 0.0911                                                    |
+-----------------------------------+-----------------------------------------------------------+
| Average input tokens per request  | 67.2363                                                   |
+-----------------------------------+-----------------------------------------------------------+
| Average output tokens per request | 127.3506                                                  |
+-----------------------------------+-----------------------------------------------------------+
| Average package latency (s)       | 0.0919                                                    |
+-----------------------------------+-----------------------------------------------------------+
| Average package per request       | 126.3184                                                  |
+-----------------------------------+-----------------------------------------------------------+
| Expected number of requests       | 1024                                                      |
+-----------------------------------+-----------------------------------------------------------+
| Result DB path                    | outputs/20250504_222303/Qwen3-235B-A22B/benchmark_data.db |
+-----------------------------------+-----------------------------------------------------------+
2025-05-04 22:24:27,790 - evalscope - INFO - 
Percentile results:
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
| Percentile | TTFT (s) | ITL (s) | TPOT (s) | Latency (s) | Input tokens | Output tokens | Output throughput(tok/s) | Total throughput(tok/s) |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
|    10%     |  5.8189  | 0.0544  |  0.0588  |   13.3598   |      64      |      128      |          6.0347          |         9.1481          |
|    25%     |  5.8442  | 0.0583  |  0.0686  |   13.5874   |      65      |      128      |          6.2648          |         9.4244          |
|    50%     |  5.8657  |  0.06   |  0.1083  |   16.7161   |      66      |      128      |          7.1796          |         11.6407         |
|    66%     |  5.8822  | 0.0607  |  0.1134  |   20.3827   |      67      |      128      |          8.7303          |         13.2849         |
|    75%     |  5.8921  | 0.0612  |  0.1193  |   20.422    |      68      |      128      |          8.7556          |         14.1945         |
|    80%     |  5.897   | 0.0616  |  0.1194  |   21.1746   |      69      |      128      |          9.5546          |         14.3859         |
|    90%     |  5.9128  | 0.0629  |  0.1195  |   21.2086   |      72      |      128      |          9.5785          |         14.5611         |
|    95%     |  5.9307  | 0.1034  |  0.1195  |   21.2282   |      77      |      128      |          9.5905          |         14.7346         |
|    98%     |  5.9465  | 0.2248  |  0.1197  |   21.2461   |      83      |      128      |          9.6005          |         14.9724         |
|    99%     |  5.9502  | 2.2631  |  0.1201  |   21.2522   |      87      |      128      |          9.604           |         15.2534         |
+------------+----------+---------+----------+-------------+--------------+---------------+--------------------------+-------------------------+
```



### Launch DeepSeek R1 671B using SGLang

Pull the Docker image:

```bash
docker pull rocm/sgl-dev:upstream_20250312_v1
```

When launching DeepSeek 671B, it will take approximately 5 minutes.

```bash
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

Once you see output similar to the following, it indicates that the container has successfully started and is ready to accept external requests:

```
[2025-04-01 03:42:11 DP7 TP7] Prefill batch. #new-seq: 1, #new-token: 7, #cached-token: 0, token usage: 0.00, #running-req: 0, #queue-req: 0, 
[2025-04-01 03:42:15] INFO:     127.0.0.1:37762 - "POST /generate HTTP/1.1" 200 OK
[2025-04-01 03:42:15] The server is fired up and ready to roll!
[2025-04-01 04:00:11] INFO:     172.17.0.1:55994 - "POST /v1/chat/completions HTTP/1.1" 200 OK
[2025-04-01 04:00:11 DP0 TP0] Prefill batch. #new-seq: 1, #new-token: 5, #cached-token: 1, token usage: 0.00, #running-req: 0, #queue-req: 0, 
[2025-04-01 04:00:43] INFO:     172.17.0.1:41068 - "POST /v1/chat/completions HTTP/1.1" 200 OK
```

Ensure local accessibility to the DeepSeek 671B container:

```
curl http://localhost:30000/get_model_info 
{"model_path":"deepseek-ai/DeepSeek-R1","tokenizer_path":"deepseek-ai/DeepSeek-R1","is_generation":true} 
curl http://localhost:30000/generate -H "Content-Type: application/json" -d '{ "text": "Once upon a time,", "sampling_params": { "max_new_tokens": 16, "temperature": 0.6 } }'
```

Next, open port 30000 on Azure NSG for remote access testing.

### Stress test DeepSeek R1 671B using SGLang with EvalScope's default dataset.

Install the evalscope stress-testing tool:

```
pip install -U "evalscope[perf,dataset]" \
    @ git+https://github.com/modelscope/evalscope.git@main
pip install gradio
```

Then use evalscope to perform stress testing. This tool supports specifying concurrency, total requests, input and output tokens, and test datasets.

- If you want to maximize total throughput, increase concurrency while reducing the number of input tokens per request. For example, use 100 concurrent requests with 100 input tokens each, focusing on the overall tokens/s metric.
- If you want to test single-request performance, decrease concurrency and increase the number of input tokens per request, paying attention to the Time-to-First-Token (TTFT) and tokens/s metrics of individual requests.

In the test, I used a relatively extreme scenario with an input of 10,000 tokens.

```
evalscope perf --url http://mi300x-xinyu.westus.cloudapp.azure.com:30000/v1/chat/completions --model "deepseek-ai/DeepSeek-R1" --parallel 1 --number 20 --api openai --min-prompt-length 10000 --dataset "longalpaca" --max-tokens 2048 --min-tokens 2048 --stream 
```

Next, I will list test results for several scenarios with different concurrency levels and request counts.

Single concurrency:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PoC-Handbook-for-Azure-AMD-MI300X/images/2.jpg)

5 Concurrent Requests:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PoC-Handbook-for-Azure-AMD-MI300X/images/3.jpg)

10 Concurrent Requests:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PoC-Handbook-for-Azure-AMD-MI300X/images/4.jpg)

**Note**: Additional performance parameters

```
--enable-torch-compile
```

This parameter is currently not supported in the AMD MI300X environment.

```
--enable-dp-attention
```

This parameter is supported in the AMD environment. However, it doesn't improve performance under low concurrency scenarios. Its effectiveness under high concurrency scenarios requires further observation.



### Stress test DeepSeek R1 671B using SGLang with EvalScope's customized dataset.

In many cases, EvalScope's default dataset might not meet our specific requirements. In this section, I will demonstrate the steps to conduct stress testing on DeepSeek R1 671B using the customized C3 dataset.

Prepare C³-dialog dataset → JSONL format:

```
python - <<'PY'
from datasets import load_dataset
import json, pathlib, tqdm, sys

# Load C3‑dialog subset
ds = load_dataset("c3", "dialog")
out = pathlib.Path("c3_evalscope.jsonl").open("w", encoding="utf-8")

def parse(item):
    """
    Yield tuples: (dialogue, question, choices, answer)
    Works for both the old and the new C3 schema.
    """
    if "documents" in item:               # New schema
        dlg = "\n".join(item["documents"])
        qs  = item["questions"]
        for q, ch, ans in zip(qs["question"], qs["choice"], qs["answer"]):
            yield dlg, q, ch, ans
    else:                                 # Old schema
        dlg = "\n".join(item.get("dialogue", item["context"]))
        ch  = item.get("choices", item["options"])
        ans = ch[item.get("label", 0)]
        yield dlg, item["question"], ch, ans

for split in ("train", "validation", "test"):
    for item in tqdm.tqdm(ds[split], desc=split):
        for dlg, q, ch, ans in parse(item):
            prompt = (
                f"以下是一段中文对话，请从给定选项中选出正确答案。\n\n{dlg}\n\n"
                f"问题：{q}\n选项：{' / '.join(ch)}\n请直接输出正确选项文本，不要解释。"
            )
            json.dump({"prompt": prompt, "answer": ans}, out, ensure_ascii=False)
            out.write("\n")

out.close()
print("✅ Lines written:", sum(1 for _ in open("c3_evalscope.jsonl")))
PY
```

```
train: 100%|█████████████████████████████████████████████████████████| 4885/4885 [00:00<00:00, 13936.95it/s]
validation: 100%|████████████████████████████████████████████████████| 1628/1628 [00:00<00:00, 14640.62it/s]
test: 100%|██████████████████████████████████████████████████████████| 1627/1627 [00:00<00:00, 14258.74it/s]
✅ Lines written: 9571
```

### Perform stress testing on DeepSeek R1 671B using a customized dataset.

```
DeepSeek-R1（30000 端口） 1️⃣ Instruction-S1-low 256→50
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 50 --max-tokens 150

Instruction-S1-high 512→150
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 50 --max-tokens 150

MultiStep-S2-low 512→150-500
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 150 --max-tokens 500

MultiStep-S2-high 1024→150-500
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 1024 --min-tokens 150 --max-tokens 500

Reasoning-S3-low 256→1024
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024

Reasoning-S3-high 512→1024 172.167.140.16
evalscope perf --url http://172.167.140.16:30000/v1/chat/completions --model deepseek-ai/DeepSeek-R1 --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 1024 --max-tokens 1024
```

The test results are available in [**results.txt**](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PoC-Handbook-for-Azure-AMD-MI300X/results1.txt).

### Launch Qwen 2.5 72B using vLLM

Start container：

```
docker run -d --name qwen72b_8x --device=/dev/kfd --device=/dev/dri --privileged --security-opt seccomp=unconfined --cap-add SYS_PTRACE -p 8000:8000 -v /mnt/resource_nvme:/mnt/resource_nvme -e HF_HOME=/mnt/resource_nvme/hf_cache -e HSA_NO_SCRATCH_RECLAIM=1 -e VLLM_USE_TRITON_FLASH_ATTN=0 -e VLLM_USE_V1=0 rocm/vllm-dev:nightly_main_20250423 vllm serve Qwen/Qwen2.5-72B-Instruct --dtype float16 --tensor-parallel-size 8 --swap-space 16 --max-model-len 8192 --max-num-batched-tokens 65536 --gpu-memory-utilization 0.95 --num-scheduler-steps 10 --disable-log-requests
```



### **Stress test Qwen 2.5 72B  using SGLang with EvalScope's customized dataset.**

```
Qwen-2.5-72B（8080 端口）
Instruction-S1-low 256→50
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 50 --max-tokens 150

Instruction-S1-high 512→150
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 50 --max-tokens 150

MultiStep-S2-low 512→150-500
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 150 --max-tokens 500

MultiStep-S2-high 1024→150-500
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 1024 --min-tokens 150 --max-tokens 500

Reasoning-S3-low 256→1024
evalscope perf --url http://172.167.140.16:8080/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 256 --min-tokens 1024 --max-tokens 1024

Reasoning-S3-high 512→1024
evalscope perf --url http://172.167.140.16:8000/v1/chat/completions --model Qwen/Qwen2.5-72B-Instruct --api openai --stream --parallel 300 --number 1000 --dataset custom --dataset-path ./c3_evalscope.jsonl --min-prompt-length 512 --min-tokens 1024 --max-tokens 1024
```

The test results are available in [**results.txt**.](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/PoC-Handbook-for-Azure-AMD-MI300X/results2.txt)



**Refer to:**

*https://techcommunity.microsoft.com/blog/azurehighperformancecomputingblog/running-deepseek-r1-on-a-single-ndv5-mi300x-vm/4372726*
