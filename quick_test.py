#!/usr/bin/env python3
"""Quick test: Check what system_prompt value is being used at save time"""

# Simulate the flow
system_prompt = "Kamu adalah asisten..."  # domain only
test_prompt = "## TOOLS..."  # test level
test_mode = "append"

# This is what the resolver should return
if test_prompt and system_prompt and test_mode == 'append':
    resolved = system_prompt + "\n\n" + test_prompt
else:
    resolved = test_prompt or system_prompt

print(f"Domain prompt: {len(system_prompt)} chars")
print(f"Test prompt: {len(test_prompt)} chars")  
print(f"Mode: {test_mode}")
print(f"\nResolved (what should be saved): {len(resolved)} chars")
print(f"Starts with domain: {resolved.startswith(system_prompt)}")
print(f"Contains test tools: {'## TOOLS' in resolved}")
