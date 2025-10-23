# Workflow Run Analysis Report

**Generated:** 2025-10-23 18:33:43

**Run ID:** all_agents_20251023_182907

---

# Automated Receipt Processing Workflow Analysis Report

## **Executive Summary**

The automated receipt processing workflow (Run ID: `all_agents_20251023_182907`) successfully processed **4 receipts** with a 100% success rate and no failures. The workflow demonstrated consistent performance, achieving an average processing time of **64.33 seconds per receipt**. The data extraction quality was high, with a mean confidence score of **0.95** across receipts and a completeness score of **2.6**. The `direct_extraction` agent was identified as the most reliable and accurate source for field and item extraction.

---

## **1. Processing Performance**

### **Workflow Execution Metrics**
| Metric                  | Value       |
|-------------------------|-------------|
| **Total Receipts**      | 4           |
| **Successful Receipts** | 4           |
| **Failed Receipts**     | 0           |
| **Total Duration**      | 257.33 sec  |
| **Average Time per Receipt** | 64.33 sec |

### **Performance Insights**
- **Success Rate**: The workflow achieved a **100% success rate**, indicating robust functionality and no critical errors during execution.
- **Processing Time**: The average processing time per receipt was **64.33 seconds**, which is efficient given the complexity of multi-agent evaluation and field extraction.

---

## **2. Data Quality Assessment**

### **Field Completeness**
| Field Name          | Completeness Rate | Common Issues/Patterns                  |
|---------------------|-------------------|-----------------------------------------|
| **Merchant Name**   | 100%              | No issues detected                      |
| **Transaction Date**| 100%              | Consistently extracted by `direct_extraction` |
| **Transaction Time**| 75%               | Missing or null values in some cases    |
| **Total Amount**    | 100%              | No issues detected                      |
| **Currency**        | 100%              | No issues detected                      |

### **Confidence Score Distribution**
- **Mean Confidence Score**: **0.95**
- **Confidence Range**: 0.85 (lowest) to 0.994 (highest)
- **Observations**: `direct_extraction` consistently provided the highest confidence scores, while `mistral` had the lowest scores due to incomplete field extraction.

### **Common Missing Fields**
- **Transaction Time**: Missing in some cases, attributed to `document_intelligence` and `mistral` agents.
- **Currency and Total Amount**: Occasionally missing when `mistral` was the primary source.

---

## **3. Multi-Agent Performance**

### **Agent Usage Frequency**
| Agent Name             | Usage Count |
|------------------------|-------------|
| **direct_extraction**  | 6           |
| **document_intelligence** | 3         |
| **mistral**            | 3           |

### **Source Attribution Patterns**
- **Field Attribution**:
  - `direct_extraction` was the primary source for most fields, including **merchant name**, **transaction date**, **total amount**, and **currency**.
  - `document_intelligence` contributed to **transaction time** extraction but had lower completeness and confidence scores.
  - `mistral` provided minimal field extraction, with consistently low scores.

- **Item Attribution**:
  - All item descriptions were extracted by `direct_extraction`, demonstrating its reliability for item-level data.

### **Agent Scoring and Selection**
| Agent Name             | Average Final Score | Primary Contribution |
|------------------------|---------------------|-----------------------|
| **direct_extraction**  | 2.115               | Most accurate and complete field extraction |
| **document_intelligence** | 1.495             | Secondary source for transaction time |
| **mistral**            | 0.275               | Minimal contribution, low completeness |

---

## **4. Merchant and Transaction Patterns**

### **Unique Merchants Identified**
- **Carrefour**
- **Globus**

### **Transaction Amount Ranges**
| Range (€)   | Count |
|-------------|-------|
| **< 20**    | 1     |
| **20-50**   | 1     |
| **50+**     | 0     |

### **Common Item Types**
- **Carrefour**:
  - Bakery items (e.g., baguettes, Pain aux raisins)
  - Groceries (e.g., Fusilli, Piment Vert)
  - Snacks (e.g., Mangues Caramelise, Noix Cajou Mi)
- **Globus**:
  - Household items (e.g., Microfaser Colors, Ersatzkopf)
  - Food items (e.g., Fruchtquark, Erdnusslocken)

---

## **5. Issues and Recommendations**

### **Identified Issues**
1. **Transaction Time Missing**:
   - `document_intelligence` and `mistral` agents failed to extract transaction time consistently, leading to incomplete data for some receipts.
2. **Low Scores from `mistral`**:
   - `mistral` provided low confidence and completeness scores, with minimal field extraction.

### **Recommendations**
1. **Improve Transaction Time Extraction**:
   - Enhance the `document_intelligence` agent's ability to accurately extract transaction time.
   - Consider training `direct_extraction` to handle transaction time extraction more effectively.
2. **Optimize Agent Scoring and Selection**:
   - Reassess the role of `mistral` in the workflow due to its low contribution and scores.
   - Implement stricter thresholds for agent selection to prioritize higher-performing sources.
3. **Expand Merchant Database**:
   - Ensure the merchant database includes variations in merchant names (e.g., "Carrefour" vs. "Carrefour Market") to improve matching accuracy.
4. **Enhance Error Logging**:
   - Introduce more detailed error tracking for missing fields to identify patterns and improve agent training.

---

## **6. Detailed Statistics**

### **Field Extraction Success Rates**
| Field Name          | Success Rate |
|---------------------|--------------|
| **Merchant Name**   | 100%         |
| **Transaction Date**| 100%         |
| **Transaction Time**| 75%          |
| **Total Amount**    | 100%         |
| **Currency**        | 100%         |

### **Item Count Distribution**
| Number of Items | Count |
|-----------------|-------|
| **< 10**        | 0     |
| **10-15**       | 1     |
| **15+**         | 1     |

### **Currency Usage**
| Currency | Count |
|----------|-------|
| **EUR**  | 2     |

---

## **Conclusion**

The automated receipt processing workflow demonstrated high accuracy and efficiency, successfully processing all receipts with no failures. `direct_extraction` was the most reliable agent, contributing the majority of field and item extractions with high confidence and completeness scores. However, issues with missing transaction times and low-performing agents like `mistral` highlight areas for improvement. Implementing targeted enhancements to agent training, source selection logic, and error tracking will further optimize the workflow and ensure consistent data quality.