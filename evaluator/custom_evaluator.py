"""
Custom Evaluator - Handle custom evaluators for test scoring.

Supports two types of custom evaluators:
1. Prompt-based: Send evaluation prompt to LLM
2. Regex-based: Extract score using regex pattern from response
"""

import re
import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from evaluator.llm_client import llm_client


@dataclass
class EvaluationResult:
    """Result of evaluating a response"""
    score: float
    status: str
    details: Dict[str, Any]
    reasoning: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'score': self.score,
            'status': self.status,
            'details': self.details,
            'reasoning': self.reasoning
        }


class CustomEvaluator:
    """Handle custom evaluator logic"""
    
    def __init__(self, evaluator_config: Dict[str, Any]):
        """
        Initialize custom evaluator with configuration.
        
        Args:
            evaluator_config: Evaluator configuration dictionary containing:
                - id: Evaluator ID
                - name: Display name
                - type: 'custom' or 'predefined'
                - eval_prompt: (optional) Prompt template for LLM evaluation
                - extraction_regex: (optional) Regex to extract score from response
                - config: Additional configuration
        """
        self.config = evaluator_config
        self.id = evaluator_config.get('id', '')
        self.name = evaluator_config.get('name', '')
        self.type = evaluator_config.get('type', 'custom')
        self.eval_prompt = evaluator_config.get('eval_prompt')
        self.extraction_regex = evaluator_config.get('extraction_regex')
        self.evaluator_config = evaluator_config.get('config', {})
    
    def evaluate(self, response: str, expected: Any, level: int = 1) -> EvaluationResult:
        """
        Evaluate a response using the configured evaluation method.
        
        Args:
            response: The LLM response to evaluate
            expected: Expected result or criteria
            level: Test level (1-5)
            
        Returns:
            EvaluationResult with score and details
        """
        if self.extraction_regex:
            return self._evaluate_with_regex(response, expected, level)
        elif self.eval_prompt:
            return self._evaluate_with_prompt(response, expected, level)
        else:
            return EvaluationResult(
                score=0.0,
                status='failed',
                details={'error': 'No evaluation method configured'},
                reasoning='Evaluator missing both eval_prompt and extraction_regex'
            )
    
    def _evaluate_with_regex(self, response: str, expected: Any, level: int) -> EvaluationResult:
        """Extract score using regex pattern"""
        try:
            # Try to find score in response
            pattern = self.extraction_regex
            match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
            
            if match:
                # Extract score from first capture group
                score_str = match.group(1)
                score = float(score_str)
                
                # Normalize score to 0-1 range
                if score > 1.0:
                    score = score / 100.0  # Assume percentage
                
                # Determine status
                status = 'passed' if score >= 0.7 else 'failed'
                
                return EvaluationResult(
                    score=score,
                    status=status,
                    details={
                        'method': 'regex',
                        'extracted_score': score_str,
                        'pattern': pattern
                    },
                    reasoning=f'Extracted score {score_str} using pattern {pattern}'
                )
            else:
                return EvaluationResult(
                    score=0.0,
                    status='failed',
                    details={
                        'method': 'regex',
                        'error': 'Pattern not found in response',
                        'pattern': pattern
                    },
                    reasoning=f'Regex pattern {pattern} did not match response'
                )
                
        except Exception as e:
            return EvaluationResult(
                score=0.0,
                status='failed',
                details={
                    'method': 'regex',
                    'error': str(e)
                },
                reasoning=f'Regex evaluation failed: {str(e)}'
            )
    
    def _evaluate_with_prompt(self, response: str, expected: Any, level: int) -> EvaluationResult:
        """Evaluate using LLM with custom prompt"""
        try:
            # Build evaluation prompt
            eval_prompt_text = self.eval_prompt
            
            # Replace placeholders
            eval_prompt_text = eval_prompt_text.replace('{response}', response)
            
            if expected:
                expected_str = json.dumps(expected) if isinstance(expected, (dict, list)) else str(expected)
                eval_prompt_text = eval_prompt_text.replace('{expected}', expected_str)
            
            eval_prompt_text = eval_prompt_text.replace('{level}', str(level))
            
            # Send to LLM
            messages = [{"role": "user", "content": eval_prompt_text}]
            llm_response = llm_client.chat_completion(messages)
            
            eval_response = llm_client.extract_content(llm_response)
            
            # Try to parse as JSON
            try:
                # Find JSON in response
                json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', eval_response, re.DOTALL)
                if json_match:
                    result_json = json.loads(json_match.group(0))
                    score = float(result_json.get('score', 0))
                    reasoning = result_json.get('reasoning', '')
                    
                    # Normalize score
                    # If score is > 1 and <= 5, assume 0-5 scale
                    if score > 5.0:
                        score = score / 100.0  # Assume percentage (0-100)
                    elif score > 1.0:
                        score = score / 5.0    # Assume 0-5 rating scale
                    
                    status = 'passed' if score >= 0.7 else 'failed'
                    
                    return EvaluationResult(
                        score=score,
                        status=status,
                        details={
                            'method': 'prompt',
                            'eval_response': eval_response[:500]  # Truncate for storage
                        },
                        reasoning=reasoning
                    )
            except json.JSONDecodeError:
                pass
            
            # Try to extract score directly
            # Look for patterns like "score: 85", "score is 85", "score 85"
            score_match = re.search(r'score[^\d]*(\d+(?:\.\d+)?)', eval_response, re.IGNORECASE)
            if score_match:
                score = float(score_match.group(1))
                # Normalize: if > 5 assume percentage, if > 1 assume 0-5 scale
                if score > 5.0:
                    score = score / 100.0
                elif score > 1.0:
                    score = score / 5.0
                
                status = 'passed' if score >= 0.7 else 'failed'
                
                return EvaluationResult(
                    score=score,
                    status=status,
                    details={
                        'method': 'prompt',
                        'eval_response': eval_response[:500]
                    },
                    reasoning='Score extracted from LLM evaluation response'
                )
            
            # Fallback: look for pass/fail in response
            if 'pass' in eval_response.lower():
                return EvaluationResult(
                    score=1.0,
                    status='passed',
                    details={'method': 'prompt', 'eval_response': eval_response[:500]},
                    reasoning='Pass keyword found in evaluation response'
                )
            elif 'fail' in eval_response.lower():
                return EvaluationResult(
                    score=0.0,
                    status='failed',
                    details={'method': 'prompt', 'eval_response': eval_response[:500]},
                    reasoning='Fail keyword found in evaluation response'
                )
            
            return EvaluationResult(
                score=0.0,
                status='failed',
                details={
                    'method': 'prompt',
                    'error': 'Could not parse evaluation response',
                    'eval_response': eval_response[:500]
                },
                reasoning='Failed to parse score from LLM evaluation'
            )
            
        except Exception as e:
            return EvaluationResult(
                score=0.0,
                status='failed',
                details={
                    'method': 'prompt',
                    'error': str(e)
                },
                reasoning=f'Prompt evaluation failed: {str(e)}'
            )


