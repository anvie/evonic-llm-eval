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
                    enabled BOOLEAN DEFAULT 1,
                    path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                "SELECT * FROM evaluation_runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
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
            cursor.execute("""
                INSERT INTO domains (id, name, description, icon, color, evaluator_id, enabled, path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    icon = excluded.icon,
                    color = excluded.color,
                    evaluator_id = excluded.evaluator_id,
                    enabled = excluded.enabled,
                    path = excluded.path,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                domain['id'], domain.get('name'), domain.get('description'),
                domain.get('icon'), domain.get('color'), domain.get('evaluator_id'),
                domain.get('enabled', True), domain.get('path')
            ))
            conn.commit()
        return domain['id']
    
    def delete_domain(self, domain_id: str) -> bool:
        """Delete a domain"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # First delete all tests in this domain
            cursor.execute("DELETE FROM tests WHERE domain_id = ?", (domain_id,))
            # Then delete the domain
            cursor.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
            conn.commit()
            return cursor.rowcount > 0
    
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
            cursor.execute("""
                INSERT INTO tests (id, domain_id, level, name, description, prompt, expected, evaluator_id, timeout_ms, weight, enabled, path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    domain_id = excluded.domain_id,
                    level = excluded.level,
                    name = excluded.name,
                    description = excluded.description,
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
                test.get('description'), test['prompt'], expected_json,
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
                                    status: str, details: str, duration_ms: int, model_name: str):
        """Save individual test result"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO individual_test_results 
                (run_id, test_id, domain, level, prompt, response, expected, score, status, details, duration_ms, model_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, test_id, domain, level, prompt, response, expected, score, status, details, duration_ms, model_name))
            conn.commit()
    
    def get_individual_test_results(self, run_id: str, domain: str = None, level: int = None) -> List[Dict[str, Any]]:
        """Get individual test results for a run"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if domain and level:
                cursor.execute(
                    "SELECT * FROM individual_test_results WHERE run_id = ? AND domain = ? AND level = ?",
                    (run_id, domain, level)
                )
            elif domain:
                cursor.execute(
                    "SELECT * FROM individual_test_results WHERE run_id = ? AND domain = ?",
                    (run_id, domain)
                )
            else:
                cursor.execute(
                    "SELECT * FROM individual_test_results WHERE run_id = ? ORDER BY domain, level",
                    (run_id,)
                )
            
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