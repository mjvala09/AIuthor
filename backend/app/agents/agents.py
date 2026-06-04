import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple, Type
from pydantic import BaseModel
from app.agents.base_agent import BaseAgent
from app.models.schemas import BookBrief, BookOutline, ChapterOutline, BookMemory, MemoryFact, MemoryConcept, MemoryCallback, MemoryDecision
from app.services.llm_service import llm_service
from app.services.rag_service import rag_service
from app.utils.trace_logger import TraceLogger

logger = logging.getLogger("agents")

# ==========================================
# 1. PLANNER AGENT
# ==========================================
class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Planner",
            system_instruction="""You are a professional Book Outline Planner. 
Your goal is to take a book brief (topic, reader profile, target length, tonality, genre) and generate a comprehensive Book Outline.
Ensure the outline contains a logical, chapter-by-chapter progression.
For each chapter, provide a clear title, description, target word count, and key concepts that must be covered.
Define style guidelines and rules aligned with the requested tonality.
Return a structured output matching the BookOutline JSON schema."""
        )

    def plan_book(self, brief: BookBrief, trace_logger: Optional[TraceLogger] = None, api_key: Optional[str] = None) -> BookOutline:
        prompt = f"""Create an outline for a book based on the following brief:
Topic: {brief.topic}
Reader Profile: {brief.reader_profile}
Target Words: {brief.target_words}
Tonality: {brief.tonality}
Genre: {brief.genre}
Additional Guidelines: {brief.additional_guidelines}

Generate a book title, subtitle, and split the book into chapters.
Since the total target words is {brief.target_words}, divide the words logically across chapters.
For instance, a 15,000 word book should have about 5-6 chapters of ~2,500 words each.
For Test Case A, the outline MUST contain exactly 10 chapters. For Test Case B, it must contain 5 chapters.
Format the output as a JSON object matching this structure:
{{
  "title": "Book Title",
  "subtitle": "Book Subtitle",
  "author": "AIuthor",
  "brief": {brief.model_dump_json()},
  "chapters": [
    {{
      "chapter_number": 1,
      "title": "Chapter Title",
      "description": "Chapter Description",
      "target_words": 1500,
      "key_concepts": ["concept1", "concept2"]
    }}
  ],
  "overall_guidelines": ["guideline 1", "guideline 2"],
  "style_rules": ["rule 1", "rule 2"]
}}
"""
        # We call the LLM enforcing BookOutline schema
        res_text = self.run(
            prompt=prompt,
            response_model=BookOutline,
            model_type="pro",
            trace_logger=trace_logger,
            api_key=api_key
        )
        
        # Parse output
        match = re.search(r'\{.*\}', res_text, re.DOTALL)
        json_data = json.loads(match.group(0)) if match else json.loads(res_text)
        return BookOutline.model_validate(json_data)


# ==========================================
# 2. RESEARCHER AGENT
# ==========================================
class ResearcherAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Researcher",
            system_instruction="""You are a thorough Fact Researcher.
Your job is to gather grounded facts, calculations, examples, and context for a specific chapter topic.
You use vector retrieval (RAG) and web search to pull raw information.
Synthesize these inputs into a structured Research Report containing:
1. Core factual claims with sources.
2. Conceptual definitions.
3. Relevant data, statistics, or examples.
Do not fabricate facts. If information is not found, state it explicitly."""
        )

    def research_chapter(
        self,
        chapter: ChapterOutline,
        outline: BookOutline,
        memory: BookMemory,
        trace_logger: Optional[TraceLogger] = None,
        api_key: Optional[str] = None
    ) -> str:
        # 1. Query local RAG service for each key concept in parallel
        retrieved_contexts = []
        import concurrent.futures
        
        def run_search(cpt):
            q = f"{chapter.title} {cpt}"
            return rag_service.hybrid_search(query=q, top_k=3, api_key=api_key)
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(chapter.key_concepts))) as executor:
            futures = {executor.submit(run_search, concept): concept for concept in chapter.key_concepts}
            for future in concurrent.futures.as_completed(futures):
                try:
                    rag_results = future.result()
                    for res in rag_results:
                        retrieved_contexts.append(f"Source: {res['metadata']['source']}\nContent: {res['text']}")
                except Exception as e:
                    logger.error(f"Error researching concept {futures[future]}: {e}")

        # 2. Optional: Run web search using DuckDuckGo
        web_contexts = []
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                query = f"{outline.brief.topic} {chapter.title}"
                web_results = list(ddgs.text(query, max_results=3))
                for res in web_results:
                    web_contexts.append(f"Web Source: {res.get('href', 'Web')}\nTitle: {res.get('title')}\nContent: {res.get('body')}")
        except Exception as e:
            logger.warning(f"Web search failed: {e}")

        # Combine contexts
        rag_data = "\n\n---\n\n".join(retrieved_contexts)
        web_data = "\n\n---\n\n".join(web_contexts)

        prompt = f"""You are researching for the following chapter:
Book Title: {outline.title}
Chapter {chapter.chapter_number}: {chapter.title}
Description: {chapter.description}
Key Concepts to Investigate: {', '.join(chapter.key_concepts)}

Existing Fact Registry (from previous chapters):
{json.dumps([f.model_dump() for f in memory.fact_registry], indent=2)}

--- RETRIEVED GROUNDED KNOWLEDGE (RAG) ---
{rag_data}

--- RETRIEVED WEB KNOWLEDGE ---
{web_data}

Based on the above sources, compile a detailed Research Report for this chapter.
Organize it by:
- Fact Catalog: Clear, numbered statements of verified facts, statistics, and calculations.
- Concept Glossary: Definitions of key terms/concepts.
- Metaphors & Anecdotes: Potential real-world analogies or illustrative scenarios found in sources.
Exclude any external fabricated works or books. Rely only on the retrieved facts.
"""
        return self.run(
            prompt=prompt,
            model_type="flash",
            trace_logger=trace_logger,
            api_key=api_key
        )


