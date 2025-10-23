"""
Run the workflow using Python code instead of a markdown file
"""

import os
import sys
from pathlib import Path
import asyncio

# Add this script's directory to the path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

def print_header(text):
    """Print a formatted header."""
    line = "=" * 80
    print(f"\n{line}")
    print(text.center(80))
    print(f"{line}\n")

def print_instructions():
    """Display instructions for running the receipt workflow."""
    print_header("RECEIPT ANALYSIS WORKFLOW SETUP")
    
    print("1. ENVIRONMENT SETUP")
    print("-------------------")
    print("Create a .env file in the root directory with the following variables:")
    print("""
# Azure OpenAI (for quality assessment and direct extraction)
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_DEPLOYMENT=your_deployment_name_here

# Document Intelligence
DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-di.cognitiveservices.azure.com/
DOCUMENT_INTELLIGENCE_KEY=your_key_here

# Mistral API
AZURE_API_KEY=your_mistral_key
PROJECT_ENDPOINT=https://foundry-eastus2-niq.services.ai.azure.com

# Blob Storage
STORAGE_ACCOUNT_NAME=your_storage_account
STORAGE_CONTAINER_NAME=your_container
STORAGE_PREFIX=receipts/
    """)
    
    print("\n2. AZURE AUTHENTICATION")
    print("---------------------")
    print("Log in with Azure CLI:")
    print("```")
    print("az login")
    print("```")
    
    print("\n3. RUN THE WORKFLOW")
    print("------------------")
    print("Option A: Intelligent routing (quality assessment first):")
    print("```")
    print("python run_workflow.py --run")
    print("  or")
    print("python receipt_analysis_workflow.py")
    print("```")
    
    print("\nOption B: All agents mode (uses all 3 agents for every receipt):")
    print("```")
    print("python run_workflow.py --all-agents")
    print("  or")
    print("python receipt_analysis_all_agents.py")
    print("```")
    
    print("\nOption C: Run test workflow with sample images:")
    print("```")
    print("python test_workflow.py")
    print("```")
    
    print("\n4. REVIEW RESULTS")
    print("---------------")
    print("Each workflow run creates a dedicated folder:")
    print("data/workflow_runs/run_YYYYMMDD_HHMMSS/")
    print("  ├── receipts/              # All receipt JSONs and summaries")
    print("  ├── workflow_summary.json  # Overall run statistics")
    print("  └── workflow.log           # Detailed log file")
    
    print_header("HAPPY RECEIPT PROCESSING!")

async def run_workflow():
    """Run the receipt analysis workflow."""
    from receipt_analysis_workflow import main as workflow_main
    
    print_header("RUNNING RECEIPT ANALYSIS WORKFLOW")
    print("Mode: Intelligent Routing (Quality Assessment)")
    print("Routes based on image quality to optimal agent(s)\n")
    
    try:
        print("Starting workflow...")
        await workflow_main()
        print("\nWorkflow completed successfully!")
        
        # Check for results in the new structure
        runs_dir = Path(script_dir).parent.parent / "data" / "workflow_runs"
        if runs_dir.exists():
            run_folders = sorted(runs_dir.glob("run_*"), key=lambda x: x.stat().st_mtime, reverse=True)
            if run_folders:
                latest_run = run_folders[0]
                print(f"\nLatest run: {latest_run.name}")
                receipts_dir = latest_run / "receipts"
                if receipts_dir.exists():
                    receipt_files = list(receipts_dir.glob("*.json"))
                    print(f"Processed {len(receipt_files)} receipts")
                    for file in receipt_files[:3]:  # Show first 3
                        print(f"  - {file.name}")
        else:
            print("\nNo results found. Check logs for details.")
            
    except Exception as e:
        print(f"\nError running workflow: {e}")
        import traceback
        traceback.print_exc()
        
        print("\nPlease check the following:")
        print("1. Environment variables are set correctly")
        print("2. Azure authentication is valid")
        print("3. Receipt images are available in blob storage")


async def run_all_agents_workflow():
    """Run the all-agents receipt analysis workflow."""
    from receipt_analysis_all_agents import main as all_agents_main
    
    print_header("RUNNING ALL AGENTS WORKFLOW")
    print("Mode: All Agents")
    print("Uses Document Intelligence + Mistral + Azure OpenAI for every receipt\n")
    
    try:
        print("Starting workflow...")
        await all_agents_main()
        print("\nWorkflow completed successfully!")
        
        # Check for results in the new structure
        runs_dir = Path(script_dir).parent.parent / "data" / "workflow_runs"
        if runs_dir.exists():
            run_folders = sorted(runs_dir.glob("all_agents_*"), key=lambda x: x.stat().st_mtime, reverse=True)
            if run_folders:
                latest_run = run_folders[0]
                print(f"\nLatest run: {latest_run.name}")
                receipts_dir = latest_run / "receipts"
                if receipts_dir.exists():
                    receipt_files = list(receipts_dir.glob("*.json"))
                    print(f"Processed {len(receipt_files)} receipts")
                    for file in receipt_files[:3]:  # Show first 3
                        print(f"  - {file.name}")
        else:
            print("\nNo results found. Check logs for details.")
            
    except Exception as e:
        print(f"\nError running workflow: {e}")
        import traceback
        traceback.print_exc()
        
        print("\nPlease check the following:")
        print("1. Environment variables are set correctly")
        print("2. Azure authentication is valid")
        print("3. Receipt images are available in blob storage")

def main():
    """Main function to display instructions or run workflow."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--run":
            # Run the intelligent routing workflow
            asyncio.run(run_workflow())
        elif sys.argv[1] == "--all-agents":
            # Run the all-agents workflow
            asyncio.run(run_all_agents_workflow())
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("\nAvailable options:")
            print("  --run         : Run intelligent routing workflow")
            print("  --all-agents  : Run all-agents workflow")
            print("  (no option)   : Show instructions")
    else:
        # Show instructions
        print_instructions()
        print("\nTo run a workflow directly, use:")
        print(f"  python {os.path.basename(__file__)} --run          (intelligent routing)")
        print(f"  python {os.path.basename(__file__)} --all-agents   (all agents mode)")


if __name__ == "__main__":
    main()