# Two-Pass LLM Evaluator Implementation Plan (v2)

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Implement a two-pass LLM evaluation system where PASS 1 generates the answer with reasoning, and PASS 2 extracts ONLY the final answer in strict format for easy parsing.

**Architecture:** Simple extraction - PASS 2 prompt asks for "number only" or "text only", evaluator parses clean output. If LLM doesn't follow format = FAIL.

**Tech Stack:** Python, existing Flask app, OpenAI-compatible API

---

## Overview: How Two-Pass Works

```
┌─────────────────────────────────────────────────────────────────┐
│                      EVALUATION FLOW                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PASS 1: Answer Generation (existing flow)                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐     │
│  │   Prompt    │ -> │    LLM      │ -> │  Raw Answer     │     │
│  │ (Indonesian)│    │   Model     │    │  with reasoning │     │
│  └─────────────┘    └─────────────┘    └─────────────────┘     │
│                                                │                │
│                                                ▼                │
│  PASS 2: Extract Final Answer Only                              │
│  ┌─────────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ "Answer ONLY    │ -> │    LLM      │ -> │  Clean      │     │
│  │  with number"   │    │   Model     │    │  Number     │     │
│  └─────────────────┘    └─────────────┘    └─────────────┘     │
│                                                │                │
│                                                ▼                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  PASS 2 OUTPUT (clean, easy to parse):                  │   │
│  │                                                         │   │
│  │  36                                                     │   │
│  │  (or) 3, 7, 15, 18, 22                                  │   │
│  │  (or) ya                                                │   │
│  │  (or) 820800                                            │   │
│  │                                                         │   │
│  │  If LLM returns anything else → FAIL                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Task 1: Create Answer Extractor Module

**Objective:** Create a simple module that calls LLM to extract final answer in strict format.

**Files:**
- Create: `evaluator/answer_extractor.py`

**Step 1: Create the module**

```python
"""
Answer Extractor Module - Two-Pass LLM Evaluation

PASS 1: LLM generates answer with reasoning
PASS 2: LLM extracts ONLY the final answer in strict format
"""

