from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from sentence_transformers import SentenceTransformer
import json
import os
from openai import OpenAI
from dotenv import load_dotenv

from utils import (
    normalize_text,
    split_into_chunks,
    is_order_intent,
    has_test_reference,
    extract_negated_tests,
    embedding_match,
    llm_fallback,
    NEGATION_WORDS,
    SYMPTOM_WORDS
)


load_dotenv()

TESTS_JSON = "tests.json"
TESTS_EMB_JSON = "tests_with_embeddings.json"
MODEL_NAME = "all-mpnet-base-v2"

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

model = SentenceTransformer(MODEL_NAME)

tests = []
if os.path.exists(TESTS_EMB_JSON):
    with open(TESTS_EMB_JSON, "r", encoding="utf-8") as f:
        tests = json.load(f)


class StreamRequest(BaseModel):
    transcript: str
    threshold: float = 0.75  # Default threshold 0.75 (75%)


class TestCreate(BaseModel):
    name: str
    category: str
    synonyms: List[str] = []


class TestUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    synonyms: Optional[List[str]] = None


@app.post("/generate_embeddings")
def generate_embeddings():
    with open(TESTS_JSON, "r", encoding="utf-8") as f:
        raw_tests = json.load(f)
    for test in raw_tests:
        embeddings = []
        # Include the actual test name first
        name_emb = model.encode(test["name"])
        embeddings.append(name_emb.tolist())
        # Then include all synonyms
        for phrase in test["synonyms"]:
            emb = model.encode(phrase)
            embeddings.append(emb.tolist())
        test["embeddings"] = embeddings
    with open(TESTS_EMB_JSON, "w", encoding="utf-8") as f:
        json.dump(raw_tests, f, ensure_ascii=False, indent=2)
    global tests
    tests = raw_tests
    return {"status": "ok", "tests_count": len(tests)}


@app.post("/match_stream")
def match_stream(req: StreamRequest):
    if not tests:
        return {"error": "Embeddings not loaded. Run /generate_embeddings first."}

    transcript = req.transcript
    chunks = split_into_chunks(transcript)

    aggregated_matches = {}
    removed_tests = set()
    detailed = []

    for chunk in chunks:
        norm_chunk = normalize_text(chunk)

        # Check for negation/cancellation
        if any(word in norm_chunk for word in NEGATION_WORDS):
            negated = extract_negated_tests(chunk, tests)
            if negated:
                for test_name in negated:
                    removed_tests.add(test_name)
                    aggregated_matches.pop(test_name, None)
                detailed.append({"chunk": chunk, "method": "negation", "removed_tests": negated})
            else:
                detailed.append({"chunk": chunk, "method": "skipped", "reason": "negation_no_test"})
            continue

        if any(word in norm_chunk for word in SYMPTOM_WORDS):
            detailed.append({"chunk": chunk, "method": "skipped", "reason": "symptom_not_test"})
            continue

        if not is_order_intent(chunk):
            if not has_test_reference(chunk, tests):
                detailed.append({"chunk": chunk, "method": "skipped", "reason": "no_intent"})
                continue
        else:
            if not has_test_reference(chunk, tests):
                detailed.append({"chunk": chunk, "method": "skipped", "reason": "action_without_test"})
                continue

        emb_matches = embedding_match(chunk, tests, model, threshold=req.threshold)
        if emb_matches:
            for m in emb_matches:
                # Don't add tests that were previously removed
                if m["name"] not in removed_tests:
                    # Keep highest score if test detected multiple times
                    if m["name"] not in aggregated_matches or m["score"] > aggregated_matches[m["name"]]["score"]:
                        aggregated_matches[m["name"]] = {
                            "method": "embedding",
                            "score": m["score"]
                        }
            detailed.append({"chunk": chunk, "method": "embedding", "matches": emb_matches})
            continue

        llm_result = llm_fallback(chunk, tests, model, openai_client, top_k=5)
        if llm_result["matches"] == ["Other"]:
            detailed.append({"chunk": chunk, "method": "skipped", "reason": "no_clear_test"})
            continue
        for m in llm_result["matches"]:
            # Don't add tests that were previously removed
            if m not in removed_tests:
                # Don't overwrite embedding matches with LLM matches
                if m not in aggregated_matches:
                    aggregated_matches[m] = {
                        "method": "llm",
                        "score": None
                    }
        detailed.append({"chunk": chunk, "method": "llm", "matches": llm_result["matches"]})

    # Format detected tests with metadata
    detected_tests_with_metadata = [
        {
            "name": test_name,
            "method": metadata["method"],
            "score": metadata["score"]
        }
        for test_name, metadata in sorted(aggregated_matches.items())
    ]

    return {
        "transcript": transcript,
        "detected_tests": detected_tests_with_metadata,
        "removed_tests": sorted(list(removed_tests)),
        "trace": detailed
    }


