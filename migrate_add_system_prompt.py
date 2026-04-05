#!/usr/bin/env python3
"""
Migration: Add system_prompt column to tests table

Run this once if you have an existing evaluation.db
"""

import sqlite3
import config

def migrate():
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    # Check if column already exists
    cursor.execute("PRAGMA table_info(tests)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'system_prompt' in columns:
        print("✓ Column 'system_prompt' already exists")
        conn.close()
        return
    
    # Add the column
    cursor.execute("""
        ALTER TABLE tests ADD COLUMN system_prompt TEXT
    """)
    
    conn.commit()
    conn.close()
    
    print("✓ Migration complete: Added 'system_prompt' column to tests table")

if __name__ == '__main__':
    migrate()