from typing import Dict, Any, Optional
from evaluator.llm_client import llm_client
import config


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
        "expected_format": "number"  # Single number
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
    
    def extract(self, domain: str, level: int, response: str) -> Dict[str, Any]:
        """
        Extract final answer using LLM with strict format instructions.
        
        Returns:
            {
                "success": bool,
                "extracted": str,           # Clean answer from PASS 2
                "expected_format": str,     # What format was expected
                "raw_pass2": str,           # Raw PASS 2 output
                "parse_error": Optional[str]
            }
        """
        # Get extraction prompt
        prompt_data = self._get_extraction_prompt(domain, level, response)
        
        if not prompt_data:
            return {
                "success": False,
                "extracted": response,  # Return original
                "expected_format": "raw",
                "raw_pass2": "",
                "parse_error": "No extraction prompt for this domain/level"
            }
        
        prompt = prompt_data["prompt"]
        expected_format = prompt_data["expected_format"]
        
        # PASS 2: Call LLM to extract clean answer
        messages = [{"role": "user", "content": prompt}]
        
        try:
            llm_response = self.client.chat_completion(
                messages,
                temperature=0.0,  # Deterministic
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
                    "parse_error": None
                }
            else:
                # LLM didn't follow format - consider as FAIL
                return {
                    "success": False,
                    "extracted": raw_pass2,
                    "expected_format": expected_format,
                    "raw_pass2": raw_pass2,
                    "parse_error": validated["error"]
                }
                
        except Exception as e:
            return {
                "success": False,
                "extracted": response,
                "expected_format": expected_format,
                "raw_pass2": "",
                "parse_error": f"Extraction error: {str(e)}"
            }
    
    def _get_extraction_prompt(self, domain: str, level: int, response: str) -> Optional[Dict]:
        """Get extraction prompt and expected format"""
        
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
        
        # Generic fallback - just ask for final answer
        return {
            "prompt": f"""Answer ONLY with the final answer. No explanation.

---BEGIN ANSWER---
{response}
---END ANSWER---

Your answer (final answer only):""",
            "expected_format": "text"
        }
    
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
        import re
        
        raw = raw.strip()
        
        if expected_format == "number":
            # Should be a single number (integer or float)
            # Remove common artifacts
            cleaned = raw.replace(',', '').replace('Rp', '').replace('rp', '').strip()
            
            # Try to extract number
            match = re.match(r'^[-+]?\d*\.?\d+$', cleaned)
            if match:
                return {"valid": True, "cleaned": cleaned, "error": ""}
            
            # Maybe has explanation - try to extract first number
            numbers = re.findall(r'[-+]?\d*\.?\d+', cleaned)
            if numbers and len(numbers) == 1:
                return {"valid": True, "cleaned": numbers[0], "error": ""}
            
            return {"valid": False, "cleaned": raw, "error": f"Expected single number, got: {raw[:50]}"}
        
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
            
            return {"valid": False, "cleaned": raw, "error": f"Expected number sequence, got: {raw[:50]}"}
        
        elif expected_format == "statements":
            # Should be: 2, 4 or similar
            parts = [p.strip() for p in raw.split(',')]
            try:
                numbers = [int(p) for p in parts if p]
                return {"valid": True, "cleaned": ', '.join(map(str, numbers)), "error": ""}
            except ValueError:
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
```

---

## Task 2: Update Evaluation Engine

**Objective:** Modify `evaluator/engine.py` to use two-pass extraction.

**Files:**
- Modify: `evaluator/engine.py`

**Step 1: Add import**

At top of file, add:
```python
from evaluator.answer_extractor import answer_extractor
```

**Step 2: Update `_run_single_test` method**

Replace the scoring section (around line 172-173) with:

```python
# PASS 2: Extract clean answer
self._log(f'[PASS2] Extracting final answer...')
extraction = answer_extractor.extract(domain, level, response_content)

if extraction["success"]:
    self._log(f'[PASS2] Format: {extraction["expected_format"]}, Answer: {extraction["extracted"]}')
else:
    self._log(f'[PASS2] Format validation FAILED: {extraction["parse_error"]}')

# Score using extracted answer
scoring_result = scoring_engine.score_test(
    domain, 
    level, 
    extraction["extracted"],  # Clean answer from PASS 2
    expected
)

# Add extraction metadata to details
scoring_result["pass2"] = {
    "success": extraction["success"],
    "format": extraction["expected_format"],
    "raw_output": extraction["raw_pass2"][:200] if extraction["raw_pass2"] else ""
}

if not extraction["success"]:
    scoring_result["pass2"]["error"] = extraction["parse_error"]
```

---

## Task 3: Update Scoring Engine

**Objective:** Update scoring to handle clean extracted answers.

**Files:**
- Modify: `evaluator/scoring.py`

**Step 1: Update `score_test` to handle clean inputs**

The scoring engine now receives clean answers like "36", "ya", "3, 7, 15, 18, 22" instead of raw text with reasoning.

```python
def score_test(self, domain: str, level: int, response: str, expected: Any) -> Dict[str, Any]:
    """Score a test response - now expects clean extracted answers"""
    test_class = get_test_class(domain)
    if not test_class:
        return {
            "score": 0.0,
            "details": {"error": f"Unknown domain: {domain}"},
            "status": "failed"
        }
    
    test_instance = test_class(level)
    scoring_result = test_instance.score_response(response, expected)
    
    # Determine status based on score
    score = scoring_result.get("score", 0.0)
    status = scoring_result.get("status", "passed" if score >= 0.8 else "failed")
    
    # Build details object
    details = {
        "details": scoring_result.get("details", ""),
    }
    
    # Include any additional fields from scoring
    for key in ["breakdown", "sql_query", "columns", "row_count", "actual_result_preview",
                "relevance", "correctness", "fluency", "keywords_found",
                "actual", "expected"]:
        if key in scoring_result:
            details[key] = scoring_result[key]
    
    return {
        "score": score,
        "details": details,
        "status": status
    }
