"""
Receipt Analysis Workflow - All Agents Version
This version processes every receipt with ALL three agents (Document Intelligence, Mistral, Azure OpenAI)
regardless of image quality, and aggregates the results for maximum accuracy.
"""

import asyncio
import os
import sys
import json
import base64
import logging
from typing import Never
from datetime import datetime
from pathlib import Path

# Import our utility functions
from receipt_workflow_utils import (
    setup_logging, save_interim_result, handle_exception, 
    resolve_content_type, extract_numeric_value, safe_filename
)

from agent_framework import (
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    ChatMessage,
    Role,
    WorkflowBuilder,
    WorkflowContext,
    executor,
)
from pydantic import BaseModel
import requests
from dotenv import load_dotenv

# Set Azure SDK loggers to WARNING or ERROR
import logging
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.identity').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('agent_framework').setLevel(logging.WARNING)

# Import processors from the main workflow
from receipt_analysis_workflow import (
    ReceiptExtractionResult,
    document_intelligence_processor,
    mistral_processor,
    direct_extraction_processor,
    aggregate_results,
    generate_run_analysis_report,
    _accumulated_results
)

# Add parent directory to path to import storage utilities
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mistral'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'aoai'))
from storage_utils import get_container_blobs, get_blob_base64


@executor(id="dispatch_to_all_agents")
async def dispatch_to_all_agents(
    request: AgentExecutorRequest, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Dispatch receipt to all three processing agents simultaneously."""
    
    # Extract blob name from the initial request
    message_text = request.messages[0].text
    # Parse blob name from message like "Process receipt: blob_name"
    if "Process receipt: " in message_text:
        blob_name = message_text.split("Process receipt: ")[1].strip()
    else:
        blob_name = "unknown"
    
    print(f"\n{'='*60}")
    print(f"Dispatching {blob_name} to all agents")
    print(f"{'='*60}\n")
    
    # Get image data
    image_data_b64 = get_blob_base64(blob_name)
    
    if not image_data_b64:
        print(f"Warning: Could not retrieve image data for {blob_name}")
        return
    
    # Create requests for all three agents
    di_request = AgentExecutorRequest(
        messages=[ChatMessage(
            Role.USER,
            text=f"Process this receipt image: {blob_name}\nImage data: {image_data_b64[:100]}..."
        )],
        should_respond=True
    )
    
    mistral_request = AgentExecutorRequest(
        messages=[ChatMessage(
            Role.USER,
            text=f"Process this receipt image: {blob_name}\nImage data: {image_data_b64[:100]}..."
        )],
        should_respond=True
    )
    
    direct_request = AgentExecutorRequest(
        messages=[ChatMessage(
            Role.USER,
            text=f"Process this receipt image: {blob_name}\nImage data: {image_data_b64[:100]}..."
        )],
        should_respond=True
    )
    
    # Send to all agents
    print(f"✓ Sending {blob_name} to Document Intelligence")
    await ctx.send_message(di_request)
    
    print(f"✓ Sending {blob_name} to Mistral Document AI")
    await ctx.send_message(mistral_request)
    
    print(f"✓ Sending {blob_name} to Azure OpenAI Vision")
    await ctx.send_message(direct_request)
    
    print(f"\nAll agents dispatched for {blob_name}\n")


async def main() -> None:
    """Main workflow execution - processes all receipts with all agents."""
    load_dotenv()
    
    # Generate a unique run ID for this workflow execution
    run_id = f"all_agents_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create run-specific output directory
    from receipt_analysis_workflow import set_run_output_dir, _run_output_dir
    run_output_dir = Path(__file__).resolve().parents[2] / "data" / "workflow_runs" / run_id
    run_output_dir.mkdir(exist_ok=True, parents=True)
    
    # Set the global variable in the main workflow module (pass as Path, not string)
    set_run_output_dir(run_output_dir)
    
    # Set up logging to the run directory
    log_file = run_output_dir / "workflow.log"
    logger = setup_logging(run_id, str(log_file))
    logger.info(f"Starting ALL AGENTS receipt analysis workflow (ID: {run_id})")
    logger.info(f"Output directory: {run_output_dir}")
    
    print(f"\n{'='*60}")
    print(f"RECEIPT ANALYSIS - ALL AGENTS MODE")
    print(f"Run ID: {run_id}")
    print(f"Output: {run_output_dir}")
    print(f"{'='*60}\n")
    
    try:
        # Build the workflow - no quality assessment, straight to all agents
        logger.info("Building all-agents workflow graph")
        workflow = (
            WorkflowBuilder()
            .set_start_executor(dispatch_to_all_agents)
            # Dispatcher sends to all three processors
            .add_edge(dispatch_to_all_agents, document_intelligence_processor)
            .add_edge(dispatch_to_all_agents, mistral_processor)
            .add_edge(dispatch_to_all_agents, direct_extraction_processor)
            # All processors send results to aggregator
            .add_edge(document_intelligence_processor, aggregate_results)
            .add_edge(mistral_processor, aggregate_results)
            .add_edge(direct_extraction_processor, aggregate_results)
            .build()
        )
        
        # Get receipt images from blob storage
        logger.info("Fetching receipt images from blob storage")
        blob_names = get_container_blobs()
        
        if not blob_names:
            logger.warning("No receipt images found in blob storage")
            print("⚠ No receipt images found in blob storage")
            return
        
        logger.info(f"Found {len(blob_names)} receipt images to process")
        print(f"Found {len(blob_names)} receipt images")
        
        # Determine number of receipts to process (limit to 3 in test mode)
        test_mode = os.environ.get("TEST_MODE", "true").lower() == "true"
        receipts_to_process = blob_names[:3] if test_mode else blob_names
        
        logger.info(f"Processing {len(receipts_to_process)} receipts in {'TEST' if test_mode else 'PRODUCTION'} mode")
        print(f"Mode: {'TEST (first 3 receipts)' if test_mode else 'PRODUCTION (all receipts)'}")
        print(f"Processing: {len(receipts_to_process)} receipts\n")
        
        # Track timing metrics
        workflow_start_time = datetime.now()
        
        # Process each receipt
        results_summary = {
            "total": len(receipts_to_process),
            "successful": 0,
            "failed": 0,
            "run_id": run_id,
            "mode": "all_agents",
            "timestamp": workflow_start_time.isoformat(),
            "results": [],
            "timing": {
                "start_time": workflow_start_time.isoformat(),
                "end_time": None,
                "total_duration_seconds": None,
                "average_per_receipt_seconds": None
            }
        }
        
        for i, blob_name in enumerate(receipts_to_process, 1):
            logger.info(f"Processing receipt {i}/{len(receipts_to_process)}: {blob_name}")
            print(f"\n{'='*60}")
            print(f"Receipt {i}/{len(receipts_to_process)}: {blob_name}")
            print(f"{'='*60}")
            
            receipt_start_time = datetime.now()
            
            try:
                # Clear accumulated results for this receipt
                if blob_name in _accumulated_results:
                    del _accumulated_results[blob_name]
                
                # Get image as base64
                image_data_b64 = get_blob_base64(blob_name)
                
                if not image_data_b64:
                    logger.warning(f"Skipping {blob_name} - could not retrieve image data")
                    print(f"⚠ Skipping - could not retrieve image data")
                    results_summary["failed"] += 1
                    results_summary["results"].append({
                        "blob_name": blob_name,
                        "status": "skipped",
                        "reason": "Empty or inaccessible blob",
                        "duration_seconds": (datetime.now() - receipt_start_time).total_seconds()
                    })
                    continue
                
                logger.info(f"Retrieved image data for {blob_name} ({len(image_data_b64)} bytes)")
                
                # Create initial request
                request = AgentExecutorRequest(
                    messages=[ChatMessage(
                        Role.USER,
                        text=f"Process receipt: {blob_name}"
                    )],
                    should_respond=True
                )
                
                # Execute workflow
                logger.info(f"Executing all-agents workflow for {blob_name}")
                events = await workflow.run(request)
                outputs = events.get_outputs()
                
                receipt_duration = (datetime.now() - receipt_start_time).total_seconds()
                
                if outputs:
                    logger.info(f"Workflow completed successfully for {blob_name} in {receipt_duration:.2f}s")
                    print(f"✓ Workflow completed successfully in {receipt_duration:.2f}s")
                    results_summary["successful"] += 1
                    results_summary["results"].append({
                        "blob_name": blob_name,
                        "status": "success",
                        "output": outputs[0],
                        "duration_seconds": receipt_duration
                    })
                else:
                    logger.warning(f"Workflow completed with no output for {blob_name}")
                    print(f"⚠ Workflow completed with no output")
                    results_summary["failed"] += 1
                    results_summary["results"].append({
                        "blob_name": blob_name,
                        "status": "no_output",
                        "duration_seconds": receipt_duration
                    })
                    
            except Exception as e:
                error_details = handle_exception(e, logger, f"processing receipt {blob_name}")
                print(f"✗ Error: {str(e)}")
                receipt_duration = (datetime.now() - receipt_start_time).total_seconds()
                results_summary["failed"] += 1
                results_summary["results"].append({
                    "blob_name": blob_name,
                    "status": "error",
                    "error": str(e),
                    "duration_seconds": receipt_duration
                })
        
        # Calculate final timing metrics
        workflow_end_time = datetime.now()
        total_duration = (workflow_end_time - workflow_start_time).total_seconds()
        results_summary["timing"]["end_time"] = workflow_end_time.isoformat()
        results_summary["timing"]["total_duration_seconds"] = round(total_duration, 2)
        if results_summary["total"] > 0:
            results_summary["timing"]["average_per_receipt_seconds"] = round(
                total_duration / results_summary["total"], 2
            )
        
        # Save summary of results
        logger.info("Saving workflow summary")
        
        summary_file = run_output_dir / "workflow_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(results_summary, f, indent=2)
        
        print(f"\n{'='*60}")
        print(f"WORKFLOW COMPLETE")
        print(f"{'='*60}")
        print(f"Successful: {results_summary['successful']}")
        print(f"Failed: {results_summary['failed']}")
        print(f"Total: {results_summary['total']}")
        print(f"Duration: {total_duration:.2f}s ({total_duration/60:.2f} min)")
        if results_summary["total"] > 0:
            print(f"Average per receipt: {total_duration/results_summary['total']:.2f}s")
        print(f"\nAll outputs saved to: {run_output_dir}")
        print(f"  - Receipts: {run_output_dir / 'receipts'}")
        print(f"  - Summary: {summary_file.name}")
        print(f"  - Log: workflow.log")
        print(f"{'='*60}\n")
        
        logger.info(f"Workflow complete: {results_summary['successful']} successful, "
                  f"{results_summary['failed']} failed")
        logger.info(f"Summary saved to {summary_file}")
        
        # Generate LLM analysis report
        await generate_run_analysis_report(run_output_dir, results_summary, logger)
        
    except Exception as e:
        error_details = handle_exception(e, logger, "main workflow execution")
        logger.critical(f"Workflow failed: {error_details['error_message']}")
        print(f"\n✗ CRITICAL ERROR: {error_details['error_message']}\n")
        
    logger.info(f"Receipt analysis workflow completed (ID: {run_id})")
    print(f"\nSee all outputs in: {run_output_dir}\n")


if __name__ == "__main__":
    asyncio.run(main())
