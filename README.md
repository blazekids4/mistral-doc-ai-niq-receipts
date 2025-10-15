# Mistral Document AI with Azure Blob Storage

This project demonstrates how to use Mistral Document AI to process documents stored in Azure Blob Storage, authenticating with Entra ID (formerly Azure AD). It provides utilities for retrieving documents from Azure Storage and analyzing them with Mistral Document AI's OCR capabilities.

## Project Structure

- `mistral-scripts/process_documents.py`: Main script to process documents from Azure Blob Storage using Mistral Document AI
- `mistral-scripts/storage_utils.py`: Utilities for accessing Azure Blob Storage with Entra ID authentication

## Setup

1. Make sure you have the required packages:

   ```bash
   pip install -r requirements.txt
   ```

2. Configure the `.env` file with your Azure settings:

   ```env
   PROJECT_ENDPOINT="https://your-foundry-instance.services.ai.azure.com/api/projects/yourProject"
   STORAGE_ACCOUNT_NAME="your-storage-account"
   STORAGE_CONTAINER_NAME="your-container"
   STORAGE_PREFIX="optional-prefix"
   AZURE_API_KEY="your-api-key"
   ```

3. Ensure your user account has been granted the "Storage Blob Data Reader" role for the Azure Storage account or container.

## Usage

### Authentication

This project uses the DefaultAzureCredential from the Azure Identity library, which supports multiple authentication methods:

1. Environment variables
2. Managed Identity
3. Visual Studio Code sign-in
4. Azure CLI sign-in
5. Azure PowerShell sign-in
6. Interactive browser sign-in

Make sure you're logged in with `az login` or another supported method before running the scripts.

### Testing Azure Blob Storage Access

To test if you can access the blob storage and list files:

```bash
python mistral-scripts/storage_utils.py
```

### Processing Documents

To process all documents from the configured container and prefix:

```bash
python mistral-scripts/process_documents.py
```

The script will:

1. Connect to Azure Blob Storage using Entra ID authentication
2. Retrieve all blobs matching the specified prefix
3. Skip empty blobs or directory entries
4. Detect file type based on extension
5. Process each document using Mistral Document AI
6. Save the response for each document to a JSON file

## Supported File Types

The script automatically detects the following file types:

- JPEG (default)
- PNG
- PDF

## Output

For each processed document, a JSON file is created with the following naming pattern:

```text
response_<filename_with_dots_replaced>.json
```

The JSON output contains the OCR results from Mistral Document AI, including:

- Text content extracted from the image (markdown format)
- Page dimensions and DPI information
- Usage information

## Load Testing Tool

The project includes a tool for load testing the Mistral Document AI API to measure latency and reliability:

```bash
python mistral-scripts/mistral_load_test.py
```

### Verification Scripts

Before running a full load test, you can use these verification scripts to ensure everything is configured correctly:

```bash
# Verify API endpoint, storage access, and telemetry packages
python mistral-scripts/verify_load_test.py

# Run a minimal load test with just 3 iterations
python mistral-scripts/test_load.py
```

### Load Test Features

- Runs multiple iterations (default: 50) against the Mistral OCR endpoint
- Tracks latency metrics, success rates, and errors
- Outputs detailed CSV and summary JSON reports
- Avoids rate limits with pacing and exponential backoff on 429s
- Supports real documents from your storage or a small sample image
- Sends telemetry to Application Insights if configured
- Supports both synchronous and asynchronous execution

### Load Test Options

- `--iterations N`: Number of API calls to make (default: 50)
- `--use-real-blobs`: Use real blobs from configured storage instead of sample image
- `--async`: Use async HTTP client with concurrency (faster, requires aiohttp)
- `--concurrency N`: Max concurrent requests when using async mode (default: 5)
- `--csv-path PATH`: Custom output CSV path

### Load Test Examples

```bash
# Basic test with 50 iterations using tiny sample image
python mistral-scripts/mistral_load_test.py

# Test with 100 iterations using real blobs from storage
python mistral-scripts/mistral_load_test.py --iterations 100 --use-real-blobs

# Fast test with async mode and 10 concurrent requests
python mistral-scripts/mistral_load_test.py --iterations 200 --async --concurrency 10
```

### Load Test Output

The test produces two output files:

1. CSV file with per-request metrics:
   - `data/responses/load_test_<timestamp>.csv`
   - Contains: iteration, attempt, timestamp, status_code, latency_ms, success, error, blob_name

2. JSON summary with statistics:
   - `data/responses/load_test_summary_<timestamp>.json`
   - Contains: count, min_ms, max_ms, mean_ms, median_ms, p50_ms, p90_ms, p95_ms, p99_ms, stdev_ms

## Troubleshooting

- **404 Error**: Check your API endpoint URL and API key. Note that the load test script uses a hardcoded endpoint URL that matches process_documents.py rather than PROJECT_ENDPOINT from .env to avoid 404 errors
- **Empty Blob**: Check that your prefix is correctly pointing to actual files
- **Authentication Error**: Make sure you're logged in with `az login`
- **Missing Packages**: Ensure you've installed all requirements with `pip install -r requirements.txt`
- **Telemetry Errors**: If you see errors with OpenTelemetry like "ObservableGauge object has no attribute 'record'", the script will automatically fall back to Application Insights SDK or disable telemetry
