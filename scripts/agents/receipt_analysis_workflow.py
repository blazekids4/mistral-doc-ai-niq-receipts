import asyncio
import os
import sys
import json
import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4
from datetime import datetime
from pathlib import Path

from typing_extensions import Never

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
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential, DefaultAzureCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from pydantic import BaseModel
import requests
from dotenv import load_dotenv

# Set Azure SDK loggers to WARNING or ERROR
import logging
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.identity').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('agent_framework').setLevel(logging.WARNING)

# Add parent directory to path to import storage utilities
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'mistral'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'aoai'))  # Also add Azure OpenAI path
from storage_utils import get_container_blobs, get_blob_base64


class ImageQualityAssessment(BaseModel):
    """Represents the quality assessment of a receipt image."""
    quality: str  # "clear", "blurry", or "uncertain"
    confidence_score: float  # 0.0 to 1.0
    reasoning: str
    image_data: str  # base64 encoded image data
    blob_name: str  # original blob name


class ReceiptExtractionResult(BaseModel):
    """Represents extracted receipt data from any agent."""
    source: str  # "document_intelligence", "mistral", or "direct_extraction"
    merchant_name: Optional[str] = None
    transaction_date: Optional[str] = None
    transaction_time: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    items: List[dict] = []
    raw_response: dict
    confidence_score: Optional[float] = None
    blob_name: str


class FinalReceiptData(BaseModel):
    """Represents the final aggregated receipt data."""
    merchant_name: str
    transaction_date: str
    transaction_time: Optional[str] = None
    total_amount: float
    currency: str
    items: List[dict]
    metadata: dict
    sources_used: List[str]
    blob_name: str


def get_quality_condition(expected_quality: str):
    """Create a condition callable that routes based on image quality."""
    def condition(message: Any) -> bool:
        if not isinstance(message, AgentExecutorResponse):
            return True
        
        try:
            assessment = ImageQualityAssessment.model_validate_json(message.agent_run_response.text)
            return assessment.quality == expected_quality
        except Exception as e:
            print(f"Error parsing quality assessment: {e}")
            return False
    
    return condition


@executor(id="to_document_intelligence_request")
async def to_document_intelligence_request(
    response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Transform quality assessment into a request for Document Intelligence agent."""
    assessment = ImageQualityAssessment.model_validate_json(response.agent_run_response.text)
    
    request = AgentExecutorRequest(
        messages=[ChatMessage(
            Role.USER, 
            text=f"Process this blurry receipt image: {assessment.blob_name}\nImage data: {assessment.image_data[:100]}..."
        )],
        should_respond=True
    )
    await ctx.send_message(request)


@executor(id="to_mistral_request")
async def to_mistral_request(
    response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Transform quality assessment into a request for Mistral agent."""
    assessment = ImageQualityAssessment.model_validate_json(response.agent_run_response.text)
    
    request = AgentExecutorRequest(
        messages=[ChatMessage(
            Role.USER,
            text=f"Process this clear receipt image: {assessment.blob_name}\nImage data: {assessment.image_data[:100]}..."
        )],
        should_respond=True
    )
    await ctx.send_message(request)


@executor(id="to_multi_agent_request")
async def to_multi_agent_request(
    response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]
) -> None:
    """Transform quality assessment into requests for multiple agents when uncertain."""
    assessment = ImageQualityAssessment.model_validate_json(response.agent_run_response.text)
    
    # Send to Document Intelligence
    di_request = AgentExecutorRequest(
        messages=[ChatMessage(
            Role.USER,
            text=f"Process this uncertain quality receipt image: {assessment.blob_name}\nImage data: {assessment.image_data[:100]}..."
        )],
        should_respond=True
    )
    
    # Send to Mistral
    mistral_request = AgentExecutorRequest(
        messages=[ChatMessage(
            Role.USER,
            text=f"Process this uncertain quality receipt image: {assessment.blob_name}\nImage data: {assessment.image_data[:100]}..."
        )],
        should_respond=True
    )
    
    # Send to Direct Extraction
    direct_request = AgentExecutorRequest(
        messages=[ChatMessage(
            Role.USER,
            text=f"Process this uncertain quality receipt image: {assessment.blob_name}\nImage data: {assessment.image_data[:100]}..."
        )],
        should_respond=True
    )
    
    await ctx.send_message(di_request)
    await ctx.send_message(mistral_request)
    await ctx.send_message(direct_request)


