import os
import base64
import json
from datetime import datetime
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult, AnalyzedDocument
from dotenv import load_dotenv
from storage_utils import get_container_blobs, download_blob_to_memory, load_environment_variables, get_blob_service_client

load_dotenv()

def _format_price(price_dict):
    """Format price dictionary to string"""
    if not price_dict:
        return "N/A"
    return "".join([f"{p}" for p in price_dict.values()])

def save_response_to_file(receipt_data, blob_name, run_id):
    """Save receipt analysis response to a JSON file"""
    # Create output directory
    output_dir = os.path.join("..", "..", "data", "responses", "document-intelligence", run_id)
    os.makedirs(output_dir, exist_ok=True)
    
    # Create filename from blob name
    safe_blob_name = blob_name.replace('/', '_').replace('\\', '_')
    output_filename = f"response_{safe_blob_name}.json"
    output_path = os.path.join(output_dir, output_filename)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(receipt_data, f, indent=2, ensure_ascii=False)
    
    print(f"Response saved to: {output_path}")
    return output_path

def process_receipt_from_blob(blob_name, document_intelligence_client, run_id):
    """Process a single receipt from blob storage"""
    print(f"\nProcessing: {blob_name}")
    
    try:
        # Get blob storage client
        storage_account_name, container_name, prefix = load_environment_variables()
        blob_service_client = get_blob_service_client(storage_account_name)
        container_client = blob_service_client.get_container_client(container_name)
        
        # Download blob data
        blob_data = download_blob_to_memory(container_client, blob_name)
        
        if not blob_data:
            print(f"Skipping {blob_name} - no data retrieved")
            return None
        
        print(f"Downloaded {len(blob_data)} bytes from blob storage")
        
        # Analyze document by passing the bytes payload directly
        poller = document_intelligence_client.begin_analyze_document(
            "prebuilt-receipt",
            blob_data,
            content_type="application/octet-stream"
        )
        
        receipts: AnalyzeResult = poller.result()
        
        # Save raw response
        receipt_dict = receipts.as_dict() if hasattr(receipts, 'as_dict') else {}
        save_response_to_file(receipt_dict, blob_name, run_id)
        
        return receipts
        
    except Exception as e:
        print(f"Error processing {blob_name}: {str(e)}")
        return None

def main():
    """Main function to process all receipts from blob storage"""
    # Load environment variables
    endpoint = os.environ.get("DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.environ.get("DOCUMENT_INTELLIGENCE_KEY")

    if not endpoint or not key:
        print("Error: DOCUMENT_INTELLIGENCE_ENDPOINT and DOCUMENT_INTELLIGENCE_KEY must be set in .env")
        return
    
    print(f"Using endpoint: {endpoint}")
    print(f"Using API key: {key[:10]}..." if key else "No key found")
    
    # Create Document Intelligence client
    document_intelligence_client = DocumentIntelligenceClient(
        endpoint=endpoint, 
        credential=AzureKeyCredential(key)
    )
    
    # Generate run ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{timestamp}"
    print(f"Starting Document Intelligence processing run: {run_id}")
    
    # Get all receipt blobs
    print("\nFetching receipts from blob storage...")
    blob_names = get_container_blobs()
    
    if not blob_names:
        print("No receipt images found in blob storage")
        return
    
    print(f"Found {len(blob_names)} receipts to process\n")
    print("="*60)
    
    # Process each receipt
    successful = 0
    failed = 0
    
    for i, blob_name in enumerate(blob_names, 1):
        print(f"\n[{i}/{len(blob_names)}] Processing: {blob_name}")
        print("-"*60)
        
        receipts = process_receipt_from_blob(blob_name, document_intelligence_client, run_id)
        
        if not receipts:
            print(f"Failed to process {blob_name}")
            failed += 1
            continue
        
        # Display extracted information
        if receipts.documents:
            for idx, receipt in enumerate(receipts.documents):
                print(f"\n--------Analysis of receipt #{idx + 1}--------")
                print(f"Receipt type: {receipt.doc_type if receipt.doc_type else 'N/A'}")
                
                if receipt.fields:
                    merchant_name = receipt.fields.get("MerchantName")
                    if merchant_name:
                        print(
                            f"Merchant Name: {merchant_name.get('valueString')} has confidence: "
                            f"{merchant_name.confidence}"
                        )
                    
                    transaction_date = receipt.fields.get("TransactionDate")
                    if transaction_date:
                        print(
                            f"Transaction Date: {transaction_date.get('valueDate')} has confidence: "
                            f"{transaction_date.confidence}"
                        )
                    
                    items = receipt.fields.get("Items")
                    if items:
                        print("Receipt items:")
                        for idx, item in enumerate(items.get("valueArray")):
                            print(f"...Item #{idx + 1}")
                            item_description = item.get("valueObject").get("Description")
                            if item_description:
                                print(
                                    f"......Item Description: {item_description.get('valueString')} has confidence: "
                                    f"{item_description.confidence}"
                                )
                            item_quantity = item.get("valueObject").get("Quantity")
                            if item_quantity:
                                print(
                                    f"......Item Quantity: {item_quantity.get('valueString')} has confidence: "
                                    f"{item_quantity.confidence}"
                                )
                            item_total_price = item.get("valueObject").get("TotalPrice")
                            if item_total_price:
                                print(
                                    f"......Total Item Price: {_format_price(item_total_price.get('valueCurrency'))} has confidence: "
                                    f"{item_total_price.confidence}"
                                )
                    
                    subtotal = receipt.fields.get("Subtotal")
                    if subtotal:
                        print(
                            f"Subtotal: {_format_price(subtotal.get('valueCurrency'))} has confidence: {subtotal.confidence}"
                        )
                    
                    tax = receipt.fields.get("TotalTax")
                    if tax:
                        print(f"Total tax: {_format_price(tax.get('valueCurrency'))} has confidence: {tax.confidence}")
                    
                    tip = receipt.fields.get("Tip")
                    if tip:
                        print(f"Tip: {_format_price(tip.get('valueCurrency'))} has confidence: {tip.confidence}")
                    
                    total = receipt.fields.get("Total")
                    if total:
                        print(f"Total: {_format_price(total.get('valueCurrency'))} has confidence: {total.confidence}")
                
                print("--------------------------------------")
            
            successful += 1
        else:
            print("No receipt documents found in analysis result")
            failed += 1
    
    # Print summary
    print("\n" + "="*60)
    print(f"PROCESSING SUMMARY FOR RUN: {run_id}")
    print("="*60)
    print(f"Total receipts processed: {len(blob_names)}")
    print(f"Successfully processed: {successful}")
    print(f"Failed to process: {failed}")
    print(f"\nResponses saved to: data/responses/document-intelligence/{run_id}/")
    print("="*60)


if __name__ == "__main__":
    main()