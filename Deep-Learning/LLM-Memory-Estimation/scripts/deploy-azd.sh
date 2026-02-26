#!/bin/bash

# Azure Developer CLI Deployment Script for Linux/Mac

ENVIRONMENT_NAME="${1:-dev}"
LOCATION="${2:-eastus}"

echo "========================================"
echo "  Azure Developer CLI Deployment"
echo "========================================"
echo ""

# Check if azd is installed
echo "Checking Azure Developer CLI..."
if ! command -v azd &> /dev/null; then
    echo "Error: Azure Developer CLI (azd) not found."
    echo ""
    echo "Install it with:"
    echo "  curl -fsSL https://aka.ms/install-azd.sh | bash"
    echo ""
    echo "Or visit: https://aka.ms/install-azd"
    exit 1
fi
echo "✓ Azure Developer CLI found"
echo ""

# Initialize environment
echo "Initializing Azure Developer CLI environment..."
azd env new "$ENVIRONMENT_NAME"

# Set location
echo "Setting location to $LOCATION..."
azd env set AZURE_LOCATION "$LOCATION"

# Deploy
echo ""
echo "Starting deployment..."
echo "This will:"
echo "  1. Provision Azure resources (App Service, Application Insights)"
echo "  2. Build and package your application"
echo "  3. Deploy to Azure Web App"
echo "  4. Configure HTTPS and monitoring"
echo ""

azd up

echo ""
echo "========================================"
echo "  Deployment Complete!"
echo "========================================"
echo ""
echo "View your app:"
azd env get-values | grep WEB_URI
echo ""
echo "Useful commands:"
echo "  azd monitor        - View application logs and metrics"
echo "  azd deploy         - Deploy code changes"
echo "  azd down           - Delete all Azure resources"
echo ""
