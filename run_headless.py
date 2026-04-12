#!/usr/bin/env python3
"""
Headless LLM Evaluation Runner
Runs evaluation without web UI - useful for CI/CD and automated testing.

Usage:
    python run_headless.py --endpoint http://192.168.1.7:8080/v1 --model llama-3.2
    python run_headless.py --endpoint http://localhost:8080/v1 --model default --output results.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List
import traceback

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evaluator.engine import EvaluationEngine
from models.db import db


class TestLogger:
    """Detailed logger for failed tests"""
    
    def __init__(self, output_dir: str = "logs"):
        self.output_dir = output_dir
        self.failed_tests: List[Dict[str, Any]] = []
        os.makedirs(output_dir, exist_ok=True)
    
    def log_test(self, domain: str, level: int, prompt: str, response: str, 
                 expected: Any, score: float, status: str, details: Any, 
                 duration_ms: int, error: str = None):
        """Log a test result"""
        if status == "failed" or score < 0.8:
            self.failed_tests.append({
                "domain": domain,
                "level": level,
                "prompt": prompt,
                "response": response,
                "expected": expected,
                "score": score,
                "status": status,
                "details": details,
                "duration_ms": duration_ms,
                "error": error
            })
    
    def save(self, model: str, endpoint: str, overall_score: float):
        """Save failed tests to JSON file"""
        if not self.failed_tests:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"failed_tests_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        report = {
            "summary": {
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "endpoint": endpoint,
                "overall_score": overall_score,
                "total_failed": len(self.failed_tests)
            },
            "failed_tests": self.failed_tests
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        return filepath
    
    def generate_readable_report(self, model: str, endpoint: str, overall_score: float):
        """Generate human-readable text report"""
        if not self.failed_tests:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"failed_tests_{timestamp}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        lines = [
            "=" * 80,
            "FAILED TESTS REPORT",
            "=" * 80,
            f"Timestamp: {datetime.now().isoformat()}",
            f"Model: {model}",
            f"Endpoint: {endpoint}",
            f"Overall Score: {overall_score*100:.1f}%",
            f"Total Failed Tests: {len(self.failed_tests)}",
            "=" * 80,
            ""
        ]
        
        for i, test in enumerate(self.failed_tests, 1):
            lines.extend([
                f"TEST #{i}: {test['domain'].upper()} Level {test['level']}",
                "-" * 80,
                f"Score: {test['score']*100:.1f}% | Status: {test['status'].upper()} | Duration: {test['duration_ms']}ms",
                "",
                "INPUT (Prompt):",
                "-" * 40,
                test['prompt'] or "(none)",
                "",
                "EXPECTED:",
                "-" * 40,
                str(test['expected']) if test['expected'] else "(none)",
                "",
                "OUTPUT (Response):",
                "-" * 40,
                test['response'] or "(none)",
                "",
                "DETAILS:",
                "-" * 40,
                str(test['details']) if test['details'] else "(none)",
                ""
            ])
            
            if test.get('error'):
                lines.extend([
                    "ERROR:",
                    "-" * 40,
                    test['error'],
                    ""
                ])
            
            lines.append("=" * 80)
            lines.append("")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        return filepath


class HeadlessRunner:
    """Run evaluation in headless mode (no web UI)"""
    
    def __init__(self, endpoint: str, model: str, api_key: str = "", log_dir: str = "logs"):
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.results: List[Dict[str, Any]] = []
        self.run_id: int = 0
        self.logger = TestLogger(log_dir)
        
    def configure(self):
        """Configure the LLM client with the provided endpoint"""
        import config
        config.LLM_BASE_URL = self.endpoint
        config.LLM_API_KEY = self.api_key
        config.LLM_MODEL = self.model
        
        # Reinitialize the LLM client with new config
        from evaluator import llm_client
        llm_client.base_url = self.endpoint
        llm_client.api_key = self.api_key
        llm_client.model = self.model
        
    def run(self, domains: List[str] = None, levels: List[int] = None) -> Dict[str, Any]:
        """Run the evaluation
        
        Args:
            domains: List of domains to test (default: all)
            levels: List of levels to test (default: 1-5)
        
        Returns:
            Dictionary with run_id, results, and summary
        """
        if domains is None:
            domains = ["conversation", "math", "sql", "tool_calling", "reasoning", "health"]
        if levels is None:
            levels = [1, 2, 3, 4, 5]
        
        # Create evaluation run
        self.run_id = db.create_evaluation_run(self.model)
        
        print(f"\n{'='*70}")
        print(f"LLM EVALUATION - HEADLESS MODE")
        print(f"{'='*70}")
        print(f"Endpoint: {self.endpoint}")
        print(f"Model: {self.model}")
        print(f"Run ID: {self.run_id}")
        print(f"Domains: {', '.join(domains)}")
        print(f"Levels: {', '.join(map(str, levels))}")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        total_tests = len(domains) * len(levels)
        completed = 0
        passed = 0
        domain_scores = {}  # Track domain scores during execution
        
        for domain in domains:
            print(f"\n[{domain.upper()}]")
            domain_results = []
            domain_passed = 0
            
            for level in levels:
                result = self._run_test(domain, level)
                self.results.append(result)
                domain_results.append(result)
                completed += 1
                
                status_icon = "✓" if result["status"] == "passed" else "✗"
                if result["status"] == "passed":
                    passed += 1
                    domain_passed += 1
                
                print(f"  Level {level}: {status_icon} {result['status'].upper()} (score: {result['score']*100:.0f}%) [{result['duration_ms']}ms]")
                
                # Small delay between tests
                time.sleep(0.3)
            
            # Calculate and display domain score after completing all levels
            if domain_results:
                avg_score = sum(r["score"] for r in domain_results) / len(domain_results)
                domain_scores[domain] = round(avg_score, 3)
                bar = "█" * int(avg_score * 10) + "░" * (10 - int(avg_score * 10))
                print(f"  ─────────────────────────────────")
                print(f"  Domain Total: {bar} {avg_score*100:.0f}% ({domain_passed}/{len(levels)} passed)")
        
        elapsed_time = time.time() - start_time
        
        # Calculate overall score
        overall_score = sum(r["score"] for r in self.results) / len(self.results) if self.results else 0
        
        # Generate and store summary
        summary = self._generate_summary(domain_scores, overall_score, passed, total_tests, elapsed_time)
        db.complete_evaluation_run(self.run_id, summary, overall_score)
        
        # Save failed tests logs
        json_log = self.logger.save(self.model, self.endpoint, overall_score)
        txt_log = self.logger.generate_readable_report(self.model, self.endpoint, overall_score)
        
        # Print final summary
        print(f"\n{'='*70}")
        print("EVALUATION COMPLETE")
        print(f"{'='*70}")
        print(f"Total Tests: {completed}")
        print(f"Passed: {passed}/{total_tests} ({passed/total_tests*100:.0f}%)")
        print(f"Overall Score: {overall_score*100:.1f}%")
        print(f"Elapsed Time: {elapsed_time:.1f}s")
        print(f"\n{'DOMAIN':<15} {'SCORE':<8} {'BAR':<12} {'PASSED'}")
        print(f"{'-'*15} {'-'*8} {'-'*12} {'-'*10}")
        for domain, score in domain_scores.items():
            bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
            domain_results = [r for r in self.results if r["domain"] == domain]
            domain_passed = sum(1 for r in domain_results if r["status"] == "passed")
            print(f"{domain:<15} {score*100:>5.0f}%   {bar} {domain_passed}/5")
        print(f"\nRun ID: {self.run_id}")
        print(f"{'='*70}\n")
        
        # Print log file paths
        if json_log or txt_log:
            print(f"Failed Tests Logs:")
            if json_log:
                print(f"  JSON: {json_log}")
            if txt_log:
                print(f"  Text: {txt_log}")
            print()
        
        return {
            "run_id": self.run_id,
            "endpoint": self.endpoint,
            "model": self.model,
            "overall_score": overall_score,
            "passed": passed,
            "total": total_tests,
            "elapsed_time": elapsed_time,
            "domain_scores": domain_scores,
            "results": self.results,
            "summary": summary,
            "log_files": {
                "json": json_log,
                "txt": txt_log
            }
        }
    
    def _run_test(self, domain: str, level: int) -> Dict[str, Any]:
        """Run a single test"""
        from tests import get_test_class
        from evaluator.llm_client import llm_client
        from evaluator.scoring import scoring_engine
        
        prompt = ""
        expected = None
        error_msg = None
        
        try:
            test_class = get_test_class(domain)
            if not test_class:
                error_msg = f"Unknown domain: {domain}"
                self.logger.log_test(domain, level, "", "", None, 0.0, "failed", 
                                     error_msg, 0, error_msg)
                return {
                    "domain": domain,
                    "level": level,
                    "status": "failed",
                    "score": 0.0,
                    "response": "",
                    "expected": None,
                    "details": error_msg,
                    "duration_ms": 0
                }
            
            test_instance = test_class(level)
            prompt = test_instance.get_prompt()
            expected = test_instance.get_expected()
            
            messages = [{"role": "user", "content": prompt}]
            
            # Add tools for tool_calling domain
            tools = None
            if domain == "tool_calling":
                from evaluator.tools import tool_framework
                tools = tool_framework.tools
            
            llm_response = llm_client.chat_completion(messages, tools)
            duration_ms = llm_response.get("duration_ms", 0) if isinstance(llm_response, dict) else 0
            
            response_content = llm_client.extract_content(llm_response)
            
            # Check for errors in response
            if response_content.startswith("Error:"):
                error_msg = response_content
            
            # Score the response
            scoring_result = scoring_engine.score_test(domain, level, response_content, expected)
            
            # Log the test
            self.logger.log_test(
                domain, level, prompt, response_content, expected,
                scoring_result["score"], scoring_result["status"],
                scoring_result["details"], duration_ms, error_msg
            )
            
            # Store in database
            db.update_test_result(
                self.run_id, domain, level,
                prompt=prompt,
                response=response_content,
                expected=json.dumps(expected) if expected else None,
                score=scoring_result["score"],
                status=scoring_result["status"],
                details=json.dumps(scoring_result["details"]) if scoring_result["details"] else None,
                duration_ms=duration_ms
            )
            
            return {
                "domain": domain,
                "level": level,
                "status": scoring_result["status"],
                "score": scoring_result["score"],
                "response": response_content[:500],  # Truncate for output
                "expected": expected,
                "details": scoring_result["details"],
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"  Level {level}: ERROR - {error_msg[:100]}")
            
            # Log the error
            self.logger.log_test(domain, level, prompt, "", expected, 0.0, "failed",
                               f"Error: {error_msg}", 0, error_msg)
            
            return {
                "domain": domain,
                "level": level,
                "status": "failed",
                "score": 0.0,
                "response": "",
                "expected": expected,
                "details": f"Error: {error_msg}",
                "duration_ms": 0
            }
    
    def _generate_summary(self, domain_scores: Dict[str, float], overall_score: float, 
                          passed: int, total: int, elapsed: float) -> str:
        """Generate a summary string"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        summary = f"""
