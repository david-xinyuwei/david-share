#!/usr/bin/env python3  
# -- coding: utf-8 --  
  
import sys  
import subprocess  
import json  
import time  
import logging  
  
from azure.identity import DefaultAzureCredential  
from azure.ai.ml import MLClient  
from azure.ai.ml.entities import ManagedOnlineEndpoint, ManagedOnlineDeployment, OnlineRequestSettings, ProbeSettings  
  
###############################################################################  
# Logger setup  
###############################################################################  
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")  
logger = logging.getLogger(__name__)  
  
###############################################################################  
# Helper: prompt_or_default  
###############################################################################  
def prompt_or_default(prompt_text, default_value=None):  
    """Prompt the user for input, with a default value fallback."""  
    while True:  
        user_input = input(prompt_text).strip()  
        if user_input:  
            return user_input  
        if default_value is not None:  
            return default_value  
        else:  
            print("Input is mandatory. Please try again.")  
  
###############################################################################  
# Query GPU quotas (optional)  
###############################################################################  
def get_all_valid_regions():  
    command = ["az.cmd", "account", "list-locations", "--query", "[].name", "-o", "json"]  
    result = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True)  
    return json.loads(result.stdout)  
  
def get_ml_quota_in_region(region, resource_group, workspace_name):  
    command = [  
        "az.cmd", "ml", "compute", "list-usage",  
        "--resource-group", resource_group,  
        "--workspace-name", workspace_name,  
        "--location", region,  
        "-o", "json"  
    ]  
    result = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True)  
    return json.loads(result.stdout)  
  
def check_gpu_quota(resource_group, workspace_name):  
    """Briefly print GPU quota information (Limit > 1) to help users understand available quotas."""  
    KEYWORDS = ["NCADSA100v4", "NCADSH100v5"]  
    SUPPORTED_AML_REGIONS = {  
        "northcentralus", "canadacentral", "centralindia", "uksouth", "westus",  
        "centralus", "eastasia", "japaneast", "japanwest", "westus3", "jioindiawest",  
        "germanywestcentral", "switzerlandnorth", "uaenorth", "southafricanorth",  
        "norwayeast", "eastus", "northeurope", "koreacentral", "brazilsouth",  
        "francecentral", "australiaeast", "eastus2", "westus2", "westcentralus",  
        "southeastasia", "westeurope", "southcentralus", "canadaeast", "swedencentral",  
        "ukwest", "australiasoutheast", "qatarcentral", "southindia", "polandcentral",  
        "switzerlandwest", "italynorth", "spaincentral", "israelcentral"  
    }  
  
    try:  
        all_regions = get_all_valid_regions()  
    except subprocess.CalledProcessError as e:  
        logger.error(f"Failed to fetch region list: {e}")  
        return  
  
    to_query = [r for r in all_regions if r in SUPPORTED_AML_REGIONS]  
    print("\n========== GPU Quota (Limit > 1) ==========")  
    print("Region,ResourceName,LocalizedValue,Usage,Limit")  
  
    for region in to_query:  
        try:  
            quota_items = get_ml_quota_in_region(region, resource_group, workspace_name)  
            if not isinstance(quota_items, list):  
                continue  
            for item in quota_items:  
                name_dict = item.get("name", {})  
                resource_name = name_dict.get("value", "")  
                localized_value = name_dict.get("localizedValue", "")  
                usage = item.get("currentValue", 0)  
                limit = item.get("limit", 0)  
                if limit > 1:  
                    combined_str = (resource_name + " " + localized_value).lower()  
                    if any(kw.lower() in combined_str for kw in KEYWORDS):  
                        print(f"{region},{resource_name},{localized_value},{usage},{limit}")  
        except subprocess.CalledProcessError as e:  
            logger.warning(f"Failed to query region {region}: {e}")  
  
###############################################################################  
# Prepare available SKUs  
###############################################################################  
INSTANCE_TYPES = [  
    "Standard_NC24ads_A100_v4",  
    "Standard_NC48ads_A100_v4",  
    "Standard_NC96ads_A100_v4",  
    "Standard_NC40ads_H100_v5",  
    "Standard_NC80ads_H100_v5"  
]  
  
