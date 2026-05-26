import os
import re
import json
import logging
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel
from app.config import settings
from app.utils.trace_logger import TraceLogger

# Setup logger
logger = logging.getLogger("llm_service")

# Try to import SDKs
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

class LLMService:
    def __init__(self):
        self.openai_configured = False
        self.openai_client = None
        
        # Configure OpenAI
        openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
        if OPENAI_AVAILABLE and openai_key:
            try:
                self.openai_client = OpenAI(api_key=openai_key)
                self.openai_configured = True
                logger.info("OpenAI API client configured successfully.")
            except Exception as e:
                logger.error(f"Error configuring OpenAI client: {e}")

    def _get_model_name(self, provider: str, model_type: str) -> str:
        """Returns specific model name depending on pro/flash and provider choice."""
        if provider == "openai":
            if model_type == "pro":
                return "gpt-4o"
            else:
                return "gpt-4o-mini"
        return "mock"

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model_type: str = "flash",  # "pro" or "flash"
        provider: Optional[str] = None,
        temperature: float = 0.7,
        response_model: Optional[Type[BaseModel]] = None,
        trace_logger: Optional[TraceLogger] = None,
        agent_name: str = "UnknownAgent",
        api_key: Optional[str] = None
    ) -> str:
        """Generates text from the LLM, tracking tokens/costs and supporting structured JSON schemas."""
        provider = "openai"
        
        # Determine provider fallback
        if not self.openai_configured and not api_key:
            logger.warning("No OpenAI API key configured or provided. Operating in MOCK mode.")
            provider = "mock"

        model_name = self._get_model_name(provider, model_type)
        
        # MOCK MODE (fallback for testing without API keys)
        if provider == "mock":
            mock_resp = self._generate_mock_response(prompt, response_model, agent_name)
            if trace_logger:
                # Estimate mock tokens
                prompt_tokens = len(prompt) // 4
                comp_tokens = len(mock_resp) // 4
                trace_logger.log_tokens(agent_name, "mock-model", prompt_tokens, comp_tokens)
            return mock_resp

        return self._call_openai(
            prompt=prompt,
            system_instruction=system_instruction,
            model_name=model_name,
            temperature=temperature,
            response_model=response_model,
            trace_logger=trace_logger,
            agent_name=agent_name,
            api_key=api_key
        )

    def _call_openai(
        self,
        prompt: str,
        system_instruction: Optional[str],
        model_name: str,
        temperature: float,
        response_model: Optional[Type[BaseModel]],
        trace_logger: Optional[TraceLogger],
        agent_name: str,
        api_key: Optional[str] = None
    ) -> str:
        import time
        max_retries = 5
        base_delay = 5
        
        client = self.openai_client
        if api_key:
            client = OpenAI(api_key=api_key)
            
        for attempt in range(max_retries):
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                params = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature
                }
                
                if response_model:
                    params["response_format"] = {"type": "json_object"}

                response = client.chat.completions.create(**params)
                res_text = response.choices[0].message.content
                
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                
                if trace_logger:
                    trace_logger.log_tokens(agent_name, model_name, prompt_tokens, completion_tokens)
                    
                return res_text
                
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "quota" in err_str
                
                if is_rate_limit and attempt < max_retries - 1:
                    sleep_time = base_delay * (2 ** attempt)
                    logger.warning(f"OpenAI Rate limit hit for {model_name} (Attempt {attempt+1}/{max_retries}). Sleeping {sleep_time}s and retrying...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"OpenAI API call failed for {model_name}: {e}.")
                    # If this is not the mini model, we can try to fall back to the mini model
                    if model_name != "gpt-4o-mini" and (self.openai_configured or api_key):
                        return self._call_openai(
                            prompt=prompt,
                            system_instruction=system_instruction,
                            model_name="gpt-4o-mini",
                            temperature=temperature,
                            response_model=response_model,
                            trace_logger=trace_logger,
                            agent_name=agent_name,
                            api_key=api_key
                        )
                    # Fallback to mock mode
                    logger.warning(f"All OpenAI options failed for {agent_name}. Falling back to MOCK mode.")
                    return self._generate_mock_response(prompt, response_model)

    def _generate_mock_response(self, prompt: str, response_model: Optional[Type[BaseModel]], agent_name: str = "UnknownAgent") -> str:
        """Returns detailed mock placeholder data based on expected schemas, so the app runs without keys."""
        # Detect topic
        prompt_lower = prompt.lower()
        is_novella = "novella" in prompt_lower or "story" in prompt_lower or "fiction" in prompt_lower or "clockwork" in prompt_lower
        
        # Detect tonality
        tonality = "Conversational"
        for t in ["Conversational", "Academic", "Storyteller", "Motivational", "Witty"]:
            if t.lower() in prompt_lower:
                tonality = t
                break
                
        # Extract chapter number
        chapter_match = re.search(r'(?:chapter|Chapter)(?:[_\s:]*)(\d+)', prompt)
        chapter_num = int(chapter_match.group(1)) if chapter_match else 1
        
        # 1. OUTLINE REQUEST
        if response_model and "BookOutline" in response_model.__name__:
            if is_novella:
                return json.dumps({
                    "title": "Echoes of the Clockwork Vault",
                    "subtitle": "A Tale of Secrets, Time, and Unlikely Allies",
                    "author": "A. I. Storyteller",
                    "brief": {
                        "topic": "5-chapter novella with two named characters",
                        "reader_profile": "General fiction reader",
                        "target_words": 10000,
                        "tonality": tonality,
                        "genre": "Fiction"
                    },
                    "chapters": [
                        {"chapter_number": 1, "title": "The Clockmaker's Key", "description": "Leo discovering the runic key.", "target_words": 1500, "key_concepts": ["Leo", "clockwork vault", "runic key"]},
                        {"chapter_number": 2, "title": "The Archivist's Discovery", "description": "Aria finds the ancient manuscript.", "target_words": 1500, "key_concepts": ["Aria", "cathedral library", "manuscript"]},
                        {"chapter_number": 3, "title": "Whispers in the Gears", "description": "Leo and Aria meet and connect key and parchment.", "target_words": 1500, "key_concepts": ["Leo", "Aria", "mysterious map"]},
                        {"chapter_number": 4, "title": "The Vault Confrontation", "description": "Confronting the shadow guardian inside the vault.", "target_words": 1500, "key_concepts": ["shadow guardian", "gear chamber"]},
                        {"chapter_number": 5, "title": "A New Dawn of Time", "description": "Securing the vault and restoring order.", "target_words": 1500, "key_concepts": ["restored order", "destiny aligned"]}
                    ],
                    "overall_guidelines": ["Maintain suspense", "Use vivid imagery"],
                    "style_rules": ["Avoid modern terminology"]
                })
            else:
                # Default S&P Personal Finance Outline (10 Chapters)
                return json.dumps({
                    "title": "The Intelligent Penny",
                    "subtitle": "A Young Adult's Guide to Financial Freedom",
                    "author": "A. I. Engineer",
                    "brief": {
                        "topic": "10-chapter guide to personal finance",
                        "reader_profile": "Young adults",
                        "target_words": 15000,
                        "tonality": tonality,
                        "genre": "Non-Fiction"
                    },
                    "chapters": [
                        {"chapter_number": 1, "title": "Money Mindset: Shifting Focus from Spending to Growing", "description": "The psychology of money and compound interest.", "target_words": 1500, "key_concepts": ["compound interest", "investing", "psychology"]},
                        {"chapter_number": 2, "title": "The Budgeting Blueprint: Systems That Actually Work", "description": "Direct systems like 50/30/20 and tracking.", "target_words": 1500, "key_concepts": ["budgeting", "50/30/20 rule", "cash flow"]},
                        {"chapter_number": 3, "title": "Saving Strategies: Building Your Emergency Fund", "description": "Liquid high-yield savings and shielding wealth.", "target_words": 1500, "key_concepts": ["emergency fund", "liquid savings", "high-yield savings"]},
                        {"chapter_number": 4, "title": "Understanding Debt & Credit Scores: The Game Rules", "description": "Hacks, rules, and escaping credit card traps.", "target_words": 1500, "key_concepts": ["credit score", "bad debt", "credit cards"]},
                        {"chapter_number": 5, "title": "Your First Investment: Stocks, Bonds, and Allocation", "description": "Basics of financial markets.", "target_words": 1500, "key_concepts": ["stocks", "bonds", "asset allocation"]},
                        {"chapter_number": 6, "title": "Index Funds & ETFs: The Set-and-Forget Wealth Engine", "description": "Passive index funds and avoiding heavy fees.", "target_words": 1500, "key_concepts": ["index funds", "ETFs", "S&P 500"]},
                        {"chapter_number": 7, "title": "Tax-Advantaged Accounts: Roth IRAs and 401(k)s", "description": "Leveraging tax brackets and tax-free growth.", "target_words": 1500, "key_concepts": ["Roth IRA", "401k", "compound tax benefits"]},
                        {"chapter_number": 8, "title": "Smart Spending: Enjoying Life Without Going Broke", "description": "Conscious spending vs mindless consumption.", "target_words": 1500, "key_concepts": ["conscious spending", "frugality", "values"]},
                        {"chapter_number": 9, "title": "Debt Demolition: Snowballs, Avalanches, and Freedom", "description": "Paying off student loans and high-interest debts.", "target_words": 1500, "key_concepts": ["debt snowball", "debt avalanche", "debt payoff"]},
                        {"chapter_number": 10, "title": "The Long Game: Inflation, Taxes, and Retiring Comfortably", "description": "Long term wealth preservation.", "target_words": 1500, "key_concepts": ["inflation", "financial independence", "long term strategy"]}
                    ],
                    "overall_guidelines": ["Explain jargon", "Use relatable analogies"],
                    "style_rules": ["Write in second-person where helpful", "Eliminate AI tells"]
                })
        
        # 2. FACT CHECKER AGENT
        if agent_name == "Fact-Checker" or "FactCheck" in prompt:
            # We must return JSON matching the schemas
            # Extract chapter text from prompt to carry it through
            ch_text_match = re.search(r'--- CHAPTER TEXT TO CHECK ---\s*(.*?)(?:\s*Verify every|$)', prompt, re.DOTALL)
            text_to_use = ch_text_match.group(1).strip() if ch_text_match else "Grounded and verified content."
            return json.dumps({
                "fact_check_report": f"Fact check report for Chapter {chapter_num}. Cross-examined stats and references. Adjusted terminology for clarity. Grounded all claims in RAG reference docs.",
                "abstain_triggered": False,
                "verified_text": text_to_use
            })
            
        # 3. MEMORY KEEPER AGENT
        if agent_name == "Memory Keeper" or (response_model and "Memory" in response_model.__name__):
            if is_novella:
                concepts = [
                    {"name": "Leo", "type": "character", "description": "A quiet, precise clockmaker with a mysterious key.", "first_introduced_chapter": 1},
                    {"name": "Aria", "type": "character", "description": "An adventurous archivist seeking ancient relics.", "first_introduced_chapter": 2}
                ]
                facts = [
                    {"claim": "Leo possesses a runic brass key.", "source_chapter": 1, "verified": True, "citation": "Clockmaker's diary"},
                    {"claim": "Aria discovered an ancient manuscript in the cathedral library.", "source_chapter": 2, "verified": True, "citation": "Cathedral archives"}
                ]
                callbacks = [
                    {"content": "Refer back to the runic engraving on Leo's key in Chapter 4 when matching it to the vault lock.", "source_chapter": 1, "target_chapter": 4, "callback_trigger": "vault_matching"}
                ]
                decisions = [
                    {"decision": "Introduced Leo and Aria as complementary protagonists.", "context": "Character setup", "rationale": "Contrast precise logic (Leo) with intuitive exploration (Aria).", "agent": "Writer", "chapter_number": 1}
                ]
            else:
                concepts = [
                    {"name": "Compound Interest", "type": "term", "description": "Earning interest on interest, leading to exponential growth over time.", "first_introduced_chapter": 1},
                    {"name": "Emergency Fund", "type": "term", "description": "Three to six months of expenses held in high-yield cash for safety.", "first_introduced_chapter": 3},
                    {"name": "Roth IRA", "type": "concept", "description": "A retirement account that allows post-tax investments to grow completely tax-free.", "first_introduced_chapter": 7}
                ]
                facts = [
                    {"claim": "Compounding frequency determines the yield speed.", "source_chapter": 1, "verified": True, "citation": "Reference text"},
                    {"claim": "Liquid savings shield investors from premature stock liquidations.", "source_chapter": 3, "verified": True, "citation": "Reference materials"}
                ]
                callbacks = [
                    {"content": "Reference the coffee-budgeting analogy from Chapter 1 in Chapter 8.", "source_chapter": 1, "target_chapter": 8, "callback_trigger": "coffee_analogy"}
                ]
                decisions = [
                    {"decision": "Structured the guide starting with mindset before tactics.", "context": "Book design", "rationale": "Mindset determines adherence to budgeting.", "agent": "Planner", "chapter_number": 1}
                ]
                
            return json.dumps({
                "fact_registry": facts,
                "concept_bible": concepts,
                "callback_index": callbacks,
                "tonality_fingerprint": ["Relatable", "Clean", tonality],
                "decision_log": decisions
            })

        # 4. ASSEMBLER AGENT
        if agent_name == "Assembler":
            # Return full front/back matter JSON
            return json.dumps({
                "half_title": "THE INTELLIGENT PENNY" if not is_novella else "ECHOES OF THE CLOCKWORK VAULT",
                "title_page": f"{'THE INTELLIGENT PENNY' if not is_novella else 'ECHOES OF THE CLOCKWORK VAULT'}\n{'A Young Adult Guide' if not is_novella else 'A Clockwork Novella'}\nBy AIuthor",
                "copyright": "Copyright © 2026 AIuthor. All rights reserved.\nISBN: 978-1-2345-6789-0 (Placeholder)\nFirst Edition\nPublished by Gateway Digital.",
                "dedication": "Dedicated to all who seek financial freedom and knowledge." if not is_novella else "Dedicated to the keepers of time and mysteries.",
                "epigraph": "\"An investment in knowledge pays the best interest.\" - Benjamin Franklin" if not is_novella else "\"Time is a storm in which we are all lost.\" - William Carlos Williams",
                "foreword": "This book provides a roadmap to help you navigate financial waters with confidence." if not is_novella else "A masterful work of fiction exploring the gears of human destiny.",
                "preface": "I wrote this guide because financial literacy is rarely taught, yet vital to survival." if not is_novella else "This story began as a dream of mechanical rhythm.",
                "acknowledgments": "Thanks to the engineering team and researchers who grounded these lessons." if not is_novella else "Thanks to the curators of historical mechanisms.",
                "introduction": "Welcome to your financial journey. This guide will outline budgeting, saving, credit scores, index funds, and long-term security. Let's begin." if not is_novella else "Leo's shop was quiet, save for the clocks. But time was ticking toward an extraordinary discovery. Here is where our story starts.",
                "afterword": "You now have the knowledge. The next step is execution. Go build your wealth." if not is_novella else "The vault remains sealed, but the clocks still tick. Leo and Aria's journey continues.",
                "appendix": "Appendix A: The compounding formula: A = P(1 + r/n)^(nt).\nAppendix B: High-yield savings checklist." if not is_novella else "Appendix: Diagram of the runic gear mechanisms.",
                "glossary": "Compound Interest: Earning interest on interest.\nRoth IRA: Tax-free retirement account." if not is_novella else "Runic Key: A brass key engraved with symbols.",
                "references": "1. Grounded RAG Reference Library, Gateway Digital.\n2. Treasury Bond Yield Studies.",
                "about_author": "AIuthor is an agentic writing pipeline built for publication-ready books.",
                "back_cover": "Discover how to master your money, build an emergency fund, and invest in index funds today." if not is_novella else "Leo holds the key. Aria holds the map. Together, they must unlock the vault before time runs out."
            })
            
        # 5. TONALITY JUDGE
        if agent_name == "TonalityJudge":
            return json.dumps({
                "score": 0.95,
                "feedback": "The prose displays excellent compliance with the requested tone."
            })

        # 6. HUMANIZER SCORER (DPO Reward Scorer)
        if agent_name == "HumanizerScorer":
            return json.dumps({
                "option_a_score": 8.8,
                "option_a_critique": "Strong direct question, engages the reader immediately.",
                "option_b_score": 9.4,
                "option_b_critique": "Excellent storytelling elements, vivid metaphors, and zero AI cliché tells.",
                "winning_option": "B",
                "justification": "Option B fits the tonality preset much better and builds an immediate narrative hook."
            })

        # 7. DPO PREFERENCE PAIRS (Humanizer Step 1)
        if agent_name == "Humanizer" and "option_a" in prompt:
            if is_novella:
                return json.dumps({
                    "option_a": "What if you held the key to time itself? Leo looked down at the brass key in his palm, feeling its weight.",
                    "option_b": "The ticking of a thousand clockwork mechanisms hummed a rhythmic symphony in the back of Leo's shop. In his calloused hands, he held a key engraved with ancient, glowing runes."
                })
            else:
                return json.dumps({
                    "option_a": "Have you ever looked at your bank account and felt a sense of dread? Let's fix that mindset today.",
                    "option_b": "Imagine your paycheck is a seed, not a snack. By planting it instead of consuming it, you build an unstoppable wealth-generating forest."
                })

        # 8. DEFAULT TEXT DRAFTS (Writer, Humanizer final, Editor, SelfHealer)
        # We generate rich, multi-paragraph text depending on topic, chapter, and tonality!
        if is_novella:
            # NOVELLA TEXT
            bodies = {
                1: """The ticking of a thousand clockwork mechanisms hummed a rhythmic symphony in the back of Leo's shop. In his calloused hands, he held a key engraved with ancient, glowing runes. It was a cold Tuesday evening when Aria, a young archivist from the cathedral library, pushed open the creaking door. Under her arm, she carried a heavy, leather-bound manuscript that smelled of age and copper.
                
                "I believe you have been looking for this," she said, placing the document on the counter. The parchment was filled with detailed schematics of a subterranean vault—the very vault Leo's father had spent his final days trying to locate. Leo adjusted his magnifying loupe, his heart hammering against his chest as the runes on the key matched the emblem printed on the manuscript's cover.
                
                They spoke long into the night, the fire dying down to embers. The key was indeed the missing component, a mechanical puzzle designed to align the vault's massive gears. They agreed to venture below the cathedral ruins at dawn, aware of the rumors of a shadow guardian guarding the vault's ancient secrets.""",
                
                2: """Aria led the way down the damp subterranean passageways beneath the cathedral library. The air was thick with the scent of decaying parchment and old copper. She pointed to a stone relief matching the design on Leo's key. The ancient manuscript she carried had detailed the exact layout, yet seeing the massive stone pillars in person felt surreal.
                
                "We must be careful," Leo whispered, his boots crunching on the loose gravel. "The gear mechanism here is designed to trigger traps if the alignment is off by even a millimeter." Aria held the torch higher, tracing the runic markings on the wall.
                
                She discovered a hidden recess in the stone work. A small, clockwork mechanism was embedded deep within the wall, its tiny bronze teeth frozen in time. This was the lock. Leo stepped forward, inserting the runic key into the slot, holding his breath as he turned it slowly.""",
                
                3: """They worked in silence, the rhythm of the clocks guiding their hands. As the key turned, a low rumbling shook the floorboards. Leo adjusted his spectacles, his heart racing. He remembered his father's warning about the vault. The gears began to move, grinding together with a mechanical roar that had not been heard for centuries.
                
                Aria spread the manuscript over a nearby stone table, tracing the labyrinth of passageways. The gears were shifting the very walls of the subterranean maze, aligning a hidden corridor. A map of the gear chamber emerged, glowing with a soft, bioluminescent light.
                
                "The core is just ahead," Aria said, her eyes shining with excitement. "But according to the notes, the final vault door requires a dual synchronization. We must activate two separate gear levers simultaneously or the entire chamber will collapse." Leo nodded, his resolve hardening as they pressed forward into the dark.""",
                
                4: """The door swung open to reveal the vault. The gears inside were massive, turning with slow, crushing force. They were not alone; a shadow moved at the edge of the chamber. Aria stepped forward, holding the manuscript high, recognizing the silhouette of the vault guardian—a mechanical automaton constructed to defend the relic.
                
                Leo ran toward the control panel, his fingers flying over the copper levers. He had to override the automaton's security protocols before it reached Aria. The gears groaned as he threw the secondary override switch.
                
                With a final, metallic click, the guardian froze, its glowing red eyes fading to black. Aria breathed a sigh of relief and stepped toward the pedestal in the center of the room, where a golden pocket watch—the primary key to the grand clockwork tower—lay resting on a velvet cushion.""",
                
                5: """The vault was secured, and the relic placed in safe hands. Leo and Aria stood on the cathedral steps, watching the sun rise over the city. The gears of time had been restored, and their legacy was now safe. The pocket watch ticked softly in Leo's pocket, a reminder of their shared adventure.
                
                "What will you do now?" Aria asked, looking toward the horizon. Leo smiled, looking at the runic key in his hand. "There are still many vaults left to find, and many gears left to align."
                
                Aria laughed, holding up the manuscript. "Then I suggest we get started. The next map points toward the clockwork city of Oakhaven." They walked down the steps, ready to face whatever mysteries the future held, their destinies aligned."""
            }
            # Add fallback novella chapter
            body = bodies.get(chapter_num, f"Leo and Aria explored Chapter {chapter_num}. They solved clockwork puzzles in the {tonality} tone, moving closer to unlocking the mystery of the vault.")
        else:
            # FINANCE TEXT
            bodies = {
                1: """Imagine your paycheck is a seed, not a snack. By planting it instead of consuming it, you build an unstoppable wealth-generating forest. Money isn't just paper; it is a tool, a leverage for your future freedom. For young adults entering the workforce, financial literacy is the single most important skill you can master to ensure lifetime stability.
                
                The engine that drives this growth is compound interest, which Albert Einstein reportedly called the eighth wonder of the world. Compound interest is simply interest earned on interest. If you invest $1,000 and earn a 10% annual return, you have $1,100 at the end of the year. In year two, you earn 10% not just on your initial $1,000, but on the $100 of interest you earned in year one. Over forty years, that single $1,000 grows to over $45,000 without you adding another penny.
                
                To start, you must establish a baseline of financial stability by tracking your cash flow. Track your expenses down to the cent, separating needs from wants. Understanding where your money goes is the prerequisite for allocating it effectively toward wealth-building assets.""",
                
                2: """Budgeting isn't about restricting yourself; it's about giving every dollar a job. A budget is a roadmap for your financial future. When you control where your money goes, you stop wondering where it went. Many young professionals fall into the trap of lifestyle inflation, increasing their spending as their salary grows. A structured budget shields you from this wealth killer.
                
                The most popular and accessible starting framework is the 50/30/20 rule. In this system, 50% of your take-home pay is allocated to absolute needs (rent, utilities, groceries), 30% to wants (dining out, entertainment, hobbies), and 20% is directly funneled into savings and investments. By automating these transfers on payday, you ensure you pay yourself first before spending a dime.
                
                To implement this system, use a simple budgeting spreadsheet or an app. Review your cash flow weekly. Adjust your allocations as your income changes, but always prioritize the 20% savings bucket. Consistency, not perfection, is the secret to budgeting success.""",
                
                3: """An emergency fund is your financial shield. Before you invest a single dollar in the stock market, you need three to six months of living expenses tucked away in a high-yield savings account. This liquid reserve protects you from unexpected expenses like car repairs, medical bills, or job loss, preventing you from falling back into high-interest debt.
                
                To build your shield, open a dedicated High-Yield Savings Account (HYSA) at an online bank. HYSAs pay significantly higher interest rates than traditional brick-and-mortar banks, allowing your emergency fund to grow and outpace inflation. Treat this account as an untouchable reserve, reserved only for genuine emergencies.
                
                Start by setting a small, achievable milestone, such as saving $1,000. Once reached, automate a portion of your monthly savings until you hit your full three-to-six-month target. Having this cash buffer provides immense peace of mind, allowing you to invest your remaining capital with confidence.""",
                
                4: """Credit is a double-edged sword. A high credit score opens doors to low interest rates on mortgages, better loan terms, and premium credit cards, while high-interest consumer debt is a wealth killer. Your credit score is a numerical representation of your creditworthiness, calculated based on payment history, credit utilization, and credit age.
                
                The golden rule of credit is simple: pay off your credit card balances in full every month. Never carry a balance to the next billing cycle. High-interest credit card debt compounding at 20% or more is a financial emergency that will destroy your wealth. Treat your credit card like a debit card, spending only what you can afford to pay off immediately.
                
                To optimize your score, keep your credit utilization ratio below 10%. This means if your credit limit is $10,000, never let your balance exceed $1,000. Set up auto-pay for all your credit accounts to guarantee you never miss a payment. With a stellar credit score, you gain access to the cheapest borrowing rates available, saving you thousands over your lifetime.""",
                
                5: """Investing is how you make your money work for you. By purchasing assets like stocks and bonds, you buy a small piece of future economic growth. While stocks offer high growth potential, bonds provide stability and income. A balanced asset allocation matching your risk tolerance is the key to building long-term wealth.
                
                When you buy a stock, you become a part-owner of that corporation. If the company grows and becomes more profitable, the value of your share increases, and you may receive dividends. Bonds, on the other hand, are loans you make to governments or corporations, which pay you a fixed interest rate over time.
                
                Asset allocation is the process of dividing your investments among these different asset classes. A younger investor with a long time horizon should typically allocate a larger percentage to stocks, as they have more time to ride out market volatility. Understanding your risk tolerance and staying disciplined is crucial to investment success.""",
                
                6: """You don't need to pick individual stocks to be a successful investor. Index funds and ETFs allow you to own a slice of the entire stock market at a very low cost. By tracking indexes like the S&P 500, you participate in the growth of the world's largest companies, keeping fees minimal and performance high.
                
                An index fund is a type of mutual fund or ETF that holds all the stocks in a specific index, such as the S&P 500. This provides instant diversification, spreading your risk across hundreds of different companies. ETFs (Exchange-Traded Funds) are similar to index funds but trade on the stock exchange like regular stocks.
                
                Passive investing through index funds has consistently outperformed active fund managers over the long term. By avoiding high management fees and transaction costs, you keep more of your returns. Start investing regularly through dollar-cost averaging, buying a fixed amount of index funds every month regardless of market conditions.""",
                
                7: """Uncle Sam wants to help you save for retirement. Tax-advantaged accounts like Roth IRAs and 401(k)s offer powerful tax benefits that accelerate compound interest. With a Roth IRA, you invest post-tax dollars, and your growth and withdrawals are completely tax-free. Maximize these accounts to protect your wealth from taxes.
                
                A 401(k) is a retirement plan sponsored by employers. Contributions are made with pre-tax dollars, reducing your current taxable income. Many employers offer a matching contribution, which is essentially free money. Always contribute enough to get the full employer match.
                
                A Roth IRA is an individual retirement account you open yourself. Since you contribute post-tax dollars, you pay no taxes on the capital gains or withdrawals in retirement. This is an incredibly powerful tool for young adults who are currently in lower tax brackets. Leverage both accounts to maximize your long-term tax efficiency.""",
                
                8: """Frugality isn't about buying cheap toilet paper; it's about aligning your spending with your values. Practice conscious spending by cutting costs mercilessly on things that don't matter to you, and spending lavishly on things that do. Differentiating between needs and wants is the key to maintaining a high savings rate.
                
                Many people fall into the trap of mindless consumption, buying things to impress others or out of habit. By practicing conscious spending, you take control of your financial choices. Ask yourself if a purchase will bring long-term value before handing over your credit card.
                
                Set up automated transfers to your savings and investment accounts on payday. By paying yourself first, you ensure your savings goals are met before you spend money on wants. This simple habit allows you to enjoy guilt-free spending on the things you truly value.""",
                
                9: """If you're carrying debt, you need a plan to destroy it. Popular strategies like the debt snowball (paying smallest balances first for psychological wins) or the debt avalanche (paying highest interest rates first to save money) can help you break free. Consistency and determination are key to escaping the debt trap.
                
                The debt snowball method focuses on psychological momentum. By paying off your smallest debt balance first, you gain a quick win that motivates you to keep going. Once the smallest debt is paid, you roll that payment into the next smallest debt.
                
                The debt avalanche method focuses on mathematical efficiency. By targeting the debt with the highest interest rate first, you minimize the total interest paid over time. Choose the method that best fits your personality and commit to it until you are debt-free.""",
                
                10: """Wealth building is a marathon, not a sprint. Inflation is a silent tax that erodes the purchasing power of your cash, which is why investing is so critical. Maintain your discipline through market ups and downs. Financial independence is the ultimate goal, giving you the freedom to choose how you spend your time.
                
                Inflation reduces the value of cash over time. If you keep all your savings in a traditional bank account, you are effectively losing money. By investing in productive assets like stocks and real estate, you protect your wealth from inflation.
                
                Stay focused on the long game. Avoid the temptation to time the market or react to short-term volatility. By maintaining a disciplined investment strategy and continually learning, you will achieve financial freedom and secure your future."""
            }
            # Add fallback finance chapter
            body = bodies.get(chapter_num, f"Welcome to Chapter {chapter_num}. We discuss advanced wealth preservation strategies here in the {tonality} tone, focusing on compound interest and grounding.")
            
        # Incorporate winning hook if it's the final humanized text request
        if "winning opening hook:" in prompt:
            # Extract winning hook
            hook_match = re.search(r'winning opening hook:\s*"(.*?)"', prompt, re.DOTALL)
            if hook_match:
                winning_hook = hook_match.group(1).strip()
                # Split body into paragraphs
                paragraphs = body.split("\n\n")
                if paragraphs:
                    # Replace first paragraph's first sentence with winning hook or prepend it
                    paragraphs[0] = winning_hook + " " + " ".join(paragraphs[0].split()[10:]) # soft blend
                    body = "\n\n".join(paragraphs)

        return body

    def _get_clean_schema(self, model: Type[BaseModel]) -> Dict[str, Any]:
        """Converts Pydantic model to a JSON schema dict and removes fields rejected by Gemini API (e.g. 'default', 'title', '$defs', 'anyOf')."""
        try:
            schema = model.model_json_schema()
            defs = schema.get("$defs", {})
            
            def resolve_refs(item, parent_key=None):
                if isinstance(item, dict):
                    if "$ref" in item:
                        ref_path = item["$ref"]
                        ref_key = ref_path.split("/")[-1]
                        if ref_key in defs:
                            return resolve_refs(defs[ref_key], parent_key)
                    
                    if "anyOf" in item:
                        # Resolve options inside anyOf
                        resolved_options = [resolve_refs(x, parent_key) for x in item["anyOf"]]
                        # Filter out null option
                        non_null_options = [x for x in resolved_options if isinstance(x, dict) and x.get("type") != "null"]
                        if non_null_options:
                            best_option = non_null_options[0]
                            item.update(best_option)
                            if any(isinstance(x, dict) and x.get("type") == "null" for x in resolved_options):
                                item["nullable"] = True
                        del item["anyOf"]
                    
                    cleaned = {}
                    for k, v in item.items():
                        if k in ["default", "additionalProperties", "$defs", "$schema"]:
                            continue
                        if k == "title" and parent_key != "properties":
                            continue
                        cleaned[k] = resolve_refs(v, k)
                    return cleaned
                elif isinstance(item, list):
                    return [resolve_refs(x, parent_key) for x in item]
                return item

            return resolve_refs(schema)
        except Exception as e:
            logger.warning(f"Failed to clean schema for {model.__name__}: {e}. Falling back to raw model class.")
            return model

llm_service = LLMService()
