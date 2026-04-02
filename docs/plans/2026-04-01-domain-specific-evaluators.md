# Domain-Specific Evaluation Mechanism Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Redesign the evaluator to support domain-specific evaluation mechanisms, where each domain can choose the most appropriate evaluation strategy (two-pass LLM, regex, keyword matching, etc.).

**Architecture:** Strategy pattern with domain-specific evaluators that can be configured independently.

**Tech Stack:** Python, existing Flask app, OpenAI-compatible API

---

## Overview: Flexible Domain Evaluation

```
┌─────────────────────────────────────────────────────────────────┐
│                   EVALUATION ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐     ┌─────────────────────────────────┐   │
│  │ Evaluation      │     │ DomainEvaluatorRegistry         │   │
│  │ Engine          │────▶│                                 │   │
│  │                 │     │ math        → TwoPassEvaluator  │   │
│  │                 │     │ reasoning   → TwoPassEvaluator  │   │
│  │                 │     │ sql         → TwoPassEvaluator  │   │
│  │                 │     │ conversation→ KeywordEvaluator  │   │
│  │                 │     │ tool_calling→ TwoPassEvaluator  │   │
│  └─────────────────┘     └─────────────────────────────────┘   │
│                                      │                          │
│                                      ▼                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              EVALUATOR STRATEGIES                        │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │                                                         │   │
│  │  TwoPassEvaluator         KeywordEvaluator              │   │
│  │  ┌──────────────────┐    ┌──────────────────┐          │   │
│  │  │ PASS1: LLM Gen   │    │ Keyword Match    │          │   │
│  │  │ PASS2: Extract   │    │ Regex Patterns   │          │   │
│  │  │ Score: Compare   │    │ Score: Weights   │          │   │
│  │  └──────────────────┘    └──────────────────┘          │   │
│  │                                                         │   │
│  │  SQLExecutorEvaluator     ToolCallEvaluator            │   │
│  │  ┌──────────────────┐    ┌──────────────────┐          │   │
│  │  │ PASS2: Extract   │    │ PASS2: Extract   │          │   │
│  │  │ Execute SQL      │    │ Validate Tools   │          │   │
│  │  │ Score: Results   │    │ Score: Match     │          │   │
│  │  └──────────────────┘    └──────────────────┘          │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Domain-Specific Strategies

| Domain | Evaluator Strategy | Why |
|--------|-------------------|-----|
| **math** | TwoPassEvaluator | Need clean number extraction |
| **reasoning** | TwoPassEvaluator | Need clean answer extraction |
| **sql** | SQLExecutorEvaluator | TwoPass + SQL execution + result comparison |
| **conversation** | KeywordEvaluator | Simple keyword/rubric matching, no LLM needed |
| **tool_calling** | ToolCallEvaluator | TwoPass + tool validation |

---

## Task 1: Create Base Evaluator Interface

**Objective:** Define the abstract base class for all evaluators.

**Files:**
- Create: `evaluator/strategies/__init__.py`
- Create: `evaluator/strategies/base.py`

**Step 1: Create strategy package structure**

```python
# evaluator/strategies/__init__.py
"""Domain-specific evaluation strategies"""

from .base import BaseEvaluator
from .two_pass import TwoPassEvaluator
from .keyword import KeywordEvaluator
from .sql_executor import SQLExecutorEvaluator
from .tool_call import ToolCallEvaluator

__all__ = [
    'BaseEvaluator',
    'TwoPassEvaluator', 
    'KeywordEvaluator',
    'SQLExecutorEvaluator',
    'ToolCallEvaluator'
]
```

**Step 2: Create base evaluator interface**

```python
# evaluator/strategies/base.py
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
    def evaluate(self, response: str, expected: Any, level: int) -> EvaluationResult:
        """
        Evaluate the LLM response against expected output.
        
        Args:
            response: Raw LLM response from PASS 1
            expected: Expected output or validation criteria
            level: Test level (1-5)
            
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
```

---

## Task 2: Implement TwoPassEvaluator

**Objective:** Move existing two-pass logic into a dedicated evaluator class.

**Files:**
- Create: `evaluator/strategies/two_pass.py`

**Step 1: Create TwoPassEvaluator**

```python
# evaluator/strategies/two_pass.py
"""
Two-Pass Evaluator

