# Regex Evaluator Guide

## Overview

Evonic LLM Evaluator now supports **regex-based evaluation** for matching complex string patterns in LLM responses.

## Evaluator Types

### 1. **Regex-Only** (`type: "regex"`)
Directly extracts values or matches patterns from the LLM response.

**Use cases:**
- Number extraction
- Date validation
- Multiple choice answers
- Exact string matching
- SQL keyword validation

### 2. **LLM Prompt** (`type: "custom"`)
Uses an LLM to evaluate response quality with a custom prompt.

**Use cases:**
- Subjective quality assessment
- Complex reasoning evaluation
- Fluency/correctness scoring

### 3. **Hybrid** (`type: "hybrid"`)
LLM generates evaluation text, regex extracts the final score.

**Use cases:**
- Structured LLM evaluation with reliable score extraction
- Quality rating with explainable reasoning

---

## Built-in Regex Evaluators

### `regex_number_extractor`
Extracts numeric answers from responses.

```json
{
  "id": "regex_number_extractor",
  "type": "regex",
  "extraction_regex": "(?:Jawaban|Score|Answer|Nilai):?\\s*(\\d+(?:\\.\\d+)?)"
}
```

**Matches:**
- `Jawaban: 42` → extracts `42`
- `Score: 85.5` → extracts `85.5`
- `Answer: 100` → extracts `100`

---

### `regex_exact_match`
Matches entire response against expected string.

```json
{
  "id": "regex_exact_match",
  "type": "regex",
  "extraction_regex": "^(.+)$"
}
```

**Behavior:**
- Extracts the full response
- Compares with expected value (case-insensitive)
- Returns 1.0 if match, 0.0 if no match

---

### `regex_multiple_choice`
Extracts multiple choice answers (A, B, C, D).

```json
{
  "id": "regex_multiple_choice",
  "type": "regex",
  "extraction_regex": "(?:Jawaban|Answer):?\\s*([ABCDabcdn])"
}
```

**Matches:**
- `Jawaban: A` → extracts `A`
- `Answer: C` → extracts `C`

---

### `regex_date_extractor`
Validates date format (YYYY-MM-DD).

```json
{
  "id": "regex_date_extractor",
  "type": "regex",
  "extraction_regex": "(\\d{4}-\\d{2}-\\d{2})"
}
```

**Matches:**
- `Tanggal: 2026-04-05` → extracts `2026-04-05`

---

### `regex_sql_validator`
Validates SQL query structure.

```json
{
  "id": "regex_sql_validator",
  "type": "regex",
  "extraction_regex": "(?i)\\b(SELECT)\\b.*\\b(FROM)\\b.*\\b(WHERE)\\b"
}
```

**Matches:**
- Queries containing SELECT, FROM, and WHERE (in that order)
- Case-insensitive matching

---

### `hybrid_quality_rater`
LLM evaluates quality, regex extracts score.

```json
{
  "id": "hybrid_quality_rater",
  "type": "hybrid",
  "eval_prompt": "Evaluate this response quality from 0-100:\n\nResponse: {response}\nExpected: {expected}\n\nProvide your evaluation and end with: SCORE: <number>",
  "extraction_regex": "SCORE:\\s*(\\d+)"
}
```

**Process:**
1. LLM evaluates response with custom prompt
2. LLM outputs: `SCORE: 85`
3. Regex extracts `85` → normalized to `0.85`

---

## Creating Custom Regex Evaluators

### Via UI (Settings Page)

1. Go to Settings → Evaluators tab
2. Click "+ Add Custom Evaluator"
3. Select type: **Regex Pattern Matcher**
4. Fill in:
   - Name: Descriptive name
   - Description: What it does
   - Extraction Regex: Pattern with capture group

### Manual JSON File

Create file in `test_definitions/evaluators/`:

```json
{
  "id": "my_custom_regex",
  "name": "My Custom Evaluator",
  "type": "regex",
  "description": "What it does",
  "extraction_regex": "your-regex-pattern-here",
  "uses_pass2": false,
  "config": {}
}
```

---

## Regex Pattern Examples

### Extract Number
```regex
(?:Jawaban|Score|Answer):?\\s*(\\d+)
```