```

---

## Task 4: Update Math Test for Clean Inputs

**Objective:** Simplify math scoring since inputs are now clean numbers.

**Files:**
- Modify: `tests/math.py`

**Step 1: Simplify `score_response`**

```python
def score_response(self, response: str, expected: float) -> Dict[str, Any]:
    """
    Score response - expects clean number from PASS 2.
    
    Response should be just a number like "36" or "820800".
    If it's not a clean number, the test fails.
    """
    import re
    
    # Clean the response
    clean = response.strip().replace(',', '').replace(' ', '')
    
    # Try to parse as number
    try:
        actual = float(clean)
    except ValueError:
        # Maybe has some text - try to extract number
        numbers = re.findall(r'[-+]?\d*\.?\d+', clean)
        if not numbers:
            return {
                "score": 0.0,
                "details": f"Not a valid number: '{response}'",
                "actual": None,
                "expected": expected
            }
        actual = float(numbers[0])
    
    # Compare
    if abs(actual - expected) < 0.01:  # Small tolerance for floats
        return {
            "score": 1.0,
            "details": f"Correct: {actual}",
            "actual": actual,
            "expected": expected
        }
    else:
        return {
            "score": 0.0,
            "details": f"Wrong: expected {expected}, got {actual}",
            "actual": actual,
            "expected": expected
        }
```

---

## Task 5: Update Reasoning Test for Clean Inputs

**Objective:** Simplify reasoning scoring with clean formats.

**Files:**
- Modify: `tests/reasoning.py`

**Step 1: Simplify all level scoring**

```python
def score_response(self, response: str, expected: Any) -> Dict[str, Any]:
    """
    Score response - expects clean format from PASS 2.
    
    Level 1: "ya" or "tidak"
    Level 2: "3, 7, 15, 18, 22"
    Level 3: "17"
    Level 4: "2, 4"
    Level 5: "820800"
    """
    
    if self.level == 1:
        # Boolean - expects "ya" or "tidak"
        clean = response.strip().lower()
        expected_clean = expected.lower() if isinstance(expected, str) else str(expected).lower()
        
        if clean == expected_clean:
            return {"score": 1.0, "details": f"Correct: {clean}"}
        else:
            return {"score": 0.0, "details": f"Wrong: expected '{expected}', got '{clean}'"}
    
    elif self.level == 2:
        # Sequence - expects "3, 7, 15, 18, 22"
        try:
            numbers = [int(n.strip()) for n in response.split(',')]
            if numbers == expected:
                return {"score": 1.0, "details": f"Correct: {numbers}"}
            else:
                return {"score": 0.0, "details": f"Wrong: expected {expected}, got {numbers}"}
        except ValueError:
            return {"score": 0.0, "details": f"Invalid format: '{response}'"}
    
    elif self.level == 3:
        # Number - expects "17"
        try:
            actual = int(response.strip())
            if actual == expected:
                return {"score": 1.0, "details": f"Correct: {actual}"}
            else:
                return {"score": 0.0, "details": f"Wrong: expected {expected}, got {actual}"}
        except ValueError:
            return {"score": 0.0, "details": f"Not a number: '{response}'"}
    
    elif self.level == 4:
        # Statements - expects "2, 4"
        try:
            statements = [int(n.strip()) for n in response.split(',')]
            if 2 in statements and 4 in statements:
                return {"score": 1.0, "details": f"Correct: statements {statements}"}
            else:
                return {"score": 0.0, "details": f"Wrong: expected 2,4 in answer"}
        except ValueError:
            return {"score": 0.0, "details": f"Invalid format: '{response}'"}
    
    elif self.level == 5:
        # Currency - expects "820800"
        import re
        clean = response.strip().replace(',', '').replace('.', '')
        try:
            actual = float(clean)
            if abs(actual - expected) < 1:  # Tolerance for currency
                return {"score": 1.0, "details": f"Correct: {actual}"}
            else:
                return {"score": 0.0, "details": f"Wrong: expected {expected}, got {actual}"}
        except ValueError:
            return {"score": 0.0, "details": f"Not a number: '{response}'"}
    
    return {"score": 0.0, "details": "Unknown level"}
