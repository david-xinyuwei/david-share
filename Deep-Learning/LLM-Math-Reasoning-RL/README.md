# Reinforcement Learning for LLM Mathematical Reasoning: From Rule-Based Rewards to Self-Verifiable Proofs

> A progressive technical guide and analysis: Understanding RLHF/GRPO roles through a "film crew" analogy, comparing DeepSeek-R1 (verifiable rewards) with DeepSeekMath-V2 (self-verifiable proofs) training architectures.

*Author: Xinyu Wei (Microsoft GBB AI Architect)*

---

## 🎯 Objectives

- Explain: Why "rule-based rewards" and "LLM-as-Judge" coexist in LLM mathematical reasoning
- Clarify: What Actor / Reward / Reference / Critic(Value) do in RLHF, which get trained, and why
- Present: Training architectures and key algorithms for DeepSeek-R1 and DeepSeekMath-V2 (with diagrams)
- Compare: When to use verifiable rewards vs. when to train a verifier

---

## 🎭 Chapter 1: Understanding RL Roles Through a "Film Crew" Analogy (Core Intuition)

Let's first clarify "who is who" in training—this makes all subsequent paper details much clearer.

### 1.1 PPO/RLHF: A "Four-Role" Film Crew

| Component | Film Crew Analogy | One-Line Responsibility | Parameters Updated During Training? |
|---|---|---|---|
| **Actor (policy)** | 🎬 Actor | Responsible for "performing"—generating responses | ✅ Trained |
| **Reward Model (RM)** | 👨‍⚖️ Judge | Scores the performance (preference/quality) | ✅ Pre-trained; usually frozen during PPO |
| **Reference Model** | 📜 Original Script | Prevents actor from "deforming" for high scores (KL constraint) | ❌ Frozen |
| **Critic / Value Model** | 🎓 Sparring Coach | Practices alongside while learning "roughly what score this performance will get" | ✅ Trained (synchronized with Actor) |

#### How Do Training Signals Flow? (PPO Architecture Diagram)

```text
Prompt x
  │
  ▼
┌───────────────┐        ┌──────────────────┐
│ Actor πθ      │        │ Reference πref   │
│ Generates y   │        │ (Original Script)│
└──────┬────────┘        └───────┬──────────┘
       │                          │
       │ logπθ(y|x)               │ logπref(y|x)
       │                          │
       ▼                          ▼
   ┌──────────────────────────────────────────┐
   │ KL Penalty:   -β · (logπθ - logπref)     │
   └──────────────────────────────────────────┘
                  │
                  │ Generated (x, y)
                  │
       ┌──────────┴──────────┐
       ▼                     ▼
┌───────────────┐     ┌───────────────┐
│ Reward Model  │     │ Critic Vψ     │
│ r = RM(x,y)   │     │ v = Vψ(x)     │
│ (Judge scores)│     │ (Coach estimates)│
└──────┬────────┘     └──────┬────────┘
       │                     │
       └──────────┬──────────┘
                  ▼
           Advantage A = r - v
                  │
                  ├──> Update Actor θ (make high-A behaviors more frequent)
                  └──> Update Critic ψ (make v closer to r)
```

**Key Point**: Reward Model and Critic compute **in parallel**, both based on generated (x, y), then jointly compute Advantage.

#### Why Must Critic Be "Trained Together"?

- As Actor improves (policy distribution changes), reward distribution also changes
- If Critic doesn't learn along, its "score prediction" becomes increasingly inaccurate
- More accurate Critic → more stable Actor updates (lower variance)

> This is why I compare Critic to a "sparring coach": it's not a bystander—it must constantly calibrate itself.

### 1.2 GRPO: Remove the "Coach", Use "Group Comparison" as Baseline

Both DeepSeek-R1 and DeepSeekMath-V2 emphasize **GRPO**. Intuitively:

- PPO needs Critic to estimate baseline
- GRPO samples a group of responses for the same prompt, using **relative performance within the group** as baseline, eliminating the need to separately train a Critic

