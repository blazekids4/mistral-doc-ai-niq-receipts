import requests
import os
import json
import datetime
from dotenv import load_dotenv
from storage_utils import get_container_blobs, get_blob_base64

def process_document_raw(base64_image, api_key, content_type="application/pdf"):
    """Process a document using Mistral Document AI with default parameters
    
    Gets the raw response from Mistral's OCR API without special configuration.
    This is useful for general document understanding and basic OCR.
    """
    
    url = "https://foundry-eastus2-niq.services.ai.azure.com/providers/mistral/azure/ocr"
    
    print(f"Using endpoint URL: {url}")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Standard payload for Mistral Document AI
    payload = {
        "model": "mistral-document-ai-2505",
        "document": {
            "type": "document_url",
            "document_url": f"data:{content_type};base64,{base64_image}"
        },
        "include_image_base64": False  # Exclude base64 images to reduce response size
    }

    try:
        print("Sending request to Mistral Document AI for raw OCR processing...")
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"Response status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            
        return response.status_code, response.json()
    except Exception as e:
        print(f"Error making request: {str(e)}")
        return 500, {"error": {"message": str(e)}}

def extract_content_from_response(response_data):
    """Extract content from Mistral Document AI response
    
    Processes the raw response to extract useful information like markdown content,
    page count, and other metadata.
    """
    
    try:
        # Check if response_data is None
        if response_data is None:
            return {
                "error": "Empty response",
                "pages": [],
                "page_count": 0,
                "total_markdown_length": 0
            }
        
        # Process Mistral Document AI response
        if "pages" in response_data:
            pages = response_data.get("pages", [])
            
            # Extract markdown from each page
            all_markdown = []
            
            for page in pages:
                page_markdown = page.get("markdown", "")
                if page_markdown:
                    all_markdown.append(page_markdown)
            
            # Combine all markdown
            combined_markdown = "\n\n---PAGE BREAK---\n\n".join(all_markdown)
            
            # Get usage info
            usage_info = response_data.get("usage_info", {})
            
            return {
                "pages": pages,
                "page_count": len(pages),
                "combined_markdown": combined_markdown,
                "total_markdown_length": len(combined_markdown),
                "response_type": "mistral_ocr_raw",
                "usage_info": usage_info,
                "model": response_data.get("model", "unknown")
            }
        
        # Fallback for unexpected format
        return {
            "error": "Unrecognized response format",
            "response_keys": list(response_data.keys()) if isinstance(response_data, dict) else "not a dict",
            "response_type": "unknown"
        }
    
    except Exception as e:
        print(f"Error extracting content: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return {"error": str(e), "raw_response": response_data}

def save_raw_response(response_data, extracted_content, filename, run_id):
    """Save raw response and extracted content to files"""
    
    # Create directory structure for responses
    base_responses_dir = os.path.join("..", "..", "data", "responses", "mistral")
    os.makedirs(base_responses_dir, exist_ok=True)
    
    response_dir = os.path.join(base_responses_dir, run_id)
    os.makedirs(response_dir, exist_ok=True)
    
    # Create markdown directory
    markdown_dir = os.path.join(response_dir, "markdown")
    os.makedirs(markdown_dir, exist_ok=True)
    
    # Save raw response as JSON
    raw_file_path = os.path.join(response_dir, f"raw_{filename}")
    with open(raw_file_path, 'w', encoding='utf-8') as file:
        json.dump(response_data, file, indent=2, ensure_ascii=False)
    print(f"  Raw response saved to {raw_file_path}")
    
    # Save extraction metadata as JSON
    summary_file_path = os.path.join(response_dir, f"extracted_{filename}")
    with open(summary_file_path, 'w', encoding='utf-8') as file:
        json.dump(extracted_content, file, indent=2, ensure_ascii=False)
    print(f"  Extraction summary saved to {summary_file_path}")
    
    # Save combined markdown
    if "combined_markdown" in extracted_content and extracted_content["combined_markdown"]:
        markdown_file_path = os.path.join(markdown_dir, f"markdown_{filename.replace('.json', '.md')}")
        with open(markdown_file_path, 'w', encoding='utf-8') as file:
            file.write(extracted_content["combined_markdown"])
        print(f"  Combined markdown saved to {markdown_file_path}")
    
    # Save individual page markdown
    if "pages" in extracted_content:
        for page in extracted_content["pages"]:
            page_idx = page.get("index", 0)
            page_markdown = page.get("markdown", "")
            if page_markdown:
                page_file_path = os.path.join(markdown_dir, f"page_{page_idx}_{filename.replace('.json', '.md')}")
                with open(page_file_path, 'w', encoding='utf-8') as file:
                    file.write(f"# Page {page_idx}\n\n")
                    file.write(page_markdown)
                print(f"  Page {page_idx} markdown saved to {page_file_path}")

def main():
    """Main function for processing PDFs with raw Mistral OCR"""
    
    # Load environment variables
    load_dotenv()
    api_key = os.environ.get('AZURE_API_KEY')
    
    if not api_key:
        print("Error: AZURE_API_KEY environment variable not found")
        return
    
    # Generate unique run ID based on timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"raw_ocr_run_{timestamp}"
    
    print(f"Starting raw OCR processing run with ID: {run_id}")
    print("="*50)
    print("Configuration:")
    print("- Mode: Raw OCR processing")
    print("- Model: mistral-document-ai-2505")
    print("- Base64 images: DISABLED")
    print("="*50)
    
    try:
        # Get documents from Azure Blob Storage
        blob_names = get_container_blobs()
        print(f"Found {len(blob_names)} documents to process")
        
        successful_docs = []
        failed_docs = []
        processing_summary = []
        
        # Process each document
        for i, blob_name in enumerate(blob_names, 1):
            print(f"\n[{i}/{len(blob_names)}] Processing: {blob_name}")
            
            # Get blob as base64
            base64_image = get_blob_base64(blob_name)
            
            # Skip empty blobs
            if not base64_image:
                print(f"Skipping {blob_name} - appears to be empty")
                continue
            
            # Determine content type based on file extension
            file_ext = os.path.splitext(blob_name.lower())[1]
            if file_ext == ".pdf":
                content_type = "application/pdf"
            elif file_ext in [".png"]:
                content_type = "image/png"
            else:
                content_type = "image/jpeg"  # Default for most image formats
            
            print(f"Content type: {content_type}")
            print(f"Document size: {len(base64_image):,} bytes")
            
            # Process document for raw OCR
            status_code, response_data = process_document_raw(
                base64_image, 
                api_key, 
                content_type
            )
            
            print(f"Status Code: {status_code}")
            
            if status_code == 200:
                # Extract content from response
                extracted_content = extract_content_from_response(response_data)
                
                # Check response type for logging
                response_type = extracted_content.get("response_type", "unknown")
                print(f"Response type: {response_type}")
                
                if "error" not in extracted_content:
                    page_count = extracted_content.get("page_count", 0)
                    markdown_length = extracted_content.get("total_markdown_length", 0)
                    
                    print(f"✓ Successfully processed {page_count} pages")
                    print(f"  Markdown content: {markdown_length:,} characters")
                    
                    # Get usage info if available
                    usage_info = extracted_content.get("usage_info", {})
                    if usage_info:
                        pages_processed = usage_info.get("pages_processed", 0)
                        doc_size = usage_info.get("doc_size_bytes", 0)
                        print(f"  Pages processed: {pages_processed}, Document size: {doc_size:,} bytes")
                    
                    processing_summary.append({
                        "document": blob_name,
                        "pages": page_count,
                        "markdown_chars": markdown_length,
                        "status": "success",
                        "response_type": response_type
                    })
                    
                    successful_docs.append(blob_name)
                else:
                    print(f"⚠ Error in extraction: {extracted_content.get('error')}")
                    processing_summary.append({
                        "document": blob_name,
                        "pages": 0,
                        "status": "error",
                        "error": extracted_content.get('error')
                    })
                
                # Save results to files
                output_filename = f"{os.path.basename(blob_name).replace('.', '_')}.json"
                save_raw_response(response_data, extracted_content, output_filename, run_id)
            else:
                failed_docs.append(blob_name)
                processing_summary.append({
                    "document": blob_name,
                    "pages": 0,
                    "status": "failed",
                    "error": response_data.get("error", "Unknown error")
                })
        
        # Print final summary
        print("\n" + "="*50)
        print(f"RAW OCR PROCESSING SUMMARY FOR RUN: {run_id}")
        print("="*50)
        print(f"Total documents processed: {len(blob_names)}")
        print(f"Successfully processed: {len(successful_docs)}")
        print(f"Failed to process: {len(failed_docs)}")
        
        # Print detailed summary for each document
        if processing_summary:
            print("\nProcessing Details:")
            for summary in processing_summary:
                if summary["status"] == "success":
                    pages = summary.get('pages', 0)
                    chars = summary.get('markdown_chars', 0)
                    print(f"  ✓ {summary['document']}")
                    print(f"     Pages: {pages}, Markdown: {chars:,} chars")
                else:
                    print(f"  ✗ {summary['document']}: Failed - {summary.get('error', 'Unknown error')}")
        
        # Save summary to JSON file
        base_responses_dir = os.path.join("..", "..", "data", "responses", "mistral")
        response_dir = os.path.join(base_responses_dir, run_id)
        os.makedirs(response_dir, exist_ok=True)
        
        summary_path = os.path.join(response_dir, "processing_summary.json")
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump({
                "run_id": run_id,
                "total_documents": len(blob_names),
                "successful": len(successful_docs),
                "failed": len(failed_docs),
                "processing_summary": processing_summary
            }, f, indent=2)
        
        print(f"\nResults saved to: {os.path.abspath(response_dir)}")
        print("="*50)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    main()