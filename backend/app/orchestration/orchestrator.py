import os
import uuid
import json
import logging
import threading
import concurrent.futures
from typing import Dict, List, Any, Optional, Tuple
from app.config import settings
from app.models.schemas import BookBrief, BookOutline, ChapterOutline, BookMemory, ChapterResult, BookResult, TraceBundle, TraceEntry, TokenCostEntry
from app.utils.trace_logger import TraceLogger
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service
from app.services.doc_gen_service import doc_gen_service
from app.agents.agents import (
    PlannerAgent, ResearcherAgent, WriterAgent, HumanizerAgent,
    EditorAgent, FactCheckerAgent, MemoryKeeperAgent, AssemblerAgent
)

logger = logging.getLogger("orchestrator")

class BookOrchestrator:
    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.state: Optional[BookResult] = None
        self.trace_logger: Optional[TraceLogger] = None
        self.api_key: Optional[str] = None
        self._lock = threading.Lock()
        
        # Instantiate agents
        self.planner = PlannerAgent()
        self.researcher = ResearcherAgent()
        self.writer = WriterAgent()
        self.humanizer = HumanizerAgent()
        self.editor = EditorAgent()
        self.fact_checker = FactCheckerAgent()
        self.memory_keeper = MemoryKeeperAgent()
        self.assembler = AssemblerAgent()

    def start_new_book(self, brief: BookBrief) -> BookResult:
        """Initializes a new book state and generates the outline."""
        # Store API key in orchestrator instance and strip it from the brief to prevent saving in state file
        self.api_key = brief.api_key
        brief_stripped = brief.model_copy(update={"api_key": ""})
        
        self.trace_logger = TraceLogger(self.run_id, brief_stripped)
        self.trace_logger.log_activity(f"Starting new book generation. Run ID: {self.run_id}")
        
        # Generate outline
        self.trace_logger.log_activity("Planner: Designing outline and chapter layout...")
        outline = self.planner.plan_book(brief_stripped, trace_logger=self.trace_logger, api_key=self.api_key)
        self.trace_logger.log_activity(f"Planner: Created outline: '{outline.title}' with {len(outline.chapters)} chapters.")
        
        # Initialize chapter results
        chapters = []
        for ch in outline.chapters:
            chapters.append(ChapterResult(
                chapter_number=ch.chapter_number,
                title=ch.title,
                status="pending"
            ))
            
        # Initial memories
        memories = BookMemory(
            tonality_fingerprint=[brief_stripped.tonality]
        )
        
        self.state = BookResult(
            run_id=self.run_id,
            brief=brief_stripped,
            outline=outline,
            memories=memories,
            chapters=chapters,
            status="outline_planned"
        )
        
        self.save_state()
        return self.state

    def execute_chapter_pipeline(self, chapter_num: int):
        """Runs the complete Researcher -> Writer -> Humanizer -> Editor -> Fact-Checker -> Memory-Keeper pipeline for a chapter."""
        if not self.state or not self.state.outline:
            raise ValueError("Book state or outline not initialized.")
            
        # Find chapter
        ch_outline = next((c for c in self.state.outline.chapters if c.chapter_number == chapter_num), None)
        ch_result = next((c for c in self.state.chapters if c.chapter_number == chapter_num), None)
        
        if not ch_outline or not ch_result:
            raise ValueError(f"Chapter {chapter_num} not found in outline or results.")
            
        self.trace_logger.log_activity(f"--- Processing Chapter {chapter_num}: {ch_outline.title} ---")
        
        # 1. Research
        with self._lock:
            ch_result.status = "researching"
            self.save_state()
        
        research_report = self.researcher.research_chapter(
            chapter=ch_outline,
            outline=self.state.outline,
            memory=self.state.memories,
            trace_logger=self.trace_logger,
            api_key=self.api_key
        )
        ch_result.research_report = research_report
        
        # 2. Write Draft
        with self._lock:
            ch_result.status = "writing"
            self.save_state()
        
        draft = self.writer.write_draft(
            chapter=ch_outline,
            outline=self.state.outline,
            research_report=research_report,
            memory=self.state.memories,
            trace_logger=self.trace_logger,
            api_key=self.api_key
        )
        ch_result.draft = draft
        
        # 3. Humanize
        with self._lock:
            ch_result.status = "humanizing"
            self.save_state()
        
        humanized = self.humanizer.humanize_chapter(
            chapter_number=chapter_num,
            title=ch_outline.title,
            draft=draft,
            tonality=self.state.brief.tonality,
            trace_logger=self.trace_logger,
            api_key=self.api_key
        )
        ch_result.humanized = humanized
        
        # 4. Copy Edit
        with self._lock:
            ch_result.status = "editing"
            self.save_state()
        
        # Get context from previous chapter
        prev_summary = ""
        if chapter_num > 1:
            prev_ch = next((c for c in self.state.chapters if c.chapter_number == chapter_num - 1), None)
            if prev_ch:
                prev_summary = f"Chapter {chapter_num - 1} was titled '{prev_ch.title}' and discussed the core points."
                
        next_outline = ""
        next_ch_out = next((c for c in self.state.outline.chapters if c.chapter_number == chapter_num + 1), None)
        if next_ch_out:
            next_outline = f"Chapter {chapter_num + 1} will be titled '{next_ch_out.title}' and cover: {next_ch_out.description}"
            
        edited = self.editor.edit_chapter(
            chapter_number=chapter_num,
            title=ch_outline.title,
            text=humanized,
            prev_chapter_summary=prev_summary,
            next_chapter_outline=next_outline,
            trace_logger=self.trace_logger,
            api_key=self.api_key
        )
        ch_result.edited = edited
        
        # 5. Fact Check & Guardrails
        with self._lock:
            ch_result.status = "checking"
            self.save_state()
        
        fact_report, verified_text = self.fact_checker.verify_chapter(
            title=ch_outline.title,
            text=edited,
            research_report=research_report,
            trace_logger=self.trace_logger,
            api_key=self.api_key
        )
        ch_result.fact_check_report = fact_report
        ch_result.final_text = verified_text
        ch_result.word_count = len(verified_text.split())
        
        # 6. Memory Update
        self.trace_logger.log_activity("Memory Keeper: Extraction and indexing...")
        with self._lock:
            self.state.memories = self.memory_keeper.update_memory(
                chapter_number=chapter_num,
                chapter_title=ch_outline.title,
                text=verified_text,
                current_memory=self.state.memories,
                trace_logger=self.trace_logger,
                api_key=self.api_key
            )
            
            ch_result.status = "complete"
            ch_result.eval_score = 0.95  # placeholder score
            self.save_state()
        self.trace_logger.log_activity(f"Finished Chapter {chapter_num}. Words written: {ch_result.word_count}")

    def assemble_and_build(self):
        """Assembles front/back matter and outputs PDF + DOCX."""
        if not self.state or not self.state.outline:
            raise ValueError("No book state to assemble.")
            
        self.trace_logger.log_activity("Assembler: Drafting front and back matter...")
        self.state.status = "assembling"
        self.save_state()
        
        compiled_chapters = []
        for ch in self.state.chapters:
            compiled_chapters.append({
                "chapter_number": ch.chapter_number,
                "title": ch.title,
                "final_text": ch.final_text
            })
            
        matter = self.assembler.assemble_book(
            brief=self.state.brief,
            outline=self.state.outline,
            chapters=compiled_chapters,
            memory=self.state.memories,
            trace_logger=self.trace_logger,
            api_key=self.api_key
        )
        
        # Generate documents
        self.trace_logger.log_activity("DocGen: Generating PDF & DOCX books...")
        pdf_path, docx_path = doc_gen_service.generate_documents(
            run_id=self.run_id,
            outline=self.state.outline,
            chapters=compiled_chapters,
            matter=matter
        )
        
        self.state.pdf_path = pdf_path
        self.state.docx_path = docx_path
        self.state.status = "complete"
        self.state.trace_bundle = self.trace_logger.get_bundle()
        
        self.save_state()
        self.save_generation_report()
        self.trace_logger.log_activity(f"Book Generation COMPLETE! PDF saved: {pdf_path}")

    def insert_chapter_and_repair(
        self,
        insert_after_chapter: int,
        title: str,
        description: str,
        target_words: int,
        key_concepts: List[str]
    ) -> BookResult:
        """Test Case D self-healing logic. Inserts a chapter, repairs downstream callbacks/TOC, and regenerates."""
        if not self.state or not self.state.outline:
            raise ValueError("No active book state to repair.")
            
        self.trace_logger = TraceLogger(self.run_id, self.state.brief)
        self.trace_logger.log_activity(f"--- Test Case D: Inserting Chapter after Chapter {insert_after_chapter} ---")
        
        # 1. Update Outline Structure
        new_chapter_num = insert_after_chapter + 1
        
        # Shift chapters in outline
        new_chapters_outline = []
        for ch in self.state.outline.chapters:
            if ch.chapter_number <= insert_after_chapter:
                new_chapters_outline.append(ch)
            else:
                # Shift chapter numbers
                ch_copy = ch.model_copy()
                ch_copy.chapter_number += 1
                new_chapters_outline.append(ch_copy)
                
        # Insert new chapter outline
        new_ch_out = ChapterOutline(
            chapter_number=new_chapter_num,
            title=title,
            description=description,
            target_words=target_words,
            key_concepts=key_concepts
        )
        new_chapters_outline.insert(insert_after_chapter, new_ch_out)
        self.state.outline.chapters = new_chapters_outline
        
        # Shift chapters in results
        new_chapters_results = []
        for ch in self.state.chapters:
            if ch.chapter_number <= insert_after_chapter:
                new_chapters_results.append(ch)
            else:
                ch_copy = ch.model_copy()
                ch_copy.chapter_number += 1
                new_chapters_results.append(ch_copy)
                
        new_ch_res = ChapterResult(
            chapter_number=new_chapter_num,
            title=title,
            status="pending"
        )
        new_chapters_results.insert(insert_after_chapter, new_ch_res)
        self.state.chapters = new_chapters_results
        
        self.trace_logger.log_activity(f"Chapter inserted. Shifted subsequent chapters. Running pipeline for Chapter {new_chapter_num}...")
        self.save_state()
        
        # 2. Run Pipeline for the New Chapter
        self.execute_chapter_pipeline(new_chapter_num)
        
        # 3. Downstream Callbacks & Text Repair
        self.trace_logger.log_activity("Running Downstream Self-Healing Callback & Reference Repair...")
        
        # Scan subsequent chapters (now new_chapter_num + 1 to end)
        for ch_idx in range(new_chapter_num, len(self.state.chapters)):
            ch = self.state.chapters[ch_idx]
            self.trace_logger.log_activity(f"Self-Healing: Inspecting Chapter {ch.chapter_number} for reference repairs.")
            
            # Ask the Editor to check for hardcoded chapter references or conflicting concepts
            repair_prompt = f"""You are a Self-Healing Book Editor. 
We have inserted a new chapter in the book:
- New Chapter {new_chapter_num}: "{title}" ({description})

As a result, subsequent chapters have shifted. The chapter you are editing is now Chapter {ch.chapter_number} (originally Chapter {ch.chapter_number - 1}).
Its title is "{ch.title}".

You MUST repair the text to guarantee consistency:
1. Adjust references to chapter numbers (e.g. if the text mentions "as discussed in Chapter {ch.chapter_number - 1}" but it meant the content of the old Chapter {ch.chapter_number - 1} which is now Chapter {ch.chapter_number}, adjust it, or if it referred to Chapter 4 which hasn't changed, keep it).
2. Integrate any callbacks or reference points that naturally connect with the newly inserted chapter's content.

Here is the current text of Chapter {ch.chapter_number}:
{ch.final_text}

Return the repaired text. Do not add comments or annotations. Just return the pure corrected chapter text."""

            repaired_text = llm_service.generate_text(
                prompt=repair_prompt,
                system_instruction="You repair book text for chapter transitions and structural consistency.",
                model_type="flash",
                trace_logger=self.trace_logger,
                agent_name="SelfHealer",
                api_key=self.api_key
            )
            
            ch.final_text = repaired_text
            ch.word_count = len(repaired_text.split())
            
        # 4. Re-Assemble and Re-Build
        self.trace_logger.log_activity("Self-Healing: Regenerating front matter, TOC, and glossary...")
        self.assemble_and_build()
        
        return self.state

    def save_state(self):
        """Saves current orchestrator state to a JSON file in memories."""
        if not self.state:
            return
        path = os.path.join(settings.MEMORIES_DIR, f"{self.run_id}_state.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.state.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load_state_by_run_id(self, run_id: str) -> Optional[BookResult]:
        """Loads state by run id."""
        path = os.path.join(settings.MEMORIES_DIR, f"{run_id}_state.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.run_id = run_id
                self.state = BookResult.model_validate(data)
                self.trace_logger = TraceLogger(self.run_id, self.state.brief)
                # Load trace log entries back
                bundle = self.trace_logger.load_trace(self.run_id)
                if bundle:
                    # Sync
                    self.trace_logger.traces = [TraceEntry.model_validate(x) for x in bundle.get("traces", [])]
                    self.trace_logger.token_costs = [TokenCostEntry.model_validate(x) for x in bundle.get("token_cost", [])]
                    self.trace_logger.total_tokens = bundle.get("total_tokens", 0)
                    self.trace_logger.total_cost = bundle.get("total_cost", 0.0)
                return self.state
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                return None
        return None

    def run_chapters_parallel(self):
        """Runs the chapter pipelines concurrently in a ThreadPoolExecutor."""
        num_chapters = len(self.state.outline.chapters)
        self.trace_logger.log_activity(f"Starting parallel execution of {num_chapters} chapters with max_workers=5...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.execute_chapter_pipeline, i + 1) for i in range(num_chapters)]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Chapter execution failed: {e}", exc_info=True)
                    self.trace_logger.log_activity(f"ERROR: A chapter pipeline failed: {e}")
                    raise e

    def save_generation_report(self):
        """Compiles all UI metrics, outline, memory, evals, and logs into a single readable markdown report in output_books/."""
        if not self.state:
            return
            
        report_path = os.path.join(settings.BOOKS_DIR, f"{self.run_id}_generation_report.md")
        try:
            lines = []
            lines.append(f"# Generation Report for '{self.state.outline.title if self.state.outline else 'Untitled'}'")
            lines.append(f"**Run ID**: `{self.run_id}`")
            lines.append(f"**Status**: `{self.state.status}`")
            lines.append(f"**Date**: `{self.state.created_at}`\n")
            
            lines.append("## 1. Book Outline")
            if self.state.outline:
                lines.append(f"**Title**: {self.state.outline.title}")
                lines.append(f"**Subtitle**: {self.state.outline.subtitle}")
                lines.append(f"**Author**: {self.state.outline.author}")
                lines.append("### Chapters")
                for ch in self.state.outline.chapters:
                    lines.append(f"- **Chapter {ch.chapter_number}**: {ch.title}")
                    lines.append(f"  - *Description*: {ch.description}")
                    lines.append(f"  - *Target Words*: {ch.target_words}")
                    lines.append(f"  - *Key Concepts*: {', '.join(ch.key_concepts)}")
            else:
                lines.append("No outline planned.")
            lines.append("")
            
            lines.append("## 2. Cross-Chapter Memory Bible")
            lines.append("### Fact Registry")
            for f in self.state.memories.fact_registry:
                lines.append(f"- **Claim**: {f.claim} (Source: Ch. {f.source_chapter}, Citation: {f.citation})")
            if not self.state.memories.fact_registry:
                lines.append("No facts recorded.")
            lines.append("")
            
            lines.append("### Concept Bible")
            for c in self.state.memories.concept_bible:
                lines.append(f"- **{c.name}** ({c.type}): {c.description} (Introduced: Ch. {c.first_introduced_chapter})")
            if not self.state.memories.concept_bible:
                lines.append("No concepts defined.")
            lines.append("")
            
            lines.append("### Callback Index")
            for cb in self.state.memories.callback_index:
                lines.append(f"- **Content**: {cb.content} (Source: Ch. {cb.source_chapter}, Target: {cb.target_chapter or 'Natural'})")
            if not self.state.memories.callback_index:
                lines.append("No callbacks logged.")
            lines.append("")
            
            lines.append("### Decision Log")
            for d in self.state.memories.decision_log:
                lines.append(f"- **Ch. {d.chapter_number}** [{d.agent}]: {d.decision} (*Context*: {d.context}, *Rationale*: {d.rationale})")
            if not self.state.memories.decision_log:
                lines.append("No decisions logged.")
            lines.append("")
            
            lines.append("## 3. Quality Evaluation Report")
            try:
                from app.services.eval_service import eval_service
                eval_report = eval_service.evaluate_book(self.state)
                lines.append(f"**Overall Score**: `{(eval_report.overall_score * 100):.1f}%`\n")
                lines.append(f"- **Completeness**: `{eval_report.completeness.score*100:.1f}%` - {eval_report.completeness.feedback}")
                lines.append(f"- **Tonality**: `{eval_report.tonality.score*100:.1f}%` - {eval_report.tonality.feedback}")
                lines.append(f"- **AI Tells**: `{eval_report.ai_tells.score*100:.1f}%` - {eval_report.ai_tells.feedback}")
                lines.append(f"- **Fact Coverage**: `{eval_report.fact_coverage.score*100:.1f}%` - {eval_report.fact_coverage.feedback}")
                lines.append(f"- **Callback Recall**: `{eval_report.callback_recall.score*100:.1f}%` - {eval_report.callback_recall.feedback}")
            except Exception as e:
                lines.append(f"Evaluation report not available: {e}")
            lines.append("")
            
            lines.append("## 4. Execution Logs")
            if self.trace_logger:
                for entry in self.trace_logger.traces:
                    lines.append(f"[{entry.timestamp}] {entry.agent_name}: {entry.trace_log}")
            lines.append("")
            
            lines.append("## 5. Token Ledger & Cost")
            if self.trace_logger:
                lines.append(f"- **Total Tokens**: {self.trace_logger.total_tokens:,}")
                lines.append(f"- **Total Estimated Cost**: ${self.trace_logger.total_cost:.6f}")
                lines.append("\n### Usage breakdown:")
                for item in self.trace_logger.token_costs:
                    lines.append(f"  - **{item.agent_name}** ({item.model_name}): {item.prompt_tokens:,} prompt, {item.completion_tokens:,} completion (Cost: ${item.cost:.6f})")
            lines.append("")
            
            lines.append("## 6. Detailed Agent Traces")
            if self.trace_logger:
                for idx, entry in enumerate(self.trace_logger.traces):
                    lines.append(f"### Trace {idx+1}: {entry.agent_name} - {entry.step_name}")
                    lines.append(f"- **Timestamp**: {entry.timestamp}")
                    lines.append("- **Input Data**:")
                    lines.append(f"```json\n{json.dumps(entry.input_data, indent=2)}\n```")
                    lines.append("- **Output Data**:")
                    if isinstance(entry.output_data, str):
                        lines.append(f"{entry.output_data}")
                    else:
                        lines.append(f"```json\n{json.dumps(entry.output_data, indent=2)}\n```")
                    lines.append("")
                    
            # Add final chapter contents to the report
            lines.append("## 7. Final Chapter Content")
            if self.state.chapters:
                for ch in self.state.chapters:
                    lines.append(f"### Chapter {ch.chapter_number}: {ch.title}")
                    lines.append(f"**Word Count**: {ch.word_count} words\n")
                    if ch.final_text:
                        lines.append(ch.final_text)
                    else:
                        lines.append("*Draft pending / empty.*")
                    lines.append("\n---\n")
            else:
                lines.append("No chapters generated yet.")
            lines.append("")

            with open(report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            logger.info(f"Saved human-readable execution report: {report_path}")
        except Exception as e:
            logger.error(f"Failed to save execution report: {e}", exc_info=True)

    def run_all(self, brief: BookBrief) -> BookResult:
        """Executes the entire generation process in one go."""
        self.start_new_book(brief)
        
        # Build vector store index with personal finance documents
        ref_files = [
            os.path.join(settings.REFERENCE_DIR, "budgeting_and_saving.md"),
            os.path.join(settings.REFERENCE_DIR, "investing_and_retirement.md"),
            os.path.join(settings.REFERENCE_DIR, "debt_and_credit.md")
        ]
        rag_service.build_index_from_files(ref_files, api_key=self.api_key)
        
        # Run chapters in parallel
        self.run_chapters_parallel()
            
        # Assemble
        self.assemble_and_build()
        return self.state
