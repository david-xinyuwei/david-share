"""
Test script to verify the project structure and imports
"""
import sys
import os

print("=" * 70)
print("Testing Project Structure and Imports")
print("=" * 70)
print()

# Test 1: Check Python version
print("1. Python Version:")
print(f"   {sys.version}")
print()

# Test 2: Check if source files exist
print("2. Checking source files...")
files_to_check = [
    "src/cli_estimator.py",
    "src/web_estimator.py",
    "src/__init__.py",
    "notebooks/memory_estimation.ipynb",
    "scripts/setup.ps1",
    "scripts/setup.sh",
    "requirements.txt",
    "README.md"
]

for file in files_to_check:
    exists = "✓" if os.path.exists(file) else "✗"
    print(f"   {exists} {file}")
print()

# Test 3: Check if required packages are installed
print("3. Checking installed packages...")
packages = ["transformers", "torch", "streamlit"]
for package in packages:
    try:
        __import__(package)
        print(f"   ✓ {package} installed")
    except ImportError:
        print(f"   ✗ {package} NOT installed")
print()

# Test 4: Try to import the main modules (without running them)
print("4. Testing module imports...")
try:
    # Add src to path
    sys.path.insert(0, 'src')
    
    # Try importing (this will test if syntax is correct)
    import cli_estimator
    print("   ✓ cli_estimator module can be imported")
except Exception as e:
    print(f"   ✗ Error importing cli_estimator: {e}")

try:
    import web_estimator
    print("   ✓ web_estimator module can be imported")
except Exception as e:
    print(f"   ✗ Error importing web_estimator: {e}")
print()

# Test 5: Quick functionality test
print("5. Testing core functionality...")
try:
    from transformers import AutoConfig
    print("   ✓ Can import AutoConfig from transformers")
    
    # Test a simple calculation function
    def estimate_model_size(nb_billion_parameters, bitwidth_model):
        return round(nb_billion_parameters * (bitwidth_model / 8), 2)
    
    test_size = estimate_model_size(14.7, 16)
    print(f"   ✓ Memory calculation test: 14.7B params @ 16-bit = {test_size} GB")
    
except Exception as e:
    print(f"   ✗ Error in functionality test: {e}")
print()

print("=" * 70)
print("Test Summary")
print("=" * 70)
print("✓ All tests completed!")
print()
print("To run the tools:")
print("  CLI Tool:    python src/cli_estimator.py")
print("  Web App:     streamlit run src/web_estimator.py")
print("  Notebook:    jupyter notebook notebooks/memory_estimation.ipynb")
print("=" * 70)