PASS 1: LLM generates answer with reasoning
PASS 2: LLM extracts ONLY the final answer in strict format
"""

from typing import Any, Optional
from .base import BaseEvaluator, EvaluationResult
from evaluator.answer_extractor import answer_extractor
import re


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
        2. Score the clean answer
        """
        # PASS 2: Extract clean answer
        extraction = self.extractor.extract(self.domain, level, response)
        
        if not extraction["success"]:
            return EvaluationResult(
                score=0.0,
                status="failed",
                details={
                    "error": extraction.get("parse_error", "Extraction failed"),
                    "raw_output": extraction.get("raw_pass2", "")[:200],
                    "pass2": {
                        "success": False,
                        "format": extraction.get("expected_format"),
                        "error": extraction.get("parse_error")
                    }
                },
                extracted_answer=extraction.get("extracted"),
                pass2_used=True
            )
        
        # Score the extracted answer
        extracted = extraction["extracted"]
        score_result = self._score_extracted(extracted, expected, level)
        
        # Add PASS2 metadata
        score_result["details"]["pass2"] = {
            "success": True,
            "format": extraction["expected_format"],
            "raw_output": extraction.get("raw_pass2", "")[:100]
        }
        
        return EvaluationResult(
            score=score_result["score"],
            status=score_result.get("status", "passed" if score_result["score"] >= 0.8 else "failed"),
            details=score_result["details"],
            extracted_answer=extracted,
            pass2_used=True
        )
    
    def _score_extracted(self, extracted: str, expected: Any, level: int) -> Dict[str, Any]:
        """Score the extracted answer - implement in subclasses or use domain logic"""
        # This will be called by the domain-specific scoring
        # For now, return a placeholder
        return {
            "score": 0.0,
            "details": {"error": "Scoring not implemented"}
        }
```

---

## Task 3: Implement KeywordEvaluator

**Objective:** Create simple keyword/regex-based evaluator for conversation domain.

**Files:**
- Create: `evaluator/strategies/keyword.py`

**Step 1: Create KeywordEvaluator**

```python
# evaluator/strategies/keyword.py
"""
Keyword Evaluator

Simple keyword and regex-based evaluation without additional LLM calls.
Used for conversation domain.
"""

from typing import Any, Dict, List
from .base import BaseEvaluator, EvaluationResult
import re


