"""
Document text extraction utility supporting PDF, DOCX, XLSX, and XLS formats.
Uses PyMuPDF (fitz), python-docx, openpyxl, and xlrd.
"""

import os
from pathlib import Path
from typing import Tuple, Dict, Any, List
import pandas as pd


def extract_text_from_pdf(file_path: str) -> str:
    """Extracts all text content across pages from a PDF file using PyMuPDF."""
    import pymupdf

    doc = pymupdf.open(file_path)
    text_parts = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text("text")
        if page_text.strip():
            text_parts.append(f"--- Page {page_num + 1} ---\n" + page_text.strip())

    doc.close()
    return "\n\n".join(text_parts).strip()


def extract_text_from_docx(file_path: str) -> str:
    """Extracts text paragraphs and table cells from a DOCX file using python-docx."""
    import docx

    doc = docx.Document(file_path)
    text_parts = []

    # Extract paragraphs
    for p in doc.paragraphs:
        if p.text.strip():
            text_parts.append(p.text.strip())

    # Extract tables
    for t_idx, table in enumerate(doc.tables):
        table_lines = [f"\n[Table {t_idx + 1}]"]
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                # Remove duplicate adjacent texts resulting from merged cells
                cleaned_cells = []
                for c in row_cells:
                    if not cleaned_cells or c != cleaned_cells[-1]:
                        cleaned_cells.append(c)
                table_lines.append(" | ".join(cleaned_cells))
        if len(table_lines) > 1:
            text_parts.append("\n".join(table_lines))

    return "\n\n".join(text_parts).strip()


def extract_text_from_excel(file_path: str) -> str:
    """Extracts tabular data from XLSX or XLS spreadsheets using pandas/openpyxl/xlrd."""
    ext = os.path.splitext(file_path)[1].lower()
    engine = "openpyxl" if ext == ".xlsx" else "xlrd"
    
    excel_file = pd.ExcelFile(file_path, engine=engine)
    sheet_texts = []

    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        # Drop rows and columns that are entirely NaN
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if not df.empty:
            sheet_header = f"=== Sheet: {sheet_name} ==="
            # Convert to formatted string representation
            records_str = df.to_string(index=False)
            sheet_texts.append(f"{sheet_header}\n{records_str}")

    return "\n\n".join(sheet_texts).strip()


def extract_document_text(file_path: str) -> Tuple[bool, str, str]:
    """
    Master function to extract readable text from a supported document.
    
    Supported extensions: .pdf, .docx, .xlsx, .xls
    
    Returns:
        (success: bool, extracted_text: str, message: str)
    """
    if not os.path.exists(file_path):
        return False, "", f"File does not exist at path: {file_path}"

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return False, "", "File is empty (0 bytes)."

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == ".pdf":
            text = extract_text_from_pdf(file_path)
            parser = "PyMuPDF"
        elif ext in [".docx", ".doc"]:
            if ext == ".doc":
                return False, "", "Legacy .doc format is not directly supported. Please convert to .docx."
            text = extract_text_from_docx(file_path)
            parser = "python-docx"
        elif ext in [".xlsx", ".xls"]:
            text = extract_text_from_excel(file_path)
            parser = "openpyxl/xlrd"
        else:
            return False, "", f"Unsupported file extension '{ext}'. Supported: PDF, DOCX, XLSX, XLS."

        if not text.strip():
            return True, "", f"Document was parsed with {parser}, but no readable text was found."

        return True, text.strip(), f"Successfully extracted text using {parser} ({len(text)} characters)."

    except Exception as e:
        return False, "", f"Extraction failed ({ext}): {str(e)}"
