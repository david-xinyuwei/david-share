"""
修复所有扫描件 PDF - 同时更新 enhanced_prompt 和 attachment_contents
"""
import json
import base64
import requests
import fitz
import os

AZURE_OPENAI_ENDPOINT = "https://your-aoai-endpoint.openai.azure.com/"
AZURE_OPENAI_KEY = "YOUR_AZURE_OPENAI_KEY"
CACHE_DIR = "gdpval_cache"

def analyze_pdf_page(img_bytes):
    """用 GPT-5.2 分析单页 PDF 图片"""
    image_base64 = base64.b64encode(img_bytes).decode('utf-8')
    headers = {'api-key': AZURE_OPENAI_KEY, 'Content-Type': 'application/json'}
    payload = {
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Extract ALL text and data from this document image. Include tables as markdown. Be thorough."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
        ]}],
        "max_completion_tokens": 4096
    }
    api_url = f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/deployments/gpt-5.2-chat/chat/completions?api-version=2024-10-21"
    resp = requests.post(api_url, headers=headers, json=payload, timeout=300)
    if resp.status_code == 200:
        return resp.json().get('choices', [{}])[0].get('message', {}).get('content', '')
    return f"[API Error: {resp.status_code}]"

def fix_pdf_with_vision(pdf_path, pdf_name):
    """用 GPT-5.2 视觉分析扫描件 PDF"""
    print(f"  📄 处理: {pdf_name}")
    doc = fitz.open(pdf_path)
    text_parts = []
    max_pages = min(len(doc), 5)
    
    for i in range(max_pages):
        print(f"    Page {i+1}/{max_pages}...", end=" ", flush=True)
        page = doc[i]
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        text = analyze_pdf_page(img_bytes)
        if text and not text.startswith("["):
            text_parts.append(f"\n--- Page {i+1} (Vision) ---\n{text}")
            print(f"✅ {len(text)} chars")
        else:
            print(f"❌ {text[:50] if text else 'empty'}")
    
    doc.close()
    return '\n'.join(text_parts)

def find_cache_file(filename):
    """在缓存目录中找到对应的文件"""
    for f in os.listdir(CACHE_DIR):
        if filename in f:
            return os.path.join(CACHE_DIR, f)
    return None

# 加载数据
with open("gdpval_enhanced.json", "r") as f:
    data = json.load(f)

# 找出所有需要修复的 PDF
pdfs_to_fix = set()
for t in data:
    ep = t.get("enhanced_prompt", "")
    if "[PDF 无可提取文本]" in ep:
        # 找出哪些 PDF 需要修复
        import re
        matches = re.findall(r"=== 附件: ([^=]*\.pdf) ===\n\[PDF 无可提取文本\]", ep, re.IGNORECASE)
        for m in matches:
            pdfs_to_fix.add(m)
    
    for att in t.get("attachment_contents", []):
        if att.get("content") == "[PDF 无可提取文本]":
            pdfs_to_fix.add(att["filename"])

print(f"需要修复的 PDF ({len(pdfs_to_fix)}):")
for p in pdfs_to_fix:
    print(f"  - {p}")

# 逐个处理 PDF 并立即保存
total_fixed = 0
for pdf_name in pdfs_to_fix:
    cache_path = find_cache_file(pdf_name)
    if not cache_path:
        print(f"  ❌ {pdf_name}: 缓存文件不存在\n")
        continue
    
    content = fix_pdf_with_vision(cache_path, pdf_name)
    print(f"  ✅ {pdf_name}: {len(content)} chars")
    
    # 立即更新数据并保存
    fixed_this = 0
    for t in data:
        # 修复 enhanced_prompt
        ep = t.get("enhanced_prompt", "")
        old = f"=== 附件: {pdf_name} ===\n[PDF 无可提取文本]"
        new = f"=== 附件: {pdf_name} ===\n{content}"
        if old in ep:
            t["enhanced_prompt"] = ep.replace(old, new)
            fixed_this += 1
        
        # 修复 attachment_contents
        for att in t.get("attachment_contents", []):
            if att.get("content") == "[PDF 无可提取文本]" and att["filename"] == pdf_name:
                att["content"] = content
                att["status"] = "success"
                att["parsed_length"] = len(content)
                fixed_this += 1
    
    # 每处理完一个PDF立即保存
    with open("gdpval_enhanced.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"     已保存 (修复 {fixed_this} 处)\n")
    total_fixed += fixed_this

print(f"\n总计修复: {total_fixed} 处")

# 验证
with open("gdpval_enhanced.json") as f:
    text = f.read()
    remaining = text.count("[PDF 无可提取文本]")
print(f"剩余未修复: {remaining}")
