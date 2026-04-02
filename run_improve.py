#!/usr/bin/env python3
"""
Continuous Improvement CLI for evonic-llm-eval.

Usage:
    python run_improve.py start --run-id <eval_run_id>
    python run_improve.py complete --cycle-id <cycle_id> --improved-run-id <run_id>
    python run_improve.py compare --base-run <id> --improved-run <id>
    python run_improve.py list-cycles [--limit 10]
    python run_improve.py status --cycle-id <cycle_id>
"""

import argparse
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from improver.pipeline import ImprovementPipeline
from improver.comparator import ScoreComparator


def cmd_start(args):
    """Start a new improvement cycle."""
    print(f"Starting improvement cycle from run: {args.run_id}")
    print("-" * 50)
    
    pipeline = ImprovementPipeline(
        output_dir=args.output_dir,
        analyzer_model=args.model
    )
    
    try:
        result = pipeline.start_cycle(
            base_run_id=args.run_id,
            min_score_threshold=args.threshold
        )
        
        if result.get('status') == 'no_failures':
            print(f"✓ {result['message']}")
            return 0
        
        print(f"✓ Cycle started: {result['cycle_id'][:8]}...")
        print(f"  Failed tests analyzed: {result['failed_tests_count']}")
        print(f"  Training examples generated: {result['examples_generated']}")
        print(f"  Output: {result['training_data_path']}")
        print()
        print(f"Next step: {result['next_step']}")
        
        if args.json:
            print()
            print(json.dumps(result, indent=2, default=str))
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_complete(args):
    """Complete an improvement cycle after fine-tuning."""
    print(f"Completing cycle: {args.cycle_id[:8]}...")
    print(f"Improved run: {args.improved_run_id[:8]}...")
    print("-" * 50)
    
    pipeline = ImprovementPipeline()
    
    try:
        result = pipeline.complete_cycle(
            cycle_id=args.cycle_id,
            improved_run_id=args.improved_run_id,
            require_approval=not args.auto_deploy
        )
        
        print(result['report'])
        print()
        
        if result['deployed']:
            print("✓ Model auto-deployed!")
        elif result.get('requires_approval'):
            print("⚠ Ready to deploy - awaiting manual approval")
        else:
            print(f"→ Recommendation: {result['recommendation']}")
        
        if args.json:
            print()
            print(json.dumps(result, indent=2, default=str))
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_compare(args):
    """Compare two evaluation runs."""
    print(f"Comparing runs:")
    print(f"  Base:     {args.base_run[:8]}...")
    print(f"  Improved: {args.improved_run[:8]}...")
    print("-" * 50)
    
    comparator = ScoreComparator()
    
    try:
        result = comparator.compare_runs(args.base_run, args.improved_run)
        print(comparator.generate_report(result))
        
        if args.json:
            print()
            print(json.dumps(result, indent=2, default=str))
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_list_cycles(args):
    """List recent improvement cycles."""
    pipeline = ImprovementPipeline()
    
    try:
        cycles = pipeline.list_cycles(limit=args.limit)
        
        if not cycles:
            print("No improvement cycles found.")
            return 0
        
        print(f"Recent improvement cycles (limit {args.limit}):")
        print("-" * 80)
        print(f"{'ID':10} {'Status':12} {'Created':20} {'Recommendation':15} {'Examples':8}")
        print("-" * 80)
        
        for cycle in cycles:
            cycle_id = cycle.get('cycle_id', '')[:8]
            status = cycle.get('status', 'unknown')[:12]
            created = str(cycle.get('created_at', ''))[:20]
            rec = (cycle.get('recommendation') or '-')[:15]
            examples = str(cycle.get('examples_count', '-'))
            
            print(f"{cycle_id:10} {status:12} {created:20} {rec:15} {examples:8}")
        
        if args.json:
            print()
            print(json.dumps(cycles, indent=2, default=str))
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_status(args):
    """Get status of an improvement cycle."""
    pipeline = ImprovementPipeline()
    
    try:
        status = pipeline.get_cycle_status(args.cycle_id)
        
        if status.get('error'):
            print(f"Error: {status['error']}")
            return 1
        
        print(f"Cycle Status: {args.cycle_id[:8]}...")
        print("-" * 50)
        print(f"  Status:         {status.get('status', 'unknown')}")
        print(f"  Base Run:       {status.get('base_run_id', 'N/A')[:8]}...")
        print(f"  Improved Run:   {(status.get('improved_run_id') or 'N/A')[:8]}...")
        print(f"  Created:        {status.get('created_at', 'N/A')}")
        print(f"  Completed:      {status.get('completed_at') or 'Not yet'}")
        print(f"  Examples:       {status.get('examples_count', 'N/A')}")
        print(f"  Recommendation: {status.get('recommendation') or 'Pending'}")
        print(f"  Training Data:  {status.get('training_data_path', 'N/A')}")
        
        if status.get('analysis_summary'):
            print(f"  Analysis:       {status['analysis_summary'][:60]}...")
        
        if args.json:
            print()
            print(json.dumps(status, indent=2, default=str))
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Continuous Improvement CLI for evonic-llm-eval",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start improvement cycle from an evaluation run
  python run_improve.py start --run-id abc123-def456

  # Complete cycle after fine-tuning
  python run_improve.py complete --cycle-id xyz789 --improved-run-id new123

  # Compare two runs directly
  python run_improve.py compare --base-run abc123 --improved-run def456

  # List recent cycles
  python run_improve.py list-cycles --limit 5
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start improvement cycle")
    start_parser.add_argument("--run-id", required=True, help="Evaluation run ID to improve")
    start_parser.add_argument("--output-dir", default="training_data/generated", help="Output directory")
    start_parser.add_argument("--model", default="claude-opus-4-0", help="Analyzer model")
    start_parser.add_argument("--threshold", type=float, default=0.8, help="Score threshold for failures")
    start_parser.add_argument("--json", action="store_true", help="Output JSON")
    start_parser.set_defaults(func=cmd_start)
    
    # Complete command
    complete_parser = subparsers.add_parser("complete", help="Complete improvement cycle")
    complete_parser.add_argument("--cycle-id", required=True, help="Improvement cycle ID")
    complete_parser.add_argument("--improved-run-id", required=True, help="Improved model's eval run ID")
    complete_parser.add_argument("--auto-deploy", action="store_true", help="Auto-deploy if criteria met")
    complete_parser.add_argument("--json", action="store_true", help="Output JSON")
    complete_parser.set_defaults(func=cmd_complete)
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two evaluation runs")
    compare_parser.add_argument("--base-run", required=True, help="Base run ID")
    compare_parser.add_argument("--improved-run", required=True, help="Improved run ID")
    compare_parser.add_argument("--json", action="store_true", help="Output JSON")
    compare_parser.set_defaults(func=cmd_compare)
    
    # List cycles command
    list_parser = subparsers.add_parser("list-cycles", help="List improvement cycles")
    list_parser.add_argument("--limit", type=int, default=10, help="Number of cycles to show")
    list_parser.add_argument("--json", action="store_true", help="Output JSON")
    list_parser.set_defaults(func=cmd_list_cycles)
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Get cycle status")
    status_parser.add_argument("--cycle-id", required=True, help="Improvement cycle ID")
    status_parser.add_argument("--json", action="store_true", help="Output JSON")
    status_parser.set_defaults(func=cmd_status)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
