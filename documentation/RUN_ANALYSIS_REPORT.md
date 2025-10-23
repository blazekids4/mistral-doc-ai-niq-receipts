# LLM-Powered Run Analysis Report

## Overview

The workflow automatically generates a comprehensive analysis report for each run using Azure OpenAI's GPT-4o model. This report provides insights, patterns, and recommendations based on the entire batch of processed receipts.

## Report Location

- **File**: `RUN_ANALYSIS_REPORT.md`
- **Directory**: `data/workflow_runs/{run_id}/`
- **Generated**: Automatically after all receipts are processed

## Report Sections

### 1. Executive Summary
High-level overview of the workflow execution, including:
- Total receipts processed
- Success/failure rates
- Overall performance metrics
- Key findings

### 2. Processing Performance
Detailed analysis of timing and throughput:
- Total duration
- Average time per receipt
- Throughput rate (receipts/minute)
- Performance bottlenecks or outliers

### 3. Data Quality Assessment
Evaluation of extracted data quality:
- **Completeness**: Which fields were successfully extracted across all receipts
- **Confidence Scores**: Distribution and patterns
- **Missing Data**: Common gaps or incomplete extractions
- **Field-level Statistics**: Success rates per field type

### 4. Multi-Agent Performance
Analysis of the multi-agent orchestration:
- **Agent Usage Frequency**: Which agents were used most often
- **Source Attribution**: Which agent contributed most fields in final outputs
- **Agent Scoring Patterns**: How agents were ranked during aggregation
- **Quality Assessment Routing**: Distribution of clear/blurry/uncertain classifications

### 5. Merchant and Transaction Patterns
Business insights from the receipt data:
- **Unique Merchants**: List and frequency
- **Transaction Amounts**: Range, average, distribution
- **Common Items**: Most frequently appearing products/services
- **Currency Usage**: If multiple currencies detected
- **Transaction Timing**: Date/time patterns if available

### 6. Issues and Recommendations
Actionable insights for improvement:
- **Failed Receipts**: Which receipts failed and why
- **Low Confidence Results**: Receipts with poor extraction quality
- **Data Quality Concerns**: Systematic issues or patterns
- **Recommended Improvements**: Specific suggestions for:
  - Image quality preprocessing
  - Agent configuration adjustments
  - Workflow optimizations
  - Additional validation steps

### 7. Detailed Statistics
Comprehensive metrics:
- **Field Extraction Rates**: Per-field success percentages
- **Item Count Distribution**: Histogram of items per receipt
- **Confidence Score Distribution**: Statistical summary
- **Processing Time Distribution**: Outliers and patterns
- **Source Attribution Matrix**: Cross-tab of agents vs fields

## Example Report Structure

```markdown
# Workflow Run Analysis Report

**Generated:** 2025-10-23 14:30:00
**Run ID:** all_agents_20251023_143000

---

## Executive Summary

This workflow successfully processed 15 out of 15 receipts in 127.5 seconds...

## Processing Performance

- **Total Duration**: 127.5 seconds (2.13 minutes)
- **Average per Receipt**: 8.5 seconds
- **Throughput**: 7.1 receipts/minute
...

## Data Quality Assessment

Overall extraction quality was high with an average confidence score of 0.87...

### Field Completeness
| Field | Success Rate |
|-------|--------------|
| Merchant Name | 100% (15/15) |
| Transaction Date | 93% (14/15) |
| Total Amount | 100% (15/15) |
...

## Multi-Agent Performance

The all-agents mode was used for this run, with the following contribution pattern:
- **Document Intelligence**: Primary source for 8 receipts
- **Mistral**: Primary source for 5 receipts
- **Direct Extraction**: Primary source for 2 receipts
...

## Merchant and Transaction Patterns

15 receipts were processed from 12 unique merchants:
- Walmart: 3 receipts
- Starbucks: 2 receipts
- Target: 2 receipts
...

## Issues and Recommendations

### Low Confidence Results
- `receipt_sample_3.png`: Confidence 0.62 - blurry image, consider preprocessing

### Recommendations
1. Implement image quality preprocessing for blurry receipts
2. Add validation rules for date formats
3. Consider adding a post-processing step for currency normalization
...

## Detailed Statistics

### Field Extraction Success Rates
- merchant_name: 100%
- transaction_date: 93%
- transaction_time: 67%
- total_amount: 100%
- currency: 87%
- items (1+): 93%

### Item Count Distribution
- 1-5 items: 6 receipts
- 6-10 items: 5 receipts
- 11-20 items: 3 receipts
- 20+ items: 1 receipt
...
```

## How It Works

### Data Collection
1. Loads all processed receipt JSON files from `receipts/` directory
2. Loads all aggregation context files from `aggregation_context/` directory
3. Reads the workflow summary JSON with timing and status information

### LLM Analysis
1. Constructs a comprehensive analysis prompt with:
   - Workflow metadata (run ID, counts, timing)
   - Sample receipt data (first 5 receipts if more than 5 processed)
   - Sample aggregation contexts (first 3 contexts if more than 3)
2. Calls Azure OpenAI GPT-4o with temperature=0.3 for consistent analysis
3. Requests structured markdown output with all required sections

### Report Generation
1. Receives LLM-generated analysis
2. Adds header with run metadata
3. Saves as `RUN_ANALYSIS_REPORT.md` in the run directory

## Configuration

The analysis report uses the same Azure OpenAI configuration as the rest of the workflow:

```env
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_KEY=your-api-key
```

## Benefits

### 1. Automated Insights
- No manual analysis required
- Consistent evaluation framework
- Immediate feedback after each run

### 2. Quality Monitoring
- Track extraction quality over time
- Identify systematic issues
- Validate agent performance

### 3. Actionable Recommendations
- Specific improvement suggestions
- Pattern detection
- Optimization opportunities

### 4. Audit Trail
- Complete run documentation
- Historical analysis records
- Performance tracking

## Limitations

- **Token Limits**: Large batches (>50 receipts) may be summarized or sampled
- **Analysis Depth**: Depends on data quality and patterns in the batch
- **LLM Variability**: Different runs may emphasize different aspects

## Future Enhancements

Potential improvements:
- Comparative analysis across multiple runs
- Trend detection over time
- Automated alerting for anomalies
- Custom analysis templates for specific use cases
- Integration with monitoring dashboards
