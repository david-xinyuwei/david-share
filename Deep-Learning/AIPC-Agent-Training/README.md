# AIPC Agent Training Flywheel

A complete **DPO + GRPO flywheel** for training domain-specific AI agents, demonstrated with an AIPC (AI PC) customer service scenario.

## 🎯 Core Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                        FLYWHEEL LOOP                            │
│                                                                 │
│   V1 (SFT)  ──►  Deploy  ──►  User Feedback (👍/👎)            │
│       ▲                              │                          │
│       │                              ▼                          │
│   V(n+1)    ◄──  DPO + GRPO  ◄──  Feedback Data                │
│                                                                 │
│   • DPO: Learn boundaries (what's wrong)                        │
│   • GRPO: Optimize quality (what's better)                      │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Training Data Strategy

### DPO Data (Accumulates)
| Version | DPO Training Data |
|---------|-------------------|
| V2 | V1 feedback errors |
| V3 | V1 + V2 feedback errors |
| V4 | V1 + V2 + V3 feedback errors |

**Key**: DPO data **accumulates** - the model should never forget learned boundaries.

### GRPO Prompts (Constant Size, Evolving Content)
| Version | GRPO Prompts Composition | Total |
|---------|--------------------------|-------|
| V2 | V1 errors (50) + New questions (50) | **100** |
| V3 | V2 errors (30) + New questions (70) | **100** |
| V4 | V3 errors (15) + New questions (85) | **100** |

**Key**: GRPO prompts maintain **constant quantity** but evolve:
- Old errors decrease (model learned them)
- New questions injected (continuous improvement)
- Model generates **fresh answers** each iteration (not reusing old responses)

## 🔄 Complete Workflow

### Phase 1: Cold Start (V1)
```bash
# Train V1 with seed data (human-annotated)
python train_sft.py \
    --data data/cold_start.jsonl \
    --output output/v1_model
```

### Phase 2: Collect Feedback (Simulate V1 Online)
```bash
# Simulate user feedback on V1 responses
python generate_feedback_data.py \
    --model output/v1_model \
    --questions data/test_questions.jsonl \
    --output-dpo data/dpo_v2.jsonl \
    --output-grpo-prompts data/grpo_prompts_v2.jsonl
```

**Output:**
- `dpo_v2.jsonl`: Preference pairs (prompt, chosen, rejected)
- `grpo_prompts_v2.jsonl`: **Only questions** (model will generate answers during GRPO training)

### Phase 3: DPO + GRPO Training (V2)
```bash
# Stage 1: DPO - Learn boundaries
python train_dpo.py \
    --base-model output/v1_model \
    --data data/dpo_v2.jsonl \
    --output output/v2_dpo

# Stage 2: GRPO - Optimize quality (real-time sampling!)
python train_grpo.py \
    --base-model output/v2_dpo \
    --prompts data/grpo_prompts_v2.jsonl \
    --judge-endpoint $AZURE_OPENAI_ENDPOINT \
    --output output/v2_model
```

### Phase 4: Iterate
```bash
# Prepare next iteration prompts
python prepare_grpo_prompts.py \
    --old-errors data/v2_errors.jsonl \
    --new-questions data/new_questions.jsonl \
    --output data/grpo_prompts_v3.jsonl \
    --target-count 100

# Continue the flywheel...
```

## 📁 Repository Structure

```
AIPC-Agent-Training/
├── data/
│   ├── cold_start.jsonl        # V1 SFT seed data (50 samples)
│   ├── test_questions.jsonl    # Evaluation questions
│   ├── dpo_v2.jsonl            # DPO pairs for V2
│   ├── grpo_prompts_v2.jsonl   # GRPO prompts for V2 (questions only!)
│   └── new_questions.jsonl     # New questions to inject each iteration
│
├── train_sft.py                # V1 cold start SFT
├── train_dpo.py                # DPO preference training
├── train_grpo.py               # GRPO with real-time sampling + scoring
├── train_iteration.py          # Complete DPO→GRPO iteration
│
├── generate_feedback_data.py   # Simulate user feedback → DPO + GRPO prompts
├── prepare_grpo_prompts.py     # Merge old errors + new questions
├── evaluate.py                 # Model evaluation
│
├── gradio_demo.py              # Interactive demo UI
└── requirements.txt
```

## 🔑 Key Design Decisions

### 1. Why DPO + GRPO (not just one)?
- **DPO**: Teaches "don't do this" (learns from mistakes)
- **GRPO**: Teaches "do this better" (optimizes among correct answers)

### 2. Why GRPO uses real-time sampling?
```python
# ❌ WRONG: Pre-generated responses
grpo_data = [{"prompt": Q, "response": A, "reward": 0.8}]  # Static!

# ✅ CORRECT: Real-time sampling during training
for prompt in grpo_prompts:
    responses = model.generate(prompt, num_samples=4)  # Fresh!
    rewards = judge.score(responses)  # Real-time!
    grpo_update(prompt, responses, rewards)
```

The model learns to improve **its current self**, not memorize old answers.

### 3. Why maintain constant GRPO prompt count?
- Too few prompts → unstable training
- New questions → prevent overfitting to old errors
- Old errors → ensure hard problems get enough practice

## 🛠️ Requirements

```bash
pip install -r requirements.txt
```

Key dependencies:
- `torch>=2.0.0`
- `transformers>=4.40.0`
- `trl>=0.12.0` (for DPOTrainer, GRPOTrainer)
- `vllm>=0.6.0` (for fast inference)
- `openai>=1.0.0` (for GPT Judge)

## 📈 Expected Results

| Version | Training Method | Accuracy |
|---------|-----------------|----------|
| V1 | SFT (cold start) | ~40% |
| V2 | DPO + GRPO | ~65% |
| V3 | DPO + GRPO | ~80% |
| V4 | DPO + GRPO | ~90%+ |

The flywheel effect: each iteration improves on the last!

## 📝 License

MIT License
