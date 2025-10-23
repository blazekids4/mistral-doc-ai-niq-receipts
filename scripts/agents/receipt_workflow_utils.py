"""
Utility functions for receipt analysis workflow
Provides consistent error handling, logging, and helper functions.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union


# Configure logging
def setup_logging(workflow_run_id: str, log_file_path: Optional[str] = None) -> logging.Logger:
    """
    Set up logging for the workflow.
    
    Args:
        workflow_run_id: Unique identifier for this workflow run
        log_file_path: Optional custom path for log file. If None, uses default location.
    """
    if log_file_path is None:
        # Use default location
        log_dir = Path(__file__).resolve().parents[2] / "data" / "logs"
        log_dir.mkdir(exist_ok=True, parents=True)
        log_file = log_dir / f"workflow_{workflow_run_id}.log"
    else:
        log_file = Path(log_file_path)
        log_file.parent.mkdir(exist_ok=True, parents=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ],
        force=True  # Override existing configuration
    )
    
    logger = logging.getLogger("receipt_workflow")
    logger.info(f"Starting workflow run: {workflow_run_id}")
    logger.info(f"Log file: {log_file}")
    return logger


def save_interim_result(data: Dict[str, Any], source: str, blob_name: str, run_id: str) -> str:
    """Save interim processing results for debugging and analysis."""
    # Create output directory
    output_dir = Path(__file__).resolve().parents[2] / "data" / "responses" / source / run_id
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Create a safe filename
    safe_blob_name = blob_name.replace('/', '_').replace('\\', '_')
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_file = output_dir / f"interim_{safe_blob_name}_{timestamp}.json"
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
        
    return str(output_file)


def handle_exception(e: Exception, logger: logging.Logger, context: str) -> Dict[str, Any]:
    """Standardized exception handling with logging."""
    import traceback
    error_details = {
        "error_type": type(e).__name__,
        "error_message": str(e),
        "context": context,
        "timestamp": datetime.now().isoformat()
    }
    
    logger.error(f"Error in {context}: {str(e)}")
    logger.debug(traceback.format_exc())
    
    return error_details


def resolve_content_type(blob_name: str) -> str:
    """Choose a sensible content type based on file extension."""
    extension = os.path.splitext(blob_name.lower())[1]
    if extension == ".png":
        return "image/png"
    if extension == ".pdf":
        return "application/pdf"
    return "image/jpeg"


def extract_numeric_value(text: str) -> Optional[float]:
    """Extract a numeric value from text, handling different formats."""
    if not text:
        return None
        
    # Remove common currency symbols
    cleaned = text.replace("$", "").replace("€", "").replace("£", "").strip()
    
    # Convert comma decimal separator to period
    cleaned = cleaned.replace(",", ".")
    
    try:
        return float(cleaned)
    except ValueError:
        return None


def safe_filename(value: str) -> str:
    """Convert a string to a filesystem-safe filename."""
    return value.replace('/', '_').replace('\\', '_').replace(':', '_')