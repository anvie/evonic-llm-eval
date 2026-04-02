"""
Score Aggregator - Aggregate scores from multiple tests per level.

Calculates average scores for levels, domains, and overall evaluation.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class TestResult:
    """Represents a single test result"""
    test_id: str
    domain: str
    level: int
    score: float
    status: str
    weight: float = 1.0
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class LevelScore:
    """Represents aggregated score for a level"""
    domain: str
    level: int
    average_score: float
    total_tests: int
    passed_tests: int
    weighted_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'domain': self.domain,
            'level': self.level,
            'average_score': self.average_score,
            'total_tests': self.total_tests,
            'passed_tests': self.passed_tests,
            'weighted_score': self.weighted_score
        }


@dataclass
class DomainScore:
    """Represents aggregated score for a domain"""
    domain: str
    average_score: float
    total_tests: int
    passed_tests: int
    levels: Dict[int, LevelScore]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'domain': self.domain,
            'average_score': self.average_score,
            'total_tests': self.total_tests,
            'passed_tests': self.passed_tests,
            'levels': {str(k): v.to_dict() for k, v in self.levels.items()}
        }


class ScoreAggregator:
    """Aggregate scores from multiple tests"""
    
    @staticmethod
    def calculate_level_score(test_results: List[TestResult]) -> LevelScore:
        """Calculate average score for a level from multiple test results
        
        Uses weighted average if weights are provided.
        
        Args:
            test_results: List of TestResult objects
            
        Returns:
            LevelScore with aggregated data
        """
        if not test_results:
            return LevelScore(
                domain="",
                level=0,
                average_score=0.0,
                total_tests=0,
                passed_tests=0
            )
        
        domain = test_results[0].domain
        level = test_results[0].level
        
        # Calculate weighted average
        total_weight = 0.0
        weighted_sum = 0.0
        passed_count = 0
        
        for result in test_results:
            weight = result.weight if result.weight > 0 else 1.0
            total_weight += weight
            weighted_sum += result.score * weight
            
            if result.status == 'passed':
                passed_count += 1
        
        # Calculate average (weighted or simple)
        if total_weight > 0:
            average_score = weighted_sum / total_weight
        else:
            average_score = sum(r.score for r in test_results) / len(test_results)
        
        return LevelScore(
            domain=domain,
            level=level,
            average_score=average_score,
            total_tests=len(test_results),
            passed_tests=passed_count,
            weighted_score=average_score  # Same as average for now
        )
    
    @staticmethod
    def calculate_domain_score(level_scores: List[LevelScore]) -> DomainScore:
        """Calculate overall domain score from level scores
        
        Args:
            level_scores: List of LevelScore objects
            
        Returns:
            DomainScore with aggregated data
        """
        if not level_scores:
            return DomainScore(
                domain="",
                average_score=0.0,
                total_tests=0,
                passed_tests=0,
                levels={}
            )
        
        domain = level_scores[0].domain
        
        # Calculate average across levels
        total_score = sum(ls.average_score for ls in level_scores)
        average_score = total_score / len(level_scores)
        
        # Sum up totals
        total_tests = sum(ls.total_tests for ls in level_scores)
        passed_tests = sum(ls.passed_tests for ls in level_scores)
        
        # Build levels dict
        levels_dict = {ls.level: ls for ls in level_scores}
        
        return DomainScore(
            domain=domain,
            average_score=average_score,
            total_tests=total_tests,
            passed_tests=passed_tests,
            levels=levels_dict
        )
    
    @staticmethod
    def calculate_overall_score(domain_scores: List[DomainScore]) -> Dict[str, Any]:
        """Calculate overall evaluation score
        
        Args:
            domain_scores: List of DomainScore objects
            
        Returns:
            Dictionary with overall score and breakdown
        """
        if not domain_scores:
            return {
                'overall_score': 0.0,
                'total_tests': 0,
                'passed_tests': 0,
                'domains': {}
            }
        
        # Calculate overall average
        total_score = sum(ds.average_score for ds in domain_scores)
        overall_score = total_score / len(domain_scores)
        
        # Sum up totals
        total_tests = sum(ds.total_tests for ds in domain_scores)
        passed_tests = sum(ds.passed_tests for ds in domain_scores)
        
        # Build domains dict
        domains_dict = {ds.domain: ds.to_dict() for ds in domain_scores}
        
        return {
            'overall_score': round(overall_score, 4),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'pass_rate': round(passed_tests / total_tests, 4) if total_tests > 0 else 0.0,
            'domains': domains_dict
        }
    
    @staticmethod
    def aggregate_results(test_results: List[TestResult]) -> Dict[str, Any]:
        """Aggregate all test results into a complete summary
        
        Args:
            test_results: List of all TestResult objects
            
        Returns:
            Complete aggregation with level, domain, and overall scores
        """
        # Group by domain and level
        by_domain_level: Dict[str, Dict[int, List[TestResult]]] = {}
        
        for result in test_results:
            if result.domain not in by_domain_level:
                by_domain_level[result.domain] = {}
            if result.level not in by_domain_level[result.domain]:
                by_domain_level[result.domain][result.level] = []
            by_domain_level[result.domain][result.level].append(result)
        
        # Calculate level scores
        all_level_scores: List[LevelScore] = []
        domain_level_scores: Dict[str, List[LevelScore]] = {}
        
        for domain, levels in by_domain_level.items():
            domain_level_scores[domain] = []
            for level, results in levels.items():
                level_score = ScoreAggregator.calculate_level_score(results)
                all_level_scores.append(level_score)
                domain_level_scores[domain].append(level_score)
        
        # Calculate domain scores
        domain_scores: List[DomainScore] = []
        for domain, level_scores in domain_level_scores.items():
            domain_score = ScoreAggregator.calculate_domain_score(level_scores)
            domain_scores.append(domain_score)
        
        # Calculate overall score
        overall = ScoreAggregator.calculate_overall_score(domain_scores)
        
        return {
            'overall': overall,
            'domains': {ds.domain: ds.to_dict() for ds in domain_scores},
            'levels': {f"{ls.domain}_{ls.level}": ls.to_dict() for ls in all_level_scores}
        }
    
    @staticmethod
    def format_score_report(aggregation: Dict[str, Any]) -> str:
        """Format aggregation as a human-readable report
        
        Args:
            aggregation: Result from aggregate_results()
            
        Returns:
            Formatted string report
        """
        lines = []
        lines.append("=" * 60)
        lines.append("EVALUATION SCORE REPORT")
        lines.append("=" * 60)
        
        overall = aggregation['overall']
        lines.append(f"\nOverall Score: {overall['overall_score']:.2%}")
        lines.append(f"Total Tests: {overall['total_tests']}")
        lines.append(f"Passed Tests: {overall['passed_tests']}")
        lines.append(f"Pass Rate: {overall['pass_rate']:.2%}")
        
        lines.append("\n" + "-" * 60)
        lines.append("DOMAIN BREAKDOWN")
        lines.append("-" * 60)
        
        for domain_name, domain_data in aggregation['domains'].items():
            lines.append(f"\n{domain_name.upper()}")
            lines.append(f"  Average: {domain_data['average_score']:.2%}")
            lines.append(f"  Tests: {domain_data['total_tests']} ({domain_data['passed_tests']} passed)")
            
            for level_str, level_data in domain_data['levels'].items():
                level = int(level_str)
                status_icon = "✓" if level_data['average_score'] >= 0.7 else "✗"
                lines.append(f"    Level {level}: {status_icon} {level_data['average_score']:.2%} ({level_data['total_tests']} tests)")
        
        lines.append("\n" + "=" * 60)
        
        return "\n".join(lines)


# Convenience functions
def calculate_level_score(test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience function to calculate level score from dict results"""
    results = [
        TestResult(
            test_id=r.get('test_id', ''),
            domain=r.get('domain', ''),
            level=r.get('level', 0),
            score=r.get('score', 0.0),
            status=r.get('status', 'failed'),
            weight=r.get('weight', 1.0),
            details=r.get('details')
        )
        for r in test_results
    ]
    return ScoreAggregator.calculate_level_score(results).to_dict()


def aggregate_all_results(test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience function to aggregate all results from dict results"""
    results = [
        TestResult(
            test_id=r.get('test_id', ''),
            domain=r.get('domain', ''),
            level=r.get('level', 0),
            score=r.get('score', 0.0),
            status=r.get('status', 'failed'),
            weight=r.get('weight', 1.0),
            details=r.get('details')
        )
        for r in test_results
    ]
    return ScoreAggregator.aggregate_results(results)


# Global aggregator instance
score_aggregator = ScoreAggregator()