class KeywordEvaluator(BaseEvaluator):
    """
    Keyword-based evaluation for conversation tests.
    
    No PASS2 LLM call needed - uses keyword matching and content analysis.
    """
    
    # Domain-specific keywords per level
    KEYWORDS = {
        "conversation": {
            1: ["ai", "assistant", "membantu", "help", "asisten", "saya", "i am", "qwen", "alibaba", "llm", "model"],
            2: ["jakarta", "ibu kota", "indonesia", "pusat", "pemerintahan", "nusantara", "ikn"],
            3: ["startup", "teknologi", "bisnis", "inovasi", "perusahaan", "skala", "pertumbuhan"],
            4: ["e-commerce", "tokopedia", "shopee", "pemasaran", "digital", "marketplace", "strategi"],
            5: ["transformasi digital", "retail", "teknologi", "adaptasi", "contoh", "online", "omnichannel"]
        }
    }
    
    # Indonesian words for fluency check
    INDONESIAN_WORDS = [
        "dan", "yang", "dengan", "untuk", "dalam", "pada", "ini", "itu",
        "adalah", "saya", "kami", "anda", "mereka", "akan", "atau", "juga",
        "dari", "ke", "di", "bisa", "dapat", "tidak", "ada", "seperti",
        "sebagai", "oleh", "karena", "tetapi", "jika", "maka", "agar"
    ]
    
    def __init__(self, domain: str = "conversation"):
        self.domain = domain
    
    @property
    def name(self) -> str:
        return f"keyword_{self.domain}"
    
    @property
    def uses_pass2(self) -> bool:
        return False
    
    def evaluate(self, response: str, expected: Any, level: int) -> EvaluationResult:
        """
        Evaluate using keyword matching and content analysis.
        
        Scoring:
        - Relevance: 30% (keyword matching)
        - Correctness: 40% (content quality)
        - Fluency: 30% (Indonesian language quality)
        """
        # Get expected keywords
        keywords = self.KEYWORDS.get(self.domain, {}).get(level, [])
        if not keywords and expected and isinstance(expected, dict):
            keywords = expected.get("keywords", [])
        
        # Score relevance (keyword matching)
        relevance = self._score_relevance(response, keywords)
        
        # Score correctness (content quality)
        correctness = self._score_correctness(response, level)
        
        # Score fluency (Indonesian language)
        fluency = self._score_fluency(response)
        
        # Calculate weighted score
        weights = {"relevance": 0.3, "correctness": 0.4, "fluency": 0.3}
        total_score = (
            relevance * weights["relevance"] +
            correctness * weights["correctness"] +
            fluency * weights["fluency"]
        )
        
        # Determine status
        if total_score >= 0.8:
            status = "passed"
        elif total_score >= 0.5:
            status = "partial"
        else:
            status = "failed"
        
        return EvaluationResult(
            score=total_score,
            status=status,
            details={
                "relevance": round(relevance, 3),
                "correctness": round(correctness, 3),
                "fluency": round(fluency, 3),
                "keywords_found": self._find_keywords(response, keywords),
                "scoring_method": "keyword_matching"
            },
            extracted_answer=None,  # No extraction for keyword evaluator
            pass2_used=False
        )
    
    def _score_relevance(self, response: str, keywords: List[str]) -> float:
        """Score based on keyword presence"""
        if not keywords:
            return 0.5
        
        found = self._find_keywords(response, keywords)
        keyword_score = len(found) / len(keywords)
        
        # Bonus for length (minimum content)
        length_score = min(len(response.split()) / 20, 1.0)
        
        return 0.8 * keyword_score + 0.2 * length_score
    
    def _score_correctness(self, response: str, level: int) -> float:
        """Score based on content correctness (domain-specific rules)"""
        response_lower = response.lower()
        
        correctness_rules = {
            1: (["ai", "assistant", "membantu", "bot", "qwen", "alibaba", "llm", "model"], 0.9, 0.5),
            2: (["jakarta", "nusantara", "ikn", "kalimantan"], 0.9, 0.3),
            3: (["teknologi", "inovasi", "perusahaan", "muda", "skala", "startup"], 0.85, 0.5),
            4: (["tokopedia", "shopee", "bukalapak", "pemasaran", "marketplace", "platform"], 0.8, 0.4),
            5: (["digital", "teknologi", "online", "e-commerce", "adaptasi", "transformasi"], 0.85, 0.5)
        }
        
        if level in correctness_rules:
            keywords, hit_score, miss_score = correctness_rules[level]
            if any(kw in response_lower for kw in keywords):
                return hit_score
            return miss_score
        
        return 0.5
    
    def _score_fluency(self, response: str) -> float:
        """Score Indonesian language fluency"""
        if not response.strip():
            return 0.0
        
        response_lower = response.lower()
        
        # Count Indonesian words
        found_words = sum(1 for word in self.INDONESIAN_WORDS if word in response_lower)
        word_score = min(found_words / 8, 1.0)  # At least 8 Indonesian words
        
        # Sentence count
        sentences = [s.strip() for s in re.split(r'[.!?]+', response) if s.strip()]
        sentence_score = min(len(sentences) / 3, 1.0)  # At least 3 sentences
        
        # Length
        length_score = min(len(response.split()) / 30, 1.0)
        
        return 0.4 * word_score + 0.3 * sentence_score + 0.3 * length_score
    
    def _find_keywords(self, response: str, keywords: List[str]) -> List[str]:
        """Find which keywords are present"""
        response_lower = response.lower()
        return [kw for kw in keywords if kw in response_lower]
```

---

## Task 4: Implement SQLExecutorEvaluator

**Objective:** Create SQL-specific evaluator with execution.

**Files:**
- Create: `evaluator/strategies/sql_executor.py`

**Step 1: Create SQLExecutorEvaluator**

```python
# evaluator/strategies/sql_executor.py
"""
SQL Executor Evaluator

Two-pass extraction + SQL execution and result validation.
Used for SQL domain.
"""