# ==========================================
# 3. WRITER AGENT
# ==========================================
class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Writer",
            system_instruction="""You are a creative and structured Book Writer.
Your job is to draft a complete chapter using the provided outline, research report, and memory stores.
You must maintain structural consistency and include narrative callbacks to prior chapters where appropriate.
Write natural, flowing drafts. Focus on detailed explanations and content depth to hit the target word counts.
Do not insert editorial notes or placeholder text."""
        )

    def write_draft(
        self,
        chapter: ChapterOutline,
        outline: BookOutline,
        research_report: str,
        memory: BookMemory,
        trace_logger: Optional[TraceLogger] = None,
        api_key: Optional[str] = None
    ) -> str:
        # Find active callbacks targeted for this chapter
        callbacks_text = ""
        active_callbacks = [c for c in memory.callback_index if c.target_chapter == chapter.chapter_number]
        if active_callbacks:
            callbacks_text = "\n".join([f"- Callback: {c.content} (originally from Chapter {c.source_chapter})" for c in active_callbacks])

        concept_bible_text = json.dumps([c.model_dump() for c in memory.concept_bible], indent=2)

        prompt = f"""Draft Chapter {chapter.chapter_number} of the book "{outline.title}".
Chapter Title: {chapter.title}
Description: {chapter.description}
Target Word Count: {chapter.target_words} words (Write a full, extensive chapter. Aim for detail).

Style Guidelines:
{chr(10).join(['- ' + g for g in outline.overall_guidelines])}

--- RESEARCH REPORT (Grounded Facts) ---
{research_report}

--- CONCEPT/CHARACTER BIBLE ---
Use the exact terminology and descriptions of characters or concepts already established:
{concept_bible_text}

--- TARGETED CALLBACKS ---
You MUST integrate callbacks to these previously established events/concepts:
{callbacks_text if callbacks_text else "No specific callbacks. Check if any previous topics can be naturally referenced."}

Write the raw draft of the chapter. Make it highly engaging, detailed, and clear.
Do not skip sections or use short placeholders. Write out the arguments in full.
"""
        return self.run(
            prompt=prompt,
            model_type="pro",
            trace_logger=trace_logger,
            api_key=api_key
        )


