#!/usr/bin/env python3
"""
Batch update all press-*.py scripts to use auto-tokenizer detection
"""

import re
import os
from pathlib import Path

# Script directory
SCRIPT_DIR = Path(__file__).parent

# Mapping of scripts to their default tokenizers
SCRIPT_TOKENIZERS = {
    "press-llama3.211bv-20250407.py": "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "press-Mixtral-8x7B-20250323.py": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "press-nemotron-3-8b-chat-4k-steerlm-20250324.py": "nvidia/nemotron-3-8b-chat-4k-steerlm",
    "press-orca-20250324.py": "microsoft/Orca-2-7b",
    "press-whisper-20250323.py": "openai/whisper-large",
    "press-phi35and0v-20250323.py": "microsoft/Phi-3-small-8k-instruct",
    "press-phi35v-multi-imges-20250315.py": "microsoft/Phi-3-vision-128k-instruct",
    "press-swinv2-20250322.py": "microsoft/swinv2-base-patch4-window12-192-22k",
    "press-phi4-0403.py": "microsoft/phi-4",
}

# Template for import section (to insert after initial imports)
IMPORT_TEMPLATE = '''import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from config_helper import input_config_with_auto_tokenizer
    USE_AUTO_CONFIG = True
except ImportError:
    print("Warning: config_helper.py not found. Using manual configuration.")
    USE_AUTO_CONFIG = False
'''

def add_default_tokenizer_constant(content, default_tokenizer):
    """Add DEFAULT_TOKENIZER constant before input_config function"""
    pattern = r'(# -+ Input Configuration -+\s*\n)(def input_config\(\):)'
    replacement = f'\\1# Default tokenizer\nDEFAULT_TOKENIZER = "{default_tokenizer}"\n\n\\2'
    return re.sub(pattern, replacement, content)

def update_input_config_function(content):
    """Update input_config function to use auto-detection"""
    # This is complex, better to do manually for each script
    # Just add the import and constant, users can manually update function logic
    pass

def process_script(script_path, default_tokenizer):
    """Process a single script file"""
    print(f"Processing {script_path.name}...")
    
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already updated
    if 'config_helper' in content:
        print(f"  ✓ Already updated, skipping")
        return False
    
    # Add import section after first set of imports
    # Find position after "from transformers import AutoTokenizer"
    import_pos = content.find('from transformers import AutoTokenizer')
    if import_pos == -1:
        print(f"  ✗ Could not find transformers import")
        return False
    
    # Find end of that import block
    import_end = content.find('\n\n', import_pos)
    if import_end == -1:
        print(f"  ✗ Could not find end of import block")
        return False
    
    # Insert new imports
    new_content = (
        content[:import_end] + 
        '\n' + IMPORT_TEMPLATE + 
        content[import_end:]
    )
    
    # Add DEFAULT_TOKENIZER constant
    new_content = add_default_tokenizer_constant(new_content, default_tokenizer)
    
    # Write back
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"  ✓ Updated successfully")
    return True

def main():
    """Main function"""
    print("=" * 60)
    print("Batch Update Press Test Scripts")
    print("=" * 60)
    print()
    
    updated_count = 0
    for script_name, default_tokenizer in SCRIPT_TOKENIZERS.items():
        script_path = SCRIPT_DIR / script_name
        if not script_path.exists():
            print(f"✗ {script_name} not found, skipping")
            continue
        
        if process_script(script_path, default_tokenizer):
            updated_count += 1
        print()
    
    print("=" * 60)
    print(f"Updated {updated_count} scripts")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Manually update input_config() in each script to use:")
    print("   if USE_AUTO_CONFIG:")
    print("       URL, API_KEY, HEADERS, tokenizer = input_config_with_auto_tokenizer(DEFAULT_TOKENIZER)")
    print("2. Test each script")
    print("3. Commit changes")

if __name__ == "__main__":
    main()
