import requests
import time
import json
import sys

class AzureContentUnderstandingClient:
    """Client for Azure AI Content Understanding API - Image Analysis"""
    
    def __init__(self, endpoint, api_key):
        """
        Initialize the client with Azure endpoint and API key.
        
        Args:
            endpoint: Your Azure AI Foundry endpoint URL
            api_key: Your Azure AI subscription key
        """
        self.endpoint = endpoint.rstrip('/')
        self.api_key = api_key
        self.api_version = "2025-05-01-preview"
        self.analyzer_id = "prebuilt-imageAnalyzer"
        
    def analyze_image(self, image_url, polling_interval=1, max_attempts=60):
        """
        Analyze an image using the Content Understanding API.
        
        Args:
            image_url: Publicly accessible URL of the image to analyze
            polling_interval: Time in seconds between status checks (default: 1)
            max_attempts: Maximum number of polling attempts (default: 60)
            
        Returns:
            dict: JSON response with analysis results
        """
        # Step 1: Submit the analysis request
        analyze_url = f"{self.endpoint}/contentunderstanding/analyzers/{self.analyzer_id}:analyze?api-version={self.api_version}"
        
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "url": image_url
        }
        
        print(f"Submitting image for analysis: {image_url}")
        
        try:
            response = requests.post(analyze_url, headers=headers, json=payload)
            response.raise_for_status()
            
            # Extract request ID from response
            initial_result = response.json()
            request_id = initial_result.get("id")
            
            if not request_id:
                raise ValueError("No request ID returned from API")
                
            print(f"Analysis submitted. Request ID: {request_id}")
            print(f"Status: {initial_result.get('status', 'Unknown')}")
            
            # Step 2: Poll for results
            return self._poll_for_results(request_id, polling_interval, max_attempts)
            
        except requests.exceptions.RequestException as e:
            print(f"Error during API request: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text}")
            sys.exit(1)
    
    def _poll_for_results(self, request_id, polling_interval, max_attempts):
        """
        Poll the API for analysis results until completion.
        
        Args:
            request_id: The ID returned from the initial analysis request
            polling_interval: Time in seconds between status checks
            max_attempts: Maximum number of polling attempts
            
        Returns:
            dict: Complete JSON response with analysis results
        """
        results_url = f"{self.endpoint}/contentunderstanding/analyzerResults/{request_id}?api-version={self.api_version}"
        
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key
        }
        
        attempts = 0
        
        while attempts < max_attempts:
            time.sleep(polling_interval)
            attempts += 1
            
            try:
                response = requests.get(results_url, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                status = result.get("status", "Unknown")
                
                print(f"Polling attempt {attempts}/{max_attempts} - Status: {status}")
                
                if status == "Succeeded":
                    print("Analysis completed successfully!")
                    return result
                elif status == "Failed":
                    print("Analysis failed!")
                    return result
                elif status in ["Running", "NotStarted"]:
                    # Continue polling
                    continue
                else:
                    print(f"Unknown status: {status}")
                    return result
                    
            except requests.exceptions.RequestException as e:
                print(f"Error during polling: {str(e)}")
                sys.exit(1)
        
        print(f"Timeout: Analysis did not complete within {max_attempts} attempts")
        return {"error": "Timeout waiting for results"}


def main():
    """Main function with example usage"""
    
    # REPLACE THESE WITH YOUR ACTUAL VALUES
    ENDPOINT = "https://your-resource.cognitiveservices.azure.com"
    API_KEY = "your-api-key-here"
    
    # Example image URL (replace with your own)
    IMAGE_URL = "https://github.com/Azure-Samples/azure-ai-content-understanding-python/raw/refs/heads/main/data/pieChart.jpg"
    
    # Initialize the client
    client = AzureContentUnderstandingClient(ENDPOINT, API_KEY)
    
    # Analyze the image
    result = client.analyze_image(IMAGE_URL)
    
    # Save results to JSON file
    output_file = "image_analysis_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_file}")
    
    # Pretty print key information
    if result.get("status") == "Succeeded":
        print("\n=== Analysis Summary ===")
        content = result.get("result", {}).get("contents", [])
        if content:
            # Print markdown description if available
            markdown = content[0].get("markdown", "")
            if markdown:
                print(f"Description: {markdown[:200]}...")
            
            # Print extracted fields if available
            fields = content[0].get("fields", {})
            if fields:
                print("\nExtracted Fields:")
                for field_name, field_data in fields.items():
                    field_value = field_data.get("valueString", field_data.get("value", "N/A"))
                    print(f"  - {field_name}: {field_value}")
    
    return result


if __name__ == "__main__":
    main()