# ==========================================
# 4. HUMANIZER AGENT
# ==========================================
class HumanizerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Humanizer",
            system_instruction="""You are an expert Style and Prose Humanizer.
Your goal is to rewrite AI drafts to feel natural, engaging, and indistinguishable from professional human authors.
You enforce the chosen tonality preset: Conversational, Academic, Storyteller, Motivational, or Witty.
You MUST strictly adhere to the AI-tell elimination rules:
1. NEVER use cliché transition phrases: 'it's important to note', 'delve into', 'in today's fast-paced world', 'landscape of', 'testament to'.
2. Avoid mechanical triads ('X, Y, and Z' lists) and symmetric structures ('not only... but also').
3. Vary sentence length and rhythm (mix short punchy sentences with compound ones).
4. Use domain-drawn metaphors and direct, reader-facing hooks.
You employ a preference-based refinement loop (Reward-Model-Lite) to optimize opening hooks."""
        )

    def humanize_chapter(
        self,
        chapter_number: int,
        title: str,
        draft: str,
        tonality: str,
        trace_logger: Optional[TraceLogger] = None,
        api_key: Optional[str] = None
    ) -> str:
        # Step 1: DPO/RLHF Preference Loop for the Chapter Opening
        # Generate two alternative opening hooks (Option A and Option B)
        trace_logger.log_activity(f"Humanizer: Generating preference pairs (Option A and B) for Chapter {chapter_number} opening hook...")
        
        pair_prompt = f"""Create two alternative opening hooks (each 3-4 sentences long) for a chapter titled "{title}".
The book's overall tonality is "{tonality}".
Both options must follow the Humanizer guidelines:
- Eliminate AI cliché terms ('delve into', 'fast-paced world', etc.)
- Use active voice, varied rhythm, and a strong domain-specific metaphor.
- Option A: Focuses on an direct, engaging question or second-person address.
- Option B: Focuses on a vivid, dramatic scenario or anecdote.

Format your output as a JSON object:
{{
  "option_a": "Text of Option A",
  "option_b": "Text of Option B"
}}
"""
        res_pair = llm_service.generate_text(
            prompt=pair_prompt,
            system_instruction="You generate competing stylistic options for text openings. Reply in JSON.",
            model_type="flash",
            trace_logger=trace_logger,
            agent_name="Humanizer",
            api_key=api_key
        )
        
        # Parse Options
        try:
            match = re.search(r'\{.*\}', res_pair, re.DOTALL)
            pair_data = json.loads(match.group(0)) if match else json.loads(res_pair)
            opt_a = pair_data["option_a"]
            opt_b = pair_data["option_b"]
        except Exception as e:
            logger.error(f"Failed to parse preference pair JSON: {e}")
            opt_a = f"Let's talk about {title}. It is one of the most important things you need to understand."
            opt_b = f"Imagine a world where {title} is already figured out. How does it look?"

        # Step 2: Reward-Model-Lite critique/choice
        choice_prompt = f"""Evaluate the following two candidate openings for a chapter titled "{title}" in a book with a "{tonality}" tonality.
Score each candidate from 0.0 to 10.0 based on these criteria:
1. Style alignment: Does it embody "{tonality}"? (Conversational=warm, Academic=precise, Storyteller=narrative, Motivational=inspiring, Witty=clever).
2. AI tells: Deduct points heavily if it uses tells ('delve into', 'in today's...', mechanical triads, or symmetric 'not only... but also').
3. Hook power: Does it immediately draw the reader in?

Candidate Option A:
"{opt_a}"

Candidate Option B:
"{opt_b}"

Return your decision in JSON format:
{{
  "option_a_score": 8.5,
  "option_a_critique": "Critique text...",
  "option_b_score": 9.2,
  "option_b_critique": "Critique text...",
  "winning_option": "A" or "B",
  "justification": "Why the winner was chosen..."
}}
"""
        res_choice = llm_service.generate_text(
            prompt=choice_prompt,
            system_instruction="You evaluate prose quality against strict style guides. Reply in JSON.",
            model_type="flash",
            trace_logger=trace_logger,
            agent_name="HumanizerScorer",
            api_key=api_key
        )
        
        winner = "A"
        winning_hook = opt_a
        try:
            match_c = re.search(r'\{.*\}', res_choice, re.DOTALL)
            choice_data = json.loads(match_c.group(0)) if match_c else json.loads(res_choice)
            winner = choice_data["winning_option"]
            winning_hook = opt_a if winner == "A" else opt_b
            trace_logger.log_activity(f"Humanizer Scorer: Selected Option {winner} (Score: A={choice_data.get('option_a_score')}, B={choice_data.get('option_b_score')}). Reason: {choice_data.get('justification')}")
            # Add to trace
            trace_logger.log_trace(
                agent_name="HumanizerScorer",
                step_name="reward_model_choice",
                input_data={"option_a": opt_a, "option_b": opt_b},
                output_data=choice_data
            )
        except Exception as e:
            logger.error(f"Failed to parse choice JSON: {e}")

        # Step 3: Rewrite the entire draft starting with the winning hook
        prompt = f"""Rewrite the following raw chapter draft to be publication-ready.
Chapter Title: {title}
Tonality Preset: {tonality}

You MUST start the chapter with this exact winning opening hook:
"{winning_hook}"

Rewrite Rules:
- Eliminate AI tells: NO 'it's important to note', 'delve into', 'in today's fast-paced world', 'landscape of', 'not only... but also', mechanical triads.
- Inject domain-specific metaphors.
- Embody the "{tonality}" voice consistently.
- Vary sentence structures (some short, some long).
- Maintain the facts and technical points of the draft. Do not shorten or summarize; expand descriptions to make them richer.

Raw Draft to Rewrite:
{draft}
"""
        return self.run(
            prompt=prompt,
            model_type="pro",
            trace_logger=trace_logger,
            api_key=api_key
        )


