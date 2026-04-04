"""Analyze evaluation failures using Claude Opus API to identify patterns and root causes."""

import json
import os
from typing import Any, Dict, List

from anthropic import Anthropic

ANALYSIS_SYSTEM_PROMPT = """\
You are an expert LLM evaluation analyst specializing in fine-tuned models for \
Indonesian-language villa customer service. Your job is to analyze failed evaluation \
tests and identify patterns, root causes, and actionable improvements.

You will receive a batch of failed test results across domains: conversation, math, \
sql, tool_calling, reasoning, and health. Each test has a prompt, expected output, actual \
response, score, and scoring details.

Respond with a JSON object (no markdown fences) following this schema:
{
  "summary": "Brief overall analysis",
  "failure_count": <int>,
  "patterns": [
    {
      "pattern_id": "<domain>_<short_label>",
      "domain": "<domain>",
      "description": "What went wrong",
      "affected_levels": [<int>, ...],
      "root_cause": "Why it went wrong",
      "severity": "high|medium|low",
      "suggested_fix": "How to fix via training data"
    }
  ],
  "domain_analysis": {
    "<domain>": {
      "pass_rate": <float>,
      "weakest_level": <int>,
      "key_issues": ["..."],
      "training_priority": "high|medium|low"
    }
  },
  "training_recommendations": [
    {
      "priority": <int>,
      "domain": "<domain>",
      "action": "generate|adjust|remove",
      "description": "What training data to create or change",
      "example_count": <int>
    }
  ]
}\
"""


class FailureAnalyzer:
    """Analyze evaluation failures using Claude Opus to identify patterns and root causes."""

    def __init__(self, api_key: str = None, model: str = "claude-opus-4-0"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.client = Anthropic(api_key=self.api_key)

    def analyze_failures(self, failed_tests: List[Dict[str, Any]], run_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Analyze a batch of failed tests and return structured analysis.

        Args:
            failed_tests: List of failed test dicts (from TestLogger or DB).
            run_context: Optional context about the evaluation run (model, scores, etc.).

        Returns:
            Structured analysis dict with patterns, root causes, and recommendations.
        """
        if not failed_tests:
            return {
                "summary": "No failures to analyze",
                "failure_count": 0,
                "patterns": [],
                "domain_analysis": {},
                "training_recommendations": [],
            }

        user_message = self._build_analysis_prompt(failed_tests, run_context)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        return self._parse_response(response)

    def analyze_from_run(self, run_id: str) -> Dict[str, Any]:
        """Load failed tests from a completed evaluation run and analyze them."""
        from models.db import db

        results = db.get_test_results(run_id)
        run_info = db.get_evaluation_run(run_id)

        failed = []
        for r in results:
            if r["status"] == "failed" or (r["score"] is not None and r["score"] < 0.8):
                failed.append({
                    "domain": r["domain"],
                    "level": r["level"],
                    "prompt": r["prompt"],
                    "response": r["response"],
                    "expected": r["expected"],
                    "score": r["score"],
                    "status": r["status"],
                    "details": r["details"],
                })

        context = {
            "run_id": run_id,
            "model_name": run_info["model_name"] if run_info else "unknown",
            "overall_score": run_info["overall_score"] if run_info else None,
        }

        return self.analyze_failures(failed, context)

    def analyze_from_log_file(self, log_path: str) -> Dict[str, Any]:
        """Analyze failures from a saved JSON log file (from run_headless.py)."""
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        failed_tests = data.get("failed_tests", [])
        context = data.get("summary", {})

        return self.analyze_failures(failed_tests, context)

    def _build_analysis_prompt(self, failed_tests: List[Dict], context: Dict = None) -> str:
        parts = []

        if context:
            parts.append(f"## Evaluation Context\n{json.dumps(context, indent=2, default=str)}\n")

        parts.append(f"## Failed Tests ({len(failed_tests)} total)\n")

        for i, test in enumerate(failed_tests, 1):
            parts.append(f"### Test #{i}: {test['domain']} Level {test['level']}")
            parts.append(f"Score: {test.get('score', 0)}")
            parts.append(f"Prompt: {test.get('prompt', '(none)')}")
            parts.append(f"Expected: {test.get('expected', '(none)')}")
            parts.append(f"Response: {test.get('response', '(none)')}")
            details = test.get("details")
            if details:
                parts.append(f"Details: {details}")
            parts.append("")

        return "\n".join(parts)

    def _parse_response(self, response) -> Dict[str, Any]:
        text = response.content[0].text.strip()

        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[: text.rfind("```")]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "summary": "Failed to parse structured analysis",
                "raw_response": text,
                "failure_count": 0,
                "patterns": [],
                "domain_analysis": {},
                "training_recommendations": [],
            }
