#!/usr/bin/env python3
"""
Migration: Add system_prompt and system_prompt_mode to domains and tests tables

Run this once if you have an existing evaluation.db
"""

import sqlite3
import config

def migrate():
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    # Check domains table
    cursor.execute("PRAGMA table_info(domains)")
    domain_columns = [row[1] for row in cursor.fetchall()]
    
    if 'system_prompt' not in domain_columns:
        cursor.execute("ALTER TABLE domains ADD COLUMN system_prompt TEXT")
        print("✓ Added 'system_prompt' column to domains table")
    
    if 'system_prompt_mode' not in domain_columns:
        cursor.execute("ALTER TABLE domains ADD COLUMN system_prompt_mode TEXT DEFAULT 'overwrite'")
        print("✓ Added 'system_prompt_mode' column to domains table")
    
    # Check tests table
    cursor.execute("PRAGMA table_info(tests)")
    test_columns = [row[1] for row in cursor.fetchall()]
    
    if 'system_prompt_mode' not in test_columns:
        cursor.execute("ALTER TABLE tests ADD COLUMN system_prompt_mode TEXT DEFAULT 'overwrite'")
        print("✓ Added 'system_prompt_mode' column to tests table")
    
    conn.commit()
    conn.close()
    
    print("✓ Migration complete: Added system prompt hierarchy columns")

if __name__ == '__main__':
    migrate()
