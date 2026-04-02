import requests
import json
import time
import re
from typing import Dict, Any, Optional, Tuple
import config

def strip_thinking_tags(content: str) -> Tuple[str, Optional[str]]:
    """
    Strip thinking tags (<tool_call>...`) from content.
    
    Returns:
        Tuple of (cleaned_content, thinking_content)
        - cleaned_content: content without thinking tags
        - thinking_content: the extracted thinking content (or None if no thinking tags)
    """
    if not content:
        return content, None
    
    # Pattern to match thinking tags (non-greedy)
    thinking_pattern = r'<think>(.*?)</think>'
    
    # Find all thinking blocks
    thinking_matches = re.findall(thinking_pattern, content, re.DOTALL)
    
    # Remove thinking tags from content
    cleaned = re.sub(thinking_pattern, '', content, flags=re.DOTALL)
    
    # Clean up extra whitespace
    cleaned = cleaned.strip()
    
    thinking_content = '\n'.join(thinking_matches) if thinking_matches else None
    
    return cleaned, thinking_content


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
            "max_tokens": 4096  # Increased for reasoning models that need tokens for thinking
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
                return {
                    "response": {"error": f"LLM API error: {response.status_code} - {response.text[:200]}"},
                    "duration_ms": duration_ms,
                    "success": False,
                    "error_type": "api_error"
                }
            
            result = response.json()
            
            if "error" in result:
                return {
                    "response": result,
                    "duration_ms": duration_ms,
                    "success": False,
                    "error_type": "llm_error"
                }
            
            # Check for empty content with finish_reason=length (generation timeout)
            choices = result.get("choices", [])
            if choices:
                finish_reason = choices[0].get("finish_reason")
                message = choices[0].get("message", {})
                content = message.get("content", "")
                reasoning = message.get("reasoning_content", "")
                
                if finish_reason == "length" and not content:
                    # Generation hit max_tokens without producing final answer
                    return {
                        "response": result,
                        "duration_ms": duration_ms,
                        "success": False,
                        "error_type": "generation_timeout",
                        "error_detail": f"Generation hit max_tokens limit ({payload['max_tokens']}) without producing final answer. The model was still reasoning when cutoff occurred. Reasoning length: {len(reasoning)} chars."
                    }
            
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
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "response": {"error": f"Request timeout after {self.timeout}s (elapsed: {elapsed_ms}ms)"},
                "duration_ms": elapsed_ms,
                "success": False,
                "error_type": "request_timeout",
                "error_detail": f"HTTP request timed out after {self.timeout} seconds. The LLM server did not respond within the timeout limit."
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "response": {"error": f"Connection error: {str(e)[:100]}"},
                "duration_ms": 0,
                "success": False,
                "error_type": "connection_error",
                "error_detail": f"Could not connect to LLM server at {self.base_url}. Check if the server is running."
            }
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000) if 'start_time' in locals() else 0
            return {
                "response": {"error": str(e)[:200]},
                "duration_ms": elapsed_ms,
                "success": False,
                "error_type": "unknown_error",
                "error_detail": str(e)
            }
    
    def extract_content(self, response: Dict[str, Any], strip_thinking: bool = True) -> str:
        """
        Extract text content from LLM response.
        
        Args:
            response: The LLM response dict
            strip_thinking: If True, strip content inside <tool_call>...` tags (for thinking models)
        
        Returns:
            The extracted content (with or without thinking tags)
        """
        if not response.get("success"):
            error_msg = response['response'].get('error', 'Unknown error')
            error_detail = response.get('error_detail', '')
            if error_detail:
                return f"Error: {error_msg}\n\nDetails: {error_detail}"
            return f"Error: {error_msg}"
        
        choices = response["response"].get("choices", [])
        if not choices:
            return "No response generated"
        
        message = choices[0].get("message", {})
        
        # Check for tool calls
        tool_calls = message.get("tool_calls")
        if tool_calls:
            return json.dumps({"tool_calls": tool_calls}, indent=2)
        
        # Return text content (fallback to reasoning_content if content is empty)
        content = message.get("content", "")
        if not content:
            # Mars endpoint may return answer in reasoning_content
            content = message.get("reasoning_content", "")
        
        if not content:
            return "No content generated"
        
        # Strip thinking tags if requested
        if strip_thinking:
            cleaned, _ = strip_thinking_tags(content)
            return cleaned
        
        return content
    
    def extract_content_with_thinking(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract both thinking and final content from LLM response.
        
        Returns:
            Dict with:
            - content: final content (without thinking tags)
            - thinking: thinking content (or None)
            - raw: original content with thinking tags
        """
        if not response.get("success"):
            return {
                "content": self.extract_content(response),
                "thinking": None,
                "raw": None
            }
        
        choices = response["response"].get("choices", [])
        if not choices:
            return {"content": "No response generated", "thinking": None, "raw": None}
        
        message = choices[0].get("message", {})
        raw_content = message.get("content", "") or message.get("reasoning_content", "")
        
        if not raw_content:
            return {"content": "No content generated", "thinking": None, "raw": None}
        
        cleaned, thinking = strip_thinking_tags(raw_content)
        
        return {
            "content": cleaned,
            "thinking": thinking,
            "raw": raw_content
        }
    
    def get_error_info(self, response: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Get error information from failed response"""
        if response.get("success"):
            return None
        
        return {
            "type": response.get("error_type", "unknown"),
            "message": response["response"].get("error", "Unknown error") if isinstance(response.get("response"), dict) else str(response.get("response")),
            "detail": response.get("error_detail", ""),
            "duration_ms": response.get("duration_ms", 0)
        }
    
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