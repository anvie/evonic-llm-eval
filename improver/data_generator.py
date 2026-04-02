"""Generate JSONL training data to address identified failure patterns."""

import json
import os
from datetime import datetime
from typing import Any, Dict, List

from anthropic import Anthropic

GENERATION_SYSTEM_PROMPT = """\
You are a training data specialist for fine-tuning LLMs. You create high-quality \
JSONL training examples for a villa customer service assistant that operates in \
Indonesian language.

The model is fine-tuned with Unsloth and expects data in chat format:
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

For tool calling examples, use this format:
{"messages": [
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": null, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "...", "arguments": "..."}}]},
  {"role": "tool", "content": "...", "tool_call_id": "call_1"},
  {"role": "assistant", "content": "..."}
]}

Guidelines:
- Use natural Indonesian language for conversation examples
- Include varied phrasings and contexts for the same concept
- For math: show step-by-step reasoning in Indonesian
- For SQL: use realistic villa/customer service schemas
- For tool calling: use the available tools (calculator, database_query, api_call, file_create, file_edit)
- For reasoning: include logical step-by-step thinking

Respond with a JSON array of training examples. Each element should be a valid \
messages object. Do not include markdown fences.\
"""


class TrainingDataGenerator:
    """Generate JSONL training data from failure analysis."""

    def __init__(self, api_key: str = None, model: str = "claude-opus-4-0",
                 output_dir: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "training_data", "generated"
        )
        self.client = Anthropic(api_key=self.api_key)
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_from_analysis(self, analysis: Dict[str, Any], examples_per_pattern: int = 5) -> Dict[str, Any]:
        """Generate training data based on failure analysis.

        Args:
            analysis: Output from FailureAnalyzer.analyze_failures().
            examples_per_pattern: Number of training examples per failure pattern.

        Returns:
            Dict with generated file path, example count, and metadata.
        """
        recommendations = analysis.get("training_recommendations", [])
        patterns = analysis.get("patterns", [])

        if not recommendations and not patterns:
            return {"file": None, "count": 0, "message": "No patterns to generate data for"}

        all_examples = []

        # Generate examples for each recommendation
        for rec in sorted(recommendations, key=lambda r: r.get("priority", 99)):
            count = rec.get("example_count", examples_per_pattern)
            examples = self._generate_examples(
                domain=rec["domain"],
                description=rec["description"],
                action=rec.get("action", "generate"),
                count=count,
                patterns=[p for p in patterns if p["domain"] == rec["domain"]],
            )
            all_examples.extend(examples)

        # If no recommendations but have patterns, generate from patterns directly
        if not recommendations and patterns:
            for pattern in patterns:
                examples = self._generate_examples(
                    domain=pattern["domain"],
                    description=pattern["suggested_fix"],
                    action="generate",
                    count=examples_per_pattern,
                    patterns=[pattern],
                )
                all_examples.extend(examples)

        # Save to JSONL
        output_path = self._save_jsonl(all_examples)

        return {
            "file": output_path,
            "count": len(all_examples),
            "domains": list({e.get("_domain", "unknown") for e in all_examples}),
        }

    def generate_for_domain(self, domain: str, weak_areas: List[str],
                            count: int = 10) -> Dict[str, Any]:
        """Generate training data for a specific domain and its weak areas.

        Args:
            domain: The evaluation domain (conversation, math, sql, etc.).
            weak_areas: List of specific weaknesses to address.
            count: Number of examples to generate.

        Returns:
            Dict with generated file path and metadata.
        """
        description = f"Domain: {domain}. Weak areas: {'; '.join(weak_areas)}"
        examples = self._generate_examples(domain, description, "generate", count)
        output_path = self._save_jsonl(examples)
        return {"file": output_path, "count": len(examples), "domain": domain}

    def _generate_examples(self, domain: str, description: str, action: str,
                           count: int, patterns: List[Dict] = None) -> List[Dict]:
        user_message = self._build_generation_prompt(domain, description, action, count, patterns)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=8192,
            system=GENERATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        examples = self._parse_examples(response)
        # Tag each example with domain metadata
        for ex in examples:
            ex["_domain"] = domain
        return examples

    def _build_generation_prompt(self, domain: str, description: str, action: str,
                                 count: int, patterns: List[Dict] = None) -> str:
        parts = [
            f"Generate {count} training examples for the '{domain}' domain.",
            f"Action: {action}",
            f"Description: {description}",
        ]

        if patterns:
            parts.append("\nFailure patterns to address:")
            for p in patterns:
                parts.append(f"- [{p.get('severity', 'medium')}] {p['description']}")
                parts.append(f"  Root cause: {p.get('root_cause', 'unknown')}")
                parts.append(f"  Fix: {p.get('suggested_fix', 'N/A')}")

        parts.append(f"\nGenerate exactly {count} diverse, high-quality examples as a JSON array.")
        return "\n".join(parts)

    def _parse_examples(self, response) -> List[Dict]:
        text = response.content[0].text.strip()

        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[: text.rfind("```")]
            text = text.strip()

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "messages" in data:
                return [data]
            return []
        except json.JSONDecodeError:
            return []

    def _save_jsonl(self, examples: List[Dict]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"generated_{timestamp}.jsonl"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            for example in examples:
                # Remove internal metadata before saving
                clean = {k: v for k, v in example.items() if not k.startswith("_")}
                # Ensure proper format
                if "messages" not in clean:
                    clean = {"messages": clean} if "role" in str(clean) else clean
                f.write(json.dumps(clean, ensure_ascii=False) + "\n")

        return filepath
