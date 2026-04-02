#!/usr/bin/env python3
"""Migration: Add total_tokens and total_duration_ms columns to evaluation_runs table"""

import sqlite3
import config

def migrate():
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    # Check if columns exist
    cursor.execute("PRAGMA table_info(evaluation_runs)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'total_tokens' not in columns:
        cursor.execute("ALTER TABLE evaluation_runs ADD COLUMN total_tokens INTEGER DEFAULT 0")
        print("Added total_tokens column")
    
    if 'total_duration_ms' not in columns:
        cursor.execute("ALTER TABLE evaluation_runs ADD COLUMN total_duration_ms INTEGER DEFAULT 0")
        print("Added total_duration_ms column")
    
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
