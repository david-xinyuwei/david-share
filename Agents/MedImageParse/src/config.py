"""
Configuration management for MedImageParse application
Handles environment variables and Azure Key Vault integration
"""
import os
from typing import Optional
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential


class Config:
    """Application configuration with Key Vault support"""
    
    def __init__(self):
        self.key_vault_endpoint = os.getenv('AZURE_KEY_VAULT_ENDPOINT')
        self._secret_client: Optional[SecretClient] = None
        
        # Initialize Key Vault client if endpoint is configured
        if self.key_vault_endpoint:
            try:
                credential = DefaultAzureCredential()
                self._secret_client = SecretClient(
                    vault_url=self.key_vault_endpoint,
                    credential=credential
                )
            except Exception as e:
                print(f"Warning: Could not initialize Key Vault client: {e}")
    
    def _get_secret(self, secret_name: str, env_var: str) -> Optional[str]:
        """Get secret from Key Vault or fallback to environment variable"""
        # Try Key Vault first
        if self._secret_client:
            try:
                secret = self._secret_client.get_secret(secret_name)
                return secret.value
            except Exception as e:
                print(f"Warning: Could not retrieve {secret_name} from Key Vault: {e}")
        
        # Fallback to environment variable
        return os.getenv(env_var)
    
    @property
    def model_2d_endpoint(self) -> Optional[str]:
        """Get MedImageParse 2D model endpoint"""
        return self._get_secret('AZURE-OPENAI-ENDPOINT-2D', 'AZURE_OPENAI_ENDPOINT_2D')
    
    @property
    def model_2d_key(self) -> Optional[str]:
        """Get MedImageParse 2D model API key"""
        return self._get_secret('AZURE-OPENAI-KEY-2D', 'AZURE_OPENAI_KEY_2D')
    
    @property
    def model_3d_endpoint(self) -> Optional[str]:
        """Get MedImageParse 3D model endpoint"""
        return self._get_secret('AZURE-OPENAI-ENDPOINT-3D', 'AZURE_OPENAI_ENDPOINT_3D')
    
    @property
    def model_3d_key(self) -> Optional[str]:
        """Get MedImageParse 3D model API key"""
        return self._get_secret('AZURE-OPENAI-KEY-3D', 'AZURE_OPENAI_KEY_3D')
    
    @property
    def app_insights_connection_string(self) -> Optional[str]:
        """Get Application Insights connection string"""
        return self._get_secret(
            'APPLICATIONINSIGHTS-CONNECTION-STRING',
            'APPLICATIONINSIGHTS_CONNECTION_STRING'
        )
    
    def is_configured(self) -> bool:
        """Check if minimum required configuration is present"""
        return bool(
            self.model_2d_endpoint and self.model_2d_key and
            self.model_3d_endpoint and self.model_3d_key
        )


# Global config instance
config = Config()
