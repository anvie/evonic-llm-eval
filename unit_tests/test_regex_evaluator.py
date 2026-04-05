#!/usr/bin/env python3
"""
Unit tests for Regex Evaluator

Tests the regex-based evaluation modes:
1. Regex Matcher (use_expected_as_pattern)
2. Score extraction
3. String matching
4. Hybrid mode
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluator.custom_evaluator import CustomEvaluator, EvaluationResult


class TestRegexMatcher:
    """Test regex_matcher evaluator (expected value as pattern)"""
    
    def test_regex_matcher_basic_match(self):
        """Test basic pattern matching"""
        config = {
            'id': 'regex_matcher',
            'name': 'Regex Matcher',
            'type': 'regex',
            'extraction_regex': '^(.+)$',
            'config': {'use_expected_as_pattern': True}
        }
        evaluator = CustomEvaluator(config)
        
        # Pattern: match any greeting
        expected = r'(?i)(hello|hi|halo)'
        response = 'Hello, how can I help you?'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 1.0
        assert result.status == 'passed'
        assert result.details['method'] == 'regex_matcher'
        assert result.details['matched_text'] is not None
    
    def test_regex_matcher_no_match(self):
        """Test when pattern doesn't match"""
        config = {
            'id': 'regex_matcher',
            'name': 'Regex Matcher',
            'type': 'regex',
            'extraction_regex': '^(.+)$',
            'config': {'use_expected_as_pattern': True}
        }
        evaluator = CustomEvaluator(config)
        
        expected = r'\d{4}-\d{2}-\d{2}'  # Date pattern
        response = 'The meeting is next Monday'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 0.0
        assert result.status == 'failed'
        assert result.details['method'] == 'regex_matcher'
    
    def test_regex_matcher_date_pattern(self):
        """Test date pattern matching"""
        config = {
            'id': 'regex_matcher',
            'type': 'regex',
            'extraction_regex': '^(.+)$',
            'config': {'use_expected_as_pattern': True}
        }
        evaluator = CustomEvaluator(config)
        
        expected = r'\d{4}-\d{2}-\d{2}'
        response = 'The reservation date is 2026-04-05'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 1.0
        assert result.status == 'passed'
        assert result.details['matched_text'] == '2026-04-05'
    
    def test_regex_matcher_sql_keywords(self):
        """Test SQL keyword pattern"""
        config = {
            'id': 'regex_matcher',
            'type': 'regex',
            'extraction_regex': '^(.+)$',
            'config': {'use_expected_as_pattern': True}
        }
        evaluator = CustomEvaluator(config)
        
        expected = r'(?i)SELECT.*FROM'
        response = 'SELECT * FROM customers WHERE id = 1'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 1.0
        assert result.status == 'passed'
    
    def test_regex_matcher_case_insensitive(self):
        """Test case-insensitive matching"""
        config = {
            'id': 'regex_matcher',
            'type': 'regex',
            'extraction_regex': '^(.+)$',
            'config': {'use_expected_as_pattern': True}
        }
        evaluator = CustomEvaluator(config)
        
        expected = r'(?i)hello'
        response = 'HELLO there!'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 1.0
        assert result.status == 'passed'


class TestRegexScoreExtraction:
    """Test score extraction mode"""
    
    def test_extract_percentage(self):
        """Test extracting percentage score"""
        config = {
            'id': 'regex_score',
            'type': 'regex',
            'extraction_regex': r'SCORE:\s*(\d+)',
            'config': {}
        }
        evaluator = CustomEvaluator(config)
        
        response = 'The quality is good. SCORE: 85'
        expected = None
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 0.85
        assert result.status == 'passed'
        assert result.details['extracted_value'] == '85'
    
    def test_extract_decimal_score(self):
        """Test extracting decimal score"""
        config = {
            'id': 'regex_score',
            'type': 'regex',
            'extraction_regex': r'score:\s*(\d+\.\d+)',
            'config': {}
        }
        evaluator = CustomEvaluator(config)
        
        # Note: Current normalization: if score > 1.0, assume percentage (divide by 100)
        # So 85.5 becomes 0.855, but 4.5 becomes 0.045 (might need improvement)
        response = 'Quality score: 85.5'
        expected = None
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 0.855
        assert result.status == 'passed'
        assert result.details['extracted_value'] == '85.5'


class TestRegexStringMatching:
    """Test string matching with extraction"""
    
    def test_extract_and_compare_match(self):
        """Test extracting value and comparing with expected"""
        config = {
            'id': 'regex_extract',
            'type': 'regex',
            'extraction_regex': r'Answer:\s*([A-D])',
            'config': {}
        }
        evaluator = CustomEvaluator(config)
        
        response = 'The correct Answer: B'
        expected = 'B'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 1.0
        assert result.status == 'passed'
        assert result.details['match'] == True
    
    def test_extract_and_compare_no_match(self):
        """Test extracting value that doesn't match expected"""
        config = {
            'id': 'regex_extract',
            'type': 'regex',
            'extraction_regex': r'Answer:\s*([A-D])',
            'config': {}
        }
        evaluator = CustomEvaluator(config)
        
        response = 'The correct Answer: C'
        expected = 'A'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 0.0
        assert result.status == 'failed'
        assert result.details['match'] == False


class TestHybridEvaluator:
    """Test hybrid mode (LLM + regex)"""
    
    def test_hybrid_configuration(self):
        """Test that hybrid mode is detected when both prompt and regex exist"""
        config = {
            'id': 'hybrid_test',
            'type': 'hybrid',
            'eval_prompt': 'Rate this response: {response}. Output: SCORE: <number>',
            'extraction_regex': r'SCORE:\s*(\d+)',
            'config': {}
        }
        evaluator = CustomEvaluator(config)
        
        # Verify both are set
        assert evaluator.eval_prompt is not None
        assert evaluator.extraction_regex is not None
        
        # Note: Actual hybrid evaluation requires LLM, so we just test config detection
        # The _evaluate_hybrid method will be called when both are present
        assert evaluator.extraction_regex is not None


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_invalid_regex_pattern(self):
        """Test handling of invalid regex pattern"""
        config = {
            'id': 'regex_invalid',
            'type': 'regex',
            'extraction_regex': r'[invalid(regex',
            'config': {'use_expected_as_pattern': True}
        }
        evaluator = CustomEvaluator(config)
        
        response = 'Any response'
        expected = r'[invalid(regex'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 0.0
        assert result.status == 'failed'
        assert 'error' in result.details
    
    def test_empty_response(self):
        """Test with empty response"""
        config = {
            'id': 'regex_matcher',
            'type': 'regex',
            'extraction_regex': '^(.+)$',
            'config': {'use_expected_as_pattern': True}
        }
        evaluator = CustomEvaluator(config)
        
        response = ''
        expected = r'hello'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 0.0
        assert result.status == 'failed'
    
    def test_no_evaluation_method(self):
        """Test when neither prompt nor regex is configured"""
        config = {
            'id': 'empty_evaluator',
            'type': 'custom',
            'config': {}
        }
        evaluator = CustomEvaluator(config)
        
        response = 'Test'
        expected = 'Test'
        
        result = evaluator.evaluate(response, expected)
        
        assert result.score == 0.0
        assert result.status == 'failed'
        assert 'No evaluation method configured' in result.details['error']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
