from app.services.excel_loader import destinations, load_workbook_rows, rag_documents

ALL_SHEETS = load_workbook_rows()
DESTINATIONS = destinations()
RAG_DOCUMENTS = rag_documents()
WORKBOOK = bool(ALL_SHEETS)
