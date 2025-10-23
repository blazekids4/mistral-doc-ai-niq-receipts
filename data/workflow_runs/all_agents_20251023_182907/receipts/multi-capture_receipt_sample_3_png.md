# Receipt Summary: multi-capture/receipt_sample_3.png

**Merchant:** GLOBUS _(source: document_intelligence)_

**Date:** 2024-08-16T12:31:08+02:00 _(source: document_intelligence)_

**Time:** 12:31 _(source: document_intelligence)_

**Total:** 40.92 EUR _(source: direct_extraction)_

## Items

- Item 1 (7% VAT): 14.95 (qty: 1) _[direct_extraction]_
- Item 2 (19% VAT): 25.97 (qty: 1) _[direct_extraction]_

## Processing Details

**Sources used:** document_intelligence, mistral, direct_extraction, document_intelligence, mistral, direct_extraction, document_intelligence, mistral, direct_extraction

**Best source:** document_intelligence

**Confidence score:** 0.97

**Completeness score:** 1.67

## Field Attribution

| Field | Source |
|-------|--------|
| merchant_name | document_intelligence |
| transaction_date | document_intelligence |
| transaction_time | document_intelligence |
| total_amount | direct_extraction |
| currency | direct_extraction |

## Source Scores

- **document_intelligence**: 1.49 (completeness: 1.67, confidence: 0.97)
- **document_intelligence**: 1.49 (completeness: 1.67, confidence: 0.97)
- **document_intelligence**: 1.49 (completeness: 1.67, confidence: 0.97)
- **direct_extraction**: 1.46 (completeness: 1.67, confidence: 0.95)
- **direct_extraction**: 1.46 (completeness: 1.67, confidence: 0.95)
- **direct_extraction**: 1.46 (completeness: 1.67, confidence: 0.95)
- **mistral**: 0.28 (completeness: 0.00, confidence: 0.85)
- **mistral**: 0.28 (completeness: 0.00, confidence: 0.85)
- **mistral**: 0.28 (completeness: 0.00, confidence: 0.85)
