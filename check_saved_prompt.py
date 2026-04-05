#!/usr/bin/env python3
"""Check what system_prompt is actually saved in the latest run"""

import sqlite3
import json

conn = sqlite3.connect('evaluation.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get latest run
cursor.execute("SELECT run_id, started_at FROM evaluation_runs ORDER BY started_at DESC LIMIT 1")
run = cursor.fetchone()
if not run:
    print("No runs found!")
    conn.close()
    exit()

run_id = run['run_id']
print(f"Latest run: {run_id}")
print(f"Started at: {run['started_at']}")
print("=" * 80)

# Get krasan_villa L2 test result
cursor.execute("""
    SELECT test_id, system_prompt, system_prompt_mode,
           LENGTH(system_prompt) as sp_length
    FROM individual_test_results
    WHERE run_id = ? AND domain = 'krasan_villa' AND level = 2
""", (run_id,))

row = cursor.fetchone()
if row:
    print(f"\n✓ Found test: {row['test_id']}")
    print(f"  system_prompt_mode: {row['system_prompt_mode']}")
    print(f"  system_prompt length: {row['sp_length']} chars")
    
    if row['system_prompt']:
        sp = row['system_prompt']
        print(f"\n  First 150 chars:")
        print(f"  {sp[:150]}...")
        print(f"\n  Contains '## TOOLS': {('## TOOLS' in sp)}")
        print(f"  Contains 'get_current_date': {('get_current_date' in sp)}")
        
        if len(sp) > 150:
            print(f"\n  Last 150 chars:")
            print(f"  ...{sp[-150:]}")
    else:
        print("  ✗ system_prompt is NULL!")
else:
    print("✗ No test result found for krasan_villa L2")

conn.close()