from typing import Any, Dict
from .base import BaseEvaluator, EvaluationResult
from evaluator.answer_extractor import answer_extractor
from evaluator.sql_executor import sql_executor


class SQLExecutorEvaluator(BaseEvaluator):
    """
    SQL evaluation with execution.
    
    1. PASS2: Extract clean SQL query
    2. Execute SQL on test database
    3. Compare results with expected
    """
    
    def __init__(self, domain: str = "sql"):
        self.domain = domain
        self.extractor = answer_extractor
    
    @property
    def name(self) -> str:
        return "sql_executor"
    
    @property
    def uses_pass2(self) -> bool:
        return True
    
    def evaluate(self, response: str, expected: Any, level: int) -> EvaluationResult:
        """Evaluate SQL with execution"""
        
        # PASS 2: Extract clean SQL
        extraction = self.extractor.extract(self.domain, level, response)
        
        if not extraction["success"]:
            return EvaluationResult(
                score=0.0,
                status="failed",
                details={
                    "error": extraction.get("parse_error", "SQL extraction failed"),
                    "pass2": {
                        "success": False,
                        "error": extraction.get("parse_error")
                    }
                },
                extracted_answer=extraction.get("extracted"),
                pass2_used=True
            )
        
        sql_query = extraction["extracted"]
        
        # Execute SQL
        execution_result = sql_executor.execute_safe_query(sql_query)
        
        if not execution_result.get("success"):
            return EvaluationResult(
                score=0.0,
                status="failed",
                details={
                    "error": execution_result.get("error", "SQL execution failed"),
                    "sql_query": sql_query,
                    "pass2": {
                        "success": True,
                        "format": extraction["expected_format"]
                    }
                },
                extracted_answer=sql_query,
                pass2_used=True
            )
        
        # Score the results
        score_result = self._score_results(
            execution_result, 
            expected, 
            level
        )
        
        # Add metadata
        score_result["details"]["sql_query"] = sql_query
        score_result["details"]["pass2"] = {
            "success": True,
            "format": extraction["expected_format"]
        }
        
        return EvaluationResult(
            score=score_result["score"],
            status=score_result.get("status", "passed" if score_result["score"] >= 0.8 else "failed"),
            details=score_result["details"],
            extracted_answer=sql_query,
            pass2_used=True
        )
    
    def _score_results(self, execution_result: Dict, expected: Dict, level: int) -> Dict:
        """Score SQL execution results"""
        # ... existing SQL scoring logic from tests/sql_gen.py ...
        # This will be moved here
        pass
```

---

## Task 5: Implement ToolCallEvaluator

**Objective:** Create tool call specific evaluator.

**Files:**
- Create: `evaluator/strategies/tool_call.py`

---

## Task 6: Create Domain Evaluator Registry

**Objective:** Create a registry that maps domains to their evaluators.

**Files:**
- Create: `evaluator/domain_evaluators.py`

**Step 1: Create the registry**

```python
# evaluator/domain_evaluators.py
"""
Domain Evaluator Registry

Maps each domain to its preferred evaluation strategy.
"""

from typing import Dict, Type
from .strategies.base import BaseEvaluator
from .strategies.two_pass import TwoPassEvaluator
from .strategies.keyword import KeywordEvaluator
from .strategies.sql_executor import SQLExecutorEvaluator
from .strategies.tool_call import ToolCallEvaluator


# Domain → Evaluator mapping
DOMAIN_EVALUATORS: Dict[str, Type[BaseEvaluator]] = {
    "math": TwoPassEvaluator,
    "reasoning": TwoPassEvaluator,
    "sql": SQLExecutorEvaluator,
    "conversation": KeywordEvaluator,  # No PASS2 needed
    "tool_calling": ToolCallEvaluator,
}


def get_evaluator(domain: str) -> BaseEvaluator:
    """
    Get the appropriate evaluator for a domain.
    
    Args:
        domain: Test domain name
        
    Returns:
        Evaluator instance for the domain
    """
    evaluator_class = DOMAIN_EVALUATORS.get(domain)
    
    if not evaluator_class:
        # Default to two-pass for unknown domains
        return TwoPassEvaluator(domain)
    
    # Instantiate with domain name
    return evaluator_class(domain)


