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

# Global tool framework instance
tool_framework = ToolFramework()