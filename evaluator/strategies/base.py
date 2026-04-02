"""
Base Evaluator Interface

All domain-specific evaluators must implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class EvaluationResult:
    """Standard result from any evaluator"""
    score: float
    status: str  # 'passed', 'failed', 'partial'
    details: Dict[str, Any]
    extracted_answer: Optional[str] = None
    pass2_used: bool = False


class BaseEvaluator(ABC):
    """
    Abstract base class for domain-specific evaluators.
    
    Each evaluator implements its own evaluation logic:
    - TwoPassEvaluator: Uses LLM to extract clean answer
    - KeywordEvaluator: Uses keyword/regex matching
    - SQLExecutorEvaluator: TwoPass + SQL execution
    - ToolCallEvaluator: TwoPass + tool validation
    """
    
    @abstractmethod
    def evaluate(self, response: str, expected: Any, level: int, prompt: str = "") -> EvaluationResult:
        """
        Evaluate the LLM response against expected output.
        
        Args:
            response: Raw LLM response from PASS 1
            expected: Expected output or validation criteria
            level: Test level (1-5)
            prompt: Original question/prompt for context (used by PASS2)
            
        Returns:
            EvaluationResult with score, status, and details
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the evaluator name for logging"""
        pass
    
    @property
    def uses_pass2(self) -> bool:
        """Whether this evaluator uses PASS2 LLM call"""
        return False
    
    def log_prefix(self) -> str:
        """Return log prefix for this evaluator"""
        return f"[{self.name.upper()}]"
