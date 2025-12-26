#!/usr/bin/env python3
"""
AIPC Agent Closed-Loop Flywheel Demo (English Version)
"""

import os
import json
import gradio as gr
from datetime import datetime
from pathlib import Path
from openai import OpenAI

# ==================== Config ====================
VLLM_PORT = 8000
MODEL_PATH = "exported_model_v3"
FEEDBACK_FILE = "/root/aipc-flywheel/data/user_feedback_en.jsonl"

# ==================== Feedback Collector ====================
class FeedbackCollector:
    def __init__(self, feedback_file: str):
        self.feedback_file = Path(feedback_file)
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        self.current_qa = {"question": "", "answer": ""}

    def save_feedback(self, rating: str, comment: str = ""):
        if not self.current_qa["question"]:
            return "Please chat first before rating", self.get_stats()
            
        feedback = {
            "timestamp": datetime.now().isoformat(),
            "prompt": self.current_qa["question"],
            "response": self.current_qa["answer"],
            "feedback": "positive" if rating == "👍" else "negative",
            "score": 10 if rating == "👍" else 2,
            "comment": comment
        }

        with open(self.feedback_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(feedback, ensure_ascii=False) + "\n")

        total = len(self.get_all_feedback())
        status = f"✅ Feedback saved! (Total: {total})"
        
        if total >= 20:
            status += f"\n\n🎉 Collected {total} feedback samples, ready for training!"
        else:
            status += f"\n\n📈 Need {20 - total} more samples to trigger training"
            
        return status, self.get_stats()

    def get_all_feedback(self):
        if not self.feedback_file.exists():
            return []
        feedback = []
        with open(self.feedback_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    feedback.append(json.loads(line))
        return feedback

    def get_stats(self):
        feedback = self.get_all_feedback()
        if not feedback:
            return "No feedback data yet"
        
        total = len(feedback)
        positive = sum(1 for f in feedback if f["feedback"] == "positive")
        negative = total - positive
        
        return f"""📊 Feedback Statistics
-----------------------
Total: {total}
👍 Positive: {positive} ({positive/total*100:.1f}%)
👎 Negative: {negative} ({negative/total*100:.1f}%)
"""

# ==================== Main App ====================
def create_demo():
    collector = FeedbackCollector(FEEDBACK_FILE)
    client = OpenAI(
        base_url=f"http://localhost:{VLLM_PORT}/v1",
        api_key="not-needed"
    )

    def chat(message: str, history: list):
        try:
            response = client.chat.completions.create(
                model=MODEL_PATH,
                messages=[
                    {"role": "system", "content": "You are an AI PC expert assistant. Answer questions about AI PC, NPU, Intel Core Ultra, AMD Ryzen AI, Qualcomm Snapdragon X, etc."},
                    {"role": "user", "content": message}
                ],
                max_tokens=512,
                temperature=0.7
            )
            answer = response.choices[0].message.content
            collector.current_qa["question"] = message
            collector.current_qa["answer"] = answer
            return answer
        except Exception as e:
            return f"❌ Error: {str(e)}\n\nPlease ensure vLLM service is running."

    with gr.Blocks(title="AIPC Agent Flywheel Demo", theme=gr.themes.Soft()) as demo:
        gr.Markdown("""
# 🔄 AIPC Agent Closed-Loop Training Flywheel

**Data Flywheel Demo - Continuous Iteration:**
1. Chat with the AIPC Agent (V3 Model - 100% accuracy on core questions)
2. Rate responses with 👍/👎
3. Feedback → SFT training (supervised fine-tuning)
4. GPT-5.2 scores → RL/GRPO training (reinforcement learning)
5. Deploy new version, iterate continuously

**Training Methods:**
| Feedback Source | Training Method | Principle |
|-----------------|-----------------|-----------|
| User 👍👎 | SFT | Learn correct answers directly |
| GPT-5.2 Score | RL/GRPO | Optimize with reward signals |
        """)

        with gr.Row():
            with gr.Column(scale=2):
                chatbot = gr.ChatInterface(
                    chat,
                    title="💬 AIPC Expert Assistant (V3)",
                    examples=[
                        "What is AI PC?",
                        "What is NPU and how is it different from GPU?",
                        "Which vendors make AI PC chips?",
                        "Is AIPC an Alibaba Cloud product?",
                        "What is Intel Core Ultra?",
                        "What is Copilot+ PC?"
                    ]
                )

            with gr.Column(scale=1):
                gr.Markdown("## 📝 Rate This Response")
                
                with gr.Row():
                    btn_good = gr.Button("👍 Good Answer", variant="primary")
                    btn_bad = gr.Button("👎 Needs Improvement", variant="secondary")
                
                comment_box = gr.Textbox(
                    label="Comments (Optional)", 
                    placeholder="Why good/bad?"
                )
                feedback_status = gr.Textbox(label="Status", interactive=False)
                
                gr.Markdown("---")
                stats_display = gr.Textbox(
                    label="Feedback Statistics", 
                    value=collector.get_stats(), 
                    interactive=False
                )
                
                gr.Markdown("---")
                gr.Markdown("""
### 🎯 Model Evolution
| Version | Data | Accuracy |
|---------|------|----------|
| V1 | 50 cold start | ~10% |
| V2 | +22 feedback | ~7.5% |
| **V3** | +48 corrected | **100%** |
                """)

        btn_good.click(
            lambda c: collector.save_feedback("👍", c),
            inputs=[comment_box],
            outputs=[feedback_status, stats_display]
        )
        btn_bad.click(
            lambda c: collector.save_feedback("👎", c),
            inputs=[comment_box],
            outputs=[feedback_status, stats_display]
        )

    return demo

if __name__ == "__main__":
    demo = create_demo()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
