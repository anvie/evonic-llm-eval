"""Adjust existing training data based on failure analysis."""

import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

ADJUSTMENT_SYSTEM_PROMPT = """\
You are a training data quality specialist. You review and adjust existing JSONL \
training data for a villa customer service LLM (Indonesian language).

Given existing training examples and an analysis of model failures, you will:
1. Identify examples that may be causing or not preventing the failures
2. Suggest modifications (fix content, add context, improve quality)
3. Flag examples that should be removed (harmful, misleading, or contradictory)

Respond with a JSON object:
{
  "adjusted": [
    {
      "original_index": <int>,
      "action": "modify|remove|keep",
      "reason": "Why this change",
      "modified_example": { ... }  // only if action == "modify"
    }
  ],
  "summary": "Brief summary of changes"
}\
"""


class DataAdjuster:
    """Adjust existing training data based on failure analysis."""

    def __init__(self, api_key: str = None, model: str = "claude-opus-4-0",
                 base_dir: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.base_dir = base_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "training_data"
        )
        self.client = Anthropic(api_key=self.api_key)

    def adjust(self, training_file: str, analysis: Dict[str, Any],
               domain_filter: str = None) -> Dict[str, Any]:
        """Adjust a training data file based on failure analysis.

        Args:
            training_file: Path to the JSONL training data file.
            analysis: Output from FailureAnalyzer.
            domain_filter: Optional domain to focus adjustments on.

        Returns:
            Dict with adjusted file path, change counts, and summary.
        """
        examples = self._load_jsonl(training_file)
        if not examples:
            return {"file": None, "message": "No examples found in training file"}

        # Filter by domain if specified
        if domain_filter:
            relevant_patterns = [
                p for p in analysis.get("patterns", [])
                if p["domain"] == domain_filter
            ]
        else:
            relevant_patterns = analysis.get("patterns", [])

        if not relevant_patterns:
            return {"file": training_file, "message": "No relevant patterns to adjust for"}

        adjustments = self._get_adjustments(examples, relevant_patterns, analysis)
        adjusted_path = self._apply_adjustments(training_file, examples, adjustments)

        return {
            "original_file": training_file,
            "adjusted_file": adjusted_path,
            "total_examples": len(examples),
            "modified": sum(1 for a in adjustments.get("adjusted", []) if a["action"] == "modify"),
            "removed": sum(1 for a in adjustments.get("adjusted", []) if a["action"] == "remove"),
            "kept": sum(1 for a in adjustments.get("adjusted", []) if a["action"] == "keep"),
            "summary": adjustments.get("summary", ""),
        }

    def merge_datasets(self, file_paths: List[str], output_name: str = None) -> str:
        """Merge multiple JSONL files into a versioned dataset.

        Args:
            file_paths: List of JSONL file paths to merge.
            output_name: Optional output filename.

        Returns:
            Path to the merged file.
        """
        all_examples = []
        for path in file_paths:
            all_examples.extend(self._load_jsonl(path))

        # Deduplicate by content hash
        seen = set()
        unique = []
        for ex in all_examples:
            key = json.dumps(ex, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                unique.append(ex)

        versions_dir = os.path.join(self.base_dir, "versions")
        os.makedirs(versions_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_name or f"merged_{timestamp}.jsonl"
        output_path = os.path.join(versions_dir, filename)

        with open(output_path, "w", encoding="utf-8") as f:
            for ex in unique:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        return output_path

    def create_version(self, source_file: str, version_tag: str = None) -> str:
        """Create a versioned snapshot of a training data file.

        Args:
            source_file: Path to the source JSONL file.
            version_tag: Optional version tag (default: timestamp).

        Returns:
            Path to the versioned copy.
        """
        versions_dir = os.path.join(self.base_dir, "versions")
        os.makedirs(versions_dir, exist_ok=True)

        tag = version_tag or datetime.now().strftime("v_%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(source_file))[0]
        dest = os.path.join(versions_dir, f"{base_name}_{tag}.jsonl")
        shutil.copy2(source_file, dest)
        return dest

    def _load_jsonl(self, path: str) -> List[Dict]:
        examples = []
        if not os.path.exists(path):
            return examples
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        examples.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return examples

    def _get_adjustments(self, examples: List[Dict], patterns: List[Dict],
                         analysis: Dict) -> Dict:
        # Send a manageable batch to Claude (first 50 examples max)
        batch = examples[:50]
        user_message = self._build_adjustment_prompt(batch, patterns, analysis)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=ADJUSTMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        return self._parse_adjustments(response)

    def _build_adjustment_prompt(self, examples: List[Dict], patterns: List[Dict],
                                 analysis: Dict) -> str:
        parts = ["## Failure Patterns\n"]
        for p in patterns:
            parts.append(f"- [{p.get('severity', 'medium')}] {p['description']}")
            parts.append(f"  Root cause: {p.get('root_cause', 'unknown')}")

        parts.append(f"\n## Existing Training Examples ({len(examples)} shown)\n")
        for i, ex in enumerate(examples):
            parts.append(f"### Example {i}")
            parts.append(json.dumps(ex, ensure_ascii=False, indent=2))
            parts.append("")

        parts.append("Review each example and decide: modify, remove, or keep.")
        return "\n".join(parts)

    def _parse_adjustments(self, response) -> Dict:
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[: text.rfind("```")]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"adjusted": [], "summary": "Failed to parse adjustment response"}

    def _apply_adjustments(self, original_path: str, examples: List[Dict],
                           adjustments: Dict) -> str:
        # Build lookup of adjustments by index
        adj_map = {}
        for adj in adjustments.get("adjusted", []):
            idx = adj.get("original_index")
            if idx is not None:
                adj_map[idx] = adj

        # Apply adjustments
        result = []
        for i, ex in enumerate(examples):
            adj = adj_map.get(i)
            if adj is None or adj["action"] == "keep":
                result.append(ex)
            elif adj["action"] == "modify" and "modified_example" in adj:
                result.append(adj["modified_example"])
            # action == "remove": skip

        # Save adjusted version
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(original_path))[0]
        adjusted_path = os.path.join(
            os.path.dirname(original_path),
            f"{base_name}_adjusted_{timestamp}.jsonl"
        )

        with open(adjusted_path, "w", encoding="utf-8") as f:
            for ex in result:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        return adjusted_path