@executor(id="document_intelligence_processor")
async def document_intelligence_processor(
    request: AgentExecutorRequest, ctx: WorkflowContext[ReceiptExtractionResult]
) -> None:
    """Process receipt using Azure Document Intelligence."""
    load_dotenv()
    
    # Extract blob name and image data from request
    message_text = request.messages[0].text
    blob_name = message_text.split(": ")[1].split("\n")[0] if ": " in message_text else "unknown"
    
    # Get full image data
    image_data_b64 = get_blob_base64(blob_name)
    image_bytes = base64.b64decode(image_data_b64)
    
    # Initialize Document Intelligence client
    endpoint = os.environ.get("DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.environ.get("DOCUMENT_INTELLIGENCE_KEY")
    
    if not endpoint or not key:
        print("Document Intelligence credentials not found in environment")
        result = ReceiptExtractionResult(
            source="document_intelligence",
            raw_response={"error": "Credentials not configured"},
            blob_name=blob_name
        )
        await ctx.send_message(result)
        return
    
    try:
        client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        
        # Determine content type based on file extension
        file_ext = os.path.splitext(blob_name.lower())[1]
        content_type = "image/jpeg"
        if file_ext == ".png":
            content_type = "image/png"
        elif file_ext == ".pdf":
            content_type = "application/pdf"
        
        # Analyze receipt using the correct API structure
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
        
        poller = client.begin_analyze_document(
            model_id="prebuilt-receipt",
            body=image_bytes,
            content_type=content_type
        )
        
        receipt_result = poller.result()
        
        # Extract structured data
        items = []
        merchant_name = None
        transaction_date = None
        transaction_time = None
        total_amount = None
        currency = None
        
        if receipt_result.documents:
            doc = receipt_result.documents[0]
            fields = doc.fields or {}
            
            merchant_name = fields.get("MerchantName", {}).get("content") if "MerchantName" in fields else None
            transaction_date = fields.get("TransactionDate", {}).get("content") if "TransactionDate" in fields else None
            transaction_time = fields.get("TransactionTime", {}).get("content") if "TransactionTime" in fields else None
            
            if "Total" in fields:
                total_field = fields["Total"]
                if hasattr(total_field, "value") and hasattr(total_field.value, "amount"):
                    total_amount = total_field.value.amount
                    currency = total_field.value.currency_code if hasattr(total_field.value, "currency_code") else None
            
            if "Items" in fields:
                items_field = fields["Items"]
                if hasattr(items_field, "value") and isinstance(items_field.value, list):
                    for item in items_field.value:
                        if hasattr(item, "value") and isinstance(item.value, dict):
                            item_dict = {
                                "description": item.value.get("Description", {}).get("content") if "Description" in item.value else None,
                                "quantity": item.value.get("Quantity", {}).get("content") if "Quantity" in item.value else None,
                                "price": item.value.get("Price", {}).get("content") if "Price" in item.value else None,
                                "total_price": item.value.get("TotalPrice", {}).get("content") if "TotalPrice" in item.value else None,
                            }
                            items.append(item_dict)
        
        result = ReceiptExtractionResult(
            source="document_intelligence",
            merchant_name=merchant_name,
            transaction_date=transaction_date,
            transaction_time=transaction_time,
            total_amount=total_amount,
            currency=currency,
            items=items,
            raw_response=receipt_result.as_dict() if hasattr(receipt_result, 'as_dict') else {},
            confidence_score=doc.confidence if receipt_result.documents else None,
            blob_name=blob_name
        )
        
        await ctx.send_message(result)
        
    except Exception as e:
        print(f"Error processing with Document Intelligence: {e}")
        result = ReceiptExtractionResult(
            source="document_intelligence",
            raw_response={"error": str(e)},
            blob_name=blob_name
        )
        await ctx.send_message(result)


@executor(id="mistral_processor")
async def mistral_processor(
    request: AgentExecutorRequest, ctx: WorkflowContext[ReceiptExtractionResult]
) -> None:
    """Process receipt using Mistral Document AI."""
    load_dotenv()
    
    # Extract blob name from request
    message_text = request.messages[0].text
    blob_name = message_text.split(": ")[1].split("\n")[0] if ": " in message_text else "unknown"
    
    # Get full image data
    image_data_b64 = get_blob_base64(blob_name)
    
    # Initialize Mistral API
    api_key = os.environ.get('AZURE_API_KEY')
    endpoint = "https://foundry-eastus2-niq.services.ai.azure.com/providers/mistral/azure/ocr"
    
    if not api_key:
        print("Mistral API key not found in environment")
        result = ReceiptExtractionResult(
            source="mistral",
            raw_response={"error": "API key not configured"},
            blob_name=blob_name
        )
        await ctx.send_message(result)
        return
    
    try:
        print(f"Processing {blob_name} with Mistral Document AI...")
        
        # Determine content type
        file_ext = os.path.splitext(blob_name.lower())[1]
        content_type = "image/jpeg"
        if file_ext in [".png"]:
            content_type = "image/png"
        elif file_ext in [".pdf"]:
            content_type = "application/pdf"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": "mistral-document-ai-2505",
            "document": {
                "type": "image_url",
                "image_url": f"data:{content_type};base64,{image_data_b64}"
            },
            "include_image_base64": False
        }
        
        print("Sending request to Mistral Document AI...")
        response = requests.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        mistral_result = response.json()
        
        print(f"Received response from Mistral Document AI for {blob_name}")
        
        # Process the OCR result using text extraction and NLP
        merchant_name = None
        transaction_date = None
        transaction_time = None
        total_amount = None
        currency = None
        items = []
        confidence_score = 0.85  # Default confidence
        
        # Extract structured data from Mistral response
        if "content" in mistral_result:
            content = mistral_result["content"]
            
            # Extract merchant name - typically first lines of the receipt
            # This is a simplistic approach; in production, use regex patterns or NER
            lines = content.strip().split('\n')
            if lines and len(lines) > 0:
                merchant_name = lines[0]
                
            # Extract date/time using regex
            import re
            date_patterns = [
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # MM/DD/YYYY or DD/MM/YYYY
                r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})',  # DD Mon YYYY
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})'  # Mon DD, YYYY
            ]
            
            time_patterns = [
                r'(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)',  # HH:MM:SS AM/PM
                r'(\d{1,2}[:.]\d{2}(?:[:.]\d{2})?\s*(?:hrs|EST|CST|MST|PST)?)'  # Military time or with timezone
            ]
            
            # Search for date
            for pattern in date_patterns:
                date_match = re.search(pattern, content)
                if date_match:
                    transaction_date = date_match.group(1)
                    break
                    
            # Search for time
            for pattern in time_patterns:
                time_match = re.search(pattern, content)
                if time_match:
                    transaction_time = time_match.group(1)
                    break
            
            # Extract total amount
            total_patterns = [
                r'TOTAL\s*[\$£€]?\s*(\d+[.,]\d{2})',
                r'Total\s*[\$£€]?\s*(\d+[.,]\d{2})',
                r'AMOUNT\s*[\$£€]?\s*(\d+[.,]\d{2})',
                r'Amount\s*[\$£€]?\s*(\d+[.,]\d{2})',
                r'BALANCE\s*[\$£€]?\s*(\d+[.,]\d{2})',
                r'Balance\s*[\$£€]?\s*(\d+[.,]\d{2})',
                r'[\$£€]\s*(\d+[.,]\d{2})\s*$'
            ]
            
            # Search for total amount
            for pattern in total_patterns:
                total_match = re.search(pattern, content)
                if total_match:
                    total_str = total_match.group(1).replace(',', '.')
                    try:
                        total_amount = float(total_str)
                    except ValueError:
                        pass
                    break
            
            # Extract currency
            currency_patterns = {
                r'[\$]': 'USD',
                r'[£]': 'GBP',
                r'[€]': 'EUR',
                r'\bUSD\b': 'USD',
                r'\bEUR\b': 'EUR',
                r'\bGBP\b': 'GBP'
            }
            
            for pattern, curr in currency_patterns.items():
                if re.search(pattern, content):
                    currency = curr
                    break
                    
            if not currency:
                currency = 'USD'  # Default currency if not found
                
            # Extract line items (simplified approach)
            # This is a very basic approach - in production, use more sophisticated 
            # pattern recognition to identify item lines vs. other content
            item_pattern = r'([A-Za-z0-9\s\-\'\.]+)\s+([\$£€]?\s?\d+\.\d{2})'
            item_matches = re.finditer(item_pattern, content)
            
            for match in item_matches:
                if match and len(match.groups()) >= 2:
                    item_name = match.group(1).strip()
                    item_price_str = match.group(2).strip().replace('$', '').replace('£', '').replace('€', '')
                    
                    try:
                        item_price = float(item_price_str)
                        # Skip very high values as they're likely not items
                        if total_amount and item_price < total_amount:
                            items.append({
                                "description": item_name,
                                "price": item_price,
                            })
                    except ValueError:
                        pass
        
        # Create the result
        result = ReceiptExtractionResult(
            source="mistral",
            merchant_name=merchant_name,
            transaction_date=transaction_date,
            transaction_time=transaction_time,
            total_amount=total_amount,
            currency=currency,
            items=items,
            raw_response=mistral_result,
            confidence_score=confidence_score,
            blob_name=blob_name
        )
        
        print(f"Extracted from Mistral: Merchant={merchant_name}, Date={transaction_date}, Total={total_amount}")
        await ctx.send_message(result)
        
    except Exception as e:
        print(f"Error processing with Mistral: {e}")
        import traceback
        traceback.print_exc()
        
        result = ReceiptExtractionResult(
            source="mistral",
            raw_response={"error": str(e)},
            blob_name=blob_name
        )
        await ctx.send_message(result)


