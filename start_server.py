#!/usr/bin/env python3
"""
Evonic LLM Evaluator - Server Startup Script
"""

import subprocess
import sys
import os
import time

def start_server():
    print("=" * 60)
    print("EVONIC LLM EVALUATOR - SERVER STARTUP")
    print("=" * 60)
    
    # Ensure we're in the right directory (use script's location)
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    print(f"Working directory: {os.getcwd()}")
    
    # Check if app.py exists
    if not os.path.exists('app.py'):
        print("ERROR: app.py not found!")
        return False
    
    # Check if config.py exists
    if not os.path.exists('config.py'):
        print("ERROR: config.py not found!")
        return False
        
    print("OK: app.py and config.py found")
    
    # Set environment
    env = os.environ.copy()
    # Add user's local bin to PATH
    home_dir = os.path.expanduser('~')
    env['PATH'] = f'{home_dir}/.local/bin:' + env.get('PATH', '')
    
    # Read current config
    print("\nCurrent Configuration:")
    try:
        with open('config.py', 'r') as f:
            config_content = f.read()
            if 'moonshotai/kimi-k2-thinking' in config_content:
                print("  Model: moonshotai/kimi-k2-thinking")
            if 'openrouter.ai' in config_content:
                print("  API: OpenRouter")
            if '8080' in config_content:
                print("  Port: 8080")
    except:
        print("  Could not read config details")
    
    # Start Flask app
    print("\nStarting Flask server...")
    try:
        proc = subprocess.Popen(
            ['python3', 'app.py'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        print(f"Starting (PID: {proc.pid})...")
        
        # Wait for initialization
        for i in range(5):
            time.sleep(1)
            sys.stdout.write(f"." if i > 0 else "")
            sys.stdout.flush()
        
        # Check if still running
        if proc.poll() is None:
            print("\n\nSERVER IS RUNNING!")
            print("=" * 60)
            print("Web UI:   http://localhost:8080")
            print("Config:   Kimi-K2-Thinking via OpenRouter")
            print("Tests:    25 tests (5 domains x 5 levels)")
            print("Action:   Click 'Start Evaluation' in web UI")
            print("=" * 60)
            print("\nServer running in background...")
            return True
        else:
            print(f"\nERROR: Server exited with code: {proc.returncode}")
            stdout, stderr = proc.communicate()
            print("\nSTDOUT:", stdout.decode()[:300])
            print("\nSTDERR:", stderr.decode()[:300])
            return False
            
    except Exception as e:
        print(f"\nERROR starting server: {e}")
        return False

if __name__ == "__main__":
    success = start_server()
    sys.exit(0 if success else 1)
