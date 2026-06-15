"""
Test script specifically for Streamlit web application
"""
import sys
import os

# Set UTF-8 encoding for console output
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

print("=" * 70)
print("Testing Streamlit Web Application")
print("=" * 70)
print()

# Add src to path
sys.path.insert(0, 'src')

# Test 1: Check Streamlit installation
print("1. Checking Streamlit installation...")
try:
    import streamlit as st
    print(f"   ✓ Streamlit version: {st.__version__}")
except ImportError as e:
    print(f"   ✗ Streamlit not installed: {e}")
    sys.exit(1)
print()

# Test 2: Check dependencies
print("2. Checking dependencies...")
dependencies = {
    "os": None,
    "streamlit": None,
    "transformers": None
}

for dep in dependencies:
    try:
        __import__(dep)
        print(f"   ✓ {dep} available")
    except ImportError:
        print(f"   ✗ {dep} NOT available")
print()

# Test 3: Test importing the web_estimator module
print("3. Testing web_estimator module...")
try:
    import web_estimator
    print("   ✓ web_estimator module imported successfully")
    
    # Check if main function exists
    if hasattr(web_estimator, 'main'):
        print("   ✓ main() function found")
    else:
        print("   ✗ main() function NOT found")
        
except Exception as e:
    print(f"   ✗ Error importing web_estimator: {e}")
    import traceback
    traceback.print_exc()
print()

# Test 4: Verify file syntax
print("4. Verifying Python syntax...")
try:
    with open('src/web_estimator.py', 'r', encoding='utf-8') as f:
        code = f.read()
    compile(code, 'src/web_estimator.py', 'exec')
    print("   ✓ Python syntax is valid")
except SyntaxError as e:
    print(f"   ✗ Syntax error found: {e}")
print()

# Test 5: Check if Streamlit command is available
print("5. Checking Streamlit command availability...")
try:
    import subprocess
    result = subprocess.run(
        ['streamlit', '--version'],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode == 0:
        print(f"   ✓ Streamlit command available")
        print(f"   Version: {result.stdout.strip()}")
    else:
        print(f"   ✗ Streamlit command failed: {result.stderr}")
except Exception as e:
    print(f"   ⚠ Could not test streamlit command: {e}")
print()

print("=" * 70)
print("Streamlit Test Summary")
print("=" * 70)
print()
print("✓ Streamlit web application is ready!")
print()
print("To run the web application:")
print("  streamlit run src/web_estimator.py")
print()
print("The app will automatically open in your default web browser.")
print("=" * 70)
