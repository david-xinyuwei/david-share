#!/bin/bash
# One-click: fetch latest data + GPT-5.4 analysis + regenerate dashboard
cd "$(dirname "$0")"

echo "🔄 Refreshing Morning Sweep..."
python3 morning_sweep.py --hours 24 -o morning_sweep_output.json

echo "🎨 Rebuilding dashboard..."
python3 -c "
import json
with open('morning_sweep_output.json') as f:
    data = json.load(f)
with open('morning_sweep_dashboard_template.html') as f:
    html = f.read()
old = \"fetch('morning_sweep_output.json').then(r=>r.json()).then(data => {\"
new = 'const data = ' + json.dumps(data, ensure_ascii=False) + ';\n{'
html = html.replace(old, new)
html = html.replace('});\n</script>', '}\n</script>')
with open('morning_sweep_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('✅ Dashboard updated! Refresh browser.')
"
