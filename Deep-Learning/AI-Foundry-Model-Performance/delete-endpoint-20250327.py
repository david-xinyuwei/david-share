#!/usr/bin/env python3  
# -- coding: utf-8 --  
  
"""  
Prerequisites:  
Make sure the following dependencies are installed: pip install azure-ai-ml azure-identity  
  
Script description:  
After running, the script will sequentially ask for Azure Subscription ID, Resource Group name, and Workspace name.  
It will list all the online Endpoints under the specified Workspace.  
It will then prompt you to enter the numbers corresponding to the Endpoints you wish to delete (multiple selections are allowed).  
Finally, it will execute the deletion of the specified Endpoints.  
"""  
  
import sys  
from azure.identity import DefaultAzureCredential  
from azure.ai.ml import MLClient  
  
  
def main():  
    # Step 1: Input Subscription ID, Resource Group, and Workspace information.  
    subscription_id = input("Please enter your Azure Subscription ID: ").strip()  
    resource_group_name = input("Please enter your Azure Resource Group name: ").strip()  
    workspace_name = input("Please enter your Azure ML Workspace name: ").strip()  
  
    # Step 2: Create an MLClient for interacting with Azure ML.  
    try:  
        credential = DefaultAzureCredential()  
        ml_client = MLClient(  
            credential=credential,  
            subscription_id=subscription_id,  
            resource_group_name=resource_group_name,  
            workspace_name=workspace_name,  
        )  
    except Exception as e:  
        print("Failed to create MLClient. Please check your input or network settings.")  
        print(f"Error details: {e}")  
        sys.exit(1)  
  
    # Step 3: List the current online Endpoints in the Workspace.  
    print("\nRetrieving the list of online Endpoints in the Workspace...")  
    try:  
        endpoints = list(ml_client.online_endpoints.list())  
    except Exception as e:  
        print("Failed to retrieve the list of Endpoints. Please check your configuration and network.")  
        print(f"Error details: {e}")  
        sys.exit(1)  
  
    if not endpoints:  
        print("No online Endpoints are available in the current Workspace. Exiting the script.")  
        sys.exit(0)  
  
    print("\nList of online Endpoints:")  
    for i, endpoint in enumerate(endpoints):  
        print(f"{i + 1}. {endpoint.name}")  
  
    # Step 4: Prompt the user to specify which Endpoints to delete (support multiple numbers separated by commas).  
    to_delete_str = input(  
        "\nEnter the numbers of the Endpoints you want to delete (e.g., 1, 3, 4). "  
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
  
    # Step 5: Execute the deletion process  
    for idx in indices:  
        endpoint_name = endpoints[idx].name  
        try:  
            print(f"\nDeleting Endpoint: {endpoint_name}...")  
            delete_poller = ml_client.online_endpoints.begin_delete(name=endpoint_name)  
            delete_poller.wait()  # Wait for the deletion to complete  
            print(f"Endpoint {endpoint_name} deleted successfully.")  
        except Exception as e:  
            print(f"Failed to delete Endpoint {endpoint_name}.")  
            print(f"Error details: {e}")  
  
    print("\nThe deletion process for all specified Endpoints has been completed. Exiting the script.")  
  
  
if __name__ == "__main__":  
    main() 