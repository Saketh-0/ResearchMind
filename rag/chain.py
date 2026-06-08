"""
LangChain RAG chain with Groq LLM module.

Builds the RAG chain using ChatGroq (llama-3.3-70b-versatile)
with a research assistant system prompt, chat memory, and web search fallback.
"""

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_community.tools import DuckDuckGoSearchResults


SYSTEM_PROMPT = """You are a precise and helpful research assistant. 
Answer the user's questions based on the provided context. 

IMPORTANT RULES:
1. If the answer is in the context, strictly base your answer on it.
2. If the context does not contain the answer, and you see web search results provided, use the web search results to answer.
3. If neither the context nor web search results contain the answer, explicitly state: 'I could not find this in the documents or web search.'

Context:
{context}

Web Search Results (if needed):
{web_context}
"""


def get_llm(api_key: str) -> ChatGroq:
    """
    Initialize the Groq LLM.

    Args:
        api_key: Groq API key.

    Returns:
        ChatGroq instance configured with llama-3.3-70b-versatile.
    """
    return ChatGroq(
        groq_api_key=api_key,
        model_name="llama-3.3-70b-versatile",
        temperature=0.2, # slightly higher for more conversational tone
        max_tokens=2048
    )


def get_rag_chain(llm: ChatGroq):
    """
    Build the RAG chain with the research assistant prompt and chat history.

    Args:
        llm: ChatGroq LLM instance.

    Returns:
        A runnable chain that takes context, web_context, chat_history, and question as inputs.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])

    chain = prompt | llm | StrOutputParser()
    return chain


def perform_web_search(query: str) -> str:
    """
    Perform a web search using DuckDuckGo.
    """
    try:
        search = DuckDuckGoSearchResults(num_results=3)
        return search.run(query)
    except Exception as e:
        return f"Web search failed: {e}"


def query_rag_stream(chain, query: str, context: str, sources: list[dict], confidence: tuple[str, str], chat_history: list):
    """
    Run a query through the RAG chain and yield tokens for streaming.

    Args:
        chain: The RAG chain.
        query: User's question.
        context: Formatted context string from retrieved chunks.
        sources: Source references from retriever.
        confidence: Confidence level tuple (level, emoji).
        chat_history: List of previous messages.

    Yields:
        Tokens of the generated answer.
    """
    # Agentic Fallback: If document confidence is LOW, augment with web search
    web_context = "No web search performed."
    if confidence[0] == "LOW" and context.strip() != "":
        web_context = perform_web_search(query)
    elif context.strip() == "": # If no documents at all
        web_context = perform_web_search(query)

    try:
        # We yield chunks as they come in from the LLM
        for chunk in chain.stream({
            "context": context,
            "web_context": web_context,
            "chat_history": chat_history,
            "question": query
        }):
            yield chunk
            
    except Exception as e:
        yield f"\n\nError generating answer: {e}"


def query_rag(chain, query: str, context: str, sources: list[dict], confidence: tuple[str, str], chat_history: list = None) -> dict:
    """
    Run a query through the RAG chain synchronously.
    """
    if chat_history is None:
        chat_history = []
        
    web_context = "No web search performed."
    if confidence[0] == "LOW" and context.strip() != "":
        web_context = perform_web_search(query)
    elif context.strip() == "":
        web_context = perform_web_search(query)

    try:
        answer = chain.invoke({
            "context": context,
            "web_context": web_context,
            "chat_history": chat_history,
            "question": query
        })

        return {
            "answer": answer,
            "sources": sources,
            "confidence_level": confidence[0],
            "confidence_emoji": confidence[1]
        }
    except Exception as e:
        raise RuntimeError(f"Error generating answer: {e}")


def query_llm_direct(llm: ChatGroq, query: str) -> str:
    """
    Query the LLM directly without any document context.
    Used for Comparison Mode to show RAG vs direct LLM.

    Args:
        llm: ChatGroq LLM instance.
        query: User's question.

    Returns:
        Direct LLM response string.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a knowledgeable assistant. Answer the following question to the best of your ability."),
        ("human", "{question}")
    ])

    chain = prompt | llm | StrOutputParser()

    try:
        return chain.invoke({"question": query})
    except Exception as e:
        return f"Error getting direct LLM response: {e}"
