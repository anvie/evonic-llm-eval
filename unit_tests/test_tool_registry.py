"""
Unit tests for tool registry functionality.

Tests the tool registry system: database layer, TestLoader tool resolution,
TestManager CRUD, engine integration, and JS mock execution.
"""

import json
import os
import sys
import shutil
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.db import Database
from evaluator.test_loader import (
    ToolDefinition, TestDefinition, DomainDefinition, LevelDefinition, TestLoader
)


# ==================== ToolDefinition Dataclass Tests ====================

class TestToolDefinitionDataclass:
    """Test ToolDefinition dataclass"""

    def test_from_dict_roundtrip(self):
        """Test from_dict and to_dict produce consistent results"""
        data = {
            "id": "test_tool",
            "name": "Test Tool",
            "description": "A test tool",
            "function": {
                "name": "test_func",
                "description": "Test function",
                "parameters": {"type": "object", "properties": {}, "required": []}
            },
            "mock_response": {"result": "ok"},
            "mock_response_type": "json"
        }
        tool = ToolDefinition.from_dict(data, "/some/path")
        result = tool.to_dict()

        assert result["id"] == "test_tool"
        assert result["name"] == "Test Tool"
        assert result["function"]["name"] == "test_func"
        assert result["mock_response"] == {"result": "ok"}
        assert result["mock_response_type"] == "json"
        assert result["path"] == "/some/path"

    def test_from_dict_defaults(self):
        """Test from_dict with minimal data uses defaults"""
        data = {"id": "min", "name": "Minimal"}
        tool = ToolDefinition.from_dict(data)

        assert tool.id == "min"
        assert tool.mock_response_type == "json"
        assert tool.function is None
        assert tool.mock_response is None

    def test_javascript_mock_type(self):
        """Test tool with JavaScript mock response type"""
        data = {
            "id": "js_tool",
            "name": "JS Tool",
            "function": {"name": "calc", "parameters": {}},
            "mock_response": "console.log(JSON.stringify({result: 42}))",
            "mock_response_type": "javascript"
        }
        tool = ToolDefinition.from_dict(data)
        assert tool.mock_response_type == "javascript"
        assert isinstance(tool.mock_response, str)


# ==================== Database Layer Tests ====================

class TestDatabaseToolOperations:
    """Test tool CRUD in database"""

    def test_create_tools_table(self, use_test_database):
        """Verify tools table exists after init"""
        from models.db import db
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tools'")
            assert cursor.fetchone() is not None

    def test_upsert_and_get_tool(self, use_test_database):
        """Create a tool, read it back, verify fields"""
        from models.db import db
        tool_data = {
            "id": "test_weather",
            "name": "Get Weather",
            "description": "Weather info",
            "function_def": {"name": "get_weather", "parameters": {}},
            "mock_response": {"temp": 32},
            "mock_response_type": "json",
            "path": "/test/path"
        }
        db.upsert_tool(tool_data)

        result = db.get_tool("test_weather")
        assert result is not None
        assert result["name"] == "Get Weather"
        assert result["function_def"]["name"] == "get_weather"
        assert result["mock_response"]["temp"] == 32

    def test_upsert_tool_update(self, use_test_database):
        """Update an existing tool"""
        from models.db import db
        tool_data = {
            "id": "upd_tool",
            "name": "Original",
            "function_def": {"name": "func"},
            "mock_response_type": "json"
        }
        db.upsert_tool(tool_data)

        tool_data["name"] = "Updated"
        db.upsert_tool(tool_data)

        result = db.get_tool("upd_tool")
        assert result["name"] == "Updated"

    def test_delete_tool(self, use_test_database):
        """Create then delete, verify gone"""
        from models.db import db
        db.upsert_tool({
            "id": "del_tool",
            "name": "To Delete",
            "function_def": {"name": "f"},
            "mock_response_type": "json"
        })
        assert db.get_tool("del_tool") is not None

        result = db.delete_tool("del_tool")
        assert result is True
        assert db.get_tool("del_tool") is None

    def test_get_tools_list(self, use_test_database):
        """Get all tools"""
        from models.db import db
        for i in range(3):
            db.upsert_tool({
                "id": f"tool_{i}",
                "name": f"Tool {i}",
                "function_def": {"name": f"func_{i}"},
                "mock_response_type": "json"
            })

        results = db.get_tools()
        assert len(results) >= 3

    def test_tool_ids_column_migration(self, use_test_database):
        """Verify tool_ids column added to domains/levels/tests"""
        from models.db import db
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            for table in ('domains', 'levels', 'tests'):
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [row[1] for row in cursor.fetchall()]
                assert 'tool_ids' in cols, f"tool_ids column missing in {table}"

    def test_js_mock_response_stored_as_string(self, use_test_database):
        """JavaScript mock responses are stored as-is (string)"""
        from models.db import db
        db.upsert_tool({
            "id": "js_tool",
            "name": "JS Tool",
            "function_def": {"name": "calc"},
            "mock_response": "console.log(42)",
            "mock_response_type": "javascript"
        })

        result = db.get_tool("js_tool")
        assert result["mock_response"] == "console.log(42)"
        assert result["mock_response_type"] == "javascript"


