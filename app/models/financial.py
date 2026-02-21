from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from enum import Enum

class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CNY = "CNY"
    UNKNOWN = "UNKNOWN"

class Unit(str, Enum):
    THOUSANDS = "thousands"
    MILLIONS = "millions"
    BILLIONS = "billions"
    ACTUAL = "actual"
    UNKNOWN = "UNKNOWN"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MISSING = "missing"

class ExtractedValue(BaseModel):
    value: Optional[float] = None
    original_text: Optional[str] = None
    confidence: ConfidenceLevel
    notes: Optional[str] = None

class IncomeStatementItem(str, Enum):
    REVENUE = "Revenue"
    COST_OF_REVENUE = "Cost of Revenue"
    GROSS_PROFIT = "Gross Profit"
    OPERATING_EXPENSES = "Operating Expenses"
    RND = "Research & Development"
    SGNA = "Selling, General & Administrative"
    OPERATING_INCOME = "Operating Income"
    INTEREST_EXPENSE = "Interest Expense"
    INCOME_TAX = "Income Tax"
    NET_INCOME = "Net Income"
    EBITDA = "EBITDA"

class FinancialExtractionResult(BaseModel):
    # Metadata
    document_name: str
    extraction_date: str
    currency: Currency
    unit: Unit
    confidence_overall: ConfidenceLevel
    
    # Extracted data structure for multiple years
    data: Dict[str, Dict[IncomeStatementItem, ExtractedValue]]
    
    # Warnings and notes
    warnings: List[str] = []
    missing_items: List[IncomeStatementItem] = []
    
    # Raw extracted text snippets for reference
    raw_extracts: Dict[str, Dict[str, str]] = Field(default_factory=dict)