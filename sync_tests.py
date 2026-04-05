#!/usr/bin/env python3
"""
Sync test definitions to database
Run this after adding new evaluators or tests
"""

from evaluator.test_manager import test_manager

if __name__ == '__main__':
    print("Syncing test definitions to database...")
    test_manager.sync_to_db()
    print("✓ Sync complete! Reload Settings page to see new evaluators.")
