"""
Utility functions for ResearchMind.

Provides helpers for text cleaning, validation, file handling,
and source formatting.
"""

import re
import os


def clean_text(text: str) -> str:
    """
    Clean extracted text by removing excessive whitespace and special characters.

    Args:
        text: Raw text string.

    Returns:
        Cleaned text string.
    """
    # Replace multiple newlines with double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Replace multiple spaces with single space
    text = re.sub(r' {2,}', ' ', text)
    # Remove non-printable characters (keep newlines and tabs)
    text = re.sub(r'[^\S\n\t]+', ' ', text)
    # Strip leading/trailing whitespace
    text = text.strip()
    return text


def validate_api_key(key: str | None) -> bool:
    """
    Check if the GROQ_API_KEY is set and non-empty.

    Args:
        key: API key string or None.

    Returns:
        True if key is valid, False otherwise.
    """
    return key is not None and len(key.strip()) > 0


def get_api_key() -> str | None:
    """
    Get GROQ_API_KEY from environment variables.
    Supports both .env files and HuggingFace Spaces secrets.

    Returns:
        API key string or None.
    """
    # Try to load from .env file (local development)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    return os.environ.get("GROQ_API_KEY")


def get_file_size_mb(file) -> float:
    """
    Get the size of an uploaded file in megabytes.

    Args:
        file: Streamlit UploadedFile object.

    Returns:
        File size in MB, rounded to 2 decimal places.
    """
    file.seek(0, 2)  # Seek to end
    size_bytes = file.tell()
    file.seek(0)  # Reset to beginning
    return round(size_bytes / (1024 * 1024), 2)


def format_source_reference(source: str, page: int | str) -> str:
    """
    Format a source citation string.

    Args:
        source: Document filename.
        page: Page number.

    Returns:
        Formatted citation string.
    """
    return f"📄 {source} — Page {page}"
