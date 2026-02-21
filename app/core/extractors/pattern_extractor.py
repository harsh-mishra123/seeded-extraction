import re
import logging
from typing import Dict, List, Tuple, Optional
from app.core.extractors.base_extractor import BaseExtractor
from app.models.financial import (
    FinancialExtractionResult, IncomeStatementItem, 
    ExtractedValue, ConfidenceLevel, Currency, Unit
)

logger = logging.getLogger(__name__)

class PatternExtractor(BaseExtractor):
    """Extract financial data using regex patterns (fallback method)"""
    
    def __init__(self):
        # Patterns for different number formats
        self.number_patterns = [
            # $1,234.56 or $1.234,56
            r'\$?\s?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)',
            # (1,234) for negative numbers
            r'\((\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)\)',
            # -1,234
            r'-\s?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)',
            # 1.234,56 (European format)
            r'(\d{1,3}(?:\.\d{3})*,\d{2})'
        ]
        
        # Unit indicators
        self.unit_patterns = {
            'thousands': r'thousand|thousands|k|000\'s',
            'millions': r'million|millions|m|mn|mln',
            'billions': r'billion|billions|b|bn'
        }
        
        # Currency indicators
        self.currency_patterns = {
            'USD': r'\$|dollars?|usd',
            'EUR': r'€|euros?|eur',
            'GBP': r'£|pounds?|gbp',
            'JPY': r'¥|yen|jpy',
            'CNY': r'¥|yuan|cny|rmb'
        }
        
        # Year patterns
        self.year_pattern = r'20\d{2}|19\d{2}'
    
    def _debug_log_lines(self, lines: List[str]):
        """Debug: print first 20 lines to see what we're working with"""
        logger.info("=== First 20 lines of document ===")
        for i, line in enumerate(lines[:20]):
            logger.info(f"Line {i}: {line}")
        logger.info("=== End of first 20 lines ===")
    
    def _extract_simple_key_value(self, lines: List[str]) -> Tuple[Dict, Dict, List]:
        """Extract simple key: value pairs without years"""
        data = {"Current": {}}
        raw_extracts = {"Current": {}}
        warnings = []
        
        logger.info("Attempting simple key-value extraction")
        
        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            parts = line.split(':', 1)
            if len(parts) != 2:
                continue
            
            key = parts[0].strip()
            value_str = parts[1].strip()
            
            logger.info(f"Line {line_num}: Found key '{key}' with value '{value_str}'")
            
            # Try to parse number
            try:
                # Remove any non-numeric characters except . and -
                value_str_clean = re.sub(r'[^\d.-]', '', value_str)
                if not value_str_clean:
                    continue
                    
                value = float(value_str_clean)
                
                # Try to map to standard item
                standard_item = self._normalize_line_item(key)
                
                if standard_item:
                    data["Current"][standard_item] = ExtractedValue(
                        value=value,
                        confidence=ConfidenceLevel.HIGH,
                        original_text=line
                    )
                    raw_extracts["Current"][standard_item.value] = line
                    logger.info(f"✅ Extracted {standard_item.value}: {value}")
                else:
                    logger.info(f"❌ Could not map '{key}' to standard item")
            except ValueError as e:
                logger.info(f"❌ Could not parse number from '{value_str}': {e}")
                continue
        
        logger.info(f"Simple extraction found {len(data['Current'])} items")
        return data, raw_extracts, warnings
        
    async def extract(self, text: str) -> FinancialExtractionResult:
        """Extract financial data using pattern matching"""
        
        # Split into lines and debug
        lines = text.split('\n')
        self._debug_log_lines(lines)
        
        # Try to detect years
        years = self._extract_years_from_table(lines)
        if not years:
            years = self._extract_years(text)
        
        # Detect currency and units
        currency = self._detect_currency(text)
        unit = self._detect_unit(text)
        
        logger.info(f"Found years: {years}")
        logger.info(f"Detected currency: {currency}, unit: {unit}")
        
        data = {}
        raw_extracts = {}
        warnings = []
        
        # Try different extraction methods in order
        if years and len(years) >= 2:
            # Try table-based extraction first
            data, raw_extracts, warnings = self._extract_from_table(lines, years)
            
            # If table extraction didn't work, try line-by-line with years
            if not data or all(len(data.get(year, {})) == 0 for year in years):
                logger.info("Table extraction found no data, trying line-by-line with years")
                data, raw_extracts, warnings = self._extract_line_by_line(text, years)
        
        # If still no data or no years, try simple key-value extraction
        if not data or all(len(data.get(year, {})) == 0 for year in (years or ["Current"])):
            logger.info("Previous methods found no data, trying simple key-value")
            data, raw_extracts, warnings = self._extract_simple_key_value(lines)
        
        # Determine missing items
        all_items = set(IncomeStatementItem)
        found_items = set()
        for year_data in data.values():
            found_items.update(year_data.keys())
        missing_items = list(all_items - found_items)
        
        if missing_items:
            warnings.append(f"Missing items: {', '.join([i.value for i in missing_items])}")
        
        logger.info(f"Extraction complete. Found {len(found_items)} line items across {len(data)} years")
        
        return FinancialExtractionResult(
            document_name="Pattern_Extracted",
            extraction_date="",
            currency=currency,
            unit=unit,
            confidence_overall=ConfidenceLevel.MEDIUM if data else ConfidenceLevel.LOW,
            data=data,
            warnings=warnings,
            missing_items=missing_items,
            raw_extracts=raw_extracts
        )
    
    def _extract_years_from_table(self, lines: List[str]) -> List[str]:
        """Extract years from table headers"""
        years = []
        year_pattern = r'(20\d{2})\s+(20\d{2})'
        
        for line in lines:
            match = re.search(year_pattern, line)
            if match:
                years = [match.group(1), match.group(2)]
                logger.info(f"Found years in table header: {years}")
                break
        
        return years
    
    def _extract_from_table(self, lines: List[str], years: List[str]) -> Tuple[Dict, Dict, List]:
        """Extract data from table format"""
        data = {year: {} for year in years}
        raw_extracts = {year: {} for year in years}
        warnings = []
        
        if not years or len(years) < 2:
            logger.info("No years found for table extraction")
            return {}, {}, ["No years found in table"]
        
        logger.info(f"Attempting table extraction with years: {years}")
        
        # Find where the table starts (line containing both years)
        start_idx = 0
        for i, line in enumerate(lines):
            if all(str(year) in line for year in years):
                start_idx = i + 1
                logger.info(f"Table starts at line {start_idx}")
                break
        
        # Process each line after the header
        for line_num in range(start_idx, len(lines)):
            line = lines[line_num].strip()
            if not line or len(line) < 5:
                continue
            
            # Skip lines that are just headers
            if any(x in line.lower() for x in ['consolidated', 'statement', 'in millions', 'except per share']):
                continue
            
            # Pattern for lines with two numbers: text then $123.4 $567.8
            # This handles the format in complete_financial.txt
            pattern = r'^([A-Za-z\s,]+?)\s+\$?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)\s+\$?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)$'
            match = re.search(pattern, line)
            
            if not match:
                # Try pattern for indented lines (like Research and development)
                pattern = r'^\s+([A-Za-z\s,]+?)\s+\$?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)\s+\$?(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?)$'
                match = re.search(pattern, line)
            
            if match:
                item_name = match.group(1).strip()
                val1 = self._parse_number(match.group(2))
                val2 = self._parse_number(match.group(3))
                
                logger.info(f"Line {line_num}: Found item '{item_name}' with values {val1}, {val2}")
                
                # Try to map to standard line item
                standard_item = self._normalize_line_item(item_name)
                
                if standard_item:
                    logger.info(f"Mapped '{item_name}' to {standard_item.value}")
                    # Note: years[1] is 2023, years[0] is 2022 (based on your file)
                    data[years[1]][standard_item] = ExtractedValue(
                        value=val1,
                        confidence=ConfidenceLevel.HIGH,
                        original_text=line
                    )
                    data[years[0]][standard_item] = ExtractedValue(
                        value=val2,
                        confidence=ConfidenceLevel.HIGH,
                        original_text=line
                    )
                    raw_extracts[years[1]][standard_item.value] = line
                    raw_extracts[years[0]][standard_item.value] = line
        
        # Count how many items were found
        total_found = sum(len(year_data) for year_data in data.values())
        logger.info(f"Table extraction found {total_found} items")
        
        return data, raw_extracts, warnings
    
    def _extract_line_by_line(self, text: str, years: List[str]) -> Tuple[Dict, Dict, List]:
        """Fallback: extract data line by line"""
        data = {}
        raw_extracts = {}
        warnings = []
        
        for year in years:
            year_data, year_raw = self._extract_for_year(text, year)
            if year_data:
                data[year] = year_data
                raw_extracts[year] = year_raw
                logger.info(f"Found {len(year_data)} items for year {year}")
        
        return data, raw_extracts, warnings
    
    def _detect_currency(self, text: str) -> Currency:
        """Detect currency from text"""
        text_lower = text.lower()
        for currency, pattern in self.currency_patterns.items():
            if re.search(pattern, text_lower):
                return Currency(currency)
        return Currency.UNKNOWN
    
    def _detect_unit(self, text: str) -> Unit:
        """Detect unit (thousands/millions/billions) from text"""
        text_lower = text.lower()
        for unit, pattern in self.unit_patterns.items():
            if re.search(pattern, text_lower):
                return Unit(unit)
        return Unit.UNKNOWN
    
    def _extract_years(self, text: str) -> List[str]:
        """Extract all years mentioned in the text"""
        years = re.findall(self.year_pattern, text)
        # Remove duplicates and sort
        return sorted(list(set(years)))
    
    def _extract_for_year(self, text: str, year: str) -> Tuple[Dict, Dict]:
        """Extract all line items for a specific year"""
        data = {}
        raw = {}
        
        # Find context around the year
        year_context = self._get_year_context(text, year)
        
        # Try to extract each line item
        for item in IncomeStatementItem:
            value, confidence, original_text = self._extract_line_item(year_context, item, year)
            if value is not None:
                data[item] = ExtractedValue(
                    value=value,
                    original_text=original_text,
                    confidence=confidence,
                    notes=None
                )
                raw[item.value] = original_text
        
        return data, raw
    
    def _get_year_context(self, text: str, year: str, context_lines: int = 5) -> str:
        """Get lines around the year for context"""
        lines = text.split('\n')
        year_lines = []
        
        for i, line in enumerate(lines):
            if year in line:
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                year_lines.extend(lines[start:end])
        
        return '\n'.join(year_lines)
    
    def _extract_line_item(self, context: str, item: IncomeStatementItem, year: str) -> Tuple[Optional[float], ConfidenceLevel, Optional[str]]:
        """Extract a specific line item value for a given year"""
        
        # Common variations of the line item
        item_variations = self._get_item_variations(item)
        
        for variation in item_variations:
            # Look for patterns like "Revenue: 1,234" or "Revenue 1,234"
            pattern = rf'{variation}.*?(\d{{1,3}}(?:[,\s]\d{{3}})*(?:\.\d{{2}})?)'
            match = re.search(pattern, context, re.IGNORECASE)
            
            if match:
                value_str = match.group(1)
                value = self._parse_number(value_str)
                
                # Check if this is for our target year
                surrounding_text = context[max(0, match.start()-50):min(len(context), match.end()+50)]
                if year in surrounding_text or self._is_recent_year(surrounding_text):
                    return value, ConfidenceLevel.HIGH, match.group(0)
        
        return None, ConfidenceLevel.MISSING, None
    
    def _get_item_variations(self, item: IncomeStatementItem) -> List[str]:
        """Get common variations of line item names"""
        variations = {
            IncomeStatementItem.REVENUE: ['revenue', 'sales', 'total revenue', 'operating revenue'],
            IncomeStatementItem.COST_OF_REVENUE: ['cost of revenue', 'cost of sales', 'cost of goods sold', 'cogs'],
            IncomeStatementItem.GROSS_PROFIT: ['gross profit', 'gross margin'],
            IncomeStatementItem.OPERATING_EXPENSES: ['operating expenses', 'opex', 'operating costs', 'total operating expenses', 'expenses'],
            IncomeStatementItem.RND: ['research and development', 'r&d', 'research & development', 'research and development expenses'],
            IncomeStatementItem.SGNA: ['selling, general and administrative', 'sg&a', 'selling, general & administrative', 'selling general and admin', 'selling general and administrative'],
            IncomeStatementItem.OPERATING_INCOME: ['operating income', 'operating profit', 'income from operations'],
            IncomeStatementItem.INTEREST_EXPENSE: ['interest expense', 'interest', 'finance costs'],
            IncomeStatementItem.INCOME_TAX: ['income tax', 'tax expense', 'provision for income taxes', 'income tax expense'],
            IncomeStatementItem.NET_INCOME: ['net income', 'net profit', 'net earnings', 'bottom line'],
            IncomeStatementItem.EBITDA: ['ebitda', 'earnings before interest'],
        }
        return variations.get(item, [item.value.lower()])
    
    def _parse_number(self, number_str: str) -> Optional[float]:
        """Parse number string to float, handling different formats"""
        try:
            # Remove spaces and commas
            number_str = number_str.replace(',', '').replace(' ', '')
            
            # Handle parentheses for negative numbers
            if number_str.startswith('(') and number_str.endswith(')'):
                number_str = '-' + number_str[1:-1]
            
            # Handle European format (1.234,56 -> 1234.56)
            if '.' in number_str and ',' in number_str:
                if number_str.index('.') < number_str.index(','):
                    number_str = number_str.replace('.', '').replace(',', '.')
            
            return float(number_str)
        except ValueError:
            return None
    
    def _is_recent_year(self, text: str) -> bool:
        """Check if text contains a recent year (2020-2025)"""
        years = re.findall(self.year_pattern, text)
        recent_years = [y for y in years if 2020 <= int(y) <= 2025]
        return len(recent_years) > 0