```

---

## Task 6: Update SQL Test

**Objective:** SQL test already returns clean-ish output, but ensure it works with extraction.

**Files:**
- Modify: `tests/sql_gen.py`

**Step 1: Ensure SQL scoring handles clean SQL**

```python
def score_response(self, response: str, expected: Any) -> Dict[str, Any]:
    """
    Score SQL response - expects clean SQL from PASS 2.
    
    Response should be just the SQL query like:
    SELECT name, salary FROM employees WHERE salary > 5000000;
    """
    import re
    
    # Clean the response
    sql = response.strip()
    
    # Remove markdown if present
    sql = re.sub(r'```sql\s*', '', sql)
    sql = re.sub(r'```\s*', '', sql)
    sql = sql.strip()
    
    # Validate it's a SELECT query
    if not sql.upper().startswith('SELECT'):
        return {"score": 0.0, "details": f"Not a SELECT query: '{sql[:50]}...'"}
    
    # Execute and compare results
    # ... existing SQL execution logic ...
```

---

## Task 7: Add Configuration

**Objective:** Add config options for two-pass.

**Files:**
- Modify: `config.py`

**Step 1: Add config**

```python
# Two-Pass Extraction Configuration
TWO_PASS_ENABLED = os.getenv("TWO_PASS_ENABLED", "1") == "1"
TWO_PASS_TEMPERATURE = float(os.getenv("TWO_PASS_TEMPERATURE", "0.0"))
```

---

## Task 8: Add Unit Tests

**Objective:** Test the extraction and validation logic.

**Files:**
- Create: `tests/test_answer_extractor.py`

**Step 1: Create tests**

```python
import pytest
from evaluator.answer_extractor import answer_extractor


class TestFormatValidation:
    """Test format validation for PASS 2 output"""
    
    def test_validate_number(self):
        """Clean number should validate"""
        result = answer_extractor._validate_format("36", "number")
        assert result["valid"] is True
        assert result["cleaned"] == "36"
    
    def test_validate_number_with_decimals(self):
        """Float number should validate"""
        result = answer_extractor._validate_format("820800.0", "number")
        assert result["valid"] is True
    
    def test_validate_number_with_text_fails(self):
        """Number with explanation should fail"""
        result = answer_extractor._validate_format("The answer is 36", "number")
        assert result["valid"] is False
    
    def test_validate_boolean_ya(self):
        """'ya' should validate"""
        result = answer_extractor._validate_format("ya", "boolean")
        assert result["valid"] is True
        assert result["cleaned"] == "ya"
    
    def test_validate_boolean_tidak(self):
        """'tidak' should validate"""
        result = answer_extractor._validate_format("tidak", "boolean")
        assert result["valid"] is True
    
    def test_validate_sequence(self):
        """Number sequence should validate"""
        result = answer_extractor._validate_format("3, 7, 15, 18, 22", "sequence")
        assert result["valid"] is True
        assert result["cleaned"] == "3, 7, 15, 18, 22"
    
    def test_validate_statements(self):
        """Statement numbers should validate"""
        result = answer_extractor._validate_format("2, 4", "statements")
        assert result["valid"] is True


