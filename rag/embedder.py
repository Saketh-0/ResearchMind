"""
Embedding generation and FAISS vector store module.

Uses sentence-transformers (BAAI/bge-small-en-v1.5) for embeddings
and FAISS IndexFlatL2 for vector storage.
"""

import functools
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


@functools.lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    Load and cache the sentence-transformer embedding model.

    Returns:
        HuggingFaceEmbeddings instance using BAAI/bge-small-en-v1.5.
    """
    return HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )


def create_vector_store(chunks: list[Document]) -> FAISS:
    """
    Create a FAISS vector store from document chunks.

    Args:
        chunks: List of LangChain Document objects with page_content and metadata.

    Returns:
        FAISS vector store instance.

    Raises:
        ValueError: If no chunks are provided.
    """
    if not chunks:
        raise ValueError("No document chunks provided to create vector store.")

    embedding_model = get_embedding_model()
    vector_store = FAISS.from_documents(chunks, embedding_model)

    return vector_store


def add_to_vector_store(vector_store: FAISS, new_chunks: list[Document]) -> FAISS:
    """
    Add new document chunks to an existing FAISS vector store.

    Args:
        vector_store: Existing FAISS vector store.
        new_chunks: New document chunks to add.

    Returns:
        Updated FAISS vector store.
    """
    if not new_chunks:
        return vector_store

    embedding_model = get_embedding_model()
    new_store = FAISS.from_documents(new_chunks, embedding_model)
    vector_store.merge_from(new_store)

    return vector_store
