#!/bin/bash
# ==============================================================================
# Complete Testing Workflow Script for AI Foundry Model Performance
# ==============================================================================
# Prerequisites: Azure infrastructure must be deployed first with 'azd up'
# 
# This script automates the testing workflow:
# 1. Check GPU quota across Azure regions
# 2. Deploy AI model to endpoint
# 3. Run stress testing / performance testing
# 4. Generate test report and save to testlogs/
# 5. (Optional) Clean up endpoint after testing
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Banner
echo "=========================================================================="
echo "   AI Foundry Model Performance Testing - Complete Workflow"
echo "=========================================================================="
echo ""
echo "Prerequisites:"
echo "  ✓ Azure infrastructure must be deployed first with 'azd up'"
echo "  ✓ Azure CLI and Python 3 must be installed"
echo ""

# ==============================================================================
# Step 1: Check prerequisites
# ==============================================================================
log_info "Checking prerequisites..."

if ! command -v az &> /dev/null; then
    log_error "Azure CLI (az) is not installed."
    echo "Install it from: https://learn.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is not installed."
    exit 1
fi

log_success "All prerequisites are installed."
echo ""

# ==============================================================================
# Step 2: Load Environment
# ==============================================================================
log_info "Step 1/5: Load Azure Environment"
echo "----------------------------------------"

# Try to load from .env file first
if [ -f .env ]; then
    log_info "Loading environment from .env file..."
    source .env
    log_success "Environment loaded:"
    echo "  Subscription ID:  $AZURE_SUBSCRIPTION_ID"
    echo "  Resource Group:   $AZURE_RESOURCE_GROUP"
    echo "  ML Workspace:     $AZURE_ML_WORKSPACE_NAME"
else
    log_warning ".env file not found. Please enter your Azure environment information:"
    read -p "Subscription ID: " AZURE_SUBSCRIPTION_ID
    read -p "Resource Group: " AZURE_RESOURCE_GROUP
    read -p "ML Workspace Name: " AZURE_ML_WORKSPACE_NAME
    
    # Save to .env for future use
    cat > .env <<EOF
AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID
AZURE_RESOURCE_GROUP=$AZURE_RESOURCE_GROUP
AZURE_ML_WORKSPACE_NAME=$AZURE_ML_WORKSPACE_NAME
EOF
    log_success "Environment info saved to .env file"
fi

# Export variables for Python scripts
export AZURE_SUBSCRIPTION_ID
export AZURE_RESOURCE_GROUP
export AZURE_ML_WORKSPACE_NAME

# Set Azure CLI subscription
log_info "Setting Azure CLI subscription..."
az account set --subscription "$AZURE_SUBSCRIPTION_ID"
log_success "Azure CLI configured."

echo ""

# ==============================================================================
# Step 3: Deploy AI Model
# ==============================================================================
log_info "Step 2/5: Deploy AI Model to Endpoint"
echo "----------------------------------------"
log_info "This script will:"
echo "  • Query GPU quota across all Azure regions"
echo "  • Show available GPU SKUs (A100/H100)"
echo "  • Deploy selected model to endpoint"
echo ""

read -p "Do you want to deploy AI model now? [Y/n]: " deploy_models

if [[ ! "$deploy_models" =~ ^[Nn]$ ]]; then
    log_info "Running model deployment script..."
    log_info "Please follow the prompts in the deployment script..."
    echo ""
    
    # Run the deployment script
    python3 scripts/deployment/deploymodels-linux-20250405.py
    
    if [ $? -eq 0 ]; then
        log_success "Model deployment completed!"
        echo ""
        log_info "Please save the endpoint information from above."
        log_warning "You will need the Scoring URI and Primary Key for testing."
        echo ""
        read -p "Press Enter to continue to testing phase..."
    else
        log_error "Model deployment failed!"
        exit 1
    fi
else
    log_warning "Skipping model deployment."
    log_info "Loading existing endpoint information..."
    read -p "Enter the endpoint scoring URI: " SCORING_URI
    read -p "Enter the endpoint primary key: " PRIMARY_KEY
    export SCORING_URI
    export PRIMARY_KEY
