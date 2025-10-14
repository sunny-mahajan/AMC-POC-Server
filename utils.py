"""
Utility functions for medical test matching system.

This module contains helper functions for text processing, intent detection,
embedding-based matching, and LLM fallback mechanisms.
"""

import re
import json
import unicodedata
import torch
from sentence_transformers import util
from typing import List, Dict, Optional, Any


# -----------------------------
# Configuration Constants
# -----------------------------

# Words that indicate negation or exclusion of tests
NEGATION_WORDS = [
    "don't", "dont", "do not", "no need", "not required",
    "not needed", "avoid", "skip", "no longer", "stop", "already have",
    "already done", "cancel", "remove", "drop", "exclude"
]

# Keywords that indicate test ordering intent
ORDER_KEYWORDS = [
    "check", "test", "do", "order", "send", "investigate", "take", "include", "add"
]

# Words that indicate symptoms rather than test names
SYMPTOM_WORDS = [
    "pain", "pressure", "heaviness", "fatigue", "breathlessness",
    "dizziness", "weakness", "palpitation", "swelling"
]


# -----------------------------
# Text Processing Functions
# -----------------------------

def normalize_text(text: str) -> str:
    """
    Normalize text by converting to lowercase and removing accents.

    Uses NFKD normalization to decompose characters and removes non-ASCII characters.
    Useful for case-insensitive and accent-insensitive matching.

    Args:
        text: Input text to normalize

    Returns:
        Normalized lowercase ASCII text

    Example:
        >>> normalize_text("Café")
        'cafe'
    """
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


def split_into_chunks(text: str) -> List[str]:
    """
    Split transcript into meaningful chunks for individual test matching.

    Process:
    1. Split on sentence boundaries (. ? ! newline)
    2. Further split on conjunctions (and, with, plus, etc.) and commas
    3. Preserve action words across subparts (e.g., "check CBC and RBS" -> ["check CBC", "check RBS"])

    Args:
        text: Full transcript text to split

    Returns:
        List of text chunks, each potentially containing a test order

    Example:
        >>> split_into_chunks("Check CBC and RBS. Also do LFT.")
        ['check CBC', 'check RBS', 'Also do LFT']
    """
    sentences = re.split(r"[.?!\n]", text)
    chunks = []

    for s in sentences:
        s = s.strip()
        if not s:
            continue

        # Find if sentence has an action word (check, test, order, etc.)
        action_word = find_action_word(s)

        # Split on conjunctions and commas to separate multiple tests
        subparts = re.split(
            r"\b(?:and|&|plus|along with|with|as well as|also)\b|,",
            s,
            flags=re.IGNORECASE
        )

        for p in subparts:
            p = p.strip()
            if not p:
                continue

            # If parent sentence had action word but this part doesn't, prepend it
            if action_word and not any(w in normalize_text(p) for w in ORDER_KEYWORDS):
                p = f"{action_word} {p}"

            chunks.append(p)

    return chunks


def find_action_word(text: str) -> Optional[str]:
    """
    Find the first action/order keyword in the text.

    Args:
        text: Text to search for action words

    Returns:
        First matching action word, or None if not found

    Example:
        >>> find_action_word("Please check the CBC test")
        'check'
    """
    norm = normalize_text(text)
    for word in ORDER_KEYWORDS:
        if word in norm:
            return word
    return None


# -----------------------------
# Intent Detection Functions
# -----------------------------

def is_order_intent(text: str) -> bool:
    """
    Check if text contains test ordering intent (action keywords).

    Args:
        text: Text to analyze for ordering intent

    Returns:
        True if text contains any ORDER_KEYWORDS, False otherwise

    Example:
        >>> is_order_intent("check CBC")
        True
        >>> is_order_intent("patient has fever")
        False
    """
    norm = normalize_text(text)
    return any(word in norm for word in ORDER_KEYWORDS)


def has_test_reference(text: str, tests: List[Dict[str, Any]]) -> bool:
    """
    Check if text directly mentions any known test name or synonym.

    Performs case-insensitive matching against test names and all their synonyms.

    Args:
        text: Text to search for test references
        tests: List of test dictionaries with 'name' and 'synonyms' fields

    Returns:
        True if any test name or synonym is found in text, False otherwise

    Example:
        >>> has_test_reference("do CBC test", tests)
        True
    """
    norm = normalize_text(text)

    for test in tests:
        # Check test name
        if test["name"].lower() in norm:
            return True

        # Check all synonyms
        for syn in test.get("synonyms", []):
            if syn.lower() in norm:
                return True

    return False


