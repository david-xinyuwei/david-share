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
    command = ["az", "account", "list-locations", "--query", "[].name", "-o", "json"]  
    result = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True)  
    return json.loads(result.stdout)  
  
def get_ml_quota_in_region(region, resource_group, workspace_name):  
    command = [  
        "az", "ml", "compute", "list-usage",  
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

def query_model_supported_skus(model_name, model_version):
    """Query Azure to get the list of SKUs supported by this model."""
    try:
        result = subprocess.run(
            ["az", "ml", "model", "show",
             "--name", model_name,
             "--version", model_version,
             "--registry-name", "AzureML",
             "--query", "tags.inference_compute_allow_list",
             "-o", "tsv"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        
        # Parse the output: "['Standard_NC24ads_A100_v4', 'Standard_NC48ads_A100_v4', ...]"
        sku_list_str = result.stdout.strip()
        if sku_list_str and sku_list_str != "None":
            # Remove brackets and quotes, split by comma
            import ast
            try:
                supported_skus = ast.literal_eval(sku_list_str)
                logger.info(f"Model '{model_name}' supports SKUs: {supported_skus}")
                return supported_skus
            except:
                # Fallback: manual parsing
                sku_list_str = sku_list_str.strip("[]'\"")
                supported_skus = [s.strip().strip("'\"") for s in sku_list_str.split(",")]
                logger.info(f"Model '{model_name}' supports SKUs (fallback parsing): {supported_skus}")
                return supported_skus
        else:
            logger.warning(f"No SKU compatibility info found for model '{model_name}'")
            return None
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to query model SKU compatibility: {e}")
        return None

def get_model_compatible_skus(model_name, model_version=None, supported_skus=None):
    """
    Get compatible GPU families for a given model.
    
    Args:
        model_name: Name of the model
        model_version: Version of the model (optional, for dynamic query)
        supported_skus: Pre-queried list of supported SKUs (optional)
    
    Returns:
        List of compatible GPU families (e.g., ["A100"], ["A100", "H100"])
    """
    # If we have the actual supported SKU list, use it
    if supported_skus:
        families = set()
        for sku in supported_skus:
            if "A100" in sku:
                families.add("A100")
            elif "H100" in sku:
                families.add("H100")
        if families:
            return sorted(list(families))
    
    # Fallback to static mapping for known models
    MODEL_SKU_COMPATIBILITY = {
        "Phi-4": ["A100", "H100"],  # Supports both
        "Phi-4-mini-instruct": ["A100"],  # Only A100
        "Phi-3.5-vision-instruct": ["A100"],
        "Phi-3-vision-128k-instruct": ["A100"],
        "Phi-3-small-8k-instruct": ["A100", "H100"],
        "financial-reports-analysis": ["A100"],
        "Llama-3.2-11B-Vision-Instruct": ["A100"],
        "mistralai-Mixtral-8x7B-Instruct-v01": ["A100"],
        "Nemotron-3-8B-Chat-4k-SteerLM": ["A100"],
        "microsoft-Orca-2-7b": ["A100"],
    }
    
    for key in MODEL_SKU_COMPATIBILITY:
        if key.lower() in model_name.lower():
            logger.info(f"Using static compatibility map for '{model_name}': {MODEL_SKU_COMPATIBILITY[key]}")
            return MODEL_SKU_COMPATIBILITY[key]
    
    # Default to A100 only if model not found
    logger.warning(f"Model '{model_name}' not in compatibility map, defaulting to A100 only")
    return ["A100"]

def check_current_region_quota(subscription_id, resource_group, workspace_name):
    """Check quota in the workspace's region and return available SKU families."""
    try:
        # Get workspace location
        result = subprocess.run(
            ["az", "ml", "workspace", "show",
             "--subscription", subscription_id,
             "--resource-group", resource_group,
             "--name", workspace_name,
             "--query", "location", "-o", "tsv"],
            stdout=subprocess.PIPE, text=True, check=True
        )
        region = result.stdout.strip()
        
        # Check quota in this region
        quota_result = subprocess.run(
            ["az", "ml", "compute", "list-usage",
             "--subscription", subscription_id,
             "--resource-group", resource_group,
             "--workspace-name", workspace_name,
             "--location", region,
             "-o", "json"],
            stdout=subprocess.PIPE, text=True, check=True
        )
        
        quota_items = json.loads(quota_result.stdout)
        available_families = []
        
        for item in quota_items:
            name_dict = item.get("name", {})
            resource_name = name_dict.get("value", "")
            limit = item.get("limit", 0)
            usage = item.get("currentValue", 0)
            
            if limit > 0:
                # Map quota families to SKU types
                if "NCADSA100v4" in resource_name:
                    available_families.append(("A100", limit - usage, limit))
                elif "NCADSH100v5" in resource_name:
                    available_families.append(("H100", limit - usage, limit))
        
        return region, available_families
    except Exception as e:
        logger.warning(f"Could not check region quota: {e}")
        return None, []
  
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
# Auto-detect existing Azure resources
###############################################################################  
def get_current_subscription():
    """Get current Azure CLI subscription information."""
    try:
        result = subprocess.run(
            ["az", "account", "show", "--query", "{id:id, name:name}", "-o", "json"],
            stdout=subprocess.PIPE, text=True, check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError:
        return None

def list_resource_groups(subscription_id):
    """List all resource groups in the subscription."""
    try:
        result = subprocess.run(
            ["az", "group", "list", "--subscription", subscription_id, 
             "--query", "[].{name:name, location:location}", "-o", "json"],
            stdout=subprocess.PIPE, text=True, check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError:
        return []

def list_ml_workspaces(subscription_id, resource_group=None):
    """List all ML workspaces, optionally filtered by resource group."""
    try:
        cmd = ["az", "ml", "workspace", "list", "--subscription", subscription_id]
        if resource_group:
            cmd.extend(["--resource-group", resource_group])
        cmd.extend(["--query", "[].{name:name, resourceGroup:resource_group, location:location}", "-o", "json"])
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError:
        return []

def select_from_list(items, item_type, key_field="name"):
    """Helper to let user select from a list of items."""
    if not items:
        return None
    
    if len(items) == 1:
        print(f"\n✓ Found 1 {item_type}: {items[0][key_field]}")
        confirm = input(f"Use this {item_type}? (Y/n): ").strip().lower()
        if confirm in ['', 'y', 'yes']:
            return items[0]
    
    print(f"\n========== Available {item_type}s ==========")
    for idx, item in enumerate(items, 1):
        display_info = f"{idx}. {item[key_field]}"
        if "location" in item:
            display_info += f" (Location: {item['location']})"
        if "resourceGroup" in item:
            display_info += f" (RG: {item['resourceGroup']})"
        print(display_info)
    print("=" * 50)
    
    while True:
        choice = input(f"\nSelect {item_type} by number (1-{len(items)}) or press Enter to input manually: ").strip()
        if not choice:
            return None  # User wants manual input
        try:
            idx = int(choice)
            if 1 <= idx <= len(items):
                return items[idx - 1]
            else:
                print(f"Please enter a number between 1 and {len(items)}")
        except ValueError:
            print("Please enter a valid number or press Enter")

###############################################################################  
# Main logic  
###############################################################################  
def main():  
    print("========== Azure ML Model Deployment ==========")
    print("Detecting existing Azure resources...\n")
    
    # 1) Get current subscription
    current_sub = get_current_subscription()
    if current_sub:
        print(f"✓ Current Azure CLI subscription:")
        print(f"  Name: {current_sub['name']}")
        print(f"  ID:   {current_sub['id']}")
        use_current = input("\nUse this subscription? (Y/n): ").strip().lower()
        if use_current in ['', 'y', 'yes']:
            subscription_id = current_sub['id']
        else:
            subscription_id = input("Enter Subscription ID: ").strip()
    else:
        print("⚠ Could not detect current subscription. Please login with: az login")
        subscription_id = input("Enter Subscription ID: ").strip()
    
    # 2) Set CLI subscription  
    try:  
        subprocess.run(["az", "account", "set", "--subscription", subscription_id], check=True)  
    except subprocess.CalledProcessError as e:  
        logger.error(f"Failed to set subscription: {e}")  
        sys.exit(1)
    
    # 3) List and select resource group
    print("\nFetching resource groups...")
    resource_groups = list_resource_groups(subscription_id)
    selected_rg = select_from_list(resource_groups, "Resource Group")
    
    if selected_rg:
        resource_group = selected_rg['name']
    else:
        resource_group = input("Enter Resource Group name: ").strip()
    
    # 4) List and select ML workspace
    print("\nFetching ML workspaces...")
    workspaces = list_ml_workspaces(subscription_id, resource_group)
    selected_ws = select_from_list(workspaces, "ML Workspace")
    
    if selected_ws:
        workspace_name = selected_ws['name']
    else:
        workspace_name = input("Enter AML Workspace or AI Foundry Project name: ").strip()
    
    print("\n========== Selected Configuration ==========")
    print(f"Subscription ID: {subscription_id}")
    print(f"Resource Group:  {resource_group}")
    print(f"Workspace:       {workspace_name}")
    print("=" * 50 + "\n")  
  
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
            "az", "ml", "model", "list",  
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
  
    # 5) Query model's supported SKUs from Azure
    print("\n🔍 Querying model compatibility from Azure...")
    supported_skus = query_model_supported_skus(model_name, model_version)
    
    # 5.1) Get model-compatible GPU families
    model_compatible_families = get_model_compatible_skus(model_name, model_version, supported_skus)
    
    if supported_skus:
        print(f"✅ Model supports these SKUs: {', '.join(supported_skus[:3])}{'...' if len(supported_skus) > 3 else ''}")
    
    logger.info(f"Model '{model_name}' is compatible with GPU families: {model_compatible_families}")
  
    # 6) Check current workspace region quota
    region, available_families = check_current_region_quota(subscription_id, resource_group, workspace_name)
    
    # 7) Find intersection: what the model supports AND what quota is available
    compatible_and_available = []
    if available_families:
        available_family_names = [f[0] for f in available_families]
        compatible_and_available = [
            (family, avail, limit) 
            for family, avail, limit in available_families 
            if family in model_compatible_families
        ]
    
    # 8) Display comprehensive SKU information
    print("\n========== A100 / H100 SKU Information ==========")
    if region:
        print(f"📍 Workspace Location: {region}")
    
    print(f"\n🔧 Model '{model_name}' supports: {', '.join(model_compatible_families)} GPUs")
    
    if available_families:
        print(f"\n✅ Available GPU Quota in this region:")
        for family, available, limit in available_families:
            compat_marker = "✅" if family in model_compatible_families else "⚠️ (not compatible with this model)"
            print(f"   - {family}: {available}/{limit} cores available {compat_marker}")
    else:
        print("\n⚠️  Could not detect quota information")
    
    if compatible_and_available:
        print(f"\n🎯 COMPATIBLE & AVAILABLE (recommended for this model):")
        for family, available, limit in compatible_and_available:
            print(f"   - {family}: {available}/{limit} cores available")
    else:
        print(f"\n❌ WARNING: No GPU quota available that is compatible with model '{model_name}'!")
        print(f"   Model needs: {', '.join(model_compatible_families)}")
        if available_families:
            available_names = [f[0] for f in available_families]
            print(f"   Region has: {', '.join(available_names)}")
        print("\n   Options:")
        print("   1. Choose a different model that supports available GPUs")
        print("   2. Request quota for compatible GPUs in this region")
        print("   3. Deploy workspace to a region with compatible GPU quota")
        print()
    
    print()
    
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
    
    print("💡 Tip: To check GPU quota across all regions, run:")
    print("   bash scripts/deployment/check-gpu-quota.sh")
    print()
    
    # Show recommended SKUs based on actual model support AND quota availability
    if supported_skus and compatible_and_available:
        print("📌 RECOMMENDED SKUs (model supports AND have quota):")
        
        # Map of SKU to required cores
        sku_core_requirements = {
            "Standard_NC24ads_A100_v4": 24,
            "Standard_NC48ads_A100_v4": 48,
            "Standard_NC96ads_A100_v4": 96,
            "Standard_NC40ads_H100_v5": 40,
            "Standard_NC80ads_H100_v5": 80,
            "Standard_ND96isr_H100_v5": 96,
            "Standard_ND96asr_v4": 96,
            "Standard_ND96amsr_A100_v4": 96,
        }
        
        # Check each model-supported SKU against available quota
        has_usable_sku = False
        for sku in supported_skus:
            required_cores = sku_core_requirements.get(sku, 999)  # Default to high number if unknown
            
            # Determine GPU family for this SKU
            sku_family = None
            if "A100" in sku:
                sku_family = "A100"
            elif "H100" in sku:
                sku_family = "H100"
            
            # Check if we have quota for this family
            if sku_family:
                for family, available, limit in compatible_and_available:
                    if family == sku_family:
                        if available >= required_cores:
                            print(f"   ✅ {sku} (requires {required_cores} cores, {available} available)")
                            has_usable_sku = True
                        else:
                            print(f"   ❌ {sku} (requires {required_cores} cores, only {available} available)")
        
        if not has_usable_sku:
            print("\n   ⚠️  WARNING: No model-supported SKU has sufficient quota!")
            print(f"   Model needs one of: {', '.join(supported_skus[:3])}{'...' if len(supported_skus) > 3 else ''}")
            for family, available, limit in compatible_and_available:
                print(f"   You have: {available} {family} cores available")
        print()
    elif available_families:
        # Have quota but model SKU list not available (fallback to generic recommendation)
        print("📌 RECOMMENDED SKUs (based on available quota, verify model compatibility):")
        for family, available, limit in available_families:
            if family == "A100":
                if available >= 24:
                    print(f"   - Standard_NC24ads_A100_v4 (requires 24 cores, {available} available)")
                if available >= 48:
                    print(f"   - Standard_NC48ads_A100_v4 (requires 48 cores, {available} available)")
                if available >= 96:
                    print(f"   - Standard_NC96ads_A100_v4 (requires 96 cores, {available} available)")
            elif family == "H100":
                if available >= 40:
                    print(f"   - Standard_NC40ads_H100_v5 (requires 40 cores, {available} available)")
                if available >= 80:
                    print(f"   - Standard_NC80ads_H100_v5 (requires 80 cores, {available} available)")
                if available >= 96:
                    print(f"   - Standard_ND96isr_H100_v5 (requires 96 cores, {available} available)")
        print()
    else:
        # Have quota but not compatible with model (shouldn't reach here with new logic)
        print("⚠️  SKUs with available quota (but may NOT be compatible with this model):")
        for family, available, limit in available_families:
            if family == "A100":
                print(f"   - Standard_NC24ads_A100_v4 (A100 - check model compatibility)")
                print(f"   - Standard_NC48ads_A100_v4 (A100 - check model compatibility)")
                print(f"   - Standard_NC96ads_A100_v4 (A100 - check model compatibility)")
            elif family == "H100":
                print(f"   - Standard_NC40ads_H100_v5 (H100 - check model compatibility)")
                print(f"   - Standard_NC80ads_H100_v5 (H100 - check model compatibility)")
        print()
    
    print("Available SKUs (for reference):")  
    for sku in INSTANCE_TYPES:  
        # Mark which ones are actually usable
        sku_family = "A100" if "A100" in sku else "H100" if "H100" in sku else "Unknown"
        is_compatible = sku_family in model_compatible_families
        has_quota = any(f[0] == sku_family and f[1] > 0 for f in available_families) if available_families else False
        
        marker = ""
        if is_compatible and has_quota:
            marker = " ✅ (Recommended)"
        elif not is_compatible:
            marker = " ⚠️ (Model incompatible)"
        elif not has_quota:
            marker = " ❌ (No quota)"
            
        print(f" - {sku}{marker}")  
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