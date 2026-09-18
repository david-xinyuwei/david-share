# 《边缘侧AI小模型训练、优化与部署》配套代码 | 第3章 §3.6.3 训练飞轮实现方案 —— V1.4 代码偏好数据

import ast
import re
def has_valid_python(text):
    """检查文本中的 Python 代码块语法是否正确"""
    # 提取 ```python ... ``` 代码块
    code_blocks = re.findall(r'```python(.*?)```', text, re.DOTALL)
    if not code_blocks:
        return False, 0
    valid_blocks = 0
    for block in code_blocks:
        try:
            ast.parse(block.strip())
            valid_blocks += 1
        except SyntaxError:
            pass
    return valid_blocks > 0, valid_blocks
# 使用：AST 通过的作为 chosen，失败的作为 rejected
if has_valid_python(response)[0]:
    chosen_responses.append(response)
else:
    rejected_responses.append(response)