###############################################################################  
# Model deployment  
###############################################################################  
def deploy_model(subscription_id, resource_group, workspace_name, model_name, model_version, instance_type, instance_count):  
    """Deploy the model and return (endpoint_name, scoring_uri, primary_key, secondary_key)."""  
  
    # Compose model URI  
    model_id = f"azureml://registries/AzureML/models/{model_name}/versions/{model_version}"  
    logger.info(f"Model ID: {model_id}")  
  
    # Init client  
    credential = DefaultAzureCredential()  
    ml_client = MLClient(credential, subscription_id, resource_group, workspace_name)  
  
    # Create endpoint  
    endpoint_name = f"custom-endpoint-{int(time.time())}"  
    endpoint = ManagedOnlineEndpoint(  
        name=endpoint_name,  
        auth_mode="key",  
        description=f"Deploy model {model_name}"  
    )  
    logger.info(f"Creating Endpoint: {endpoint_name}")  
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()  
  
    # Create deployment  
    deployment_name = "custom-deployment"  
    deployment = ManagedOnlineDeployment(  
        name=deployment_name,  
        endpoint_name=endpoint_name,  
        model=model_id,  
        instance_type=instance_type,  
        instance_count=instance_count,  
        request_settings=OnlineRequestSettings(  
            max_concurrent_requests_per_instance=1,  
            request_timeout_ms=90000  # 90秒，与UI部署相同  
        ),  
        liveness_probe=ProbeSettings(  
            failure_threshold=30,  
            initial_delay=600,  # 600秒，与UI部署相同  
            period=10,  
            success_threshold=1,  
            timeout=2  
        ),  
        readiness_probe=ProbeSettings(  
            failure_threshold=30,  
            initial_delay=10,  # UI部署里 readiness_probe 仍是10秒  
            period=10,  
            success_threshold=1,  
            timeout=2  
        )  
    )  
  
    logger.info(f"Deploying model {model_name} to Endpoint {endpoint_name} ...")  
    ml_client.online_deployments.begin_create_or_update(deployment).result()  
  
    # Route 100% traffic  
    endpoint.traffic = {deployment_name: 100}  
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()  
  
    # Get scoring URI and keys  
    endpoint = ml_client.online_endpoints.get(endpoint_name)  
    scoring_uri = endpoint.scoring_uri  
  
    keys = ml_client.online_endpoints.get_keys(endpoint_name)  
    primary_key = keys.primary_key  
    secondary_key = keys.secondary_key  
  
    logger.info("\n===== Deployment Successful. Endpoint Information =====")  
    logger.info(f"Endpoint name: {endpoint_name}")  
    logger.info(f"Scoring URI:   {scoring_uri}")  
    logger.info(f"Primary Key:   {primary_key}")  
    logger.info(f"Secondary Key: {secondary_key}")  
  
    example_code = f'''import requests  
headers = {{"Authorization": "Bearer {primary_key}", "Content-Type": "application/json"}}  
data = {{"input_data": {{"input_string": [{{"role": "user","content": "Your prompt here"}}],"parameters": {{"max_new_tokens": 50}}}}}}  
response = requests.post("{scoring_uri}", headers=headers, json=data)  
print(response.json())'''  
  
    logger.info("You can test the deployment using the following code:\n" + example_code)  
  
    return endpoint_name, scoring_uri, primary_key, secondary_key  
  
