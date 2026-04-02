import sqlite3
from typing import Dict, Any, List, Optional
import config

class SQLExecutor:
    def __init__(self, db_path: str = config.TEST_DB_PATH):
        self.db_path = db_path
    
    def execute_safe_query(self, query: str) -> Dict[str, Any]:
        """Execute SQL query with safety checks"""
        
        # Safety validation
        validation_result = self._validate_query(query)
        if not validation_result["valid"]:
            return validation_result
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute(query)
                
                if query.strip().upper().startswith("SELECT"):
                    rows = cursor.fetchall()
                    result = [dict(row) for row in rows]
                    return {
                        "success": True,
                        "result": result,
                        "row_count": len(result),
                        "columns": [description[0] for description in cursor.description] if cursor.description else []
                    }
                else:
                    conn.commit()
                    return {
                        "success": True,
                        "result": "Non-SELECT query executed",
                        "affected_rows": cursor.rowcount
                    }
                    
        except sqlite3.Error as e:
            return {
                "success": False,
                "error": f"SQL execution error: {str(e)}",
                "query": query
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "query": query
            }
    
    def _validate_query(self, query: str) -> Dict[str, Any]:
        """Validate SQL query for safety"""
        
        # Basic checks
        if not query.strip():
            return {"valid": False, "error": "Empty query"}
        
        query_upper = query.upper()
        
        # Block dangerous operations
        dangerous_keywords = [
            "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", 
            "TRUNCATE", "CREATE", "GRANT", "REVOKE"
        ]
        
        for keyword in dangerous_keywords:
            if f" {keyword} " in f" {query_upper} ":
                return {
                    "valid": False, 
                    "error": f"Query contains dangerous operation: {keyword}"
                }
        
        # Allow only SELECT queries for safety
        if not query_upper.startswith("SELECT"):
            return {
                "valid": False,
                "error": "Only SELECT queries are allowed for evaluation"
            }
        
        return {"valid": True}
    
    def compare_results(self, actual_result: List[Dict], expected_result: List[Dict]) -> Dict[str, Any]:
        """Compare actual query results with expected results"""
        
        if not isinstance(actual_result, list) or not isinstance(expected_result, list):
            return {
                "match": False,
                "error": "Both actual and expected results must be lists"
            }
        
        # Check row count
        if len(actual_result) != len(expected_result):
            return {
                "match": False,
                "reason": f"Row count mismatch: actual {len(actual_result)}, expected {len(expected_result)}"
            }
        
        # Check each row
        for i, (actual_row, expected_row) in enumerate(zip(actual_result, expected_result)):
            if not isinstance(actual_row, dict) or not isinstance(expected_row, dict):
                return {
                    "match": False,
                    "reason": f"Row {i}: not a dictionary"
                }
            
            # Check keys
            if set(actual_row.keys()) != set(expected_row.keys()):
                return {
                    "match": False,
                    "reason": f"Row {i}: column mismatch"
                }
            
            # Check values
            for key in actual_row.keys():
                actual_val = actual_row[key]
                expected_val = expected_row[key]
                
                # Handle numeric comparison with tolerance
                if isinstance(actual_val, (int, float)) and isinstance(expected_val, (int, float)):
                    if abs(actual_val - expected_val) > 0.001:
                        return {
                            "match": False,
                            "reason": f"Row {i}, column {key}: value mismatch {actual_val} vs {expected_val}"
                        }
                elif actual_val != expected_val:
                    return {
                        "match": False,
                        "reason": f"Row {i}, column {key}: value mismatch {actual_val} vs {expected_val}"
                    }
        
        return {"match": True}
    
    def get_sample_data_info(self) -> Dict[str, Any]:
        """Get information about the test database schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Get row counts
                table_info = {}
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    row_count = cursor.fetchone()[0]
                    
                    # Get column names
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [row[1] for row in cursor.fetchall()]
                    
                    table_info[table] = {
                        "row_count": row_count,
                        "columns": columns
                    }
                
                return {
                    "success": True,
                    "tables": tables,
                    "table_info": table_info
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# Global SQL executor instance
sql_executor = SQLExecutor()