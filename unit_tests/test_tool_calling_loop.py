"""
Unit tests for the multi-turn tool calling loop.

Tests the _run_tool_calling_loop method in the evaluation engine.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluator.engine import EvaluationEngine, MAX_TOOL_ITERATIONS
from evaluator.tools import tool_framework


class TestToolCallingLoop(unittest.TestCase):
    """Test the multi-turn tool calling loop"""
    
    def setUp(self):
        """Set up test engine"""
        self.engine = EvaluationEngine(use_configurable_tests=True)
        self.engine.log_queue = MagicMock()  # Mock log queue
        self.tools = tool_framework.tools
    
    def _create_tool_call_response(self, tool_calls):
        """Helper to create mock LLM response with tool calls"""
        return {
            "success": True,
            "response": {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls
                    }
                }]
            },
            "duration_ms": 100,
            "total_tokens": 50
        }
    
    def _create_text_response(self, content, thinking=None):
        """Helper to create mock LLM response with text"""
        message = {
            "role": "assistant",
            "content": content
        }
        if thinking:
            message["reasoning_content"] = thinking
        
        return {
            "success": True,
            "response": {
                "choices": [{
                    "message": message
                }]
            },
            "duration_ms": 100,
            "total_tokens": 50
        }
    
    @patch('evaluator.engine.llm_client')
    def test_single_tool_call_then_answer(self, mock_llm):
        """Test: LLM makes 1 tool call, then answers"""
        # First call: tool call
        # Second call: final answer
        mock_llm.chat_completion.side_effect = [
            self._create_tool_call_response([{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": json.dumps({"location": "Jakarta"})
                }
            }]),
            self._create_text_response("The weather in Jakarta is 32°C and sunny.")
        ]
        mock_llm.extract_content_with_thinking.side_effect = [
            {"content": None, "thinking": None, "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": json.dumps({"location": "Jakarta"})
                }
            }]},
            {"content": "The weather in Jakarta is 32°C and sunny.", "thinking": None}
        ]
        
        result = self.engine._run_tool_calling_loop(
            "What's the weather in Jakarta?",
            self.tools
        )
        
        self.assertEqual(len(result["all_tool_calls"]), 1)
        self.assertEqual(result["all_tool_calls"][0]["function"]["name"], "get_weather")
        self.assertEqual(result["iterations"], 2)
        self.assertIn("weather", result["final_response"].lower())
    
    @patch('evaluator.engine.llm_client')
    def test_multiple_tool_calls_sequence(self, mock_llm):
        """Test: LLM makes 2 tool calls in sequence, then answers"""
        # First call: get_weather
        # Second call: search_restaurants
        # Third call: final answer
        mock_llm.chat_completion.side_effect = [
            self._create_tool_call_response([{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "arguments": json.dumps({"location": "Bali"})
                }
            }]),
            self._create_tool_call_response([{
                "id": "call_2",
                "type": "function",
                "function": {
                    "name": "search_hotels",
                    "arguments": json.dumps({"location": "Bali"})
                }
            }]),
            self._create_text_response("Bali is sunny at 30°C. I found 3 hotels for you.")
        ]
        mock_llm.extract_content_with_thinking.side_effect = [
            {"content": None, "thinking": None, "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": json.dumps({"location": "Bali"})}
            }]},
            {"content": None, "thinking": None, "tool_calls": [{
                "id": "call_2",
                "type": "function",
                "function": {"name": "search_hotels", "arguments": json.dumps({"location": "Bali"})}
            }]},
            {"content": "Bali is sunny at 30°C. I found 3 hotels for you.", "thinking": None}
        ]
        
        result = self.engine._run_tool_calling_loop(
            "What's the weather in Bali and find me a hotel?",
            self.tools
        )
        
        self.assertEqual(len(result["all_tool_calls"]), 2)
        tool_names = [tc["function"]["name"] for tc in result["all_tool_calls"]]
        self.assertIn("get_weather", tool_names)
        self.assertIn("search_hotels", tool_names)
        self.assertEqual(result["iterations"], 3)
    
    @patch('evaluator.engine.llm_client')
    def test_no_tool_call_direct_answer(self, mock_llm):
        """Test: LLM answers directly without tool calls"""
        mock_llm.chat_completion.return_value = self._create_text_response(
            "I don't need any tools to answer this."
        )
        mock_llm.extract_content_with_thinking.return_value = {
            "content": "I don't need any tools to answer this.",
            "thinking": None
        }
        
        result = self.engine._run_tool_calling_loop(
            "What is 2 + 2?",
            self.tools
        )
        
        self.assertEqual(len(result["all_tool_calls"]), 0)
        self.assertEqual(result["iterations"], 1)
        self.assertEqual(result["final_response"], "I don't need any tools to answer this.")
    
    @patch('evaluator.engine.llm_client')
    def test_max_iterations_limit(self, mock_llm):
        """Test: Loop stops at MAX_TOOL_ITERATIONS"""
        # Always return tool calls (never final answer)
        mock_llm.chat_completion.return_value = self._create_tool_call_response([{
            "id": "call_n",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"location": "Test"})
            }
        }])
        mock_llm.extract_content_with_thinking.return_value = {
            "content": None,
            "thinking": None,
            "tool_calls": [{
                "id": "call_n",
                "type": "function",
                "function": {"name": "get_weather", "arguments": json.dumps({"location": "Test"})}
            }]
        }
        
        result = self.engine._run_tool_calling_loop(
            "Keep calling tools forever",
            self.tools
        )
        
        self.assertEqual(result["iterations"], MAX_TOOL_ITERATIONS)
        self.assertEqual(len(result["all_tool_calls"]), MAX_TOOL_ITERATIONS)
    
    @patch('evaluator.engine.llm_client')
    def test_thinking_captured_from_first_iteration(self, mock_llm):
        """Test: Thinking content is captured from first iteration"""
        mock_llm.chat_completion.side_effect = [
            self._create_tool_call_response([{
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": json.dumps({"location": "Jakarta"})}
            }]),
            self._create_text_response("It's sunny in Jakarta.")
        ]
        mock_llm.extract_content_with_thinking.side_effect = [
            {
                "content": None,
                "thinking": "I need to check the weather first.",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": json.dumps({"location": "Jakarta"})}
                }]
            },
            {"content": "It's sunny in Jakarta.", "thinking": None}
        ]
        
        result = self.engine._run_tool_calling_loop(
            "What's the weather?",
            self.tools
        )
        
        self.assertEqual(result["thinking"], "I need to check the weather first.")
    
    @patch('evaluator.engine.llm_client')
    def test_duration_and_tokens_accumulated(self, mock_llm):
        """Test: Duration and tokens are accumulated across iterations"""
        mock_llm.chat_completion.side_effect = [
            {
                "success": True,
                "response": {"choices": [{"message": {"content": None, "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": "{}"}
                }]}}]},
                "duration_ms": 100,
                "total_tokens": 50
            },
            {
                "success": True,
                "response": {"choices": [{"message": {"content": "Done"}}]},
                "duration_ms": 150,
                "total_tokens": 75
            }
        ]
        mock_llm.extract_content_with_thinking.side_effect = [
            {"content": None, "thinking": None, "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "get_weather", "arguments": "{}"}
            }]},
            {"content": "Done", "thinking": None}
        ]
        
        result = self.engine._run_tool_calling_loop("Test", self.tools)
        
        self.assertEqual(result["total_duration_ms"], 250)  # 100 + 150
        self.assertEqual(result["total_tokens"], 125)  # 50 + 75
    
    @patch('evaluator.engine.llm_client')
    def test_parallel_tool_calls(self, mock_llm):
        """Test: LLM makes multiple tool calls in single response"""
        mock_llm.chat_completion.side_effect = [
            self._create_tool_call_response([
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": json.dumps({"location": "Jakarta"})}
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": json.dumps({"location": "Bali"})}
                }
            ]),
            self._create_text_response("Jakarta: 32°C, Bali: 30°C")
        ]
        mock_llm.extract_content_with_thinking.side_effect = [
            {"content": None, "thinking": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": json.dumps({"location": "Jakarta"})}},
                {"id": "call_2", "type": "function", "function": {"name": "get_weather", "arguments": json.dumps({"location": "Bali"})}}
            ]},
            {"content": "Jakarta: 32°C, Bali: 30°C", "thinking": None}
        ]
        
        result = self.engine._run_tool_calling_loop(
            "What's the weather in Jakarta and Bali?",
            self.tools
        )
        
        self.assertEqual(len(result["all_tool_calls"]), 2)
        self.assertEqual(result["iterations"], 2)


class TestMaxToolIterations(unittest.TestCase):
    """Test MAX_TOOL_ITERATIONS constant"""
    
    def test_max_iterations_defined(self):
        """Test that MAX_TOOL_ITERATIONS is defined"""
        self.assertIsNotNone(MAX_TOOL_ITERATIONS)
        self.assertIsInstance(MAX_TOOL_ITERATIONS, int)
    
    def test_max_iterations_reasonable(self):
        """Test that MAX_TOOL_ITERATIONS is reasonable (between 3 and 10)"""
        self.assertGreaterEqual(MAX_TOOL_ITERATIONS, 3)
        self.assertLessEqual(MAX_TOOL_ITERATIONS, 10)


if __name__ == "__main__":
    unittest.main()