###############################################################################  
# Main logic  
###############################################################################  
def main():  
    # 1) Collect subscription, resource group, and workspace information  
    print("========== Enter Basic Information ==========")  
    subscription_id = prompt_or_default("Subscription ID: ")  
    resource_group = prompt_or_default("Resource Group: ")  
    workspace_name = prompt_or_default("AML Workspace Name or AI Foundry Poject Name: ")  
  
    # 2) Set CLI subscription  
    try:  
        subprocess.run(["az.cmd", "account", "set", "--subscription", subscription_id], check=True)  
    except subprocess.CalledProcessError as e:  
        logger.error(f"Failed to set subscription: {e}")  
        sys.exit(1)  
  
    # 3) Prompt user for model name and version  
    example_models = [  
        "Phi-4", "Phi-3.5-vision-instruct", "financial-reports-analysis",  
        "databricks-dbrx-instruct", "Llama-3.2-11B-Vision-Instruct",  
        "Phi-3-small-8k-instruct", "Phi-3-vision-128k-instruct",  
        "microsoft-swinv2-base-patch4-window12-192-22k",  
        "mistralai-Mixtral-8x7B-Instruct-v01", "Muse",  
        "openai-whisper-large", "snowflake-arctic-base",  
        "Nemotron-3-8B-Chat-4k-SteerLM",  
        "stabilityai-stable-diffusion-xl-refiner-1-0",  
        "microsoft-Orca-2-7b"  
    ]  
    print("\n========== Model Name Examples ==========")  
    for m in example_models:  
        print(f" - {m}")  
    print("==========================================\n")  
  
    partial_str = prompt_or_default("Enter the model name to search (e.g., 'Phi-4'): ", "Phi-4")  
    print("\n========== Matching Models ==========")  
    try:  
        subprocess.run([  
            "az.cmd", "ml", "model", "list",  
            "--registry-name", "AzureML",  
            "--query", f"[?contains(name, '{partial_str}')]",  
            "-o", "table"  
        ], check=True)  
    except subprocess.CalledProcessError as e:  
        logger.error(f"Failed to query models: {e}")  
        sys.exit(1)  
  
    # 4) Get full model name and version from user  
    print("\nNote: The above table is for reference only. Enter the exact model name below:")  
    model_name = input("Enter full model name (case-sensitive): ").strip()  
    if not model_name:  
        logger.error("Model name is empty. Exiting.")  
        sys.exit(1)  
  
    model_version = input("Enter model version (e.g., 7): ").strip()  
    if not model_version:  
        logger.error("Model version is empty. Exiting.")  
        sys.exit(1)  
  
    logger.info(f"User-specified model: name='{model_name}', version='{model_version}'")  
  
    # 5) (Optional) Query GPU quotas  
    check_gpu_quota(resource_group, workspace_name)  
  
    # 6) Display available SKU information  
    print("\n========== A100 / H100 SKU Information ==========")  
    print(f"{'SKU Name':<35} {'GPU Count':<10} {'GPU Memory (VRAM)':<20} {'CPU Cores':<10}")  
    print(f"{'-'*35} {'-'*10} {'-'*20} {'-'*10}")  
    sku_table = [  
        ("Standard_NC24ads_A100_v4", "1", "80 GB", "24"),  
        ("Standard_NC48ads_A100_v4", "2", "160 GB (2x80 GB)", "48"),  
        ("Standard_NC96ads_A100_v4", "4", "320 GB (4x80 GB)", "96"),  
        ("Standard_NC40ads_H100_v5", "1", "80 GB", "40"),  
        ("Standard_NC80ads_H100_v5", "2", "160 GB (2x80 GB)", "80"),  
    ]  
    for sku, gpu_count, vram, cpu_cores in sku_table:  
        print(f"{sku:<35} {gpu_count:<10} {vram:<20} {cpu_cores:<10}")  
    print()  
    print("Available SKUs:")  
    for sku in INSTANCE_TYPES:  
        print(f" - {sku}")  
    print()  
  
    instance_type = input("Enter the SKU to use: ").strip()  
    if instance_type not in INSTANCE_TYPES:  
        logger.error(f"SKU '{instance_type}' is not in the available list. Exiting.")  
        sys.exit(1)  
  
    try:  
        instance_count = int(input("Enter the number of instances (integer): "))  
    except ValueError:  
        logger.error("Instance count must be an integer. Exiting.")  
        sys.exit(1)  
  
    # 7) Deploy the model  
    endpoint_name, scoring_uri, primary_key, secondary_key = deploy_model(  
        subscription_id=subscription_id,  
        resource_group=resource_group,  
        workspace_name=workspace_name,  
        model_name=model_name,  
        model_version=model_version,  
        instance_type=instance_type,  
        instance_count=instance_count  
    )  
  
    # 8) Display deployment results  
    logger.info("========== Deployment Completed ==========")  
    logger.info(f"Endpoint name: {endpoint_name}")  
    logger.info(f"Scoring URI:   {scoring_uri}")  
    logger.info(f"Primary Key:   {primary_key}")  
    logger.info(f"Secondary Key: {secondary_key}")  
  
    print("\n----- Deployment Information -----")  
    print(f"ENDPOINT_NAME={endpoint_name}")  
    print(f"SCORING_URI={scoring_uri}")  
    print(f"PRIMARY_KEY={primary_key}")  
    print(f"SECONDARY_KEY={secondary_key}")  
  
if __name__ == "__main__":  
    main()  