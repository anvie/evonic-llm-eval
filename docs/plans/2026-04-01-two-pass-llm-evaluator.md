# Two-Pass LLM Evaluator Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Implement a two-pass LLM evaluation system where the first pass generates the answer, and the second pass extracts/formats the answer in a strict, parseable format.

**Architecture:** 
- Add a new `answer_extractor` module that uses LLM to extract structured answers
- Each domain test gets a specific extraction prompt template
- Strict JSON output format for easy parsing
- Fallback to regex extraction if LLM extraction fails

**Tech Stack:** Python, existing Flask app, OpenAI-compatible API, JSON schema

---

## Overview: How Two-Pass Works

```
┌─────────────────────────────────────────────────────────────────┐
│                      EVALUATION FLOW                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PASS 1: Answer Generation                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Prompt    │ -> │    LLM      │ -> │  Raw Answer │         │
│  │ (Indonesian)│    │   Model     │    │   (text)    │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                │                │
│                                                ▼                │
│  PASS 2: Answer Extraction                                     │
│  ┌─────────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Extraction      │ -> │    LLM      │ -> │  Structured │     │
│  │ Prompt Template │    │   Model     │    │   JSON      │     │
│  └─────────────────┘    └─────────────┘    └─────────────┘     │
│                                                │                │
│                                                ▼                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  {                                                      │   │
│  │    "answer_type": "number",                             │   │
│  │    "answer_value": 36,                                  │   │
│  │    "confidence": "high",                                │   │
│  │    "reasoning": "15% of 240 equals 36"                   │   │
│  │  }                                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Task 1: Create Answer Extractor Module

**Objective:** Create a new module that handles the second-pass LLM call to extract structured answers.

**Files:**
- Create: `evaluator/answer_extractor.py`

**Step 1: Create the module with extraction logic**

```python
"""
Answer Extractor Module - Two-Pass LLM Evaluation

This module handles the second pass of evaluation, extracting structured
answers from raw LLM responses using another LLM call with strict formatting.
"""

import json
import time
from typing import Dict, Any, Optional
from evaluator.llm_client import llm_client
import config