class TestExtractionPrompts:
    """Test that extraction prompts are generated correctly"""
    
    def test_math_prompt(self):
        """Math extraction prompt should ask for number only"""
        prompt_data = answer_extractor._get_extraction_prompt("math", 2, "some answer")
        assert "number only" in prompt_data["prompt"].lower() or "number" in prompt_data["prompt"].lower()
        assert prompt_data["expected_format"] == "number"
    
    def test_reasoning_l1_prompt(self):
        """Reasoning L1 should ask for ya/tidak"""
        prompt_data = answer_extractor._get_extraction_prompt("reasoning", 1, "some answer")
        assert "ya" in prompt_data["prompt"].lower() or "tidak" in prompt_data["prompt"].lower()
        assert prompt_data["expected_format"] == "boolean"
    
    def test_reasoning_l2_prompt(self):
        """Reasoning L2 should ask for sequence"""
        prompt_data = answer_extractor._get_extraction_prompt("reasoning", 2, "some answer")
        assert prompt_data["expected_format"] == "sequence"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create Answer Extractor | `evaluator/answer_extractor.py` |
| 2 | Update Evaluation Engine | `evaluator/engine.py` |
| 3 | Update Scoring Engine | `evaluator/scoring.py` |
| 4 | Update Math Test | `tests/math.py` |
| 5 | Update Reasoning Test | `tests/reasoning.py` |
| 6 | Update SQL Test | `tests/sql_gen.py` |
| 7 | Add Configuration | `config.py` |
| 8 | Add Unit Tests | `tests/test_answer_extractor.py` |

---

## Example Flow

### Math Level 2: "Hitung 15% dari 240"

**PASS 1 Output:**
```
Untuk menghitung 15% dari 240:
Langkah 1: Konversi 15% ke desimal = 0.15
Langkah 2: Kalikan 0.15 x 240 = 36

Jadi, 15% dari 240 adalah 36.
```

**PASS 2 Input:**
```
Answer ONLY with the final number. No explanation, no steps, no words.
Just the number. Nothing else.

---BEGIN ANSWER---
[output from PASS 1]
---END ANSWER---

Your answer (number only):
```

**PASS 2 Output:**
```
36
```

**Evaluator:**
- Receives clean "36"
- Parses as float: 36.0
- Compares with expected: 36.0
- Score: 1.0 ✓

---

### Reasoning Level 2: Number sequence

**PASS 1 Output:**
```
Mari kita urutkan angka-angka tersebut:
- Angka: 15, 3, 22, 7, 18
- Urutan dari terkecil: 3, 7, 15, 18, 22
```

**PASS 2 Output:**
```
3, 7, 15, 18, 22
```

**Evaluator:**
- Receives clean "3, 7, 15, 18, 22"
- Parses as [3, 7, 15, 18, 22]
- Compares with expected: [3, 7, 15, 18, 22]
- Score: 1.0 ✓

---

### Reasoning Level 3: Team members (CRITICAL FIX)

**PASS 1 Output:**
```
Tim A = 5 anggota
Tim B = 5 + 3 = 8 anggota  
Tim C = 8 / 2 = 4 anggota
Total = 5 + 8 + 4 = 17 anggota
```

**PASS 2 Output:**
```
17
```

**Evaluator:**
- Receives clean "17"
- Compares with expected: 17 ✓ (NOT 19!)

---

### Reasoning Level 5: Currency calculation

**PASS 1 Output:**
```
Harga awal: Rp 1.200.000
Setelah diskon 20%: Rp 960.000
Setelah diskon tambahan 10%: Rp 864.000
Setelah diskon member 5%: Rp 820.800
```

**PASS 2 Output:**
```
820800
```

**Evaluator:**
- Receives clean "820800"
- Compares with expected: 820800.0
- Score: 1.0 ✓

---

## If LLM Doesn't Follow Format

If PASS 2 returns something like "The answer is 36" instead of just "36":

1. `_validate_format()` detects it's not clean
2. Returns `{"valid": False, "error": "Expected single number, got: The answer is 36"}`
3. Evaluator marks it as extraction failure
4. Score: 0.0 ✗

This ensures the LLM follows instructions properly.

---

Plan complete. Ready for approval.
