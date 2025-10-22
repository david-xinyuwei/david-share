"""
Unit tests for configuration module
"""
import pytest
from unittest.mock import Mock, patch
from src.config import Config


def test_config_initialization():
    """Test Config initialization"""
    config = Config()
    assert config is not None


@patch('src.config.os.getenv')
def test_config_fallback_to_env(mock_getenv):
    """Test fallback to environment variables when Key Vault unavailable"""
    mock_getenv.side_effect = lambda key: {
        'AZURE_OPENAI_ENDPOINT_2D': 'https://test-2d.com',
        'AZURE_OPENAI_KEY_2D': 'test-key-2d',
        'AZURE_OPENAI_ENDPOINT_3D': 'https://test-3d.com',
        'AZURE_OPENAI_KEY_3D': 'test-key-3d',
    }.get(key)
    
    config = Config()
    assert config.model_2d_endpoint == 'https://test-2d.com'
    assert config.model_2d_key == 'test-key-2d'
    assert config.model_3d_endpoint == 'https://test-3d.com'
    assert config.model_3d_key == 'test-key-3d'


def test_config_is_configured():
    """Test is_configured method"""
    with patch('src.config.os.getenv') as mock_getenv:
        # All config present
        mock_getenv.side_effect = lambda key: {
            'AZURE_OPENAI_ENDPOINT_2D': 'https://test.com',
            'AZURE_OPENAI_KEY_2D': 'key',
            'AZURE_OPENAI_ENDPOINT_3D': 'https://test.com',
            'AZURE_OPENAI_KEY_3D': 'key',
        }.get(key)
        
        config = Config()
        assert config.is_configured() == True
        
        # Missing config
        mock_getenv.return_value = None
        config = Config()
        assert config.is_configured() == False
