#!/bin/bash

# Azure OpenAI API 调用脚本，用于生成图像。

# 请在此处填写你的 Azure OpenAI endpoint 与 API 密钥
ENDPOINT="https://xinyu-m9xli6n9-westus3.cognitiveservices.azure.com"
DEPLOYMENT="gpt-image-1"
API_VERSION="2025-04-01-preview"
AZURE_API_KEY="G97Q"

# 默认参数配置
PROMPT=${1:-"A photograph of a red fox in an autumn forest"}
OUTPUT_IMAGE=${2:-"generated_image.png"}
SIZE=${3:-"1024x1024"}        # 可选：1024x1024、512x512 等
QUALITY=${4:-"medium"}        # 可选："low"、"medium"、"high"
NUMBER=${5:-"1"}              # 一次生成图片数量，默认是 1

# 使用独立文件保存响应头和内容
HEADERS_FILE=$(mktemp)
RESPONSE_BODY=$(mktemp)

# 执行 curl 请求，捕获响应头和正文
curl -X POST "$ENDPOINT/openai/deployments/$DEPLOYMENT/images/generations?api-version=$API_VERSION" \
  -H "Content-Type: application/json" \
  -H "api-key: $AZURE_API_KEY" \
  -d "{
     \"prompt\" : \"$PROMPT\",
     \"size\" : \"$SIZE\",
     \"quality\" : \"$QUALITY\",
     \"n\" : $NUMBER
    }" \
  -D "$HEADERS_FILE" \
  -o "$RESPONSE_BODY"

# 提取 request_id（从响应头中）
request_id=$(grep -Fi "x-request-id" "$HEADERS_FILE" | awk '{print $2}' | tr -d '\r')

# 提取 Base64 图像数据并写入图片文件
jq -r '.data[0].b64_json' "$RESPONSE_BODY" | base64 --decode > "$OUTPUT_IMAGE"

# 输出结果
echo "图片已生成并保存为: $OUTPUT_IMAGE"
echo "Request ID: $request_id"

# 删除临时文件
rm "$HEADERS_FILE" "$RESPONSE_BODY"