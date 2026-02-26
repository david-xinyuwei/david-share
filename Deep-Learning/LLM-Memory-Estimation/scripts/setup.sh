#!/bin/bash
# Setup script for LLM Inference Memory Estimation Tool
# Usage: ./setup.sh

set -e

echo "======================================================"
echo "  LLM Inference Memory Estimation Tool - Setup"
echo "======================================================"
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version || { echo "Error: Python 3 not found. Please install Python 3.8+"; exit 1; }

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "======================================================"
echo "  Setup completed successfully!"
echo "======================================================"
echo ""
echo "To use the tool:"
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Run the command-line tool:"
echo "     python python-estimating.py"
echo ""
echo "  3. Or run the web interface:"
echo "     streamlit run streamlit-estimating.py"
echo ""
echo "  4. Or open the Jupyter Notebook:"
echo "     jupyter notebook Estimate_the_Memory_Consumption_for_Running_LLMs_(V2).ipynb"
echo ""
echo "  5. To deactivate the virtual environment:"
echo "     deactivate"
echo "======================================================"