#### GRPO Update Intuition (Pseudocode)

```text
Given prompt x:
  1) Sample K responses y1..yK from Actor
  2) Compute reward for each: r1..rK
  3) Compute group baseline (e.g., mean r̄)
  4) Update Actor with (ri - r̄) as weights
  5) Can still add KL(Actor || Reference) constraint
```

Visualization:

```text
Same problem x
  ├─ y1 → r1
  ├─ y2 → r2
  ├─ y3 → r3
  └─ yK → rK

Group baseline r̄ = mean(r)
Advantage: Ai = ri - r̄
```

---

## 🧠 Chapter 2: Two Types of Math Tasks Determine Two Types of Rewards

### 2.1 "Fill-in-the-Blank" vs "Proof Problems"

| Task Type | Typical Competitions | Output | Verification Difficulty | Suitable Reward |
|---|---|---|---|---|
| **Verifiable Final Answer** | AIME/HMMT etc. | A number / A choice | ✅ Very Low | Rule-based reward (exact match / unit tests) |
| **Proof/Reasoning Process** | IMO/Putnam | Long proof chain | ❌ Very High | Trained verifier (LLM-as-Judge) |

**Core Contradiction** (from the paper):

> *"Pursuing higher final answer accuracy doesn't address a key issue: correct answers don't guarantee correct reasoning."*

Intuition:
- Fill-in-the-blank: reward is "right/wrong"
- Proof problems: reward is "rigor/completeness/presence of fatal flaws"

---

## 🔧 Chapter 3: DeepSeek-R1—How "Verifiable Rewards" Boost Reasoning Ability

> Key Point: R1 heavily uses **rule-based rewards** (verifiable) for math/code tasks, only introducing more subjective model scoring for general tasks.

### 3.1 What Does R1's "Rule Reward" Look Like?

```python
def rule_reward(answer, ground_truth):
    # 1) format reward (e.g., must include \boxed{})
    if not has_boxed(answer):
        return 0.0

    # 2) accuracy reward (strict comparison)
    return 1.0 if extract_boxed(answer) == ground_truth else 0.0
```

### 3.2 Engineering Advantages of Rule-Based Rewards

- **Reliable**: Almost no noise
- **Cheap**: No need to call additional LLM
- **Scalable**: Can run massive rollouts
- **Anti reward-hacking**: Clear alignment objective

### 3.3 But Its Ceiling Is Also Clear

- Correct final answer ≠ correct reasoning
- Completely inapplicable to proof problems (no "uniquely decidable" ground truth)

---

## 🔬 Chapter 4: DeepSeekMath-V2—"Self-Verifiable Proof" Training Architecture (with Meta-Verification)

This section is from the DeepSeekMath-V2 paper (verified against local `DeepSeekMath_V2.pdf`).

### 4.1 Verifier: First Train "Judges" to Find Issues and Score

Verifier's objective (Paper Section 2.1.1): For given problem X and proof Y, output analysis + score s ∈ {0, 0.5, 1}.

**Scoring Criteria** (Three-tier system):
- **1 point**: Completely correct, all steps rigorous and clear
- **0.5 points**: Overall logic correct, but with minor omissions or errors
- **0 points**: Contains fatal logical errors or severe gaps

