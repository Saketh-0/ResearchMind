"""
Custom RAG evaluation pipeline module.

Computes evaluation metrics for RAG pipeline quality using LLM-as-judge:
Faithfulness, Answer Relevancy, Context Precision, and Context Recall.

Replaces ragas dependency with direct LLM-based evaluation via Groq.
"""

import json
import pandas as pd
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# ─────────────────────────────────────────────
# Evaluation Prompts
# ─────────────────────────────────────────────

FAITHFULNESS_PROMPT = """You are an evaluation judge. Score how faithfully the answer is supported by the given context.

Context:
{context}

Question: {question}
Answer: {answer}

Score from 0.0 to 1.0:
- 1.0 = Every claim in the answer is directly supported by the context
- 0.5 = Some claims are supported, some are not
- 0.0 = The answer contains information not found in the context (hallucination)

Respond with ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""

ANSWER_RELEVANCY_PROMPT = """You are an evaluation judge. Score how relevant the answer is to the question asked.

Question: {question}
Answer: {answer}

Score from 0.0 to 1.0:
- 1.0 = The answer directly and completely addresses the question
- 0.5 = The answer partially addresses the question or includes irrelevant information
- 0.0 = The answer does not address the question at all

Respond with ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""

CONTEXT_PRECISION_PROMPT = """You are an evaluation judge. Score how precise/relevant the retrieved context chunks are for answering the question.

Question: {question}
Context:
{context}

Score from 0.0 to 1.0:
- 1.0 = All retrieved chunks are highly relevant to the question
- 0.5 = Some chunks are relevant, some are not
- 0.0 = None of the retrieved chunks are relevant to the question

Respond with ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""

CONTEXT_RECALL_PROMPT = """You are an evaluation judge. Score how well the retrieved context covers the information needed to produce the expected answer.

Question: {question}
Expected Answer: {ground_truth}
Retrieved Context:
{context}

Score from 0.0 to 1.0:
- 1.0 = The context contains all information needed to produce the expected answer
- 0.5 = The context contains some but not all of the needed information
- 0.0 = The context is missing the key information from the expected answer

Respond with ONLY a JSON object: {{"score": <float>, "reason": "<brief explanation>"}}"""


def _parse_score(response: str) -> float:
    """
    Parse a score from the LLM's JSON response.

    Falls back to 0.0 if parsing fails.
    """
    try:
        # Try to extract JSON from the response
        text = response.strip()
        # Handle cases where LLM wraps JSON in markdown code blocks
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        data = json.loads(text)
        score = float(data.get("score", 0.0))
        return max(0.0, min(1.0, score))  # Clamp to [0, 1]
    except (json.JSONDecodeError, ValueError, IndexError, AttributeError):
        # Try to find a number in the response
        import re
        numbers = re.findall(r"(\d+\.?\d*)", response)
        if numbers:
            score = float(numbers[0])
            if 0.0 <= score <= 1.0:
                return score
        return 0.0


def _evaluate_single(
    llm: ChatGroq,
    prompt_template: str,
    **kwargs
) -> float:
    """
    Run a single evaluation metric using the LLM.

    Args:
        llm: ChatGroq LLM instance.
        prompt_template: The evaluation prompt template string.
        **kwargs: Variables to fill into the prompt template.

    Returns:
        Score between 0.0 and 1.0.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a precise evaluation judge. Always respond with valid JSON."),
        ("human", prompt_template)
    ])
    chain = prompt | llm | StrOutputParser()

    try:
        response = chain.invoke(kwargs)
        return _parse_score(response)
    except Exception:
        return 0.0