def get_evaluator_info(domain: str) -> Dict:
    """Get information about the evaluator for a domain"""
    evaluator = get_evaluator(domain)
    return {
        "name": evaluator.name,
        "uses_pass2": evaluator.uses_pass2,
        "domain": domain
    }


def list_evaluators() -> Dict[str, Dict]:
    """List all domain-evaluator mappings"""
    return {
        domain: get_evaluator_info(domain)
        for domain in DOMAIN_EVALUATORS
    }
```

---

## Task 7: Update Evaluation Engine

**Objective:** Modify `evaluator/engine.py` to use domain evaluators.

**Files:**
- Modify: `evaluator/engine.py`

**Step 1: Replace direct scoring with evaluator registry**

```python
# In _run_single_test method, replace:

# OLD:
scoring_result = scoring_engine.score_test(domain, level, extraction["extracted"], expected)

# NEW:
from evaluator.domain_evaluators import get_evaluator

evaluator = get_evaluator(domain)
result = evaluator.evaluate(response_content, expected, level)

scoring_result = {
    "score": result.score,
    "status": result.status,
    "details": result.details
}

# Log evaluator used
self._log(f'[EVAL] Using {evaluator.name} (PASS2: {evaluator.uses_pass2})')
```

---

## Task 8: Update Configuration

**Objective:** Add config to allow overriding evaluator per domain.

**Files:**
- Modify: `config.py`

**Step 1: Add evaluator config**

```python
# Evaluator Configuration
# Override default evaluator for specific domains
# Format: {"domain": "evaluator_type"}
EVALUATOR_OVERRIDES = {
    # Example: Use keyword evaluator for math (not recommended)
    # "math": "keyword"
}

# Get evaluator type for domain
def get_evaluator_type(domain: str) -> str:
    """Get configured evaluator type for domain"""
    import os
    env_key = f"EVALUATOR_{domain.upper()}"
    return os.getenv(env_key, EVALUATOR_OVERRIDES.get(domain, "default"))
```

---

## Task 9: Update Tests

**Objective:** Update test classes to work with new evaluator system.

**Files:**
- Modify: `tests/math.py`
- Modify: `tests/reasoning.py`
- Modify: `tests/conversation.py`
- Modify: `tests/sql_gen.py`

---

## Task 10: Add Unit Tests for Evaluators

**Objective:** Create tests for each evaluator strategy.

**Files:**
- Create: `tests/test_evaluators.py`

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create Base Evaluator Interface | `evaluator/strategies/base.py` |
| 2 | Implement TwoPassEvaluator | `evaluator/strategies/two_pass.py` |
| 3 | Implement KeywordEvaluator | `evaluator/strategies/keyword.py` |
| 4 | Implement SQLExecutorEvaluator | `evaluator/strategies/sql_executor.py` |
| 5 | Implement ToolCallEvaluator | `evaluator/strategies/tool_call.py` |
| 6 | Create Domain Evaluator Registry | `evaluator/domain_evaluators.py` |
| 7 | Update Evaluation Engine | `evaluator/engine.py` |
| 8 | Update Configuration | `config.py` |
| 9 | Update Tests | `tests/*.py` |
| 10 | Add Unit Tests | `tests/test_evaluators.py` |

---

## Benefits

1. **Flexibility**: Each domain uses the most appropriate evaluation strategy
2. **Efficiency**: Conversation tests skip PASS2 LLM call (saves tokens/time)
3. **Maintainability**: Clear separation of concerns
4. **Extensibility**: Easy to add new evaluator strategies
5. **Configurability**: Can override evaluators via config/env

---

## Domain → Evaluator Mapping (Final)

| Domain | Evaluator | PASS2? | Why |
|--------|-----------|--------|-----|
| math | TwoPassEvaluator | ✓ | Need clean number extraction |
| reasoning | TwoPassEvaluator | ✓ | Need clean answer extraction |
| sql | SQLExecutorEvaluator | ✓ | Need clean SQL + execution |
| conversation | KeywordEvaluator | ✗ | Simple keyword matching |
| tool_calling | ToolCallEvaluator | ✓ | Need clean tool extraction |

---

Plan complete. Ready for approval.
