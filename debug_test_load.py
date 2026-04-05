#!/usr/bin/env python3
"""Check what the test_loader is actually loading for krasan_explicit_date_2"""

from evaluator.test_loader import test_loader

print("=" * 80)
print("Loading test: krasan_explicit_date_2")
print("=" * 80)

test = test_loader.get_test('krasan_explicit_date_2')
if test:
    print(f"✓ Test loaded:")
    print(f"  ID: {test.id}")
    print(f"  system_prompt: {test.system_prompt is not None}")
    print(f"  system_prompt_mode: '{test.system_prompt_mode}'")
    if test.system_prompt:
        print(f"  First 100 chars: {test.system_prompt[:100]}...")
    
    # Load domain too
    domain = test_loader.load_domain('krasan_villa')
    if domain:
        print(f"\n✓ Domain loaded:")
        print(f"  system_prompt: {domain.system_prompt is not None}")
        if domain.system_prompt:
            print(f"  First 100 chars: {domain.system_prompt[:100]}...")
    
    # Test the resolver
    print(f"\n✓ Testing resolve_system_prompt:")
    resolved = test_loader.resolve_system_prompt(test, domain)
    if resolved:
        print(f"  Resolved length: {len(resolved)} chars")
        print(f"  First 150 chars: {resolved[:150]}...")
    else:
        print(f"  ✗ Resolved to NULL!")
else:
    print("✗ Test NOT found!")
