import os
import json
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models.schemas import TraceBundle, TraceEntry, TokenCostEntry, BookBrief
from app.config import settings

class TraceLogger:
    def __init__(self, run_id: str, brief: BookBrief):
        self.run_id = run_id
        self.brief = brief
        self.traces: List[TraceEntry] = []
        self.token_costs: List[TokenCostEntry] = []
        self.total_tokens = 0
        self.total_cost = 0.0
        self.log_filepath = os.path.join(settings.TRACES_DIR, f"{run_id}_trace.json")
        self.txt_log_filepath = os.path.join(settings.TRACES_DIR, f"{run_id}_activity.log")
        self._lock = threading.RLock()
        self._save_state()

    def log_activity(self, message: str):
        timestamp = datetime.now().isoformat()
        log_line = f"[{timestamp}] {message}\n"
        with self._lock:
            with open(self.txt_log_filepath, "a", encoding="utf-8") as f:
                f.write(log_line)
        print(log_line.strip())

    def log_trace(self, agent_name: str, step_name: str, input_data: Any, output_data: Any, trace_log: str = ""):
        entry = TraceEntry(
            agent_name=agent_name,
            step_name=step_name,
            input_data=input_data,
            output_data=output_data,
            trace_log=trace_log
        )
        with self._lock:
            self.traces.append(entry)
            self.log_activity(f"Agent {agent_name} completed step {step_name}.")
            self._save_state()

    def log_tokens(self, agent_name: str, model_name: str, prompt_tokens: int, completion_tokens: int):
        # Calculate cost based on current model rates (per 1M tokens)
        cost = 0.0
        model_lower = model_name.lower()
        if "gemini-2.5-flash" in model_lower or "gemini-1.5-flash" in model_lower:
            cost = (prompt_tokens * 0.075 / 1_000_000) + (completion_tokens * 0.30 / 1_000_000)
        elif "gemini-2.5-pro" in model_lower or "gemini-1.5-pro" in model_lower:
            cost = (prompt_tokens * 1.25 / 1_000_000) + (completion_tokens * 5.00 / 1_000_000)
        elif "gpt-4o-mini" in model_lower:
            cost = (prompt_tokens * 0.150 / 1_000_000) + (completion_tokens * 0.600 / 1_000_000)
        elif "gpt-4o" in model_lower:
            cost = (prompt_tokens * 5.00 / 1_000_000) + (completion_tokens * 15.00 / 1_000_000)
        else:
            # Fallback estimation
            cost = (prompt_tokens * 0.50 / 1_000_000) + (completion_tokens * 1.50 / 1_000_000)

        entry = TokenCostEntry(
            agent_name=agent_name,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost
        )
        with self._lock:
            self.token_costs.append(entry)
            self.total_tokens += (prompt_tokens + completion_tokens)
            self.total_cost += cost
            self.log_activity(f"Usage [Agent: {agent_name}, Model: {model_name}]: {prompt_tokens} prompt tokens, {completion_tokens} completion tokens (Est. Cost: ${cost:.6f})")
            self._save_state()

    def get_bundle(self) -> TraceBundle:
        with self._lock:
            return TraceBundle(
                run_id=self.run_id,
                brief=self.brief,
                traces=self.traces,
                token_cost=self.token_costs,
                total_tokens=self.total_tokens,
                total_cost=round(self.total_cost, 6)
            )

    def _save_state(self):
        bundle = self.get_bundle()
        try:
            with open(self.log_filepath, "w", encoding="utf-8") as f:
                f.write(bundle.model_dump_json(indent=2))
        except Exception as e:
            print(f"Error saving trace state: {e}")

    @classmethod
    def load_trace(cls, run_id: str) -> Optional[Dict[str, Any]]:
        path = os.path.join(settings.TRACES_DIR, f"{run_id}_trace.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None
