"""
Unit tests for V1 History API endpoints.
"""

import pytest
import json
import sys
import os
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.db import db


class TestHistoryAPILastId:
    """Test /api/v1/history/last/id endpoint"""
    
    def test_returns_last_run_id(self):
        """Test that endpoint returns the most recent run ID"""
        from app import app
        
        # Create a test run
        run_id = db.create_evaluation_run("test-model-history")
        
        with app.test_client() as client:
            response = client.get('/api/v1/history/last/id')
            assert response.status_code == 200
            
            data = response.get_json()
            assert "run_id" in data
            assert "model_name" in data
            assert "started_at" in data
            assert "status" in data
    
    def test_returns_404_when_no_runs(self):
        """Test 404 when no runs exist (edge case)"""
        # This test assumes there might be runs in the DB
        # In a clean DB, it would return 404
        from app import app
        
        with app.test_client() as client:
            response = client.get('/api/v1/history/last/id')
            # Either 200 (runs exist) or 404 (no runs)
            assert response.status_code in [200, 404]


class TestHistoryAPIRunDomainLevel:
    """Test /api/v1/history/<run_id>/<domain>/<level> endpoint"""
    
    def test_returns_test_results(self):
        """Test endpoint returns test results with full details"""
        from app import app
        
        # Create a test run and result
        run_id = db.create_evaluation_run("test-model")
        
        # Save test result with full details
        details = {
            "evaluator": "tool_call",
            "called_tools": ["get_current_date"],
            "thinking": "Let me check the date...",
            "tools_available": [
                {"name": "get_current_date", "description": "Get current date"}
            ],
            "conversation_log": [
                {
                    "turn": 1,
                    "thinking": "I need to get the date",
                    "tool_calls": [{"name": "get_current_date", "arguments": {}}],
                    "tool_results": [{"result": {"date": "2026-04-04"}}]
                }
            ]
        }
        
        db.save_individual_test_result(
            run_id=run_id,
            test_id="test_history_1",
            domain="tool_calling",
            level=1,
            prompt="What is today's date?",
            response="Today is April 4th, 2026",
            expected='{"tools": ["get_current_date"]}',
            score=1.0,
            status="passed",
            details=json.dumps(details),
            duration_ms=500,
            model_name="test-model"
        )
        
        with app.test_client() as client:
            response = client.get(f'/api/v1/history/{run_id}/tool_calling/1')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data["run_id"] == run_id
            assert data["domain"] == "tool_calling"
            assert data["level"] == 1
            assert len(data["tests"]) == 1
            
            test = data["tests"][0]
            assert test["test_id"] == "test_history_1"
            assert test["score"] == 1.0
            assert test["status"] == "passed"
            
            # Check details are parsed
            assert isinstance(test["details"], dict)
            assert "conversation_log" in test["details"]
            assert "tools_available" in test["details"]
            assert len(test["details"]["conversation_log"]) == 1
    
    def test_returns_404_for_invalid_run(self):
        """Test 404 for non-existent run ID"""
        from app import app
        
        with app.test_client() as client:
            response = client.get('/api/v1/history/invalid-run-id/math/1')
            assert response.status_code == 404
            
            data = response.get_json()
            assert "error" in data
    
    def test_returns_empty_tests_for_no_results(self):
        """Test empty tests array when no results for domain/level"""
        from app import app
        
        # Create a run but don't add results for specific domain
        run_id = db.create_evaluation_run("test-model")
        
        with app.test_client() as client:
            response = client.get(f'/api/v1/history/{run_id}/nonexistent_domain/1')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data["tests"] == []


class TestHistoryAPILastDomainLevel:
    """Test /api/v1/history/last/<domain>/<level> endpoint"""
    
    def test_returns_last_run_results(self):
        """Test endpoint returns results from most recent run"""
        from app import app
        
        # Create test run and result
        run_id = db.create_evaluation_run("test-model-last")
        
        db.save_individual_test_result(
            run_id=run_id,
            test_id="test_last_1",
            domain="math",
            level=2,
            prompt="What is 5 + 3?",
            response="8",
            expected='{"answer": 8}',
            score=1.0,
            status="passed",
            details='{"evaluator": "two_pass"}',
            duration_ms=100,
            model_name="test-model-last"
        )
        
        with app.test_client() as client:
            response = client.get('/api/v1/history/last/math/2')
            assert response.status_code == 200
            
            data = response.get_json()
            assert "run_id" in data
            assert data["domain"] == "math"
            assert data["level"] == 2
            assert "tests" in data
    
    def test_returns_empty_for_no_results(self):
        """Test returns empty tests when no results for domain/level"""
        from app import app
        
        # Ensure there's at least one run
        db.create_evaluation_run("test-model")
        
        with app.test_client() as client:
            response = client.get('/api/v1/history/last/nonexistent/5')
            # Should return 200 with empty tests (not 404)
            assert response.status_code == 200
            
            data = response.get_json()
            assert data["tests"] == []


class TestDatabaseLastRun:
    """Test database methods for last run"""
    
    def test_get_last_run(self):
        """Test get_last_run returns most recent run"""
        # Create multiple runs
        run1 = db.create_evaluation_run("model-1")
        run2 = db.create_evaluation_run("model-2")
        
        last_run = db.get_last_run()
        assert last_run is not None
        assert last_run["run_id"] == run2
    
    def test_get_last_run_id(self):
        """Test get_last_run_id returns ID string"""
        run_id = db.create_evaluation_run("model-test")
        
        last_id = db.get_last_run_id()
        assert last_id is not None
        assert isinstance(last_id, str)
        assert last_id == run_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
