"""
Model Configuration Mapping
Auto-generated from README.md table
Maps AML model names to their HuggingFace tokenizer names
"""

MODEL_TOKENIZER_MAP = {
    # Model Name on AML: HuggingFace tokenizer name
    "Phi-4": "microsoft/phi-4",
    "Phi-3.5-vision-instruct": "microsoft/Phi-3.5-vision-instruct",
    "financial-reports-analysis": None,  # No tokenizer specified
    "Llama-3.2-11B-Vision-Instruct": "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "Phi-3-small-8k-instruct": "microsoft/Phi-3-small-8k-instruct",
    "Phi-3-vision-128k-instruct": "microsoft/Phi-3-vision-128k-instruct",
    "microsoft-swinv2-base-patch4-window12-192-22k": "microsoft/swinv2-base-patch4-window12-192-22k",
    "mistralai-Mixtral-8x7B-Instruct-v01": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "Muse": "microsoft/wham",
    "openai-whisper-large": "openai/whisper-large",
    "snowflake-arctic-base": "Snowflake/snowflake-arctic-base",
    "Nemotron-3-8B-Chat-4k-SteerLM": "nvidia/nemotron-3-8b-chat-4k-steerlm",
    "stabilityai-stable-diffusion-xl-refiner-1-0": "stabilityai/stable-diffusion-xl-refiner-1.0",
    "microsoft-Orca-2-7b": "microsoft/Orca-2-7b",
}


def get_tokenizer_name(model_name: str) -> str:
    """
    Get HuggingFace tokenizer name for a given AML model name.
    
    Args:
        model_name: Model name from Azure ML/AI Foundry
        
    Returns:
        HuggingFace tokenizer name, or None if not found
        
    Examples:
        >>> get_tokenizer_name("Phi-4")
        'microsoft/phi-4'
        
        >>> get_tokenizer_name("unknown-model")
        None
    """
    # Try exact match first
    if model_name in MODEL_TOKENIZER_MAP:
        return MODEL_TOKENIZER_MAP[model_name]
    
    # Try case-insensitive match
    model_name_lower = model_name.lower()
    for key, value in MODEL_TOKENIZER_MAP.items():
        if key.lower() == model_name_lower:
            return value
    
    # Try partial match (for models like "Phi-4" in URL "phi-4-xxx")
    for key, value in MODEL_TOKENIZER_MAP.items():
        if key.lower() in model_name_lower or model_name_lower in key.lower():
            return value
    
    return None


def extract_model_name_from_url(scoring_uri: str) -> str:
    """
    Extract model name from Azure ML endpoint URL.
    
    Args:
        scoring_uri: Azure ML scoring URI
        
    Returns:
        Extracted model name, or None if not found
        
    Examples:
        >>> extract_model_name_from_url("https://phi-4-xxx.eastus.inference.ml.azure.com/score")
        'Phi-4'
        
        >>> extract_model_name_from_url("https://custom-endpoint-123.eastus.inference.ml.azure.com/score")
        None
    """
    import re
    
    # Extract hostname from URL
    match = re.search(r'https?://([^/]+)', scoring_uri)
    if not match:
        return None
    
    hostname = match.group(1)
    
    # Try to match known model names in hostname
    hostname_lower = hostname.lower()
    for model_name in MODEL_TOKENIZER_MAP.keys():
        if model_name.lower() in hostname_lower:
            return model_name
    
    return None


def get_tokenizer_from_url(scoring_uri: str) -> str:
    """
    Auto-detect tokenizer name from scoring URI.
    
    Args:
        scoring_uri: Azure ML scoring URI
        
    Returns:
        HuggingFace tokenizer name, or None if not found
        
    Examples:
        >>> get_tokenizer_from_url("https://phi-4-xxx.eastus.inference.ml.azure.com/score")
        'microsoft/phi-4'
    """
    model_name = extract_model_name_from_url(scoring_uri)
    if model_name:
        return get_tokenizer_name(model_name)
    return None


if __name__ == "__main__":
    # Test the functions
    print("=== Model Tokenizer Mapping ===")
    for model, tokenizer in MODEL_TOKENIZER_MAP.items():
        print(f"{model:50s} -> {tokenizer}")
    
    print("\n=== Test URL Extraction ===")
    test_urls = [
        "https://phi-4-xxx.eastus.inference.ml.azure.com/score",
        "https://custom-endpoint-1760773801.francecentral.inference.ml.azure.com/score",
        "https://mistralai-mixtral-8x7b-instruct-v01.westus.inference.ml.azure.com/score",
    ]
    for url in test_urls:
        tokenizer = get_tokenizer_from_url(url)
        print(f"URL: {url}")
        print(f"  -> Tokenizer: {tokenizer}\n")
