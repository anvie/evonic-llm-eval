"""
Unit tests for tool call evaluation logic.

Tests the ToolCallEvaluator from evaluator/strategies/tool_call.py
"""

import unittest
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluator.strategies.tool_call import ToolCallEvaluator


class TestToolCallEvaluation(unittest.TestCase):
    """Test tool call evaluation scoring"""
    
    def setUp(self):
        """Set up evaluator"""
        self.evaluator = ToolCallEvaluator()
    
    def test_correct_single_tool(self):
        """Test: Correct single tool call → score 1.0"""
        response = json.dumps({
            "tool_calls": [{
                "id": "call_1",
                "function": {
                    "name": "get_weather",
                    "arguments": json.dumps({"location": "Jakarta"})
                }
            }]
        })
        expected = {"tools": ["get_weather"]}
        
        result = self.evaluator.evaluate(response, expected, level=1)
        
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.status, "passed")
    
    def test_correct_multiple_tools(self):
        """Test: All expected tools called → score 1.0"""
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "function": {"name": "get_weather", "arguments": "{}"}},
                {"id": "call_2", "function": {"name": "search_hotels", "arguments": "{}"}}
            ]
        })
        expected = {"tools": ["get_weather", "search_hotels"]}
        
        result = self.evaluator.evaluate(response, expected, level=3)
        
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.status, "passed")
    
    def test_missing_one_tool(self):
        """Test: 1 of 2 expected tools called → score 0.5"""
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "function": {"name": "get_weather", "arguments": "{}"}}
            ]
        })
        expected = {"tools": ["get_weather", "search_hotels"]}
        
        result = self.evaluator.evaluate(response, expected, level=3)
        
        self.assertEqual(result.score, 0.5)
        self.assertEqual(result.status, "failed")
    
    def test_missing_all_tools(self):
        """Test: No expected tools called → score 0.0"""
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "function": {"name": "calculator", "arguments": "{}"}}
            ]
        })
        expected = {"tools": ["get_weather", "search_hotels"]}
        
        result = self.evaluator.evaluate(response, expected, level=3)
        
        self.assertEqual(result.score, 0.0)
        self.assertEqual(result.status, "failed")
    
    def test_extra_tools_ok(self):
        """Test: Extra tools called (beyond expected) → still passes"""
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "function": {"name": "get_weather", "arguments": "{}"}},
                {"id": "call_2", "function": {"name": "calculator", "arguments": "{}"}},
                {"id": "call_3", "function": {"name": "search_hotels", "arguments": "{}"}}
            ]
        })
        expected = {"tools": ["get_weather"]}
        
        result = self.evaluator.evaluate(response, expected, level=1)
        
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.status, "passed")
    
    def test_two_of_three_tools(self):
        """Test: 2 of 3 expected tools → score 0.67"""
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "function": {"name": "get_weather", "arguments": "{}"}},
                {"id": "call_2", "function": {"name": "search_hotels", "arguments": "{}"}}
            ]
        })
        expected = {"tools": ["get_weather", "search_hotels", "send_notification"]}
        
        result = self.evaluator.evaluate(response, expected, level=4)
        
        self.assertAlmostEqual(result.score, 2/3, places=2)
        self.assertEqual(result.status, "failed")  # < 0.8 threshold
    
    def test_expected_as_list(self):
        """Test: Expected can be a list directly"""
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "function": {"name": "calculator", "arguments": "{}"}}
            ]
        })
        expected = ["calculator"]  # List instead of dict
        
        result = self.evaluator.evaluate(response, expected, level=1)
        
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.status, "passed")
    
    def test_expected_with_chain(self):
        """Test: Expected with 'chain' key (for chained calls)"""
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "function": {"name": "get_weather", "arguments": "{}"}},
                {"id": "call_2", "function": {"name": "search_restaurants", "arguments": "{}"}}
            ]
        })
        expected = {"chain": ["get_weather", "search_restaurants"]}
        
        result = self.evaluator.evaluate(response, expected, level=3)
        
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.status, "passed")
    
    def test_no_tool_calls_fails(self):
        """Test: No tool calls when expected → fails"""
        response = "I don't need any tools for this."
        expected = {"tools": ["calculator"]}
        
        result = self.evaluator.evaluate(response, expected, level=1)
        
        # Should fail or have low score since no tool calls detected
        self.assertLess(result.score, 0.8)
    
    def test_details_include_called_tools(self):
        """Test: Result details include called tools list"""
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "function": {"name": "get_weather", "arguments": "{}"}}
            ]
        })
        expected = {"tools": ["get_weather"]}
        
        result = self.evaluator.evaluate(response, expected, level=1)
        
        self.assertIn("called_tools", result.details)
        self.assertIn("get_weather", result.details["called_tools"])
    
    def test_details_include_missing_tools(self):
        """Test: Result details include missing tools list"""
        response = json.dumps({
            "tool_calls": [
                {"id": "call_1", "function": {"name": "get_weather", "arguments": "{}"}}
            ]
        })
        expected = {"tools": ["get_weather", "search_hotels"]}
        
        result = self.evaluator.evaluate(response, expected, level=3)
        
        self.assertIn("missing_tools", result.details)
        self.assertIn("search_hotels", result.details["missing_tools"])


class TestToolCallExtraction(unittest.TestCase):
    """Test tool call extraction from various formats"""
    
    def setUp(self):
        """Set up evaluator"""
        self.evaluator = ToolCallEvaluator()
    
    def test_extract_openai_format(self):
        """Test extraction from OpenAI tool_calls format"""
        response = json.dumps({
            "tool_calls": [{
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": json.dumps({"location": "Tokyo"})
                }
            }]
        })
        
        tool_calls = self.evaluator._extract_tool_calls(response)
        
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["function"]["name"], "get_weather")
    
    def test_extract_gemma4_format(self):
        """Test extraction from Gemma4 format"""
        response = '<|tool_call>get_weather{location:<|"|>Jakarta<|"|>}<|tool_call|>'
        
        tool_calls = self.evaluator._extract_tool_calls(response)
        
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0]["function"]["name"], "get_weather")
    
    def test_extract_no_tool_calls(self):
        """Test extraction returns empty list for plain text"""
        response = "The weather today is sunny."
        
        tool_calls = self.evaluator._extract_tool_calls(response)
        
        self.assertEqual(tool_calls, [])


if __name__ == "__main__":
    unittest.main()
