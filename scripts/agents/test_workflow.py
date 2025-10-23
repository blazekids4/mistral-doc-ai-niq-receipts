"""
Test the receipt analysis workflow with sample receipts from existing directories.
This script copies sample receipt images to a temporary blob storage container for testing.
"""

import os
import shutil
import sys
import json
from pathlib import Path
import asyncio
from datetime import datetime

# Add parent directories to path
script_dir = Path(__file__).resolve().parent
sys.path.append(str(script_dir))
sys.path.append(str(script_dir.parent / "mistral"))
sys.path.append(str(script_dir.parent / "aoai"))
sys.path.append(str(script_dir.parent / "doc-intelligence"))

from dotenv import load_dotenv
from receipt_analysis_workflow import main as run_workflow

def setup_test_data():
    """Set up test data by copying samples from various sources to a test directory."""
    print("Setting up test data for workflow...")
    
    # Create test directory
    test_dir = script_dir.parents[1] / "data" / "test_receipts"
    test_dir.mkdir(exist_ok=True, parents=True)
    
    # Source directories to look for sample receipts
    source_dirs = [
        script_dir.parents[1] / "data" / "inputs",
        script_dir.parents[1] / "data" / "blurry-receipt",
        script_dir.parents[0] / "resources"  # If any samples are in the resources directory
    ]
    
    # Image extensions to look for
    image_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
    
    # Find and copy sample files
    copied_files = []
    for source_dir in source_dirs:
        if not source_dir.exists():
            print(f"Source directory not found: {source_dir}")
            continue
            
        print(f"Scanning {source_dir}...")
        
        # Look for files directly in the directory
        for file in source_dir.glob("*"):
            if file.is_file() and file.suffix.lower() in image_extensions:
                dest_file = test_dir / file.name
                if not dest_file.exists():
                    print(f"Copying {file.name}...")
                    shutil.copy2(file, dest_file)
                    copied_files.append(dest_file)
        
        # Look for files in subdirectories (one level deep)
        for subdir in source_dir.glob("*"):
            if subdir.is_dir():
                for file in subdir.glob("*"):
                    if file.is_file() and file.suffix.lower() in image_extensions:
                        dest_file = test_dir / file.name
                        if not dest_file.exists():
                            print(f"Copying {file.name}...")
                            shutil.copy2(file, dest_file)
                            copied_files.append(dest_file)
    
    if not copied_files:
        print("No sample receipt files found. Please add sample files to the data/inputs directory.")
        return False
        
    print(f"Copied {len(copied_files)} sample receipt files to {test_dir}")
    
    # Set environment variables for testing
    os.environ["STORAGE_PREFIX"] = ""  # No prefix for local testing
    os.environ["TEST_MODE"] = "true"   # Enable test mode
    
    return True

async def main():
    """Main test function."""
    load_dotenv()
    
    # Setup test data
    if not setup_test_data():
        print("Test setup failed.")
        return
    
    # Configure environment variables for the workflow
    # These would typically be set in .env but we override them for testing
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.environ["TEST_RUN_ID"] = f"test_{timestamp}"
    
    # Print testing configuration
    print("\n" + "="*60)
    print("RECEIPT WORKFLOW TEST CONFIGURATION")
    print("="*60)
    print(f"Test Run ID: {os.environ['TEST_RUN_ID']}")
    print(f"Storage Account: {os.environ.get('STORAGE_ACCOUNT_NAME', 'Not configured')}")
    print(f"Storage Container: {os.environ.get('STORAGE_CONTAINER_NAME', 'Not configured')}")
    print(f"Azure OpenAI Endpoint: {os.environ.get('AZURE_OPENAI_ENDPOINT', 'Not configured')}")
    print(f"Document Intelligence Endpoint: {os.environ.get('DOCUMENT_INTELLIGENCE_ENDPOINT', 'Not configured')}")
    print(f"Mistral Project Endpoint: {os.environ.get('PROJECT_ENDPOINT', 'Not configured')}")
    print("="*60 + "\n")
    
    # Run the workflow
    print("Starting receipt analysis workflow...")
    await run_workflow()
    
    # After testing, check for results
    results_dir = script_dir.parents[1] / "data" / "responses" / "aggregated"
    if results_dir.exists():
        result_files = list(results_dir.glob("final_*.json"))
        print(f"\nFound {len(result_files)} result files:")
        for file in result_files[-3:]:  # Show the most recent 3 files
            print(f" - {file.name}")
            
            # Display a sample result
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    print(f"   Merchant: {data.get('merchant_name', 'Unknown')}")
                    print(f"   Date: {data.get('transaction_date', 'Unknown')}")
                    print(f"   Total: {data.get('total_amount', 'Unknown')} {data.get('currency', '')}")
                    print(f"   Items: {len(data.get('items', []))}")
                    print(f"   Sources: {', '.join(data.get('sources_used', []))}")
                    print()
            except Exception as e:
                print(f"   Error reading result: {e}")

if __name__ == "__main__":
    asyncio.run(main())