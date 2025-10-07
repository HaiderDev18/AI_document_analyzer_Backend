from typing import Optional, Tuple
from django.conf import settings
import os
import re

try:
    import pdfplumber  # type: ignore
except Exception:
    pdfplumber = None

# from llama_index.core import SimpleDirectoryReader
from llama_parse import LlamaParse

from dotenv import load_dotenv


# Load environment variables
load_dotenv()


def _clean_text(text: str) -> str:
    """
    Normalize PDF artifacts while PRESERVING document structure.

    KEY CHANGES:
    - Keep section headers separated
    - Preserve paragraph boundaries
    - Don't merge everything into one giant blob
    """
    # Remove page headers/footers
    text = re.sub(
        r"\n?\s*Page\s+\d+(\s+of\s+\d+)?\s*\n", "\n", text, flags=re.IGNORECASE
    )

    # Fix broken section numbers like "6.\n0 RETENTION" -> "6.0 RETENTION"
    text = re.sub(r"(\d)\.\s*\n\s*(\d)", r"\1.\2", text)

    # Normalize excessive spaces (but keep single spaces)
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Collapse excessive blank lines (3+ becomes 2)
    text = re.sub(r"\n{3,}", "\n\n", text)


    lines = text.split("\n")
    cleaned_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            # Keep empty lines (paragraph boundaries)
            cleaned_lines.append("")
            continue

        # Check if this looks like a section header (number + uppercase)
        is_header = bool(re.match(r"^\d+\.\d*\s+[A-Z]", stripped))

        # Check if previous line ended mid-word or mid-sentence
        if (
            cleaned_lines
            and cleaned_lines[-1]
            and not is_header
            and not re.search(
                r"[.!?:]\s*$", cleaned_lines[-1]
            )  # doesn't end with punctuation
            and stripped[0].islower()
        ):  # continues with lowercase
            # This is a line wrap - merge with previous
            cleaned_lines[-1] += " " + stripped
        else:
            # Keep as separate line
            cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines).strip()


def extract_text_from_files(file_paths, result_type="text"):
    """
    Extract text with BETTER structure preservation for legal/financial docs.
    """
    if not file_paths:
        return ""

    file_path = file_paths[0]
    _, ext = os.path.splitext(file_path.lower())

    # For PDFs, use pdfplumber with layout=True for better structure
    if ext == ".pdf" and pdfplumber is not None:
        text_blocks = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Extract with layout to preserve positioning
                    page_text = page.extract_text(layout=True) or ""

                    if page_text:
                        # Add page marker for debugging (optional)
                        # text_blocks.append(f"\n--- Page {page_num} ---\n")
                        text_blocks.append(page_text)
        except Exception as e:
            print(f"pdfplumber failed: {e}, falling back to LlamaParse")
            text_blocks = []

        if text_blocks:
            raw_text = "\n\n".join(text_blocks)
            return _clean_text(raw_text)

    # Fallback: LlamaParse
    parser = LlamaParse(result_type=result_type, auto_mode=True)
    result = parser.parse(file_path)
    text_documents = result.get_text_documents(split_by_page=False)
    text = "\n\n".join([doc.text for doc in text_documents])
    return _clean_text(text)


class DocumentProcessor:
    """
    Service class for processing documents and extracting text.
    """

    @classmethod
    def extract_text(cls, file_content: bytes, file_type: str) -> str:
        """
        Extract text based on file type.
        """
        file_type = file_type.lower()

        if file_type == "pdf":
            return extract_text_from_files(file_content)
        elif file_type == "docx":
            return extract_text_from_files(file_content)
        elif file_type == "doc":
            return cls.extract_text_from_doc(file_content)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    @staticmethod
    def validate_file(file, file_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file
        """
        if file_type not in settings.ALLOWED_FILE_TYPES:
            return (
                False,
                f"File type '{file_type}' not allowed. Allowed types: {', '.join(settings.ALLOWED_FILE_TYPES)}",
            )

        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file.size > max_size:
            return (
                False,
                f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB",
            )

        return True, None