def run_evaluation(
    questions: list[str],
    ground_truths: list[str],
    answers: list[str],
    contexts: list[list[str]],
    llm: ChatGroq,
) -> dict:
    """
    Run evaluation on question-answer pairs using LLM-as-judge.

    Computes four metrics:
    - Faithfulness: Is the answer grounded in the retrieved context?
    - Answer Relevancy: Does the answer address the question?
    - Context Precision: Are the retrieved chunks relevant?
    - Context Recall: Does the context cover the expected answer?

    Args:
        questions: List of test questions.
        ground_truths: List of expected/reference answers.
        answers: List of RAG-generated answers.
        contexts: List of lists of retrieved context strings.
        llm: ChatGroq LLM instance for evaluation.

    Returns:
        Dict of metric name -> average score.
    """
    faithfulness_scores = []
    relevancy_scores = []
    precision_scores = []
    recall_scores = []

    for q, gt, a, ctx_list in zip(questions, ground_truths, answers, contexts):
        ctx_str = "\n\n---\n\n".join(ctx_list)

        # Faithfulness
        f_score = _evaluate_single(
            llm, FAITHFULNESS_PROMPT,
            context=ctx_str, question=q, answer=a
        )
        faithfulness_scores.append(f_score)

        # Answer Relevancy
        r_score = _evaluate_single(
            llm, ANSWER_RELEVANCY_PROMPT,
            question=q, answer=a
        )
        relevancy_scores.append(r_score)

        # Context Precision
        p_score = _evaluate_single(
            llm, CONTEXT_PRECISION_PROMPT,
            question=q, context=ctx_str
        )
        precision_scores.append(p_score)

        # Context Recall
        c_score = _evaluate_single(
            llm, CONTEXT_RECALL_PROMPT,
            question=q, ground_truth=gt, context=ctx_str
        )
        recall_scores.append(c_score)

    return {
        "faithfulness": sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0.0,
        "answer_relevancy": sum(relevancy_scores) / len(relevancy_scores) if relevancy_scores else 0.0,
        "context_precision": sum(precision_scores) / len(precision_scores) if precision_scores else 0.0,
        "context_recall": sum(recall_scores) / len(recall_scores) if recall_scores else 0.0,
    }


def format_evaluation_results(results: dict) -> pd.DataFrame:
    """
    Format evaluation results into a styled DataFrame.

    Color coding:
        Green:  > 0.8
        Yellow: 0.5 - 0.8
        Red:    < 0.5

    Args:
        results: Dict of metric name -> score.

    Returns:
        DataFrame with Metric, Score, and Rating columns.
    """
    metric_names = {
        "faithfulness": "Faithfulness",
        "answer_relevancy": "Answer Relevancy",
        "context_precision": "Context Precision",
        "context_recall": "Context Recall",
    }

    rows = []
    for key, display_name in metric_names.items():
        score = results.get(key, 0.0)
        if score is None:
            score = 0.0

        if score > 0.8:
            rating = "🟢 Good"
        elif score >= 0.5:
            rating = "🟡 Fair"
        else:
            rating = "🔴 Poor"

        rows.append({
            "Metric": display_name,
            "Score": round(score, 4),
            "Rating": rating
        })

    return pd.DataFrame(rows)


def get_metric_explanations() -> dict:
    """
    Return human-friendly explanations for each evaluation metric.

    Returns:
        Dict mapping metric name to explanation string.
    """
    return {
        "Faithfulness": (
            "Measures whether the generated answer is factually consistent "
            "with the retrieved context. A high score means the answer doesn't "
            "contain hallucinated information — everything stated is supported "
            "by the source documents."
        ),
        "Answer Relevancy": (
            "Measures how well the generated answer addresses the original "
            "question. A high score means the answer is on-topic and directly "
            "responds to what was asked, without unnecessary or irrelevant "
            "information."
        ),
        "Context Precision": (
            "Measures whether the retrieved chunks are actually relevant to "
            "answering the question. A high score means the retriever is "
            "finding the right passages and not pulling in irrelevant content."
        ),
        "Context Recall": (
            "Measures whether all the relevant information needed to answer "
            "the question was successfully retrieved. A high score means the "
            "retriever is not missing important passages from the documents."
        ),
    }
