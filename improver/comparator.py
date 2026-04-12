"""Compare evaluation results before and after improvement cycles."""

import json
from typing import Any, Dict, List, Optional
from models.db import db


class ScoreComparator:
    """Compare two evaluation runs and determine if improvement warrants deployment."""
    
    # Deployment criteria
    MIN_IMPROVEMENT = 0.05  # 5% minimum overall improvement
    MAX_REGRESSION = 0.10   # 10% maximum regression per domain
    MIN_TOOL_CALLING = 0.70  # Tool calling must be at least 70%
    
    def __init__(self):
        pass
    
    def compare_runs(self, base_run_id: int, improved_run_id: int) -> Dict[str, Any]:
        """
        Compare two evaluation runs.
        
        Returns:
            {
                "base_run_id": str,
                "improved_run_id": str,
                "base_score": float,
                "improved_score": float,
                "delta": float,
                "improvement_pct": str,
                "domain_comparison": {
                    "<domain>": {"base": float, "improved": float, "delta": float}
                },
                "regressions": [...],
                "improvements": [...],
                "recommendation": "deploy" | "iterate" | "rollback",
                "recommendation_reasons": [...]
            }
        """
        # Get run info
        base_run = db.get_evaluation_run(base_run_id)
        improved_run = db.get_evaluation_run(improved_run_id)
        
        if not base_run or not improved_run:
            raise ValueError("One or both runs not found")
        
        # Get test results
        base_results = db.get_test_results(base_run_id)
        improved_results = db.get_test_results(improved_run_id)
        
        # Calculate domain scores
        base_domain_scores = self._calculate_domain_scores(base_results)
        improved_domain_scores = self._calculate_domain_scores(improved_results)
        
        # Calculate overall scores
        base_score = base_run.get('overall_score') or self._calculate_overall(base_results)
        improved_score = improved_run.get('overall_score') or self._calculate_overall(improved_results)
        
        delta = improved_score - base_score
        improvement_pct = f"{delta * 100:+.1f}%" if base_score > 0 else "N/A"
        
        # Build domain comparison
        domains = set(base_domain_scores.keys()) | set(improved_domain_scores.keys())
        domain_comparison = {}
        regressions = []
        improvements = []
        
        for domain in domains:
            base_val = base_domain_scores.get(domain, 0.0)
            improved_val = improved_domain_scores.get(domain, 0.0)
            domain_delta = improved_val - base_val
            
            domain_comparison[domain] = {
                "base": round(base_val, 3),
                "improved": round(improved_val, 3),
                "delta": round(domain_delta, 3)
            }
            
            if domain_delta < -0.01:  # Regressed by more than 1%
                regressions.append({
                    "domain": domain,
                    "delta": domain_delta,
                    "severity": "high" if domain_delta < -self.MAX_REGRESSION else "low"
                })
            elif domain_delta > 0.01:  # Improved by more than 1%
                improvements.append({
                    "domain": domain,
                    "delta": domain_delta
                })
        
        # Determine recommendation
        recommendation, reasons = self._determine_recommendation(
            delta, domain_comparison, regressions
        )
        
        return {
            "base_run_id": base_run_id,
            "improved_run_id": improved_run_id,
            "base_score": round(base_score, 3),
            "improved_score": round(improved_score, 3),
            "delta": round(delta, 3),
            "improvement_pct": improvement_pct,
            "domain_comparison": domain_comparison,
            "regressions": regressions,
            "improvements": improvements,
            "recommendation": recommendation,
            "recommendation_reasons": reasons
        }
    
    def _calculate_domain_scores(self, results: List[Dict]) -> Dict[str, float]:
        """Calculate average score per domain."""
        domain_scores = {}
        domain_counts = {}
        
        for result in results:
            domain = result.get('domain')
            score = result.get('score')
            
            if domain and score is not None:
                domain_scores[domain] = domain_scores.get(domain, 0.0) + score
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        return {
            domain: domain_scores[domain] / domain_counts[domain]
            for domain in domain_scores
            if domain_counts[domain] > 0
        }
    
    def _calculate_overall(self, results: List[Dict]) -> float:
        """Calculate weighted overall score."""
        if not results:
            return 0.0
        
        total_weight = 0
        weighted_sum = 0
        
        for result in results:
            score = result.get('score')
            level = result.get('level', 1)
            
            if score is not None:
                weight = level  # Higher levels = more weight
                total_weight += weight
                weighted_sum += score * weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def _determine_recommendation(
        self, 
        delta: float, 
        domain_comparison: Dict,
        regressions: List[Dict]
    ) -> tuple:
        """Determine deployment recommendation."""
        reasons = []
        
        # Check overall improvement
        if delta < self.MIN_IMPROVEMENT:
            reasons.append(f"Overall improvement ({delta*100:.1f}%) below threshold ({self.MIN_IMPROVEMENT*100}%)")
        
        # Check for severe regressions
        severe_regressions = [r for r in regressions if r['severity'] == 'high']
        if severe_regressions:
            domains = [r['domain'] for r in severe_regressions]
            reasons.append(f"Severe regression in: {', '.join(domains)}")
        
        # Check tool_calling score
        tool_calling = domain_comparison.get('tool_calling', {})
        if tool_calling.get('improved', 0) < self.MIN_TOOL_CALLING:
            reasons.append(f"Tool calling score ({tool_calling.get('improved', 0)*100:.1f}%) below minimum ({self.MIN_TOOL_CALLING*100}%)")
        
        # Determine recommendation
        if delta < 0:
            return "rollback", reasons + ["Overall score decreased"]
        elif reasons:
            return "iterate", reasons
        else:
            return "deploy", ["All criteria met"]
    
    def generate_report(self, comparison: Dict) -> str:
        """Generate human-readable comparison report."""
        lines = [
            "=" * 60,
            "IMPROVEMENT CYCLE COMPARISON REPORT",
            "=" * 60,
            "",
            f"Base Run:     #{comparison['base_run_id']:04d}",
            f"Improved Run: #{comparison['improved_run_id']:04d}",
            "",
            f"Overall Score: {comparison['base_score']*100:.1f}% → {comparison['improved_score']*100:.1f}% ({comparison['improvement_pct']})",
            "",
            "-" * 60,
            "DOMAIN BREAKDOWN",
            "-" * 60,
        ]
        
        for domain, scores in comparison['domain_comparison'].items():
            delta_str = f"{scores['delta']*100:+.1f}%"
            lines.append(f"  {domain:15} {scores['base']*100:5.1f}% → {scores['improved']*100:5.1f}% ({delta_str})")
        
        lines.extend([
            "",
            "-" * 60,
            f"RECOMMENDATION: {comparison['recommendation'].upper()}",
            "-" * 60,
        ])
        
        for reason in comparison['recommendation_reasons']:
            lines.append(f"  • {reason}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def should_deploy(self, comparison: Dict) -> bool:
        """Simple boolean check for deployment decision."""
        return comparison['recommendation'] == 'deploy'


# Global instance
comparator = ScoreComparator()
