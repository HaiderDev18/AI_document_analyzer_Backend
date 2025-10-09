"""
Table Extraction Service

Extracts tables from PDFs and converts them to searchable text format.
Handles checkboxes, tick marks, and structured data.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TableCell:
    """Represents a single table cell"""
    text: str
    row: int
    col: int
    is_checkbox: bool = False
    checkbox_state: Optional[str] = None  # 'checked', 'unchecked', None


@dataclass
class ExtractedTable:
    """Represents an extracted table with metadata"""
    headers: List[str]
    rows: List[List[str]]
    page_number: int
    table_index: int
    has_checkboxes: bool = False

    def to_text(self) -> str:
        """Convert table to readable text format"""
        if not self.headers or not self.rows:
            return ""

        # Create text representation
        lines = []
        lines.append(f"[Table {self.table_index + 1} from Page {self.page_number}]")

        # Headers
        header_line = " | ".join(self.headers)
        lines.append(header_line)
        lines.append("-" * len(header_line))

        # Rows
        for row in self.rows:
            row_line = " | ".join(str(cell) for cell in row)
            lines.append(row_line)

        return "\n".join(lines)

    def to_search_text(self) -> str:
        """Convert table to search-optimized text"""
        search_lines = []

        # Add searchable key-value pairs
        for row in self.rows:
            if len(row) >= 2:
                # Assume first column is key, rest are values
                key = str(row[0]).strip()
                values = [str(v).strip() for v in row[1:] if str(v).strip()]

                if key and values:
                    # Create searchable phrase
                    search_lines.append(f"{key}: {', '.join(values)}")

        return " | ".join(search_lines)


class TableExtractor:
    """
    Extract tables from PDFs using pdfplumber
    """

    # Checkbox/tick mark detection patterns
    CHECKBOX_PATTERNS = {
        'checked': ['✓', '✔', '☑', '✗', '×', 'x', 'X', 'Yes', 'YES', 'yes', 'Y', 'True'],
        'unchecked': ['☐', '□', 'No', 'NO', 'no', 'N', 'False', '-', ''],
    }

    def __init__(self):
        try:
            import pdfplumber
            self.pdfplumber = pdfplumber
            self.available = True
        except ImportError:
            self.pdfplumber = None
            self.available = False

    def detect_checkbox_state(self, cell_text: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if cell contains a checkbox and its state

        Returns:
            (is_checkbox, state) where state is 'checked', 'unchecked', or None
        """
        if not cell_text:
            return False, None

        cell_text = cell_text.strip()

        # Check for checked patterns
        for pattern in self.CHECKBOX_PATTERNS['checked']:
            if pattern in cell_text or cell_text == pattern:
                return True, 'checked'

        # Check for unchecked patterns
        for pattern in self.CHECKBOX_PATTERNS['unchecked']:
            if cell_text == pattern:
                return True, 'unchecked'

        return False, None

    def normalize_cell_value(self, cell_text: str) -> str:
        """
        Normalize cell value, converting checkboxes to readable text
        """
        if not cell_text:
            return ""

        is_checkbox, state = self.detect_checkbox_state(cell_text)

        if is_checkbox:
            if state == 'checked':
                return "Yes"
            elif state == 'unchecked':
                return "No"

        return cell_text.strip()

    def extract_tables_from_pdf(self, pdf_path: str) -> List[ExtractedTable]:
        """
        Extract all tables from a PDF file

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of ExtractedTable objects
        """
        if not self.available:
            print("pdfplumber not available for table extraction")
            return []

        extracted_tables = []

        try:
            with self.pdfplumber.open(pdf_path) as pdf:
                print(f"[Table Extractor] Processing {len(pdf.pages)} pages")
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extract tables from this page
                    tables = page.extract_tables()

                    if not tables:
                        print(f"  Page {page_num}: No tables found")
                        continue
                    else:
                        print(f"  Page {page_num}: Found {len(tables)} table(s)")

                    for table_idx, table in enumerate(tables):
                        if not table or len(table) < 2:  # Need at least header + 1 row
                            continue

                        # First row is typically headers
                        raw_headers = table[0]
                        raw_rows = table[1:]

                        # Normalize headers
                        headers = [self.normalize_cell_value(h) if h else f"Column_{i}"
                                  for i, h in enumerate(raw_headers)]

                        # Normalize rows and detect checkboxes
                        normalized_rows = []
                        has_checkboxes = False

                        for row in raw_rows:
                            if not row:
                                continue

                            normalized_row = []
                            for cell in row:
                                cell_text = cell if cell else ""
                                is_checkbox, state = self.detect_checkbox_state(cell_text)

                                if is_checkbox:
                                    has_checkboxes = True
                                    normalized_value = "Yes" if state == 'checked' else "No"
                                else:
                                    normalized_value = self.normalize_cell_value(cell_text)

                                normalized_row.append(normalized_value)

                            # Only add non-empty rows
                            if any(cell.strip() for cell in normalized_row):
                                normalized_rows.append(normalized_row)

                        if normalized_rows:
                            extracted_table = ExtractedTable(
                                headers=headers,
                                rows=normalized_rows,
                                page_number=page_num,
                                table_index=table_idx,
                                has_checkboxes=has_checkboxes
                            )
                            extracted_tables.append(extracted_table)

        except Exception as e:
            print(f"Error extracting tables from PDF: {e}")
            return []

        return extracted_tables

    def tables_to_searchable_text(self, tables: List[ExtractedTable]) -> str:
        """
        Convert extracted tables to searchable text format

        This creates a comprehensive text representation that:
        1. Is readable by humans
        2. Is searchable by semantic search
        3. Preserves table structure and relationships
        """
        if not tables:
            return ""

        sections = []

        for table in tables:
            # Add table as formatted text
            sections.append(table.to_text())
            sections.append("")  # Empty line separator

            # Add search-optimized key-value pairs
            search_text = table.to_search_text()
            if search_text:
                sections.append(f"[Table Data: {search_text}]")
                sections.append("")

        return "\n".join(sections)

    def extract_table_metadata(self, tables: List[ExtractedTable]) -> Dict[str, Any]:
        """
        Extract metadata about tables for semantic enrichment
        """
        if not tables:
            return {}

        metadata = {
            'has_tables': True,
            'table_count': len(tables),
            'tables_with_checkboxes': sum(1 for t in tables if t.has_checkboxes),
            'total_rows': sum(len(t.rows) for t in tables),
            'table_headers': []
        }

        # Collect all unique headers
        all_headers = set()
        for table in tables:
            all_headers.update(table.headers)

        metadata['table_headers'] = list(all_headers)

        return metadata


