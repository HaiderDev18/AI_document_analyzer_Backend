from typing import Optional, Tuple
from django.conf import settings
import io

# from llama_index.core import SimpleDirectoryReader
from llama_parse import LlamaParse

from dotenv import load_dotenv
import os


# Load environment variables
load_dotenv()


def extract_text_from_files(file_paths, result_type="text"):
    """
    Extracts text from a list of files using LlamaParse and SimpleDirectoryReader.

    Args:
        file_paths (list): List of file paths to be processed.
        result_type (str): The format of the extracted result ("markdown" or "text").

    Returns:
        list: A list of extracted text strings for each file.
    """
    # Set up the parser
    parser = LlamaParse(result_type=result_type, auto_mode=True)

    result = parser.parse(file_paths[0])

    text_documents = result.get_text_documents(split_by_page=False)
    print("*************text_documents", text_documents)
    text = "\n".join([doc.text for doc in text_documents])
    return text

    # Define file extractor for supported file types
    # file_extractor = {
    #     ".pdf": parser,
    #     ".docx": parser,
    #     ".doc": parser  # Use the same parser for both PDF and DOCX
    # }

    # # Use SimpleDirectoryReader to parse the provided files
    # documents = SimpleDirectoryReader(input_files=file_paths, file_extractor=file_extractor).load_data()

    # # Extract and return text from each document
    # return documents


class DocumentProcessor:
    """
    Service class for processing documents and extracting text.
    Uses robust libraries for better accuracy.
    """

    # @staticmethod
    # def extract_text_from_pdf(file_content: bytes) -> str:
    #     try:
    #         pdf_file = io.BytesIO(file_content)
    #         text = extract_text(pdf_file)
    #         return text.strip()
    #     except Exception as e:
    #         raise Exception(f"Error extracting text from PDF: {str(e)}")

    # @staticmethod
    # def extract_text_from_doc(file_content: bytes) -> str:
    #     """
    #     Extract text from DOC file using the 'textract' library.
    #     Requires system dependencies like 'antiword'.
    #     """
    #     try:
    #         import tempfile
    #         import os
    #         with tempfile.NamedTemporaryFile(delete=False, suffix=".doc") as temp:
    #             temp.write(file_content)
    #             filepath = temp.name

    #         try:
    #             text = textract.process(filepath).decode('utf-8')
    #         finally:
    #             os.remove(filepath) # Cleanup

    #         return text.strip()
    #     except textract.exceptions.ShellError as e:
    #          raise Exception("Error extracting from .doc file. Ensure 'antiword' is installed on the system.")
    #     except Exception as e:
    #         raise Exception(f"Error extracting text from DOC: {str(e)}")

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
        # Check file type
        if file_type not in settings.ALLOWED_FILE_TYPES:
            return (
                False,
                f"File type '{file_type}' not allowed. Allowed types: {', '.join(settings.ALLOWED_FILE_TYPES)}",
            )

        # Check file size
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB to bytes
        if file.size > max_size:
            return (
                False,
                f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB",
            )

        return True, None
