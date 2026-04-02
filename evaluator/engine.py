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


class EvaluationEngine:
    def __init__(self, use_configurable_tests: bool = False):
        """
        Initialize evaluation engine.
        
        Args:
            use_configurable_tests: If True, load tests from test_definitions/
                                   If False, use legacy hardcoded tests
        """
        self.current_run_id: Optional[str] = None
        self.is_running = False
        self.was_interrupted = False
        self.lock = Lock()
        self.thread: Optional[Thread] = None
        self.log_queue = queue.Queue()
        self.use_configurable_tests = use_configurable_tests
        self.total_tokens = 0
        self.total_duration_ms = 0
        self.model_name: Optional[str] = None
    
    def _log(self, message: str):
        """Log a message to the queue"""
        timestamp = time.strftime('%H:%M:%S')
        self.log_queue.put(f"[{timestamp}] {message}")
    
    def start_evaluation(self, model_name: str = None) -> str:
        """Start a new evaluation run"""
        with self.lock:
            if self.is_running:
                raise Exception("Evaluation already running")
            
            # Use config model if not specified
            if model_name is None or model_name == "default":
                model_name = config.LLM_MODEL
            
            self.model_name = model_name
            self.current_run_id = db.create_evaluation_run(model_name)
            self.is_running = True
            self.was_interrupted = False
            self.total_tokens = 0
            self.total_duration_ms = 0
            self._log(f'[INFO] Memulai evaluasi untuk model: {model_name}')
            
            # Start test logger
            test_logger.start_run(self.current_run_id, model_name)
            
            # Start evaluation in background thread
            self.thread = Thread(target=self._run_evaluation, args=(self.current_run_id, model_name))
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
                "tok_per_sec": round(tok_per_sec, 1) if tok_per_sec else None
            }
    
    def _run_evaluation(self, run_id: str, model_name: str):
        """Main evaluation loop - supports both legacy and configurable tests"""
        self._log(f'[SYSTEM] Evaluation thread (run_id: {run_id}) dimulai.')
        
        try:
            if self.use_configurable_tests:
                self._run_configurable_evaluation(run_id, model_name)
            else:
                self._run_legacy_evaluation(run_id, model_name)
            
            # Generate summary after all tests
            if self.is_running:
                self._generate_summary(run_id, model_name)
                
        except Exception as e:
            self._log(f'[ERROR] Evaluation error: {e}')
            print(f"Evaluation error: {e}")
        finally:
            with self.lock:
                self.is_running = False
            
            # Finalize test logger
            final_status = "completed" if not self.was_interrupted else "interrupted"
            test_logger.finalize_run(status=final_status)
    
    def _run_legacy_evaluation(self, run_id: str, model_name: str):
        """Run evaluation using legacy hardcoded tests"""
        domains = ["conversation", "math", "sql", "tool_calling", "reasoning"]
        
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
    
    def _run_configurable_evaluation(self, run_id: str, model_name: str):
        """Run evaluation using configurable test definitions"""
        # Sync tests from files to database
        test_manager.sync_to_db()
        
        # Load all domains
        domains = test_manager.list_domains()
        
        for domain_data in domains:
            domain_id = domain_data['id']
            
            # Skip disabled domains
            if not domain_data.get('enabled', True):
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
                    db.update_test_result(
                        run_id, domain_id, level,
                        prompt=first_prompt,
                        response=test_results[0].details.get('response') if test_results[0].details else None,
                        expected=json.dumps(first_expected) if first_expected else None,
                        score=avg_score,
                        status=status,
                        model_name=model_name
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

            # Send to LLM (PASS 1)
            messages = [{"role": "user", "content": prompt}]

            # Add tools for tool_calling domain
            tools = None
            if domain == "tool_calling":
                from evaluator.tools import tool_framework
                tools = tool_framework.tools
                self._log(f'[TOOLS] Available: {[t["function"]["name"] for t in tools]}')

            self._log(f'[LLM] Sending request to model...')
            llm_response = llm_client.chat_completion(messages, tools)
            
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
            raw_content = content_info["raw"]  # Original content
            
            # Log if thinking content was detected
            if thinking_content:
                self._log(f'[THINKING] Model used thinking ({len(thinking_content)} chars)')
            
            # Log response (truncated)
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
    
    def _run_single_configurable_test(self, test: Dict[str, Any], domain: str, 
                                       level: int, model_name: str, run_id: str) -> TestResult:
        """Run a single configurable test"""
        test_id = test['id']
        prompt = test['prompt']
        expected = test.get('expected', {})
        weight = test.get('weight', 1.0)
        
        self._log(f'')
        self._log(f'═══════════════════════════════════════════════════════════════')
        self._log(f'[TEST] {test.get("name", test_id)} ({domain} L{level})')
        self._log(f'───────────────────────────────────────────────────────────────')
        
        # Truncate prompt for display
        prompt_display = prompt[:300] + '...' if len(prompt) > 300 else prompt
        prompt_display = prompt_display.replace('\n', ' ')
        self._log(f'[INPUT] {prompt_display}')
        
        if expected:
            expected_str = str(expected)[:100] + '...' if len(str(expected)) > 100 else str(expected)
            self._log(f'[EXPECTED] {expected_str}')
        
        # Send to LLM
        messages = [{"role": "user", "content": prompt}]
        tools = None
        
        # Add tools for tool_calling domain
        if domain == "tool_calling":
            from evaluator.tools import tool_framework
            tools = tool_framework.tools
            self._log(f'[TOOLS] Available: {[t["function"]["name"] for t in tools]}')
        
        self._log(f'[LLM] Sending request to model...')
        llm_response = llm_client.chat_completion(messages, tools)
        
        duration_ms = llm_response.get("duration_ms", 0) if isinstance(llm_response, dict) else 0
        total_tokens = llm_response.get("total_tokens", 0) if isinstance(llm_response, dict) else 0
        self._log(f'[LLM] Response received in {duration_ms}ms, {total_tokens} tokens')
        
        # Accumulate tokens
        self.total_tokens += total_tokens
        self.total_duration_ms += duration_ms
        
        response_content = llm_client.extract_content(llm_response)
        
        # Log response
        response_display = response_content[:200] + '...' if len(response_content) > 200 else response_content
        response_display = response_display.replace('\n', ' ')
        self._log(f'[OUTPUT] {response_display}')
        
        # Evaluate using appropriate evaluator
        evaluator_id = test.get('evaluator_id', '')
        
        # Try to get predefined evaluator first
        evaluator = get_evaluator(domain)  # Legacy evaluator
        
        # Check if we need to use a custom evaluator
        evaluator_config = test_loader.get_evaluator(evaluator_id)
        if evaluator_config and evaluator_config.type == 'custom':
            custom_eval = CustomEvaluator(evaluator_config.to_dict())
            self._log(f'[EVAL] Using custom evaluator: {evaluator_config.name}')
            result = custom_eval.evaluate(response_content, expected, level)
        else:
            # Use domain evaluator
            self._log(f'[EVAL] Using {evaluator.name} (PASS2: {evaluator.uses_pass2})')
            result = evaluator.evaluate(response_content, expected, level)
        
        # Build details
        details = result.details if hasattr(result, 'details') else {}
        if not isinstance(details, dict):
            details = {"details": str(details)}
        
        # Include response in details for modal display
        details['response'] = response_content
        
        # Log result
        status_icon = '✓' if result.status == 'passed' else '✗'
        self._log(f'[RESULT] {status_icon} Status: {result.status.upper()}, Score: {result.score*100:.0f}%')
        
        # Save individual test result
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
            model_name=model_name
        )
        
        self._log(f'═══════════════════════════════════════════════════════════════')
        
        # Log to JSON file
        test_logger.log_test(
            domain=domain,
            level=level,
            test_id=test_id,
            prompt=prompt,
            response=response_content,
            thinking=None,  # TODO: extract thinking from configurable tests
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
    
    def _generate_summary(self, run_id: str, model_name: str):
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
        summary = scoring_engine.generate_summary(results_dict, model_name)
        overall_score = scoring_engine.calculate_overall_score(results_dict)
        
        # Store summary with token stats
        db.complete_evaluation_run(
            run_id, summary, overall_score,
            total_tokens=self.total_tokens,
            total_duration_ms=self.total_duration_ms
        )
    
    def get_test_matrix(self, run_id: Optional[str] = None) -> Dict[str, Any]:
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
        elif self.was_interrupted:
            status = "interrupted"
        else:
            status = "completed"
        
        # Calculate tok/s
        tok_per_sec = None
        if self.total_duration_ms > 0:
            tok_per_sec = (self.total_tokens / self.total_duration_ms) * 1000

        return {
            "domains": matrix,
            "run_id": run_id,
            "model_name": model_name,
            "status": status,
            "tok_per_sec": round(tok_per_sec, 1) if tok_per_sec else None,
            "total_tokens": self.total_tokens,
            "total_duration_ms": self.total_duration_ms
        }


# Global evaluation engine instance (uses legacy tests by default)
evaluation_engine = EvaluationEngine(use_configurable_tests=True)

# Configurable test engine (for when user wants to use JSON test definitions)
configurable_engine = EvaluationEngine(use_configurable_tests=True)