# ==================== TestLoader Tool Tests ====================

class TestLoaderToolOperations:
    """Test tool loading and resolution in TestLoader"""

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """Create temporary test structure with tools"""
        tests_dir = tmp_path / "test_definitions"
        custom_dir = tmp_path / "custom_tests"
        tools_dir = tests_dir / "tools"
        evaluators_dir = tests_dir / "evaluators"

        for d in [tests_dir, custom_dir, tools_dir, evaluators_dir]:
            d.mkdir(parents=True, exist_ok=True)

        return tests_dir, custom_dir, tools_dir

    def _create_tool_file(self, tools_dir, tool_id, func_name=None, mock_response=None):
        """Helper to create a tool JSON file"""
        func_name = func_name or tool_id
        tool_data = {
            "id": tool_id,
            "name": tool_id.replace("_", " ").title(),
            "description": f"Test tool {tool_id}",
            "function": {
                "name": func_name,
                "description": f"Function {func_name}",
                "parameters": {"type": "object", "properties": {}, "required": []}
            },
            "mock_response": mock_response or {"result": f"mock_{tool_id}"},
            "mock_response_type": "json"
        }
        with open(tools_dir / f"{tool_id}.json", "w") as f:
            json.dump(tool_data, f)
        return tool_data

    def test_scan_tools(self, temp_dirs):
        """Scan tool JSON files from directory"""
        tests_dir, custom_dir, tools_dir = temp_dirs
        self._create_tool_file(tools_dir, "tool_a")
        self._create_tool_file(tools_dir, "tool_b")

        loader = TestLoader(
            str(tests_dir), str(custom_dir),
            str(tests_dir / "evaluators"), str(custom_dir / "evaluators")
        )
        scanned = loader.scan_tools()

        assert len(scanned) == 2
        ids = {t.id for t in scanned}
        assert "tool_a" in ids
        assert "tool_b" in ids

    def test_get_tool(self, temp_dirs):
        """Get a single tool by ID"""
        tests_dir, custom_dir, tools_dir = temp_dirs
        self._create_tool_file(tools_dir, "my_tool")

        loader = TestLoader(
            str(tests_dir), str(custom_dir),
            str(tests_dir / "evaluators"), str(custom_dir / "evaluators")
        )
        tool = loader.get_tool("my_tool")
        assert tool is not None
        assert tool.id == "my_tool"

    def test_resolve_tools_domain_only(self, temp_dirs):
        """Tools attached to domain are resolved"""
        tests_dir, custom_dir, tools_dir = temp_dirs
        self._create_tool_file(tools_dir, "domain_tool")

        loader = TestLoader(
            str(tests_dir), str(custom_dir),
            str(tests_dir / "evaluators"), str(custom_dir / "evaluators")
        )

        domain = DomainDefinition(id="test", name="Test", description="", tool_ids=["domain_tool"])
        test = TestDefinition(id="t1", name="T1", description="", prompt="p",
                              expected={}, evaluator_id="e", domain_id="test", level=1)

        resolved = loader.resolve_tools(test, domain)
        assert len(resolved) == 1
        assert resolved[0]["function"]["name"] == "domain_tool"

    def test_resolve_tools_domain_and_level(self, temp_dirs):
        """Tools from domain + level are accumulated"""
        tests_dir, custom_dir, tools_dir = temp_dirs
        self._create_tool_file(tools_dir, "d_tool")
        self._create_tool_file(tools_dir, "l_tool")

        loader = TestLoader(
            str(tests_dir), str(custom_dir),
            str(tests_dir / "evaluators"), str(custom_dir / "evaluators")
        )

        domain = DomainDefinition(id="test", name="Test", description="", tool_ids=["d_tool"])
        level = LevelDefinition(domain_id="test", level=1, tool_ids=["l_tool"])
        test = TestDefinition(id="t1", name="T1", description="", prompt="p",
                              expected={}, evaluator_id="e", domain_id="test", level=1)

        resolved = loader.resolve_tools(test, domain, level)
        assert len(resolved) == 2
        func_names = {r["function"]["name"] for r in resolved}
        assert func_names == {"d_tool", "l_tool"}

    def test_resolve_tools_all_levels(self, temp_dirs):
        """Tools from domain + level + test are accumulated"""
        tests_dir, custom_dir, tools_dir = temp_dirs
        self._create_tool_file(tools_dir, "d_tool")
        self._create_tool_file(tools_dir, "l_tool")
        self._create_tool_file(tools_dir, "t_tool")

        loader = TestLoader(
            str(tests_dir), str(custom_dir),
            str(tests_dir / "evaluators"), str(custom_dir / "evaluators")
        )

        domain = DomainDefinition(id="test", name="Test", description="", tool_ids=["d_tool"])
        level = LevelDefinition(domain_id="test", level=1, tool_ids=["l_tool"])
        test = TestDefinition(id="t1", name="T1", description="", prompt="p",
                              expected={}, evaluator_id="e", domain_id="test", level=1,
                              tool_ids=["t_tool"])

        resolved = loader.resolve_tools(test, domain, level)
        assert len(resolved) == 3

    def test_resolve_tools_deduplication(self, temp_dirs):
        """Same function name at different levels: last wins"""
        tests_dir, custom_dir, tools_dir = temp_dirs
        self._create_tool_file(tools_dir, "shared_v1", func_name="shared_func",
                               mock_response={"version": 1})
        self._create_tool_file(tools_dir, "shared_v2", func_name="shared_func",
                               mock_response={"version": 2})

        loader = TestLoader(
            str(tests_dir), str(custom_dir),
            str(tests_dir / "evaluators"), str(custom_dir / "evaluators")
        )

        domain = DomainDefinition(id="test", name="Test", description="", tool_ids=["shared_v1"])
        test = TestDefinition(id="t1", name="T1", description="", prompt="p",
                              expected={}, evaluator_id="e", domain_id="test", level=1,
                              tool_ids=["shared_v2"])

        resolved = loader.resolve_tools(test, domain)
        assert len(resolved) == 1
        assert resolved[0]["mock_response"]["version"] == 2

    def test_resolve_tools_empty(self, temp_dirs):
        """No tools attached returns empty list"""
        tests_dir, custom_dir, tools_dir = temp_dirs

        loader = TestLoader(
            str(tests_dir), str(custom_dir),
            str(tests_dir / "evaluators"), str(custom_dir / "evaluators")
        )

        domain = DomainDefinition(id="test", name="Test", description="")
        test = TestDefinition(id="t1", name="T1", description="", prompt="p",
                              expected={}, evaluator_id="e", domain_id="test", level=1)

        resolved = loader.resolve_tools(test, domain)
        assert resolved == []

    def test_resolve_tools_missing_tool_id_skipped(self, temp_dirs):
        """Non-existent tool IDs are silently skipped"""
        tests_dir, custom_dir, tools_dir = temp_dirs
        self._create_tool_file(tools_dir, "real_tool")

        loader = TestLoader(
            str(tests_dir), str(custom_dir),
            str(tests_dir / "evaluators"), str(custom_dir / "evaluators")
        )

        domain = DomainDefinition(id="test", name="Test", description="",
                                  tool_ids=["real_tool", "nonexistent_tool"])
        test = TestDefinition(id="t1", name="T1", description="", prompt="p",
                              expected={}, evaluator_id="e", domain_id="test", level=1)

        resolved = loader.resolve_tools(test, domain)
        assert len(resolved) == 1
        assert resolved[0]["function"]["name"] == "real_tool"