@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/api/tests")
def get_tests():
    """Get list of available tests for the frontend"""
    if not tests:
        return {"error": "Tests not loaded"}
    
    # Return simplified test data for frontend
    simplified_tests = []
    for test in tests:
        simplified_tests.append({
            "id": test.get("id", test["name"].lower().replace(" ", "-")),
            "name": test["name"],
            "category": test.get("category", "lab"),
            "synonyms": test.get("synonyms", [])
        })
    
    return simplified_tests

@app.get("/api/status")
def api_status():
    return {
        "status": "running",
        "model": MODEL_NAME,
        "tests_loaded": len(tests)
    }

@app.get("/api/config")
def get_config():
    """Get configuration for frontend (API keys, etc.)"""
    return {
        "deepgram_api_key": os.getenv("DEEPGRAM_API_KEY", "")
    }

@app.get("/api/categories")
def get_categories():
    """Get unique list of categories from existing tests"""
    try:
        raw_tests = load_tests_from_file()
        categories = sorted(set(test.get("category") for test in raw_tests if test.get("category")))
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading categories: {str(e)}")


# Helper functions for test management
def load_tests_from_file():
    """Load tests from tests.json"""
    if os.path.exists(TESTS_JSON):
        with open(TESTS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_tests_to_file(tests_data):
    """Save tests to tests.json"""
    with open(TESTS_JSON, "w", encoding="utf-8") as f:
        json.dump(tests_data, f, ensure_ascii=False, indent=2)


def regenerate_embeddings():
    """Regenerate embeddings after test modification"""
    raw_tests = load_tests_from_file()
    for test in raw_tests:
        embeddings = []
        # Include the actual test name first
        name_emb = model.encode(test["name"])
        embeddings.append(name_emb.tolist())
        # Then include all synonyms
        for phrase in test["synonyms"]:
            emb = model.encode(phrase)
            embeddings.append(emb.tolist())
        test["embeddings"] = embeddings

    with open(TESTS_EMB_JSON, "w", encoding="utf-8") as f:
        json.dump(raw_tests, f, ensure_ascii=False, indent=2)

    global tests
    tests = raw_tests
    return raw_tests


def generate_test_id(name):
    """Generate a unique test ID from name"""
    return name.lower().replace(" ", "_").replace("-", "_")


# Test CRUD endpoints
@app.post("/api/tests")
def create_test(test_data: TestCreate):
    """Create a new test"""
    raw_tests = load_tests_from_file()

    # Generate ID from name
    test_id = generate_test_id(test_data.name)

    # Check if test ID already exists
    if any(t.get("id") == test_id for t in raw_tests):
        raise HTTPException(status_code=400, detail=f"Test with ID '{test_id}' already exists")

    # Create new test
    new_test = {
        "id": test_id,
        "name": test_data.name,
        "category": test_data.category,
        "synonyms": test_data.synonyms
    }

    raw_tests.append(new_test)
    save_tests_to_file(raw_tests)

    # Regenerate embeddings
    regenerate_embeddings()

    return {
        "status": "success",
        "message": f"Test '{test_data.name}' created successfully",
        "test": new_test
    }


@app.put("/api/tests/{test_id}")
def update_test(test_id: str, test_data: TestUpdate):
    """Update an existing test"""
    raw_tests = load_tests_from_file()

    # Find test by ID
    test_index = next((i for i, t in enumerate(raw_tests) if t.get("id") == test_id), None)

    if test_index is None:
        raise HTTPException(status_code=404, detail=f"Test with ID '{test_id}' not found")

    # Update test fields
    if test_data.name is not None:
        raw_tests[test_index]["name"] = test_data.name
    if test_data.category is not None:
        raw_tests[test_index]["category"] = test_data.category
    if test_data.synonyms is not None:
        raw_tests[test_index]["synonyms"] = test_data.synonyms

    save_tests_to_file(raw_tests)

    # Regenerate embeddings
    regenerate_embeddings()

    return {
        "status": "success",
        "message": f"Test '{test_id}' updated successfully",
        "test": raw_tests[test_index]
    }


@app.delete("/api/tests/{test_id}")
def delete_test(test_id: str):
    """Delete a test"""
    raw_tests = load_tests_from_file()

    # Find test by ID
    test_index = next((i for i, t in enumerate(raw_tests) if t.get("id") == test_id), None)

    if test_index is None:
        raise HTTPException(status_code=404, detail=f"Test with ID '{test_id}' not found")

    deleted_test = raw_tests.pop(test_index)
    save_tests_to_file(raw_tests)

    # Regenerate embeddings
    regenerate_embeddings()

    return {
        "status": "success",
        "message": f"Test '{deleted_test['name']}' deleted successfully",
        "test": deleted_test
    }


@app.post("/api/tests/{test_id}/synonyms")
def add_synonym(test_id: str, synonym: dict):
    """Add a synonym to a test"""
    if "synonym" not in synonym:
        raise HTTPException(status_code=400, detail="Missing 'synonym' field in request body")

    raw_tests = load_tests_from_file()

    # Find test by ID
    test_index = next((i for i, t in enumerate(raw_tests) if t.get("id") == test_id), None)

    if test_index is None:
        raise HTTPException(status_code=404, detail=f"Test with ID '{test_id}' not found")

    synonym_text = synonym["synonym"].strip()

    # Check if synonym already exists
    if synonym_text in raw_tests[test_index]["synonyms"]:
        raise HTTPException(status_code=400, detail=f"Synonym '{synonym_text}' already exists")

    raw_tests[test_index]["synonyms"].append(synonym_text)
    save_tests_to_file(raw_tests)

    # Regenerate embeddings
    regenerate_embeddings()

    return {
        "status": "success",
        "message": f"Synonym '{synonym_text}' added successfully",
        "test": raw_tests[test_index]
    }


@app.delete("/api/tests/{test_id}/synonyms/{synonym}")
def remove_synonym(test_id: str, synonym: str):
    """Remove a synonym from a test"""
    raw_tests = load_tests_from_file()

    # Find test by ID
    test_index = next((i for i, t in enumerate(raw_tests) if t.get("id") == test_id), None)

    if test_index is None:
        raise HTTPException(status_code=404, detail=f"Test with ID '{test_id}' not found")

    # Check if synonym exists
    if synonym not in raw_tests[test_index]["synonyms"]:
        raise HTTPException(status_code=404, detail=f"Synonym '{synonym}' not found")

    raw_tests[test_index]["synonyms"].remove(synonym)
    save_tests_to_file(raw_tests)

    # Regenerate embeddings
    regenerate_embeddings()

    return {
        "status": "success",
        "message": f"Synonym '{synonym}' removed successfully",
        "test": raw_tests[test_index]
    }
