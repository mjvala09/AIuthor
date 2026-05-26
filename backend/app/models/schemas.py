from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

# 1. Brief & Outline schemas
class BookBrief(BaseModel):
    topic: str
    reader_profile: str
    target_words: int = 15000
    tonality: str = "Conversational"  # Conversational, Academic, Storyteller, Motivational, Witty
    genre: str = "Non-Fiction"
    additional_guidelines: Optional[str] = ""
    api_key: Optional[str] = ""

class ChapterOutline(BaseModel):
    chapter_number: int
    title: str
    description: str
    target_words: int
    key_concepts: List[str] = []

class ChapterInsertRequest(BaseModel):
    insert_after_chapter: int
    title: str
    description: str
    target_words: int
    key_concepts: List[str] = []
    api_key: Optional[str] = ""

class BookOutline(BaseModel):
    title: str
    subtitle: Optional[str] = ""
    author: Optional[str] = "AIuthor"
    brief: BookBrief
    chapters: List[ChapterOutline]
    overall_guidelines: List[str] = []
    style_rules: List[str] = []

# 2. Memory schemas
class MemoryFact(BaseModel):
    claim: str
    source_chapter: int
    verified: bool = False
    citation: Optional[str] = ""

class MemoryConcept(BaseModel):
    name: str
    type: str  # "character", "setting", "term", "concept"
    description: str
    first_introduced_chapter: int
    details: Dict[str, Any] = Field(default_factory=dict)

class MemoryCallback(BaseModel):
    content: str
    source_chapter: int
    target_chapter: int
    callback_trigger: str
    applied: bool = False

class MemoryDecision(BaseModel):
    decision: str
    context: str
    rationale: str
    agent: str
    chapter_number: int
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class BookMemory(BaseModel):
    fact_registry: List[MemoryFact] = Field(default_factory=list)
    concept_bible: List[MemoryConcept] = Field(default_factory=list)
    callback_index: List[MemoryCallback] = Field(default_factory=list)
    tonality_fingerprint: List[str] = Field(default_factory=list)
    decision_log: List[MemoryDecision] = Field(default_factory=list)

# 3. Chapter results
class ChapterResult(BaseModel):
    chapter_number: int
    title: str
    draft: str = ""
    humanized: str = ""
    edited: str = ""
    final_text: str = ""
    status: str = "pending"  # pending, researching, writing, humanizing, editing, checking, complete
    word_count: int = 0
    research_report: str = ""
    fact_check_report: str = ""
    eval_score: float = 0.0

# 4. Observability & Tracing
class TraceEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    agent_name: str
    step_name: str
    input_data: Any
    output_data: Any
    trace_log: str = ""

class TokenCostEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    agent_name: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    cost: float

class TraceBundle(BaseModel):
    run_id: str
    brief: BookBrief
    traces: List[TraceEntry] = Field(default_factory=list)
    token_cost: List[TokenCostEntry] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0

# 5. Full Book State
class BookResult(BaseModel):
    run_id: str
    brief: BookBrief
    outline: Optional[BookOutline] = None
    memories: BookMemory = Field(default_factory=BookMemory)
    chapters: List[ChapterResult] = Field(default_factory=list)
    pdf_path: Optional[str] = ""
    docx_path: Optional[str] = ""
    status: str = "idle"  # idle, outline_planned, active, complete, failed
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    trace_bundle: Optional[TraceBundle] = None

# 6. Evals
class RubricScore(BaseModel):
    dimension: str
    score: float  # 0.0 to 1.0
    feedback: str
    details: Dict[str, Any] = Field(default_factory=dict)

class EvalsReport(BaseModel):
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    completeness: RubricScore
    tonality: RubricScore
    ai_tells: RubricScore
    fact_coverage: RubricScore
    callback_recall: RubricScore
    overall_score: float
