"""
Keyword Evaluator

Simple keyword and regex-based evaluation without additional LLM calls.
Used for conversation domain - no PASS2 needed.
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
    
    def evaluate(self, response: str, expected: Any, level: int, prompt: str = "") -> EvaluationResult:
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
            score=round(total_score, 3),
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
