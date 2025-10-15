#!/usr/bin/env python
"""
Verification script for Mistral Document AI load testing
"""
import os
import sys
import json
import time
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

# Get script directory
SCRIPT_DIR = Path(__file__).parent.absolute()

def verify_endpoint():
    """
    Verify that the Mistral API endpoint is accessible
    """
    # Load environment variables
    load_dotenv()
    api_key = os.environ.get('AZURE_API_KEY')
    
    # Use the same hardcoded endpoint from the load test script
    endpoint = "https://foundry-eastus2-niq.services.ai.azure.com/providers/mistral/azure/ocr"
    
    if not api_key:
        print("ERROR: AZURE_API_KEY not set in .env file")
        return False
        
    # Create a minimal sample image (1x1 transparent PNG)
    sample_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    content_type = "image/png"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": "mistral-document-ai-2505",
        "document": {
            "type": "image_url",
            "image_url": f"data:{content_type};base64,{sample_base64}"
        },
        "include_image_base64": False
    }
    
    print(f"Verifying Mistral API endpoint: {endpoint}")
    try:
        start = time.perf_counter()
        response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        latency_ms = (time.perf_counter() - start) * 1000.0
        
        print(f"Response status code: {response.status_code}")
        print(f"Response time: {latency_ms:.2f} ms")
        
        if 200 <= response.status_code < 300:
            print("API endpoint verification: SUCCESS")
            return True
        else:
            print(f"API endpoint verification: FAILED - HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"API endpoint verification: ERROR - {e}")
        return False

def verify_telemetry_packages():
    """
    Verify that the required telemetry packages are installed
    """
    print("\nChecking telemetry package availability...")
    
    # Check OpenTelemetry packages
    try:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        print("✓ OpenTelemetry packages are installed")
        otel_available = True
    except ImportError:
        print("✗ OpenTelemetry packages not found")
        otel_available = False
        
    # Check Azure Monitor exporter
    try:
        from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
        print("✓ Azure Monitor exporter is installed")
        azure_monitor_available = True
    except ImportError:
        print("✗ Azure Monitor exporter not found")
        azure_monitor_available = False
        
    # Check Application Insights fallback
    try:
        from applicationinsights import TelemetryClient
        print("✓ Application Insights SDK is installed")
        app_insights_available = True
    except ImportError:
        print("✗ Application Insights SDK not found")
        app_insights_available = False
        
    return {
        'otel_available': otel_available,
        'azure_monitor_available': azure_monitor_available,
        'app_insights_available': app_insights_available
    }
    
def verify_storage_access():
    """
    Verify access to Azure Blob Storage
    """
    print("\nVerifying Azure Blob Storage access...")
    
    try:
        # Import the storage_utils module directly
        sys.path.insert(0, str(SCRIPT_DIR))
        from storage_utils import get_all_blobs_with_prefix
        
        # Get all blobs with the configured prefix
        blobs = get_all_blobs_with_prefix()
        
        if blobs:
            print(f"✓ Successfully accessed storage - found {len(blobs)} blobs")
            print(f"First few blobs: {', '.join(blobs[:3])}...")
            return True
        else:
            print("✓ Storage accessible but no blobs found with current prefix")
            return True
            
    except Exception as e:
        print(f"✗ Storage access verification failed: {e}")
        return False

def print_summary(results):
    """
    Print a summary of verification results
    """
    print("\n=== VERIFICATION SUMMARY ===")
    
    all_success = all(results.values())
    
    for name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{name}: {status}")
        
    print("\nOverall Status: " + ("✓ PASS" if all_success else "✗ FAIL"))
    
    return all_success

if __name__ == "__main__":
    print("=== Mistral Document AI Load Test Verification ===\n")
    
    results = {
        "API Endpoint": verify_endpoint(),
        "Storage Access": verify_storage_access()
    }
    
    # Add telemetry results
    telemetry_results = verify_telemetry_packages()
    results.update({
        "OpenTelemetry": telemetry_results['otel_available'],
        "Azure Monitor": telemetry_results['azure_monitor_available'],
        "App Insights": telemetry_results['app_insights_available']
    })
    
    success = print_summary(results)
    sys.exit(0 if success else 1)