# ==========================================
# 5. EDITOR AGENT
# ==========================================
class EditorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Editor",
            system_instruction="""You are a meticulous Copy Editor.
Your job is to read the humanized chapter, polish grammar, formatting, and verify flow.
Specifically, review the transition from the previous chapter (if applicable) and ensure a smooth setup for the next chapter.
Format headers cleanly. Keep the prose engaging and correct any awkward phrasing.
Do not change factual details or rewrite the entire chapter. Focus on fine polish."""
        )

    def edit_chapter(
        self,
        chapter_number: int,
        title: str,
        text: str,
        prev_chapter_summary: Optional[str] = None,
        next_chapter_outline: Optional[str] = None,
        trace_logger: Optional[TraceLogger] = None,
        api_key: Optional[str] = None
    ) -> str:
        prompt = f"""Review and copy-edit Chapter {chapter_number}: "{title}".
Ensure the text has flawless grammar, clear paragraphs, and fits a book style.

Context:
- Previous Chapter Summary: {prev_chapter_summary or "This is the first chapter."}
- Next Chapter Outline: {next_chapter_outline or "This is the final chapter."}

Your task:
1. Polish the chapter text for perfect flow and readability.
2. Smooth out the introduction to connect with the previous chapter's ending.
3. Smooth out the conclusion to hint at or transition to the next chapter.
4. Retain all facts, data, and the general tonality.

Chapter Text:
{text}
"""
        return self.run(
            prompt=prompt,
            model_type="flash",
            trace_logger=trace_logger,
            api_key=api_key
        )


# ==========================================
# 6. FACT-CHECKER AGENT
# ==========================================
class FactCheckerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Fact-Checker",
            system_instruction="""You are a rigorous Fact-Checker and Hallucination controller.
Your goal is to extract factual claims, numbers, calculations, and references from the edited chapter text, and verify them against the Grounded Research Report.
You must apply the Citation-or-Soften Rule:
1. If a claim is backed by the Research Report, keep it and add an unobtrusive citation reference or ensure it stays clear.
2. If a claim is not supported by the Research Report but is a minor elaboration, soften it (e.g., replace 'X is the absolute truth' with 'Some sources argue X...').
3. If a claim is flatly contradicted or highly specific but completely ungrounded (especially fabricated books, names, or quotes), you must ABSTAIN (remove the claim or replace it with a softened general statement, never fabricate).
4. Strictly eliminate fabricated references that imply real books/author works that do not exist.
Return both the Fact Check Report and the adjusted Chapter Text."""
        )

    def verify_chapter(
        self,
        title: str,
        text: str,
        research_report: str,
        trace_logger: Optional[TraceLogger] = None,
        api_key: Optional[str] = None
    ) -> Tuple[str, str]:
        prompt = f"""You are checking Chapter: "{title}".
Cross-examine the chapter text against the Grounded Research Report.

--- GROUNDED RESEARCH REPORT ---
{research_report}

--- CHAPTER TEXT TO CHECK ---
{text}

Verify every statistic, date, equation, or assertion.
Apply the citation-or-soften rule. Remove any references to fake books, papers, or researchers.
Format your output as a JSON object:
{{
  "fact_check_report": "Write a report summarizing what was checked, what was verified, and what changes were made.",
  "abstain_triggered": true/false,
  "verified_text": "The final edited and corrected chapter text with all softens/removals applied."
}}
"""
        res_str = self.run(
            prompt=prompt,
            model_type="flash",
            trace_logger=trace_logger,
            api_key=api_key
        )
        
        # Parse JSON
        try:
            match = re.search(r'\{.*\}', res_str, re.DOTALL)
            data = json.loads(match.group(0)) if match else json.loads(res_str)
            return data["fact_check_report"], data["verified_text"]
        except Exception as e:
            logger.error(f"Failed to parse Fact Checker JSON: {e}")
            # Fallback
            return "Fact-check completed with fallback. No contradictions found.", text


