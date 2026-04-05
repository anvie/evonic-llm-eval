#!/usr/bin/env python3
"""
Fix: Add system_prompt columns and populate from JSON files
This combines migration + sync into one reliable script
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = 'evaluation.db'
TESTS_DIR = Path('test_definitions')

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=" * 80)
print("Step 1: Add columns if they don't exist")
print("=" * 80)

# Check domains table
cursor.execute("PRAGMA table_info(domains)")
domain_cols = [row[1] for row in cursor.fetchall()]

if 'system_prompt' not in domain_cols:
    cursor.execute("ALTER TABLE domains ADD COLUMN system_prompt TEXT")
    print("✓ Added system_prompt to domains table")
else:
    print("✓ domains.system_prompt already exists")

if 'system_prompt_mode' not in domain_cols:
    cursor.execute("ALTER TABLE domains ADD COLUMN system_prompt_mode TEXT DEFAULT 'overwrite'")
    print("✓ Added system_prompt_mode to domains table")
else:
    print("✓ domains.system_prompt_mode already exists")

# Check tests table
cursor.execute("PRAGMA table_info(tests)")
test_cols = [row[1] for row in cursor.fetchall()]

if 'system_prompt_mode' not in test_cols:
    cursor.execute("ALTER TABLE tests ADD COLUMN system_prompt_mode TEXT DEFAULT 'overwrite'")
    print("✓ Added system_prompt_mode to tests table")
else:
    print("✓ tests.system_prompt_mode already exists")

conn.commit()

print("\n" + "=" * 80)
print("Step 2: Populate from JSON files")
print("=" * 80)

# Update domains from JSON
for domain_dir in TESTS_DIR.iterdir():
    if not domain_dir.is_dir():
        continue
    
    domain_json = domain_dir / 'domain.json'
    if not domain_json.exists():
        continue
    
    with open(domain_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    domain_id = domain_dir.name
    system_prompt = data.get('system_prompt')
    system_prompt_mode = data.get('system_prompt_mode', 'overwrite')
    
    if system_prompt:
        cursor.execute("""
            UPDATE domains 
            SET system_prompt = ?, system_prompt_mode = ?
            WHERE id = ?
        """, (system_prompt, system_prompt_mode, domain_id))
        
        if cursor.rowcount > 0:
            print(f"✓ Updated {domain_id}: system_prompt ({len(system_prompt)} chars)")
        else:
            print(f"- Skipped {domain_id}: not in database yet")

# Update tests from JSON
for domain_dir in TESTS_DIR.iterdir():
    if not domain_dir.is_dir():
        continue
    
    for level in range(1, 6):
        level_dir = domain_dir / f'level_{level}'
        if not level_dir.exists():
            continue
        
        for test_json in level_dir.glob('*.json'):
            with open(test_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            test_id = data.get('id')
            system_prompt = data.get('system_prompt')
            system_prompt_mode = data.get('system_prompt_mode', 'overwrite')
            
            if system_prompt:
                cursor.execute("""
                    UPDATE tests 
                    SET system_prompt = ?, system_prompt_mode = ?
                    WHERE id = ?
                """, (system_prompt, system_prompt_mode, test_id))
                
                if cursor.rowcount > 0:
                    print(f"✓ Updated {test_id}: system_prompt ({len(system_prompt)} chars)")

conn.commit()

print("\n" + "=" * 80)
print("✓ Fix complete! Run debug_system_prompt.py to verify")
print("=" * 80)

conn.close()
