import requests
import json
import time
from typing import Dict, Any, Optional
import config

class LLMClient:
    def __init__(self):
        self.base_url = config.LLM_BASE_URL
        self.api_key = config.LLM_API_KEY
        self.model = config.LLM_MODEL
        self.timeout = config.LLM_TIMEOUT
    
    def chat_completion(self, messages: list, tools: Optional[list] = None, temperature: float = 0.1) -> Dict[str, Any]:
        """Send chat completion request to OpenAI-compatible endpoint"""
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2000
        }
        
        if tools:
            payload["tools"] = tools
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                url, 
                json=payload, 
                headers=headers, 
                timeout=self.timeout
            )
            duration_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code != 200:
                raise Exception(f"LLM API error: {response.status_code} - {response.text}")
            
            result = response.json()
            
            if "error" in result:
                raise Exception(f"LLM error: {result['error']}")
            
            # Extract token usage if available
            usage = result.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
            
            return {
                "response": result,
                "duration_ms": duration_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "success": True
            }
            
        except requests.exceptions.Timeout:
            return {
                "response": {"error": "Request timeout"},
                "duration_ms": self.timeout * 1000,
                "success": False
            }
        except requests.exceptions.ConnectionError:
            return {
                "response": {"error": "Connection error"},
                "duration_ms": 0,
                "success": False
            }
        except Exception as e:
            return {
                "response": {"error": str(e)},
                "duration_ms": 0,
                "success": False
            }
    
    def extract_content(self, response: Dict[str, Any]) -> str:
        """Extract text content from LLM response"""
        if not response.get("success"):
            return f"Error: {response['response'].get('error', 'Unknown error')}"
        
        choices = response["response"].get("choices", [])
        if not choices:
            return "No response generated"
        
        message = choices[0].get("message", {})
        
        # Check for tool calls
        tool_calls = message.get("tool_calls")
        if tool_calls:
            return json.dumps({"tool_calls": tool_calls}, indent=2)
        
        # Return text content
        return message.get("content", "No content generated")
    
    def extract_tool_calls(self, response: Dict[str, Any]) -> Optional[list]:
        """Extract tool calls from LLM response"""
        if not response.get("success"):
            return None
        
        choices = response["response"].get("choices", [])
        if not choices:
            return None
        
        message = choices[0].get("message", {})
        return message.get("tool_calls")

# Global LLM client instance
llm_client = LLMClient()