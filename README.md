# Evonic LLM Evaluator

A fully working end-to-end web-based application to evaluate the capabilities of Large Language Models (LLMs) across 5 domains with 5 levels of complexity each.

## Description

Evonic LLM Evaluator is a comprehensive testing framework designed to systematically evaluate Large Language Models across multiple capability domains. The system provides a standardized way to measure LLM performance through 25 carefully designed tests spanning conversation, mathematical reasoning, SQL generation, tool calling, and logical reasoning capabilities.

The application features a real-time web interface built with Flask and Jinja templates, providing immediate visual feedback during evaluation runs. All results are persisted in SQLite for historical comparison and analysis.

## Key Features

- **Multi-Domain Evaluation**: 5 domains × 5 complexity levels = 25 comprehensive tests
- **Real-time Web Interface**: Live progress updates with color-coded status grid
- **OpenAI-Compatible API**: Works with any local LLM (llama.cpp, Ollama, vLLM, etc.)
- **Tool Calling Framework**: Full OpenAI JSON schema support with 5 executable tools
- **SQL Execution Engine**: Real SQLite database with Indonesian business sample data
- **Automated Scoring**: Domain-specific scoring rubrics and exact match validation
- **Executive Summaries**: LLM-generated evaluation summaries after each run
- **Historical Tracking**: Complete persistence of all test results for comparison
- **Indonesian Language Support**: Native support for Indonesian language evaluation

## Features

- **5 Evaluation Domains**: Conversation, Math, SQL Generation, Tool Calling, Reasoning
- **5 Complexity Levels**: Level 1 (simplest) to Level 5 (most complex)
- **Real-time Web Interface**: Jinja-based SSR with auto-polling
- **OpenAI-compatible API**: Works with any local LLM (llama.cpp, Ollama, etc.)
- **Tool Calling Framework**: Calculator, Database Query, API Calls, File Operations
- **SQL Execution**: Real SQLite database with sample data
- **Persistence**: SQLite storage of all test results
- **Executive Summary**: LLM-generated evaluation summary

## Project Structure

```
evonic-llm-eval/
├── app.py                 # Flask application
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── models/
│   └── db.py            # Database models and persistence
├── evaluator/
│   ├── engine.py        # Test execution engine
│   ├── llm_client.py    # OpenAI-compatible API client
│   ├── tools.py         # Tool calling framework
│   ├── sql_executor.py  # Safe SQL execution
│   └── scoring.py       # Scoring and evaluation
├── tests/
│   ├── __init__.py      # Test registry
│   ├── base.py          # Base test class
│   ├── conversation.py  # Indonesian Q&A tests
│   ├── math.py          # Mathematical calculations
│   ├── sql_gen.py       # SQL generation
│   ├── tool_calling.py  # Function calling
│   └── reasoning.py     # Logical reasoning
├── seed/
│   └── test_db.sqlite   # Sample database for SQL tests
├── static/
│   └── style.css        # CSS styles
└── templates/
    ├── base.html        # Base template
    ├── index.html       # Main dashboard
    └── history.html     # Evaluation history
```

## Getting Started

### Prerequisites

1. **Install Python 3.8+** if not already installed:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3 python3-pip
   
   # macOS
   brew install python
   
   # Windows
   # Download from python.org or use Windows Store
   ```

2. **Install required Python packages**:
   ```bash
   pip install flask requests
   ```

3. **Set up your local LLM** (choose one):
   
   **Option A: Using Ollama**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Pull a model
   ollama pull llama3
   
   # Start Ollama (runs on http://localhost:11434)
   ollama serve
   ```
   
   **Option B: Using llama.cpp**
   ```bash
   # Build llama.cpp
   git clone https://github.com/ggerganov/llama.cpp
   cd llama.cpp
   make
   
   # Download a model and start server
   ./server -m ./models/llama-3.1-8b-instruct.Q4_K_M.gguf --host 0.0.0.0 --port 8080
   ```

### Installation

1. **Clone or download the project**:
   ```bash
   cd ~/dev
   git clone <your-repo-url> evonic-llm-eval
   cd evonic-llm-eval
   ```

2. **Verify the test database** is created:
   ```bash
   ls -la seed/test_db.sqlite
   # Should show the database file (~20KB)
   ```

3. **Configure your LLM endpoint** (edit `config.py` or set environment variables):
   ```bash
   # For Ollama
   export LLM_BASE_URL="http://localhost:11434"
   export LLM_API_KEY="not-needed"
   export LLM_MODEL="llama3"
   
   # For llama.cpp
   export LLM_BASE_URL="http://localhost:8080"
   export LLM_API_KEY="not-needed"  
   export LLM_MODEL="default"
   ```

## Configuration

Edit `config.py` or set environment variables:

```bash
export LLM_BASE_URL="http://localhost:8080/v1"  # Your LLM API endpoint
export LLM_API_KEY="not-needed"                # API key if required
export LLM_MODEL="default"                     # Model name
export DEBUG=1                                  # Enable debug mode
```

## How to Use

### Starting the Application

1. **Ensure your LLM server is running** on the configured port
2. **Start the evaluation web app**:
   ```bash
   cd ~/dev/evonic-llm-eval
   python3 app.py
   ```
   
   You should see output like:
   ```
   * Serving Flask app 'app'
   * Debug mode: on
   * Running on http://0.0.0.0:5000
   ```