def extract_and_merge_tables_with_text(pdf_path: str, extracted_text: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extract tables and merge with existing text extraction

    Args:
        pdf_path: Path to PDF file
        extracted_text: Already extracted text from document

    Returns:
        (merged_text, table_metadata)
    """
    extractor = TableExtractor()

    if not extractor.available:
        return extracted_text, {'has_tables': False}

    # Extract tables
    tables = extractor.extract_tables_from_pdf(pdf_path)

    if not tables:
        return extracted_text, {'has_tables': False}

    # Convert tables to searchable text
    table_text = extractor.tables_to_searchable_text(tables)

    # Merge with extracted text
    # Strategy: Add tables at the end with clear markers
    merged_text = extracted_text.strip()

    if table_text:
        merged_text += "\n\n" + "="*50 + "\n"
        merged_text += "EXTRACTED TABLES\n"
        merged_text += "="*50 + "\n\n"
        merged_text += table_text

    # Get table metadata
    table_metadata = extractor.extract_table_metadata(tables)

    return merged_text, table_metadata


# Example usage
if __name__ == "__main__":
    # Test table extraction
    extractor = TableExtractor()

    # Simulate a table with checkboxes
    test_table = [
        ["Requirement", "Included", "Notes"],
        ["Public Liability Insurance", "✓", "Required"],
        ["Professional Indemnity", "✓", "£5M minimum"],
        ["Employers Liability", "✗", "Not applicable"],
        ["CAR Insurance", "Yes", "Specific requirement"],
    ]

    print("Testing checkbox detection:")
    for row in test_table[1:]:
        for cell in row:
            is_cb, state = extractor.detect_checkbox_state(cell)
            if is_cb:
                print(f"  '{cell}' -> Checkbox: {state}")
