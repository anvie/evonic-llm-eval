#!/usr/bin/env python3
"""Debug: Check what sync_to_db is actually loading"""

from evaluator.test_loader import test_loader

print("=" * 80)
print("Loading domains from files...")
print("=" * 80)

domains = test_loader.scan_domains()
for domain in domains:
    if domain.id == 'krasan_villa':
        print(f"\n✓ Found krasan_villa:")
        print(f"  system_prompt in object: {domain.system_prompt is not None}")
        print(f"  system_prompt_mode: {domain.system_prompt_mode}")
        if domain.system_prompt:
            print(f"  First 100 chars: {domain.system_prompt[:100]}...")
        print(f"  to_dict() keys: {list(domain.to_dict().keys())}")
        domain_dict = domain.to_dict()
        print(f"  to_dict()['system_prompt']: {domain_dict.get('system_prompt') is not None}")