# ==================== TestManager Tool CRUD Tests ====================

class TestManagerToolCRUD:
    """Test tool CRUD operations in TestManager"""

    @pytest.fixture
    def manager(self, use_test_database, tmp_path):
        """Create a TestManager with temp directories"""
        from evaluator.test_manager import TestManager
        tests_dir = tmp_path / "test_definitions"
        custom_dir = tmp_path / "custom_tests"
        evaluators_dir = tests_dir / "evaluators"
        custom_evaluators_dir = custom_dir / "evaluators"

        for d in [tests_dir, custom_dir, evaluators_dir, custom_evaluators_dir]:
            d.mkdir(parents=True, exist_ok=True)

        mgr = TestManager(
            str(tests_dir), str(custom_dir),
            str(evaluators_dir), str(custom_evaluators_dir)
        )
        return mgr

    def test_create_tool(self, manager):
        """Create via manager, verify JSON file exists + data correct"""
        data = {
            "id": "new_tool",
            "name": "New Tool",
            "description": "A new tool",
            "function": {
                "name": "new_func",
                "description": "New function",
                "parameters": {"type": "object", "properties": {}}
            },
            "mock_response": {"data": "test"},
            "mock_response_type": "json"
        }
        result = manager.create_tool(data)
        assert result is not None
        assert result["id"] == "new_tool"
        assert result["name"] == "New Tool"

        # Verify file exists
        tool_file = manager.tools_dir / "new_tool.json"
        assert tool_file.exists()

    def test_update_tool(self, manager):
        """Update fields, verify persisted"""
        manager.create_tool({
            "id": "upd_tool",
            "name": "Original",
            "function": {"name": "func", "parameters": {}},
            "mock_response_type": "json"
        })

        result = manager.update_tool("upd_tool", {"name": "Updated Name"})
        assert result["name"] == "Updated Name"

        # Verify persisted in file
        fresh = manager.get_tool("upd_tool")
        assert fresh["name"] == "Updated Name"

    def test_delete_tool(self, manager):
        """Delete, verify file + data cleaned"""
        manager.create_tool({
            "id": "del_tool",
            "name": "To Delete",
            "function": {"name": "func", "parameters": {}},
            "mock_response_type": "json"
        })

        result = manager.delete_tool("del_tool")
        assert result is True
        assert manager.get_tool("del_tool") is None

        tool_file = manager.tools_dir / "del_tool.json"
        assert not tool_file.exists()

    def test_list_tools(self, manager):
        """Create multiple, list all"""
        for i in range(3):
            manager.create_tool({
                "id": f"list_tool_{i}",
                "name": f"Tool {i}",
                "function": {"name": f"func_{i}", "parameters": {}},
                "mock_response_type": "json"
            })

        tools = manager.list_tools()
        assert len(tools) >= 3

    def test_create_duplicate_raises(self, manager):
        """Creating a tool with existing ID raises ValueError"""
        manager.create_tool({
            "id": "dup_tool",
            "name": "Original",
            "function": {"name": "func", "parameters": {}},
            "mock_response_type": "json"
        })

        with pytest.raises(ValueError, match="already exists"):
            manager.create_tool({
                "id": "dup_tool",
                "name": "Duplicate",
                "function": {"name": "func2", "parameters": {}},
                "mock_response_type": "json"
            })


