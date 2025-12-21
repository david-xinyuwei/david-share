# GDPVAL Grok Benchmark Tool

> AI Model Evaluation Platform for Real-World Economically Valuable Tasks with GPT-5.2 as Judge

## 🎯 Overview

GDPVAL (GDP-Valuable Tasks) Benchmark Tool evaluates AI models on **real-world business tasks** across 9 industry sectors. It uses **GPT-5.2-chat as an impartial judge** to score responses on 5 dimensions, with support for human review and correction.

**Key Results**: In initial testing, grok-4-fast-non-reasoning achieved **8.2/10** average score, comparable to gpt-5.2-chat-baseline (**8.4/10**).

---

## 🧠 Technical Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js 14)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  Sector  │  │  Model   │  │ Progress │  │   Visualization  │ │
│  │ Selector │  │ Selector │  │  Panel   │  │ Radar/Bar/HeatMap│ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
│                         │ WebSocket                              │
└─────────────────────────┼───────────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────────┐
│                    Backend (FastAPI)                             │
│  ┌──────────────────────┴────────────────────────────────────┐  │
│  │                   WebSocket Handler                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐  │  │
│  │  │ Phase 1:    │  │ Phase 2:    │  │ Phase 3 & 4:      │  │  │
│  │  │ Model Test  │→ │ AI Evaluate │→ │ Human Review +    │  │  │
│  │  │ (Streaming) │  │ (GPT-5.2)   │  │ Final Results     │  │  │
│  │  └─────────────┘  └─────────────┘  └───────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│         │                      │                                 │
│    ┌────┴────┐           ┌─────┴─────┐                          │
│    │Grok API │           │Azure OpenAI│                          │
│    │(GitHub) │           │ (GPT-5.2)  │                          │
│    └─────────┘           └───────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

### 4-Phase Evaluation Workflow

| Phase | Name | Description |
|-------|------|-------------|
| 1 | **Model Testing** | Call selected models with task prompts, stream responses in real-time |
| 2 | **AI Evaluation** | GPT-5.2-chat scores each response on 5 dimensions (1-10) |
| 3 | **Human Re-check** | Optional: Human reviews and corrects AI scores |
| 4 | **Complete** | Final results generated with human corrections applied |

### Evaluation Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Completeness | 20% | Does the response address all aspects of the task? |
| Accuracy | 20% | Is the information factually correct? |
| Professionalism | 20% | Does it use appropriate industry terminology? |
| Clarity | 20% | Is the response well-structured and easy to understand? |
| Actionability | 20% | Does it provide concrete, implementable recommendations? |

### GPT-5.2 Baseline Comparison

To ensure fair evaluation, we support running **GPT-5.2-chat as a contestant** (without the judge prompt):

| Role | System Prompt | API |
|------|---------------|-----|
| **GPT-5.2 as Judge** | Full evaluation prompt with scoring criteria | Azure OpenAI responses API |
| **GPT-5.2 as Contestant** | None (same as Grok models) | Azure OpenAI responses API |

This allows comparing Grok models against the same model used as judge, detecting potential self-preference bias.

---

## 🖥️ Environment

| Component | Specification |
|-----------|---------------|
| **Frontend** | Next.js 14.2.18 + TypeScript + Tailwind CSS + Recharts |
| **Backend** | FastAPI + WebSocket + uvicorn |
| **Grok API** | Azure AI Foundry (models.inference.ai.azure.com) |
| **Judge API** | Azure OpenAI (gpt-5.2-chat with responses API) |
| **Node.js** | >= 18.x |
| **Python** | >= 3.10 |

---

## 🚀 Quick Start

### Prerequisites

```bash
# Node.js 18+
node --version  # v18.x or higher

# Python 3.10+
python --version  # 3.10 or higher
```

### Installation

```bash
# Clone repository
git clone https://github.com/YOUR-USERNAME/gdpval-benchmark.git
cd gdpval-benchmark

# Backend setup
cd backend
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
npm run build
```

### Configuration

Create environment variables or use the UI to configure:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `GROK_ENDPOINT` | Azure AI Foundry endpoint | `https://models.inference.ai.azure.com` |
| `GROK_API_KEY` | GitHub token for Grok API | `YOUR-API-KEY` |
| `JUDGE_ENDPOINT` | Azure OpenAI endpoint | `https://YOUR-RESOURCE.openai.azure.com` |
| `JUDGE_API_KEY` | Azure OpenAI API key | `YOUR-API-KEY` |
| `JUDGE_MODEL` | Judge model deployment name | `gpt-5.2-chat` |