# Extraction prompt templates per domain/level
EXTRACTION_PROMPTS = {
    "math": {
        "template": """Dari jawaban berikut, ekstrak jawaban numerik final.

JAWABAN:
{response}

INSTRUKSI:
1. Identifikasi jawaban numerik final dari teks di atas
2. Jika ada mata uang (Rp), konversi ke angka biasa (tanpa Rp, tanpa titik pemisah ribuan)
3. Jika ada persentase, berikan angka desimal atau hasil perhitungan

JAWABAN DALAM FORMAT JSON:
{{
  "answer_type": "number",
  "answer_value": <ANGKA_FINAL>,
  "confidence": "high" | "medium" | "low",
  "reasoning": "<penjelasan singkat>"
}}

PENTING: Jawab HANYA dengan JSON valid, tanpa markdown code block.""",
    },
    
    "reasoning": {
        1: """Dari jawaban berikut, tentukan apakah kesimpulan logisnya benar.

JAWABAN:
{response}

PERTANYAAN ASLI: "Jika hari ini hujan, maka saya akan membawa payung. Hari ini hujan. Apakah saya akan membawa payung?"

INSTRUKSI:
Ekstrak jawaban final: "ya" atau "tidak"

JSON:
{{
  "answer_type": "boolean",
  "answer_value": "ya" | "tidak",
  "confidence": "high" | "medium" | "low"
}}

PENTING: Jawab HANYA dengan JSON valid.""",

        2: """Dari jawaban berikut, ekstrak urutan angka yang benar.

JAWABAN:
{response}

PERTANYAAN ASLI: "Urutkan angka berikut dari terkecil ke terbesar: 15, 3, 22, 7, 18"

INSTRUKSI:
Berikan urutan final sebagai array angka dalam JSON.

JSON:
{{
  "answer_type": "array",
  "answer_value": [angka1, angka2, angka3, angka4, angka5],
  "confidence": "high" | "medium" | "low"
}}

PENTING: Jawab HANYA dengan JSON valid.""",

        3: """Dari jawaban berikut, ekstrak total anggota.

JAWABAN:
{response}

PERTANYAAN ASLI:
- Tim A memiliki 5 anggota
- Tim B memiliki 3 anggota lebih banyak dari Tim A
- Tim C memiliki setengah anggota Tim B

INSTRUKSI:
Hitung: Tim A = 5, Tim B = 5+3 = 8, Tim C = 8/2 = 4
Total = 5 + 8 + 4 = 17

JSON:
{{
  "answer_type": "number",
  "answer_value": <TOTAL_ANGGOTA>,
  "confidence": "high" | "medium" | "low",
  "calculation": "Tim A = X, Tim B = Y, Tim C = Z, Total = X+Y+Z"
}}

PENTING: Jawab HANYA dengan JSON valid.""",

        4: """Dari jawaban berikut, identifikasi pernyataan yang benar.

JAWABAN:
{response}

PERTANYAAN ASLI:
1. Semua burung bisa terbang
2. Beberapa burung bisa terbang
3. Tidak ada burung yang bisa terbang
4. Penguin adalah burung yang tidak bisa terbang

INSTRUKSI:
Identifikasi nomor pernyataan yang BENAR.

JSON:
{{
  "answer_type": "statements",
  "answer_value": [nomor_pernyataan_yang_benar],
  "confidence": "high" | "medium" | "low"
}}

PENTING: Jawab HANYA dengan JSON valid.""",

        5: """Dari jawaban berikut, ekstrak harga final yang harus dibayar.

JAWABAN:
{response}

PERTANYAAN ASLI:
- Diskon 20% untuk pembelian di atas Rp 500.000
- Diskon tambahan 10% untuk pembelian di atas Rp 1.000.000
- Diskon tambahan 5% untuk member loyal
- Harga awal: Rp 1.200.000

INSTRUKSI:
Hitung: 1.200.000 x 0.8 x 0.9 x 0.95 = 820.800

JSON:
{{
  "answer_type": "currency",
  "answer_value": <ANGKA_TANPA_FORMAT>,
  "confidence": "high" | "medium" | "low"
}}

PENTING: Jawab HANYA dengan JSON valid."""
    },
    
    "sql": {
        "template": """Dari jawaban berikut, ekstrak query SQL yang dihasilkan.

JAWABAN:
{response}

INSTRUKSI:
Berikan SQL query final dalam format JSON.

JSON:
{{
  "answer_type": "sql",
  "answer_value": "<QUERY_SQL>",
  "confidence": "high" | "medium" | "low"
}}

PENTING: Jawab HANYA dengan JSON valid."""
    },
    
    "tool_calling": {
        "template": """Dari jawaban berikut, ekstrak tool calls yang dipanggil.

JAWABAN:
{response}

INSTRUKSI:
Berikan daftar tool yang dipanggil dalam format JSON.

JSON:
{{
  "answer_type": "tools",
  "answer_value": ["tool_name_1", "tool_name_2"],
  "confidence": "high" | "medium" | "low"
}}

PENTING: Jawab HANYA dengan JSON valid."""
    },
    
    "conversation": {
        "template": """Dari jawaban berikut, berikan skor kualitas.

JAWABAN:
{response}

INSTRUKSI:
Nilai jawaban berdasarkan:
- relevance: apakah menjawab pertanyaan (0.0-1.0)
- correctness: apakah informasi benar (0.0-1.0)
- fluency: apakah bahasa Indonesia baik (0.0-1.0)

JSON:
{{
  "answer_type": "rubric",
  "relevance": <score>,
  "correctness": <score>,
  "fluency": <score>,
  "confidence": "high" | "medium" | "low"
}}

PENTING: Jawab HANYA dengan JSON valid."""
    }
}


