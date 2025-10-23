import os
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient
import io
import base64
from dotenv import load_dotenv

# Cache credential at module level to avoid repeated authentication
_cached_credential = None
_cached_blob_service_client = None
_cached_account_name = None

def get_cached_credential():
    """Get or create a cached DefaultAzureCredential instance"""
    global _cached_credential
    if _cached_credential is None:
        _cached_credential = DefaultAzureCredential()
    return _cached_credential

def load_environment_variables():
    """Load environment variables from .env file"""
    load_dotenv()
    
    storage_account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
    storage_container_name = os.environ.get("STORAGE_CONTAINER_NAME")
    # Normalize prefix: ensure it ends with a slash if non-empty and does not start with a leading slash
    raw_prefix = os.environ.get("STORAGE_PREFIX", "")  # Default to empty string if not provided
    storage_prefix = ""
    if raw_prefix:
        storage_prefix = raw_prefix.lstrip('/').rstrip('/') + '/'
    
    return storage_account_name, storage_container_name, storage_prefix

def get_blob_service_client(account_name):
    """Get a blob service client using cached DefaultAzureCredential"""
    global _cached_blob_service_client, _cached_account_name
    
    # Return cached client if it exists and is for the same account
    if _cached_blob_service_client and _cached_account_name == account_name:
        return _cached_blob_service_client
    
    # Create new client with cached credential
    account_url = f"https://{account_name}.blob.core.windows.net"
    credential = get_cached_credential()
    _cached_blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
    _cached_account_name = account_name
    
    return _cached_blob_service_client

def list_blobs_with_prefix(container_client, prefix=""):
    """List all blobs with the given prefix"""
    return [blob for blob in container_client.list_blobs(name_starts_with=prefix)]

def download_blob_to_memory(container_client, blob_name):
    """Download a blob to memory"""
    blob_client = container_client.get_blob_client(blob_name)
    download_stream = blob_client.download_blob()
    return download_stream.readall()

def encode_blob_to_base64(blob_data):
    """Encode blob data to base64 string"""
    return base64.b64encode(blob_data).decode('utf-8')

def get_blob_base64(blob_name):
    """Get a specific blob and convert it to base64"""
    storage_account_name, container_name, prefix = load_environment_variables()

    blob_service_client = get_blob_service_client(storage_account_name)
    container_client = blob_service_client.get_container_client(container_name)

    # If blob_name is provided as a relative name, prepend the configured prefix
    resolved_blob_name = blob_name
    if prefix and not blob_name.startswith(prefix):
        resolved_blob_name = prefix + blob_name.lstrip('/')

    blob_data = download_blob_to_memory(container_client, resolved_blob_name)
    return encode_blob_to_base64(blob_data)

def list_all_blobs_in_container(max_results=100):
    """List all blobs in the container for debugging purposes"""
    storage_account_name, container_name, _ = load_environment_variables()
    
    try:
        blob_service_client = get_blob_service_client(storage_account_name)
        container_client = blob_service_client.get_container_client(container_name)
        
        print(f"\nListing all blobs in container '{container_name}' (limited to {max_results}):")
        all_blobs = list(container_client.list_blobs())[:max_results]
        
        if all_blobs:
            for blob in all_blobs:
                print(f" - {blob.name}")
            
            if len(all_blobs) == max_results:
                print(f"... (showing first {max_results} results only)")
        else:
            print(" - No blobs found in container")
            
        return all_blobs
    except Exception as e:
        print(f"Error listing all blobs: {str(e)}")
        return []

