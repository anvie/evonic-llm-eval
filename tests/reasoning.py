from .base import BaseTest
from typing import Dict, Any
import re


class ReasoningTest(BaseTest):
    """Logical reasoning tests - expects clean format from PASS 2"""
    
    def get_prompt(self) -> str:
        prompts = {
            1: "Jika hari ini hujan, maka saya akan membawa payung. Hari ini hujan. Apakah saya akan membawa payung?",
            2: "Urutkan angka berikut dari terkecil ke terbesar: 15, 3, 22, 7, 18",
            3: """Sebuah perusahaan memiliki 3 tim: A, B, dan C. 
- Tim A memiliki 5 anggota
- Tim B memiliki 3 anggota lebih banyak dari Tim A
- Tim C memiliki setengah anggota Tim B
Berapa total anggota semua tim?""",
            4: """Dari pernyataan berikut, mana yang benar?
1. Semua burung bisa terbang
2. Beberapa burung bisa terbang
3. Tidak ada burung yang bisa terbang
4. Penguin adalah burung yang tidak bisa terbang""",
            5: """Sebuah toko memberikan diskon bertingkat:
- Diskon 20% untuk pembelian di atas Rp 500.000
- Diskon tambahan 10% untuk pembelian di atas Rp 1.000.000
- Diskon tambahan 5% untuk member loyal

Seorang member loyal membeli produk seharga Rp 1.200.000. Berapa harga yang harus dibayar setelah semua diskon?"""
        }
        return prompts.get(self.level, "")
    
    def get_expected(self) -> Any:
        expected = {
            1: "ya",
            2: [3, 7, 15, 18, 22],
            3: 17,  # Tim A=5, Tim B=5+3=8, Tim C=8/2=4, Total=5+8+4=17
            4: [2, 4],  # Pernyataan 2 dan 4 benar
            5: 820800.0  # 1,200,000 * 0.8 * 0.9 * 0.95
        }
        return expected.get(self.level, "")
    
    def score_response(self, response: str, expected: Any) -> Dict[str, Any]:
        """
        Score response - expects clean format from PASS 2.
        
        Level 1: "ya" or "tidak"
        Level 2: "3, 7, 15, 18, 22"
        Level 3: "17"
        Level 4: "2, 4"
        Level 5: "820800"
        """
        
        if self.level == 1:
            return self._score_level_1(response, expected)
        elif self.level == 2:
            return self._score_level_2(response, expected)
        elif self.level == 3:
            return self._score_level_3(response, expected)
        elif self.level == 4:
            return self._score_level_4(response, expected)
        elif self.level == 5:
            return self._score_level_5(response, expected)
        
        return {"score": 0.0, "details": "Unknown level"}
    
    def _score_level_1(self, response: str, expected: str) -> Dict[str, Any]:
        """Level 1: Boolean - expects 'ya' or 'tidak'"""
        clean = response.strip().lower()
        
        if clean == expected:
            return {"score": 1.0, "details": f"Correct: {clean}"}
        else:
            return {"score": 0.0, "details": f"Wrong: expected '{expected}', got '{clean}'"}
    
    def _score_level_2(self, response: str, expected: list) -> Dict[str, Any]:
        """Level 2: Sequence - expects '3, 7, 15, 18, 22'"""
        try:
            numbers = [int(n.strip()) for n in response.split(',')]
            if numbers == expected:
                return {"score": 1.0, "details": f"Correct: {numbers}"}
            else:
                return {"score": 0.0, "details": f"Wrong: expected {expected}, got {numbers}"}
        except ValueError:
            return {"score": 0.0, "details": f"Invalid format: '{response}'"}
    
    def _score_level_3(self, response: str, expected: int) -> Dict[str, Any]:
        """Level 3: Number - expects '17'"""
        try:
            actual = int(response.strip())
            if actual == expected:
                return {"score": 1.0, "details": f"Correct: {actual}"}
            else:
                return {"score": 0.0, "details": f"Wrong: expected {expected}, got {actual}"}
        except ValueError:
            return {"score": 0.0, "details": f"Not a number: '{response}'"}
    
    def _score_level_4(self, response: str, expected: list) -> Dict[str, Any]:
        """Level 4: Statements - expects '2, 4'"""
        try:
            statements = [int(n.strip()) for n in response.split(',')]
            # Check if all expected statements are present
            if all(s in statements for s in expected):
                return {"score": 1.0, "details": f"Correct: statements {statements}"}
            else:
                return {"score": 0.0, "details": f"Wrong: expected {expected}, got {statements}"}
        except ValueError:
            return {"score": 0.0, "details": f"Invalid format: '{response}'"}
    
    def _score_level_5(self, response: str, expected: float) -> Dict[str, Any]:
        """Level 5: Currency - expects '820800'"""
        clean = response.strip()
        
        # Remove common separators and currency symbols
        clean = clean.replace(',', '').replace('.', '').replace('Rp', '').replace('rp', '').strip()
        
        try:
            actual = float(clean)
            if abs(actual - expected) < 1:  # Tolerance for currency
                return {"score": 1.0, "details": f"Correct: {actual}"}
            else:
                return {"score": 0.0, "details": f"Wrong: expected {expected}, got {actual}"}
        except ValueError:
            return {"score": 0.0, "details": f"Not a number: '{response}'"}
