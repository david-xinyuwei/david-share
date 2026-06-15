#!/usr/bin/env python3  
# -- coding: utf-8 --  
  
"""  
Prerequisites:  
Make sure the following dependencies are installed: pip install azure-ai-ml azure-identity  
  
Script description:  
Auto-detects Azure subscription, resource groups, and ML workspaces.
Lists all online Endpoints under the selected Workspace.  
Prompts you to enter the numbers corresponding to the Endpoints you wish to delete (multiple selections allowed).  
Finally, executes the deletion of the specified Endpoints.  
"""  
  
import sys  
import subprocess  
import json  
from azure.identity import DefaultAzureCredential  
from azure.ai.ml import MLClient  


def get_current_subscription():
    """Get current Azure CLI subscription"""
    try:
        result = subprocess.run(
            ["az.cmd", "account", "show", "--output", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        sub_info = json.loads(result.stdout)
        return sub_info
    except Exception as e:
        print(f"Error getting current subscription: {e}")
        return None


def get_resource_groups(subscription_id):
    """Get all resource groups in the subscription"""
    try:
        result = subprocess.run(
            ["az.cmd", "group", "list", "--subscription", subscription_id, "--output", "json"],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error getting resource groups: {e}")
        return []


def get_ml_workspaces(subscription_id, resource_group=None):
    """Get all ML workspaces in the subscription or resource group"""
    try:
        if resource_group:
            cmd = [
                "az.cmd", "ml", "workspace", "list",
                "--subscription", subscription_id,
                "--resource-group", resource_group,
                "--output", "json"
            ]
        else:
            cmd = [
                "az.cmd", "ml", "workspace", "list",
                "--subscription", subscription_id,
                "--output", "json"
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error getting ML workspaces: {e}")
        return []


def select_from_list(items, item_type, display_func):
    """Generic function to select an item from a list"""
    if not items:
        print(f"No {item_type} found.")
        return None
    
    if len(items) == 1:
        item = items[0]
        display_name = display_func(item)
        choice = input(f"\n✓ Found 1 {item_type}: {display_name}\nUse this {item_type}? (Y/n): ").strip().lower()
        if choice in ['', 'y', 'yes']:
            return item
        else:
            print(f"User declined to use the {item_type}.")
            return None
    
    print(f"\n========== Available {item_type}s ==========")
    for i, item in enumerate(items, 1):
        print(f"{i}. {display_func(item)}")
    print("=" * 50)
    
    while True:
        choice = input(f"\nSelect {item_type} by number (1-{len(items)}) or press Enter to input manually: ").strip()
        
        if not choice:
            return None  # Manual input
        
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return items[idx]
        
        print(f"Invalid selection. Please enter a number between 1 and {len(items)}.")


def main():  
    print("========== Azure ML Endpoint Deletion ==========")
    print("Detecting existing Azure resources...\n")
    
    # Step 1: Get current subscription
    sub_info = get_current_subscription()
    if not sub_info:
        print("❌ Could not detect Azure subscription. Please run 'az login' first.")
        sys.exit(1)
    
    subscription_id = sub_info['id']
    subscription_name = sub_info['name']
    
    print(f"✓ Current Azure CLI subscription:")
    print(f"  Name: {subscription_name}")
    print(f"  ID:   {subscription_id}")
    
    choice = input("\nUse this subscription? (Y/n): ").strip().lower()
    if choice not in ['', 'y', 'yes']:
        subscription_id = input("Please enter your Azure Subscription ID: ").strip()
    
    # Step 2: Get resource groups
    print("\nFetching resource groups...")
    resource_groups = get_resource_groups(subscription_id)
    
    selected_rg = select_from_list(
        resource_groups,
        "Resource Group",
        lambda rg: f"{rg['name']} (Location: {rg['location']})"
    )
    
    if selected_rg:
        resource_group_name = selected_rg['name']
    else:
        resource_group_name = input("Please enter your Resource Group name: ").strip()
    
    # Step 3: Get ML workspaces
    print("\nFetching ML workspaces...")
    workspaces = get_ml_workspaces(subscription_id, resource_group_name)
    
    selected_ws = select_from_list(
        workspaces,
        "ML Workspace",
        lambda ws: f"{ws['name']} (Location: {ws['location']}) (RG: {ws['resource_group']})"
    )
    
    if selected_ws:
        workspace_name = selected_ws['name']
    else:
        workspace_name = input("Please enter your ML Workspace name: ").strip()
    
    print("\n========== Selected Configuration ==========")
    print(f"Subscription ID: {subscription_id}")
    print(f"Resource Group:  {resource_group_name}")
    print(f"Workspace:       {workspace_name}")
    print("=" * 50)
  
    # Step 4: Create MLClient
    try:  
        credential = DefaultAzureCredential()  
        ml_client = MLClient(  
            credential=credential,  
            subscription_id=subscription_id,  
            resource_group_name=resource_group_name,  
            workspace_name=workspace_name,  
        )  
    except Exception as e:  
        print("Failed to create MLClient. Please check your configuration.")  
        print(f"Error details: {e}")  
        sys.exit(1)  
  
    # Step 5: List the current online Endpoints in the Workspace.  
    print("\n========== Available Endpoints ==========")
    print("Retrieving the list of online Endpoints...")  
    try:  
        endpoints = list(ml_client.online_endpoints.list())  
    except Exception as e:  
        print("Failed to retrieve the list of Endpoints. Please check your configuration and network.")  
        print(f"Error details: {e}")  
        sys.exit(1)  
  
    if not endpoints:  
        print("No online Endpoints found in the current Workspace. Exiting the script.")  
        sys.exit(0)  
  
    print(f"\nFound {len(endpoints)} online Endpoint(s):")  
    for i, endpoint in enumerate(endpoints):  
        print(f"{i + 1}. {endpoint.name}")
    print("=" * 50)
  
    # Step 6: Prompt the user to specify which Endpoints to delete (support multiple numbers separated by commas).  
    to_delete_str = input(  
        "\nEnter the numbers of the Endpoints you want to delete (e.g., 1, 3, 4).\n"
        "Press Enter to skip: "  
    ).strip()  
    if not to_delete_str:  
        print("No numbers entered. Exiting the script.")  
        sys.exit(0)  
  
    # Parse the user's input into a list of indices  
    indices = []  
    for s in to_delete_str.split(","):  
        s = s.strip()  # Remove any extra spaces  
        if s.isdigit():  # Check if the input is a valid number  
            idx = int(s) - 1  # Convert user-friendly number to list index (1-based to 0-based index)  
            if 0 <= idx < len(endpoints):  # Ensure the index is within range  
                indices.append(idx)  
            else:  
                print(f"Warning: Number {s} is out of range and will be ignored.")  
        else:  
            print(f"Warning: Could not parse input '{s}'. It will be ignored.")  
  
    # If no valid indices are found, exit the script  
    if not indices:  
        print("No valid Endpoint numbers detected. Exiting the script.")  
        sys.exit(0)  
  
    # Step 7: Execute the deletion process  
    print("\n========== Deleting Endpoints ==========")
    for idx in indices:  
        endpoint_name = endpoints[idx].name  
        try:  
            print(f"\nDeleting Endpoint: {endpoint_name}...")  
            delete_poller = ml_client.online_endpoints.begin_delete(name=endpoint_name)  
            delete_poller.wait()  # Wait for the deletion to complete  
            print(f"✓ Endpoint {endpoint_name} deleted successfully.")  
        except Exception as e:  
            print(f"✗ Failed to delete Endpoint {endpoint_name}.")  
            print(f"Error details: {e}")  
  
    print("\n========== Deletion Complete ==========")
    print("All specified Endpoints have been processed. Exiting the script.")  
  
  
if __name__ == "__main__":  
    main() 