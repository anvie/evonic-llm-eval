from typing import Dict, Any, Optional
import json
from tests import get_test_class

class ScoringEngine:
    def __init__(self):
        pass
    
    def score_test(self, domain: str, level: int, response: str, expected: Any) -> Dict[str, Any]:
        """Score a test response"""
        test_class = get_test_class(domain)
        if not test_class:
            return {
                "score": 0.0,
                "details": {"error": f"Unknown domain: {domain}"},
                "status": "failed"
            }
        
        test_instance = test_class(level)
        scoring_result = test_instance.score_response(response, expected)
        
        # Determine status based on score
        score = scoring_result.get("score", 0.0)
        status = scoring_result.get("status", "passed" if score >= 0.8 else "failed")
        
        # Build details object with all relevant info
        details = {
            "details": scoring_result.get("details", ""),
        }
        
        # Include breakdown if available (for SQL tests)
        if "breakdown" in scoring_result:
            details["breakdown"] = scoring_result["breakdown"]
        if "sql_query" in scoring_result:
            details["sql_query"] = scoring_result["sql_query"]
        if "columns" in scoring_result:
            details["columns"] = scoring_result["columns"]
        if "row_count" in scoring_result:
            details["row_count"] = scoring_result["row_count"]
        if "actual_result_preview" in scoring_result:
            details["actual_result_preview"] = scoring_result["actual_result_preview"]
        
        # For conversation tests, include relevance/correctness/fluency
        if "relevance" in scoring_result:
            details["relevance"] = scoring_result["relevance"]
        if "correctness" in scoring_result:
            details["correctness"] = scoring_result["correctness"]
        if "fluency" in scoring_result:
            details["fluency"] = scoring_result["fluency"]
        if "keywords_found" in scoring_result:
            details["keywords_found"] = scoring_result["keywords_found"]
        
        return {
            "score": score,
            "details": details,
            "status": status
        }
    
    def validate_tool_calls(self, tool_calls: list, expected_tools: list) -> Dict[str, Any]:
        """Validate tool calls against expected tools"""
        if not tool_calls:
            return {
                "valid": False,
                "error": "No tool calls found"
            }
        
        called_tools = [call["function"]["name"] for call in tool_calls]
        
        # Check if all expected tools were called
        missing_tools = set(expected_tools) - set(called_tools)
        extra_tools = set(called_tools) - set(expected_tools)
        
        return {
            "valid": len(missing_tools) == 0,
            "called_tools": called_tools,
            "missing_tools": list(missing_tools),
            "extra_tools": list(extra_tools)
        }
    
    def calculate_overall_score(self, test_results: list) -> float:
        """Calculate weighted overall score from all test results"""
        if not test_results:
            return 0.0
        
        # Get only completed tests with scores
        scored_tests = [
            result for result in test_results 
            if result.get("score") is not None and result.get("status") != "skipped"
        ]
        
        if not scored_tests:
            return 0.0
        
        # Weight by level (higher levels contribute more)
        total_weight = 0
        weighted_sum = 0
        
        for result in scored_tests:
            level = result.get("level", 1)
            weight = level  # Level 1 = weight 1, Level 5 = weight 5
            score = result.get("score", 0.0)
            
            total_weight += weight
            weighted_sum += score * weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def generate_summary(self, test_results: list, model_name: str) -> str:
        """Generate executive summary using scoring data"""
        if not test_results:
            return "No tests completed"
        
        # Count results by domain
        domain_scores = {}
        domain_counts = {}
        
        for result in test_results:
            domain = result.get("domain")
            score = result.get("score", 0.0)
            
            if domain not in domain_scores:
                domain_scores[domain] = 0.0
                domain_counts[domain] = 0
            
            domain_scores[domain] += score
            domain_counts[domain] += 1
        
        # Calculate average per domain
        domain_avgs = {}
        for domain in domain_scores:
            if domain_counts[domain] > 0:
                domain_avgs[domain] = domain_scores[domain] / domain_counts[domain]
        
        # Find strongest and weakest domains
        if domain_avgs:
            strongest_domain = max(domain_avgs.items(), key=lambda x: x[1])
            weakest_domain = min(domain_avgs.items(), key=lambda x: x[1])
            
            # Generate summary text
            summary_parts = []
            
            if strongest_domain[1] >= 0.8:
                summary_parts.append(f"excel dalam {strongest_domain[0]}")
            elif strongest_domain[1] >= 0.6:
                summary_parts.append(f"cukup baik dalam {strongest_domain[0]}")
            
            if weakest_domain[1] <= 0.4:
                summary_parts.append(f"tetapi kurang dalam {weakest_domain[0]}")
            elif weakest_domain[1] <= 0.6:
                summary_parts.append(f"dengan performa sedang dalam {weakest_domain[0]}")
            
            if summary_parts:
                summary = f"Model {model_name} " + ", ".join(summary_parts) + "."
            else:
                summary = f"Model {model_name} menunjukkan performa yang seimbang di semua domain."
        else:
            summary = f"Model {model_name} telah diuji tetapi tidak ada data domain yang cukup."
        
        return summary

# Global scoring engine instance
scoring_engine = ScoringEngine()