# ==================== JS Mock Execution Tests ====================

class TestJsMockExecution:
    """Test JavaScript mock response execution"""

    @pytest.fixture
    def engine_instance(self):
        """Create a minimal engine-like object for testing _execute_js_mock"""
        from evaluator.engine import EvaluationEngine
        engine = EvaluationEngine.__new__(EvaluationEngine)
        engine.log_lines = []
        engine.verbose = False
        return engine

    def _log(self, msg):
        """Dummy log method"""
        pass

    def test_execute_js_mock_simple(self, engine_instance):
        """Simple JS returning object"""
        engine_instance._log = self._log
        js_code = 'console.log(JSON.stringify({result: 42}))'
        result = engine_instance._execute_js_mock(js_code, {})
        assert result.get("result") == 42

    def test_execute_js_mock_with_args(self, engine_instance):
        """JS using ARGS variable"""
        engine_instance._log = self._log
        js_code = 'const args = JSON.parse(ARGS); console.log(JSON.stringify({greeting: "hello " + args.name}))'
        result = engine_instance._execute_js_mock(js_code, {"name": "world"})
        assert result.get("greeting") == "hello world"

    def test_execute_js_mock_timeout(self, engine_instance):
        """Infinite loop JS hits timeout"""
        engine_instance._log = self._log
        js_code = 'while(true) {}'
        result = engine_instance._execute_js_mock(js_code, {})
        assert "error" in result
        assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()


