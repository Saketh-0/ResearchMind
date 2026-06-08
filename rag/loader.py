"""
PDF loading and text chunking module.

Uses PyMuPDF (fitz) for PDF text extraction and LangChain's
RecursiveCharacterTextSplitter for intelligent chunking.
"""

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


def extract_text_from_pdf(file_bytes: bytes, filename: str) -> list[dict]:
    """
    Extract text from a PDF file page by page.

    Args:
        file_bytes: Raw bytes of the uploaded PDF file.
        filename: Original filename for source attribution.

    Returns:
        List of dicts with keys: text, page_num, source.
        Pages with no extractable text are skipped.
    """
    pages = []
    skipped_pages = []

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Could not open PDF '{filename}': {e}")

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")

        if text and text.strip():
            pages.append({
                "text": text.strip(),
                "page_num": page_num + 1,  # 1-indexed for display
                "source": filename
            })
        else:
            skipped_pages.append(page_num + 1)

    doc.close()

    return pages, skipped_pages


def chunk_documents(pages: list[dict], chunk_size: int = 1200, chunk_overlap: int = 200) -> list[Document]:
    """
    Split extracted pages into smaller chunks for embedding.

    Args:
        pages: List of page dicts from extract_text_from_pdf.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of LangChain Document objects with metadata.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    documents = []
    for page in pages:
        chunks = text_splitter.split_text(page["text"])
        for chunk in chunks:
            doc = Document(
                page_content=chunk,
                metadata={
                    "source": page["source"],
                    "page": page["page_num"]
                }
            )
            documents.append(doc)

    return documents


def process_uploaded_files(uploaded_files) -> tuple[list[Document], int, list[str]]:
    """
    Process multiple uploaded PDF files: extract text and chunk.

    Args:
        uploaded_files: List of Streamlit UploadedFile objects.

    Returns:
        Tuple of (all_chunks, total_pages_processed, warnings).
    """
    all_chunks = []
    total_pages = 0
    warnings = []

    for uploaded_file in uploaded_files:
        try:
            file_bytes = uploaded_file.read()
            pages, skipped = extract_text_from_pdf(file_bytes, uploaded_file.name)

            if not pages:
                warnings.append(
                    f"⚠️ '{uploaded_file.name}' has no extractable text "
                    f"(possibly scanned). Skipped."
                )
                continue

            if skipped:
                warnings.append(
                    f"⚠️ '{uploaded_file.name}': Skipped pages {skipped} "
                    f"(no extractable text)."
                )

            total_pages += len(pages)
            chunks = chunk_documents(pages)
            all_chunks.extend(chunks)

        except ValueError as e:
            warnings.append(f"❌ {e}")
        except Exception as e:
            warnings.append(f"❌ Error processing '{uploaded_file.name}': {e}")

    return all_chunks, total_pages, warnings
