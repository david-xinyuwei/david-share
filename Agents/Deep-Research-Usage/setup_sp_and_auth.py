#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import subprocess
import logging
from datetime import datetime
from getpass import getpass

LOG_FILE = "setup_sp_and_auth.log"
CREDENTIALS_JSON = "deep_research_credentials.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

def prompt_value(label: str, default: str = "", required: bool = True, secret: bool = False) -> str:
    while True:
        prompt = f"{label}"
        if default:
            prompt += f" [{default}]"
        prompt += ": "
        try:
            val = getpass(prompt) if secret else input(prompt)
        except EOFError:
            val = ""
        val = (val or "").strip()
        if not val and default:
            val = default
        if required and not val:
            print("值不能为空，请重新输入。")
            continue
        return val

def run_cli(cmd: list, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)

def check_azure_cli() -> bool:
    try:
        run_cli(["az", "--version"])
        return True
    except Exception as e:
        logger.error("未检测到 Azure CLI，请先安装：https://learn.microsoft.com/cli/azure/install-azure-cli")
        logger.error(e)
        return False

def azure_login() -> bool:
    try:
        res = run_cli(["az", "account", "show"], check=False)
        if res.returncode == 0:
            return True
        run_cli(["az", "login"], check=True)
        return True
    except Exception as e:
        logger.error(f"Azure 登录失败: {e}")
        return False

def set_subscription(subscription_id: str) -> bool:
    try:
        run_cli(["az", "account", "set", "--subscription", subscription_id], check=True)
        return True
    except Exception as e:
        logger.error(f"设置订阅失败: {e}")
        return False

def create_service_principal(subscription_id: str, sp_name: str):
    try:
        cmd = [
            "az", "ad", "sp", "create-for-rbac",
            "--name", sp_name,
            "--role", "Contributor",
            "--scopes", f"/subscriptions/{subscription_id}",
            "--output", "json",
        ]
        out = run_cli(cmd, check=True)
        sp = json.loads(out.stdout)
        return sp["appId"], sp["password"], sp["tenant"]
    except Exception as e:
        logger.error(f"创建 Service Principal 失败: {e}")
        return None, None, None

def assign_roles(client_id: str, subscription_id: str, resource_group: str, workspace_name: str) -> bool:
    roles = [
        ("Cognitive Services Contributor", f"/subscriptions/{subscription_id}"),
        ("Cognitive Services User", f"/subscriptions/{subscription_id}"),
        ("AzureML Data Scientist", f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}"),
    ]
    ok = 0
    for role, scope in roles:
        try:
            run_cli(
                ["az", "role", "assignment", "create",
                 "--assignee", client_id, "--role", role, "--scope", scope],
                check=True,
            )
            ok += 1
        except Exception as e:
            logger.warning(f"无法分配角色 {role}: {e}")
    return ok > 0

def install_dependencies() -> bool:
    pkgs = ["azure-identity", "azure-ai-projects", "azure-ai-agents", "requests"]
    ok = 0
    for p in pkgs:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", p], check=True)
            ok += 1
        except Exception as e:
            logger.warning(f"安装依赖 {p} 失败: {e}")
    return ok == len(pkgs)

def save_credentials_json(data: dict) -> bool:
    try:
        with open(CREDENTIALS_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"凭据已保存到 {CREDENTIALS_JSON}")
        return True
    except Exception as e:
        logger.error(f"写入凭据文件失败: {e}")
        return False

def main():
    print("=== Deep-Research Service Principal 创建与授权工具 ===")
    print()

    if not check_azure_cli():
        sys.exit(1)
    if not azure_login():
        sys.exit(1)

    subscription_id = prompt_value("Azure Subscription ID")
    if not set_subscription(subscription_id):
        sys.exit(1)

    resource_group = prompt_value("Resource Group 名称", "deepresearch-resource")
    workspace_name = prompt_value("Azure ML Workspace / Project 名称", "deepresearch")
    project_endpoint = prompt_value("Project Endpoint (例如: https://<resource>.services.ai.azure.com/api/projects/<project>)")
    bing_resource_name = prompt_value("Bing Grounding 连接名称", "bing-connection")
    deep_research_model = prompt_value("Deep Research 模型部署名", "o3-deep-research")
    model_deployment = prompt_value("聊天模型部署名", "gpt-4o")

    sp_name = prompt_value("Service Principal 名称", f"deepresearch-sp-{int(time.time())}")
    client_id, client_secret, tenant_id = create_service_principal(subscription_id, sp_name)
    if not client_id or not client_secret or not tenant_id:
        sys.exit(1)

    assign_roles(client_id, subscription_id, resource_group, workspace_name)
    install_dependencies()

    data = {
        "azure_client_id": client_id,
        "azure_client_secret": client_secret,
        "azure_tenant_id": tenant_id,
        "azure_subscription_id": subscription_id,
        "project_endpoint": project_endpoint.rstrip("/"),
        "bing_resource_name": bing_resource_name,
        "deep_research_model": deep_research_model,
        "model_deployment": model_deployment,
        "resource_group": resource_group,
        "workspace_name": workspace_name,
        "service_principal_name": sp_name,
        "created_at": datetime.now().isoformat(),
    }
    save_credentials_json(data)
    print("\n✅ 创建完成。下一步：运行 python deep_research_usage.py")

if __name__ == "__main__":
    main()