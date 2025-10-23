# Receipt Analysis Agent Workflows

## Overview

The agent workflows provide intelligent, multi-agent receipt processing with automatic quality assessment, smart routing, and comprehensive output tracking. Each workflow run generates detailed outputs including individual agent results, aggregation decisions, and an **LLM-powered analysis report**.

## Workflows

### 1. Intelligent Routing Workflow (`receipt_analysis_workflow.py`)

**Purpose**: Assesses image quality and routes receipts to the optimal processing agent(s).

**How It Works**:
1. **Quality Assessment**: Azure OpenAI analyzes each receipt image
2. **Smart Routing**:
   - **Clear images** → Mistral Document AI (best for high-quality OCR)
   - **Blurry images** → Azure Document Intelligence (better for poor quality)
   - **Uncertain quality** → All 3 agents (consensus mode)
3. **Processing**: Selected agent(s) extract receipt data
4. **Aggregation**: Results are synthesized with field-level attribution
5. **Analysis Report**: LLM generates comprehensive run analysis

**Run Command**:
```bash
python run_workflow.py
```

### 2. All-Agents Workflow (`receipt_analysis_all_agents.py`)

**Purpose**: Processes every receipt with all three agents for maximum accuracy through consensus.

**How It Works**:
1. **Dispatch**: Each receipt is sent to all 3 agents simultaneously
2. **Parallel Processing**:
   - Azure Document Intelligence
   - Mistral Document AI
   - Azure OpenAI Vision (Direct Extraction)
3. **Aggregation**: Best fields from each agent are merged
4. **Analysis Report**: LLM generates comprehensive run analysis

**Run Command**:
```bash
python run_workflow.py --all-agents
```

## Output Structure

Each workflow run creates a timestamped directory with 5 output directories:

```
data/workflow_runs/{run_id}/
├── receipts/                           # Final aggregated results
│   ├── {receipt_name}.json            # Structured receipt data
│   └── {receipt_name}.md              # Human-readable summary
├── intermediary_outputs/               # Individual agent outputs
│   ├── {receipt_name}_document_intelligence.json
│   ├── {receipt_name}_mistral.json
│   └── {receipt_name}_direct_extraction.json
├── aggregation_context/                # Synthesis decision logs
│   └── {receipt_name}_aggregation.json
├── logs/                               # Workflow execution logs
│   └── workflow.log
├── workflow_summary.json               # Run statistics
└── RUN_ANALYSIS_REPORT.md             # 🆕 LLM-powered analysis
```

## 🆕 LLM-Powered Analysis Report

### What Is It?

After processing all receipts, the workflow automatically generates a comprehensive analysis report using Azure OpenAI's GPT-4o model. This report provides actionable insights, patterns, and recommendations for the entire batch.

### Report Sections

1. **Executive Summary**
   - High-level overview of the run
   - Success/failure rates
   - Key findings

2. **Processing Performance**
   - Timing metrics
   - Throughput analysis
   - Performance bottlenecks

3. **Data Quality Assessment**
   - Field completeness rates
   - Confidence score distributions
   - Common missing data patterns

4. **Multi-Agent Performance**
   - Agent usage frequency
   - Source attribution patterns
   - Agent scoring and selection analysis

5. **Merchant and Transaction Patterns**
   - Unique merchants identified
   - Transaction amount ranges
   - Common item types
   - Currency usage

6. **Issues and Recommendations**
   - Failed receipts analysis
   - Low confidence results
   - Data quality concerns
   - Specific improvement suggestions

7. **Detailed Statistics**
   - Per-field extraction rates
   - Item count distributions
   - Processing time distributions
   - Source attribution matrix

### Example Report Output

```markdown
# Workflow Run Analysis Report

**Generated:** 2025-10-23 14:30:00
**Run ID:** all_agents_20251023_143000

---

## Executive Summary

This workflow successfully processed 15 out of 15 receipts in 127.5 seconds 
(average 8.5s per receipt). Overall extraction quality was excellent with an 
average confidence score of 0.87 and 95% field completeness.

## Processing Performance

- **Total Duration**: 127.5 seconds (2.13 minutes)
- **Average per Receipt**: 8.5 seconds
- **Throughput**: 7.1 receipts/minute
- **Success Rate**: 100% (15/15)

The all-agents mode demonstrated consistent performance across all receipts...

## Data Quality Assessment

### Field Completeness
| Field | Success Rate |
|-------|--------------|
| Merchant Name | 100% (15/15) |
| Transaction Date | 93% (14/15) |
| Total Amount | 100% (15/15) |
| Currency | 87% (13/15) |
| Items (1+) | 93% (14/15) |

One receipt (receipt_sample_3.png) was missing the transaction date...

## Multi-Agent Performance

**Primary Source Attribution:**
- Document Intelligence: 8 receipts (53%)
- Mistral: 5 receipts (33%)
- Direct Extraction: 2 receipts (13%)

Document Intelligence showed the highest completeness scores...

## Issues and Recommendations

### Low Confidence Results
1. `receipt_sample_3.png`: Confidence 0.62
   - Issue: Blurry image, poor contrast
   - Recommendation: Implement image preprocessing

### Recommendations
1. Add image quality preprocessing for blurry receipts
2. Implement validation rules for date format consistency
3. Consider currency normalization post-processing
4. Add item-level confidence scoring
```