class AnswerExtractor:
    """Extract structured answers from raw LLM responses"""
    
    def __init__(self):
        self.client = llm_client
    
    def extract(self, domain: str, level: int, response: str) -> Dict[str, Any]:
        """
        Extract structured answer from raw response.
        
        Returns:
            {
                "success": bool,
                "answer_type": str,
                "answer_value": Any,
                "confidence": str,
                "reasoning": str,
                "raw_extraction": str,
                "parse_error": Optional[str]
            }
        """
        # Get extraction prompt
        prompt = self._get_extraction_prompt(domain, level, response)
        
        if not prompt:
            return self._fallback_extraction(domain, level, response)
        
        # Call LLM for extraction
        messages = [{"role": "user", "content": prompt}]
        
        try:
            llm_response = self.client.chat_completion(
                messages, 
                temperature=0.0,  # Deterministic for extraction
                tools=None
            )
            
            raw_content = self.client.extract_content(llm_response)
            
            # Parse JSON from response
            parsed = self._parse_json_response(raw_content)
            
            if parsed.get("success"):
                return {
                    "success": True,
                    "answer_type": parsed.get("answer_type", "unknown"),
                    "answer_value": parsed.get("answer_value"),
                    "confidence": parsed.get("confidence", "medium"),
                    "reasoning": parsed.get("reasoning", ""),
                    "raw_extraction": raw_content,
                    "parse_error": None
                }
            else:
                # JSON parse failed, try fallback
                return self._fallback_extraction(domain, level, response)
                
        except Exception as e:
            return {
                "success": False,
                "answer_type": "error",
                "answer_value": None,
                "confidence": "low",
                "reasoning": f"Extraction error: {str(e)}",
                "raw_extraction": "",
                "parse_error": str(e)
            }
    
    def _get_extraction_prompt(self, domain: str, level: int, response: str) -> str:
        """Get the appropriate extraction prompt for domain/level"""
        
        if domain == "reasoning":
            # Reasoning has level-specific prompts
            prompts = EXTRACTION_PROMPTS.get("reasoning", {})
            template = prompts.get(level)
            if template:
                return template.format(response=response)
        elif domain in EXTRACTION_PROMPTS:
            template = EXTRACTION_PROMPTS[domain].get("template")
            if template:
                return template.format(response=response)
        
        # Generic fallback prompt
        return self._get_generic_prompt(response)
    
    def _get_generic_prompt(self, response: str) -> str:
        """Generic extraction prompt for unknown domains"""
        return f"""Dari jawaban berikut, ekstrak informasi penting.

JAWABAN:
{response}

INSTRUKSI:
Ekstrak jawaban utama dari teks di atas.

JSON:
{{
  "answer_type": "text" | "number" | "array",
  "answer_value": <jawaban>,
  "confidence": "high" | "medium" | "low"
}}

PENTING: Jawab HANYA dengan JSON valid."""
    
    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling various formats"""
        
        # Strip whitespace
        raw = raw.strip()
        
        # Try direct parse first
        try:
            return {"success": True, **json.loads(raw)}
        except json.JSONDecodeError:
            pass
        
        # Try extracting from markdown code block
        import re
        code_block = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
        if code_block:
            try:
                return {"success": True, **json.loads(code_block.group(1).strip())}
            except json.JSONDecodeError:
                pass
        
        # Try finding JSON object in text
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            try:
                return {"success": True, **json.loads(json_match.group(0))}
            except json.JSONDecodeError:
                pass
        
        return {
            "success": False,
            "error": "Could not parse JSON from response",
            "raw": raw
        }
    
    def _fallback_extraction(self, domain: str, level: int, response: str) -> Dict[str, Any]:
        """Fallback to regex-based extraction if LLM extraction fails"""
        
        import re
        
        # Domain-specific fallback extraction
        if domain == "math":
            return self._fallback_math(response)
        elif domain == "reasoning":
            return self._fallback_reasoning(level, response)
        elif domain == "sql":
            return self._fallback_sql(response)
        
        # Generic fallback - return raw text
        return {
            "success": False,
            "answer_type": "raw",
            "answer_value": response,
            "confidence": "low",
            "reasoning": "Used regex fallback",
            "raw_extraction": "",
            "parse_error": "No LLM extraction available"
        }
    
    def _fallback_math(self, response: str) -> Dict[str, Any]:
        """Regex fallback for math extraction"""
        import re
        
        # Handle Indonesian format (dots as thousand separators)
        text = re.sub(r'\b(\d{1,3}(?:\.\d{3})+)\b', 
                      lambda m: m.group(0).replace('.', ''), response)
        
        # Look for currency
        rp_match = re.search(r'rp\s*([\d,]+)', text, re.IGNORECASE)
        if rp_match:
            num = rp_match.group(1).replace(',', '')
            try:
                return {
                    "success": True,
                    "answer_type": "currency",
                    "answer_value": float(num),
                    "confidence": "medium",
                    "reasoning": "Extracted via regex (currency)",
                    "raw_extraction": "",
                    "parse_error": None
                }
            except ValueError:
                pass
        
        # Look for last number
        numbers = re.findall(r'[-+]?\d*\.?\d+', text)
        if numbers:
            try:
                return {
                    "success": True,
                    "answer_type": "number",
                    "answer_value": float(numbers[-1]),
                    "confidence": "low",
                    "reasoning": "Extracted via regex (last number)",
                    "raw_extraction": "",
                    "parse_error": None
                }
            except ValueError:
                pass
        
        return {
            "success": False,
            "answer_type": "raw",
            "answer_value": response,
            "confidence": "low",
            "reasoning": "No number found in response",
            "raw_extraction": "",
            "parse_error": "No numeric value found"
        }
    
    def _fallback_reasoning(self, level: int, response: str) -> Dict[str, Any]:
        """Regex fallback for reasoning extraction"""
        import re
        
        if level == 1:
            # Boolean answer
            if "ya" in response.lower():
                return {
                    "success": True,
                    "answer_type": "boolean",
                    "answer_value": "ya",
                    "confidence": "medium",
                    "reasoning": "Regex fallback",
                    "raw_extraction": "",
                    "parse_error": None
                }
        elif level == 2:
            # Number sequence
            numbers = [int(n) for n in re.findall(r'\b\d+\b', response)]
            unique_sorted = sorted(set(numbers))
            if len(unique_sorted) >= 5:
                return {
                    "success": True,
                    "answer_type": "array",
                    "answer_value": unique_sorted[:5],
                    "confidence": "low",
                    "reasoning": "Regex fallback (sorted unique)",
                    "raw_extraction": "",
                    "parse_error": None
                }
        elif level in [3, 5]:
            # Number extraction
            return self._fallback_math(response)
        
        return {
            "success": False,
            "answer_type": "raw",
            "answer_value": response,
            "confidence": "low",
            "reasoning": "No pattern matched",
            "raw_extraction": "",
            "parse_error": "Regex fallback failed"
        }
    
    def _fallback_sql(self, response: str) -> Dict[str, Any]:
        """Regex fallback for SQL extraction"""
        import re
        
        # Find SQL-like content
        sql_match = re.search(r'SELECT\s+[\s\S]+?;', response, re.IGNORECASE)
        if sql_match:
            return {
                "success": True,
                "answer_type": "sql",
                "answer_value": sql_match.group(0),
                "confidence": "medium",
                "reasoning": "Regex fallback (SELECT statement)",
                "raw_extraction": "",
                "parse_error": None
            }
        
        return {
            "success": False,
            "answer_type": "raw",
            "answer_value": response,
            "confidence": "low",
            "reasoning": "No SQL found",
            "raw_extraction": "",
            "parse_error": "No SQL statement found"
        }


# Global extractor instance
answer_extractor = AnswerExtractor()
```

---

## Task 2: Update Evaluation Engine to Use Two-Pass

**Objective:** Modify `evaluator/engine.py` to call the answer extractor after getting LLM response.

**Files:**
- Modify: `evaluator/engine.py:112-211` (the `_run_single_test` method)

**Step 1: Add import for answer_extractor**

Add at the top of `evaluator/engine.py`:

```python
from evaluator.answer_extractor import answer_extractor
```

**Step 2: Update `_run_single_test` method**

Replace the scoring section (around line 172-173) with:

```python
# Score the response
self._log(f'[SCORING] Evaluating response...')

# PASS 2: Extract structured answer using LLM
extraction_result = answer_extractor.extract(domain, level, response_content)
self._log(f'[EXTRACT] Type: {extraction_result.get("answer_type")}, Value: {extraction_result.get("answer_value")}')

# Use extracted value for scoring
if extraction_result.get("success"):
    extracted_value = extraction_result.get("answer_value")
    scoring_result = scoring_engine.score_test(domain, level, extracted_value, expected)
    scoring_result["extraction"] = {
        "method": "llm",
        "confidence": extraction_result.get("confidence"),
        "raw_extraction": extraction_result.get("raw_extraction", "")[:200]
    }
else:
    # Fallback to original response if extraction failed
    scoring_result = scoring_engine.score_test(domain, level, response_content, expected)
    scoring_result["extraction"] = {
        "method": "fallback",
        "reason": extraction_result.get("parse_error", "Unknown error")
    }
```

---

## Task 3: Update Scoring Engine to Handle Extracted Values

**Objective:** Modify scoring engine to accept pre-extracted values.

**Files:**
- Modify: `evaluator/scoring.py`

**Step 1: Update `score_test` method signature**

Change from:
```python
def score_test(self, domain: str, level: int, response: str, expected: Any) -> Dict[str, Any]:
```

To:
```python
def score_test(self, domain: str, level: int, response: Any, expected: Any) -> Dict[str, Any]:
```

**Step 2: Update test classes to handle both string and pre-extracted values**

In each test class (`tests/math.py`, `tests/reasoning.py`, etc.), update `score_response` to check if the response is already extracted:

```python
def score_response(self, response: Any, expected: Any) -> Dict[str, Any]:
    # If response is already extracted (from two-pass), use directly
    if isinstance(response, (int, float, list, dict)):
        return self._score_extracted(response, expected)
    
    # Otherwise, use legacy string parsing
    return self._score_from_string(response, expected)
```

---

## Task 4: Update Math Test Class

**Objective:** Update math tests to handle extracted numeric values.

**Files:**
- Modify: `tests/math.py`

**Step 1: Refactor `score_response` method**

```python
def score_response(self, response: Any, expected: float) -> Dict[str, Any]:
    """Score response - handles both extracted values and raw strings"""
    
    # Handle pre-extracted numeric value (from two-pass)
    if isinstance(response, (int, float)):
        actual = float(response)
        return self._compare_values(actual, expected)
    
    # Handle dict from extraction (contains answer_value)
    if isinstance(response, dict) and "answer_value" in response:
        actual = float(response["answer_value"])
        return self._compare_values(actual, expected)
    
    # Legacy: extract from raw string
    actual = self._extract_number(str(response))
    if actual is None:
        return {
            "score": 0.0,
            "details": "No numeric answer found",
            "actual": None,
            "expected": expected
        }
    
    return self._compare_values(actual, expected)

def _compare_values(self, actual: float, expected: float) -> Dict[str, Any]:
    """Compare actual vs expected values"""
    if abs(actual - expected) < 0.001:
        return {
            "score": 1.0,
            "details": "Exact match",
            "actual": actual,
            "expected": expected
        }
    else:
        return {
            "score": 0.0,
            "details": f"Mismatch: expected {expected}, got {actual}",
            "actual": actual,
            "expected": expected
        }
```

---

## Task 5: Update Reasoning Test Class

**Objective:** Update reasoning tests to handle extracted values.

**Files:**
- Modify: `tests/reasoning.py`

**Step 1: Refactor `score_response` for each level**

```python
def score_response(self, response: Any, expected: Any) -> Dict[str, Any]:
    """Score response - handles both extracted values and raw strings"""
    
    # Handle pre-extracted values (from two-pass)
    if isinstance(response, dict):
        return self._score_extracted(self.level, response, expected)
    
    # Handle pre-extracted list/number directly
    if isinstance(response, (list, int, float)):
        return self._score_extracted_direct(self.level, response, expected)
    
    # Legacy: extract from raw string
    return self._score_from_string(self.level, str(response), expected)

def _score_extracted(self, level: int, extracted: dict, expected: Any) -> Dict[str, Any]:
    """Score pre-extracted JSON response"""
    
    answer_type = extracted.get("answer_type", "unknown")
    answer_value = extracted.get("answer_value")
    
    if level == 1:
        # Boolean logic
        if answer_value and "ya" in str(answer_value).lower():
            return {"score": 1.0, "details": "Correct logical conclusion"}
        return {"score": 0.0, "details": "Incorrect logical conclusion"}
    
    elif level == 2:
        # Number sequence
        if isinstance(answer_value, list) and answer_value == expected:
            return {"score": 1.0, "details": "Correct number sequence"}
        return {"score": 0.0, "details": f"Incorrect sequence: got {answer_value}"}
    
    elif level == 3:
        # Arithmetic - total members
        if isinstance(answer_value, (int, float)) and answer_value == expected:
            return {"score": 1.0, "details": "Correct arithmetic reasoning"}
        return {"score": 0.0, "details": f"Expected {expected}, got {answer_value}"}
    
    elif level == 4:
        # Logical deduction
        if isinstance(answer_value, list):
            if 2 in answer_value and 4 in answer_value:
                return {"score": 1.0, "details": "Correct logical deduction"}
        return {"score": 0.0, "details": "Incorrect logical deduction"}
    
    elif level == 5:
        # Multi-step calculation
        if isinstance(answer_value, (int, float)):
            if abs(answer_value - expected) < 0.01:
                return {"score": 1.0, "details": "Correct multi-step calculation"}
        return {"score": 0.0, "details": f"Expected {expected}, got {answer_value}"}
    
    return {"score": 0.0, "details": "Unknown level"}

def _score_extracted_direct(self, level: int, value: Any, expected: Any) -> Dict[str, Any]:
    """Score directly extracted value (not in dict)"""
    
    if level in [1, 4]:
        return self._score_extracted(level, {"answer_value": value}, expected)
    elif level in [2, 3, 5]:
        return self._score_extracted(level, {"answer_value": value}, expected)
    
    return {"score": 0.0, "details": "Unknown level"}
```

---

## Task 6: Add Tests for Two-Pass Extraction

**Objective:** Create unit tests for the answer extractor.

**Files:**
- Create: `tests/test_answer_extractor.py`

**Step 1: Create test file**

```python
import pytest
from evaluator.answer_extractor import answer_extractor


class TestMathExtraction:
    """Test math answer extraction"""
    
    def test_extract_percentage_calculation(self):
        """Test: 15% of 240 = 36"""
        response = "Untuk menghitung 15% dari 240:\n15/100 x 240 = 36\nJadi, 15% dari 240 adalah 36."
        result = answer_extractor.extract("math", 2, response)
        
        assert result["success"] is True
        assert result["answer_type"] == "number"
        assert result["answer_value"] == 36
    
    def test_extract_currency_with_dots(self):
        """Test: Rp 820.800 extraction"""
        response = "Harga final yang harus dibayar adalah Rp 820.800"
        result = answer_extractor.extract("math", 5, response)
        
        assert result["success"] is True
        assert abs(result["answer_value"] - 820800) < 1


class TestReasoningExtraction:
    """Test reasoning answer extraction"""
    
    def test_extract_number_sequence(self):
        """Test: Sorted sequence extraction"""
        response = "Urutan dari terkecil ke terbesar: 3, 7, 15, 18, 22"
        result = answer_extractor.extract("reasoning", 2, response)
        
        assert result["success"] is True
        assert result["answer_value"] == [3, 7, 15, 18, 22]
    
    def test_extract_total_members(self):
        """Test: Team member count = 17"""
        response = "Tim A = 5 orang\nTim B = 8 orang\nTim C = 4 orang\nTotal = 5 + 8 + 4 = 17 anggota"
        result = answer_extractor.extract("reasoning", 3, response)
        
        assert result["success"] is True
        assert result["answer_value"] == 17


class TestJSONParsing:
    """Test JSON parsing from various LLM output formats"""
    
    def test_parse_plain_json(self):
        """Test parsing plain JSON"""
        raw = '{"answer_type": "number", "answer_value": 36}'
        parsed = answer_extractor._parse_json_response(raw)
        
        assert parsed["success"] is True
        assert parsed["answer_value"] == 36
    
    def test_parse_markdown_json(self):
        """Test parsing JSON from markdown code block"""
        raw = '```json\n{"answer_type": "number", "answer_value": 36}\n```'
        parsed = answer_extractor._parse_json_response(raw)
        
        assert parsed["success"] is True
        assert parsed["answer_value"] == 36
    
    def test_parse_json_with_surrounding_text(self):
        """Test parsing JSON embedded in text"""
        raw = 'Berikut adalah jawaban:\n{"answer_type": "number", "answer_value": 36}\nSekian.'
        parsed = answer_extractor._parse_json_response(raw)
        
        assert parsed["success"] is True
        assert parsed["answer_value"] == 36
```

---

## Task 7: Update Configuration

**Objective:** Add configuration options for two-pass extraction.

**Files:**
- Modify: `config.py`

**Step 1: Add two-pass configuration**

```python
# Two-Pass Extraction Configuration
TWO_PASS_ENABLED = os.getenv("TWO_PASS_ENABLED", "1") == "1"
TWO_PASS_MODEL = os.getenv("TWO_PASS_MODEL", LLM_MODEL)  # Use same model by default
TWO_PASS_TEMPERATURE = float(os.getenv("TWO_PASS_TEMPERATURE", "0.0"))
TWO_PASS_TIMEOUT = int(os.getenv("TWO_PASS_TIMEOUT", "30"))
```

---

## Task 8: Add Cost Tracking for Two-Pass

**Objective:** Track additional LLM calls and costs from two-pass extraction.

**Files:**
- Modify: `models/db.py`

**Step 1: Add extraction metadata columns**

```python
# In evaluation_results table, add columns:
extraction_method TEXT,  -- 'llm' or 'fallback'
extraction_confidence TEXT,  -- 'high', 'medium', 'low'
extraction_duration_ms INTEGER,
```

---

## Task 9: Add Feature Flag Toggle in UI

**Objective:** Allow users to enable/disable two-pass extraction from the web UI.

**Files:**
- Modify: `templates/index.html`
- Modify: `app.py`

**Step 1: Add toggle switch in UI**

Add a toggle in the settings panel:
```html
<div class="setting-item">
    <label>Two-Pass Extraction</label>
    <input type="checkbox" id="two-pass-toggle" checked>
    <span class="helper-text">Use LLM to extract structured answers</span>
</div>
```

---

## Task 10: Update Documentation

**Objective:** Document the two-pass evaluation approach.

**Files:**
- Create: `docs/two-pass-evaluation.md`

**Step 1: Create documentation**

```markdown
# Two-Pass LLM Evaluation

## Overview

The two-pass evaluation approach improves answer extraction accuracy by using 
the LLM itself to parse and format answers in a strict, predictable structure.

## Flow

1. **Pass 1**: Send the test prompt to the LLM, receive natural language response
2. **Pass 2**: Send the response + extraction prompt to LLM, receive structured JSON

## Benefits

- Handles varied Indonesian response formats
- Extracts final answers from multi-step reasoning
- Normalizes currency formats (Rp 820.800 -> 820800)
- Works with step-by-step explanations

## Configuration

Set environment variables:
- `TWO_PASS_ENABLED=1` - Enable two-pass (default: enabled)
- `TWO_PASS_MODEL=<model>` - Model for extraction (default: same as evaluation)
- `TWO_PASS_TEMPERATURE=0.0` - Temperature for extraction (default: 0.0)
```

---

## Summary

| Task | Files | Estimated Time |
|------|-------|----------------|
| 1. Create Answer Extractor | `evaluator/answer_extractor.py` | 15 min |
| 2. Update Evaluation Engine | `evaluator/engine.py` | 10 min |
| 3. Update Scoring Engine | `evaluator/scoring.py` | 10 min |
| 4. Update Math Tests | `tests/math.py` | 10 min |
| 5. Update Reasoning Tests | `tests/reasoning.py` | 15 min |
| 6. Add Unit Tests | `tests/test_answer_extractor.py` | 15 min |
| 7. Update Config | `config.py` | 5 min |
| 8. Add DB Columns | `models/db.py` | 10 min |
| 9. Add UI Toggle | `templates/index.html`, `app.py` | 15 min |
| 10. Documentation | `docs/two-pass-evaluation.md` | 10 min |

**Total Estimated Time:** ~2 hours

---

## Verification

After implementation, verify with:

```bash
# Run extraction tests
python -m pytest tests/test_answer_extractor.py -v

# Run full evaluation
python run_headless.py --model default

# Check logs for two-pass activity
grep -E "\[EXTRACT\]" evaluation.log
```

---

Plan complete. Ready for approval.
