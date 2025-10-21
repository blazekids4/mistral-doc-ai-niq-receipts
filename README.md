# Mistral Document AI with Azure Blob Storage

A Python-based solution for automated document processing using Mistral Document AI and Azure Blob Storage. This project demonstrates enterprise-grade OCR capabilities with Azure integration, providing tools for document processing, load testing, and performance monitoring.

## Table of Contents

- [Summary](#summary)
- [Value Proposition](#value-proposition)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Usage](#usage)
- [Load Testing](#load-testing)
- [Supported File Types](#supported-file-types)
- [Output Format](#output-format)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Summary

This project provides a complete solution for processing documents stored in Azure Blob Storage using Mistral Document AI's OCR capabilities. It includes:

- **Document Processing Pipeline**: Automated retrieval and processing of documents from Azure Blob Storage
- **Authentication**: Secure Entra ID (Azure AD) authentication using DefaultAzureCredential
- **Load Testing Framework**: Comprehensive performance testing with metrics collection
- **Telemetry Integration**: Application Insights and OpenTelemetry support for monitoring
- **Batch Processing**: Efficient processing of multiple documents with detailed reporting

## Value Proposition

### Business Value

- **Automated Document Processing**: Eliminate manual data entry by automatically extracting text and structured data from receipts, invoices, and other documents
- **Scalability**: Process thousands of documents efficiently with batch processing and concurrent execution
- **Cost Optimization**: Understand API performance and costs through detailed metrics and load testing
- **Azure Integration**: Leverage existing Azure infrastructure with seamless Blob Storage and Identity integration
- **Quality Assurance**: Built-in verification tools ensure reliable operation before production deployment

### Technical Value

- **Enterprise Security**: Uses Azure Entra ID for secure, credential-less authentication
- **Performance Monitoring**: Track latency, throughput, and error rates with detailed metrics
- **Flexible Architecture**: Support for synchronous and asynchronous processing modes
- **Observability**: Integrated telemetry with Application Insights and OpenTelemetry
- **Production Ready**: Includes error handling, retry logic, and rate limiting

## How It Works

### Architecture Overview

```
┌─────────────────────┐
│   Azure Blob        │
│   Storage           │◄─── Documents (PDFs, Images)
└──────────┬──────────┘
           │
           │ DefaultAzureCredential
           │ (Entra ID Auth)
           ▼
┌─────────────────────┐
│  Storage Utils      │
│  - List Blobs       │
│  - Download         │
│  - Base64 Encode    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Processing Scripts │
│  - Image OCR        │
│  - PDF OCR          │
│  - Load Testing     │
└──────────┬──────────┘
           │
           │ HTTPS + API Key
           ▼
┌─────────────────────┐
│  Mistral Document   │
│  AI (OCR)           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Results Storage    │
│  - JSON Responses   │
│  - CSV Metrics      │
│  - Telemetry        │
└─────────────────────┘
```

### Processing Flow

1. **Authentication**: The application authenticates to Azure using `DefaultAzureCredential`, which supports multiple methods (Azure CLI, Managed Identity, Interactive login, etc.)

2. **Document Retrieval**: 
   - Connects to Azure Blob Storage using the Storage Blob Data Reader role
   - Lists all blobs in the specified container
   - Downloads documents as needed for processing

3. **Document Processing**:
   - **Images** (`images_ocr.py`): Processes individual image files (PNG, JPG, JPEG)
   - **PDFs** (`pdfs_ocr_raw.py`): Processes PDF documents with chunking support for large files
   - Encodes documents in Base64 format for API transmission

4. **Mistral API Integration**:
   - Sends documents to Mistral Document AI endpoint
   - Supports both synchronous and asynchronous processing modes
   - Implements retry logic and error handling
   - Tracks performance metrics (latency, tokens, costs)

5. **Results Storage**:
   - Saves OCR responses as JSON files with timestamps
   - Generates CSV reports for load testing metrics
   - Optionally sends telemetry to Application Insights

### Key Components

#### Storage Utilities (`storage_utils.py`)

Handles all Azure Blob Storage operations:
- **Authentication**: Entra ID-based authentication
- **Blob Listing**: Enumerate files in containers
- **Download**: Retrieve blob content
- **Base64 Encoding**: Prepare documents for API transmission

#### Image OCR (`images_ocr.py`)

Processes individual image files:
- Supports common image formats (PNG, JPG, JPEG)
- Extracts text from receipts and documents
- Saves structured JSON responses

#### PDF OCR (`pdfs_ocr_raw.py`)

Processes PDF documents:
- Handles multi-page PDFs
- Supports chunking for large documents
- Raw text extraction with structured output

#### Load Testing (`mistral_load_test.py`)

Comprehensive performance testing:
- Concurrent request processing
- Detailed metrics collection (latency, throughput, error rates)
- CSV and JSON reporting
- Performance baseline establishment

## Project Structure

```
mistral-doc-ai-niq-receipts/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── data/
│   ├── ground-truth/                 # Reference data for validation
│   │   └── doc_intel_single_capture_response.json
│   ├── inputs/                       # Input documents (not in repo)
│   └── responses/                    # Processing results
│       ├── content-understanding/    # Alternative OCR results
│       └── mistral/                  # Mistral API responses
│           ├── *.json                # Individual responses
│           ├── *.csv                 # Load test metrics
│           └── run_*/                # Timestamped batch runs
├── scripts/
│   ├── content-understanding/
│   │   └── content_understanding.py  # Alternative OCR implementation
│   └── mistral/
│       ├── storage_utils.py          # Azure Blob Storage utilities
│       ├── images_ocr.py             # Image processing script
│       ├── pdfs_ocr_raw.py           # PDF processing script
│       └── load-tests/
│           ├── mistral_load_test.py  # Load testing framework
│           └── test_load.py          # Load test execution
```

## Prerequisites

- **Python**: 3.8 or higher
- **Azure Account**: Active Azure subscription
- **Azure Resources**:
  - Azure Blob Storage account
  - Storage container with documents
- **Mistral AI**: API key for Mistral Document AI
- **Azure Permissions**:
  - Storage Blob Data Reader role on the storage account
  - Entra ID authentication configured

## Setup

### 1. Clone the Repository

```powershell
git clone https://github.com/blazekids4/mistral-doc-ai-niq-receipts.git
cd mistral-doc-ai-niq-receipts
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure Azure Authentication

Authenticate using Azure CLI (recommended for local development):

```powershell
az login
```

For production environments, use Managed Identity or Service Principal.

### 4. Set Environment Variables

Create a `.env` file or set environment variables:

```powershell
# Mistral API Configuration
$env:MISTRAL_API_KEY = "your-mistral-api-key"

# Azure Storage Configuration
$env:AZURE_STORAGE_ACCOUNT_NAME = "your-storage-account"
$env:AZURE_STORAGE_CONTAINER_NAME = "your-container-name"

# Optional: Application Insights
$env:APPLICATIONINSIGHTS_CONNECTION_STRING = "your-connection-string"
```

### 5. Verify Setup

Test your configuration:

```powershell
python scripts/mistral/storage_utils.py
```

## Usage

### Process Images

Process individual image files from Azure Blob Storage:

```powershell
cd scripts/mistral
python images_ocr.py
```

This will:
- List all images in the specified container
- Process each image through Mistral Document AI
- Save results to `data/responses/mistral/`

### Process PDFs

Process PDF documents:

```powershell
cd scripts/mistral
python pdfs_ocr_raw.py
```

Features:
- Automatic chunking for large PDFs
- Multi-page document support
- Structured text extraction

### Run Load Tests

Execute performance testing:

```powershell
cd scripts/mistral/load-tests
python mistral_load_test.py
```

This generates:
- **CSV Report**: Detailed metrics for each request
- **JSON Summary**: Aggregated statistics (avg latency, throughput, costs)
- **Console Output**: Real-time progress and results

### Custom Processing

You can also import the utilities in your own scripts:

```python
from storage_utils import StorageUtils

# Initialize storage client
storage = StorageUtils(
    account_name="your-account",
    container_name="your-container"
)

# List blobs
blobs = storage.list_blobs()

# Download and encode
blob_data = storage.download_blob("document.pdf")
encoded = storage.encode_to_base64(blob_data)
```

## Load Testing

### Metrics Collected

- **Latency**: Request/response time per document
- **Throughput**: Documents processed per second
- **Error Rates**: Success vs. failure rates
- **Token Usage**: Input and output tokens
- **Cost Estimates**: Based on token usage
- **Concurrency**: Parallel request handling

### Sample Output

**CSV Format** (`load_test_YYYYMMDD_HHMMSS.csv`):
```csv
timestamp,document_name,latency_ms,tokens_input,tokens_output,success,error_message
2025-10-20 10:30:15,receipt_001.png,1234,150,50,True,
2025-10-20 10:30:16,receipt_002.png,1156,145,48,True,
```

**JSON Summary** (`load_test_summary_YYYYMMDD_HHMMSS.json`):
```json
{
  "total_requests": 100,
  "successful": 98,
  "failed": 2,
  "avg_latency_ms": 1195,
  "p95_latency_ms": 1850,
  "throughput_per_sec": 4.2,
  "total_tokens": 19500,
  "estimated_cost_usd": 0.39
}
```

## Supported File Types

### Images
- PNG (`.png`)
- JPEG (`.jpg`, `.jpeg`)
- Other formats supported by Mistral Document AI

### Documents
- PDF (`.pdf`)
- Multi-page PDFs with automatic chunking

## Output Format

### JSON Response Structure

```json
{
  "document_id": "receipt_001.png",
  "processed_at": "2025-10-20T10:30:15Z",
  "mistral_response": {
    "text": "Extracted text content...",
    "confidence": 0.98,
    "metadata": {
      "pages": 1,
      "language": "en"
    }
  },
  "performance": {
    "latency_ms": 1234,
    "tokens_input": 150,
    "tokens_output": 50
  }
}
```

## Configuration

### Storage Configuration

Modify in `storage_utils.py` or use environment variables:

```python
storage = StorageUtils(
    account_name=os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
    container_name=os.getenv("AZURE_STORAGE_CONTAINER_NAME")
)
```

### Mistral API Configuration

Configure in processing scripts:

```python
api_key = os.getenv("MISTRAL_API_KEY")
endpoint = "https://api.mistral.ai/v1/chat/completions"
model = "pixtral-12b-2409"  # or your preferred model
```

### Telemetry Configuration

Optional Application Insights integration:

```python
connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
```

## Troubleshooting

### Authentication Issues

**Problem**: `DefaultAzureCredential failed to retrieve a token`

**Solution**:
1. Ensure you're logged in: `az login`
2. Verify your account has the correct role assignment
3. Check environment variables are set correctly

### Storage Access Errors

**Problem**: `This request is not authorized to perform this operation`

**Solution**:
1. Verify Storage Blob Data Reader role is assigned
2. Check storage account name and container name
3. Ensure firewall rules allow your IP (if configured)

### API Rate Limiting

**Problem**: `429 Too Many Requests`

**Solution**:
1. Implement rate limiting in your code
2. Use exponential backoff for retries
3. Contact Mistral AI to increase quota limits

### Large PDF Processing

**Problem**: Files too large for single API call

**Solution**:
- Use `pdfs_ocr_raw.py` which supports automatic chunking
- Adjust chunk size in configuration
- Process pages individually if needed

## Best Practices

1. **Security**: Never commit API keys or credentials to version control
2. **Cost Management**: Monitor token usage and set budget alerts
3. **Error Handling**: Implement comprehensive retry logic
4. **Logging**: Enable detailed logging for production deployments
5. **Testing**: Run load tests before production to establish baselines
6. **Monitoring**: Use Application Insights for production observability

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
- Create an issue in the GitHub repository
- Contact the maintainers
- Check Azure and Mistral AI documentation

## Acknowledgments

- Mistral AI for Document AI capabilities
- Microsoft Azure for cloud infrastructure
- NIQ for project sponsorship

---

**Last Updated**: October 20, 2025