@executor(id="direct_extraction_processor")
async def direct_extraction_processor(
    request: AgentExecutorRequest, ctx: WorkflowContext[ReceiptExtractionResult]
) -> None:
    """Process receipt using direct Azure OpenAI vision model extraction for uncertain quality images."""
    load_dotenv()
    
    # Extract blob name from request
    message_text = request.messages[0].text
    blob_name = message_text.split(": ")[1].split("\n")[0] if ": " in message_text else "unknown"
    
    # Get full image data
    image_data_b64 = get_blob_base64(blob_name)
    
    # Initialize Azure OpenAI client
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
    api_version = "2024-12-01-preview"
    
    if not endpoint or not subscription_key or not deployment:
        print("Azure OpenAI configuration not found in environment")
        result = ReceiptExtractionResult(
            source="direct_extraction",
            raw_response={"error": "Azure OpenAI not configured properly"},
            blob_name=blob_name
        )
        await ctx.send_message(result)
        return
    
    try:
        print(f"Processing {blob_name} with Azure OpenAI vision model...")
        
        # Determine content type based on file extension
        file_ext = os.path.splitext(blob_name.lower())[1]
        content_type = "image/jpeg"  # Default
        if file_ext == ".png":
            content_type = "image/png"
        elif file_ext == ".pdf":
            content_type = "application/pdf"
            
        # Create client
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=subscription_key,
        )
        
        # Send request with structured extraction prompt
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": "You are a receipt analysis expert. Extract structured data from the receipt image. Return ONLY a JSON object without any explanations or additional text."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": (
                                "Analyze this receipt image and extract the following structured information as valid JSON:\n"
                                "- merchant_name: The name of the business or merchant\n"
                                "- transaction_date: The date of the transaction in any consistent format\n"
                                "- transaction_time: The time of the transaction if available\n"
                                "- total_amount: The total amount as a number without currency symbols\n"
                                "- currency: The currency code (USD, EUR, etc.)\n"
                                "- items: An array of purchased items, each with description and price\n"
                                "- confidence_level: Your confidence in the extracted data (0.0-1.0)\n\n"
                                "If any field is unreadable or missing, use null. Return ONLY valid JSON with these fields."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{image_data_b64}",
                                "detail": "high"
                            },
                        },
                    ],
                }
            ],
            temperature=0.0,
            max_tokens=4000,
        )
        
        # Get result text
        result_text = response.choices[0].message.content if response.choices else None
        
        if not result_text:
            print("No content in Azure OpenAI response")
            result = ReceiptExtractionResult(
                source="direct_extraction",
                raw_response={"error": "No content in response"},
                blob_name=blob_name
            )
            await ctx.send_message(result)
            return
            
        # Parse the JSON response
        import json
        import re
        
        # Clean response text to ensure it's valid JSON
        # Sometimes the model returns markdown-formatted JSON
        cleaned_text = result_text
        if "```json" in cleaned_text:
            cleaned_text = re.search(r"```json\n(.*?)```", cleaned_text, re.DOTALL)
            if cleaned_text:
                cleaned_text = cleaned_text.group(1)
            else:
                cleaned_text = result_text.replace("```json", "").replace("```", "")
        
        extraction_data = json.loads(cleaned_text)
        
        # Map to our result model
        result = ReceiptExtractionResult(
            source="direct_extraction",
            merchant_name=extraction_data.get("merchant_name"),
            transaction_date=extraction_data.get("transaction_date"),
            transaction_time=extraction_data.get("transaction_time"),
            total_amount=extraction_data.get("total_amount"),
            currency=extraction_data.get("currency"),
            items=extraction_data.get("items") or [],
            raw_response={
                "model": deployment,
                "response": result_text,
                "extraction": extraction_data
            },
            confidence_score=extraction_data.get("confidence_level", 0.9),
            blob_name=blob_name
        )
        
        print(f"Extracted from Azure OpenAI: Merchant={result.merchant_name}, Date={result.transaction_date}, Total={result.total_amount}")
        await ctx.send_message(result)
        
    except Exception as e:
        print(f"Error processing with Azure OpenAI: {e}")
        import traceback
        traceback.print_exc()
        
        result = ReceiptExtractionResult(
            source="direct_extraction",
            raw_response={"error": str(e)},
            blob_name=blob_name
        )
        await ctx.send_message(result)