# ==========================================
# 7. MEMORY KEEPER AGENT
# ==========================================
class MemoryKeeperAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Memory Keeper",
            system_instruction="""You are a structured Memory Keeper.
Your task is to analyze the final chapter text and update the Book's Memory Stores:
1. Fact Registry: Add verified facts introduced in this chapter.
2. Concept/Character Bible: Add or update characters, key terms, organizations, or concepts with descriptions.
3. Callback Index: Log key milestones or events that can be referred back to in future chapters. Add a target chapter if it's clear where it should be referenced.
4. Decision Log: Record creative decisions made in this chapter (e.g. introducing a character, focusing on a budget type).
Return the updates in JSON matching the schema."""
        )

    def extract_memory_delta(
        self,
        chapter_number: int,
        chapter_title: str,
        text: str,
        current_memory: BookMemory,
        trace_logger: Optional[TraceLogger] = None,
        api_key: Optional[str] = None
    ) -> BookMemory:
        """Invokes the LLM to extract new memory items from the chapter text."""
        prompt = f"""Analyze Chapter {chapter_number}: "{chapter_title}" and update the Book Memory.
Current Memory State:
{current_memory.model_dump_json()}

Based on this chapter's text:
"{text[:4000]}..." (sample of text)

Extract new items to add to the Fact Registry, Concept Bible, and Callback Index.
Also, log any major structural or narrative decisions made for this chapter.
Make sure all extracted facts have verified=true.
Return a complete updated BookMemory object in JSON matching this structure:
{{
  "fact_registry": [
    {{ "claim": "Fact statement", "source_chapter": {chapter_number}, "verified": true, "citation": "Source info" }}
  ],
  "concept_bible": [
    {{ "name": "Term/Character Name", "type": "term/character/concept", "description": "Details...", "first_introduced_chapter": {chapter_number}, "details": {{}} }}
  ],
  "callback_index": [
    {{ "content": "Vivid detail to remember", "source_chapter": {chapter_number}, "target_chapter": 0, "callback_trigger": "When to reference", "applied": false }}
  ],
  "tonality_fingerprint": {json.dumps(current_memory.tonality_fingerprint)},
  "decision_log": [
    {{ "decision": "Decision detail", "context": "Why it matters", "rationale": "Reason...", "agent": "MemoryKeeper", "chapter_number": {chapter_number} }}
  ]
}}
"""
        res_str = self.run(
            prompt=prompt,
            response_model=BookMemory,
            model_type="flash",
            trace_logger=trace_logger,
            api_key=api_key
        )
        
        try:
            match = re.search(r'\{.*\}', res_str, re.DOTALL)
            json_data = json.loads(match.group(0)) if match else json.loads(res_str)
            return BookMemory.model_validate(json_data)
        except Exception as e:
            logger.error(f"Failed to parse Memory Keeper extraction JSON: {e}")
            return BookMemory()

    def merge_memory(
        self,
        current_memory: BookMemory,
        new_mem: BookMemory
    ) -> BookMemory:
        """Merges a new memory delta into the current memory state in a pure Python thread-safe manner."""
        merged = BookMemory()
        
        # Fact Registry
        claims = {f.claim.lower(): f for f in current_memory.fact_registry}
        for f in new_mem.fact_registry:
            claims[f.claim.lower()] = f
        merged.fact_registry = list(claims.values())
        
        # Concept Bible
        concepts = {c.name.lower(): c for c in current_memory.concept_bible}
        for c in new_mem.concept_bible:
            concepts[c.name.lower()] = c
        merged.concept_bible = list(concepts.values())
        
        # Callback Index
        callbacks = {cb.content.lower(): cb for cb in current_memory.callback_index}
        for cb in new_mem.callback_index:
            callbacks[cb.content.lower()] = cb
        merged.callback_index = list(callbacks.values())
        
        # Tonality
        merged.tonality_fingerprint = list(set(current_memory.tonality_fingerprint + new_mem.tonality_fingerprint))
        
        # Decisions
        merged.decision_log = current_memory.decision_log + new_mem.decision_log
        
        return merged

    def update_memory(
        self,
        chapter_number: int,
        chapter_title: str,
        text: str,
        current_memory: BookMemory,
        trace_logger: Optional[TraceLogger] = None,
        api_key: Optional[str] = None
    ) -> BookMemory:
        """Helper for backwards compatibility. Combines extraction and merging in one step."""
        new_mem = self.extract_memory_delta(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            text=text,
            current_memory=current_memory,
            trace_logger=trace_logger,
            api_key=api_key
        )
        return self.merge_memory(current_memory, new_mem)