def get_container_blobs():
    """Get all blobs from the container with the prefix specified in environment variables"""
    storage_account_name, container_name, configured_prefix = load_environment_variables()

    print(f"Storage account: {storage_account_name}")
    print(f"Container name: {container_name}")

    # Use configured prefix from .env if present; otherwise use empty string to get all files
    receipts_prefix = configured_prefix or ""
    print(f"Looking for blobs with prefix: {receipts_prefix}")
    
    try:
        blob_service_client = get_blob_service_client(storage_account_name)
        container_client = blob_service_client.get_container_client(container_name)

        # List all blob prefixes for debugging
        print("Available prefixes in the container:")
        unique_prefixes = set()
        all_blobs = list(container_client.list_blobs())
        for blob in all_blobs:
            parts = blob.name.split('/')
            if len(parts) > 1:
                prefix = parts[0] + '/'
                unique_prefixes.add(prefix)

        if unique_prefixes:
            for prefix in sorted(unique_prefixes):
                print(f" - {prefix}")
        else:
            print(" - No prefixes found (flat structure)")

        # Return the blobs with our target prefix
        container_blobs = [blob.name for blob in container_client.list_blobs(name_starts_with=receipts_prefix)]

        if not container_blobs:
            print(f"\nWARNING: No blobs found with prefix '{receipts_prefix}'")
            print("Try one of these alternatives based on your container structure:")

            # List common prefixes found in the container for the user to try
            for prefix in sorted(unique_prefixes)[:5]:  # Show up to 5 options
                print(f" - Try using '{prefix}' as the prefix in your .env file")

            # Suggest checking top-level blobs
            print(" - Try using an empty prefix to list all blobs")

            # List all blobs for better debugging
            list_all_blobs_in_container()

        return container_blobs
    except Exception as e:
        print(f"Error connecting to blob storage: {str(e)}")
        return []

def set_receipts_prefix(new_prefix):
    """
    Update the current receipts prefix path.
    
    Args:
        new_prefix (str): The new prefix path (e.g., 'receipts/' or 'documents/receipts/')
        
    Returns:
        list: List of blob names with the new prefix
    """
    # This is a simple function that returns blobs with the specified prefix
    # Useful for testing different prefixes after seeing what's available
    storage_account_name, container_name, _ = load_environment_variables()
    
    try:
        blob_service_client = get_blob_service_client(storage_account_name)
        container_client = blob_service_client.get_container_client(container_name)
        
        print(f"Looking for blobs with custom prefix: '{new_prefix}'")
        blobs = [blob.name for blob in container_client.list_blobs(name_starts_with=new_prefix)]
        
        print(f"Found {len(blobs)} blobs with prefix '{new_prefix}'")
        for name in blobs[:10]:  # Limit display to first 10
            print(f" - {name}")
            
        if len(blobs) > 10:
            print(f"... and {len(blobs) - 10} more")
            
        return blobs
    except Exception as e:
        print(f"Error using custom prefix: {str(e)}")
        return []

if __name__ == "__main__":
    # Test functionality
    try:
        print("\n=== TESTING STORAGE UTILS ===")
        print("1. Looking for blobs using configured prefix from .env...")
        blob_names = get_container_blobs()
        print(f"\nFound {len(blob_names)} files in the container using configured prefix")
        
        if blob_names:
            for name in blob_names:
                print(f" - {name}")
                
            # Get the first blob as an example. Pass only the blob's filename relative to prefix if prefix used
            first_blob = blob_names[0]
            # If the configured prefix is set and the blob name already contains it, pass the trailing part to get_blob_base64
            _, _, configured_prefix = load_environment_variables()
            if configured_prefix and first_blob.startswith(configured_prefix):
                relative_name = first_blob[len(configured_prefix):]
            else:
                relative_name = first_blob

            base64_data = get_blob_base64(relative_name)
            print(f"Successfully encoded blob {first_blob} to base64")
            print(f"Base64 string length: {len(base64_data)}")
        else:
            print("\n2. No blobs found with the configured prefix. Listing all blobs...")
            list_all_blobs_in_container()
            
            print("\nIf you see relevant files above, you can test a custom prefix by running:")
            print("python -c \"import storage_utils; storage_utils.set_receipts_prefix('your/prefix/')\"")
            print("Or update the STORAGE_PREFIX value in your .env file")
            
    except Exception as e:
        print(f"Error: {str(e)}")