def extract_negated_tests(text: str, tests: List[Dict[str, Any]]) -> List[str]:
    """
    Extract test names that are being negated/cancelled in the text.

    Identifies tests mentioned alongside negation words and returns their names
    for removal from the detected tests list.

    Args:
        text: Text containing negation/cancellation intent
        tests: List of test dictionaries with 'name' and 'synonyms' fields

    Returns:
        List of test names that should be removed

    Example:
        >>> extract_negated_tests("avoid CBC", tests)
        ["Complete Blood Count"]
    """
    norm = normalize_text(text)
    negated_tests = []

    # Check if text contains negation words
    has_negation = any(word in norm for word in NEGATION_WORDS)
    if not has_negation:
        return []

    # Find which tests are mentioned in this negated context
    for test in tests:
        # Check test name
        if test["name"].lower() in norm:
            negated_tests.append(test["name"])
            continue

        # Check all synonyms
        for syn in test.get("synonyms", []):
            if syn.lower() in norm:
                negated_tests.append(test["name"])
                break

    return negated_tests


# -----------------------------
# Embedding Matching Functions
# -----------------------------

def embedding_match(text: str, tests: List[Dict[str, Any]], model, threshold: float = 0.75) -> List[Dict[str, Any]]:
    """
    Match text against test embeddings using cosine similarity.

    Encodes the query text and compares it against all test synonym embeddings.
    Returns tests whose best synonym match exceeds the threshold.

    Args:
        text: Query text to match
        tests: List of tests with pre-computed embeddings
        model: SentenceTransformer model for encoding
        threshold: Minimum cosine similarity score (0-1) to consider a match

    Returns:
        List of matching tests with format: [{"name": str, "score": float}, ...]
        Sorted by score in descending order

    Example:
        >>> embedding_match("complete blood count", tests, model, 0.75)
        [{"name": "CBC", "score": 0.92}]
    """
    query_emb = model.encode(text, convert_to_tensor=True)
    results = []

    for test in tests:
        # Convert stored embeddings to tensor
        emb_tensor = torch.tensor(test["embeddings"])

        # Calculate cosine similarity with all synonym embeddings
        scores = util.cos_sim(query_emb, emb_tensor)
        best_score = torch.max(scores).item()

        # Add to results if above threshold
        if best_score >= threshold:
            results.append({"name": test["name"], "score": round(best_score, 3)})

    return results


def embedding_topk(text: str, tests: List[Dict[str, Any]], model, top_k: int = 5) -> List[str]:
    """
    Get top-k most similar tests based on embedding similarity.

    Similar to embedding_match but returns fixed number of top results
    regardless of threshold. Used for LLM fallback candidate generation.

    Args:
        text: Query text to match
        tests: List of tests with pre-computed embeddings
        model: SentenceTransformer model for encoding
        top_k: Number of top matches to return

    Returns:
        List of test names, ordered by similarity score (highest first)

    Example:
        >>> embedding_topk("blood sugar", tests, model, top_k=3)
        ["RBS", "FBS", "HBA1c"]
    """
    query_emb = model.encode(text, convert_to_tensor=True)
    scored = []

    for test in tests:
        emb_tensor = torch.tensor(test["embeddings"])
        scores = util.cos_sim(query_emb, emb_tensor)
        best_score = torch.max(scores).item()
        scored.append({"name": test["name"], "score": best_score})

    # Sort by score descending and return top-k test names
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [s["name"] for s in scored[:top_k]]


# -----------------------------
# LLM Fallback Function
# -----------------------------

def llm_fallback(text: str, tests: List[Dict[str, Any]], model, openai_client, top_k: int = 5) -> Dict[str, List[str]]:
    """
    Use LLM to select most appropriate test from embedding-based candidates.

    When embedding matching is ambiguous, this function:
    1. Gets top-k most similar tests using embeddings
    2. Asks GPT-4o-mini to select the most appropriate test(s)
    3. Applies rules for panel selection, negation handling, etc.

    Args:
        text: Doctor's text/speech to analyze
        tests: List of all available tests
        model: SentenceTransformer model for embedding generation
        openai_client: OpenAI client instance
        top_k: Number of candidate tests to consider

    Returns:
        Dictionary with "matches" key containing list of test names
        Returns {"matches": ["Other"]} if no clear match

    Example:
        >>> llm_fallback("kidney function", tests, model, client)
        {"matches": ["RFT"]}
    """
    # Get top candidate tests using embeddings
    candidate_tests = embedding_topk(text, tests, model, top_k=top_k)

    # Construct prompt for LLM
    prompt = f"""
Doctor said: "{text}"

Candidate tests: {", ".join(candidate_tests)}

Rules:
- Pick the SINGLE most appropriate test.
- If the doctor clearly mentioned multiple distinct tests (e.g., fasting sugar + post-meal sugar), return both.
- Prefer the broader panel/profile if both a panel and its components are in candidates (e.g., choose RFT instead of Creatinine).
- Do NOT include tests that were explicitly negated (e.g., "don't do CBC").
- Return max 2 items.

Return JSON only in this format:
{{ "matches": ["TEST_NAME1", "TEST_NAME2"] }}
If nothing fits, return:
{{ "matches": ["Other"] }}
"""

    # Call OpenAI API
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    # Parse response
    try:
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception:
        return {"matches": ["Other"]}
