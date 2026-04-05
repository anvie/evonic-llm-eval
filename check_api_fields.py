#!/usr/bin/env python3
"""Debug: Check exactly what fields the API returns"""

import sqlite3

conn = sqlite3.connect('evaluation.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

run_id = 'e99abad2-7221-43b1-974b-4cf8fe650678'

# Check what columns are in the result
cursor.execute("""
    SELECT * FROM individual_test_results
    WHERE run_id = ? AND domain = 'krasan_villa' AND level = 2
""", (run_id,))

row = cursor.fetchone()
if row:
    print("Available columns in individual_test_results:")
    for i, desc in enumerate(cursor.description):
        print(f"  {i}. {desc[0]}")
    
    print(f"\nField values for krasan_explicit_date_2:")
    print(f"  system_prompt: {'present' if row['system_prompt'] else 'NULL'}")
    print(f"  system_prompt_mode: {row['system_prompt_mode']}")
    
    if row['system_prompt']:
        print(f"  system_prompt length: {len(row['system_prompt'])}")
        print(f"  First 100: {row['system_prompt'][:100]}")

conn.close()