### How to Access

The report is automatically generated and saved as:
```
data/workflow_runs/{run_id}/RUN_ANALYSIS_REPORT.md
```

Open it with any markdown viewer or directly in VS Code for formatted viewing.

### Benefits

- **Automated Insights**: No manual analysis required
- **Quality Monitoring**: Track extraction quality trends
- **Actionable Recommendations**: Specific improvement suggestions
- **Audit Trail**: Complete documentation of each run
- **Pattern Detection**: Identify systematic issues

## Processing Agents

### 1. Azure Document Intelligence
- **Strengths**: Excellent for structured receipts, handles poor quality well
- **API**: Azure Cognitive Services - Prebuilt Receipt Model
- **Best For**: Blurry images, standard receipt formats

### 2. Mistral Document AI
- **Strengths**: Fast, accurate OCR for clear images
- **API**: Mistral AI Foundry endpoint
- **Best For**: High-quality images, varied receipt layouts

### 3. Azure OpenAI Vision (Direct Extraction)
- **Strengths**: Understanding context, handling unusual formats
- **API**: GPT-4o with vision capabilities
- **Best For**: Uncertain quality, complex layouts, fallback processing

## Aggregation Logic

When multiple agents process the same receipt, results are aggregated using:

### Scoring Algorithm

```
Score = (Completeness × 0.7) + (Confidence × 0.3) + Source Priority
```

- **Completeness**: Percentage of fields successfully extracted
- **Confidence**: Agent-reported confidence score (0.0-1.0)
- **Source Priority**: Tiebreaker (Document Intelligence > Mistral > Direct)

### Field Selection

1. Start with the highest-scoring agent's results as the base
2. Fill in missing fields from other agents
3. Track which agent provided each field (source attribution)

### Item Deduplication

- Merge item lists from all agents
- Remove duplicates based on description similarity
- Track which agent contributed each item

## Configuration

### Environment Variables

Required in `.env` file:

```bash
# Azure OpenAI (Quality Assessment + Direct Extraction + Analysis Report)
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_KEY=your-api-key

# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=your-key

# Mistral Document AI
MISTRAL_API_KEY=your-mistral-key
AZURE_AI_PROJECT_CONNECTION_STRING=your-connection-string

# Azure Storage
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account
AZURE_STORAGE_CONTAINER_NAME=your-container

# Optional: Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=your-connection-string

# Mode
TEST_MODE=true  # Process first 3 receipts only (set to false for all)
```

### Test Mode

By default, workflows run in TEST mode (processes first 3 receipts):
```bash
TEST_MODE=true python run_workflow.py
```

For production (all receipts):
```bash
TEST_MODE=false python run_workflow.py --all-agents
```

## Usage Examples

### Basic Intelligent Routing

```bash
cd scripts/agents
python run_workflow.py
```

**Output**: Each receipt is quality-assessed and routed to optimal agent(s).

### All-Agents Consensus Mode

```bash
python run_workflow.py --all-agents
```

**Output**: Maximum accuracy through 3-agent consensus.

### View Results

```bash
# View final aggregated results
cat data/workflow_runs/all_agents_20251023_143000/receipts/receipt_name.json

# View human-readable summary
cat data/workflow_runs/all_agents_20251023_143000/receipts/receipt_name.md

# View agent-specific outputs
cat data/workflow_runs/all_agents_20251023_143000/intermediary_outputs/receipt_name_mistral.json

# View aggregation decisions
cat data/workflow_runs/all_agents_20251023_143000/aggregation_context/receipt_name_aggregation.json

# 🆕 View LLM analysis report
cat data/workflow_runs/all_agents_20251023_143000/RUN_ANALYSIS_REPORT.md
```

## Understanding Output Files

### Final Receipt JSON (`receipts/*.json`)

