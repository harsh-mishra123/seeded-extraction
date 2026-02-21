from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from app.models.financial import FinancialExtractionResult, IncomeStatementItem

class BaseExtractor(ABC):
    """Base class for all extractors"""
    
    @abstractmethod
    async def extract(self, text: str) -> FinancialExtractionResult:
        """Extract financial data from text"""
        pass
    
    def _normalize_line_item(self, text: str) -> Optional[IncomeStatementItem]:
        """Map various phrasings to standard line items"""
        text_lower = text.lower().strip()
        
        # Mapping dictionary for common variations
        mappings = {
            "revenue": IncomeStatementItem.REVENUE,
            "sales": IncomeStatementItem.REVENUE,
            "total revenue": IncomeStatementItem.REVENUE,
            "operating revenue": IncomeStatementItem.REVENUE,
            
            "cost of revenue": IncomeStatementItem.COST_OF_REVENUE,
            "cost of sales": IncomeStatementItem.COST_OF_REVENUE,
            "cost of goods sold": IncomeStatementItem.COST_OF_REVENUE,
            "cogs": IncomeStatementItem.COST_OF_REVENUE,
            
            "gross profit": IncomeStatementItem.GROSS_PROFIT,
            "gross margin": IncomeStatementItem.GROSS_PROFIT,
            
            "operating expenses": IncomeStatementItem.OPERATING_EXPENSES,
            "opex": IncomeStatementItem.OPERATING_EXPENSES,
            "total operating expenses": IncomeStatementItem.OPERATING_EXPENSES,
            "expenses": IncomeStatementItem.OPERATING_EXPENSES,
            
            "research and development": IncomeStatementItem.RND,
            "r&d": IncomeStatementItem.RND,
            "research & development": IncomeStatementItem.RND,
            "research and development expenses": IncomeStatementItem.RND,
            
            "selling general and administrative": IncomeStatementItem.SGNA,
            "sg&a": IncomeStatementItem.SGNA,
            "selling, general & administrative": IncomeStatementItem.SGNA,
            "selling, general and administrative": IncomeStatementItem.SGNA,
            "selling general and admin": IncomeStatementItem.SGNA,
            
            "operating income": IncomeStatementItem.OPERATING_INCOME,
            "operating profit": IncomeStatementItem.OPERATING_INCOME,
            "income from operations": IncomeStatementItem.OPERATING_INCOME,
            
            "interest expense": IncomeStatementItem.INTEREST_EXPENSE,
            "interest": IncomeStatementItem.INTEREST_EXPENSE,
            "finance costs": IncomeStatementItem.INTEREST_EXPENSE,
            
            "income tax": IncomeStatementItem.INCOME_TAX,
            "tax expense": IncomeStatementItem.INCOME_TAX,
            "provision for income taxes": IncomeStatementItem.INCOME_TAX,
            "income tax expense": IncomeStatementItem.INCOME_TAX,
            
            "net income": IncomeStatementItem.NET_INCOME,
            "net profit": IncomeStatementItem.NET_INCOME,
            "net earnings": IncomeStatementItem.NET_INCOME,
            "bottom line": IncomeStatementItem.NET_INCOME,
            
            "ebitda": IncomeStatementItem.EBITDA,
            "earnings before interest": IncomeStatementItem.EBITDA,
            "ebitda": IncomeStatementItem.EBITDA,
        }
        
        # Check for exact matches first
        for key, value in mappings.items():
            if key in text_lower:
                return value
        
        # Check for partial matches (e.g., "R&D" in text)
        if "r&d" in text_lower or "research" in text_lower:
            return IncomeStatementItem.RND
        if "sg&a" in text_lower or "selling" in text_lower:
            return IncomeStatementItem.SGNA
        
        return None