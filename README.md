# AIuthor — Premium Agentic Book Writer

AIuthor is a production-ready, multi-agent AI system designed to transform a user brief (topic, reader profile, target length, tonality preset, and genre) into a **publication-ready book** complete with full front matter, body chapters with narrative callbacks, and back matter. 

It is designed to showcase advanced capabilities in **orchestration, grounding, memory, and voice**.

---

## 🚀 One-Command Quick Start

To install dependencies, compile the React frontend, and start the FastAPI web dashboard, run the root-level startup script:

1. **Verify Prerequisites**: Ensure you have **Python 3.10+**, **Poetry**, and **Node.js (with npm)** installed.
2. **Configure API Keys (Optional)**: If you would like to run the agents with live LLMs, create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY="your-gemini-api-key"
   OPENAI_API_KEY="your-openai-api-key"
   ```
   *Note: If no keys are provided, the system automatically runs in **Mock Mode**, generating structured mocks to demonstrate flow.*
3. **Execute Startup**:
   ```bash
   chmod +x run.sh
   ./run.sh
   ```
4. **Open Dashboard**: Navigate to **`http://localhost:8000`** in your browser.

---

## 🧪 CLI Verification Suite (All Test Cases)

To execute all four assessment test cases programmatically and run quality checks:

1. **Navigate to the Backend**:
   ```bash
   cd backend
   ```
2. **Execute Test Runner**:
   ```bash
   poetry run python scripts/generate_test_books.py
   ```
3. **Verify Artifacts**:
   - PDF + Word books are saved in `backend/output_books/`.
   - Quality evaluation reports and trace logs are saved in `backend/traces/`.

---

## 📂 Deliverables Checklist

All deliverables requested in the technical assessment have been generated and can be found at the following links:

1. **Prompts Dossier**: [docs/prompts_dossier.md](file:///home/manoj-vala/projects/TheGatewayCorp-Assignment/docs/prompts_dossier.md) — Comprehensive guide to every prompt, input, output, failure mode, and justification.
2. **Architecture Doc**: [docs/architecture.md](file:///home/manoj-vala/projects/TheGatewayCorp-Assignment/docs/architecture.md) — One-page topology, memory structure, and sequence flows.
3. **Memory Schema**: [docs/memory_schema.md](file:///home/manoj-vala/projects/TheGatewayCorp-Assignment/docs/memory_schema.md) — JSON schemas and example records for Fact Registry, Concept Bible, etc.
4. **Design Decisions Log**: [docs/design_decisions.md](file:///home/manoj-vala/projects/TheGatewayCorp-Assignment/docs/design_decisions.md) — Documentation of the 10 most consequential architectural decisions.
5. **Quality Evals Report**: [docs/evals_report.md](file:///home/manoj-vala/projects/TheGatewayCorp-Assignment/docs/evals_report.md) — Rubrics, runs, scores, and failure analyses.
6. **Sample Books (PDF + DOCX)**: Located in `backend/output_books/` after running the CLI test suite.

---

## 🛠️ System Architecture & Components

AIuthor operates as an event-driven **orchestrator-worker DAG pipeline** managing the state of a book run:

```
[User Brief] ──> Planner Agent ──> Book Outline ──> Chapter Loops
                                                         │
   ┌─────────────────────────────────────────────────────┘
   ▼
1. Researcher Agent  ──> Hybrid RAG & Web Search Report
2. Writer Agent      ──> Raw chapter draft integrating callbacks
3. Humanizer Agent   ──> DPO opening hook loop & AI tell elimination
4. Editor Agent      ──> Polish grammar and transitional flow
5. Fact-Checker      ──> Citation-or-soften grounding verification
6. Memory Keeper     ──> Update Fact, Concept, and Callback registers
   ▲
   └─────────────────── Loop next chapter
```

### Key Technical Achievements:
- **Custom PDF Canvas Templates**: Implemented two-pass relative page numbering, drawing lowercase Roman numerals on front matter and reset Arabic numerals (1, 2, 3...) starting from the Introduction.
- **Self-Healing Downstream Repair (Test Case D)**: Restructures outlines, shifts subsequent chapter numbering, writes the new chapter, and runs a transition-repair agent over all downstream chapters to update chapter references.
- **Preference-Based Refinement (DPO/RLHF)**: Humanizer generates twoCompeting openings (Option A vs B) and uses a critic scorer prompt (Reward-Model-Lite) to choose the best hook based on tonality rubrics.
- **BM25 + Vector Hybrid Search**: Combines semantic embeddings with custom term-frequency retrieval to ground factual claims.