# ==================== Integration: Registry + Embedded Merge ====================

class TestToolMergeLogic:
    """Test that registry tools merge correctly with embedded tools"""

    @pytest.fixture
    def temp_dirs(self, tmp_path):
        tests_dir = tmp_path / "test_definitions"
        custom_dir = tmp_path / "custom_tests"
        tools_dir = tests_dir / "tools"
        evaluators_dir = tests_dir / "evaluators"
        for d in [tests_dir, custom_dir, tools_dir, evaluators_dir]:
            d.mkdir(parents=True, exist_ok=True)
        return tests_dir, custom_dir, tools_dir

    def _create_tool_file(self, tools_dir, tool_id, func_name=None, mock_response=None):
        func_name = func_name or tool_id
        tool_data = {
            "id": tool_id,
            "name": tool_id,
            "function": {
                "name": func_name,
                "description": f"Function {func_name}",
                "parameters": {"type": "object", "properties": {}}
            },
            "mock_response": mock_response or {"source": "registry"},
            "mock_response_type": "json"
        }
        with open(tools_dir / f"{tool_id}.json", "w") as f:
            json.dump(tool_data, f)

    def test_registry_tools_no_duplicates(self, temp_dirs):
        """Same tool at domain and test level: only one in final list"""
        tests_dir, custom_dir, tools_dir = temp_dirs
        self._create_tool_file(tools_dir, "shared", func_name="shared_func")

        loader = TestLoader(
            str(tests_dir), str(custom_dir),
            str(tests_dir / "evaluators"), str(custom_dir / "evaluators")
        )

        domain = DomainDefinition(id="d", name="D", description="", tool_ids=["shared"])
        test = TestDefinition(id="t", name="T", description="", prompt="p",
                              expected={}, evaluator_id="e", domain_id="d", level=1,
                              tool_ids=["shared"])

        resolved = loader.resolve_tools(test, domain)
        func_names = [r["function"]["name"] for r in resolved]
        assert func_names.count("shared_func") == 1
