#!/usr/bin/env python3
"""Quick test of the test_loader module"""

from evaluator.test_loader import test_loader

# Test loading domains
domains = test_loader.scan_domains()
print(f'Loaded {len(domains)} domains:')
for d in domains:
    print(f'  - {d.name} ({d.id})')

# Test loading tests for a level
tests = test_loader.load_tests_by_level('math', 1)
print(f'\nMath Level 1 tests: {len(tests)}')
for t in tests:
    print(f'  - {t.name}: {t.prompt}')

# Test loading evaluators
evaluators = test_loader.load_evaluators()
print(f'\nLoaded {len(evaluators)} evaluators:')
for e in evaluators:
    print(f'  - {e.name} ({e.type})')

print('\nAll tests passed!')
