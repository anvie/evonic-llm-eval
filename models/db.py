import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
import config

class Database:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        self._init_tables()
    
    def _init_tables(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Evaluation runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    model_name TEXT,
                    summary TEXT,
                    overall_score REAL,
                    total_tokens INTEGER DEFAULT 0,
                    total_duration_ms INTEGER DEFAULT 0
                )
            """)
            
            # Test results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    model_name TEXT,
                    domain TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    prompt TEXT,
                    response TEXT,
                    expected TEXT,
                    score REAL,
                    status TEXT NOT NULL,
                    details TEXT,
                    duration_ms INTEGER,
                    FOREIGN KEY (run_id) REFERENCES evaluation_runs (run_id)
                )
            """)
            
            # Improvement cycles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS improvement_cycles (
                    cycle_id TEXT PRIMARY KEY,
                    base_run_id TEXT NOT NULL,
                    improved_run_id TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME,
                    status TEXT DEFAULT 'pending',
                    analysis TEXT,
                    training_data_path TEXT,
                    examples_count INTEGER,
                    comparison TEXT,
                    recommendation TEXT,
                    FOREIGN KEY (base_run_id) REFERENCES evaluation_runs (run_id),
                    FOREIGN KEY (improved_run_id) REFERENCES evaluation_runs (run_id)
                )
            """)
            
            # Generated training data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generated_training_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_id TEXT NOT NULL,
                    source_test_id INTEGER,
                    domain TEXT,
                    level INTEGER,
                    prompt TEXT,
                    response TEXT,
                    tool_calls TEXT,
                    rationale TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cycle_id) REFERENCES improvement_cycles (cycle_id),
                    FOREIGN KEY (source_test_id) REFERENCES test_results (id)
                )
            """)
            
            # ==================== Configurable Test System Tables ====================
            
            # Domains table (cache of domain.json files)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS domains (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    icon TEXT,
                    color TEXT,
                    evaluator_id TEXT,
                    system_prompt TEXT,
                    system_prompt_mode TEXT DEFAULT 'overwrite',
                    enabled BOOLEAN DEFAULT 1,
                    path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Levels table (cache of level.json files)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS levels (
                    domain_id TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    system_prompt TEXT,
                    system_prompt_mode TEXT DEFAULT 'overwrite',
                    path TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (domain_id, level),
                    FOREIGN KEY (domain_id) REFERENCES domains(id)
                )
            """)

            # Tests table (cache of test JSON files)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tests (
                    id TEXT PRIMARY KEY,
                    domain_id TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    system_prompt TEXT,
                    system_prompt_mode TEXT DEFAULT 'overwrite',
                    prompt TEXT NOT NULL,
                    expected TEXT,
                    evaluator_id TEXT,
                    timeout_ms INTEGER DEFAULT 30000,
                    weight REAL DEFAULT 1.0,
                    enabled BOOLEAN DEFAULT 1,
                    path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (domain_id) REFERENCES domains(id)
                )
            """)
            
            # Evaluators table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evaluators (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    description TEXT,
                    eval_prompt TEXT,
                    extraction_regex TEXT,
                    uses_pass2 BOOLEAN DEFAULT 0,
                    config TEXT,
                    path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Level scores (aggregated from multiple tests)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS level_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    average_score REAL NOT NULL,
                    total_tests INTEGER NOT NULL,
                    passed_tests INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
                )
            """)
            
            # Individual test results (new table for multi-test per level)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS individual_test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    test_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    prompt TEXT,
                    response TEXT,
                    expected TEXT,
                    score REAL,
                    status TEXT NOT NULL,
                    details TEXT,
                    duration_ms INTEGER,
                    model_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id),
                    FOREIGN KEY (test_id) REFERENCES tests(id)
                )
            """)
            
            # Tools registry table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tools (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    function_def TEXT NOT NULL,
                    mock_response TEXT,
                    mock_response_type TEXT DEFAULT 'json',
                    path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add system_prompt and system_prompt_mode columns to individual_test_results if they don't exist
            cursor.execute("PRAGMA table_info(individual_test_results)")
            itr_cols = [row[1] for row in cursor.fetchall()]
            if 'system_prompt' not in itr_cols:
                cursor.execute("ALTER TABLE individual_test_results ADD COLUMN system_prompt TEXT")
            if 'system_prompt_mode' not in itr_cols:
                cursor.execute("ALTER TABLE individual_test_results ADD COLUMN system_prompt_mode TEXT")

            # Add tool_ids column to domains, levels, tests if they don't exist
            for table in ('domains', 'levels', 'tests'):
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [row[1] for row in cursor.fetchall()]
                if 'tool_ids' not in cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN tool_ids TEXT")
            
            # Create indexes for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tests_domain ON tests(domain_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tests_level ON tests(domain_id, level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_level_scores_run ON level_scores(run_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_individual_results_run ON individual_test_results(run_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_individual_results_test ON individual_test_results(test_id)")
            
            conn.commit()
    
    def create_evaluation_run(self, model_name: str) -> str:
        """Create a new evaluation run and return run_id"""
        run_id = str(uuid.uuid4())
        started_at = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO evaluation_runs (run_id, started_at, model_name) VALUES (?, ?, ?)",
                (run_id, started_at, model_name)
            )
            conn.commit()
        
        return run_id
    
    def update_test_result(self, run_id: str, domain: str, level: int, **kwargs):
        """Update test result with various fields"""
        allowed_fields = {
            'model_name', 'prompt', 'response', 'expected', 'score', 
            'status', 'details', 'duration_ms'
        }
        
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return
        
        set_clause = ", ".join(f"{field} = ?" for field in updates.keys())
        values = list(updates.values()) + [run_id, domain, level]
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if row exists
            cursor.execute(
                "SELECT id FROM test_results WHERE run_id = ? AND domain = ? AND level = ?",
                (run_id, domain, level)
            )
            
            if cursor.fetchone():
                # Update existing
                cursor.execute(
                    f"UPDATE test_results SET {set_clause} WHERE run_id = ? AND domain = ? AND level = ?",
                    values
                )
            else:
                # Insert new
                columns = ['run_id', 'domain', 'level'] + list(updates.keys())
                placeholders = ', '.join(['?'] * len(columns))
                insert_values = [run_id, domain, level] + list(updates.values())
                
                cursor.execute(
                    f"INSERT INTO test_results ({', '.join(columns)}) VALUES ({placeholders})",
                    insert_values
                )
            
            conn.commit()
    
    def complete_evaluation_run(self, run_id: str, summary: str, overall_score: float, 
                                 total_tokens: int = 0, total_duration_ms: int = 0):
        """Mark evaluation run as completed"""
        completed_at = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE evaluation_runs 
                   SET completed_at = ?, summary = ?, overall_score = ?, 
                       total_tokens = ?, total_duration_ms = ? 
                   WHERE run_id = ?""",
                (completed_at, summary, overall_score, total_tokens, total_duration_ms, run_id)
            )
            conn.commit()
    
    def get_evaluation_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get evaluation run details"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM evaluation_runs WHERE run_id = ?",
                (run_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_test_results(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all test results for a run"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM test_results WHERE run_id = ? ORDER BY domain, level",
                (run_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_runs(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Get evaluation runs with pagination, ordered by most recent first"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT e.*,
                    (SELECT COUNT(*) FROM individual_test_results WHERE run_id = e.run_id) as test_count,
                    (SELECT COUNT(*) FROM individual_test_results WHERE run_id = e.run_id AND status = 'passed') as passed_count
                FROM evaluation_runs e
                ORDER BY e.started_at DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_runs_count(self) -> int:
        """Get total count of evaluation runs"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM evaluation_runs")
            return cursor.fetchone()[0]
    
    def get_run_stats(self, run_id: str) -> Dict[str, Any]:
        """Get statistics for a run"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Count tests by status
            cursor.execute(
                """
                SELECT status, COUNT(*) as count 
                FROM test_results 
                WHERE run_id = ? 
                GROUP BY status
                """,
                (run_id,)
            )
            status_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Average score
            cursor.execute(
                "SELECT AVG(score) FROM test_results WHERE run_id = ? AND score IS NOT NULL",
                (run_id,)
            )
            avg_score = cursor.fetchone()[0] or 0.0
            
            return {
                'status_counts': status_counts,
                'avg_score': avg_score,
                'total_tests': sum(status_counts.values())
            }
    
    # ==================== Improvement Cycles ====================
    
    def create_improvement_cycle(
        self, 
        cycle_id: str, 
        base_run_id: str,
        analysis: str = None,
        training_data_path: str = None,
        examples_count: int = 0
    ) -> str:
        """Create a new improvement cycle."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO improvement_cycles 
                   (cycle_id, base_run_id, status, analysis, training_data_path, examples_count)
                   VALUES (?, ?, 'training_data_ready', ?, ?, ?)""",
                (cycle_id, base_run_id, analysis, training_data_path, examples_count)
            )
            conn.commit()
        return cycle_id
    
    def complete_improvement_cycle(
        self,
        cycle_id: str,
        improved_run_id: str,
        comparison: str,
        recommendation: str
    ):
        """Mark improvement cycle as completed."""
        completed_at = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE improvement_cycles 
                   SET improved_run_id = ?, completed_at = ?, status = 'completed',
                       comparison = ?, recommendation = ?
                   WHERE cycle_id = ?""",
                (improved_run_id, completed_at, comparison, recommendation, cycle_id)
            )
            conn.commit()
    
    def get_improvement_cycle(self, cycle_id: str) -> Optional[Dict[str, Any]]:
        """Get improvement cycle details."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM improvement_cycles WHERE cycle_id = ?",
                (cycle_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_improvement_cycles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent improvement cycles."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM improvement_cycles ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def save_generated_training_data(
        self,
        cycle_id: str,
        examples: List[Dict[str, Any]]
    ):
        """Save generated training examples to database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for ex in examples:
                cursor.execute(
                    """INSERT INTO generated_training_data
                       (cycle_id, source_test_id, domain, level, prompt, response, tool_calls, rationale)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        cycle_id,
                        ex.get('source_test_id'),
                        ex.get('domain'),
                        ex.get('level'),
                        ex.get('prompt'),
                        ex.get('response'),
                        json.dumps(ex.get('tool_calls')) if ex.get('tool_calls') else None,
                        ex.get('rationale')
                    )
                )
            conn.commit()
    
    # ==================== Configurable Test System CRUD ====================
    
    # Domain operations
    def get_domains(self) -> List[Dict[str, Any]]:
        """Get all domains"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM domains ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_domain(self, domain_id: str) -> Optional[Dict[str, Any]]:
        """Get a single domain by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM domains WHERE id = ?", (domain_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def upsert_domain(self, domain: Dict[str, Any]) -> str:
        """Insert or update a domain"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            system_prompt = domain.get('system_prompt')
            system_prompt_mode = domain.get('system_prompt_mode', 'overwrite')
            cursor.execute("""
                INSERT INTO domains (id, name, description, icon, color, evaluator_id, system_prompt, system_prompt_mode, enabled, path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    icon = excluded.icon,
                    color = excluded.color,
                    evaluator_id = excluded.evaluator_id,
                    system_prompt = excluded.system_prompt,
                    system_prompt_mode = excluded.system_prompt_mode,
                    enabled = excluded.enabled,
                    path = excluded.path,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                domain['id'], domain.get('name'), domain.get('description'),
                domain.get('icon'), domain.get('color'), domain.get('evaluator_id'),
                system_prompt, system_prompt_mode, domain.get('enabled', True), domain.get('path')
            ))
            conn.commit()
        return domain['id']
    
    def delete_domain(self, domain_id: str) -> bool:
        """Delete a domain"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # First delete all tests in this domain
            cursor.execute("DELETE FROM tests WHERE domain_id = ?", (domain_id,))
            # Delete level definitions
            cursor.execute("DELETE FROM levels WHERE domain_id = ?", (domain_id,))
            # Then delete the domain
            cursor.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # Level operations
    def upsert_level(self, level_data: Dict[str, Any]) -> None:
        """Insert or update a level definition"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO levels (domain_id, level, system_prompt, system_prompt_mode, path, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(domain_id, level) DO UPDATE SET
                    system_prompt = excluded.system_prompt,
                    system_prompt_mode = excluded.system_prompt_mode,
                    path = excluded.path,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                level_data['domain_id'], level_data['level'],
                level_data.get('system_prompt'), level_data.get('system_prompt_mode', 'overwrite'),
                level_data.get('path')
            ))
            conn.commit()

    def get_level(self, domain_id: str, level: int) -> Optional[Dict[str, Any]]:
        """Get a single level definition"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM levels WHERE domain_id = ? AND level = ?",
                (domain_id, level)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_levels_for_domain(self, domain_id: str) -> List[Dict[str, Any]]:
        """Get all level definitions for a domain"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM levels WHERE domain_id = ? ORDER BY level",
                (domain_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_levels_for_domain(self, domain_id: str) -> None:
        """Delete all level definitions for a domain"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM levels WHERE domain_id = ?", (domain_id,))
            conn.commit()

    # Test operations
    def get_tests(self, domain_id: str = None, level: int = None) -> List[Dict[str, Any]]:
        """Get tests, optionally filtered by domain and level"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if domain_id and level:
                cursor.execute(
                    "SELECT * FROM tests WHERE domain_id = ? AND level = ? ORDER BY name",
                    (domain_id, level)
                )
            elif domain_id:
                cursor.execute(
                    "SELECT * FROM tests WHERE domain_id = ? ORDER BY level, name",
                    (domain_id,)
                )
            elif level:
                cursor.execute(
                    "SELECT * FROM tests WHERE level = ? ORDER BY domain_id, name",
                    (level,)
                )
            else:
                cursor.execute("SELECT * FROM tests ORDER BY domain_id, level, name")
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_test(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get a single test by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tests WHERE id = ?", (test_id,))
            row = cursor.fetchone()
            result = dict(row) if row else None
            if result and result.get('expected'):
                result['expected'] = json.loads(result['expected'])
            return result
    
    def upsert_test(self, test: Dict[str, Any]) -> str:
        """Insert or update a test"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            expected_json = json.dumps(test.get('expected')) if test.get('expected') else None
            system_prompt = test.get('system_prompt')
            system_prompt_mode = test.get('system_prompt_mode', 'overwrite')
            cursor.execute("""
                INSERT INTO tests (id, domain_id, level, name, description, system_prompt, system_prompt_mode, prompt, expected, evaluator_id, timeout_ms, weight, enabled, path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    domain_id = excluded.domain_id,
                    level = excluded.level,
                    name = excluded.name,
                    description = excluded.description,
                    system_prompt = excluded.system_prompt,
                    system_prompt_mode = excluded.system_prompt_mode,
                    prompt = excluded.prompt,
                    expected = excluded.expected,
                    evaluator_id = excluded.evaluator_id,
                    timeout_ms = excluded.timeout_ms,
                    weight = excluded.weight,
                    enabled = excluded.enabled,
                    path = excluded.path,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                test['id'], test['domain_id'], test['level'], test.get('name'),
                test.get('description'), system_prompt, system_prompt_mode, test['prompt'], expected_json,
                test.get('evaluator_id'), test.get('timeout_ms', 30000),
                test.get('weight', 1.0), test.get('enabled', True), test.get('path')
            ))
            conn.commit()
        return test['id']
    
    def delete_test(self, test_id: str) -> bool:
        """Delete a test"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tests WHERE id = ?", (test_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_tests_by_domain_level(self, domain_id: str, level: int) -> List[Dict[str, Any]]:
        """Get all tests for a specific domain and level"""
        return self.get_tests(domain_id=domain_id, level=level)
    
    # Evaluator operations
    def get_evaluators(self) -> List[Dict[str, Any]]:
        """Get all evaluators"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM evaluators ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_evaluator(self, evaluator_id: str) -> Optional[Dict[str, Any]]:
        """Get a single evaluator by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM evaluators WHERE id = ?", (evaluator_id,))
            row = cursor.fetchone()
            result = dict(row) if row else None
            if result and result.get('config'):
                result['config'] = json.loads(result['config'])
            return result
    
    def upsert_evaluator(self, evaluator: Dict[str, Any]) -> str:
        """Insert or update an evaluator"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            config_json = json.dumps(evaluator.get('config')) if evaluator.get('config') else None
            cursor.execute("""
                INSERT INTO evaluators (id, name, type, description, eval_prompt, extraction_regex, uses_pass2, config, path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    description = excluded.description,
                    eval_prompt = excluded.eval_prompt,
                    extraction_regex = excluded.extraction_regex,
                    uses_pass2 = excluded.uses_pass2,
                    config = excluded.config,
                    path = excluded.path,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                evaluator['id'], evaluator.get('name'), evaluator.get('type'),
                evaluator.get('description'), evaluator.get('eval_prompt'),
                evaluator.get('extraction_regex'), evaluator.get('uses_pass2', False),
                config_json, evaluator.get('path')
            ))
            conn.commit()
        return evaluator['id']
    
    def delete_evaluator(self, evaluator_id: str) -> bool:
        """Delete an evaluator"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM evaluators WHERE id = ?", (evaluator_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    # Tool operations
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get all tools"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tools ORDER BY name")
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                if d.get('function_def'):
                    d['function_def'] = json.loads(d['function_def'])
                if d.get('mock_response') and d.get('mock_response_type', 'json') == 'json':
                    try:
                        d['mock_response'] = json.loads(d['mock_response'])
                    except (json.JSONDecodeError, TypeError):
                        pass
                results.append(d)
            return results

    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get a single tool by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tools WHERE id = ?", (tool_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            if d.get('function_def'):
                d['function_def'] = json.loads(d['function_def'])
            if d.get('mock_response') and d.get('mock_response_type', 'json') == 'json':
                try:
                    d['mock_response'] = json.loads(d['mock_response'])
                except (json.JSONDecodeError, TypeError):
                    pass
            return d

    def upsert_tool(self, tool: Dict[str, Any]) -> str:
        """Insert or update a tool"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            function_def = json.dumps(tool['function_def']) if isinstance(tool.get('function_def'), dict) else tool.get('function_def')
            mock_response = tool.get('mock_response')
            if isinstance(mock_response, (dict, list)):
                mock_response = json.dumps(mock_response)
            cursor.execute("""
                INSERT INTO tools (id, name, description, function_def, mock_response, mock_response_type, path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    function_def = excluded.function_def,
                    mock_response = excluded.mock_response,
                    mock_response_type = excluded.mock_response_type,
                    path = excluded.path,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                tool['id'], tool.get('name'), tool.get('description'),
                function_def, mock_response,
                tool.get('mock_response_type', 'json'), tool.get('path')
            ))
            conn.commit()
        return tool['id']

    def delete_tool(self, tool_id: str) -> bool:
        """Delete a tool"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tools WHERE id = ?", (tool_id,))
            conn.commit()
            return cursor.rowcount > 0

    # Level scores operations
    def save_level_score(self, run_id: str, domain: str, level: int, 
                         average_score: float, total_tests: int, passed_tests: int):
        """Save aggregated level score"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO level_scores (run_id, domain, level, average_score, total_tests, passed_tests)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (run_id, domain, level, average_score, total_tests, passed_tests))
            conn.commit()
    
    def get_level_scores(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all level scores for a run"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM level_scores WHERE run_id = ? ORDER BY domain, level",
                (run_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # Individual test results operations
    def save_individual_test_result(self, run_id: str, test_id: str, domain: str, level: int,
                                    prompt: str, response: str, expected: str, score: float,
                                    status: str, details: str, duration_ms: int, model_name: str,
                                    system_prompt: str = None, system_prompt_mode: str = None):
        """Save individual test result with optional system_prompt and mode"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO individual_test_results 
                (run_id, test_id, domain, level, prompt, response, expected, score, status, details, duration_ms, model_name, system_prompt, system_prompt_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, test_id, domain, level, prompt, response, expected, score, status, details, duration_ms, model_name, system_prompt, system_prompt_mode))
            conn.commit()
    
    def get_individual_test_results(self, run_id: str, domain: str = None, level: int = None) -> List[Dict[str, Any]]:
        """Get individual test results for a run - prioritize saved resolved system_prompt"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Select from individual_test_results table directly (has the saved resolved prompt)
            # JOIN is only needed to get domain name for reference, not for prompt
            if domain and level:
                cursor.execute("""
                    SELECT itr.*, d.name as domain_name
                    FROM individual_test_results itr
                    LEFT JOIN domains d ON itr.domain = d.id
                    WHERE itr.run_id = ? AND itr.domain = ? AND itr.level = ?
                """, (run_id, domain, level))
            elif domain:
                cursor.execute("""
                    SELECT itr.*, d.name as domain_name
                    FROM individual_test_results itr
                    LEFT JOIN domains d ON itr.domain = d.id
                    WHERE itr.run_id = ? AND itr.domain = ?
                """, (run_id, domain))
            else:
                cursor.execute("""
                    SELECT itr.*, d.name as domain_name
                    FROM individual_test_results itr
                    LEFT JOIN domains d ON itr.domain = d.id
                    WHERE itr.run_id = ? ORDER BY itr.domain, itr.level
                """, (run_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_last_run(self) -> Optional[Dict[str, Any]]:
        """Get the most recent evaluation run"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM evaluation_runs 
                ORDER BY started_at DESC 
                LIMIT 1
            """)
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_last_run_id(self) -> Optional[str]:
        """Get the most recent evaluation run ID"""
        run = self.get_last_run()
        return run["run_id"] if run else None

# Create global database instance
db = Database()