import json
from collections import Counter

data = json.load(open("/root/gdpval-web/gdpval_enhanced.json"))

print("=== 数据预处理完整性报告 ===\n")

print(f"总任务数: {len(data)}")
with_att = len([t for t in data if t.get("attachment_contents")])
print(f"有附件任务: {with_att}")
print(f"有 enhanced_prompt: {len([t for t in data if t.get(enhanced_prompt)])}")

# 收集附件信息
all_att = []
for t in data:
    for a in t.get("attachment_contents", []):
        ext = a["filename"].rsplit(".",1)[-1].lower()
        all_att.append((a.get("status"), ext))

print(f"\n总附件数: {len(all_att)}")

success_count = sum(1 for s,e in all_att if s == "success")
partial_count = sum(1 for s,e in all_att if s == "partial")
print(f"解析状态: success={success_count}, partial={partial_count}")

print("\n=== 各类型解析情况 ===")
exts = set(e for s,e in all_att)
for ext in sorted(exts):
    total = sum(1 for s,e in all_att if e == ext)
    ok = sum(1 for s,e in all_att if e == ext and s == "success")
    rate = ok/total*100 if total else 0
    print(f"  {ext:8}: {ok:3}/{total:3} ({rate:.0f}%)")

print("\n=== 问题汇总 ===")
text_fail = sum(1 for s,e in all_att if e in ("docx","xlsx","pdf","txt","pptx") and s=="partial")
if text_fail:
    print(f"⚠️  文本类附件解析失败: {text_fail} 个")
else:
    print("✅ PDF/Excel/TXT/PPTX 全部解析成功")

media = sum(1 for s,e in all_att if e in ("wav","mp3","mp4","psd","step","pages","zip"))
print(f"ℹ️  多媒体/特殊格式: {media} 个 (无法转文本，正常)")
