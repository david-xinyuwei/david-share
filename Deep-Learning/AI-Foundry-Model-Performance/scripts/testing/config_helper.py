#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration helper for press test scripts
Provides auto-detection of tokenizers from Azure ML endpoint URLs
"""

import sys
import os

# Import model configuration
try:
    from model_config import get_tokenizer_from_url, get_tokenizer_name, MODEL_TOKENIZER_MAP
except ImportError:
    print("Warning: model_config.py not found. Auto-detection disabled.")
    get_tokenizer_from_url = None
    get_tokenizer_name = None
    MODEL_TOKENIZER_MAP = {}

try:
    from transformers import AutoTokenizer
except ImportError as e:
    print("Please install the transformers library first. Error:", e)
    sys.exit(1)


def load_tokenizer_auto(url, default_model=None):
    """
    Auto-detect and load tokenizer from Azure ML endpoint URL.
    
    Args:
        url: Azure ML scoring URI
        default_model: Default tokenizer model if auto-detection fails
        
    Returns:
        Loaded tokenizer object
        
    Raises:
        Exception if tokenizer cannot be loaded
    """
    # Try to auto-detect tokenizer from URL
    auto_detected_tokenizer = None
    if get_tokenizer_from_url:
        auto_detected_tokenizer = get_tokenizer_from_url(url)
    
    if auto_detected_tokenizer:
        print(f"\n✅ Auto-detected tokenizer: {auto_detected_tokenizer}")
        use_auto = input("Use this tokenizer? (Y/n): ").strip().lower()
        if use_auto in ['', 'y', 'yes']:
            model_name = auto_detected_tokenizer
        else:
            model_name = _prompt_for_model_name(default_model)
    else:
        print("\n⚠️  Could not auto-detect tokenizer from URL.")
        model_name = _prompt_for_model_name(default_model)
    
    # Load tokenizer
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        print(f"✅ Tokenizer loaded successfully: {model_name}\n")
        return tokenizer
    except Exception as e:
        print(f"❌ Failed to load tokenizer: {e}")
        raise


def _prompt_for_model_name(default_model=None):
    """
    Prompt user to enter model name with available options.
    
    Args:
        default_model: Default model name if user doesn't provide one
        
    Returns:
        Model name string
    """
    print("\nAvailable models:")
    for i, (aml_name, hf_name) in enumerate(MODEL_TOKENIZER_MAP.items(), 1):
        if hf_name:
            print(f"  {i:2d}. {aml_name:50s} -> {hf_name}")
    
    if default_model:
        prompt = f"\nEnter model name (default: {default_model}): "
    else:
        prompt = "\nEnter model name for tokenizer: "
    
    model_name = input(prompt).strip()
    
    if not model_name:
        if default_model:
            print(f"Using default: {default_model}")
            return default_model
        else:
            raise Exception("Model name cannot be empty!")
    
    return model_name


def input_config_with_auto_tokenizer(default_model=None):
    """
    Standard input configuration for press test scripts.
    Prompts for URL, API key, and auto-detects tokenizer.
    
    Args:
        default_model: Default tokenizer model if auto-detection fails
        
    Returns:
        tuple: (url, api_key, headers, tokenizer)
    """
    url = input("Please enter the API service URL: ").strip()
    if not url:
        raise Exception("URL cannot be empty!")
    
    api_key = input("Please enter the API Key: ").strip()
    if not api_key:
        raise Exception("API Key cannot be empty!")
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    tokenizer = load_tokenizer_auto(url, default_model)
    
    return url, api_key, headers, tokenizer


if __name__ == "__main__":
    # Test the helper
    print("=== Configuration Helper Test ===")
    print("This module provides auto-tokenizer detection for press test scripts.")
    print("\nExample usage:")
    print("  from config_helper import input_config_with_auto_tokenizer")
    print("  URL, API_KEY, HEADERS, tokenizer = input_config_with_auto_tokenizer('microsoft/phi-4')")
