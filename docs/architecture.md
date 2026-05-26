# AIuthor — System Architecture

This document describes the architectural topology, memory systems, and execution flows of the AIuthor book writer agentic system.

---

## 1. Agent Topology

AIuthor operates as an event-driven **orchestrator-worker pipeline** where a central State Machine manages the overall progress, and specific agents are invoked sequentially or conditionally based on execution status.

```mermaid
flowchart TD
    subgraph UI [Frontend Dashboard]
        Dashboard[React Web UI]
    end

    subgraph Backend [FastAPI Server]
        API[API Endpoints]
        Orchestrator[Book Orchestrator]
    end

    subgraph Agents [Agent Pipeline]
        Planner[Planner Agent]
        Researcher[Researcher Agent]
        Writer[Writer Agent]
        Humanizer[Humanizer Agent]
        Editor[Editor Agent]
        FactChecker[Fact-Checker Agent]
        MemoryKeeper[Memory Keeper Agent]
        Assembler[Assembler Agent]
        SelfHealer[Self-Healer Agent]
    end

    subgraph Storage [Persistent Data]
        State[(Book State JSON)]
        MemoryDB[(Memory Store Files)]
        RAGIndex[(Local RAG Index)]
        OutputDocs[(PDF + DOCX Books)]
        Traces[(Trace logs)]
    end

    Dashboard <--> |HTTP/WS| API
    API <--> Orchestrator
    
    Orchestrator --> |Invokes| Planner
    Orchestrator --> |Invokes| Researcher
    Orchestrator --> |Invokes| Writer
    Orchestrator --> |Invokes| Humanizer
    Orchestrator --> |Invokes| Editor
    Orchestrator --> |Invokes| FactChecker
    Orchestrator --> |Invokes| MemoryKeeper
    Orchestrator --> |Invokes| Assembler
    Orchestrator --> |Invokes| SelfHealer

    Orchestrator <--> |Saves/Loads| State
    Researcher <--> |Queries| RAGIndex
    MemoryKeeper --> |Appends| MemoryDB
    SelfHealer <--> |Updates| State
    Assembler --> |Triggers DocGen| OutputDocs
    Orchestrator --> |Logs Traces| Traces
```

---

## 2. Memory Architecture

A single context window is never stuffed with previous chapters. Instead, AIuthor maintains structured, queryable files for the book memory:

1. **Fact Registry**: A cumulative ledger of verified facts, statistics, and calculations. Extracted by the Memory Keeper and checked by the Fact-Checker.
2. **Concept/Character Bible**: A registry of terms, characters, and descriptions. Ensured by the Writer for consistency.
3. **Callback Index**: Log of narrative milestones or milestones to refer back to (e.g. "Char X did Y in Ch. 1").
4. **Tonality Fingerprint**: Style guidelines, custom rules, and vocabulary choices cascading through all book surfaces.
5. **Decision Log**: Audit log of creative decisions made during the writing loop.

---

## 3. Data Flow

```mermaid
sequenceDiagram
    participant User as User / Frontend
    participant Orch as Book Orchestrator
    participant RAG as RAG Service
    participant Agent as Active Agent
    participant Mem as Memory Stores

    User->>Orch: Submit Book Brief
    Orch->>Agent: Invoke Planner Agent
    Agent-->>Orch: Return Book Outline
    Orch->>User: Display Outline & Start Background Writing

    loop For each Chapter
        Orch->>RAG: hybrid_search(Concepts)
        RAG-->>Orch: Grounded facts
        Orch->>Agent: Invoke Researcher (Facts + Web)
        Agent-->>Orch: Research Report
        
        Orch->>Mem: Get active callbacks & concept schemas
        Mem-->>Orch: Context definitions
        Orch->>Agent: Invoke Writer Agent (Outline + Research + Callbacks)
        Agent-->>Orch: Raw Chapter Draft
        
        Orch->>Agent: Invoke Humanizer (Draft + Tonality Preset)
        Note over Agent: Runs RLHF opening choice
        Note over Agent: Eliminates AI tells
        Agent-->>Orch: Humanized Text
        
        Orch->>Agent: Invoke Editor (Transitions)
        Agent-->>Orch: Copy-edited Text
        
        Orch->>Agent: Invoke Fact-Checker (Verify against Report)
        Note over Agent: Citation-or-soften rule
        Agent-->>Orch: Verified Chapter Text
        
        Orch->>Agent: Invoke Memory Keeper (Extract changes)
        Agent->>Mem: Update Fact, Concept, and Callback registers
    end

    Orch->>Agent: Invoke Assembler (Compile all sections)
    Agent-->>Orch: Front & Back matter
    Orch->>Orch: DocGen (Generate styled PDF/DOCX)
    Orch->>User: Completed Book ready for Download
```

---

## 4. Failure Paths & Recovery

1. **LLM API Failures**:
   - If a call to `gemini-2.5-pro` fails (e.g. rate limit, content block), the `LLMService` automatically falls back to `gemini-2.5-flash` or `gemini-1.5-flash` to continue execution.
   - If both fail, it can fall back to OpenAI API keys if provided.
2. **Fact Discrepancies**:
   - If the Fact-Checker detects ungrounded assertions, it either softens the statements using hedges ("some sources argue...") or triggers the *abstention rule*, omitting the claim to prevent hallucinations.
3. **Downstream Insertion (Test Case D)**:
   - When a chapter is inserted, the outline is restructured, and the orchestrator shifts subsequent chapter numbers.
   - It runs the standard pipeline for the new chapter.
   - It then invokes the `SelfHealer` editor on all downstream chapters, scanning their texts and rewriting hardcoded chapter numbers (e.g. changing "Chapter 5" references to "Chapter 6") and integrating callbacks relative to the new chapter.
