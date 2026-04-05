#!/usr/bin/env python3
"""Debug: Check if test has system_prompt in database"""

import sqlite3
import json

conn = sqlite3.connect('evaluation.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check if test exists in tests table
print("=" * 80)
print("Checking tests table for krasan_explicit_date_2...")
print("=" * 80)
cursor.execute("SELECT id, name, system_prompt, system_prompt_mode FROM tests WHERE id = 'krasan_explicit_date_2'")
row = cursor.fetchone()
if row:
    print(f"✓ Found in tests table:")
    print(f"  ID: {row['id']}")
    print(f"  Name: {row['name']}")
    print(f"  Has system_prompt: {row['system_prompt'] is not None}")
    print(f"  system_prompt_mode: {row['system_prompt_mode']}")
    if row['system_prompt']:
        print(f"  system_prompt (first 100 chars): {row['system_prompt'][:100]}...")
else:
    print("✗ NOT found in tests table!")

# Check domain
print("\n" + "=" * 80)
print("Checking domains table for krasan_villa...")
print("=" * 80)
cursor.execute("SELECT id, name, system_prompt FROM domains WHERE id = 'krasan_villa'")
row = cursor.fetchone()
if row:
    print(f"✓ Found in domains table:")
    print(f"  ID: {row['id']}")
    print(f"  Has system_prompt: {row['system_prompt'] is not None}")
    if row['system_prompt']:
        print(f"  system_prompt (first 100 chars): {row['system_prompt'][:100]}...")
else:
    print("✗ NOT found in domains table!")

# Check individual_test_results for the run
run_id = 'a16abebc-2099-4dae-b0b2-30dc60513069'
print("\n" + "=" * 80)
print(f"Checking individual_test_results for run {run_id}...")
print("=" * 80)
cursor.execute("""
    SELECT test_id, domain, level 
    FROM individual_test_results 
    WHERE run_id = ? AND domain = 'krasan_villa' AND level = 2
""", (run_id,))
rows = cursor.fetchall()
if rows:
    print(f"✓ Found {len(rows)} test(s):")
    for row in rows:
        print(f"  - test_id: {row['test_id']}, domain: {row['domain']}, level: {row['level']}")
else:
    print(f"✗ No tests found for this run/domain/level")

# Check the actual JOIN query
print("\n" + "=" * 80)
print("Testing the actual JOIN query...")
print("=" * 80)
cursor.execute("""
    SELECT itr.test_id, 
           t.system_prompt as test_system_prompt, 
           d.system_prompt as domain_system_prompt
    FROM individual_test_results itr
    JOIN tests t ON itr.test_id = t.id
    JOIN domains d ON itr.domain = d.id
    WHERE itr.run_id = ? AND itr.domain = 'krasan_villa' AND itr.level = 2
""", (run_id,))
rows = cursor.fetchall()
if rows:
    print(f"✓ JOIN returned {len(rows)} row(s):")
    for row in rows:
        print(f"  test_id: {row['test_id']}")
        print(f"    test_system_prompt: {row['test_system_prompt'] is not None}")
        print(f"    domain_system_prompt: {row['domain_system_prompt'] is not None}")
else:
    print(f"✗ JOIN returned NO rows (JOIN failed!)")

conn.close()