# Predefined evaluation prompts for common use cases
DEFAULT_EVAL_PROMPTS = {
    'numeric': """Evaluate if this response contains the correct numeric answer.

Expected answer: {expected}
Response: {response}

Rate the response on a scale of 0-5 where:
- 5: Exact correct answer
- 4: Close answer (within 5% tolerance)
- 3: Partially correct (right method, wrong final answer)
- 2: Wrong answer but shows understanding
- 1: Completely wrong
- 0: No numeric response

Return JSON: {"score": <0-5>, "reasoning": "<explanation>"}""",

    'factual': """Evaluate if this response contains accurate factual information.

Expected facts: {expected}
Response: {response}

Rate the response on a scale of 0-5 based on:
- Accuracy of information
- Completeness
- Relevance

Return JSON: {"score": <0-5>, "reasoning": "<explanation>"}""",

    'conversation': """Evaluate this conversational response.

Expected content: {expected}
Response: {response}

Rate on a scale of 0-5 based on:
- Relevance to the question
- Accuracy of information
- Fluency and naturalness

Return JSON: {"score": <0-5>, "reasoning": "<explanation>", "relevance": <0-1>, "accuracy": <0-1>, "fluency": <0-1>}""",

    'code': """Evaluate this code response.

Expected output: {expected}
Response: {response}

Rate on a scale of 0-5 based on:
- Correctness
- Code quality
- Efficiency

Return JSON: {"score": <0-5>, "reasoning": "<explanation>"}"""
}


def get_default_eval_prompt(prompt_type: str) -> Optional[str]:
    """Get a default evaluation prompt by type"""
    return DEFAULT_EVAL_PROMPTS.get(prompt_type)


def create_custom_evaluator(evaluator_type: str, config: Dict[str, Any] = None) -> CustomEvaluator:
    """Create a custom evaluator with default configuration"""
    config = config or {}
    
    # Merge with default prompt if specified
    if evaluator_type in DEFAULT_EVAL_PROMPTS and 'eval_prompt' not in config:
        config['eval_prompt'] = DEFAULT_EVAL_PROMPTS[evaluator_type]
    
    config['type'] = 'custom'
    
    return CustomEvaluator(config)