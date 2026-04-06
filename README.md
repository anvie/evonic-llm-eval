# Evonic LLM Evaluator

A web-based application to evaluate the capabilities of Large Language Models (LLMs) across multiple domains with configurable complexity levels.

## Key Features

- **Multi-Domain Evaluation**: Configurable domains (conversation, math, SQL, tool calling, reasoning, health, needle-in-haystack, etc.) with 5 complexity levels each
- **Real-time Web Interface**: Live progress updates with color-coded matrix grid
- **OpenAI-Compatible API**: Works with any local LLM (llama.cpp, Ollama, vLLM) or cloud providers (OpenRouter, etc.)
- **Pluggable Evaluator System**: Keyword matching, regex, two-pass extraction, LLM-as-judge, and custom hybrid evaluators
- **Tool Calling Framework**: OpenAI JSON schema support with mock tool responses (JSON or JavaScript)
- **SQL Execution Engine**: Real SQLite database with sample data for SQL generation tests
- **3-Layer System Prompt Hierarchy**: Domain, level, and test-level system prompts with overwrite/append modes
- **Test Management UI**: Create, edit, and organize test definitions via the settings page
- **Historical Tracking**: Full persistence of all runs with detailed per-test results
- **Training Data Generation**: Export test results as Gemma 4 format JSONL for fine-tuning
- **Headless Mode**: Run evaluations from CLI via `run_headless.py`
- **Indonesian Language Support**: Native support for Indonesian language evaluation

## Getting Started

### Prerequisites

1. **Python 3.8+**
2. **A local LLM server** or cloud API endpoint (OpenAI-compatible `/v1/chat/completions`)

### Installation

```bash
git clone <your-repo-url> evonic-llm-eval
cd evonic-llm-eval
pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and configure your LLM endpoint:

```bash
cp .env.example .env
```

```env
# For local LLM (llama.cpp, Ollama)
LLM_BASE_URL=http://localhost:8080/v1
LLM_API_KEY=
LLM_MODEL=default

# For OpenRouter / cloud providers
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-api-key-here
LLM_MODEL=moonshotai/kimi-k2-thinking
```

See `.env.example` for all available configuration keys.

### Starting the Application

```bash
python3 app.py
```

Open your browser to `http://localhost:8080`.

### Headless Mode (CLI)

```bash
python3 run_headless.py --endpoint http://localhost:8080/v1 --model default
```

## How It Works

### Test Definitions

Tests are defined as JSON files organized by domain and level:

```
test_definitions/
├── conversation/
│   ├── domain.json
│   ├── level_1/
│   │   └── simple_greeting.json
│   └── level_2/
│       └── geography.json
├── health/
├── needle_in_haystack/
├── evaluators/          # Evaluator configs (keyword, regex, two_pass, etc.)
└── tools/               # Tool definitions with mock responses
```

Each test specifies a prompt, expected output, and which evaluator to use. Create and manage tests through the **Settings** page (`/settings`).

### Evaluators

| Evaluator | Type | Description |
|-----------|------|-------------|
| **Keyword** | predefined | Scores based on keyword presence, relevance, and fluency |
| **Two-Pass** | predefined | LLM generates answer, then extracts final value for comparison |
| **Regex Matcher** | regex | Matches response against regex pattern in expected field |
| **Natural Text Compare** | custom | LLM judge compares expected text vs response (1-3 scale) |
| **Tool Call** | predefined | Validates tool calls against expected tools and arguments |
| **SQL Executor** | predefined | Executes generated SQL and compares results |
| **Hybrid Quality Rater** | hybrid | LLM evaluates quality, regex extracts score |

Custom evaluators can be created via the Settings page with configurable eval prompts, regex patterns, and scoring configs.

### System Prompt Hierarchy

System prompts resolve in 3 layers: **Domain** -> **Level** -> **Test**, with each layer supporting `overwrite` (replace) or `append` (concatenate) modes.

## API Endpoints

### Evaluation
- `POST /api/start` - Start evaluation
- `POST /api/stop` - Stop evaluation
- `GET /api/status` - Get current status

### Results
- `GET /api/run/<run_id>/matrix` - Get full result matrix
- `GET /api/run/<run_id>/tests/<domain>/<level>` - Get per-test results
- `GET /api/v1/history/<run_id>/<domain>/<level>` - Get historical test results
- `DELETE /api/history/<run_id>` - Delete a run

### Test Management
- `GET/POST /api/settings/domains` - List/create domains
- `GET/POST /api/settings/tests` - List/create tests
- `GET/POST /api/settings/evaluators` - List/create evaluators
- `GET/POST /api/settings/tools` - List/create tools
- `GET /api/settings/export` - Export all definitions
- `POST /api/settings/import` - Import definitions

## Requirements

- **Python** 3.8+
- **Flask** >= 3.0
- **Requests** >= 2.31
- **python-dotenv**
- **anthropic** (optional, for improver module)
- Any **OpenAI-compatible LLM endpoint**

## License

MIT License
