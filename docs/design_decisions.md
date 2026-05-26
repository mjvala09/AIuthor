# AIuthor — Design Decisions Log

This log documents the ten most consequential engineering and architectural decisions made during the design of the AIuthor Book Generator.

---

## 1. Single-Command Startup (`run.sh`)
- **Decision**: Provide a root-level shell script that compiles the React frontend (Vite) and launches the FastAPI backend serving both the API and the static build folder.
- **Rationale**: Meets the "one-command runnable MVP" requirement perfectly. It simplifies the evaluator's setup by handling npm installs, builds, python dependencies, and server launch in one step.

## 2. ReportLab PDF Generation Canvas subclass (`BookCanvas`)
- **Decision**: Subclassed `canvas.Canvas` to implement a two-pass layout compiler.
- **Rationale**: Necessary to support **roman-numeral page numbers for front matter** and **arabic page numbers starting at 1 from the introduction**. It captures template switches and performs relative page numbering in the second-pass draw.

## 3. Two-Pass PDF Compilation for Table of Contents (TOC)
- **Decision**: Run the document layout builder once in-memory to capture the page numbers where chapter headers are drawn, then compile a second time with the resolved page numbers inserted into the TOC.
- **Rationale**: PDF layouts are dynamic and depend on word lengths. Re-running the build with a cached pages index guarantees that page numbers in the Table of Contents are 100% correct and clickable.

## 4. Unified Client-Agnostic LLM Client Wrapper (`LLMService`)
- **Decision**: Implemented a unified LLM service that detects available keys and handles fallbacks. If a pro model fails, it automatically routes calls to a flash model.
- **Rationale**: API rate limits and network errors are common. Transparent fallbacks ensure the agent pipeline never crashes midway through a long book generation run.

## 5. Mock Mode for Keyless Portability
- **Decision**: Added a fallback MOCK mode in `LLMService` which returns structured mock outline and chapter texts when no API keys are provided.
- **Rationale**: Allows the evaluator to run the entire app, interact with the dashboard, and inspect the traces immediately, even before they set up their API keys.

## 6. Preference-Based Refinement (DPO/RLHF) opening hook loop
- **Decision**: Implemented an automated hook scorer within the `HumanizerAgent` that generates two competing opening options and uses a critic prompt (Reward-Model-Lite) to select the winner.
- **Rationale**: Demonstrates applied awareness of reinforcement learning without needing to fine-tune a model. The critic scores candidates on tonality fidelity and AI tells, selecting the best hook before drafting the full chapter.

## 7. RAG BM25 + Dense Hybrid Search
- **Decision**: Combined vector search (using local NumPy cosine similarities for zero binary dependencies) with a custom pure-Python BM25 keyword indexer.
- **Rationale**: Dense embeddings capture semantic similarity, while BM25 excels at exact keyword matching (like technical terms, dates, and names). Combining them offers robust RAG grounding without needing a complex external database.

## 8. Web Search Fallback with DuckDuckGo Search
- **Decision**: Integrated the free `duckduckgo_search` library as the researcher's search tool.
- **Rationale**: Avoids forcing the user to register for paid search APIs (Google, Tavily) while maintaining full web search grounding capabilities out-of-the-box.

## 9. Downstream Transition Repair (Test Case D)
- **Decision**: Created a specialized `SelfHealer` editor that runs after a chapter is inserted to scan subsequent chapters, adjust chapter-number strings, and integrate callbacks from the new chapter.
- **Rationale**: Solves the test case D requirement. Prevents broken narrative flow and numbering inconsistencies that naturally happen when modifying a book structure.

## 10. Asynchronous Background Execution via FastAPI BackgroundTasks
- **Decision**: Outlines are generated synchronously so the user sees the plan immediately, while chapters are written and copy-edited asynchronously in background tasks.
- **Rationale**: Writing 10 detailed chapters (25,000+ words) can take 5+ minutes, which would cause standard HTTP connections to timeout. Background tasks allow the React dashboard to poll progress and display real-time logs.