**Verifier's RL Reward** (paper formula):
- R_format: Check if output includes required "evaluation + boxed score"
- R_score(s', s) = 1 - |s' - s|: Distance between predicted score and expert-labeled score

### 4.2 Meta-Verifier: Specifically Preventing "Judges Making Up Issues"

Key insight from Paper Section 2.1.2:

> *"When evaluating flawed proofs during training, the verifier can receive full reward by predicting the correct scores while hallucinating non-existent issues, undermining its trustworthiness."*

Problem: If Verifier is only supervised on "whether score is correct", it might use "fabricated flaws" to explain low scores.

**Solution**: Introduce meta-verification—have another model audit whether the verifier's analysis is **real, reasonable, and sufficient to support that score**.

**Enhanced Verifier Reward** (paper formula):

R_V = R_format · R_score · R_meta

Where R_meta comes from meta-verifier's quality score for the "review text".

**Effect**: Verification analysis quality score improved from **0.85 to 0.96**, while maintaining score prediction accuracy.

#### Two-Layer Verification Architecture (Proof → Verifier → Meta-Verifier)

```text
Problem X + Proof Y
        │
        ▼
┌───────────────────────┐
│ Verifier πφ           │
│ - Find flaws/gaps     │
│ - Explain deductions  │
│ - Output score s∈{0,0.5,1}│
└───────────┬───────────┘
            │ (More worth reviewing when s is low)
            ▼
┌───────────────────────┐
│ Meta-Verifier πη       │
│ - Audit if "review" is real│
│ - Audit if deduction reasons hold│
│ - Output quality score ms∈{0,0.5,1}│
└───────────┬───────────┘
            ▼
Trustworthy review for training/filtering
```

### 4.3 Generator: Initialize from Verifier Checkpoint, Then Learn "Write Proof + Self-Evaluate"

Key approach from Paper Section 2.2.2:
- Generator outputs two parts: proof Y + self-evaluation Z
- Let Verifier score the proof, while meta-verifying the self-evaluation

**Reward Function** (paper provides coefficients):

R = R_format(Y,Z) · (α · R_Y + β · R_Z)

Where (intuitive explanation):
- R_Y: Whether the proof is actually good
- R_Z: Whether your self-evaluation is honest and accurate (needs verifier + meta-verifier to check)
- Paper settings: α = 0.76, β = 0.24

**Incentive Mechanism** (paper quotes):
- *"Faithful acknowledgment of errors is rewarded over false claims of correctness."*
- *"A good strategy to obtain high rewards is to identify and resolve as many issues as possible before finalizing the response."*

#### "Self-Verifiable Proof" Closed Loop (Generate→Self-Evaluate→External Verify→Training Signal)

```text
Prompt X
  │
  ▼
┌───────────────────────────────┐
│ Generator πθ                   │
│ Generates: Proof Y + Self-Review Z│
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│ Verifier πφ                    │
│ Scores Proof Y: s              │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│ Meta-Verifier πη               │
│ Audits Self-Review Z honesty/quality│
└───────────────┬───────────────┘
                ▼
Reward R = α·(proof score) + β·(self-review fidelity)
```

### 4.4 Verification-Generation Co-Evolution

The **automated closed loop** described in Paper Section 2.3 is the biggest highlight:

1. **Verifier → Generator**: Use verifier as reward model to train generator
2. **Generator → Verifier**: As generator improves, it produces harder-to-verify proofs, challenging the verifier
3. **Automatic Labeling**: For each proof, generate n verification analyses, filter using meta-verification, auto-label difficult problems

```text
For each proof:
  1) Generate n independent verification analyses
  2) For analyses with score 0 or 0.5:
     - Generate m meta-verification assessments
     - Valid if majority confirms findings
  3) If ≥k valid analyses give lowest score → label with that score
  4) If no legitimate issues → label with 1
  5) Otherwise → discard or route to human
```

> **In the last two training iterations, the fully automated pipeline completely replaced human annotation.**

### 4.5 Inference Time: One Model, Massive Compute Overhead

**Key Finding**: The paper explicitly states—

> "All experiments used a **single model**, our final proof generator, which performs **both proof generation and verification**."

**Not two model weights—one model switching roles via prompts!**

```text
┌─────────────────────────────────────────────────────────────────────┐
│              Inference: Single Model + Prompt Role Switching         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Same model weights πθ                                              │
│      │                                                              │
│      ├── Prompt A (Generation) ──► Generate proof Y + self-eval Z   │
│      │                                                              │
│      └── Prompt B (Verification) ─► Verify others' proofs (majority voting)│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**But what's the cost? Look at the paper's inference configuration:**

| Config | Value | Description |
|--------|-------|-------------|
| Initial proof samples | **64** | Generate 64 candidate proofs per problem |
| Verification analyses/proof | **64** | Run 64 verifications per proof |
| Parallel threads | **32** | Best@32 selection |
| Refinement iterations | **Up to 16** | refinement iterations |
| Per iteration | **64 proofs × 8 analyses** | Select highest-scoring pairs |

**Inference Overhead Estimate** (single IMO problem):
```
Initial: 64 proofs × 64 verifications = 4,096 inferences
Iteration: 16 rounds × 64 pairs = 1,024 refinements
Total: ~5,000+ model calls/problem
```

**This is what "scaling test-time compute" really means!**

Paper quote: "By scaling test-time compute under verifier guidance, our model solves problems that **require hours of effort from human competitors**."

**So this is not a time-saving approach—it's "trading compute for accuracy":**
- ✅ **Advantage**: Only need one model weight, simple deployment
- ❌ **Disadvantage**: Massive inference overhead, suitable for offline competition scenarios
- 🎯 **Applicable**: IMO/CMO/Putnam scenarios where "you have hours per problem"

---

## 📝 Chapter 5: Core Prompt Templates (Paper Essence)

### 5.1 Proof Generation Prompt (Complete Version)

This prompt enables the model to **generate proof + self-evaluate**, key to implementing "self-verification":

```text
Your task is to solve a given problem. The problem may ask you to
prove a statement, or ask for an answer. If finding an answer is
required, you should come up with the answer, and your final solution
should also be a rigorous proof of that answer being valid.

Your final solution to the problem should be exceptionally comprehensive
and easy-to-follow, which will be rated according to the following
evaluation instruction:

'''
Here is the instruction to evaluate the quality of a solution to a problem.
The problem may ask for a proof of statement, or ask for an answer. If
finding an answer is required, the solution should present the answer,
and it should also be a rigorous proof of that answer being valid.

Please evaluate the solution and score it according to the following criteria:
- If the solution is completely correct, with all steps executed properly
  and clearly demonstrated, then the score is 1
- If the solution is generally correct, but with some details omitted or
  minor errors, then the score is 0.5
- If the solution does not actually address the required problem, contains
  fatal errors, or has severe omissions, then the score is 0

Additionally, referencing anything from any paper does not save the need
to prove the reference. It's okay IF AND ONLY IF the solution also presents
a valid proof of the reference argument(s); otherwise, if the solution
omits the proof or if the proof provided is not completely correct, the
solution should be scored according to the criteria above, and definitely
not with a score of 1
'''

In fact, you already have the ability to rate your solution yourself,
so you are expected to reason carefully about how to solve a given problem,
evaluate your method according to the instruction, and refine your solution
by fixing issues identified until you can make no further progress.

In your final response, you should present a detailed solution to the
problem followed by your evaluation of that solution.

- To give a good final response, you should try your best to locate
  potential issues in your own (partial) solution according to the
  evaluation instruction above, and fix them as many as you can.
- A good final response should just faithfully present your progress,
  including the best solution you can give, as well as a faithful
  evaluation of that solution.
- Only when you fail to locate any issues in your solution should you
  score it with 1.
- If you do notice some issues in your solution but fail to resolve them
  with your best efforts, it's totally ok to faithfully present the issues
  in your final response.
- The worst final response would provide a wrong solution but lie that
  it's correct or claim that it's correct without careful error checking.
  A better version should faithfully identify errors in the solution.
  Remember! You CAN'T cheat! If you cheat, we will know, and you will
  be penalized!

Your final response should be in the following format:

## Solution
... // Your final solution to the problem here. You should try your best
to optimize the quality of your solution according to the evaluation
instruction above before finalizing it here.

## Self Evaluation
Here is my evaluation of the solution:

... // Your evaluation here. You are required to present in detail the
key steps of the solution or the steps for which you had doubts regarding
their correctness, and explicitly analyze whether each step is accurate.

Based on my evaluation, the final overall score should be: \boxed{...}
--
Here is your task input:
## Problem
{question}
```

**Key Design Elements**:
- Explicitly tells the model "you have the ability to self-evaluate" (In fact, you already have the ability...)
- Emphasizes honesty: "The worst final response would provide a wrong solution but lie..."
- Anti-cheating deterrent: "Remember! You CAN'T cheat! If you cheat, we will know, and you will be penalized!"

### 5.2 Proof Verification Prompt (Complete Version)

```text
## Instruction
Your task is to evaluate the quality of a solution to a problem. The
problem may ask for a proof of statement, or ask for an answer. If
finding an answer is required, the solution should present the answer,
and it should also be a rigorous proof of that answer being valid.

Please evaluate the solution and score it according to the following criteria:
- If the solution is completely correct, with all steps executed properly
  and clearly demonstrated, then the score is 1
- If the solution is generally correct, but with some details omitted or
  minor errors, then the score is 0.5
- If the solution does not actually address the required problem, contains
  fatal errors, or has severe omissions, then the score is 0

Additionally, referencing anything from any paper does not save the need
to prove the reference. It's okay IF AND ONLY IF the solution also presents
a valid proof of the reference argument(s).

Your response format:
Here is my evaluation of the solution:

... // Present key steps, analyze correctness, explain errors if any

Based on my evaluation, the final overall score should be: \boxed{...}
--
Here is your task input:
## Problem
{question}

## Solution
{proof}
```

### 5.3 Meta-Verification Prompt (Complete Version)

```text
You are given a "problem", "solution", and "solution evaluation",
and you need to assess whether this "solution evaluation" is reasonable.

Your task is to analyze the "solution evaluation" from these aspects:

1. Step Restatement: Check whether the "solution" actually has the behaviors
   mentioned in the "solution evaluation"

2. Defect Analysis (MOST IMPORTANT): Check whether the errors or defects
   pointed out are reasonable
   - For each defect found, analyze:
     a) whether this defect actually exists
     b) whether the analysis of this defect is accurate
   - Note: positive components (claims of correctness) are NOT in your scope

