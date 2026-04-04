import requests
import json
import time
import re
from typing import Dict, Any, Optional, Tuple
import config

# Import Gemma 4 parser for auto-detection
from evaluator.gemma4_parser import is_gemma4_format, strip_gemma4_thinking

def strip_thinking_tags(content: str) -> Tuple[str, Optional[str]]:
    """
    Strip thinking tags from content with auto-format detection.
    
    Supports:
    - Standard: <think>...</think>
    - Gemma 4: <|channel>thought...<channel|>
    
    Auto-detects format and uses appropriate parser.
    
    Returns:
        Tuple of (cleaned_content, thinking_content)
        - cleaned_content: content without thinking tags
        - thinking_content: the extracted thinking content (or None if no thinking tags)
    """
    if not content:
        return content, None
    
    # Auto-detect Gemma 4 format
    if is_gemma4_format(content):
        return strip_gemma4_thinking(content)
    
    # Standard format: <think>...</think>
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
        self._cached_model_name = None
    
    def get_actual_model_name(self, force_refresh: bool = False) -> str:
        """
        Get the actual model name from the remote endpoint.
        
        For llama.cpp servers, this fetches from /props endpoint.
        Falls back to config model name if endpoint is unavailable.
        
        Args:
            force_refresh: If True, bypass cache and fetch fresh
            
        Returns:
            The actual model name from the server, or config fallback
        """
        if self._cached_model_name and not force_refresh:
            return self._cached_model_name
        
        # Try llama.cpp specific /props endpoint first
        try:
            props_url = f"{self.base_url.rstrip('/v1')}/props"
            response = requests.get(props_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "model_alias" in data:
                    self._cached_model_name = data["model_alias"]
                    return self._cached_model_name
        except Exception:
            pass
        
        # Try OpenAI-compatible /v1/models endpoint
        try:
            models_url = f"{self.base_url}/models"
            response = requests.get(models_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Handle different response formats
                if "data" in data and data["data"]:
                    self._cached_model_name = data["data"][0].get("id", self.model)
                    return self._cached_model_name
                elif "models" in data and data["models"]:
                    self._cached_model_name = data["models"][0].get("name", self.model)
                    return self._cached_model_name
        except Exception:
            pass
        
        # Fallback to config
        return self.model
    
    def chat_completion(self, messages: list, tools: Optional[list] = None, temperature: float = 0.1, enable_thinking: bool = True) -> Dict[str, Any]:
        """Send chat completion request to OpenAI-compatible endpoint"""
        url = f"{self.base_url}/chat/completions"
        
        # For Gemma4 models, inject <|think|> token to activate thinking mode
        # This goes at the start of the first system/user message
        processed_messages = []
        thinking_injected = False
        # Use actual model name from endpoint for detection
        actual_model = self._cached_model_name or self.model or ""
        model_lower = actual_model.lower()
        is_gemma4 = 'gemma-4' in model_lower or 'gemma4' in model_lower or 'gemma-4-base' in model_lower
        
        # DEBUG: Log Gemma4 detection
        if config.DEBUG:
            print(f"[DEBUG] Model detection: cached={self._cached_model_name}, config={self.model}, is_gemma4={is_gemma4}, enable_thinking={enable_thinking}")
        
        for msg in messages:
            new_msg = msg.copy()
            if not thinking_injected and is_gemma4 and enable_thinking:
                role = msg.get('role', '')
                content = msg.get('content', '')
                # Inject think token at start of first user/system message
                if role in ('user', 'system') and content:
                    new_msg['content'] = '<|think|>\n' + content
                    thinking_injected = True
                    if config.DEBUG:
                        print(f"[DEBUG] Injected <|think|> token into {role} message")
            processed_messages.append(new_msg)
        
        payload = {
            "model": self.model,
            "messages": processed_messages,
            "temperature": temperature,
            "max_tokens": 4096  # Increased for reasoning models that need tokens for thinking
        }
        
        if tools:
            payload["tools"] = tools
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Only add Authorization header if API key is set
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
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
        
        Handles two formats:
        1. llama.cpp --reasoning mode: thinking in message.reasoning_content, answer in message.content
        2. Tag-based thinking: <think>...</think> or <|channel>thought...<channel|> in content
        
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
        content = message.get("content", "")
        reasoning_content = message.get("reasoning_content")  # llama.cpp --reasoning mode
        tool_calls = message.get("tool_calls")
        
        # Priority 0: Check for tool_calls in message (OpenAI format)
        if tool_calls:
            tool_content = json.dumps({"tool_calls": tool_calls}, indent=2)
            return {
                "content": tool_content,
                "thinking": reasoning_content,
                "raw": tool_content,
                "tool_calls": tool_calls
            }
        
        # Priority 0.5: Check for Gemma4 tool calls in content
        if content and '<|tool_call>' in content:
            from evaluator.gemma4_parser import extract_gemma4_tool_calls, gemma4_tool_calls_to_openai_format
            gemma4_calls = extract_gemma4_tool_calls(content)
            if gemma4_calls:
                openai_calls = gemma4_tool_calls_to_openai_format(gemma4_calls)
                tool_content = json.dumps({"tool_calls": openai_calls}, indent=2)
                return {
                    "content": tool_content,
                    "thinking": reasoning_content,
                    "raw": content,
                    "tool_calls": openai_calls
                }
        
        # Priority 1: llama.cpp reasoning_content field (from --reasoning on)
        if reasoning_content:
            return {
                "content": content or "No content generated",
                "thinking": reasoning_content,
                "raw": content
            }
        
        # Priority 2: Tag-based thinking extraction (<think> or Gemma4 format)
        if content:
            cleaned, thinking = strip_thinking_tags(content)
            return {
                "content": cleaned,
                "thinking": thinking,
                "raw": content
            }
        
        return {"content": "No content generated", "thinking": None, "raw": None}
    
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