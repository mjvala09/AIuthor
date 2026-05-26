import logging
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel
from app.services.llm_service import llm_service
from app.utils.trace_logger import TraceLogger

logger = logging.getLogger("base_agent")

class BaseAgent:
    def __init__(self, name: str, system_instruction: str):
        self.name = name
        self.system_instruction = system_instruction

    def run(
        self,
        prompt: str,
        response_model: Optional[Type[BaseModel]] = None,
        model_type: str = "flash",  # "pro" or "flash"
        provider: Optional[str] = None,
        temperature: float = 0.7,
        trace_logger: Optional[TraceLogger] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> str:
        """Executes the agent's core LLM logic, tracking traces and usage."""
        if trace_logger:
            trace_logger.log_activity(f"Agent {self.name} started execution.")
            
        try:
            output = llm_service.generate_text(
                prompt=prompt,
                system_instruction=self.system_instruction,
                model_type=model_type,
                provider=provider,
                temperature=temperature,
                response_model=response_model,
                trace_logger=trace_logger,
                agent_name=self.name,
                api_key=api_key
            )
            
            # Log trace details
            if trace_logger:
                trace_logger.log_trace(
                    agent_name=self.name,
                    step_name="generate_content",
                    input_data={"prompt": prompt, "model_type": model_type, "provider": provider},
                    output_data=output
                )
                
            return output
            
        except Exception as e:
            logger.error(f"Error executing agent {self.name}: {e}")
            if trace_logger:
                trace_logger.log_activity(f"Agent {self.name} failed with error: {str(e)}")
                trace_logger.log_trace(
                    agent_name=self.name,
                    step_name="generate_content_failed",
                    input_data={"prompt": prompt},
                    output_data=f"ERROR: {str(e)}"
                )
            raise e
