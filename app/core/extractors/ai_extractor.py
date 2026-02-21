import openai
import json
from typing import Optional, Dict, Any, List
from app.core.extractors.base_extractor import BaseExtractor
from app.models.financial import (
    FinancialExtractionResult, IncomeStatementItem, 
    ExtractedValue, ConfidenceLevel, Currency, Unit
)
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class AIExtractor(BaseExtractor):
    """Extract financial data using LLM"""
    
    def __init__(self):
        # Initialize the OpenAI client (new syntax)
        if settings.openai_api_key:
            self.client = openai.OpenAI(api_key=settings.openai_api_key)
        else:
            self.client = openai.OpenAI()  # Will use OPENAI_API_KEY from env
            logger.warning("Using OpenAI API key from environment")
    
    async def extract(self, text: str) -> FinancialExtractionResult:
        """Use AI to extract structured financial data"""
        
        # Truncate text if too long (GPT-4 context limit)
        max_chars = 100000  # Adjust based on token limits
        if len(text) > max_chars:
            text = text[:max_chars]
            logger.warning(f"Text truncated to {max_chars} characters")
        
        prompt = self._create_extraction_prompt(text)
        
        try:
            # New OpenAI API syntax
            response = self.client.chat.completions.create(
                model=settings.ai_model or "gpt-4",
                messages=[
                    {"role": "system", "content": "You are a financial analyst expert at extracting structured data from financial documents. Extract the requested information with high precision."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return self._parse_ai_response(result)
            
        except Exception as e:
            logger.error(f"AI extraction failed: {str(e)}")
            # Fallback to pattern matching
            from app.core.extractors.pattern_extractor import PatternExtractor
            pattern_extractor = PatternExtractor()
            return await pattern_extractor.extract(text)
    
    def _create_extraction_prompt(self, text: str) -> str:
        """Create prompt for AI extraction"""
        items = [item.value for item in IncomeStatementItem]
        
        return f"""
        Extract the following income statement items from the financial document text below.
        
        Required items: {', '.join(items)}
        
        For each item, extract values for ALL available years. Look for numbers in tables or text.
        
        Return a JSON object with this structure:
        {{
            "metadata": {{
                "currency": "USD or EUR or GBP etc (infer from context, use UNKNOWN if can't determine)",
                "unit": "thousands or millions or billions or actual (infer from context)",
                "confidence_overall": "high or medium or low"
            }},
            "data": {{
                "2023": {{
                    "Revenue": {{"value": 1234.5, "confidence": "high", "original_text": "Revenue $1,234.5M"}},
                    "Operating Expenses": {{"value": 234.5, "confidence": "medium", "original_text": "OpEx 234.5M"}}
                }},
                "2022": {{
                    "Revenue": {{"value": 1100.2, "confidence": "high", "original_text": "Revenue 1,100.2M"}}
                }}
            }},
            "warnings": ["Missing data for R&D in 2022"],
            "raw_extracts": {{
                "2023": {{
                    "Revenue": "Revenue for the year ended December 31, 2023 was $1,234.5 million",
                    "Operating Expenses": "Operating expenses were $234.5 million"
                }}
            }}
        }}
        
        Important guidelines:
        1. If a value is not found, omit it from the data object
        2. Extract numbers as floats (remove commas, handle parentheses for negatives)
        3. Note the unit (thousands/millions) and convert to actual numbers if specified
        4. If you're uncertain about a value, set confidence to "low" and add a note
        5. Preserve original text snippets for reference
        
        Document text:
        {text}
        """
    
    def _parse_ai_response(self, response: Dict) -> FinancialExtractionResult:
        """Parse and validate AI response"""
        metadata = response.get("metadata", {})
        
        # Determine missing items
        all_items = set(IncomeStatementItem)
        found_items = set()
        data = response.get("data", {})
        for year_data in data.values():
            found_items.update([IncomeStatementItem(k) for k in year_data.keys() if k in [item.value for item in IncomeStatementItem]])
        
        missing_items = list(all_items - found_items)
        
        # Create result object
        result = FinancialExtractionResult(
            document_name="AI_Extracted",
            extraction_date="",  # Will be filled by processor
            currency=Currency(metadata.get("currency", "UNKNOWN")),
            unit=Unit(metadata.get("unit", "UNKNOWN")),
            confidence_overall=ConfidenceLevel(metadata.get("confidence_overall", "medium")),
            data={},
            warnings=response.get("warnings", []),
            missing_items=missing_items,
            raw_extracts=response.get("raw_extracts", {})
        )
        
        # Parse and validate data
        for year, items in response.get("data", {}).items():
            result.data[year] = {}
            for item_name, value_data in items.items():
                try:
                    # Find matching enum
                    item = None
                    for enum_item in IncomeStatementItem:
                        if enum_item.value.lower() in item_name.lower() or item_name.lower() in enum_item.value.lower():
                            item = enum_item
                            break
                    
                    if item:
                        result.data[year][item] = ExtractedValue(
                            value=float(value_data.get("value")) if value_data.get("value") else None,
                            original_text=value_data.get("original_text"),
                            confidence=ConfidenceLevel(value_data.get("confidence", "medium")),
                            notes=value_data.get("notes")
                        )
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse {item_name}: {str(e)}")
        
        return result