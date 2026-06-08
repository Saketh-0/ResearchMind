"""
Similarity search and context retrieval module.

Handles querying the FAISS vector store and formatting
results for the RAG chain.
"""

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS


def retrieve_relevant_chunks(
    vector_store: FAISS,
    query: str,
    k: int = 6
) -> list[tuple[Document, float]]:
    """
    Retrieve the top-k most relevant document chunks for a query.

    Args:
        vector_store: FAISS vector store to search.
        query: User's question.
        k: Number of chunks to retrieve.

    Returns:
        List of (Document, score) tuples, sorted by relevance.
        Score is L2 distance (lower = more similar).
    """
    results = vector_store.similarity_search_with_score(query, k=k)
    return results


def format_context(chunks_with_scores: list[tuple[Document, float]]) -> str:
    """
    Format retrieved chunks into a context string for the LLM.

    Each chunk is labeled with its source document and page number
    so the LLM can cite them in its answer.

    Args:
        chunks_with_scores: List of (Document, score) tuples.

    Returns:
        Formatted context string.
    """
    context_parts = []
    for i, (doc, score) in enumerate(chunks_with_scores, 1):
        source = doc.metadata.get("source", "Unknown")
        page = doc.metadata.get("page", "?")
        context_parts.append(
            f"[Source {i}: {source}, Page {page}]\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(context_parts)


def get_source_references(chunks_with_scores: list[tuple[Document, float]]) -> list[dict]:
    """
    Extract source references from retrieved chunks.

    Args:
        chunks_with_scores: List of (Document, score) tuples.

    Returns:
        List of dicts with source, page, content, and similarity_score.
    """
    sources = []
    for doc, score in chunks_with_scores:
        similarity = 1 / (1 + float(score))  # Convert L2 distance to similarity
        sources.append({
            "source": doc.metadata.get("source", "Unknown"),
            "page": doc.metadata.get("page", "?"),
            "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
            "similarity_score": round(similarity, 3)
        })
    return sources


def get_confidence_level(chunks_with_scores: list[tuple[Document, float]]) -> tuple[str, str]:
    """
    Determine confidence level based on average similarity scores.

    FAISS returns L2 distances (lower = more similar).
    We convert to similarity: similarity = 1 / (1 + distance).

    Thresholds:
        > 0.8  → HIGH   (🟢)
        0.5-0.8 → MEDIUM (🟡)
        < 0.5  → LOW    (🔴)

    Args:
        chunks_with_scores: List of (Document, score) tuples.

    Returns:
        Tuple of (level_string, emoji).
    """
    if not chunks_with_scores:
        return "LOW", "🔴"

    similarities = [1 / (1 + score) for _, score in chunks_with_scores]
    avg_similarity = sum(similarities) / len(similarities)

    if avg_similarity > 0.8:
        return "HIGH", "🟢"
    elif avg_similarity >= 0.5:
        return "MEDIUM", "🟡"
    else:
        return "LOW", "🔴"
