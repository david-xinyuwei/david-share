# Reasoning-CoT

After the release of OpenAI o1, its training methods and reasoning approaches have garnered a lot of attention. I utilized the Prompt method to simulate Reasoning CoT based on 4o. Although its generalization ability and accuracy are certainly not as good as o1, it can still provide some help for everyone to understand reasoning.

## Basic AOAI 4o

Using the default AOAI 4o(2024-05-13), I asked "How many 'r' letters are in the word strawberry?" three times, and the answer was wrong each time.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWb0icCptwcBLppaO7SDGlVQXV1DuOZFhSMib1fl0Q48D3Q1lYskbwKeRz9jccaWMjia8a9icYKN4eatg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## AOAI Reasoning CoT

I write Reasoning CoT and use Streamlit to publish the UI, calling the same AOAI 4o, and ask the question three times. To differentiate, the sentences are slightly different.


![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWb0icCptwcBLppaO7SDGlVQc6hZvjmzE7xviajE1bkqLNliaAwvj8sWCIEYgLEFgUP0JPdU1TxftcWw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWb0icCptwcBLppaO7SDGlVQI89Awhp34VpqVic0wPIekiaaZqoEHHZ22sQyXGu9B6e9UZhtLoibaNHbQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWb0icCptwcBLppaO7SDGlVQ5tSLotnkXKY2iawHhzUQtUxFXHw0XbLoQb4sJ8tv0PEicDApUQOdQlnQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Code implementation

I wrote two pieces of code: one is responsible for the main code implementation and exposes the API locally, and the other calls the API using Streamlit. You can run both files in the WSL environment on your laptop.

code.py code：

```
(base) root@davidwei:~/cot# cat code.py
import os
import openai
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

openai.api_type = "azure"
openai.api_base = "https://***.openai.azure.com/"
openai.api_version = "2024-02-15-preview"
openai.api_key = '****'

deployment_name = 'eastus3xinyuwei'

# 创建 FastAPI 应用
app = FastAPI()

class QueryRequest(BaseModel):
    query: str
    previous_turns: List[str] = []

class SynthesisRequest(BaseModel):
    query: str
    turns: List[str]

def call_llm(messages):
    response = openai.ChatCompletion.create(
        engine=deployment_name,
        messages=messages,
        temperature=0.7,
        max_tokens=1500,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
    )
    return response['choices'][0]['message']['content']

def generate_turn(query, previous_turns=None):
    initial_system_prompt = """You are an AI assistant skilled in detailed, step-by-step analysis. When given a question or problem, break down your thought process into clear, logical steps. For each step, explain your reasoning. Conclude with a final answer. Use the following markdown structure:
## Thought Process
1. [First step]
   **Explanation:** [Detailed explanation of this step]
2. [Second step]
   **Explanation:** [Detailed explanation of this step]
...
## Conclusion
[Final answer]

Be thorough and show your reasoning clearly."""

    followup_system_prompt = """You are an AI assistant capable of refining and enhancing previous reasoning. Consider the previous turns of reasoning and provide an improved and more detailed analysis. Use the following markdown structure:
## Review
[Critique of previous reasoning]
## Enhanced Reasoning
[Improved reasoning steps]
## Updated Conclusion
[Updated final answer]

Be comprehensive and aim to enhance the quality of the prior responses."""

    if previous_turns is None or len(previous_turns) == 0:
        # 第一轮
        messages = [
            {"role": "system", "content": initial_system_prompt},
            {"role": "user", "content": query}
        ]
    else:
        # 后续轮次
        previous_content = "\n\n".join(previous_turns)
        messages = [
            {"role": "system", "content": followup_system_prompt},
            {
                "role": "user",
                "content": f"Original Query: {query}\n\nPrevious Turns:\n{previous_content}\n\nProvide the next turn of reasoning."
            }
        ]
    return call_llm(messages)

def synthesize_turns(query, turns):
    synthesis_prompt = """You are an AI assistant tasked with synthesizing multiple turns of reasoning into a cohesive final answer. Analyze the previous turns, compare them, and produce a well-reasoned conclusion. Use the following markdown structure:
## Synthesis
### Analysis of Turns
[Analysis of each turn]
### Comparison
[Comparison of the turns]
### Final Reasoning
[Combined reasoning]
### Comprehensive Final Answer
[Detailed final answer]
### Concise Answer
[Summarized final answer]

Ensure that the final answers are clear, comprehensive, and actionable."""

    turns_text = "\n\n".join([f"Turn {i+1}:\n{turn}" for i, turn in enumerate(turns)])
    messages = [
        {"role": "system", "content": synthesis_prompt},
        {
            "role": "user",
            "content": f"Original Query: {query}\n\nTurns of Reasoning:\n{turns_text}"
        }
    ]
    return call_llm(messages)

@app.post("/generate_turn/")
def api_generate_turn(request: QueryRequest):
    try:
        result = generate_turn(request.query, request.previous_turns)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/synthesize_turns/")
def api_synthesize_turns(request: SynthesisRequest):
    try:
        result = synthesize_turns(request.query, request.turns)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

ui.py code：

```
(base) root@davidwei:~/cot# cat ui.py
import streamlit as st
import requests

API_URL = "http://localhost:8000" 

def main():
    st.title("Xinyu Wei' CoT AI Assistant")

    query = st.text_input("Enter your query:", "")
    if 'turns' not in st.session_state:
        st.session_state.turns = []

    if st.button("Generate Turn"):
        if query:
            response = requests.post(f"{API_URL}/generate_turn/", json={"query": query, "previous_turns": st.session_state.turns})
            if response.status_code == 200:
                result = response.json().get("result", "")
                st.session_state.turns.append(result)
                st.write(result)
            else:
                st.error(f"Error: {response.status_code}")

    if st.button("Synthesize Turns"):
        if query and st.session_state.turns:
            response = requests.post(f"{API_URL}/synthesize_turns/", json={"query": query, "turns": st.session_state.turns})
            if response.status_code == 200:
                result = response.json().get("result", "")
                st.write("### Final Synthesis")
                st.write(result)
            else:
                st.error(f"Error: {response.status_code}")

if __name__ == "__main__":
    main()
```

The way to run code:

```
uvicorn llama_api:app --host 0.0.0.0 --port 8000&

streamlit run llama_ui.py
```

​	

