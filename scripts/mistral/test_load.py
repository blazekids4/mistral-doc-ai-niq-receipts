#!/usr/bin/env python
"""
Test script for mistral_load_test.py - runs a minimal load test to verify functionality
"""
import os
import sys
import subprocess
from pathlib import Path

# Get the directory of this script
SCRIPT_DIR = Path(__file__).parent.absolute()

def run_test():
    """
    Run a small load test with minimal iterations to verify functionality
    """
    print("Running minimal load test to verify functionality...")
    # Run with only 3 iterations for quick testing
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, "mistral_load_test.py"), 
           "--iterations", "3"]
    
    # Execute the command
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("\nSTDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("\nTest completed successfully!")
            return True
        else:
            print(f"\nTest failed with return code {result.returncode}")
            return False
    except Exception as e:
        print(f"Error running test: {e}")
        return False

if __name__ == "__main__":
    run_test()