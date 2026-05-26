import os
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.models.schemas import BookBrief, BookOutline, BookResult, EvalsReport, ChapterInsertRequest
from app.orchestration.orchestrator import BookOrchestrator
from app.services.eval_service import eval_service

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

app = FastAPI(title="AIuthor Book Generator API", version="0.1.0")

# Enable CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active orchestrators in memory
active_runs: Dict[str, BookOrchestrator] = {}

def run_book_generation_task(orchestrator: BookOrchestrator):
    try:
        # Load reference files if they exist and index RAG
        ref_files = [
            os.path.join(settings.REFERENCE_DIR, "budgeting_and_saving.md"),
            os.path.join(settings.REFERENCE_DIR, "investing_and_retirement.md"),
            os.path.join(settings.REFERENCE_DIR, "debt_and_credit.md")
        ]
        # Build index
        from app.services.rag_service import rag_service
        rag_service.build_index_from_files(ref_files, api_key=orchestrator.api_key)
        
        # Execute chapter-by-chapter pipeline in parallel
        orchestrator.state.status = "writing_chapters"
        orchestrator.run_chapters_parallel()
            
        # Assemble
        orchestrator.assemble_and_build()
        
    except Exception as e:
        logger.error(f"Error in background generation run {orchestrator.run_id}: {e}", exc_info=True)
        if orchestrator.state:
            orchestrator.state.status = "failed"
            orchestrator.save_state()

def run_chapter_repair_task(
    orchestrator: BookOrchestrator,
    after_chapter: int,
    title: str,
    description: str,
    target_words: int,
    key_concepts: List[str]
):
    try:
        orchestrator.state.status = "repairing"
        orchestrator.insert_chapter_and_repair(
            insert_after_chapter=after_chapter,
            title=title,
            description=description,
            target_words=target_words,
            key_concepts=key_concepts
        )
    except Exception as e:
        logger.error(f"Error in background repair run {orchestrator.run_id}: {e}", exc_info=True)
        if orchestrator.state:
            orchestrator.state.status = "failed"
            orchestrator.save_state()

# --- API Routes ---

@app.post("/api/generate", response_model=BookResult)
def generate_book(brief: BookBrief, background_tasks: BackgroundTasks):
    """Starts a new book generation process. Generates outline immediately, writes chapters in background."""
    orchestrator = BookOrchestrator()
    initial_state = orchestrator.start_new_book(brief)
    
    # Store orchestrator in memory
    active_runs[orchestrator.run_id] = orchestrator
    
    # Queue the writing task
    background_tasks.add_task(run_book_generation_task, orchestrator)
    
    return initial_state

@app.get("/api/status/{run_id}", response_model=BookResult)
def get_status(run_id: str):
    """Retrieves current book state, checking active memory runs or loading from file."""
    if run_id in active_runs:
        return active_runs[run_id].state
        
    # Attempt to load from saved state file
    orchestrator = BookOrchestrator(run_id=run_id)
    state = orchestrator.load_state_by_run_id(run_id)
    if state:
        active_runs[run_id] = orchestrator
        return state
        
    raise HTTPException(status_code=404, detail=f"Book run {run_id} not found.")

@app.post("/api/insert-chapter/{run_id}", response_model=BookResult)
def insert_chapter(run_id: str, request: ChapterInsertRequest, background_tasks: BackgroundTasks):
    """Triggers Test Case D - inserts chapter and repairs downstream, executing in the background."""
    if run_id not in active_runs:
        orchestrator = BookOrchestrator(run_id=run_id)
        state = orchestrator.load_state_by_run_id(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Book run {run_id} not found.")
        active_runs[run_id] = orchestrator
        
    orchestrator = active_runs[run_id]
    if orchestrator.state.status in ["active", "repairing", "assembling"]:
        raise HTTPException(status_code=400, detail="Cannot insert chapter while another agent task is running.")
        
    # Set the API key
    orchestrator.api_key = request.api_key

    # Queue repair
    background_tasks.add_task(
        run_chapter_repair_task,
        orchestrator,
        request.insert_after_chapter,
        request.title,
        request.description,
        request.target_words,
        request.key_concepts
    )
    
    orchestrator.state.status = "repairing"
    orchestrator.save_state()
    return orchestrator.state

@app.get("/api/books")
def list_books():
    """Lists all generated books (looking at memories/state files)."""
    states = []
    if not os.path.exists(settings.MEMORIES_DIR):
        return states
        
    for filename in os.listdir(settings.MEMORIES_DIR):
        if filename.endswith("_state.json"):
            try:
                with open(os.path.join(settings.MEMORIES_DIR, filename), "r", encoding="utf-8") as f:
                    states.append(json.load(f))
            except Exception:
                pass
    return states

@app.get("/api/books/download/{run_id}/{file_type}")
def download_book(run_id: str, file_type: str):
    """Serves the generated PDF or DOCX file."""
    if file_type not in ["pdf", "docx"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Must be 'pdf' or 'docx'.")
        
    ext = "pdf" if file_type == "pdf" else "docx"
    filepath = os.path.join(settings.BOOKS_DIR, f"{run_id}_book.{ext}")
    
    if os.path.exists(filepath):
        return FileResponse(
            path=filepath,
            filename=f"{run_id}_book.{ext}",
            media_type="application/pdf" if file_type == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    raise HTTPException(status_code=404, detail="Requested book file not found. Ensure generation finished successfully.")

@app.get("/api/evals/{run_id}", response_model=EvalsReport)
def get_evals(run_id: str):
    """Runs automated evaluations on the book and returns the report card."""
    if run_id not in active_runs:
        orchestrator = BookOrchestrator(run_id=run_id)
        state = orchestrator.load_state_by_run_id(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Book run {run_id} not found.")
        active_runs[run_id] = orchestrator
        
    state = active_runs[run_id].state
    if state.status != "complete":
        raise HTTPException(status_code=400, detail="Cannot run evaluations on an incomplete book.")
        
    report = eval_service.evaluate_book(state)
    
    # Save report to docs for deliverables
    report_path = os.path.join(settings.TRACES_DIR, f"{run_id}_eval_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
        
    return report

# --- Mount Static Frontend ---

frontend_dist = os.path.join(os.path.dirname(settings.WORKSPACE_DIR), "frontend", "dist")

if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
else:
    @app.get("/")
    def read_root():
        return JSONResponse(content={
            "message": "FastAPI server running successfully. Frontend not compiled yet.",
            "instructions": "Navigate to the frontend folder and run 'npm run build' or run the root './run.sh' script to run both.",
            "api_docs": "/docs"
        })