# Store results in memory - will be accessed by the aggregate_results function
# We'll use a dictionary to store results by blob name
_accumulated_results = {}

# Global variable to store the run output directory
# Global variable to store the run output directory
_run_output_dir = None

def set_run_output_dir(output_dir):
    """Set the global run output directory."""
    global _run_output_dir
    # Accept both string and Path objects
    if isinstance(output_dir, str):
        _run_output_dir = Path(output_dir)
    else:
        _run_output_dir = output_dir

@executor(id="aggregate_results")
async def aggregate_results(
    result: ReceiptExtractionResult, ctx: WorkflowContext[Never, str]
) -> None:
    """Aggregate results from multiple agents and determine final JSON representation with smart field merging."""
    
    # Declare global at the top of the function
    global _run_output_dir
    
    # Accumulate results by blob name
    if result.blob_name not in _accumulated_results:
        _accumulated_results[result.blob_name] = []
    
    _accumulated_results[result.blob_name].append(result)
    print(f"Added result from {result.source} for {result.blob_name}")
    
    # Save individual agent output immediately
    if _run_output_dir:
        intermediary_dir = _run_output_dir / "intermediary_outputs"
        intermediary_dir.mkdir(exist_ok=True, parents=True)
        
        safe_blob_name = result.blob_name.replace('/', '_').replace('\\', '_').replace('.', '_')
        intermediary_file = intermediary_dir / f"{safe_blob_name}_{result.source}.json"
        
        with open(intermediary_file, 'w') as f:
            json.dump(result.model_dump(), f, indent=2)
        
        print(f"  → Saved intermediary output: {intermediary_file.name}")
    
    # Get all accumulated results for this blob
    results = _accumulated_results[result.blob_name]
    
    # Filter out results with errors
    valid_results = [r for r in results if not isinstance(r.raw_response, dict) or 'error' not in r.raw_response]
    
    if not valid_results:
        await ctx.yield_output("No valid results to aggregate")
        return
    
    # Collect all sources
    sources_used = [r.source for r in valid_results]
    blob_name = valid_results[0].blob_name
    
    print(f"\nAggregating results from {len(valid_results)} sources: {', '.join(sources_used)}")
    
    # Define source priorities (used for tiebreakers)
    source_priorities = {
        "document_intelligence": 3,  # Highest priority for structured data
        "mistral": 2,               # Good general OCR
        "direct_extraction": 1      # Fallback
    }
    
    # Calculate completeness and confidence scores
    scored_results = []
    for result in valid_results:
        # Calculate completeness score
        completeness_score = 0.0
        field_counts = 0
        
        # Core fields (weighted higher)
        if result.merchant_name:
            completeness_score += 2.0
            field_counts += 1
        if result.transaction_date:
            completeness_score += 2.0
            field_counts += 1
        if result.total_amount is not None:
            completeness_score += 3.0  # Total amount is critical
            field_counts += 1
        if result.currency:
            completeness_score += 1.0
            field_counts += 1
            
        # Items (weighted based on count and detail)
        if result.items:
            item_score = min(len(result.items) * 0.5, 5.0)  # Cap at 5.0
            completeness_score += item_score
            field_counts += 1
            
        # Additional fields
        if result.transaction_time:
            completeness_score += 1.0
            field_counts += 1
            
        # Normalize completeness score by number of fields
        if field_counts > 0:
            normalized_completeness = completeness_score / field_counts
        else:
            normalized_completeness = 0.0
            
        # Factor in confidence score if available
        confidence = result.confidence_score if result.confidence_score is not None else 0.5
        
        # Calculate final score: weight completeness more than confidence
        final_score = (normalized_completeness * 0.7) + (confidence * 0.3)
        
        # Add source priority as a tiebreaker (small factor)
        source_priority = source_priorities.get(result.source, 0) * 0.01
        final_score += source_priority
        
        scored_results.append({
            "result": result,
            "score": final_score,
            "completeness": normalized_completeness,
            "confidence": confidence
        })
        
        print(f"Source: {result.source}, Score: {final_score:.2f}, "
              f"Completeness: {normalized_completeness:.2f}, Confidence: {confidence:.2f}")
    
    # Sort results by score
    scored_results.sort(key=lambda x: x["score"], reverse=True)
    
    # The highest scoring result forms our base
    best_result = scored_results[0]["result"]
    print(f"Selected base result: {best_result.source} (score: {scored_results[0]['score']:.2f})")
    
    # Smart field merging - take best fields from all results
    # Track which source provided each field for attribution
    field_sources = {}
    
    # For non-list fields, use the highest-scoring result that has that field
    merchant_name = best_result.merchant_name
    field_sources['merchant_name'] = best_result.source if merchant_name else None
    
    transaction_date = best_result.transaction_date
    field_sources['transaction_date'] = best_result.source if transaction_date else None
    
    transaction_time = best_result.transaction_time
    field_sources['transaction_time'] = best_result.source if transaction_time else None
    
    total_amount = best_result.total_amount
    field_sources['total_amount'] = best_result.source if total_amount is not None else None
    
    currency = best_result.currency
    field_sources['currency'] = best_result.source if currency else None
    
    # For item lists, merge items from all sources with deduplication
    all_items = []
    seen_item_descriptions = set()
    item_sources = []  # Track which source contributed each item
    
    # Start with items from the best result
    if best_result.items:
        for item in best_result.items:
            if item.get("description"):
                desc_key = item["description"].lower().strip()
                if desc_key not in seen_item_descriptions:
                    seen_item_descriptions.add(desc_key)
                    all_items.append(item)
                    item_sources.append({
                        "description": item.get("description"),
                        "source": best_result.source
                    })
    
    # Add unique items from other results
    for scored in scored_results[1:]:
        result = scored["result"]
        
        # Also fill in any missing fields from other results
        if not merchant_name and result.merchant_name:
            merchant_name = result.merchant_name
            field_sources['merchant_name'] = result.source
            print(f"Using merchant_name from {result.source}: {merchant_name}")
            
        if not transaction_date and result.transaction_date:
            transaction_date = result.transaction_date
            field_sources['transaction_date'] = result.source
            print(f"Using transaction_date from {result.source}: {transaction_date}")
            
        if not transaction_time and result.transaction_time:
            transaction_time = result.transaction_time
            field_sources['transaction_time'] = result.source
            print(f"Using transaction_time from {result.source}: {transaction_time}")
            
        if total_amount is None and result.total_amount is not None:
            total_amount = result.total_amount
            field_sources['total_amount'] = result.source
            print(f"Using total_amount from {result.source}: {total_amount}")
            
        if not currency and result.currency:
            currency = result.currency
            field_sources['currency'] = result.source
            print(f"Using currency from {result.source}: {currency}")
        
        # Add unique items
        if result.items:
            for item in result.items:
                if item.get("description"):
                    desc_key = item["description"].lower().strip()
                    if desc_key not in seen_item_descriptions:
                        seen_item_descriptions.add(desc_key)
                        all_items.append(item)
                        item_sources.append({
                            "description": item.get("description"),
                            "source": result.source
                        })
                        print(f"Adding item from {result.source}: {item.get('description')}")
    
    # Create final aggregated result
    final_data = FinalReceiptData(
        merchant_name=merchant_name or "Unknown",
        transaction_date=transaction_date or "Unknown",
        transaction_time=transaction_time,
        total_amount=total_amount or 0.0,
        currency=currency or "USD",
        items=all_items,
        metadata={
            "processing_timestamp": datetime.now().isoformat(),
            "confidence_score": scored_results[0]["confidence"],
            "completeness_score": scored_results[0]["completeness"],
            "aggregation_score": scored_results[0]["score"],
            "best_source": best_result.source,
            "source_scores": {
                r["result"].source: r["score"] for r in scored_results
            },
            "field_sources": field_sources,  # Track which source provided each field
            "item_sources": item_sources  # Track which source provided each item
        },
        sources_used=sources_used,
        blob_name=blob_name
    )
    
    # Use the global run output directory (already declared at function start)
    if _run_output_dir is None:
        # Fallback if not set
        _run_output_dir = Path(__file__).resolve().parents[2] / "data" / "workflow_runs" / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    receipts_dir = _run_output_dir / "receipts"
    receipts_dir.mkdir(exist_ok=True, parents=True)
    
    # Save detailed aggregation context
    aggregation_dir = _run_output_dir / "aggregation_context"
    aggregation_dir.mkdir(exist_ok=True, parents=True)
    
    # Make a safe filename
    safe_blob_name = blob_name.replace('/', '_').replace('\\', '_').replace('.', '_')
    
    # Save aggregation decision context
    aggregation_context = {
        "blob_name": blob_name,
        "timestamp": datetime.now().isoformat(),
        "num_sources": len(valid_results),
        "sources_evaluated": sources_used,
        "scoring_details": [
            {
                "source": r["result"].source,
                "final_score": r["score"],
                "completeness_score": r["completeness"],
                "confidence_score": r["confidence"],
                "extracted_fields": {
                    "merchant_name": r["result"].merchant_name,
                    "transaction_date": r["result"].transaction_date,
                    "transaction_time": r["result"].transaction_time,
                    "total_amount": r["result"].total_amount,
                    "currency": r["result"].currency,
                    "num_items": len(r["result"].items) if r["result"].items else 0
                }
            }
            for r in scored_results
        ],
        "selection_logic": {
            "best_source": best_result.source,
            "best_score": scored_results[0]["score"],
            "field_attribution": field_sources,
            "item_attribution": item_sources,
            "merge_strategy": "highest_scoring_base_with_gap_filling"
        },
        "final_output": final_data.model_dump()
    }
    
    aggregation_file = aggregation_dir / f"{safe_blob_name}_aggregation.json"
    with open(aggregation_file, 'w') as f:
        json.dump(aggregation_context, f, indent=2)
    
    print(f"Aggregation context saved to: {aggregation_file.name}")
    output_file = receipts_dir / f"{safe_blob_name}.json"
    
    with open(output_file, 'w') as f:
        json.dump(final_data.model_dump(), f, indent=2)
    
    print(f"Final result saved to: {output_file}")
    
    # Also save a markdown summary for human review
    markdown_file = receipts_dir / f"{safe_blob_name}.md"
    
    with open(markdown_file, 'w') as f:
        f.write(f"# Receipt Summary: {blob_name}\n\n")
        f.write(f"**Merchant:** {merchant_name or 'Unknown'} _(source: {field_sources.get('merchant_name', 'none')})_\n\n")
        f.write(f"**Date:** {transaction_date or 'Unknown'} _(source: {field_sources.get('transaction_date', 'none')})_\n\n")
        f.write(f"**Time:** {transaction_time or 'Not available'} _(source: {field_sources.get('transaction_time', 'none')})_\n\n")
        f.write(f"**Total:** {total_amount or 0.0} {currency or 'USD'} _(source: {field_sources.get('total_amount', 'none')})_\n\n")
        
        f.write("## Items\n\n")
        if all_items:
            for idx, item in enumerate(all_items):
                description = item.get("description", "Unknown item")
                price = item.get("price") or item.get("total_price") or "Unknown price"
                quantity = item.get("quantity", "1")
                item_source = item_sources[idx]["source"] if idx < len(item_sources) else "unknown"
                f.write(f"- {description}: {price} (qty: {quantity}) _[{item_source}]_\n")
        else:
            f.write("No items extracted\n")
            
        f.write("\n## Processing Details\n\n")
        f.write(f"**Sources used:** {', '.join(sources_used)}\n\n")
        f.write(f"**Best source:** {best_result.source}\n\n")
        f.write(f"**Confidence score:** {scored_results[0]['confidence']:.2f}\n\n")
        f.write(f"**Completeness score:** {scored_results[0]['completeness']:.2f}\n\n")
        
        f.write("## Field Attribution\n\n")
        f.write("| Field | Source |\n")
        f.write("|-------|--------|\n")
        for field, source in field_sources.items():
            if source:
                f.write(f"| {field} | {source} |\n")
        
        f.write("\n## Source Scores\n\n")
        for r in scored_results:
            f.write(f"- **{r['result'].source}**: {r['score']:.2f} ")
            f.write(f"(completeness: {r['completeness']:.2f}, confidence: {r['confidence']:.2f})\n")
    
    await ctx.yield_output(f"Receipt processing complete. Results saved to:\n- {output_file.name}\n- {markdown_file.name}")


