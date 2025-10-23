# LLM-Powered Analysis Report Feature

## Summary

A new component has been added to both receipt analysis workflows that automatically generates a comprehensive markdown analysis report using Azure OpenAI's GPT-4o model after processing all receipts.

## What Was Added

### 1. New Function: `generate_run_analysis_report()`

**Location**: `scripts/agents/receipt_analysis_workflow.py`

**Purpose**: Generates an intelligent analysis report summarizing the entire workflow run.

**Functionality**:
- Collects all receipt data and aggregation contexts
- Constructs a comprehensive analysis prompt
- Calls Azure OpenAI GPT-4o for analysis
- Saves report as `RUN_ANALYSIS_REPORT.md`

**Parameters**:
```python
async def generate_run_analysis_report(
    run_output_dir: Path,      # Directory for this run
    results_summary: dict,     # Run statistics
    logger: logging.Logger     # Logger instance
) -> None
```

### 2. Integration Points

**Modified Files**:
1. `scripts/agents/receipt_analysis_workflow.py`
   - Added `generate_run_analysis_report()` function (lines ~1020-1165)
   - Integrated into `main()` workflow (called after processing completes)

2. `scripts/agents/receipt_analysis_all_agents.py`
   - Imported `generate_run_analysis_report` from main workflow
   - Integrated into `main()` workflow (called after processing completes)

### 3. Documentation

**New Files**:
1. `documentation/RUN_ANALYSIS_REPORT.md` - Comprehensive documentation of the feature
2. `scripts/agents/README_AGENT_WORKFLOWS.md` - Complete agent workflow guide including analysis report

## How It Works

### Step-by-Step Process

1. **Workflow completes** processing all receipts
2. **Data collection**:
   - Loads all final receipt JSONs
   - Loads all aggregation context files
   - Includes workflow summary (timing, success rates)
3. **LLM prompt construction**:
   - Workflow metadata
   - Sample receipts (first 5 if > 5 total)
   - Sample aggregation contexts (first 3 if > 3 total)
   - Structured analysis requirements
4. **Azure OpenAI call**:
   - Model: GPT-4o
   - Temperature: 0.3 (consistent analysis)
   - Max tokens: 4000
5. **Report generation**:
   - Saves as `RUN_ANALYSIS_REPORT.md`
   - Includes timestamp and run ID
   - Formatted markdown with sections

### Report Contents

The LLM generates analysis covering:

1. **Executive Summary** - High-level overview
2. **Processing Performance** - Timing and throughput
3. **Data Quality Assessment** - Field completeness and confidence
4. **Multi-Agent Performance** - Agent usage and attribution patterns
5. **Merchant and Transaction Patterns** - Business insights
6. **Issues and Recommendations** - Specific improvement suggestions
7. **Detailed Statistics** - Comprehensive metrics

## Example Output

### Directory Structure

```
data/workflow_runs/all_agents_20251023_143000/
├── receipts/
├── intermediary_outputs/
├── aggregation_context/
├── workflow_summary.json
├── workflow.log
└── RUN_ANALYSIS_REPORT.md  ← NEW FILE
```

### Sample Report Excerpt

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
...

## Issues and Recommendations

### Recommendations
1. Implement image quality preprocessing for blurry receipts
2. Add validation rules for date format consistency
3. Consider currency normalization post-processing
...
```

## Configuration

Uses existing Azure OpenAI configuration:

```bash
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_KEY=your-api-key
```

No additional configuration required.

## Benefits

### For Developers
- **Automated Quality Checks**: Immediate feedback on extraction quality
- **Pattern Detection**: Identifies systematic issues automatically
- **Performance Monitoring**: Track metrics across runs
- **Debugging Aid**: Highlights problematic receipts

### For Business Users
- **Actionable Insights**: Specific recommendations for improvement
- **Business Intelligence**: Merchant and transaction patterns
- **Quality Assurance**: Confidence in automated processing
- **Audit Trail**: Complete documentation of each run

### For Operations
- **No Manual Analysis**: Fully automated
- **Consistent Format**: Same structure every run
- **Easy to Compare**: Compare reports across runs
- **Shareable**: Markdown format readable anywhere

## Usage

### Automatic Generation

The report is generated automatically at the end of each workflow run:

```bash
# Intelligent routing workflow
python run_workflow.py

# All-agents workflow
python run_workflow.py --all-agents
```

### Viewing the Report

```bash
# In VS Code (formatted view)
code data/workflow_runs/{run_id}/RUN_ANALYSIS_REPORT.md

# In terminal
cat data/workflow_runs/{run_id}/RUN_ANALYSIS_REPORT.md

# In browser (with markdown viewer)
# Or any markdown viewer application
```

## Error Handling

### Graceful Failures

If report generation fails:
- Warning is logged
- Console message displays error
- Workflow continues (doesn't block completion)
- Other outputs are still available

### Common Issues

1. **Azure OpenAI not configured**
   - Check `.env` file
   - Verify endpoint, deployment, and API key

2. **Insufficient API quota**
   - Check Azure OpenAI consumption
   - Increase quota or wait for reset

3. **No receipts processed**
   - Report only generates if at least one receipt succeeded
   - Check workflow logs for processing errors

## Implementation Details

### Code Changes

**Lines added**: ~145 lines
**Files modified**: 2 (receipt_analysis_workflow.py, receipt_analysis_all_agents.py)
**Files created**: 2 (documentation files)

### Dependencies

No new dependencies required. Uses existing:
- `openai` - Azure OpenAI client (already in requirements.txt)
- `json` - Standard library
- `pathlib` - Standard library

### Performance Impact

- **Time**: Adds ~5-15 seconds per run (depends on batch size)
- **Cost**: 1 additional GPT-4o API call per run (~500-3000 tokens)
- **Memory**: Minimal (samples data if > 5 receipts)

## Future Enhancements

Potential improvements:
- [ ] Comparative analysis across runs
- [ ] Trend detection over time
- [ ] Custom analysis templates
- [ ] HTML report format option
- [ ] Email report delivery
- [ ] Dashboard integration
- [ ] Automated alerting

## Testing

### Test Scenarios

1. **Happy Path**: 3 receipts, all successful
   - ✅ Report generated with all sections
   
2. **Mixed Results**: Some failures
   - ✅ Report analyzes both successes and failures
   
3. **Large Batch**: 50+ receipts
   - ✅ Report uses sampling (first 5 receipts)
   
4. **No Azure OpenAI**: Config missing
   - ✅ Graceful skip with warning message

### Validation

Run a test workflow to validate:

```bash
cd scripts/agents
TEST_MODE=true python run_workflow.py --all-agents
```

Check for `RUN_ANALYSIS_REPORT.md` in the output directory.

## Rollback

To disable the feature:

1. Comment out the call in `main()`:
   ```python
   # await generate_run_analysis_report(_run_output_dir, results_summary, logger)
   ```

2. Or set environment variable:
   ```bash
   ENABLE_ANALYSIS_REPORT=false
   ```
   (Would need to add this check to the code)

## Related Documentation

- [RUN_ANALYSIS_REPORT.md](RUN_ANALYSIS_REPORT.md) - Feature documentation
- [README_AGENT_WORKFLOWS.md](../scripts/agents/README_AGENT_WORKFLOWS.md) - Complete workflow guide
- [OUTPUT_STRUCTURE.md](OUTPUT_STRUCTURE.md) - Output directory structure (if exists)
