"""
Two-Pass Evaluator

PASS 1: LLM generates answer with reasoning
PASS 2: LLM extracts ONLY the final answer in strict format

Used for: math, reasoning domains
"""

from typing import Any, Dict
from .base import BaseEvaluator, EvaluationResult
from evaluator.answer_extractor import answer_extractor
from tests import get_test_class


class TwoPassEvaluator(BaseEvaluator):
    """
    Two-pass evaluation for domains that need clean answer extraction.
    
    Used for: math, reasoning
    """
    
    def __init__(self, domain: str):
        self.domain = domain
        self.extractor = answer_extractor
    
    @property
    def name(self) -> str:
        return f"two_pass_{self.domain}"
    
    @property
    def uses_pass2(self) -> bool:
        return True
    
    def evaluate(self, response: str, expected: Any, level: int) -> EvaluationResult:
        """
        Evaluate using two-pass extraction.
        
        1. Extract clean answer via PASS2
        2. Score the clean answer using domain-specific test class
        """
        # PASS 2: Extract clean answer
        extraction = self.extractor.extract(self.domain, level, response)
        
        if not extraction["success"]:
            return EvaluationResult(
                score=0.0,
                status="failed",
                details={
                    "error": extraction.get("parse_error", "Extraction failed"),
                    "raw_output": extraction.get("raw_pass2", ""),
                    "input_response": response[:500] if len(response) > 500 else response,
                    "pass2": {
                        "success": False,
                        "format": extraction.get("expected_format"),
                        "raw_output": extraction.get("raw_pass2", ""),
                        "prompt": extraction.get("pass2_prompt", ""),
                        "error": extraction.get("parse_error"),
                        "extracted_attempt": extraction.get("extracted", "")
                    }
                },
                extracted_answer=extraction.get("extracted"),
                pass2_used=True
            )
        
        # Score the extracted answer using domain test class
        extracted = extraction["extracted"]
        
        test_class = get_test_class(self.domain)
        if test_class:
            test_instance = test_class(level)
            score_result = test_instance.score_response(extracted, expected)
        else:
            score_result = {"score": 0.0, "details": f"Unknown domain: {self.domain}"}
        
        # Determine status
        score = score_result.get("score", 0.0)
        status = score_result.get("status", "passed" if score >= 0.8 else "failed")
        
        # Build details
        details = score_result.get("details", {})
        if isinstance(details, str):
            details = {"details": details}
        
        # Add PASS2 metadata
        details["pass2"] = {
            "success": True,
            "format": extraction["expected_format"],
            "raw_output": extraction.get("raw_pass2", ""),
            "prompt": extraction.get("pass2_prompt", ""),
            "input_response": response[:500] if len(response) > 500 else response,
            "extracted_answer": extracted
        }
        
        return EvaluationResult(
            score=score,
            status=status,
            details=details,
            extracted_answer=extracted,
            pass2_used=True
        )
