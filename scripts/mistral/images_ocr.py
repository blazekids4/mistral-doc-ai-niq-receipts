import requests
import os
import json
import datetime
from dotenv import load_dotenv
from storage_utils import get_container_blobs, get_blob_base64

load_dotenv()

def process_document(base64_image, api_key, content_type="image/jpeg"):
    """Process a document using Mistral Document AI"""
    # Use the correct working endpoint for Mistral Document AI
    url = "https://foundry-eastus2-niq.services.ai.azure.com/providers/mistral/azure/ocr"
    
    print(f"Using endpoint URL: {url}")

    # Headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Request body
    payload = {
        "model": "mistral-document-ai-2505", # Verified working model name
        "document": {
            "type": "image_url",
            "image_url": f"data:{content_type};base64,{base64_image}"
        },
        "include_image_base64": False  # Set to False to reduce response size
    }

    # Make the POST request
    try:
        print("Sending request to Mistral Document AI...")
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"Response status code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            
        return response.status_code, response.json()
    except Exception as e:
        print(f"Error making request: {str(e)}")
        return 500, {"error": {"message": str(e)}}

def save_response_to_file(response_data, filename, run_id):
    """Save response to a JSON file in a directory specific to this run"""
    # Ensure base responses directory exists
    base_responses_dir = os.path.join("..", "data", "responses")
    os.makedirs(base_responses_dir, exist_ok=True)
    
    # Create a responses directory with the run ID
    response_dir = os.path.join(base_responses_dir, run_id)
    os.makedirs(response_dir, exist_ok=True)
    
    # Full path for the response file
    file_path = os.path.join(response_dir, filename)
    
    with open(file_path, 'w') as file:
        json.dump(response_data, file, indent=2)
    print(f"Response saved to {file_path}")

def main():
    # Load environment variables
    load_dotenv()
    api_key = os.environ.get('AZURE_API_KEY')
    project_endpoint = os.environ.get('PROJECT_ENDPOINT')
    
    # Generate a unique run ID using current timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{timestamp}"
    print(f"Starting processing run with ID: {run_id}")
    
    print(f"Project endpoint: {project_endpoint}")
    if not api_key:
        print("Error: AZURE_API_KEY environment variable not found")
        return
    else:
        # Display first few characters of API key to verify it's loaded
        print(f"API key found (first 5 chars): {api_key[:5]}...")
    
    # Get all blobs with the specified prefix
    try:
        blob_names = get_container_blobs()
        print(f"Found {len(blob_names)} documents to process")
        
        # Keep track of successful and failed documents
        successful_docs = []
        failed_docs = []
        
        for i, blob_name in enumerate(blob_names, 1):
            print(f"Processing document {i}/{len(blob_names)}: {blob_name}")
            
            # Get blob as base64
            base64_image = get_blob_base64(blob_name)
            
            # Skip empty blobs (likely directories)
            if not base64_image:
                print(f"Skipping {blob_name} - appears to be empty or a directory")
                continue
                
            # Determine file extension and content type
            file_ext = os.path.splitext(blob_name.lower())[1]
            content_type = "image/jpeg"  # Default
            if file_ext in [".png"]:
                content_type = "image/png"
            elif file_ext in [".pdf"]:
                content_type = "application/pdf"
            
            print(f"File type detected: {content_type} (data length: {len(base64_image)} bytes)")
            
            # Process the document
            status_code, response_data = process_document(base64_image, api_key, content_type)
            
            print(f"Status Code: {status_code}")
            
            # Save response to file with unique run ID included
            output_filename = f"response_{os.path.basename(blob_name).replace('.', '_')}.json"
            save_response_to_file(response_data, output_filename, run_id)
            
            # Track success/failure
            if status_code == 200:
                successful_docs.append(blob_name)
            else:
                failed_docs.append(blob_name)
        
        # Print summary at the end
        print("\n" + "="*50)
        print(f"PROCESSING SUMMARY FOR RUN: {run_id}")
        print("="*50)
        print(f"Total documents processed: {len(blob_names)}")
        print(f"Successfully processed: {len(successful_docs)}")
        print(f"Failed to process: {len(failed_docs)}")
        if failed_docs:
            print("\nFailed documents:")
            for doc in failed_docs:
                print(f" - {doc}")
        print("\nResponses saved to directory:")
        base_responses_dir = os.path.join("..", "data", "responses")
        print(f"{os.path.abspath(os.path.join(base_responses_dir, run_id))}")
        print("="*50)
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()