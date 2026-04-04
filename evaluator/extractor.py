"""
Multi-Layer Answer Extractor

Provides robust answer extraction with multiple fallback layers:
1. LLM extraction (primary)
2. Regex patterns (fallback)
3. Domain heuristics (last resort)
"""

import re
import json
from typing import Any, Optional, Tuple, List
from evaluator.llm_client import llm_client


class AnswerExtractor:
    """Multi-layer answer extraction with fallbacks"""
    
    # Regex patterns for number extraction (ordered by priority)
    NUMBER_PATTERNS = [
        # LaTeX boxed: \boxed{10} or \boxed{10}
        (r'\\boxed\{(\d+(?:\.\d+)?)\}', 'latex_boxed'),
        # Answer is X patterns
        (r'(?:answer|hasil|jawaban)\s*(?:is|nya|ialah|adalah)[:\s]*(\d+(?:\.\d+)?)', 'answer_is'),
        # Equals at end: = 10 or =10
        (r'=\s*(\d+(?:\.\d+)?)\s*[.\s]*$', 'equals_end'),
        # Indonesian: adalah 10
        (r'(?:adalah|ialah)\s+(\d+(?:\.\d+)?)', 'adalah'),
        # Colon pattern: Result: 10
        (r':\s*(\d+(?:\.\d+)?)\s*[.\s]*$', 'colon'),
    ]
    
    def __init__(self):
        self.extraction_prompts = {
            'number': self._get_number_prompt(),
            'text': self._get_text_prompt(),
            'json': self._get_json_prompt(),
        }
    
    def extract(self, 
                response: str, 
                format_type: str = 'number',
                domain: str = 'general',
                original_question: str = '',
                use_llm: bool = True) -> Tuple[Any, str]:
        """
        Extract answer from response using multi-layer approach.
        
        Args:
            response: The LLM response to extract from
            format_type: 'number', 'text', or 'json'
            domain: Domain for heuristics (math, sql, etc.)
            original_question: Original question for context
            use_llm: Whether to use LLM extraction (Layer 1)
        
        Returns:
            Tuple of (extracted_value, method_used)
            method_used: 'llm' | 'regex_{pattern_name}' | 'heuristic'
        """
        # Layer 1: LLM Extraction
        if use_llm:
            try:
                extracted = self._llm_extract(response, format_type, original_question)
                if extracted is not None:
                    validated = self._validate_format(extracted, format_type)
                    if validated is not None:
                        return validated, 'llm'
            except Exception as e:
                print(f"[EXTRACTOR] LLM extraction failed: {e}")
        
        # Layer 2: Regex Fallback
        if format_type == 'number':
            extracted, method = self._regex_extract_number(response)
            if extracted is not None:
                return extracted, method
        
        # Layer 3: Domain-specific heuristics
        extracted, method = self._heuristic_extract(response, format_type, domain)
        if extracted is not None:
            return extracted, method
        
        # Nothing worked
        return None, 'failed'
    
    def _llm_extract(self, response: str, format_type: str, question: str = '') -> Optional[str]:
        """Use LLM to extract answer from response."""
        prompt_template = self.extraction_prompts.get(format_type, self.extraction_prompts['text'])
        
        prompt = prompt_template.format(
            question=question,
            response=response
        )
        
        messages = [{"role": "user", "content": prompt}]
        llm_response = llm_client.chat_completion(messages, temperature=0.0)
        
        if llm_response.get("success"):
            content = llm_client.extract_content(llm_response)
            # Strip thinking tags if present
            content, _ = self._strip_thinking(content)
            return content.strip()
        
        return None
    
    def _regex_extract_number(self, response: str) -> Tuple[Optional[float], str]:
        """Extract number using regex patterns."""
        for pattern, method_name in self.NUMBER_PATTERNS:
            match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    value = float(match.group(1))
                    return value, f'regex_{method_name}'
                except (ValueError, IndexError):
                    continue
        
        # Last resort: find last number in response
        all_numbers = re.findall(r'\d+(?:\.\d+)?', response)
        if all_numbers:
            try:
                return float(all_numbers[-1]), 'regex_last_number'
            except ValueError:
                pass
        
        return None, 'regex_failed'
    
    def _heuristic_extract(self, response: str, format_type: str, domain: str) -> Tuple[Any, str]:
        """Domain-specific heuristic extraction."""
        
        if domain == 'math' and format_type == 'number':
            # For math, last number is often the answer
            all_numbers = re.findall(r'\d+(?:\.\d+)?', response)
            if all_numbers:
                # Filter out likely non-answer numbers (like equation coefficients)
                # Usually the answer is the last or second-to-last number
                for num in reversed(all_numbers[-3:]):
                    try:
                        return float(num), 'heuristic_math'
                    except ValueError:
                        continue
        
        elif domain == 'sql':
            # Extract SQL query
            sql_match = re.search(r'(SELECT\s+.*?(?:;|$))', response, re.IGNORECASE | re.DOTALL)
            if sql_match:
                return sql_match.group(1).strip(), 'heuristic_sql'
        
        elif domain == 'tool_calling':
            # Try to extract JSON tool calls
            try:
                # Find JSON in response
                json_match = re.search(r'\{[^{}]*\}', response)
                if json_match:
                    return json.loads(json_match.group(0)), 'heuristic_json'
            except json.JSONDecodeError:
                pass
        
        # For text format, return the whole response (stripped)
        if format_type == 'text':
            cleaned = response.strip()
            if cleaned:
                return cleaned, 'heuristic_text'
        
        return None, 'heuristic_failed'
    
    def _validate_format(self, value: Any, format_type: str) -> Any:
        """Validate extracted value matches expected format."""
        if value is None:
            return None
        
        if format_type == 'number':
            # Try to convert to float
            try:
                if isinstance(value, str):
                    # Remove any non-numeric characters except decimal point and minus
                    cleaned = re.sub(r'[^\d.\-]', '', value)
                    if cleaned:
                        return float(cleaned)
                else:
                    return float(value)
            except (ValueError, TypeError):
                return None
        
        elif format_type == 'json':
            # Try to parse as JSON
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return None
            return value
        
        elif format_type == 'text':
            # Just return as string
            return str(value).strip() if value else None
        
        return value
    
    def _strip_thinking(self, content: str) -> Tuple[str, Optional[str]]:
        """Strip thinking tags from content with auto-format detection."""
        if not content:
            return content, None
        
        # Import here to avoid circular imports
        from evaluator.gemma4_parser import is_gemma4_format, strip_gemma4_thinking
        
        # Auto-detect Gemma 4 format
        if is_gemma4_format(content):
            return strip_gemma4_thinking(content)
        
        # Standard format: <think>...</think>
        pattern = r'<think>(.*?)</think>'
        matches = re.findall(pattern, content, re.DOTALL)
        cleaned = re.sub(pattern, '', content, flags=re.DOTALL).strip()
        thinking = '\n'.join(matches) if matches else None
        
        return cleaned, thinking
    
    def _get_number_prompt(self) -> str:
        """Get prompt for number extraction."""
        return """Extract the final numeric answer from the AI response.

RULES:
1. Output ONLY the number (no text, no explanation)
2. Remove any formatting (LaTeX, boxes, etc.)
3. If multiple numbers, output the final answer
4. Use decimal point for decimals (e.g., 3.14 not 3,14)

---ORIGINAL QUESTION---
{question}
---END QUESTION---

---BEGIN RESPONSE---
{response}
---END RESPONSE---

Extracted number:"""
    
    def _get_text_prompt(self) -> str:
        """Get prompt for text extraction."""
        return """Extract the final answer from the AI response.

RULES:
1. Output ONLY the answer text
2. No explanations, no reasoning
3. Keep the exact wording of the answer

---ORIGINAL QUESTION---
{question}
---END QUESTION---

---BEGIN RESPONSE---
{response}
---END RESPONSE---

Extracted answer:"""
    
    def _get_json_prompt(self) -> str:
        """Get prompt for JSON extraction."""
        return """Extract the JSON data from the AI response.

RULES:
1. Output ONLY valid JSON
2. No markdown code blocks
3. No explanations

---BEGIN RESPONSE---
{response}
---END RESPONSE---

Extracted JSON:"""


# Global extractor instance
answer_extractor = AnswerExtractor()
