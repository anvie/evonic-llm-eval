"""
Evaluation Engine - Run LLM evaluations using configurable test definitions.

Supports both:
1. Legacy hardcoded tests (from tests/ module)
2. New configurable tests (from test_definitions/ directory)
"""

import time
import json
from typing import Dict, Any, List, Optional
import queue
from threading import Thread, Lock

from tests import get_test_class
from evaluator.llm_client import llm_client
from evaluator.scoring import scoring_engine
from evaluator.domain_evaluators import get_evaluator
from evaluator.test_loader import test_loader
from evaluator.test_manager import test_manager
from evaluator.score_aggregator import ScoreAggregator, TestResult
from evaluator.custom_evaluator import CustomEvaluator
from evaluator.logger import test_logger
from models.db import db
import config

# Maximum iterations for multi-turn tool calling
MAX_TOOL_ITERATIONS = 5


class EvaluationEngine:
    def __init__(self, use_configurable_tests: bool = False):
        """
        Initialize evaluation engine.
        
        Args:
            use_configurable_tests: If True, load tests from test_definitions/
                                   If False, use legacy hardcoded tests
        """
        self.current_run_id: Optional[int] = None
        self.is_running = False
        self.was_interrupted = False  # User clicked Stop
        self.has_error = False       # Error occurred during evaluation
        self.error_message: Optional[str] = None
        self.lock = Lock()
        self.thread: Optional[Thread] = None
        self.log_queue = queue.Queue()
        self.use_configurable_tests = use_configurable_tests
        self.total_tokens=0
        self.total_duration_ms = 0
        self.model_name: Optional[str] = None
    
    def _log(self, message: str):
        """Log a message to the queue"""
        timestamp = time.strftime('%H:%M:%S')
        self.log_queue.put(f"[{timestamp}] {message}")
    
    def start_evaluation(self, model_name: str = None, domains: list = None) -> str:
        """Start a new evaluation run
        
        Args:
            model_name: Model to evaluate (None = use configured model)
            domains: List of domain names to test (None = all domains)
        """
        with self.lock:
            if self.is_running:
                raise Exception("Evaluation already running")
            
            # Always force-refresh model name from server at eval start
            # The frontend may send a stale model name (fetched at page load),
            # so always fetch the current name from the server.
            from evaluator.llm_client import llm_client
            model_name = llm_client.get_actual_model_name(force_refresh=True)
            
            self.model_name = model_name
            self.selected_domains = domains  # Store selected domains
            self.current_run_id = db.create_evaluation_run(model_name)
            self.is_running = True
            self.was_interrupted = False
            self.has_error = False
            self.error_message = None
            self.total_tokens=0
            self.total_duration_ms = 0
            
            domains_str = ', '.join(domains) if domains else 'all'
            self._log(f'[INFO] Memulai evaluasi untuk model: {model_name}')
            self._log(f'[INFO] Domain yang dipilih: {domains_str}')
            
            # Start test logger
            test_logger.start_run(self.current_run_id, model_name)
            
            # Start evaluation in background thread
            self.thread = Thread(target=self._run_evaluation, args=(self.current_run_id, model_name, domains))
            self.thread.daemon = True
            self.thread.start()
            
            return self.current_run_id
    
    def stop_evaluation(self):
        """Stop current evaluation"""
        with self.lock:
            self.is_running = False
            self.was_interrupted = True
    
    def reset_state(self):
        """Reset engine state to idle"""
        with self.lock:
            self.current_run_id = None
            self.is_running = False
            self.was_interrupted = False
            self.total_tokens = 0
            self.total_duration_ms = 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get current evaluation status"""
        with self.lock:
            if not self.current_run_id:
                return {"status": "idle"}
            
            run_info = db.get_evaluation_run(self.current_run_id)
            test_results = db.get_test_results(self.current_run_id)
            stats = db.get_run_stats(self.current_run_id)
            
            # Determine status
            if self.is_running:
                status = "running"
            elif self.has_error:
                status = "error"
            elif self.was_interrupted:
                status = "interrupted"
            else:
                status = "completed"
            
            # Calculate tok/s
            tok_per_sec = None
            if self.total_duration_ms > 0:
                tok_per_sec = (self.total_tokens / self.total_duration_ms) * 1000
            
            return {
                "status": status,
                "run_id": self.current_run_id,
                "run_info": run_info,
                "test_results": test_results,
                "stats": stats,
                "tok_per_sec": round(tok_per_sec, 1) if tok_per_sec else None,
                "error_message": self.error_message if self.has_error else None
            }
    
    def _run_evaluation(self, run_id: int, model_name: str, domains: list = None):
        """Main evaluation loop - supports both legacy and configurable tests
        
        Args:
            run_id: Unique run identifier
            model_name: Model being evaluated
            domains: List of domain names to test (None = all domains)
        """
        self._log(f'[SYSTEM] Evaluation thread (run_id: {run_id}) dimulai.')
        
        try:
            if self.use_configurable_tests:
                self._run_configurable_evaluation(run_id, model_name, domains)
            else:
                self._run_legacy_evaluation(run_id, model_name, domains)
            
            # Generate summary after all tests
            if self.is_running:
                self._generate_summary(run_id, model_name)
                
        except Exception as e:
            import traceback
            self._log(f'[ERROR] Evaluation error: {e}')
            self._log(f'[ERROR] Traceback: {traceback.format_exc()[-500:]}')
            print(f"Evaluation error: {e}")
            traceback.print_exc()
            # Mark as error (not user-interrupted)
            self.has_error = True
            self.error_message = str(e)
        finally:
            with self.lock:
                self.is_running = False
            
            # Finalize test logger
            if self.has_error:
                final_status = "error"
            elif self.was_interrupted:
                final_status = "interrupted"
            else:
                final_status = "completed"
            test_logger.finalize_run(status=final_status)
    
    def _run_legacy_evaluation(self, run_id: int, model_name: str, selected_domains: list = None):
        """Run evaluation using legacy hardcoded tests
        
        Args:
            run_id: Unique run identifier
            model_name: Model being evaluated
            selected_domains: List of domain names to test (None = all domains)
        """
        all_domains = ["conversation", "math", "sql", "tool_calling", "reasoning", "health"]
        
        # Filter domains if selection provided
        if selected_domains:
            domains = [d for d in all_domains if d in selected_domains]
        else:
            domains = all_domains
        
        for domain in domains:
            for level in range(1, 6):  # Levels 1-5
                if not self.is_running:
                    break
                
                # Update status to running
                db.update_test_result(
                    run_id, domain, level,
                    status="running",
                    model_name=model_name
                )
                self._log(f'[TEST] Menjalankan tes: {domain} Level {level}')
                
                # Run the test
                test_result = self._run_single_legacy_test(domain, level)
                
                # Store result
                db.update_test_result(
                    run_id, domain, level,
                    prompt=test_result["prompt"],
                    response=test_result["response"],
                    expected=json.dumps(test_result["expected"]) if test_result["expected"] else None,
                    score=test_result["score"],
                    status=test_result["status"],
                    details=json.dumps(test_result["details"]) if test_result["details"] else None,
                    duration_ms=test_result["duration_ms"]
                )
                
                # Small delay between tests
                time.sleep(0.5)
    
    def _run_configurable_evaluation(self, run_id: int, model_name: str, selected_domains: list = None):
        """Run evaluation using configurable test definitions
        
        Args:
            run_id: Unique run identifier
            model_name: Model being evaluated
            selected_domains: List of domain names to test (None = all domains)
        """
        # Clear global test_loader cache to ensure fresh data
        from evaluator.test_loader import test_loader
        test_loader.clear_cache()

        # Sync tests from files to database
        test_manager.sync_to_db()
        
        # Load all domains
        domains = test_manager.list_domains()
        
        for domain_data in domains:
            domain_id = domain_data['id']
            
            # Skip disabled domains
            if not domain_data.get('enabled', True):
                continue
            
            # Skip domains not in selection (if selection provided)
            if selected_domains and domain_id not in selected_domains:
                continue
            
            # Run tests for each level
            for level in range(1, 6):
                if not self.is_running:
                    break
                
                # Load tests for this domain/level
                tests = test_manager.list_tests(domain_id, level)
                
                if not tests:
                    self._log(f'[SKIP] No tests for {domain_id} Level {level}')
                    continue
                
                # Set status to "running" for this cell before starting
                db.update_test_result(
                    run_id, domain_id, level,
                    status="running",
                    model_name=model_name
                )
                
                self._log(f'[TEST] Running {len(tests)} test(s) for {domain_id} Level {level}')
                
                # Run all tests for this level
                test_results = []
                first_prompt = None
                first_response = None
                first_expected = None
                
                for test in tests:
                    if not self.is_running:
                        break
                    
                    if not test.get('enabled', True):
                        continue
                    
                    result = self._run_single_configurable_test(
                        test, domain_id, level, model_name, run_id
                    )
                    test_results.append(result)
                    
                    # Store first test's prompt/response for display
                    if first_prompt is None:
                        first_prompt = test.get('prompt', '')
                        first_expected = test.get('expected', {})
                
                # Calculate average score for this level
                if test_results:
                    level_score = ScoreAggregator.calculate_level_score(test_results)
                    
                    # Calculate total duration for this level
                    level_duration_ms = sum(
                        r.details.get('duration_ms', 0) if r.details else 0 
                        for r in test_results
                    )
                    
                    # Store level score
                    db.save_level_score(
                        run_id, domain_id, level,
                        level_score.average_score,
                        level_score.total_tests,
                        level_score.passed_tests
                    )
                    
                    # Also update the legacy test_results table for compatibility
                    avg_score = level_score.average_score
                    status = 'passed' if avg_score >= 0.7 else 'failed'
                    
                    # Get details from first test result (includes thinking, response, etc.)
                    first_details = test_results[0].details if test_results[0].details else {}
                    
                    db.update_test_result(
                        run_id, domain_id, level,
                        prompt=first_prompt,
                        response=first_details.get('response'),
                        expected=json.dumps(first_expected) if first_expected else None,
                        score=avg_score,
                        status=status,
                        details=json.dumps(first_details) if first_details else None,
                        model_name=model_name,
                        duration_ms=level_duration_ms
                    )
                
                time.sleep(0.5)
    
    def _run_single_legacy_test(self, domain: str, level: int) -> Dict[str, Any]:
        """Run a single legacy test using domain-specific evaluator"""
        try:
            test_class = get_test_class(domain)
            if not test_class:
                self._log(f'[ERROR] Unknown domain: {domain}')
                return {
                    "prompt": "",
                    "response": "",
                    "expected": None,
                    "score": 0.0,
                    "status": "failed",
                    "details": f"Unknown domain: {domain}",
                    "duration_ms": 0
                }

            test_instance = test_class(level)
            prompt = test_instance.get_prompt()
            expected = test_instance.get_expected()

            # Log test start with input
            self._log(f'')
            self._log(f'═══════════════════════════════════════════════════════════════')
            self._log(f'[TEST] {domain.upper()} Level {level}')
            self._log(f'───────────────────────────────────────────────────────────────')
            
            # Truncate prompt for display
            prompt_display = prompt[:300] + '...' if len(prompt) > 300 else prompt
            prompt_display = prompt_display.replace('\n', ' ')
            self._log(f'[INPUT] {prompt_display}')
            
            if expected:
                expected_str = str(expected)[:100] + '...' if len(str(expected)) > 100 else str(expected)
                self._log(f'[EXPECTED] {expected_str}')

            # Handle tool_calling domain with multi-turn loop
            if domain == "tool_calling":
                from evaluator.tools import tool_framework
                tools = tool_framework.tools
                self._log(f'[TOOLS] Available: {[t["function"]["name"] for t in tools]}')
                
                # Run tool calling loop
                loop_result = self._run_tool_calling_loop(prompt, tools, system_prompt=system_prompt)
                
                duration_ms = loop_result["total_duration_ms"]
                total_tokens = loop_result["total_tokens"]
                thinking_content = loop_result["thinking"]

                # Log thinking first (before summary)
                if thinking_content:
                    if config.LOG_FULL_THINKING:
                        self._log(f'[THINKING] {thinking_content}')
                    else:
                        self._log(f'[THINKING] Model used thinking ({len(thinking_content)} chars)')

                # Build response content with all tool calls
                all_tool_calls = loop_result["all_tool_calls"]
                if all_tool_calls:
                    response_content = json.dumps({"tool_calls": all_tool_calls}, indent=2)
                else:
                    response_content = loop_result["final_response"]

                self._log(f'[LLM] Total: {duration_ms}ms, {total_tokens} tokens, {loop_result["iterations"]} iteration(s)')
                self._log(f'[TOOLS] Made {len(all_tool_calls)} tool call(s): {[tc["function"]["name"] for tc in all_tool_calls]}')

                # Accumulate tokens and duration
                self.total_tokens += total_tokens
                self.total_duration_ms += duration_ms

                error_info = None  # No single error for loop
            else:
                # Standard single-turn LLM call for other domains
                messages = [{"role": "user", "content": prompt}]
                tools = None

                self._log(f'[LLM] Sending request to model...')
                llm_response = llm_client.chat_completion(messages, tools, enable_thinking=config.LLM_ENABLE_THINKING)
                
                # Safely extract duration and tokens
                duration_ms = llm_response.get("duration_ms", 0) if isinstance(llm_response, dict) else 0
                total_tokens = llm_response.get("total_tokens", 0) if isinstance(llm_response, dict) else 0
                
                # Check for LLM errors
                error_info = llm_client.get_error_info(llm_response)
                if error_info:
                    self._log(f'[ERROR] LLM {error_info["type"]}: {error_info["message"]}')
                    if error_info["detail"]:
                        self._log(f'[ERROR] Detail: {error_info["detail"][:100]}')
                else:
                    self._log(f'[LLM] Response received in {duration_ms}ms, {total_tokens} tokens')
                
                # Accumulate tokens and duration for tok/s calculation
                self.total_tokens += total_tokens
                self.total_duration_ms += duration_ms
                
                # Extract content with thinking separation
                content_info = llm_client.extract_content_with_thinking(llm_response)
                response_content = content_info["content"]  # Final content (without thinking)
                thinking_content = content_info["thinking"]  # Thinking content (if present)

                # Log thinking for single-turn path
                if thinking_content:
                    if config.LOG_FULL_THINKING:
                        self._log(f'[THINKING] {thinking_content}')
                    else:
                        self._log(f'[THINKING] Model used thinking ({len(thinking_content)} chars)')

            # Log response
            if config.LOG_FULL_RESPONSE:
                self._log(f'[OUTPUT] {response_content}')
            else:
                response_display = response_content[:200] + '...' if len(response_content) > 200 else response_content
                response_display = response_display.replace('\n', ' ')
                self._log(f'[OUTPUT] {response_display}')

            # Get domain-specific evaluator
            evaluator = get_evaluator(domain)
            self._log(f'[EVAL] Using {evaluator.name} (PASS2: {evaluator.uses_pass2})')
            
            # Evaluate using domain-specific strategy (only final content, not thinking)
            # Pass the original prompt for context (helps PASS 2 extraction)
            self._log(f'[SCORING] Evaluating response...')
            result = evaluator.evaluate(response_content, expected, level, prompt)
            
            # Build details dict
            details = result.details
            if not isinstance(details, dict):
                details = {"details": str(details)}
            
            # Add evaluator info
            details["evaluator"] = evaluator.name
            details["uses_pass2"] = evaluator.uses_pass2
            
            # Add thinking content to details if present
            if thinking_content:
                details["thinking"] = thinking_content
            
            # Add LLM error info to details if present
            if error_info:
                details["llm_error"] = {
                    "type": error_info["type"],
                    "message": error_info["message"],
                    "detail": error_info["detail"]
                }
            
            # Log result
            status_icon = '✓' if result.status == 'passed' else '✗'
            self._log(f'[RESULT] {status_icon} Status: {result.status.upper()}, Score: {result.score*100:.0f}%')
            
            # Get details string for logging
            details_inner = details.get("details", "")
            if isinstance(details_inner, str):
                self._log(f'[DETAILS] {details_inner[:80]}')
            elif isinstance(details_inner, dict):
                # For conversation: show relevance/correctness/fluency
                if "relevance" in details_inner:
                    self._log(f'[DETAILS] R:{details_inner.get("relevance",0):.2f} C:{details_inner.get("correctness",0):.2f} F:{details_inner.get("fluency",0):.2f}')
                else:
                    self._log(f'[DETAILS] {str(details_inner)[:80]}')
            else:
                self._log(f'[DETAILS] {str(details_inner)[:80]}')
            
            self._log(f'═══════════════════════════════════════════════════════════════')

            # Log to JSON file
            test_logger.log_test(
                domain=domain,
                level=level,
                test_id=f"{domain}_L{level}",
                prompt=prompt,
                response=response_content,
                thinking=thinking_content,
                expected=expected,
                score=result.score,
                status=result.status,
                details=details,
                duration_ms=duration_ms,
                tokens=total_tokens,
                model_name=self.model_name
            )

            return {
                "prompt": prompt,
                "response": response_content,
                "expected": expected,
                "score": result.score,
                "status": result.status,
                "details": details,
                "duration_ms": duration_ms
            }
        except Exception as e:
            self._log(f'[ERROR] Exception: {type(e).__name__}: {str(e)[:100]}')
            return {
                "prompt": "",
                "response": "",
                "expected": None,
                "score": 0.0,
                "status": "failed",
                "details": f"Test error: {type(e).__name__}: {str(e)}",
                "duration_ms": 0
            }
    
    def _resolve_system_prompt(self, test: Dict[str, Any], domain_name: str) -> Optional[str]:
        """
        Resolve system prompt using 3-layer hierarchy:
        Domain-level → Level-level → Test-level with mode (overwrite/append)

        Args:
            test: Test dictionary (fresh from test_manager.list_tests)
            domain_name: Domain name to load

        Returns:
            Resolved system prompt or None
        """
        from evaluator.test_loader import test_loader, TestDefinition

        # Load domain first (always needed for fallback)
        domain = test_loader.load_domain(domain_name)

        # Load level definition
        level_num = test.get('level', 1)
        level_def = test_loader.load_level(domain_name, level_num)

        # Always build TestDefinition from the test dict (which is fresh from
        # test_manager.list_tests). Don't use test_loader.get_test() as it may
        # return stale cached data from a different TestLoader instance.
        test_def = TestDefinition(
            id=test.get('id', ''),
            name=test.get('name', ''),
            description=test.get('description', ''),
            prompt=test.get('prompt', ''),
            expected=test.get('expected', {}),
            evaluator_id=test.get('evaluator_id', ''),
            domain_id=domain_name,
            level=level_num,
            system_prompt=test.get('system_prompt'),
            system_prompt_mode=test.get('system_prompt_mode', 'overwrite')
        )

        # Use 3-layer hierarchy resolver
        resolved = test_loader.resolve_system_prompt(test_def, domain, level_def)

        # Determine source for logging
        if resolved:
            snippet = resolved.replace('\n', ' ').strip()[:100]
            if len(resolved) > 100:
                snippet += '...'

            sources = []
            if domain and domain.system_prompt:
                sources.append('DOMAIN')
            if level_def and level_def.system_prompt:
                sources.append(f'LEVEL(mode={level_def.system_prompt_mode})')
            if test_def.system_prompt:
                sources.append(f'TEST(mode={test_def.system_prompt_mode})')

            source = '+'.join(sources) if sources else 'UNKNOWN'

            self._log(f'[SYSTEM][{domain_name}][L{level_num}] Source: {source}')
            self._log(f'[SYSTEM][{domain_name}][L{level_num}] Prompt ({len(resolved)} chars): {snippet}')
        else:
            self._log(f'[SYSTEM][{domain_name}][L{level_num}] No system prompt at any level')

        return resolved

    def _resolve_registry_tools(self, test: Dict[str, Any], domain_name: str, level_num: int):
        """
        Resolve tools from the registry using 3-layer hierarchy (always append, deduplicated).

        Returns:
            (tools_list, mock_responses_dict, mock_response_types_dict)
        """
        from evaluator.test_loader import test_loader, TestDefinition

        domain = test_loader.load_domain(domain_name)
        level_def = test_loader.load_level(domain_name, level_num)

        test_def = TestDefinition(
            id=test.get('id', ''),
            name=test.get('name', ''),
            description=test.get('description', ''),
            prompt=test.get('prompt', ''),
            expected=test.get('expected', {}),
            evaluator_id=test.get('evaluator_id', ''),
            domain_id=domain_name,
            level=level_num,
            tool_ids=test.get('tool_ids')
        )

        resolved = test_loader.resolve_tools(test_def, domain, level_def)

        tools_list = []
        mock_responses = {}
        mock_response_types = {}

        for rt in resolved:
            tool_def = {"type": rt.get("type", "function"), "function": rt["function"]}
            tools_list.append(tool_def)

            func_name = rt["function"]["name"]
            if rt.get("mock_response") is not None:
                mock_responses[func_name] = rt["mock_response"]
                mock_response_types[func_name] = rt.get("mock_response_type", "json")

        return tools_list, mock_responses, mock_response_types

    def _format_tool_result_text(self, data, indent=0):
        """Convert tool result dict/list to plain text format to save tokens"""
        if not isinstance(data, (dict, list)):
            return str(data)
        lines = []
        prefix = "  " * indent
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    lines.append(f"{prefix}{key}:")
                    lines.append(self._format_tool_result_text(value, indent + 1))
                elif isinstance(value, list):
                    lines.append(f"{prefix}{key}:")
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            lines.append(f"{prefix}  [{i+1}]")
                            lines.append(self._format_tool_result_text(item, indent + 2))
                        else:
                            lines.append(f"{prefix}  - {item}")
                else:
                    lines.append(f"{prefix}{key}: {value}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    lines.append(f"{prefix}[{i+1}]")
                    lines.append(self._format_tool_result_text(item, indent + 1))
                else:
                    lines.append(f"{prefix}- {item}")
        return "\n".join(lines)

    def _execute_python_mock(self, py_code: str, args: dict):
        """Execute Python mock response via exec()"""
        import math, ast as _ast
        namespace = {
            'args': args,
            'math': math,
            'json': json,
            're': __import__('re'),
            'result': None,
        }
        try:
            exec(py_code, namespace)
            result = namespace.get('result')
            if result is None:
                return {"error": "mock did not set result"}
            return result
        except Exception as e:
            self._log(f'[PY-MOCK] Exception: {str(e)}')
            return {"error": f"Python mock failed: {str(e)}"}

    def _run_single_configurable_test(self, test: Dict[str, Any], domain: str,
                                       level: int, model_name: str, run_id: int) -> TestResult:
        """Run a single configurable test"""
        test_id = test['id']
        prompt = test['prompt']
        expected = test.get('expected', {})
        weight = test.get('weight', 1.0)
        
        # Initialize variables for tool calling
        loop_result = None
        tools = None
        
        self._log(f'')
        self._log(f'═══════════════════════════════════════════════════════════════')
        self._log(f'[TEST][{domain.upper()}][L{level}] {test.get("name", test_id)}')
        self._log(f'───────────────────────────────────────────────────────────────')
        
        # Truncate prompt for display
        prompt_display = prompt[:300] + '...' if len(prompt) > 300 else prompt
        prompt_display = prompt_display.replace('\n', ' ')
        self._log(f'[INPUT] {prompt_display}')
        
        if expected:
            expected_str = str(expected)[:100] + '...' if len(str(expected)) > 100 else str(expected)
            self._log(f'[EXPECTED] {expected_str}')
        
        # Resolve system prompt using hierarchy (domain → test with mode)
        system_prompt = self._resolve_system_prompt(test, domain)

        # Resolve registry tools (domain → level → test, append + dedup)
        registry_tools, registry_mocks, registry_mock_types = self._resolve_registry_tools(test, domain, level)

        # Check if test has embedded tools OR is tool_calling domain OR uses tool_call evaluator
        test_tools = test.get('tools') or []  # Handle None explicitly
        has_embedded_tools = len(test_tools) > 0
        evaluator_id = test.get('evaluator_id', '')
        uses_tool_evaluator = evaluator_id == 'tool_call'
        has_registry_tools = len(registry_tools) > 0

        if domain == "tool_calling" or has_embedded_tools or uses_tool_evaluator or has_registry_tools:
            # Start with registry tools (if any)
            tools = list(registry_tools)
            mock_responses = dict(registry_mocks)
            mock_response_types = dict(registry_mock_types)

            if has_embedded_tools:
                # Merge embedded tools (override registry tools with same function name)
                embedded_func_names = set()
                for t in test_tools:
                    tool_def = {
                        "type": "function",
                        "function": t.get("function", t)
                    }
                    func_name = t.get("function", {}).get("name") or t.get("name")
                    embedded_func_names.add(func_name)

                    # Replace or append
                    existing_idx = next((i for i, rt in enumerate(tools) if rt.get("function", {}).get("name") == func_name), None)
                    if existing_idx is not None:
                        tools[existing_idx] = tool_def
                    else:
                        tools.append(tool_def)

                    if "mock_response" in t:
                        mock_responses[func_name] = t["mock_response"]
                        mock_response_types[func_name] = "json"  # embedded are always JSON

                self._log(f'[TOOLS] Merged: registry({len(registry_tools)}) + embedded({len(test_tools)}) = {len(tools)} tools')
            elif has_registry_tools:
                self._log(f'[TOOLS] Using registry tools: {[t["function"]["name"] for t in tools]}')
            elif not tools:
                from evaluator.tools import tool_framework
                tools = tool_framework.tools
                mock_responses = None
                mock_response_types = {}
                self._log(f'[TOOLS] Available: {[t["function"]["name"] for t in tools]}')
            
            # Run tool calling loop
            loop_result = self._run_tool_calling_loop(prompt, tools, mock_responses, system_prompt=system_prompt, mock_response_types=mock_response_types)
            
            duration_ms = loop_result["total_duration_ms"]
            total_tokens = loop_result["total_tokens"]
            thinking_content = loop_result["thinking"]

            # Log thinking first (before summary)
            if thinking_content:
                if config.LOG_FULL_THINKING:
                    self._log(f'[THINKING] {thinking_content}')
                else:
                    self._log(f'[THINKING] Model used thinking ({len(thinking_content)} chars)')

            # Build response content with all tool calls
            all_tool_calls = loop_result["all_tool_calls"]
            if all_tool_calls:
                response_content = json.dumps({"tool_calls": all_tool_calls}, indent=2)
            else:
                response_content = loop_result["final_response"]

            self._log(f'[LLM] Total: {duration_ms}ms, {total_tokens} tokens, {loop_result["iterations"]} iteration(s)')
            self._log(f'[TOOLS] Made {len(all_tool_calls)} tool call(s): {[tc["function"]["name"] for tc in all_tool_calls]}')

            # Accumulate tokens and duration
            self.total_tokens += total_tokens
            self.total_duration_ms += duration_ms
        else:
            # Standard single-turn LLM call for other domains
            if system_prompt:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
                self._log(f'[SYSTEM] Using custom system prompt ({len(system_prompt)} chars)')
            else:
                messages = [{"role": "user", "content": prompt}]
            tools = None
            
            self._log(f'[LLM] Sending request to model...')
            llm_response = llm_client.chat_completion(messages, tools, enable_thinking=config.LLM_ENABLE_THINKING)
            
            duration_ms = llm_response.get("duration_ms", 0) if isinstance(llm_response, dict) else 0
            total_tokens = llm_response.get("total_tokens", 0) if isinstance(llm_response, dict) else 0
            self._log(f'[LLM] Response received in {duration_ms}ms, {total_tokens} tokens')
            
            # Accumulate tokens
            self.total_tokens += total_tokens
            self.total_duration_ms += duration_ms
            
            # Extract content with thinking separation
            content_info = llm_client.extract_content_with_thinking(llm_response)
            response_content = content_info["content"]
            thinking_content = content_info["thinking"]

            # Log thinking for single-turn path
            if thinking_content:
                if config.LOG_FULL_THINKING:
                    self._log(f'[THINKING] {thinking_content}')
                else:
                    self._log(f'[THINKING] Model used thinking ({len(thinking_content)} chars)')

        # Log response
        if config.LOG_FULL_RESPONSE:
            self._log(f'[OUTPUT] {response_content}')
        else:
            response_display = response_content[:200] + '...' if len(response_content) > 200 else response_content
            response_display = response_display.replace('\n', ' ')
            self._log(f'[OUTPUT] {response_display}')

        # Evaluate using appropriate evaluator
        evaluator_id = test.get('evaluator_id', '')
        
        # Check if we need to use a custom evaluator from test_definitions/evaluators/
        evaluator_config = test_loader.get_evaluator(evaluator_id) if evaluator_id else None
        
        if evaluator_config and evaluator_config.type in ('custom', 'regex', 'hybrid'):
            custom_eval = CustomEvaluator(evaluator_config.to_dict())
            self._log(f'[EVAL] Using custom evaluator: {evaluator_config.name} (type: {evaluator_config.type})')
            result = custom_eval.evaluate(response_content, expected, level)
        elif evaluator_id:
            # Use built-in evaluator type (tool_call, keyword, two_pass, sql_executor)
            evaluator = get_evaluator(domain, evaluator_type=evaluator_id)
            self._log(f'[EVAL] Using {evaluator.name} (type: {evaluator_id})')
            result = evaluator.evaluate(response_content, expected, level)
        else:
            # Fall back to domain default evaluator
            evaluator = get_evaluator(domain)
            self._log(f'[EVAL] Using {evaluator.name} (PASS2: {evaluator.uses_pass2})')
            result = evaluator.evaluate(response_content, expected, level)
        
        # Build details
        details = result.details if hasattr(result, 'details') else {}
        if not isinstance(details, dict):
            details = {"details": str(details)}
        
        # Add evaluator info
        if evaluator_config and evaluator_config.type == 'custom':
            details["evaluator"] = f"custom:{evaluator_config.name}"
        elif evaluator_config:
            details["evaluator"] = evaluator_config.name
            details["uses_pass2"] = evaluator_config.uses_pass2
        else:
            details["evaluator"] = "unknown"
        
        # Include response in details for modal display
        details['response'] = response_content
        details['duration_ms'] = duration_ms
        
        # Add thinking content to details if present
        if thinking_content:
            details["thinking"] = thinking_content
        
        # Add conversation log (for tool-calling tests or any test with multi-turn interaction)
        if loop_result and loop_result.get("conversation_log"):
            details["conversation_log"] = loop_result["conversation_log"]
        
        # Store tool definitions for UI display (only for tool-calling tests)
        if (domain == "tool_calling" or has_embedded_tools) and tools:
                details["tools_available"] = [
                    {
                        "name": t.get("function", {}).get("name", ""),
                        "description": t.get("function", {}).get("description", ""),
                        "parameters": t.get("function", {}).get("parameters", {})
                    }
                    for t in tools
                ]
        
        # Log result
        status_icon = '✓' if result.status == 'passed' else '✗'
        self._log(f'[RESULT] {status_icon} Status: {result.status.upper()}, Score: {result.score*100:.0f}%')
        
        # Save individual test result with resolved system_prompt and mode
        db.save_individual_test_result(
            run_id=run_id,
            test_id=test_id,
            domain=domain,
            level=level,
            prompt=prompt,
            response=response_content,
            expected=json.dumps(expected) if expected else None,
            score=result.score,
            status=result.status,
            details=json.dumps(details) if details else None,
            duration_ms=duration_ms,
            model_name=model_name,
            system_prompt=system_prompt,  # Save the resolved system prompt that was actually used
            system_prompt_mode=test.get('system_prompt_mode', 'overwrite')  # Save the mode
        )
        
        self._log(f'═══════════════════════════════════════════════════════════════')
        
        # Log to JSON file
        test_logger.log_test(
            domain=domain,
            level=level,
            test_id=test_id,
            prompt=prompt,
            response=response_content,
            thinking=thinking_content,
            expected=expected,
            score=result.score,
            status=result.status,
            details=details,
            duration_ms=duration_ms,
            tokens=total_tokens,
            model_name=model_name
        )
        
        return TestResult(
            test_id=test_id,
            domain=domain,
            level=level,
            score=result.score,
            status=result.status,
            weight=weight,
            details=details
        )
    
    def _generate_summary(self, run_id: int, model_name: str):
        """Generate executive summary"""
        self._log('[INFO] Semua tes selesai. Membuat ringkasan...')
        test_results = db.get_test_results(run_id)
        
        # Convert database rows to dict format
        results_dict = []
        for result in test_results:
            results_dict.append({
                "domain": result["domain"],
                "level": result["level"],
                "score": result["score"],
                "status": result["status"]
            })
        
        # Generate summary
        summary = scoring_engine.generate_summary(results_dict, model_name, llm_client=llm_client)
        overall_score = scoring_engine.calculate_overall_score(results_dict)
        
        # Store summary with token stats
        db.complete_evaluation_run(
            run_id, summary, overall_score,
            total_tokens=self.total_tokens,
            total_duration_ms=self.total_duration_ms
        )
    
    def _run_tool_calling_loop(self, prompt: str, tools: list, mock_responses: Dict[str, Any] = None, system_prompt: str = None, mock_response_types: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Run multi-turn tool calling loop with mock execution.
        
        Args:
            prompt: User prompt
            tools: List of tool definitions (OpenAI format)
            mock_responses: Optional dict mapping tool name -> mock response
                           If provided, uses these instead of tool_framework
            system_prompt: Optional system prompt
        
        Continues until:
        - LLM returns final answer (no tool calls)
        - OR max iterations reached
        
        Returns:
            Dict with:
            - all_tool_calls: List of all tool calls made
            - final_response: Final text response
            - iterations: Number of iterations
            - total_duration_ms: Total duration
            - total_tokens: Total tokens used
            - thinking: Thinking content (if any)
            - messages: Full conversation history
        """
        from evaluator.tools import tool_framework
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        all_tool_calls = []
        conversation_log = []  # Capture each turn's details
        total_duration_ms = 0
        total_tokens = 0
        thinking_content = None
        final_response = ""
        
        for iteration in range(MAX_TOOL_ITERATIONS):
            self._log(f'[TOOL-LOOP] Iteration {iteration + 1}/{MAX_TOOL_ITERATIONS}')
            
            # Initialize turn log
            turn_log = {
                "turn": iteration + 1,
                "thinking": None,
                "tool_calls": [],
                "tool_results": [],
                "response": None
            }
            
            # Send to LLM
            llm_response = llm_client.chat_completion(messages, tools, enable_thinking=config.LLM_ENABLE_THINKING)
            
            # Accumulate stats
            duration_ms = llm_response.get("duration_ms", 0) if isinstance(llm_response, dict) else 0
            tokens = llm_response.get("total_tokens", 0) if isinstance(llm_response, dict) else 0
            total_duration_ms += duration_ms
            total_tokens += tokens
            
            # Extract content and thinking
            content_info = llm_client.extract_content_with_thinking(llm_response)
            response_content = content_info["content"]
            
            # Capture thinking for this turn
            turn_thinking = content_info.get("thinking")
            if turn_thinking:
                turn_log["thinking"] = turn_thinking
                # Also store first turn thinking as main thinking
                if iteration == 0:
                    thinking_content = turn_thinking
            
            # Check for tool calls
            tool_calls = content_info.get("tool_calls", [])
            
            # Also try to extract from response content if it's JSON
            if not tool_calls:
                try:
                    data = json.loads(response_content)
                    if isinstance(data, dict) and "tool_calls" in data:
                        tool_calls = data["tool_calls"]
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # If no tool calls, we have the final answer
            if not tool_calls:
                final_response = response_content
                turn_log["response"] = response_content
                conversation_log.append(turn_log)
                self._log(f'[TOOL-LOOP] Final answer received (no more tool calls)')
                break
            
            # Process tool calls
            self._log(f'[TOOL-LOOP] Got {len(tool_calls)} tool call(s)')
            
            for tc in tool_calls:
                func_name = tc.get("function", {}).get("name", "unknown")
                func_args_str = tc.get("function", {}).get("arguments", "{}")
                tc_id = tc.get("id", f"call_{len(all_tool_calls)}")
                
                # Parse arguments
                try:
                    func_args = json.loads(func_args_str) if isinstance(func_args_str, str) else func_args_str
                except json.JSONDecodeError:
                    func_args = {}
                
                self._log(f'[TOOL-CALL] {func_name}({json.dumps(func_args)[:50]}...)')
                
                # Store tool call info
                tool_call_info = {
                    "id": tc_id,
                    "function": {
                        "name": func_name,
                        "arguments": func_args_str if isinstance(func_args_str, str) else json.dumps(func_args)
                    }
                }
                all_tool_calls.append(tool_call_info)
                
                # Execute mock tool - check mock_responses first (registry + embedded)
                if mock_responses and func_name in mock_responses:
                    mock_value = mock_responses[func_name]
                    mock_type = (mock_response_types or {}).get(func_name, 'json')

                    if mock_type in ('javascript', 'python') and isinstance(mock_value, str):
                        # Execute Python mock
                        mock_result_data = self._execute_python_mock(mock_value, func_args)
                        self._log(f'[MOCK] Executed Python mock for {func_name}')
                    else:
                        mock_result_data = mock_value
                        self._log(f'[MOCK] Using mock response for {func_name}')

                    mock_result = {
                        "tool_call_id": tc_id,
                        "function_name": func_name,
                        "result": mock_result_data,
                        "success": True
                    }
                else:
                    # Fall back to tool_framework
                    mock_result = tool_framework.execute_tool({
                        "id": tc_id,
                        "function": {
                            "name": func_name,
                            "arguments": json.dumps(func_args) if isinstance(func_args, dict) else func_args_str
                        }
                    })
                
                result_str = self._format_tool_result_text(mock_result.get("result", {}))
                self._log(f'[TOOL-RESULT] {result_str[:100]}...')
                
                # Add to turn log
                turn_log["tool_calls"].append({
                    "name": func_name,
                    "arguments": func_args,
                    "id": tc_id
                })
                turn_log["tool_results"].append({
                    "tool_call_id": tc_id,
                    "function_name": func_name,
                    "result": mock_result.get("result", {})
                })
                
                # Add to conversation
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result_str
                })
            
            # Add turn to conversation log
            conversation_log.append(turn_log)
        
        return {
            "all_tool_calls": all_tool_calls,
            "final_response": final_response,
            "iterations": iteration + 1,
            "total_duration_ms": total_duration_ms,
            "total_tokens": total_tokens,
            "thinking": thinking_content,
            "conversation_log": conversation_log,
            "messages": messages
        }
    
    def get_test_matrix(self, run_id: Optional[int] = None) -> Dict[str, Any]:
        """Get test matrix for UI display"""
        if not run_id:
            run_id = self.current_run_id

        if not run_id:
            return {"domains": {}, "status": "no_run"}

        test_results = db.get_test_results(run_id)

        # Organize by domain and level
        matrix = {}
        
        # Get domains from test definitions or use legacy
        if self.use_configurable_tests:
            domains = [d['id'] for d in test_manager.list_domains()]
        else:
            domains = ["conversation", "math", "sql", "tool_calling", "reasoning"]
        
        for domain in domains:
            matrix[domain] = {}
            for level in range(1, 6):
                matrix[domain][level] = {
                    "status": "pending",
                    "score": None,
                    "details": None,
                    "prompt": None,
                    "response": None,
                    "expected": None,
                    "duration_ms": None
                }

        # Fill with actual results
        for result in test_results:
            domain = result["domain"]
            level = result["level"]

            if domain in matrix and level in matrix[domain]:
                matrix[domain][level] = {
                    "status": result["status"],
                    "score": result["score"],
                    "details": json.loads(result["details"]) if result["details"] else None,
                    "prompt": result.get("prompt"),
                    "response": result.get("response"),
                    "expected": json.loads(result["expected"]) if result.get("expected") else None,
                    "duration_ms": result.get("duration_ms"),
                    "model_name": result.get("model_name")
                }

        # Get run info for model name
        run_info = db.get_evaluation_run(run_id)
        model_name = run_info.get("model_name") if run_info else None
        
        # Determine status
        if self.is_running:
            status = "running"
        elif self.has_error:
            status = "error"
        elif self.was_interrupted:
            status = "interrupted"
        else:
            status = "completed"
        
        # Calculate tok/s
        tok_per_sec = None
        if self.total_duration_ms > 0:
            tok_per_sec = (self.total_tokens / self.total_duration_ms) * 1000

        # Count completed individual tests for accurate progress
        individual_results = db.get_individual_test_results(run_id)
        completed_tests = len(individual_results)

        return {
            "domains": matrix,
            "run_id": run_id,
            "model_name": model_name,
            "status": status,
            "completed_tests": completed_tests,
            "overall_score": run_info.get("overall_score") if run_info else None,
            "tok_per_sec": round(tok_per_sec, 1) if tok_per_sec else None,
            "total_tokens": self.total_tokens,
            "total_duration_ms": self.total_duration_ms,
            "error_message": self.error_message if self.has_error else None
        }


# Global evaluation engine instance (uses legacy tests by default)
evaluation_engine = EvaluationEngine(use_configurable_tests=True)

# Configurable test engine (for when user wants to use JSON test definitions)
configurable_engine = EvaluationEngine(use_configurable_tests=True)