```json
{
  "merchant_name": "Walmart",
  "transaction_date": "2024-10-15",
  "transaction_time": "14:32:00",
  "total_amount": 45.67,
  "currency": "USD",
  "items": [
    {
      "description": "Bananas",
      "price": 2.99,
      "quantity": "1"
    }
  ],
  "metadata": {
    "processing_timestamp": "2025-10-23T14:30:15",
    "confidence_score": 0.92,
    "completeness_score": 0.95,
    "best_source": "document_intelligence",
    "field_sources": {
      "merchant_name": "document_intelligence",
      "transaction_date": "mistral",
      "total_amount": "document_intelligence"
    },
    "item_sources": [
      {"description": "Bananas", "source": "mistral"}
    ]
  },
  "sources_used": ["document_intelligence", "mistral", "direct_extraction"],
  "blob_name": "receipts/walmart_receipt.png"
}
```

### Aggregation Context (`aggregation_context/*_aggregation.json`)

Shows complete decision-making process:
- All agent scores and extracted fields
- Selection logic and reasoning
- Field and item attribution details
- Complete synthesis prompt context

### 🆕 Analysis Report (`RUN_ANALYSIS_REPORT.md`)

Comprehensive LLM-generated insights covering:
- Executive summary of the entire run
- Performance metrics and bottlenecks
- Data quality patterns and issues
- Agent performance comparison
- Business insights (merchants, amounts, items)
- Specific recommendations for improvement

## Troubleshooting

### No Analysis Report Generated

**Symptom**: Workflow completes but no `RUN_ANALYSIS_REPORT.md` file.

**Possible Causes**:
- Azure OpenAI not configured (check `.env`)
- No receipts processed successfully
- Insufficient API quota

**Solution**:
```bash
# Verify Azure OpenAI configuration
echo $env:AZURE_OPENAI_ENDPOINT
echo $env:AZURE_OPENAI_DEPLOYMENT

# Check workflow logs
cat data/workflow_runs/{run_id}/workflow.log | grep "analysis"
```

### All Receipts Routed to "Uncertain"

**Symptom**: Every receipt uses all 3 agents even when images seem clear.

**This is normal**: The quality assessor is conservative. If genuinely uncertain, it's better to use all agents than risk poor extraction.

**To investigate**:
- Check quality assessment reasoning in logs
- Review image quality (resolution, contrast, blur)
- Adjust quality assessment prompt if needed

### Low Confidence Scores

**Symptom**: Analysis report shows many low confidence results.

**Possible Causes**:
- Poor image quality (blur, low resolution)
- Unusual receipt formats
- Missing critical information on receipts

**Solution**:
- Implement image preprocessing
- Add receipt format training data
- Use all-agents mode for maximum accuracy

### Missing Fields

**Symptom**: Some receipts missing certain fields (e.g., transaction_time).

**This is normal**: Not all receipts contain all fields. Check:
1. Analysis report "Data Quality Assessment" section
2. Aggregation context to see if any agent extracted the field
3. Original receipt image to confirm field presence

## Performance Optimization

### Speed vs Accuracy Trade-offs

| Mode | Speed | Accuracy | Cost | Use Case |
|------|-------|----------|------|----------|
| Intelligent Routing | Fast | Good | Low | Production, clear images |
| All-Agents | Slow | Best | High | Critical data, uncertain quality |
| Single Agent | Fastest | Variable | Lowest | Testing, known formats |

### Batch Processing Tips

1. **Test Mode First**: Always run with `TEST_MODE=true` initially
2. **Monitor Costs**: Check Azure consumption after each run
3. **Tune Concurrency**: Adjust based on API rate limits
4. **Review Analysis Reports**: Use insights to optimize future runs

## Integration

### Import as Module

```python
from receipt_analysis_workflow import (
    document_intelligence_processor,
    mistral_processor,
    direct_extraction_processor,
    aggregate_results,
    generate_run_analysis_report
)

# Use processors in custom workflows
```

### Custom Aggregation

```python
# Implement custom scoring logic
def custom_scoring(result):
    return (result.completeness * 0.5) + (result.custom_metric * 0.5)
```

## Future Enhancements

Potential improvements:
- [ ] Comparative analysis across multiple runs
- [ ] Trend detection over time
- [ ] Automated alerting for anomalies
- [ ] Custom analysis templates
- [ ] Integration with monitoring dashboards
- [ ] Real-time streaming analysis
- [ ] Multi-language support
- [ ] Custom agent training

## Support

For issues or questions:
1. Check workflow logs: `data/workflow_runs/{run_id}/workflow.log`
2. Review analysis report for insights
3. Verify all environment variables are set
4. Ensure Azure authentication is working (`az login`)

## Related Documentation

- [Main Project README](../../README.md)
- [Analysis Report Documentation](../../documentation/RUN_ANALYSIS_REPORT.md)
- [Workflow Utils](receipt_workflow_utils.py)
- [Storage Utils](storage_utils.py)