### Running

**Option 1: Separate terminals**

```bash
# Terminal 1 - Backend (port 8000)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend (port 3000)
cd frontend
npm start
```

**Option 2: One-click start**

```bash
chmod +x start.sh
./start.sh
```

### Access

- **Web UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

---

## 📊 Test Results

### Sample Benchmark: Manufacturing + Finance Sectors

**Configuration**:
- Models: grok-3-mini, grok-4-fast-non-reasoning, gpt-5.2-chat-baseline
- Tasks per sector: 2
- Total evaluations: 12

| Model | Manufacturing | Finance | **Avg** |
|-------|---------------|---------|---------|
| grok-3-mini | 8.0 | 6.4 | **7.2** |
| grok-4-fast-non-reasoning | 8.2 | 8.2 | **8.2** |
| gpt-5.2-chat-baseline | 8.0 | 8.8 | **8.4** |

### Latency Comparison

| Model | Avg Latency | Notes |
|-------|-------------|-------|
| grok-3-mini | 1.2s | Fastest |
| grok-4-fast-non-reasoning | 0.9s | Very fast |
| gpt-5.2-chat-baseline | 18.5s | Includes reasoning |

---

## 🔍 Features

### Real-time Streaming
- WebSocket-based streaming for model responses
- Live progress updates during evaluation

### Visualization
- **Capability Radar**: 5-dimension comparison across all models
- **Model Ranking**: Horizontal bar chart of overall scores
- **Sector × Model Heatmap**: Color-coded performance matrix with averages

### Export Options
- **JSON**: Complete results with responses and reasons
- **Excel**: Tabular data for further analysis
- **HTML Report**: Standalone shareable report

### Human Review
- Edit AI scores in results table
- Corrections automatically recalculate charts
- Track number of human corrections applied

---

## ⚠️ Pitfalls & Solutions

### Issue 1: GPT-5.2 API returns error

**Symptom**: `[ERROR] Unknown model: gpt-5.2-chat-baseline`

**Cause**: Code used display name instead of actual model name

**Solution**: Use `self.config.judge_model` (configured value like `gpt-5.2-chat`) instead of hardcoded string

### Issue 2: Grok responses show variable reference error

**Symptom**: All Grok model responses are error messages `[ERROR] local variable referenced before assignment`

**Cause**: Variable scope issue in streaming code after adding GPT-5.2 baseline branch

**Solution**: Ensure `await self.send()` is inside the `if chunk.choices` block

### Issue 3: Frontend shows blank page after rebuild

**Symptom**: Page loads but shows nothing

**Cause**: Multiple Next.js processes on different ports, or stale `.next` cache

**Solution**: 
```bash
pkill -9 -f node
rm -rf .next
npm run build
npm start
```

---

## 📁 Project Structure

```
gdpval-web/
├── backend/
│   ├── main.py              # FastAPI + WebSocket server
│   ├── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx     # Main page component
│   │   │   ├── layout.tsx   # App layout
│   │   │   └── globals.css  # Global styles
│   │   └── components/
│   │       ├── RadarChart.tsx
│   │       ├── BarChart.tsx
│   │       ├── HeatMap.tsx
│   │       ├── ProgressPanel.tsx
│   │       ├── ResultsTable.tsx
│   │       └── StreamLog.tsx
│   ├── package.json
│   ├── next.config.js       # API proxy configuration
│   ├── tailwind.config.js
│   └── tsconfig.json
├── README.md
├── README-CN.md
└── start.sh
```

---

## 💡 Recommendations

| Use Case | Recommendation |
|----------|----------------|
| Quick comparison | Use grok-3-mini (fastest) vs gpt-5.2-chat-baseline |
| Production evaluation | Use grok-4 or grok-4-fast-reasoning for best quality |
| Bias detection | Always include gpt-5.2-chat-baseline when GPT-5.2 is judge |
| Large-scale testing | Limit tasks_per_sector to 5-10 to avoid rate limits |

---

## 📚 References

- [Azure AI Foundry - Grok Models](https://ai.azure.com/)
- [Azure OpenAI - GPT-5.2](https://learn.microsoft.com/azure/ai-services/openai/)
- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.3.0 | 2025-12-21 | Added GPT-5.2 baseline comparison, 4-phase workflow, human review |
| 0.2.0 | 2025-12-20 | Added HeatMap, radar chart, Excel export |
| 0.1.0 | 2025-12-19 | Initial release with Gradio UI |

---

*Author: Xinyu Wei (Microsoft AI and Apps GBB Architect) | Verified: 2025-12-21*