LLM Evaluation Summary
======================
Timestamp: {timestamp}
Endpoint: {self.endpoint}
Model: {self.model}

Overall Score: {overall_score*100:.1f}%
Tests Passed: {passed}/{total}

Domain Breakdown:
{chr(10).join(f"  - {k}: {v*100:.0f}%" for k, v in domain_scores.items())}

Elapsed Time: {elapsed:.1f} seconds
Run ID: {self.run_id}
"""
        return summary.strip()
    
    def save_results(self, output_path: str):
        """Save results to JSON file"""
        output_data = {
            "run_id": self.run_id,
            "endpoint": self.endpoint,
            "model": self.model,
            "results": self.results,
            "summary": self._generate_summary if hasattr(self, '_generate_summary') else None
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Run LLM evaluation in headless mode")
    parser.add_argument("--endpoint", "-e", default=None, help="LLM API endpoint (or set LLM_BASE_URL env var)")
    parser.add_argument("--model", "-m", default=None, help="Model name (or set LLM_MODEL env var)")
    parser.add_argument("--api-key", "-k", default=None, help="API key (or set LLM_API_KEY env var)")
    parser.add_argument("--output", "-o", default=None, help="Output JSON file path")
    parser.add_argument("--log-dir", "-L", default="logs", help="Directory for failed tests logs (default: logs)")
    parser.add_argument("--domains", "-d", nargs="+", default=None, 
                        choices=["conversation", "math", "sql", "tool_calling", "reasoning"],
                        help="Domains to test (default: all)")
    parser.add_argument("--levels", "-l", nargs="+", type=int, default=None,
                        help="Levels to test (default: 1-5)")
    parser.add_argument("--timeout", "-t", type=int, default=120, help="Request timeout in seconds")
    
    args = parser.parse_args()
    
    # Use environment variables as defaults
    endpoint = args.endpoint or os.environ.get("LLM_BASE_URL", "http://localhost:8080/v1")
    model = args.model or os.environ.get("LLM_MODEL", "default")
    api_key = args.api_key if args.api_key is not None else os.environ.get("LLM_API_KEY", "")
    
    # Set timeout
    import config
    config.LLM_TIMEOUT = args.timeout
    
    # Create and configure runner
    runner = HeadlessRunner(
        endpoint=endpoint,
        model=model,
        api_key=api_key,
        log_dir=args.log_dir
    )
    runner.configure()
    
    # Run evaluation
    results = runner.run(
        domains=args.domains,
        levels=args.levels
    )
    
    # Save results if output path specified
    if args.output:
        runner.save_results(args.output)
    
    # Return exit code based on pass rate
    pass_rate = results["passed"] / results["total"]
    if pass_rate >= 0.5:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()