### Extract Percentage
```regex
(\\d+(?:\\.\\d+)?)\\s*%
```

### Extract Email
```regex
([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})
```

### Extract URL
```regex
(https?:\\/\\/[^\\s]+)
```

### Extract Date (YYYY-MM-DD)
```regex
(\\d{4}-\\d{2}-\\d{2})
```

### Extract Time (HH:MM)
```regex
(\\d{2}:\\d{2})
```

### Multiple Choice
```regex
[Jj]awaban:\\s*([ABCD])
```

### Exact Match (Case-Insensitive)
```regex
(?i)^expected answer$
```

### SQL Keywords
```regex
(?i)\\b(SELECT)\\b.*\\b(FROM)\\b
```

---

## How Regex Evaluation Works

### Mode 1: Score Extraction
If the regex captures a number:
1. Extract value from first capture group
2. Try to parse as float
3. Normalize:
   - If > 100: assume percentage, divide by 100
   - If > 5: assume 0-100 scale, divide by 100
   - Otherwise: use as-is (0-1 scale)
4. Status: `passed` if score >= 0.7, else `failed`

### Mode 2: String Matching
If the regex captures a non-numeric string AND expected value exists:
1. Extract value from first capture group
2. Compare with expected (case-insensitive)
3. Score: 1.0 if match, 0.0 if no match

### Mode 3: Full Match (No Capture Groups)
If regex has no capture groups:
1. Just check if pattern matches anywhere in response
2. Score: 1.0 if match found, 0.0 if not

---

## Testing Your Regex

Use [regex101.com](https://regex101.com) to test patterns before deploying.

Example test flow:
1. Run evaluation with test LLM
2. Check logs for "Extracted value" message
3. Verify score calculation is correct
4. Adjust regex if needed

---

## Best Practices

✅ **DO:**
- Use capture groups `(...)` to extract specific values
- Make patterns case-insensitive with `(?i)` when appropriate
- Test patterns thoroughly before using in production
- Use descriptive evaluator names
- Document what each evaluator does

❌ **DON'T:**
- Use overly complex regex (hard to debug)
- Forget to escape special characters (`.` `*` `+` `?` etc.)
- Assume all responses will match your pattern
- Use regex for tasks better suited to LLM evaluation

---

## Troubleshooting

### "Pattern not found in response"
- Check if response format matches your pattern
- Verify regex escaping (JSON requires double backslash `\\`)
- Test with regex101.com

### "Invalid regex pattern"
- Check for syntax errors
- Ensure brackets/parens are balanced
- Test in Python: `re.search(your_pattern, test_string)`

### Score always 0.0
- Verify capture group is extracting correct value
- Check if value is being parsed as number
- Review normalization logic

---

## Examples by Domain

### Conversation Tests
```json
{
  "evaluator_id": "regex_exact_match",
  "expected": "Halo, nama saya Asisten"
}
```

### Math Tests
```json
{
  "evaluator_id": "regex_number_extractor",
  "expected": 42
}
```

### SQL Tests
```json
{
  "evaluator_id": "regex_sql_validator"
}
```

### Multiple Choice Tests
```json
{
  "evaluator_id": "regex_multiple_choice",
  "expected": "B"
}
```

### Date Validation Tests
```json
{
  "evaluator_id": "regex_date_extractor",
  "expected": "2026-04-05"
}
```

---

## Migration from Other Evaluator Types

### From `keyword` evaluator → `regex_exact_match`
Old:
```json
{"evaluator_id": "keyword", "expected": {"keywords": ["hello", "assist"]}}
```

New:
```json
{"evaluator_id": "regex_exact_match", "expected": "Hello, I am your assistant"}
```

### From `two_pass` evaluator → `hybrid_quality_rater`
Old:
```json
{"evaluator_id": "two_pass", "expected": {"criteria": "correctness"}}
```

New:
```json
{"evaluator_id": "hybrid_quality_rater", "expected": {"quality_threshold": 80}}
```

---

## See Also

- Custom Evaluator implementation: `evaluator/custom_evaluator.py`
- Test Loader: `evaluator/test_loader.py`
- Settings UI: `templates/settings.html`