3. **Open your browser** to http://localhost:5000

### Running an Evaluation

1. **On the main dashboard**, you'll see:
   - Start/Stop evaluation buttons
   - Status indicator
   - Progress bar
   - 5×5 test matrix (empty initially)

2. **Click "Start Evaluation"** to begin testing
   - The system will run all 25 tests sequentially
   - Each cell in the matrix will update in real-time
   - Green = passed, Red = failed, Spinner = running

3. **Monitor progress**:
   - Watch the progress bar fill as tests complete
   - See scores update in each test cell (0-100%)
   - The page auto-refreshes every 2 seconds

4. **After completion**:
   - An executive summary will appear below the matrix
   - All results are saved to the SQLite database
   - You can view detailed results in the History page

### Viewing Results

1. **Current Run**: The dashboard shows the latest results
2. **History Page**: Visit http://localhost:5000/history to see all past runs
3. **Run Details**: Click any run ID to see detailed test-by-test results
4. **Export Data**: All data is stored in `evaluation.db` SQLite file

### Configuration Options

Edit `config.py` for advanced configuration:

```python
# LLM Configuration
LLM_BASE_URL = "http://localhost:11434"  # Ollama default
LLM_API_KEY = "not-needed"               # Most local LLMs don't need keys
LLM_MODEL = "llama3"                     # Model name
LLM_TIMEOUT = 120                        # Timeout in seconds

# Database paths
DB_PATH = "evaluation.db"                # Results database
TEST_DB_PATH = "seed/test_db.sqlite"     # Test SQL database

# Flask settings
HOST = "0.0.0.0"                        # Bind to all interfaces
PORT = 5000                             # Web server port
DEBUG = True                            # Debug mode
```

### API Usage

The system provides REST API endpoints for programmatic access:

```bash
# Get current status
curl http://localhost:5000/api/status

# Start evaluation
curl -X POST http://localhost:5000/api/start -H "Content-Type: application/json" -d '{"model_name":"llama3"}'

# Get test matrix
curl http://localhost:5000/api/test_matrix

# Get run details
curl http://localhost:5000/api/run/fcf9b967-5742-4dd4-a6bf-1208af6b6707
```

### Troubleshooting

**Common Issues:**

1. **LLM Connection Failed**:
   - Check your LLM server is running
   - Verify the base URL in config.py
   - Test with: `curl http://localhost:11434/v1/models`

2. **Module Not Found**:
   - Install missing packages: `pip install flask requests`

3. **Database Errors**:
   - Check file permissions for `*.db` and `*.sqlite` files
   - Delete corrupted databases to regenerate

4. **Port Already in Use**:
   - Change PORT in config.py or kill existing process
   - Use `lsof -i :5000` to find processes using port 5000

## Evaluation Domains

### 1. Conversation (Indonesian Q&A)
- Level 1: Simple introduction
- Level 2: Factual questions about Indonesia
- Level 3: Concept explanations
- Level 4: Contextual conversations
- Level 5: Complex reasoning in Indonesian

### 2. Mathematical Calculations
- Level 1: Basic arithmetic
- Level 2: Percentage calculations
- Level 3: Compound interest
- Level 4: Geometry problems
- Level 5: Multi-step word problems

### 3. SQL Generation
- Level 1: Simple SELECT queries
- Level 2: JOIN with WHERE clauses
- Level 3: GROUP BY aggregations
- Level 4: Subqueries and HAVING
- Level 5: Complex CTE + window functions

### 4. Tool Calling
- Level 1: Calculator usage
- Level 2: Database queries
- Level 3: API calls
- Level 4: File creation
- Level 5: Multi-step agent workflows

### 5. Logical Reasoning
- Level 1: Simple if-then logic
- Level 2: Sequence ordering
- Level 3: Constraint satisfaction
- Level 4: Deductive reasoning
- Level 5: Complex multi-step reasoning

## API Endpoints

- `GET /` - Main dashboard
- `GET /history` - Evaluation history
- `POST /api/start` - Start evaluation
- `POST /api/stop` - Stop evaluation
- `GET /api/status` - Get current status
- `GET /api/test_matrix` - Get test matrix
- `GET /api/run/<run_id>` - Get run details

## Technical Details

- **Backend**: Flask with Jinja templates
- **Database**: SQLite for persistence
- **LLM Integration**: OpenAI-compatible API format
- **Frontend**: Server-side rendered with JavaScript polling
- **Tool Calling**: OpenAI JSON schema format
- **SQL Execution**: Safe query validation and execution

## Requirements

### System Requirements
- **Python**: 3.8 or higher
- **Operating System**: Linux, macOS, or Windows (WSL recommended for Windows)
- **Memory**: Minimum 2GB RAM (4GB+ recommended)
- **Storage**: ~100MB for application + test data

### Python Dependencies
- **Flask** >= 3.0 - Web framework
- **Requests** >= 2.31 - HTTP client for API calls
- **SQLite3** - Built-in database support

### LLM Requirements
- **Local LLM Server**: llama.cpp, Ollama, vLLM, or any OpenAI-compatible API endpoint
- **API Compatibility**: Must support `/v1/chat/completions` endpoint
- **Model**: Any capable LLM (tested with Llama 3, Mistral, and similar models)

### Optional Dependencies
- **curl** or **wget** - For testing API endpoints
- **pip** - Python package manager

## License

MIT License