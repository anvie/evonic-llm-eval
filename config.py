import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# LLM Configuration (OpenAI-compatible endpoint)
# For OpenRouter: https://openrouter.ai/api/v1
# For local LLM: http://localhost:8080/v1
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")  # Set your OpenRouter API key
LLM_MODEL = os.getenv("LLM_MODEL", "moonshotai/kimi-k2-thinking")  # Model for evaluation
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "120"))

# Two-Pass Extraction Configuration
# PASS 1: LLM generates answer with reasoning
# PASS 2: LLM extracts ONLY the final answer in strict format
TWO_PASS_ENABLED = os.getenv("TWO_PASS_ENABLED", "1") == "1"
TWO_PASS_TEMPERATURE = float(os.getenv("TWO_PASS_TEMPERATURE", "0.0"))

# Domain Evaluator Configuration
# Override default evaluator for specific domains
# Available types: two_pass, keyword, sql_executor, tool_call
# Example: EVALUATOR_MATH=keyword would use keyword matching for math (not recommended)
EVALUATOR_OVERRIDES = {
    # "math": "keyword",        # Override math to use keyword evaluator
    # "conversation": "two_pass",  # Override conversation to use two-pass
}

def get_evaluator_type(domain: str) -> str:
    """Get configured evaluator type for domain"""
    # Check environment variable first
    env_key = f"EVALUATOR_{domain.upper()}"
    env_value = os.getenv(env_key)
    if env_value:
        return env_value.lower()
    
    # Check config overrides
    if domain in EVALUATOR_OVERRIDES:
        return EVALUATOR_OVERRIDES[domain].lower()
    
    return "default"

# Database paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "evaluation.db")
TEST_DB_PATH = os.path.join(BASE_DIR, "seed", "test_db.sqlite")

# Flask
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
DEBUG = os.getenv("DEBUG", "1") == "1"

# Real-time log verbosity
LOG_FULL_THINKING = os.getenv("LOG_FULL_THINKING", "0") == "1"
LOG_FULL_RESPONSE = os.getenv("LOG_FULL_RESPONSE", "0") == "1"

# LLM API call logging (to markdown file)
LLM_API_LOG_ENABLED = os.getenv("LLM_API_LOG_ENABLED", "0") == "1"
LLM_API_LOG_FILE = os.getenv("LLM_API_LOG_FILE", os.path.join(BASE_DIR, "logs", "llm_api_calls.md"))
