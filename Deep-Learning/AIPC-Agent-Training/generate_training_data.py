"""
generate_training_data.py - 从私有知识库生成 AIPC 技术支持训练数据

使用 GPT-4o 从技术文档中生成高质量的 QA 对话数据，用于 GRPO 训练。

使用方法：
    python generate_training_data.py --docs ./docs --output ./data/aipc_training_data.json

输入：
    - docs 目录下的 .txt / .md / .pdf 文件

输出：
    - JSON 格式的训练数据，每条包含 prompt 和 response
"""

import os
import json
import argparse
from typing import List, Dict
from pathlib import Path
from openai import AzureOpenAI

# 数据生成 prompt
GENERATE_QA_PROMPT = """你是一个 AIPC 技术支持专家。请基于以下技术文档内容，生成 5 个真实用户可能会问的问题和专业回答。

要求：
1. 问题要自然，像真实用户会问的那样
2. 回答要专业、详细、有可操作性
3. 覆盖不同难度：基础问题、进阶问题、故障排除
4. 问题之间不要重复

文档内容：
{doc_content}

请输出 JSON 格式（不要加 markdown 代码块标记）：
[
    {{"question": "用户问题1", "answer": "专业回答1"}},
    {{"question": "用户问题2", "answer": "专业回答2"}},
    ...
]"""


class TrainingDataGenerator:
    """训练数据生成器"""
    
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]
        )
        self.deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    
    def read_document(self, file_path: str) -> str:
        """读取文档内容"""
        path = Path(file_path)
        
        if path.suffix.lower() in ['.txt', '.md']:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        elif path.suffix.lower() == '.pdf':
            # 简单的 PDF 处理，实际项目中可能需要更复杂的处理
            try:
                import pymupdf4llm
                return pymupdf4llm.to_markdown(str(path))
            except ImportError:
                print(f"警告：需要 pymupdf4llm 来处理 PDF: pip install pymupdf4llm")
                return ""
        else:
            print(f"警告：不支持的文件格式: {path.suffix}")
            return ""
    
    def generate_qa_from_doc(self, doc_content: str, max_chars: int = 8000) -> List[Dict]:
        """从文档生成 QA 对"""
        
        # 截断过长的文档
        if len(doc_content) > max_chars:
            doc_content = doc_content[:max_chars] + "\n...(文档已截断)"
        
        prompt = GENERATE_QA_PROMPT.format(doc_content=doc_content)
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            
            # 清理 markdown 代码块标记
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            qa_pairs = json.loads(content.strip())
            return qa_pairs
            
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            print(f"原始响应: {content[:200]}...")
            return []
        except Exception as e:
            print(f"API 调用失败: {e}")
            return []
    
    def process_docs_folder(self, docs_path: str) -> List[Dict]:
        """处理整个文档目录"""
        all_qa = []
        docs_dir = Path(docs_path)
        
        # 支持的文件类型
        extensions = ['.txt', '.md', '.pdf']
        
        files = []
        for ext in extensions:
            files.extend(docs_dir.glob(f'**/*{ext}'))
        
        print(f"找到 {len(files)} 个文档文件")
        
        for i, file_path in enumerate(files):
            print(f"\n[{i+1}/{len(files)}] 处理: {file_path.name}")
            
            doc_content = self.read_document(str(file_path))
            if not doc_content:
                continue
            
            qa_pairs = self.generate_qa_from_doc(doc_content)
            print(f"  生成了 {len(qa_pairs)} 个 QA 对")
            
            # 添加来源信息
            for qa in qa_pairs:
                qa['source'] = file_path.name
            
            all_qa.extend(qa_pairs)
        
        return all_qa


def main(args):
    """主流程"""
    
    print("=" * 60)
    print("AIPC 训练数据生成")
    print("=" * 60)
    
    # 检查环境变量
    required_vars = ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]
    missing = [v for v in required_vars if v not in os.environ]
    if missing:
        raise ValueError(f"缺少环境变量: {', '.join(missing)}")
    
    # 生成数据
    generator = TrainingDataGenerator()
    qa_pairs = generator.process_docs_folder(args.docs)
    
    print(f"\n总共生成 {len(qa_pairs)} 个 QA 对")
    
    # 转换为训练格式
    training_data = []
    for qa in qa_pairs:
        training_data.append({
            "prompt": qa["question"],
            "response": qa["answer"]
        })
    
    # 保存
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(training_data, f, ensure_ascii=False, indent=2)
    
    print(f"训练数据已保存至: {output_path}")
    
    # 显示示例
    print("\n数据示例：")
    for item in training_data[:3]:
        print(f"  Q: {item['prompt'][:50]}...")
        print(f"  A: {item['response'][:50]}...")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成 AIPC 技术支持训练数据")
    parser.add_argument("--docs", required=True, help="文档目录路径")
    parser.add_argument("--output", default="./data/aipc_training_data.json", help="输出文件路径")
    
    args = parser.parse_args()
    main(args)
