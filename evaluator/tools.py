import json
import sqlite3
import requests
from typing import Dict, Any, Optional
import config

class ToolFramework:
    def __init__(self):
        self.tools = self._get_tools_definition()
    
    def _get_tools_definition(self) -> list:
        """Get OpenAI-compatible tool definitions"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather information for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name or location"
                            }
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_restaurants",
                    "description": "Search for restaurants by criteria",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cuisine": {
                                "type": "string",
                                "description": "Type of cuisine (Italian, Japanese, etc.)"
                            },
                            "location": {
                                "type": "string",
                                "description": "City or area"
                            },
                            "min_rating": {
                                "type": "number",
                                "description": "Minimum rating (1-5)"
                            }
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_hotels",
                    "description": "Search for hotels in a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City or area"
                            },
                            "check_in": {
                                "type": "string",
                                "description": "Check-in date (YYYY-MM-DD)"
                            },
                            "check_out": {
                                "type": "string",
                                "description": "Check-out date (YYYY-MM-DD)"
                            }
                        },
                        "required": ["location"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_order",
                    "description": "Get order details by customer ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_id": {
                                "type": "integer",
                                "description": "Customer ID"
                            }
                        },
                        "required": ["customer_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "send_notification",
                    "description": "Send notification to a user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email": {
                                "type": "string",
                                "description": "Email address"
                            },
                            "message": {
                                "type": "string",
                                "description": "Notification message"
                            }
                        },
                        "required": ["email", "message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "Perform mathematical calculations",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Mathematical expression to evaluate"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "database_query",
                    "description": "Execute SQL query against the test database",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "SQL query to execute"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "api_call",
                    "description": "Make HTTP API call",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "API endpoint URL"
                            },
                            "method": {
                                "type": "string",
                                "enum": ["GET", "POST", "PUT", "DELETE"],
                                "description": "HTTP method"
                            },
                            "data": {
                                "type": "object",
                                "description": "Request data (for POST/PUT)"
                            }
                        },
                        "required": ["url", "method"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "file_create",
                    "description": "Create a new file with content",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "Name of the file to create"
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to write to the file"
                            }
                        },
                        "required": ["filename", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "file_edit",
                    "description": "Edit an existing file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {
                                "type": "string",
                                "description": "Name of the file to edit"
                            },
                            "operation": {
                                "type": "string",
                                "enum": ["append", "prepend", "replace"],
                                "description": "Edit operation"
                            },
                            "content": {
                                "type": "string",
                                "description": "Content to add or replace"
                            }
                        },
                        "required": ["filename", "operation", "content"]
                    }
                }
            }
        ]
    
    def execute_tool(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool call"""
        function_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"])
        
        try:
            if function_name == "calculator":
                result = self._calculator(arguments)
            elif function_name == "database_query":
                result = self._database_query(arguments)
            elif function_name == "api_call":
                result = self._api_call(arguments)
            elif function_name == "file_create":
                result = self._file_create(arguments)
            elif function_name == "file_edit":
                result = self._file_edit(arguments)
            elif function_name == "get_weather":
                result = self._get_weather(arguments)
            elif function_name == "search_restaurants":
                result = self._search_restaurants(arguments)
            elif function_name == "search_hotels":
                result = self._search_hotels(arguments)
            elif function_name == "get_order":
                result = self._get_order(arguments)
            elif function_name == "send_notification":
                result = self._send_notification(arguments)
            else:
                result = {"error": f"Unknown tool: {function_name}"}
            
            return {
                "tool_call_id": tool_call["id"],
                "function_name": function_name,
                "result": result,
                "success": "error" not in result
            }
            
        except Exception as e:
            return {
                "tool_call_id": tool_call["id"],
                "function_name": function_name,
                "result": {"error": str(e)},
                "success": False
            }
    
    def _calculator(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute mathematical calculation"""
        expression = args["expression"]
        
        # Basic safety: only allow math operations
        allowed_chars = set("0123456789+-*/.() ")
        if not all(c in allowed_chars for c in expression):
            return {"error": "Invalid characters in expression"}
        
        try:
            result = eval(expression, {"__builtins__": {}})
            return {"result": result, "expression": expression}
        except Exception as e:
            return {"error": f"Calculation error: {str(e)}"}
    
    def _database_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute SQL query against test database"""
        query = args["query"]
        
        # Basic safety check
        if any(keyword in query.upper() for keyword in ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER"]):
            return {"error": "Query contains potentially dangerous operations"}
        
        try:
            with sqlite3.connect(config.TEST_DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query)
                
                if query.strip().upper().startswith("SELECT"):
                    rows = cursor.fetchall()
                    result = [dict(row) for row in rows]
                    return {"result": result, "row_count": len(result)}
                else:
                    conn.commit()
                    return {"result": "Query executed successfully", "affected_rows": cursor.rowcount}
                    
        except Exception as e:
            return {"error": f"Database error: {str(e)}"}
    
    def _api_call(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Make mock API call (simulated)"""
        url = args["url"]
        method = args["method"]
        data = args.get("data", {})
        
        # Mock responses for common endpoints
        mock_responses = {
            "https://api.example.com/users": {"users": [{"id": 1, "name": "John Doe"}]},
            "https://api.example.com/products": {"products": [{"id": 1, "name": "Product A", "price": 100}]},
            "https://api.example.com/orders": {"orders": [{"id": 1, "status": "completed"}]}
        }
        
        if url in mock_responses:
            return {"response": mock_responses[url], "status": "success"}
        else:
            return {"error": f"Mock API endpoint not found: {url}", "status": "not_found"}
    
    def _file_create(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new file"""
        filename = args["filename"]
        content = args["content"]
        
        # Restrict to safe directory
        safe_dir = "/tmp/llm_eval_files/"
        import os
        os.makedirs(safe_dir, exist_ok=True)
        
        filepath = os.path.join(safe_dir, filename)
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            return {"filepath": filepath, "status": "created"}
        except Exception as e:
            return {"error": f"File creation error: {str(e)}"}
    
    def _file_edit(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Edit an existing file"""
        filename = args["filename"]
        operation = args["operation"]
        content = args["content"]
        
        safe_dir = "/tmp/llm_eval_files/"
        import os
        filepath = os.path.join(safe_dir, filename)
        
        if not os.path.exists(filepath):
            return {"error": "File does not exist"}
        
        try:
            if operation == "append":
                with open(filepath, 'a') as f:
                    f.write(content)
            elif operation == "prepend":
                with open(filepath, 'r+') as f:
                    existing = f.read()
                    f.seek(0)
                    f.write(content + existing)
            elif operation == "replace":
                with open(filepath, 'w') as f:
                    f.write(content)
            
            return {"filepath": filepath, "operation": operation, "status": "success"}
            
        except Exception as e:
            return {"error": f"File edit error: {str(e)}"}
    
    def _get_weather(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get mock weather data"""
        location = args.get("location", "Unknown")
        # Mock weather responses
        weather_data = {
            "jakarta": {"temp": 32, "condition": "Cerah berawan", "humidity": 75},
            "bali": {"temp": 30, "condition": "Cerah", "humidity": 70},
            "yogyakarta": {"temp": 29, "condition": "Berawan", "humidity": 80},
            "surabaya": {"temp": 33, "condition": "Panas", "humidity": 65},
        }
        loc_lower = location.lower()
        if loc_lower in weather_data:
            return {"location": location, "weather": weather_data[loc_lower], "status": "success"}
        return {"location": location, "weather": {"temp": 28, "condition": "Normal", "humidity": 70}, "status": "success"}
    
    def _search_restaurants(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search mock restaurants"""
        cuisine = args.get("cuisine", "any")
        location = args.get("location", "Jakarta")
        min_rating = args.get("min_rating", 0)
        
        # Mock restaurant data
        restaurants = [
            {"name": "Ristorante Italia", "cuisine": "Italian", "rating": 4.5, "location": "Jakarta"},
            {"name": "Sushi Tei", "cuisine": "Japanese", "rating": 4.2, "location": "Jakarta"},
            {"name": "Warung Padang", "cuisine": "Indonesian", "rating": 4.8, "location": "Jakarta"},
        ]
        
        filtered = [r for r in restaurants if r["rating"] >= min_rating]
        if cuisine.lower() != "any":
            filtered = [r for r in filtered if cuisine.lower() in r["cuisine"].lower()]
        
        return {"restaurants": filtered, "count": len(filtered), "status": "success"}
    
    def _search_hotels(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search mock hotels"""
        location = args.get("location", "Bali")
        
        # Mock hotel data
        hotels = [
            {"name": "Grand Hyatt", "location": "Bali", "rating": 4.8, "price_per_night": 2500000},
            {"name": "Ayana Resort", "location": "Bali", "rating": 4.9, "price_per_night": 3000000},
            {"name": "Alila Villas", "location": "Bali", "rating": 4.7, "price_per_night": 2800000},
        ]
        
        return {"hotels": hotels, "location": location, "count": len(hotels), "status": "success"}
    
    def _get_order(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get mock order data"""
        customer_id = args.get("customer_id", 0)
        
        # Mock order data
        orders = {
            123: {"order_id": "ORD-001", "items": ["Laptop", "Mouse"], "total": 15000000, "status": "shipped"},
            456: {"order_id": "ORD-002", "items": ["Phone"], "total": 8000000, "status": "delivered"},
        }
        
        if customer_id in orders:
            return {"customer_id": customer_id, "order": orders[customer_id], "status": "success"}
        return {"customer_id": customer_id, "order": None, "status": "not_found"}
    
    def _send_notification(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Send mock notification"""
        email = args.get("email", "")
        message = args.get("message", "")
        
        # Mock: just return success
        return {"email": email, "message_preview": message[:50], "status": "sent", "notification_id": "NOTIF-12345"}

# Global tool framework instance
tool_framework = ToolFramework()