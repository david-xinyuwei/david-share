#!/bin/bash

# Startup script for Azure App Service
echo "Starting LLM Memory Estimator..."

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start Streamlit
echo "Starting Streamlit app..."
streamlit run src/web_estimator.py \
  --server.port 8000 \
  --server.address 0.0.0.0 \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.serverAddress "0.0.0.0" \
  --browser.gatherUsageStats false
