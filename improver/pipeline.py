"""Orchestrate the full continuous improvement pipeline."""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.db import db
from .analyzer import FailureAnalyzer
from .data_generator import TrainingDataGenerator
from .data_adjuster import DataAdjuster
from .comparator import ScoreComparator


class ImprovementPipeline:
    """
    Orchestrate the continuous improvement cycle:
    1. Get failed tests from evaluation run
    2. Analyze failures with Claude Opus
    3. Generate/adjust training data
    4. (External) Fine-tune model
    5. Evaluate new model
    6. Compare results
    7. Decide: deploy/iterate/rollback
    """
    
    def __init__(
        self,
        output_dir: str = "training_data/generated",
        analyzer_model: str = "claude-opus-4-0"
    ):
        self.output_dir = output_dir
        self.analyzer = FailureAnalyzer(model=analyzer_model)
        self.generator = TrainingDataGenerator(model=analyzer_model)
        self.adjuster = DataAdjuster()
        self.comparator = ScoreComparator()
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
    
    def start_cycle(self, base_run_id: str, min_score_threshold: float = 0.8) -> Dict[str, Any]:
        """
        Start an improvement cycle from an evaluation run.
        
        Args:
            base_run_id: The evaluation run ID to improve from
            min_score_threshold: Tests below this score are considered failures
            
        Returns:
            {
                "cycle_id": str,
                "base_run_id": str,
                "training_data_path": str,
                "analysis": {...},
                "examples_generated": int,
                "next_step": str
            }
        """
        # Create cycle ID
        cycle_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Get failed tests
        all_results = db.get_test_results(base_run_id)
        failed_tests = [
            r for r in all_results 
            if r.get('score', 1.0) < min_score_threshold or r.get('status') == 'failed'
        ]
        
        if not failed_tests:
            return {
                "cycle_id": cycle_id,
                "base_run_id": base_run_id,
                "status": "no_failures",
                "message": f"No tests below threshold ({min_score_threshold}). Nothing to improve.",
                "next_step": "None needed"
            }
        
        # Analyze failures
        print(f"Analyzing {len(failed_tests)} failed tests...")
        analysis = self.analyzer.analyze_failures(failed_tests)
        
        # Generate training data
        print("Generating training data...")
        generated_examples = []
        
        for recommendation in analysis.get('training_recommendations', []):
            if recommendation.get('action') == 'generate':
                examples = self.generator.generate_for_domain(
                    domain=recommendation.get('domain'),
                    patterns=analysis.get('patterns', []),
                    count=recommendation.get('example_count', 10)
                )
                generated_examples.extend(examples)
        
        # Save training data
        output_path = os.path.join(
            self.output_dir, 
            f"cycle_{cycle_id[:8]}_{timestamp}.jsonl"
        )
        
        self._save_training_data(output_path, generated_examples, cycle_id)
        
        # Store cycle info in database
        db.create_improvement_cycle(
            cycle_id=cycle_id,
            base_run_id=base_run_id,
            analysis=json.dumps(analysis),
            training_data_path=output_path,
            examples_count=len(generated_examples)
        )
        
        return {
            "cycle_id": cycle_id,
            "base_run_id": base_run_id,
            "training_data_path": output_path,
            "analysis": analysis,
            "failed_tests_count": len(failed_tests),
            "examples_generated": len(generated_examples),
            "status": "training_data_ready",
            "next_step": "Run fine-tuning with the generated data, then call complete_cycle()"
        }
    
    def complete_cycle(
        self, 
        cycle_id: str, 
        improved_run_id: str,
        require_approval: bool = True
    ) -> Dict[str, Any]:
        """
        Complete an improvement cycle after fine-tuning and re-evaluation.
        
        Args:
            cycle_id: The improvement cycle ID
            improved_run_id: The evaluation run ID of the improved model
            require_approval: If True, don't auto-deploy even if criteria met
            
        Returns:
            {
                "cycle_id": str,
                "comparison": {...},
                "recommendation": str,
                "deployed": bool
            }
        """
        # Get cycle info
        cycle = db.get_improvement_cycle(cycle_id)
        if not cycle:
            raise ValueError(f"Cycle not found: {cycle_id}")
        
        base_run_id = cycle['base_run_id']
        
        # Compare results
        comparison = self.comparator.compare_runs(base_run_id, improved_run_id)
        
        # Update cycle with results
        db.complete_improvement_cycle(
            cycle_id=cycle_id,
            improved_run_id=improved_run_id,
            comparison=json.dumps(comparison),
            recommendation=comparison['recommendation']
        )
        
        # Determine deployment
        should_deploy = self.comparator.should_deploy(comparison)
        deployed = False
        
        if should_deploy and not require_approval:
            deployed = True
            # In a real system, this would trigger model deployment
            print(f"✓ Auto-deploying improved model from run {improved_run_id}")
        
        return {
            "cycle_id": cycle_id,
            "base_run_id": base_run_id,
            "improved_run_id": improved_run_id,
            "comparison": comparison,
            "recommendation": comparison['recommendation'],
            "report": self.comparator.generate_report(comparison),
            "deployed": deployed,
            "requires_approval": require_approval and should_deploy
        }
    
    def _save_training_data(
        self, 
        path: str, 
        examples: List[Dict], 
        cycle_id: str
    ) -> None:
        """Save training examples as JSONL."""
        with open(path, 'w', encoding='utf-8') as f:
            for example in examples:
                # Add metadata
                example['_meta'] = {
                    'cycle_id': cycle_id,
                    'generated_at': datetime.now().isoformat(),
                    'source': 'evonic-improver'
                }
                f.write(json.dumps(example, ensure_ascii=False) + '\n')
        
        print(f"Saved {len(examples)} examples to {path}")
    
    def list_cycles(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent improvement cycles."""
        return db.get_improvement_cycles(limit=limit)
    
    def get_cycle_status(self, cycle_id: str) -> Dict[str, Any]:
        """Get detailed status of an improvement cycle."""
        cycle = db.get_improvement_cycle(cycle_id)
        if not cycle:
            return {"error": f"Cycle not found: {cycle_id}"}
        
        status = {
            "cycle_id": cycle_id,
            "base_run_id": cycle.get('base_run_id'),
            "improved_run_id": cycle.get('improved_run_id'),
            "status": cycle.get('status', 'unknown'),
            "created_at": cycle.get('created_at'),
            "completed_at": cycle.get('completed_at'),
            "training_data_path": cycle.get('training_data_path'),
            "examples_count": cycle.get('examples_count'),
            "recommendation": cycle.get('recommendation')
        }
        
        # Parse analysis if available
        if cycle.get('analysis'):
            try:
                status['analysis_summary'] = json.loads(cycle['analysis']).get('summary')
            except:
                pass
        
        return status


# Convenience function
def run_improvement_cycle(
    base_run_id: str,
    output_dir: str = "training_data/generated",
    analyzer_model: str = "claude-opus-4-0"
) -> Dict[str, Any]:
    """
    Convenience function to start an improvement cycle.
    
    Usage:
        result = run_improvement_cycle("abc123-run-id")
        print(f"Training data at: {result['training_data_path']}")
    """
    pipeline = ImprovementPipeline(
        output_dir=output_dir,
        analyzer_model=analyzer_model
    )
    return pipeline.start_cycle(base_run_id)
