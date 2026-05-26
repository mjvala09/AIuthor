# AIuthor — Quality Evaluations Report

This report outlines the scoring rubrics, automated evaluation checks, and verification results for the four test cases.

---

## 1. Evaluation Rubric

AIuthor evaluates each generated book against five distinct quality dimensions (matching the company's evaluation expectations):

| Dimension | Weight | 5/5 (1.0) Looks Like |
| :--- | :--- | :--- |
| **Structural Completeness** | 20% | All front matter, body chapters, and back matter are present and fully drafted. |
| **Tonality Fidelity** | 30% | The chosen preset (Conversational, Academic, Storyteller, etc.) is consistent across all chapters and metadata. |
| **AI-Tell Detection** | 20% | Zero occurrences of cliché phrases (e.g. 'delve into', 'in today's...') and mechanical triads. |
| **Fact Coverage** | 15% | Essential RAG fact items are accurately represented and cited without hallucinations. |
| **Callback Recall** | 15% | Narrative callbacks are correctly logged and referenced downstream with high coherence. |

---

## 2. Metric Verification Formulae

### 1. Structural Completeness
Score is calculated as:
$$\text{Score} = \frac{N_{\text{complete\_chapters}}}{N_{\text{planned\_chapters}}}$$
Deductions apply if key front/back matter items (like copyright, TOC, or glossary) are missing.

### 2. Tonality Fidelity
Calculated via **LLM-as-Judge**:
The `TonalityJudge` evaluates chapter excerpts against stylistic guidelines (e.g. use of second-person in conversational tone, active voice, etc.) scoring from 0.0 to 1.0.

### 3. AI-Tell Detection
Calculated via Regex patterns scanning for forbidden tells:
$$\text{Score} = \max\left(0.0, 1.0 - (\text{occurrences} \times 0.05)\right)$$
This deducts 5% for every occurrence of expressions like "delve into" or "it is important to note".

### 4. Fact Coverage
Scans the final text for terms and figures established in the Fact Registry and Concept Bible:
$$\text{Score} = \frac{\text{Concepts Present}}{\text{Total Registered Concepts}}$$

### 5. Callback Recall
Checks if callbacks targeted for specific downstream chapters are present and contextually relevant (giving 1.0 for perfect matches and 0.5 for partial matches).

---

## 3. Test Cases Execution Summary

The CLI test suite (`backend/scripts/generate_test_books.py`) verifies the system using four test cases:

### Test Case A: Personal Finance Guide
- **Description**: 10-chapter beginner's guide to personal finance, Conversational tone.
- **Verification**: Generates 10 full chapters and compiles them. Page numbering starts at 1 on the introduction. Evaluates RAG search grounding.
- **Expected Score**: $>90\%$ (Perfect structure, zero tells, conversational hooks).

### Test Case B: Novella
- **Description**: 5-chapter novella, Storyteller tone, carrying two characters (Leo and Maya) throughout.
- **Verification**: Verifies that character traits from Chapter 1 (Leo's silver flask, old canvas hat) are recalled and matched in later chapters (e.g. Chapter 3 callback index).
- **Expected Score**: $>90\%$ (Rich narrative flow, character consistency).

### Test Case C: Tonal Variations
- **Description**: Re-running Chapter 3 in Academic, Motivational, and Witty presets.
- **Verification**: Saves variations under `output_books/`. Academic varies to third-person with definitions; Motivational uses short, punchy calls-to-action; Witty uses humorous metaphors.

### Test Case D: Downstream Repair
- **Description**: Inserting a chapter between Chapter 4 and 5 of Test Case A, verifying self-healing.
- **Verification**: Checks if the subsequent chapters automatically shift (Chapter 5 becomes Chapter 6), repairs transition references, and regenerates the TOC and Glossary.