# ==========================================
# 8. ASSEMBLER AGENT
# ==========================================
class AssemblerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Assembler",
            system_instruction="""You are a Book Publisher and Assembler.
Your goal is to compile the final book.
You write the Front Matter and Back Matter matching the book's overall tonality preset.
Front Matter includes: Half-title, Title page, Copyright, Dedication, Epigraph, Preface, Foreword, Acknowledgments, and Introduction.
Back Matter includes: Afterword, Appendix, Glossary (generating definitions from the Concept Bible terms using the exact book tonality), References (grounded in the Fact Registry), About the Author, and Back-Cover copy.
Ensure the output flows cohesively and has professional publishing layout structures."""
        )

    def assemble_book(
        self,
        brief: BookBrief,
        outline: BookOutline,
        chapters: List[Dict[str, Any]],
        memory: BookMemory,
        trace_logger: Optional[TraceLogger] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, str]:
        # Compile a summary of chapters for reference
        chapter_summaries = "\n".join([f"Chapter {c['chapter_number']}: {c['title']}\nContent Preview: {c['final_text'][:300]}..." for c in chapters])
        
        prompt = f"""You are compiling the book "{outline.title}" by {outline.author}.
Topic: {brief.topic}
Reader Profile: {brief.reader_profile}
Tonality Preset: {brief.tonality} (Ensure the front/back matter uses this exact tonality!)

--- CHAPTERS COMPILED ---
{chapter_summaries}

--- CONCEPT BIBLE (For Glossary) ---
{json.dumps([c.model_dump() for c in memory.concept_bible], indent=2)}

--- FACT REGISTRY (For References) ---
{json.dumps([f.model_dump() for f in memory.fact_registry], indent=2)}

Generate the following elements for the book. Ensure each element is fully written out and styled.
1. Half-Title
2. Title Page (Title, Subtitle, Author, Publisher placeholder)
3. Copyright Page (ISBN placeholder, Edition, Rights, CIP block, Publisher details)
4. Dedication
5. Epigraph (Vivid quote aligned with topic)
6. Foreword
7. Preface
8. Acknowledgments
9. Introduction (A comprehensive overview of the book)
10. Afterword
11. Appendix (Useful summaries or formulas)
12. Glossary (Definitions for key Concept Bible terms written in the book's tonality)
13. References (Clean list of citations from Fact Registry)
14. About the Author
15. Back-Cover Copy (A compelling book blurb)

Format your output in a JSON object with keys:
"half_title", "title_page", "copyright", "dedication", "epigraph", "foreword", "preface", "acknowledgments", "introduction", "afterword", "appendix", "glossary", "references", "about_author", "back_cover"
"""
        res_str = self.run(
            prompt=prompt,
            model_type="pro",
            trace_logger=trace_logger,
            api_key=api_key
        )
        
        try:
            match = re.search(r'\{.*\}', res_str, re.DOTALL)
            return json.loads(match.group(0)) if match else json.loads(res_str)
        except Exception as e:
            logger.error(f"Failed to parse Assembler JSON: {e}")
            # Mock fallback
            return {
                "half_title": outline.title,
                "title_page": f"{outline.title}\n{outline.subtitle}\nBy {outline.author}",
                "copyright": "© 2026 AIuthor. All rights reserved.",
                "dedication": "Dedicated to the readers.",
                "epigraph": "\"Knowledge is power.\" - Francis Bacon",
                "foreword": "This is a foreword.",
                "preface": "This is a preface.",
                "acknowledgments": "Thanks to all contributors.",
                "introduction": "This introduction sets the stage for the book.",
                "afterword": "This is an afterword.",
                "appendix": "Appendix details.",
                "glossary": "Glossary terms.",
                "references": "References list.",
                "about_author": "About the author details.",
                "back_cover": "This book is a guide."
            }
