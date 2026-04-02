"""
Answer Extractor Module - Two-Pass LLM Evaluation

PASS 1: LLM generates answer with reasoning
PASS 2: LLM extracts ONLY the final answer in strict format

This module handles PASS 2 - extracting clean answers from verbose LLM responses.
"""

from typing import Dict, Any, Optional
from evaluator.llm_client import llm_client
import config
import re


# Extraction prompt templates per domain/level
# Each template instructs LLM to output ONLY the answer in specific format
EXTRACTION_PROMPTS = {
    "math": {
        "template": """Answer ONLY with the final number. No explanation, no steps, no words.

Just the number. Nothing else.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (number only):""",
        "expected_format": "number"
    },
    
    "reasoning": {
        1: {
            "template": """Answer ONLY with "ya" or "tidak". One word only. No explanation.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (ya/tidak only):""",
            "expected_format": "boolean"
        },
        
        2: {
            "template": """Answer ONLY with the sorted numbers separated by comma.

Format: number1, number2, number3, number4, number5

No explanation. Just the numbers.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (numbers only):""",
            "expected_format": "sequence"
        },
        
        3: {
            "template": """Answer ONLY with the total number. No explanation, no steps.

Just the number. Nothing else.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (number only):""",
            "expected_format": "number"
        },
        
        4: {
            "template": """Answer ONLY with the statement numbers that are correct.

Format: number, number (e.g., "2, 4")

No explanation. Just the numbers.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (statement numbers only):""",
            "expected_format": "statements"
        },
        
        5: {
            "template": """Answer ONLY with the final price in Rupiah (number only, no Rp prefix, no dots, no commas).

Just the number. Nothing else.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (number only):""",
            "expected_format": "number"
        }
    },
    
    "sql": {
        "template": """Answer ONLY with the SQL query. No explanation, no markdown.

Just the SQL statement ending with semicolon.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (SQL only):""",
        "expected_format": "sql"
    },
    
    "tool_calling": {
        "template": """Answer ONLY with the tool names separated by comma.

Format: tool1, tool2, tool3

No explanation. Just tool names.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (tool names only):""",
        "expected_format": "tools"
    },
    
    "conversation": {
        "template": """Rate this conversation response.

Answer ONLY with three numbers (0.0 to 1.0) in this exact format:
relevance,correctness,fluency

Example: 0.8,0.9,0.7

No explanation. Just three numbers.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (three numbers only):""",
        "expected_format": "rubric"
    }
}