fi

echo ""

# ==============================================================================
# Step 4: Run Stress Testing / Performance Testing
# ==============================================================================
log_info "Step 3/5: Run Stress Testing / Performance Testing"
echo "----------------------------------------"

read -p "Do you want to run performance/stress tests now? [Y/n]: " run_tests

if [[ ! "$run_tests" =~ ^[Nn]$ ]]; then
    log_info "Available test scenarios:"
    echo ""
    echo "  === Text Generation Models ==="
    echo "  1) Phi-4 - Stress test (multiple concurrent requests)"
    echo "  2) Llama 3.2 11B Vision - Multimodal test"
    echo "  3) Mixtral 8x7B - Large model performance test"
    echo "  4) Orca 2 - Instruction-following test"
    echo "  5) Nemotron 3 8B - SteerLM capability test"
    echo ""
    echo "  === Specialized Models ==="
    echo "  6) Financial Reports Analysis - Domain-specific test"
    echo "  7) Whisper - Audio transcription test"
    echo "  8) SwinV2 - Computer vision test"
    echo ""
    echo "  === Advanced Options ==="
    echo "  9) Concurrency test (configurable threads)"
    echo "  10) Custom test script"
    echo "  11) Skip tests"
    echo ""
    
    read -p "Enter choice [1-11]: " test_choice
    
    # Create testlogs directory if it doesn't exist
    mkdir -p testlogs
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    
    case $test_choice in
        1)
            log_info "Running Phi-4 stress test..."
            TEST_LOG="testlogs/phi4-test-${TIMESTAMP}.txt"
            python3 scripts/testing/press-phi4-0403.py 2>&1 | tee "$TEST_LOG"
            log_success "Test results saved to: $TEST_LOG"
            ;;
        2)
            log_info "Running Llama 3.2 11B Vision test..."
            TEST_LOG="testlogs/llama32-test-${TIMESTAMP}.txt"
            python3 scripts/testing/press-llama3.211bv-20250407.py 2>&1 | tee "$TEST_LOG"
            log_success "Test results saved to: $TEST_LOG"
            ;;
        3)
            log_info "Running Mixtral 8x7B performance test..."
            TEST_LOG="testlogs/mixtral-test-${TIMESTAMP}.txt"
            python3 scripts/testing/press-Mixtral-8x7B-20250323.py 2>&1 | tee "$TEST_LOG"
            log_success "Test results saved to: $TEST_LOG"
            ;;
        4)
            log_info "Running Orca 2 test..."
            TEST_LOG="testlogs/orca-test-${TIMESTAMP}.txt"
            python3 scripts/testing/press-orca-20250324.py 2>&1 | tee "$TEST_LOG"
            log_success "Test results saved to: $TEST_LOG"
            ;;
        5)
            log_info "Running Nemotron 3 8B test..."
            TEST_LOG="testlogs/nemotron-test-${TIMESTAMP}.txt"
            python3 scripts/testing/press-nemotron-3-8b-chat-4k-steerlm-20250324.py 2>&1 | tee "$TEST_LOG"
            log_success "Test results saved to: $TEST_LOG"
            ;;
        6)
            log_info "Running Financial Reports Analysis test..."
            TEST_LOG="testlogs/financial-test-${TIMESTAMP}.txt"
            python3 scripts/testing/press.financial-reports-analysis-20250321.py 2>&1 | tee "$TEST_LOG"
            log_success "Test results saved to: $TEST_LOG"
            ;;
        7)
            log_info "Running Whisper audio transcription test..."
            TEST_LOG="testlogs/whisper-test-${TIMESTAMP}.txt"
            python3 scripts/testing/press-whisper-20250323.py 2>&1 | tee "$TEST_LOG"
            log_success "Test results saved to: $TEST_LOG"
            ;;
        8)
            log_info "Running SwinV2 computer vision test..."
            TEST_LOG="testlogs/swinv2-test-${TIMESTAMP}.txt"
            python3 scripts/testing/press-swinv2-20250322.py 2>&1 | tee "$TEST_LOG"
            log_success "Test results saved to: $TEST_LOG"
            ;;
        9)
            log_info "Running Concurrency test..."
            TEST_LOG="testlogs/concurrency-test-${TIMESTAMP}.txt"
            python3 scripts/testing/concurrency_test.py 2>&1 | tee "$TEST_LOG"
            log_success "Test results saved to: $TEST_LOG"
            ;;
        10)
            read -p "Enter test script path (e.g., scripts/testing/press-phi4-0403.py): " custom_script
            if [ -f "$custom_script" ]; then
                log_info "Running custom test script..."
                TEST_LOG="testlogs/custom-test-${TIMESTAMP}.txt"
                python3 "$custom_script" 2>&1 | tee "$TEST_LOG"
                log_success "Test results saved to: $TEST_LOG"
            else
                log_error "Test script not found: $custom_script"
                exit 1
            fi
            ;;
        11)
            log_warning "Skipping performance tests."
            ;;
        *)
            log_error "Invalid choice."
            exit 1
            ;;
    esac
    
    echo ""
    log_success "Testing phase completed!"
    log_info "Test results are available in the testlogs/ directory."
