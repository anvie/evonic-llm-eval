"""
Unit tests for the tool framework mock executor.

Tests the mock tool execution functionality used in multi-turn
tool calling evaluations.
"""

import unittest
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluator.tools import tool_framework


class TestMockExecutor(unittest.TestCase):
    """Test individual mock tool executions"""
    
    def test_get_weather_known_location(self):
        """Test weather for known location returns correct format"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"location": "Jakarta"})
            }
        })
        
        self.assertTrue(result["success"])
        self.assertEqual(result["function_name"], "get_weather")
        self.assertIn("weather", result["result"])
        self.assertIn("temp", result["result"]["weather"])
    
    def test_get_weather_unknown_location(self):
        """Test weather for unknown location returns default"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"location": "Unknown City"})
            }
        })
        
        self.assertTrue(result["success"])
        self.assertIn("weather", result["result"])
    
    def test_calculator_simple(self):
        """Test simple calculation"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "calculator",
                "arguments": json.dumps({"expression": "2 + 3 * 4"})
            }
        })
        
        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["result"], 14)
    
    def test_calculator_complex(self):
        """Test complex calculation"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "calculator",
                "arguments": json.dumps({"expression": "(100 - 20) * 0.9"})
            }
        })
        
        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["result"], 72.0)
    
    def test_calculator_invalid_chars(self):
        """Test calculator rejects invalid characters"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "calculator",
                "arguments": json.dumps({"expression": "import os"})
            }
        })
        
        self.assertFalse(result["success"])
        self.assertIn("error", result["result"])
    
    def test_search_restaurants(self):
        """Test restaurant search returns results"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "search_restaurants",
                "arguments": json.dumps({"location": "Jakarta", "cuisine": "Italian"})
            }
        })
        
        self.assertTrue(result["success"])
        self.assertIn("restaurants", result["result"])
        self.assertIsInstance(result["result"]["restaurants"], list)
    
    def test_search_restaurants_with_rating(self):
        """Test restaurant search with min rating filter"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "search_restaurants",
                "arguments": json.dumps({"location": "Jakarta", "min_rating": 4.5})
            }
        })
        
        self.assertTrue(result["success"])
        # All returned restaurants should have rating >= 4.5
        for r in result["result"]["restaurants"]:
            self.assertGreaterEqual(r["rating"], 4.5)
    
    def test_search_hotels(self):
        """Test hotel search returns results"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "search_hotels",
                "arguments": json.dumps({"location": "Bali"})
            }
        })
        
        self.assertTrue(result["success"])
        self.assertIn("hotels", result["result"])
        self.assertGreater(len(result["result"]["hotels"]), 0)
    
    def test_get_order_existing(self):
        """Test get order for existing customer"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "get_order",
                "arguments": json.dumps({"customer_id": 123})
            }
        })
        
        self.assertTrue(result["success"])
        self.assertIn("order", result["result"])
        self.assertIsNotNone(result["result"]["order"])
    
    def test_get_order_not_found(self):
        """Test get order for non-existing customer"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "get_order",
                "arguments": json.dumps({"customer_id": 99999})
            }
        })
        
        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["status"], "not_found")
    
    def test_send_notification(self):
        """Test send notification returns success"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "send_notification",
                "arguments": json.dumps({
                    "email": "test@example.com",
                    "message": "Hello, this is a test notification"
                })
            }
        })
        
        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["status"], "sent")
        self.assertIn("notification_id", result["result"])
    
    def test_unknown_tool_fallback(self):
        """Test unknown tool returns error"""
        result = tool_framework.execute_tool({
            "id": "call_1",
            "function": {
                "name": "unknown_function",
                "arguments": json.dumps({"arg1": "value1"})
            }
        })
        
        self.assertFalse(result["success"])
        self.assertIn("error", result["result"])
        self.assertIn("Unknown tool", result["result"]["error"])
    
    def test_tool_call_id_preserved(self):
        """Test that tool call ID is preserved in result"""
        result = tool_framework.execute_tool({
            "id": "unique_call_123",
            "function": {
                "name": "get_weather",
                "arguments": json.dumps({"location": "Bali"})
            }
        })
        
        self.assertEqual(result["tool_call_id"], "unique_call_123")


class TestToolFrameworkDefinitions(unittest.TestCase):
    """Test tool framework definitions"""
    
    def test_tools_defined(self):
        """Test that tools are defined"""
        self.assertIsNotNone(tool_framework.tools)
        self.assertGreater(len(tool_framework.tools), 0)
    
    def test_tool_format(self):
        """Test tools follow OpenAI format"""
        for tool in tool_framework.tools:
            self.assertEqual(tool["type"], "function")
            self.assertIn("function", tool)
            self.assertIn("name", tool["function"])
            self.assertIn("description", tool["function"])
            self.assertIn("parameters", tool["function"])
    
    def test_required_tools_exist(self):
        """Test that commonly used tools exist"""
        tool_names = [t["function"]["name"] for t in tool_framework.tools]
        
        expected_tools = [
            "get_weather",
            "search_restaurants",
            "search_hotels",
            "calculator",
            "get_order",
            "send_notification"
        ]
        
        for expected in expected_tools:
            self.assertIn(expected, tool_names, f"Missing tool: {expected}")


if __name__ == "__main__":
    unittest.main()