class AnswerExtractor:
    """Extract clean final answers from LLM responses"""
    
    def __init__(self):
        self.client = llm_client
        self.enabled = getattr(config, 'TWO_PASS_ENABLED', True)
        self.temperature = getattr(config, 'TWO_PASS_TEMPERATURE', 0.0)
    
    def extract(self, domain: str, level: int, response: str) -> Dict[str, Any]:
        """
        Extract final answer using LLM with strict format instructions.
        
        Args:
            domain: Test domain (math, reasoning, sql, etc.)
            level: Test level (1-5)
            response: Raw LLM response from PASS 1
            
        Returns:
            {
                "success": bool,
                "extracted": str,           # Clean answer from PASS 2
                "expected_format": str,     # What format was expected
                "raw_pass2": str,           # Raw PASS 2 output
                "pass2_prompt": str,        # Prompt used for PASS 2
                "parse_error": Optional[str]
            }
        """
        # Check if two-pass is enabled
        if not self.enabled:
            return {
                "success": True,
                "extracted": response,
                "expected_format": "raw",
                "raw_pass2": "",
                "pass2_prompt": "",
                "parse_error": None
            }
        
        # Get extraction prompt
        prompt_data = self._get_extraction_prompt(domain, level, response)
        
        if not prompt_data:
            return {
                "success": True,
                "extracted": response,
                "expected_format": "raw",
                "raw_pass2": "",
                "pass2_prompt": "",
                "parse_error": None
            }

        prompt = prompt_data["prompt"]
        expected_format = prompt_data["expected_format"]
        
        # PASS 2: Call LLM to extract clean answer
        messages = [{"role": "user", "content": prompt}]
        
        try:
            llm_response = self.client.chat_completion(
                messages,
                temperature=self.temperature,
                tools=None
            )
            
            raw_pass2 = self.client.extract_content(llm_response).strip()
            
            # Validate the format
            validated = self._validate_format(raw_pass2, expected_format)
            
            if validated["valid"]:
                return {
                    "success": True,
                    "extracted": validated["cleaned"],
                    "expected_format": expected_format,
                    "raw_pass2": raw_pass2,
                    "pass2_prompt": prompt,
                    "parse_error": None
                }
            else:
                # LLM didn't follow format - consider as FAIL
                return {
                    "success": False,
                    "extracted": raw_pass2,
                    "expected_format": expected_format,
                    "raw_pass2": raw_pass2,
                    "pass2_prompt": prompt,
                    "parse_error": validated["error"]
                }
                
        except Exception as e:
            return {
                "success": False,
                "extracted": response,
                "expected_format": expected_format,
                "raw_pass2": "",
                "pass2_prompt": prompt,
                "parse_error": f"Extraction error: {str(e)}"
            }
    
    def _get_extraction_prompt(self, domain: str, level: int, response: str) -> Optional[Dict]:
        """Get extraction prompt and expected format for domain/level"""
        
        if domain == "reasoning":
            # Reasoning has level-specific prompts
            level_prompts = EXTRACTION_PROMPTS.get("reasoning", {})
            if level in level_prompts:
                data = level_prompts[level]
                return {
                    "prompt": data["template"].format(response=response),
                    "expected_format": data["expected_format"]
                }
        elif domain in EXTRACTION_PROMPTS:
            data = EXTRACTION_PROMPTS[domain]
            if "template" in data:
                return {
                    "prompt": data["template"].format(response=response),
                    "expected_format": data["expected_format"]
                }
        
        # No extraction prompt - return original response
        return None
    
    def _validate_format(self, raw: str, expected_format: str) -> Dict[str, Any]:
        """
        Validate that PASS 2 output follows expected format.
        
        Returns:
            {
                "valid": bool,
                "cleaned": str,    # Cleaned/normalized answer
                "error": str       # Error message if invalid
            }
        """
        
        raw = raw.strip()
        
        if expected_format == "number":
            # Should be a single number (integer or float)
            # Remove common artifacts
            cleaned = raw.replace('Rp', '').replace('rp', '').strip()
            cleaned = cleaned.replace(',', '').replace('.', '')  # Remove separators for Indonesian format
            
            # Try to extract number
            match = re.match(r'^[-+]?\d+$', cleaned)
            if match:
                return {"valid": True, "cleaned": cleaned, "error": ""}
            
            # Try float pattern
            match = re.match(r'^[-+]?\d+\.?\d*$', cleaned)
            if match:
                return {"valid": True, "cleaned": cleaned, "error": ""}
            
            # Maybe has explanation - try to extract first number
            numbers = re.findall(r'[-+]?\d+\.?\d*', cleaned)
            if numbers and len(numbers) == 1:
                return {"valid": True, "cleaned": numbers[0], "error": ""}
            
            return {"valid": False, "cleaned": raw, "error": f"Expected single number, got: {raw[:100]}"}
        
        elif expected_format == "boolean":
            # Should be "ya" or "tidak"
            lower = raw.lower().strip()
            if lower in ["ya", "tidak"]:
                return {"valid": True, "cleaned": lower, "error": ""}
            return {"valid": False, "cleaned": raw, "error": f"Expected 'ya' or 'tidak', got: {raw[:50]}"}
        
        elif expected_format == "sequence":
            # Should be: 3, 7, 15, 18, 22
            # Remove brackets if present
            cleaned = raw.replace('[', '').replace(']', '').strip()
            
            # Try to parse as comma-separated numbers
            parts = [p.strip() for p in cleaned.split(',')]
            try:
                numbers = [int(p) for p in parts if p]
                if len(numbers) >= 2:
                    return {"valid": True, "cleaned": ', '.join(map(str, numbers)), "error": ""}
            except ValueError:
                pass
            
            return {"valid": False, "cleaned": raw, "error": f"Expected number sequence, got: {raw[:100]}"}
        
        elif expected_format == "statements":
            # Should be: 2, 4 or similar
            parts = [p.strip() for p in raw.split(',')]
            try:
                numbers = [int(p) for p in parts if p]
                if numbers:
                    return {"valid": True, "cleaned": ', '.join(map(str, numbers)), "error": ""}
            except ValueError:
                pass
            return {"valid": False, "cleaned": raw, "error": f"Expected statement numbers, got: {raw[:50]}"}
        
        elif expected_format == "sql":
            # Should be SQL query
            upper = raw.upper()
            if "SELECT" in upper:
                return {"valid": True, "cleaned": raw, "error": ""}
            return {"valid": False, "cleaned": raw, "error": "Expected SQL query"}
        
        elif expected_format == "tools":
            # Should be: tool1, tool2
            parts = [p.strip() for p in raw.split(',') if p.strip()]
            if parts:
                return {"valid": True, "cleaned": ', '.join(parts), "error": ""}
            return {"valid": False, "cleaned": raw, "error": "Expected tool names"}
        
        elif expected_format == "rubric":
            # Should be: 0.8,0.9,0.7
            parts = raw.split(',')
            if len(parts) == 3:
                try:
                    scores = [float(p.strip()) for p in parts]
                    if all(0 <= s <= 1 for s in scores):
                        return {"valid": True, "cleaned": raw, "error": ""}
                except ValueError:
                    pass
            return {"valid": False, "cleaned": raw, "error": "Expected three scores (0.0-1.0)"}
        
        # Default: accept any text
        return {"valid": True, "cleaned": raw, "error": ""}


# Global extractor instance
answer_extractor = AnswerExtractor()
