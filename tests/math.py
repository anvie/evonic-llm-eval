from .base import BaseTest
from typing import Dict, Any, Optional
import re


class MathTest(BaseTest):
    """Mathematical calculation tests - expects clean number from PASS 2"""
    
    def get_prompt(self) -> str:
        prompts = {
            1: "Berapa hasil dari 7 + 3?",
            2: "Hitung 15% dari 240",
            3: "Jika deposito Rp 10.000.000 dengan bunga 6% per tahun, berapa total setelah 2 tahun?",
            4: "Hitung luas segitiga dengan alas 8 cm dan tinggi 6 cm",
            5: "Sebuah toko memberikan diskon 20% kemudian tambahan diskon 10%. Jika harga awal Rp 500.000, berapa harga akhir?"
        }
        return prompts.get(self.level, "")
    
    def get_expected(self) -> float:
        expected = {
            1: 10.0,
            2: 36.0,        # 15% of 240 = 36.0
            3: 11236000.0,  # 10,000,000 * (1.06)^2
            4: 24.0,        # 0.5 * 8 * 6
            5: 360000.0     # 500,000 * 0.8 * 0.9
        }
        return expected.get(self.level, 0.0)
    
    def score_response(self, response: str, expected: float) -> Dict[str, Any]:
        """
        Score response - expects clean number from PASS 2.
        
        Response should be just a number like "36" or "820800".
        If it's not a clean number, try to extract but mark as lower confidence.
        """
        import re
        
        # Clean the response
        clean = response.strip()
        
        # Try to parse as number directly
        try:
            actual = float(clean)
            return self._compare_values(actual, expected)
        except ValueError:
            pass
        
        # Maybe has some separators - try to remove them
        clean_no_sep = clean.replace(',', '').replace('.', '').replace(' ', '')
        try:
            actual = float(clean_no_sep)
            return self._compare_values(actual, expected)
        except ValueError:
            pass
        
        # Maybe has Rp prefix or other text - try to extract number
        numbers = re.findall(r'[-+]?\d+\.?\d*', clean)
        if numbers:
            try:
                actual = float(numbers[0])
                # If we had to extract, still try to match
                return self._compare_values(actual, expected)
            except ValueError:
                pass
        
        return {
            "score": 0.0,
            "details": f"Not a valid number: '{response}'",
            "actual": None,
            "expected": expected
        }
    
    def _compare_values(self, actual: float, expected: float) -> Dict[str, Any]:
        """Compare actual vs expected values"""
        if abs(actual - expected) < 0.01:  # Small tolerance for floats
            return {
                "score": 1.0,
                "details": f"Correct: {actual}",
                "actual": actual,
                "expected": expected
            }
        else:
            return {
                "score": 0.0,
                "details": f"Wrong: expected {expected}, got {actual}",
                "actual": actual,
                "expected": expected
            }
