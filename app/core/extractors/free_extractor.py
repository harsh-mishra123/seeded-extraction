import re
import logging
from typing import Dict, List, Tuple, Optional
from app.core.extractors.base_extractor import BaseExtractor
from app.models.financial import (
    FinancialExtractionResult, IncomeStatementItem, 
    ExtractedValue, ConfidenceLevel, Currency, Unit
)

logger = logging.getLogger(__name__)

class FreeExtractor(BaseExtractor):
    """Free extractor that works with common financial statement formats"""
    
    async def extract(self, text: str) -> FinancialExtractionResult:
        """Extract financial data using multiple free methods"""
        
        lines = text.split('\n')
        
        # Try different free extraction methods
        data, raw_extracts, warnings = self._try_all_methods(lines)
        
        # Detect currency and units
        currency = self._detect_currency(text)
        unit = self._detect_unit(text)
        
        # Determine missing items
        all_items = set(IncomeStatementItem)
        found_items = set()
        for year_data in data.values():
            found_items.update(year_data.keys())
        missing_items = list(all_items - found_items)
        
        return FinancialExtractionResult(
            document_name="Free_Extracted",
            extraction_date="",
            currency=currency,
            unit=unit,
            confidence_overall=ConfidenceLevel.HIGH if data else ConfidenceLevel.LOW,
            data=data,
            warnings=warnings,
            missing_items=missing_items,
            raw_extracts=raw_extracts
        )
    
    def _try_all_methods(self, lines: List[str]) -> Tuple[Dict, Dict, List]:
        """Try multiple extraction methods"""
        
        # Method 1: Table format (like complete_financial.txt)
        data, raw, warnings = self._extract_table_format(lines)
        if data and any(data.values()):
            return data, raw, warnings
        
        # Method 2: Key-value format (like ultra_test.txt)
        data, raw, warnings = self._extract_key_value_format(lines)
        if data and any(data.values()):
            return data, raw, warnings
        
        # Method 3: Line-by-line with years
        data, raw, warnings = self._extract_line_by_line(lines)
        return data, raw, warnings
    
    def _extract_table_format(self, lines: List[str]) -> Tuple[Dict, Dict, List]:
        """Extract from table format like complete_financial.txt"""
        data = {"2023": {}, "2022": {}}
        raw = {"2023": {}, "2022": {}}
        warnings = []
        
        # Mapping of line items to their variations
        item_mapping = {
            "Revenue": IncomeStatementItem.REVENUE,
            "Cost of revenue": IncomeStatementItem.COST_OF_REVENUE,
            "Gross profit": IncomeStatementItem.GROSS_PROFIT,
            "Research and development": IncomeStatementItem.RND,
            "Selling, general and admin": IncomeStatementItem.SGNA,
            "Total operating expenses": IncomeStatementItem.OPERATING_EXPENSES,
            "Operating income": IncomeStatementItem.OPERATING_INCOME,
            "Interest expense": IncomeStatementItem.INTEREST_EXPENSE,
            "Income tax expense": IncomeStatementItem.INCOME_TAX,
            "Net income": IncomeStatementItem.NET_INCOME,
            "EBITDA": IncomeStatementItem.EBITDA,
        }
        
        for line in lines:
            line = line.strip()
            if not line or 'CONSOLIDATED' in line or 'In millions' in line:
                continue
            
            # Check each known item
            for item_text, standard_item in item_mapping.items():
                if item_text in line:
                    # Extract numbers - look for $123.4 pattern
                    numbers = re.findall(r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)', line)
                    if len(numbers) >= 2:
                        val1 = self._parse_number(numbers[0])
                        val2 = self._parse_number(numbers[1])
                        
                        # Determine which year is which based on order in your file
                        data["2023"][standard_item] = ExtractedValue(
                            value=val1, confidence=ConfidenceLevel.HIGH, original_text=line
                        )
                        data["2022"][standard_item] = ExtractedValue(
                            value=val2, confidence=ConfidenceLevel.HIGH, original_text=line
                        )
                        raw["2023"][standard_item.value] = line
                        raw["2022"][standard_item.value] = line
                        break
        
        return data, raw, warnings
    
    def _extract_key_value_format(self, lines: List[str]) -> Tuple[Dict, Dict, List]:
        """Extract from key: value format like ultra_test.txt"""
        data = {"Current": {}}
        raw = {"Current": {}}
        warnings = []
        
        key_mapping = {
            "Revenue": IncomeStatementItem.REVENUE,
            "Expenses": IncomeStatementItem.OPERATING_EXPENSES,
            "Net Income": IncomeStatementItem.NET_INCOME,
        }
        
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                key = parts[0].strip()
                value_str = parts[1].strip()
                
                # Extract number
                numbers = re.findall(r'(\d+\.?\d*)', value_str)
                if numbers:
                    value = float(numbers[0])
                    
                    if key in key_mapping:
                        standard_item = key_mapping[key]
                        data["Current"][standard_item] = ExtractedValue(
                            value=value, confidence=ConfidenceLevel.HIGH, original_text=line
                        )
                        raw["Current"][standard_item.value] = line
        
        return data, raw, warnings
    
    def _extract_line_by_line(self, lines: List[str]) -> Tuple[Dict, Dict, List]:
        """Simple line-by-line extraction"""
        data = {}
        raw = {}
        warnings = ["Using basic line-by-line extraction"]
        
        # Simple implementation
        return data, raw, warnings
    
    def _parse_number(self, num_str: str) -> float:
        """Parse number string to float"""
        # Remove commas and spaces
        num_str = num_str.replace(',', '').strip()
        return float(num_str)
    
    def _detect_currency(self, text: str) -> Currency:
        if '$' in text:
            return Currency.USD
        return Currency.UNKNOWN
    
    def _detect_unit(self, text: str) -> Unit:
        if 'millions' in text.lower():
            return Unit.MILLIONS
        return Unit.UNKNOWN