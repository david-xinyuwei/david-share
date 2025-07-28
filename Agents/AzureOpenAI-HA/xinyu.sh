#!/bin/bash
# 使用服务主体登录 Azure
az login --service-principal -u xx -p xxx --tenant *.com > /dev/null 2>&1

# 定义 payload 变量
payload="{\"messages\":[{\"role\":\"system\",\"content\":[{\"type\":\"text\",\"text\":\"You are an AI assistant that helps people find information.\"}]},{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"hi,1+1=?\"}]}],\"temperature\":0.7,\"top_p\":0.95,\"max_tokens\":800}"

# 定义 Traffic Manager 的名称和资源组
tm_profile="4vatm"
tm_resource_group="davidai"

# 定义两个 URL 和它们在 Traffic Manager 中的名称
endpoints1="apim-japan*.azure-api.net"
endpoints2="apim-westus*.azure-api.net"
url1="https://apim-japan*.azure-api.net/openai"
url2="https://apim-westus*.azure-api.net/openai"

# 显示两个 endpoint 的 priority
echo "##########Fetching updated priorities for both endpoints...##########"
endpoint1_priority=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name $endpoints1 --type externalEndpoints --query "priority" -o tsv)
endpoint2_priority=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name $endpoints2 --type externalEndpoints --query "priority" -o tsv)
echo "Current priority for $endpoints1 : $endpoint1_priority"
echo "Current priority for $endpoints2 : $endpoint2_priority"
# 检查 URL 状态码
check_status_code() {
    local status_code=$(curl -X POST "$1" -H "Content-Type: application/json" -d "$payload" -s -o /dev/null -w "%{http_code}")
    echo $status_code
}

# 比较状态码并根据用户输入更新 Traffic Manager 的优先级
update_priority_based_on_status_code() {
    status_code1=$(check_status_code $url1)
    status_code2=$(check_status_code $url2)

    echo "===>Status code for $url1: $status_code1"
    echo "===>Status code for $url2: $status_code2"

    if [[ "$status_code1" == "200" && "$status_code2" == "200" ]]; then
        echo "==========>Both URLs are responding with status 200. Continuing to compare speeds."
        return 0
    else
        if [[ "$status_code1" != "200" || "$status_code2" != "200" ]]; then
            read -p "One of the URLs is not responding with status 200. Do you want to update Traffic Manager priority? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                if [[ "$status_code1" == "200" ]]; then
                    faster_endpoint="$endpoints1"
                    slower_endpoint="$endpoints2"
                else
                    faster_endpoint="$endpoints2"
                    slower_endpoint="$endpoints1"
                fi
                    faster_endpoint_priority=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name "$faster_endpoint" --type externalEndpoints --query "priority" -o tsv)
                let "slower_endpoint_new_priority = $faster_endpoint_priority + 1"
                echo "Updating $slower_endpoint priority to $slower_endpoint_new_priority"
                az network traffic-manager endpoint update --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name "$slower_endpoint" --type externalEndpoints --priority $slower_endpoint_new_priority
  echo "##########Fetching updated priorities for both endpoints...##########"
  endpoint1_priority=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name $endpoints1 --type externalEndpoints --query "priority" -o tsv)
  endpoint2_priority=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name $endpoints2 --type externalEndpoints --query "priority" -o tsv)
  echo "Current priority for $endpoints1 : $endpoint1_priority"
  echo "Current priority for $endpoints2 : $endpoint2_priority"

                exit 0
            fi
        fi
        return 1
    fi
}

# 在计算平均时间的函数之前调用上述函数
update_priority_based_on_status_code


# 计算平均时间的函数
calculate_average_time() {
  local url=$1
  local total_time=0
  local count=3
  for i in $(seq 1 $count); do
    local time=$( { time curl -X POST "$url" -H "Content-Type: application/json" -d "$payload" 2>&1 1>/dev/null; } 2>&1 | grep real | awk '{print $2}' )
    local seconds=$(echo $time | awk -F'm' '{print ($1 * 60) + $2}' | sed 's/s//')
    total_time=$(echo "$total_time + $seconds" | bc)
  done
  local average=$(echo "scale=3; $total_time / $count" | bc)
  echo $average
}

# 计算两个 URL 的平均时间
average_time1=$(calculate_average_time $url1)
average_time2=$(calculate_average_time $url2)


# 比较两个 URL 的平均时间并输出结果
echo "##########Testing 3 times to calculate average response time. Please wait...##########"
difference=$(echo "$average_time1 - $average_time2" | bc)
abs_difference=${difference#-} # 获取绝对值
if (( $(echo "$average_time1 < $average_time2" | bc -l) )); then
  echo "URL $url1 is faster than $url2 on average by ${abs_difference}s with average time: ${average_time1}s"
  faster_endpoint="$endpoints1"
  slower_endpoint="$endpoints2"
else
  echo "URL $url2 is faster than $url1 on average by ${abs_difference}s with average time: ${average_time2}s"
  faster_endpoint="$endpoints2"
  slower_endpoint="$endpoints1"
fi
# 显示两个 endpoint 的 priority
echo "##########Fetching updated priorities for both endpoints...##########"
faster_endpoint_priority_updated=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name "$faster_endpoint" --type externalEndpoints --query "priority" -o tsv)
slower_endpoint_priority_updated=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name "$slower_endpoint" --type externalEndpoints --query "priority" -o tsv)

echo "Current priority for $faster_endpoint: $faster_endpoint_priority_updated"
echo "Current priority for $slower_endpoint: $slower_endpoint_priority_updated"
# 根据脚本的输出调整 Traffic Manager endpoint 的优先级
read -p "==========>Do you need or want to update Traffic Manager endpoint priorities based on the fastest region? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    faster_endpoint_priority=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name "$faster_endpoint" --type externalEndpoints --query "priority" -o tsv)

# 计算较慢的 endpoint 的新优先级
slower_endpoint_new_priority=$(echo "$faster_endpoint_priority + 1" | bc)

# 更新较慢的 endpoint 的优先级
echo "Updating $slower_endpoint priority to $slower_endpoint_new_priority"
az network traffic-manager endpoint update --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name "$slower_endpoint" --type externalEndpoints --priority $slower_endpoint_new_priority  > /dev/null 2>&1
# 显示两个 endpoint 的 priority
echo "Fetching updated priorities for both endpoints..."
faster_endpoint_priority_updated=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name "$faster_endpoint" --type externalEndpoints --query "priority" -o tsv)
slower_endpoint_priority_updated=$(az network traffic-manager endpoint show --profile-name "$tm_profile" --resource-group "$tm_resource_group" --name "$slower_endpoint" --type externalEndpoints --query "priority" -o tsv)

echo "Updated priority for $faster_endpoint: $faster_endpoint_priority_updated"
echo "Updated priority for $slower_endpoint: $slower_endpoint_priority_updated"
else
            echo "No updates will be performed based on user input."
fi