else
    log_warning "Skipping performance tests."
fi

echo ""

# ==============================================================================
# Step 5: Cleanup (Optional)
# ==============================================================================
log_info "Step 4/5: Cleanup Endpoint (Optional)"
echo "----------------------------------------"

read -p "Do you want to delete the endpoint now? [y/N]: " cleanup_endpoint

if [[ "$cleanup_endpoint" =~ ^[Yy]$ ]]; then
    log_warning "Running endpoint cleanup script..."
    python3 scripts/deployment/delete-endpoint-20250327.py
    log_success "Endpoint cleanup completed!"
else
    log_info "Skipping endpoint cleanup."
    log_warning "Remember to delete the endpoint later to avoid charges:"
    echo "  python3 scripts/deployment/delete-endpoint-20250327.py"
fi

echo ""

# ==============================================================================
# Step 6: Summary
# ==============================================================================
log_success "=========================================================================="
log_success "   Complete Workflow Finished!"
log_success "=========================================================================="
echo ""
echo "Summary:"
echo "  ✓ Environment loaded from: .env"
if [[ ! "$deploy_models" =~ ^[Nn]$ ]]; then
    echo "  ✓ Model deployed to endpoint"
fi
if [[ ! "$run_tests" =~ ^[Nn]$ ]]; then
    echo "  ✓ Performance tests executed"
    echo "  ✓ Test results saved to: testlogs/"
fi
if [[ "$cleanup_endpoint" =~ ^[Yy]$ ]]; then
    echo "  ✓ Endpoint cleaned up"
fi
echo ""
echo "Next Steps:"
echo ""
echo "  📊 View Test Results:"
echo "     cat testlogs/*.txt"
echo "     # Or open testlogs/ directory to view detailed results"
echo ""
echo "  🔄 Run Another Test:"
echo "     bash scripts/deployment/deploy-all.sh"
echo ""
echo "  📝 Manually Run Individual Scripts:"
echo "     • Deploy model:  python3 scripts/deployment/deploymodels-linux-20250405.py"
echo "     • Run test:      python3 scripts/testing/press-phi4-0403.py"
echo "     • Delete endpoint: python3 scripts/deployment/delete-endpoint-20250327.py"
echo ""
echo "  🌐 View Resources in Azure Portal:"
echo "     https://portal.azure.com/#@/resource/subscriptions/$AZURE_SUBSCRIPTION_ID/resourceGroups/$AZURE_RESOURCE_GROUP"
echo ""
echo "  🧹 Clean Up All Resources:"
echo "     azd down --purge --force"
echo ""
log_info "For more information, see README.md"
echo "=========================================================================="
echo ""
