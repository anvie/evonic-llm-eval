#!/usr/bin/env python3
"""Simulate what the evaluation engine does"""

from evaluator.test_loader import test_loader
from evaluator.engine import EvaluationEngine

# Create a mock test dict like the engine receives
test = {
    'id': 'krasan_explicit_date_2',
    'name': 'Explicit Date Availability',
    'level': 2
}

# Simulate what engine._resolve_system_prompt does
print("=" * 80)
print("Simulating engine._resolve_system_prompt()")
print("=" * 80)

engine = EvaluationEngine(use_configurable_tests=True)
resolved = engine._resolve_system_prompt(test, 'krasan_villa')

if resolved:
    print(f"✓ Resolved: {len(resolved)} chars")
    print(f"\nFirst 200 chars:")
    print(resolved[:200])
    print("\n...")
    print(f"\nLast 200 chars:")
    print(resolved[-200:])
else:
    print("✗ Returned NULL!")