3. Expression Analysis: Whether expressions are accurate

4. Score Analysis: Whether the final score matches the defects found

Importantly: If the "solution evaluation" believes the "solution" is completely
accurate and has not found any errors, then regardless of whether the "solution"
itself is actually accurate, you should still consider its analysis reasonable.
```

**Elegant Design**:
- Meta-verifier **only audits whether "identified issues" are real**, not whether "claims of correctness" are valid
- This avoids infinite recursive auditing

---

## 📊 Chapter 6: Experimental Results

### 6.1 Proof Capability Comparison by Category

![Figure 1: CNML-Level Scores by Category](images/figure1-cnml-scores.png)

*DeepSeekMath-V2 outperforms GPT-5-Thinking-High and Gemini 2.5 Pro across all five categories: algebra, geometry, number theory, combinatorics, and inequality.*

### 6.2 Iterative Improvement Effects & ProofBench Results

![Figure 2-3: Iterative Improvement and ProofBench](images/figure2-3-refinement-proofbench.png)

**Key Findings**:
- Pass@1 improves significantly with iteration count
- Best@32 (best selected by self-evaluation) is much higher than average, showing the model can accurately distinguish proof quality
- Outperforms DeepMind's DeepThink (IMO Gold) on IMO-ProofBench Basic set

### 6.3 Competition Results

| Competition | Fully Solved | Score Rate |
|---|---|---|
| **IMO 2025** | P1, P2, P3, P4, P5 | **83.3%** 🥇 |
| **CMO 2024** | P1, P2, P4, P5, P6 | **73.8%** 🥇 |
| **Putnam 2024** | 11/12 problems | **98.3%** (118/120, exceeding human high score of 90) |

---

## 📐 Chapter 7: Comparison and Selection Recommendations

### 7.1 When to Use Rule Rewards? When to Train a Verifier?

| Scenario | Recommendation | Reason |
|---|---|---|
| Has standard answer/executable verification (math results, unit tests) | Rule reward | Cheap, reliable, scalable |
| Need to evaluate reasoning process (proofs, review, complex reasoning) | Train verifier | Can only rely on semantic judgment |
| Worried about verifier hallucination/fabrication | Add meta-verification | Improve "review text" trustworthiness |
| Need model to iteratively improve its own output | Train self-verification | Let model "know" its reward function |

### 7.2 DeepSeek-R1 vs DeepSeekMath-V2 Summary

| Dimension | DeepSeek-R1 | DeepSeekMath-V2 |
|---|---|---|
| **Target Task** | General reasoning (math/code/general) | Mathematical proofs (theorem proving) |
| **Primary Reward** | Rule-based rewards (final answer match) | Trained verifier + meta-verifier |
| **Can Evaluate Reasoning Process** | ❌ Only looks at final answer | ✅ Can evaluate proof rigor |
| **Self-Verification Ability** | ❌ | ✅ Can self-evaluate and iteratively improve |
| **Representative Competitions** | AIME, HMMT | IMO, CMO, Putnam |

---

## ⚠️ Limitations

- **Training code and data not open-sourced**: Paper describes reproducible "approach", but hard to reproduce "equivalent results"
- **Proof verifier evaluation is still probabilistic**: Needs multi-sample/voting/review strategies to reduce misjudgment
- **Hardest IMO-level problems remain challenging**: Paper acknowledges *"the hardest IMO-level problems remain challenging for our model"*

---

## 📚 References

1. **DeepSeekMath-V2**: Shao et al., "Towards Self-Verifiable Mathematical Reasoning", 2025. [[PDF](DeepSeekMath_V2.pdf)] [[GitHub](https://github.com/deepseek-ai/DeepSeek-Math-V2)]
2. **DeepSeek-R1**: Guo et al., *Nature*, 2025. [[DOI](https://doi.org/10.1038/s41586-025-09422-z)]
3. **GRPO**: Shao et al., "DeepSeekMath", 2024. [[arXiv](https://arxiv.org/abs/2402.03300)]

---

*Last Updated: 2025-12-13*

---

## 🔄 Chapter 8: Three RL Training Approaches Compared

Beyond the DeepSeekMath-V2 paper's method, there are two mainstream engineering approaches: **Agent Lightning** (local training) and **Azure RFT** (cloud managed).

### 8.1 Full Comparison of Three Approaches

| Dimension | DeepSeekMath-V2 (Paper) | Agent Lightning (Local) | Azure RFT (Cloud) |
|-----------|-------------------------|------------------------|-------------------|
| **Goal** | Mathematical proofs (theorem proving) | Math reasoning (word problems) | General reasoning |
| **Training Algorithm** | GRPO + Verifier RL | GRPO / PPO / DAPO | Managed RFT (undisclosed) |
| **Reward Source** | Trained Verifier + Meta-Verifier | Custom functions (rules+structure) | Graders (rules/models/code) |
| **Self-Verification** | ✅ Model learns to self-evaluate | ❌ External reward only | ❌ External reward only |
| **Inference Iteration** | ✅ ~5000+ calls/problem | ❌ Single generation | ❌ Single generation |
| **Supported Models** | DeepSeek series | Open-source (Qwen, LLaMA) | OpenAI (o4-mini, GPT-5) |
| **Hardware Requirement** | Large-scale cluster | 40GB+ GPU (H100/A100) | No local GPU needed |
| **Open Source** | Paper public, code not released | Fully open source | Managed service |
| **Use Case** | IMO/Putnam competition proofs | Engineering-grade math reasoning | Quick prototyping/OpenAI ecosystem |

### 8.2 Reward Function Design Comparison

All three approaches need to define "what makes a good answer", but implement it differently:

#### DeepSeekMath-V2: Three-Layer Verification Reward

```text
┌─────────────────────────────────────────────────────────────────┐
│                  DeepSeekMath-V2 Reward Architecture             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Generator Output: Proof Y + Self-Evaluation Z                  │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────┐                                            │
│  │ Verifier πφ     │ ──► R_Y = proof_score (0/0.5/1)           │
│  │ (Trained Judge) │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │ Meta-Verifier πη│ ──► R_meta = is self-eval honest (0/0.5/1)│
│  │ (Audits Judge)  │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  R = R_format · (α·R_Y + β·R_Z)    α=0.76, β=0.24              │
│                                                                 │
│  Key: Reward model itself needs training, can evaluate reasoning│
└─────────────────────────────────────────────────────────────────┘
```

#### Agent Lightning: Composite Rule-Based Reward

```python
def compute_reward(response, ground_truth):
    reward = 0.0
    
    # 1) Structure reward: has reasoning chain?
    if "<think>" in response and "</think>" in response:
        reward += 0.5  # correct format
    
    # 2) Correctness reward: final answer
    if extract_answer(response) == ground_truth:
        reward += 2.0  # correct answer
    
    # 3) Depth reward: reasoning sufficiency
    if len(extract_think(response)) > 100:
        reward += 0.5  # reasoning long enough
    
    return reward  # max 3.0

