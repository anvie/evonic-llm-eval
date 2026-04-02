#!/usr/bin/env python3
"""Verify the configurable test system implementation"""

import sys
sys.path.insert(0, '/home/hermes/dev/evonic-llm-eval')

from evaluator.test_manager import test_manager
from evaluator.score_aggregator import ScoreAggregator, TestResult

print("=" * 60)
print("Verifying Configurable Test System")
print("=" * 60)

# Test 1: List domains
print("\n1. Testing domain loading...")
domains = test_manager.list_domains()
print(f"   Loaded {len(domains)} domains:")
for d in domains:
    print(f"   - {d['name']}: {d['total_tests']} tests")

# Test 2: List evaluators
print("\n2. Testing evaluator loading...")
evaluators = test_manager.list_evaluators()
print(f"   Loaded {len(evaluators)} evaluators:")
for e in evaluators:
    print(f"   - {e['name']} ({e['type']})")

# Test 3: Score aggregator
print("\n3. Testing score aggregator...")
results = [
    TestResult('t1', 'math', 1, 0.9, 'passed', 1.0),
    TestResult('t2', 'math', 1, 0.7, 'passed', 1.0),
    TestResult('t3', 'math', 1, 0.5, 'failed', 1.0),
]
level_score = ScoreAggregator.calculate_level_score(results)
print(f"   Average score: {level_score.average_score:.2f} (expected: 0.70)")
print(f"   Total tests: {level_score.total_tests} (expected: 3)")
print(f"   Passed tests: {level_score.passed_tests} (expected: 2)")

# Test 4: Create domain
print("\n4. Testing domain creation...")
try:
    new_domain = test_manager.create_domain({
        'id': 'test_domain',
        'name': 'Test Domain',
        'description': 'A test domain for verification',
        'icon': 'file',
        'color': '#FF0000'
    }, is_custom=True)
    print(f"   Created domain: {new_domain['name']}")
    
    # Clean up
    test_manager.delete_domain('test_domain')
    print("   Deleted test domain successfully")
except Exception as e:
    print(f"   Error: {e}")

# Test 5: Create test
print("\n5. Testing test creation...")
try:
    # First create a test domain
    test_manager.create_domain({
        'id': 'test_domain',
        'name': 'Test Domain',
        'description': 'Test',
        'icon': 'file',
        'color': '#FF0000'
    }, is_custom=True)
    
    # Create test
    new_test = test_manager.create_test('test_domain', 1, {
        'id': 'test_test',
        'name': 'Test Question',
        'prompt': 'What is 1+1?',
        'expected': {'answer': 2},
        'evaluator_id': 'two_pass'
    })
    print(f"   Created test: {new_test['name']}")
    
    # Clean up
    test_manager.delete_test('test_test')
    test_manager.delete_domain('test_domain')
    print("   Cleaned up successfully")
except Exception as e:
    print(f"   Error: {e}")

print("\n" + "=" * 60)
print("All verification tests completed!")
print("=" * 60)