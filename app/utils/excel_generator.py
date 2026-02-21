import pandas as pd
import logging
from app.models.financial import FinancialExtractionResult, IncomeStatementItem

logger = logging.getLogger(__name__)

class ExcelGenerator:
    def __init__(self):
        pass
    
    def generate(self, result: FinancialExtractionResult, output_path: str):
        """Simplified Excel generator - no formatting to avoid errors"""
        try:
            # Create a simple Excel file
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                
                # SHEET 1: Financial Data
                data_rows = []
                years = sorted(result.data.keys())
                
                # Header row
                header = ['Line Item']
                for year in years:
                    header.append(str(year))
                data_rows.append(header)
                
                # Data rows
                for item in IncomeStatementItem:
                    row = [item.value]
                    for year in years:
                        if year in result.data and item in result.data[year]:
                            value_obj = result.data[year][item]
                            row.append(value_obj.value if value_obj.value else 'N/A')
                        else:
                            row.append('N/A')
                    data_rows.append(row)
                
                df1 = pd.DataFrame(data_rows[1:], columns=data_rows[0])
                df1.to_excel(writer, sheet_name='Financial Data', index=False)
                
                # SHEET 2: Metadata
                metadata = {
                    'Property': ['Document Name', 'Extraction Date', 'Currency', 'Unit', 'Status'],
                    'Value': [
                        result.document_name,
                        result.extraction_date,
                        result.currency.value if result.currency else 'Unknown',
                        result.unit.value if result.unit else 'Unknown',
                        'Success'
                    ]
                }
                df2 = pd.DataFrame(metadata)
                df2.to_excel(writer, sheet_name='Metadata', index=False)
                
                # SHEET 3: Missing Items
                if result.missing_items:
                    missing_data = {
                        'Missing Line Items': [item.value for item in result.missing_items]
                    }
                    df3 = pd.DataFrame(missing_data)
                    df3.to_excel(writer, sheet_name='Missing Items', index=False)
            
            logger.info(f"✅ Excel file created successfully: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create Excel file: {str(e)}")
            # Create a simple error report as fallback
            try:
                with open(output_path.replace('.xlsx', '_error.txt'), 'w') as f:
                    f.write(f"Error creating Excel: {str(e)}\n")
                    f.write(f"Document: {result.document_name}\n")
            except:
                pass
            return False
