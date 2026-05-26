import os
import sys
import json
import logging

# Ensure backend folder is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.models.schemas import BookBrief
from app.orchestration.orchestrator import BookOrchestrator
from app.services.eval_service import eval_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_runner")

def run_test_case_a() -> str:
    logger.info("==========================================")
    logger.info("   RUNNING TEST CASE A: 10-Chapter Finance Book   ")
    logger.info("==========================================")
    
    brief = BookBrief(
        topic="Beginner's guide to personal finance",
        reader_profile="Young adults starting their careers, no prior finance background",
        target_words=10000, # reduced to fit assessment timeline but keep standard structure
        tonality="Conversational",
        genre="Non-Fiction",
        additional_guidelines="Focus on emergency funds, compound interest, index funds, and credit score optimization."
    )
    
    orchestrator = BookOrchestrator(run_id="test-a")
    state = orchestrator.run_all(brief)
    
    # Run Evals
    report = eval_service.evaluate_book(state)
    eval_path = os.path.join(settings.TRACES_DIR, "test-a_eval_report.json")
    with open(eval_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
        
    logger.info(f"Test Case A Complete! PDF: {state.pdf_path}, Word: {state.docx_path}")
    logger.info(f"Evaluation Score: {report.overall_score:.4f}")
    return state.run_id

def run_test_case_b():
    logger.info("==========================================")
    logger.info("   RUNNING TEST CASE B: 5-Chapter Novella   ")
    logger.info("==========================================")
    
    brief = BookBrief(
        topic="A mystery novella about a lost compass",
        reader_profile="General fiction readers, young adult",
        target_words=5000,
        tonality="Storyteller",
        genre="Fiction",
        additional_guidelines="Must feature two main characters, Leo (a retired explorer) and Maya (his curious granddaughter), throughout the 5 chapters."
    )
    
    orchestrator = BookOrchestrator(run_id="test-b")
    state = orchestrator.run_all(brief)
    
    # Run Evals
    report = eval_service.evaluate_book(state)
    eval_path = os.path.join(settings.TRACES_DIR, "test-b_eval_report.json")
    with open(eval_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
        
    logger.info(f"Test Case B Complete! PDF: {state.pdf_path}, Word: {state.docx_path}")
    logger.info(f"Evaluation Score: {report.overall_score:.4f}")

def run_test_case_c(run_id_a: str):
    logger.info("==========================================")
    logger.info("   RUNNING TEST CASE C: Chapter 3 Tonal Variations   ")
    logger.info("==========================================")
    
    # Load Test Case A state
    orchestrator = BookOrchestrator()
    state = orchestrator.load_state_by_run_id(run_id_a)
    if not state or len(state.chapters) < 3:
        logger.error("Test Case A state not found or has fewer than 3 chapters. Skipping C.")
        return
        
    ch3 = state.chapters[2] # 0-indexed
    logger.info(f"Chapter 3 Original Title: {ch3.title}")
    
    tonalities = ["Academic", "Motivational", "Witty"]
    for t in tonalities:
        logger.info(f"Regenerating Chapter 3 in '{t}' tonality...")
        # Humanize using the different tonality preset
        humanized = orchestrator.humanizer.humanize_chapter(
            chapter_number=3,
            title=ch3.title,
            draft=ch3.draft,
            tonality=t,
            trace_logger=orchestrator.trace_logger
        )
        
        # Save variation file
        out_path = os.path.join(settings.BOOKS_DIR, f"test_c_chapter3_{t.lower()}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(humanized)
        logger.info(f"Saved: {out_path}")

def run_test_case_d(run_id_a: str):
    logger.info("==========================================")
    logger.info("   RUNNING TEST CASE D: Self-Healing Chapter Insertion   ")
    logger.info("==========================================")
    
    # Load Test Case A state
    orchestrator = BookOrchestrator()
    state = orchestrator.load_state_by_run_id(run_id_a)
    if not state:
        logger.error("Test Case A state not found. Skipping D.")
        return
        
    logger.info(f"Current chapters count: {len(state.chapters)}")
    
    # Insert new chapter between Chapter 4 and 5
    new_state = orchestrator.insert_chapter_and_repair(
        insert_after_chapter=4,
        title="Chapter 4b: Advanced Investing Strategies",
        description="ETFs, Index Funds, Dollar-cost averaging, and tax-advantaged retirement accounts.",
        target_words=1500,
        key_concepts=["ETFs", "Index Funds", "Roth IRA", "Compound Growth"]
    )
    
    # Run Evals on the newly repaired book
    report = eval_service.evaluate_book(new_state)
    eval_path = os.path.join(settings.TRACES_DIR, "test-d_eval_report.json")
    with open(eval_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
        
    logger.info(f"Test Case D Complete! Updated chapters count: {len(new_state.chapters)}")
    logger.info(f"New PDF generated at: {new_state.pdf_path}")
    logger.info(f"Evaluation Score: {report.overall_score:.4f}")

if __name__ == "__main__":
    logger.info("Starting AIuthor CLI Verification Suite...")
    
    # 1. Run A
    run_id_a = run_id_a = run_test_case_a()
    
    # 2. Run B
    run_test_case_b()
    
    # 3. Run C
    run_test_case_c(run_id_a)
    
    # 4. Run D
    run_test_case_d(run_id_a)
    
    logger.info("==========================================")
    logger.info("   CLI VERIFICATION SUITE RUN COMPLETED   ")
    logger.info("==========================================")
