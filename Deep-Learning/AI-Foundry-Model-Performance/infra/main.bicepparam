// Bicep parameters file for AI Foundry Model Performance
// This file provides default parameters for the main.bicep template
// Values can be overridden by azd environment variables

using 'main.bicep'

// Location will be set by azd from AZURE_LOCATION environment variable
// If not set, it will prompt the user
param location = readEnvironmentVariable('AZURE_LOCATION', 'eastus')

// Principal ID for role assignments (optional)
param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID', '')

// Environment name
param environmentName = readEnvironmentVariable('AZURE_ENV_NAME', 'dev')