async def generate_run_analysis_report(run_output_dir: Path, results_summary: dict, logger: logging.Logger) -> None:
    """Generate an LLM-powered analysis report for the entire workflow run."""
    
    print(f"\n{'='*60}")
    print("Generating LLM Analysis Report...")
    print(f"{'='*60}\n")
    
    logger.info("Starting LLM analysis report generation")
    
    try:
        # Collect all receipt data
        receipts_dir = run_output_dir / "receipts"
        aggregation_dir = run_output_dir / "aggregation_context"
        
        if not receipts_dir.exists():
            logger.warning("No receipts directory found, skipping analysis report")
            return
        
        # Load all receipt JSONs
        receipt_files = list(receipts_dir.glob("*.json"))
        all_receipts = []
        
        for receipt_file in receipt_files:
            try:
                with open(receipt_file, 'r') as f:
                    receipt_data = json.load(f)
                    all_receipts.append(receipt_data)
            except Exception as e:
                logger.warning(f"Could not load receipt file {receipt_file.name}: {e}")
        
        # Load aggregation contexts
        all_aggregations = []
        if aggregation_dir.exists():
            aggregation_files = list(aggregation_dir.glob("*_aggregation.json"))
            for agg_file in aggregation_files:
                try:
                    with open(agg_file, 'r') as f:
                        agg_data = json.load(f)
                        all_aggregations.append(agg_data)
                except Exception as e:
                    logger.warning(f"Could not load aggregation file {agg_file.name}: {e}")
        
        # Prepare analysis context
        analysis_context = {
            "run_summary": results_summary,
            "num_receipts": len(all_receipts),
            "receipts_sample": all_receipts[:5] if len(all_receipts) > 5 else all_receipts,
            "aggregations_sample": all_aggregations[:3] if len(all_aggregations) > 3 else all_aggregations
        }
        
        # Create prompt for LLM analysis
        analysis_prompt = f"""You are an expert data analyst reviewing the results of an automated receipt processing workflow. 

Analyze the following workflow execution data and generate a comprehensive markdown report.

## Workflow Summary
- Run ID: {results_summary.get('run_id')}
- Total Receipts: {results_summary.get('total')}
- Successful: {results_summary.get('successful')}
- Failed: {results_summary.get('failed')}
- Total Duration: {results_summary.get('timing', {}).get('total_duration_seconds', 0):.2f} seconds
- Average per Receipt: {results_summary.get('timing', {}).get('average_per_receipt_seconds', 0):.2f} seconds

## Receipt Data Sample
{json.dumps(analysis_context['receipts_sample'], indent=2)[:5000]}

## Aggregation Context Sample
{json.dumps(analysis_context['aggregations_sample'], indent=2)[:5000]}

## Analysis Requirements

Generate a detailed markdown report with the following sections:

1. **Executive Summary**: High-level overview of the workflow execution
2. **Processing Performance**: Analysis of timing, success rates, and throughput
3. **Data Quality Assessment**: 
   - Completeness of extracted fields across receipts
   - Confidence score distributions
   - Common missing fields or patterns
4. **Multi-Agent Performance**:
   - Which agents were used most frequently
   - Source attribution patterns (which agent contributed most fields)
   - Agent scoring and selection patterns
5. **Merchant and Transaction Patterns**:
   - Unique merchants identified
   - Transaction amount ranges
   - Common item types
6. **Issues and Recommendations**:
   - Receipts that failed or had low confidence
   - Data quality concerns
   - Recommended improvements
7. **Detailed Statistics**:
   - Field extraction success rates
   - Item count distributions
   - Currency usage

Format the report professionally with clear sections, bullet points, tables where appropriate, and actionable insights."""

        # Call Azure OpenAI for analysis
        load_dotenv()
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = "2024-12-01-preview"
        
        if not all([endpoint, deployment, api_key]):
            logger.error("Azure OpenAI configuration missing, cannot generate analysis report")
            print("⚠ Azure OpenAI not configured - skipping analysis report")
            return
        
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=api_key,
        )
        
        logger.info("Calling Azure OpenAI for run analysis")
        print("Analyzing workflow data with Azure OpenAI...")
        
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert data analyst specializing in document processing workflows. Generate clear, actionable, professional reports."
                },
                {
                    "role": "user",
                    "content": analysis_prompt
                }
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        
        analysis_report = response.choices[0].message.content if response.choices else None
        
        if not analysis_report:
            logger.error("No response from Azure OpenAI for analysis")
            print("⚠ Failed to generate analysis report")
            return
        
        # Save the analysis report
        report_file = run_output_dir / "RUN_ANALYSIS_REPORT.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"# Workflow Run Analysis Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Run ID:** {results_summary.get('run_id')}\n\n")
            f.write("---\n\n")
            f.write(analysis_report)
        
        print(f"✓ Analysis report saved: {report_file.name}")
        logger.info(f"Analysis report generated successfully: {report_file}")
        
    except Exception as e:
        logger.error(f"Error generating analysis report: {e}")
        print(f"⚠ Error generating analysis report: {e}")