# Key: Simple rules, no trained judge, only checks final answer + format
```

#### Azure RFT: Grader Composition

```python
# Multigrader example: combining multiple scoring methods
{
    "type": "multi",
    "graders": {
        "correctness": {
            "type": "python",
            "source": "def grade(s,i): return 1.0 if s.output==i.answer else 0.0"
        },
        "format": {
            "type": "string_check",
            "operation": "like",
            "input": "{{ sample.output_text }}",
            "reference": "\\boxed{"
        },
        "quality": {
            "type": "score_model",
            "model": "gpt-4o-2024-08-06",
            "input": [{"role": "user", "content": "Rate this solution..."}]
        }
    },
    "calculate_output": "correctness * 0.6 + format * 0.2 + quality * 0.2"
}

# Key: Flexible composition, supports LLM-as-Judge, managed execution
```

### 8.3 Key Difference: Self-Verification vs External Reward

| Feature | DeepSeekMath-V2 | Agent Lightning / Azure RFT |
|---------|-----------------|----------------------------|
| **Does model know reward function?** | ✅ Yes, learned verification rules during training | ❌ No, only knows reward signal |
| **Can self-improve?** | ✅ Self-evaluates + iteratively fixes at inference | ❌ Cannot self-correct after generation |
| **Inference overhead** | 🔴 Extremely high (~5000 calls/problem) | 🟢 Low (single generation) |
| **Suitable for real-time?** | ❌ Offline competitions | ✅ Online services |

**Core Insight**:

DeepSeekMath-V2's "self-verification" means **teaching the model verification ability during training**, enabling it at inference to:
1. Generate answer AND self-evaluation simultaneously
2. Identify issues based on self-evaluation
3. Iterate until self-evaluation is perfect

Agent Lightning / Azure RFT use **pure external rewards**—the model doesn't know "why this answer is good", only that "this answer got a high score".

### 8.4 Training Complexity Comparison

```text
DeepSeekMath-V2 Training Pipeline (Complex):
─────────────────────────────────────────────────────
Stage 1: Train Verifier (needs human-labeled proof quality)
   │
   ▼
Stage 2: Train Meta-Verifier (prevents Verifier hallucination)
   │
   ▼
Stage 3: Train Generator (using Verifier as Reward Model)
   │
   ▼
Stage 4: Co-evolution (Generator↔Verifier mutually improve)
─────────────────────────────────────────────────────

Agent Lightning Training Pipeline (Simple):
─────────────────────────────────────────────────────
Stage 1: Define reward function (rule code)
   │
   ▼
Stage 2: GRPO training (single stage)
─────────────────────────────────────────────────────

Azure RFT Training Pipeline (Simplest):
─────────────────────────────────────────────────────
Step 1: Prepare JSONL data
Step 2: Define Grader (JSON config)
Step 3: Submit training job (Azure Portal / API)
─────────────────────────────────────────────────────
```



