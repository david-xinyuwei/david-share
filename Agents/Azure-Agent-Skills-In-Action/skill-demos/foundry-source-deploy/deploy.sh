#!/bin/bash
# Deploy a Foundry Hosted Agent from source code (no Docker, no ACR).
# Source: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/deploy-hosted-agent-code
set -euo pipefail

ENDPOINT="https://ai-account-zc3svc6qlpe3k.services.ai.azure.com/api/projects/ai-project-toolbox-demo-env"
API_VERSION="2025-11-15-preview"
AGENT="hello-source-agent"
CODE_DIR="$(cd "$(dirname "$0")/agent-code" && pwd)"
ZIP="/tmp/${AGENT}.zip"
LOG="/tmp/${AGENT}-deploy.log"

echo "=== Foundry Source Code Deploy ===" | tee "$LOG"
echo "Agent: $AGENT" | tee -a "$LOG"
echo "Endpoint: $ENDPOINT" | tee -a "$LOG"
echo "Code dir: $CODE_DIR" | tee -a "$LOG"
date | tee -a "$LOG"

# 1. Get token
echo -e "\n--- Step 1: Get token ---" | tee -a "$LOG"
TOKEN=$(az account get-access-token --resource "https://ai.azure.com" --query accessToken -o tsv)
echo "Token: ${#TOKEN} chars" | tee -a "$LOG"

# 2. Build zip (flat, no wrapper folder)
echo -e "\n--- Step 2: Build zip ---" | tee -a "$LOG"
cd "$CODE_DIR"
rm -f "$ZIP"
python3 -c "
import zipfile, os
with zipfile.ZipFile('$ZIP', 'w', zipfile.ZIP_DEFLATED) as z:
    for f in ['main.py', 'requirements.txt']:
        z.write(f, f)
print('Files in zip:', [i.filename for i in zipfile.ZipFile('$ZIP').infolist()])
"
SHA=$(sha256sum "$ZIP" | cut -d' ' -f1)
echo "ZIP: $(ls -lh "$ZIP" | awk '{print $5}')" | tee -a "$LOG"
echo "SHA: $SHA" | tee -a "$LOG"

# 3. Create agent (multipart)
echo -e "\n--- Step 3: Create agent ---" | tee -a "$LOG"
RESP=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$ENDPOINT/agents?api-version=$API_VERSION" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json" \
  -H "Foundry-Features: CodeAgents=V1Preview,HostedAgents=V1Preview" \
  -H "x-ms-agent-name: $AGENT" \
  -H "x-ms-code-zip-sha256: $SHA" \
  -F "metadata=@metadata.json;type=application/json" \
  -F "code=@$ZIP;type=application/zip;filename=$AGENT.zip")

HTTP_CODE=$(echo "$RESP" | tail -1 | sed 's/HTTP_STATUS://')
BODY=$(echo "$RESP" | sed '$d')
echo "HTTP: $HTTP_CODE" | tee -a "$LOG"
echo "$BODY" | python3 -m json.tool 2>/dev/null | tee -a "$LOG" || echo "$BODY" | tee -a "$LOG"

if [ "$HTTP_CODE" = "409" ]; then
  echo "Agent exists, trying Update..." | tee -a "$LOG"
  RESP=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$ENDPOINT/agents/$AGENT?api-version=$API_VERSION" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/json" \
    -H "Foundry-Features: CodeAgents=V1Preview,HostedAgents=V1Preview" \
    -H "x-ms-code-zip-sha256: $SHA" \
    -F "metadata=@metadata.json;type=application/json" \
    -F "code=@$ZIP;type=application/zip;filename=$AGENT.zip")
  HTTP_CODE=$(echo "$RESP" | tail -1 | sed 's/HTTP_STATUS://')
  BODY=$(echo "$RESP" | sed '$d')
  echo "Update HTTP: $HTTP_CODE" | tee -a "$LOG"
  echo "$BODY" | python3 -m json.tool 2>/dev/null | tee -a "$LOG" || echo "$BODY" | tee -a "$LOG"
fi

# 4. Poll for active
echo -e "\n--- Step 4: Poll for active ---" | tee -a "$LOG"
for i in $(seq 1 60); do
  STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" \
    -H "Foundry-Features: CodeAgents=V1Preview,HostedAgents=V1Preview" \
    "$ENDPOINT/agents/$AGENT/versions/1?api-version=$API_VERSION" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "error")
  echo "  [$i] Status: $STATUS" | tee -a "$LOG"
  [ "$STATUS" = "active" ] && break
  [ "$STATUS" = "failed" ] && echo "FAILED" | tee -a "$LOG" && break
  sleep 10
done

# 5. Invoke
echo -e "\n--- Step 5: Invoke ---" | tee -a "$LOG"
INVOKE_RESP=$(curl -s -X POST "$ENDPOINT/agents/$AGENT/endpoint/protocols/openai/responses?api-version=v1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Foundry-Features: CodeAgents=V1Preview,HostedAgents=V1Preview" \
  -d '{"model":"gpt-4.1-mini","input":"What time is it? Also calculate 42 * 17 for me.","stream":false,"store":false}')

echo "$INVOKE_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Status: {d.get(\"status\",\"?\")}')
for item in d.get('output',[]):
    if item.get('type')=='message':
        for c in item.get('content',[]):
            t=c.get('text','')
            if t: print(f'Response: {t[:300]}')
    elif item.get('type')=='function_call':
        print(f'Tool: {item.get(\"name\",\"?\")}({item.get(\"arguments\",\"\")[:80]})')
" 2>/dev/null | tee -a "$LOG"

echo -e "\n=== Deploy complete ===" | tee -a "$LOG"
date | tee -a "$LOG"
echo "Log: $LOG"