async def main() -> None:
    """Main workflow execution."""
    load_dotenv()
    
    # Generate a unique run ID for this workflow execution
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create run-specific output directory
    global _run_output_dir
    _run_output_dir = Path(__file__).resolve().parents[2] / "data" / "workflow_runs" / run_id
    _run_output_dir.mkdir(exist_ok=True, parents=True)
    
    # Set up logging to the run directory
    log_file = _run_output_dir / "workflow.log"
    logger = setup_logging(run_id, str(log_file))
    logger.info(f"Starting receipt analysis workflow (ID: {run_id})")
    logger.info(f"Output directory: {_run_output_dir}")
    
    print(f"\n{'='*60}")
    print(f"RECEIPT ANALYSIS WORKFLOW")
    print(f"Run ID: {run_id}")
    print(f"Output: {_run_output_dir}")
    print(f"{'='*60}\n")
    
    try:
        # Create Azure OpenAI chat client for quality assessment
        logger.info("Initializing Azure OpenAI client for quality assessment")
        
        # Get the deployment name from environment variable
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        if not deployment_name:
            logger.error("AZURE_OPENAI_DEPLOYMENT environment variable is not set")
            print("Error: AZURE_OPENAI_DEPLOYMENT environment variable is not set")
            return
            
        chat_client = AzureOpenAIChatClient(
            credential=AzureCliCredential(), 
            deployment_name=deployment_name
        )
        
        # Agent 1: Image Quality Assessor
        logger.info("Creating quality assessment agent")
        quality_assessor = AgentExecutor(
            chat_client.create_agent(
                instructions=(
                    "You are an image quality assessment specialist for receipt images. "
                    "Analyze the provided receipt image and determine its quality level. "
                    "Return JSON with fields: quality ('clear', 'blurry', or 'uncertain'), "
                    "confidence_score (0.0 to 1.0), reasoning (explanation), "
                    "image_data (the base64 data), and blob_name. "
                    "Consider factors like text readability, contrast, resolution, and blur."
                ),
                response_format=ImageQualityAssessment,
            ),
            id="quality_assessor",
        )
        
        # Build the workflow
        logger.info("Building workflow graph")
        workflow = (
            WorkflowBuilder()
            .set_start_executor(quality_assessor)
            # Clear quality -> Mistral
            .add_edge(quality_assessor, to_mistral_request, condition=get_quality_condition("clear"))
            .add_edge(to_mistral_request, mistral_processor)
            # Blurry quality -> Document Intelligence
            .add_edge(quality_assessor, to_document_intelligence_request, condition=get_quality_condition("blurry"))
            .add_edge(to_document_intelligence_request, document_intelligence_processor)
            # Uncertain quality -> All agents
            .add_edge(quality_assessor, to_multi_agent_request, condition=get_quality_condition("uncertain"))
            .add_edge(to_multi_agent_request, document_intelligence_processor)
            .add_edge(to_multi_agent_request, mistral_processor)
            .add_edge(to_multi_agent_request, direct_extraction_processor)
            # Send results directly to aggregator
            .add_edge(mistral_processor, aggregate_results)
            .add_edge(document_intelligence_processor, aggregate_results)
            .add_edge(direct_extraction_processor, aggregate_results)
            .build()
        )
        
        # Get receipt images from blob storage
        logger.info("Fetching receipt images from blob storage")
        blob_names = get_container_blobs()
        
        if not blob_names:
            logger.warning("No receipt images found in blob storage")
            return
        
        logger.info(f"Found {len(blob_names)} receipt images to process")
        
        # Determine number of receipts to process (limit to 3 in test mode)
        # In production, remove the slicing to process all receipts
        test_mode = os.environ.get("TEST_MODE", "true").lower() == "true"
        receipts_to_process = blob_names[:3] if test_mode else blob_names
        
        logger.info(f"Processing {len(receipts_to_process)} receipts in {'TEST' if test_mode else 'PRODUCTION'} mode")
        
        # Track timing metrics
        workflow_start_time = datetime.now()
        
        # Process each receipt
        results_summary = {
            "total": len(receipts_to_process),
            "successful": 0,
            "failed": 0,
            "run_id": run_id,
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
            
            receipt_start_time = datetime.now()
            
            try:
                # Get image as base64
                image_data_b64 = get_blob_base64(blob_name)
                
                if not image_data_b64:
                    logger.warning(f"Skipping {blob_name} - could not retrieve image data")
                    results_summary["failed"] += 1
                    results_summary["results"].append({
                        "blob_name": blob_name,
                        "status": "skipped",
                        "reason": "Empty or inaccessible blob",
                        "duration_seconds": (datetime.now() - receipt_start_time).total_seconds()
                    })
                    continue
                
                logger.info(f"Retrieved image data for {blob_name} ({len(image_data_b64)} bytes)")
                
                # Create initial request with image data
                request = AgentExecutorRequest(
                    messages=[ChatMessage(
                        Role.USER,
                        text=f"Assess the quality of this receipt image: {blob_name}\nImage data (base64): {image_data_b64[:200]}..."
                    )],
                    should_respond=True
                )
                
                # Execute workflow
                logger.info(f"Executing workflow for {blob_name}")
                events = await workflow.run(request)
                outputs = events.get_outputs()
                
                receipt_duration = (datetime.now() - receipt_start_time).total_seconds()
                
                if outputs:
                    logger.info(f"Workflow completed successfully for {blob_name} in {receipt_duration:.2f}s")
                    results_summary["successful"] += 1
                    results_summary["results"].append({
                        "blob_name": blob_name,
                        "status": "success",
                        "output": outputs[0],
                        "duration_seconds": receipt_duration
                    })
                else:
                    logger.warning(f"Workflow completed with no output for {blob_name}")
                    results_summary["failed"] += 1
                    results_summary["results"].append({
                        "blob_name": blob_name,
                        "status": "no_output",
                        "duration_seconds": receipt_duration
                    })
                    
            except Exception as e:
                error_details = handle_exception(e, logger, f"processing receipt {blob_name}")
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
        
        summary_file = _run_output_dir / "workflow_summary.json"
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
        print(f"\nAll outputs saved to: {_run_output_dir}")
        print(f"  - Receipts: {_run_output_dir / 'receipts'}")
        print(f"  - Summary: {summary_file.name}")
        print(f"  - Log: workflow.log")
        print(f"{'='*60}\n")
        
        logger.info(f"Workflow complete: {results_summary['successful']} successful, "
                  f"{results_summary['failed']} failed")
        logger.info(f"Summary saved to {summary_file}")
        
        # Generate LLM analysis report
        await generate_run_analysis_report(_run_output_dir, results_summary, logger)
        
    except Exception as e:
        error_details = handle_exception(e, logger, "main workflow execution")
        logger.critical(f"Workflow failed: {error_details['error_message']}")
        
    logger.info(f"Receipt analysis workflow completed (ID: {run_id})")
    print(f"\nSee all outputs in: {_run_output_dir}\n")


if __name__ == "__main__":
    asyncio.run(main())
