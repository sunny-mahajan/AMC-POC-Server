from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from sentence_transformers import SentenceTransformer
import json
import os
import time
from openai import OpenAI
from dotenv import load_dotenv
from sqlalchemy.orm import Session

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
from database import init_db, get_db, get_db_session, TestRepository

load_dotenv()

MODEL_NAME = "all-mpnet-base-v2"

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()
    print("Database initialized")
    # Warm up cache in background
    warm_cache()

model = SentenceTransformer(MODEL_NAME)

# Enhanced caching system with smart invalidation
_tests_cache = None
_cache_valid = False
_cache_timestamp = 0
_cache_ttl = 300  # 5 minutes TTL for cache

def get_tests_with_embeddings(db: Session = None) -> List[dict]:
    """Get tests with embeddings, using optimized cache"""
    global _tests_cache, _cache_valid, _cache_timestamp
    
    current_time = time.time()
    
    # Check if cache is valid and not expired
    if (_cache_valid and 
        _tests_cache is not None and 
        (current_time - _cache_timestamp) < _cache_ttl):
        return _tests_cache
    
    # Cache miss or expired - reload from database
    if db is None:
        db = get_db_session()
        try:
            _tests_cache = TestRepository.get_tests_with_embeddings(db)
            _cache_valid = True
            _cache_timestamp = current_time
            print(f"Cache reloaded: {len(_tests_cache)} tests with embeddings")
            return _tests_cache
        finally:
            db.close()
    else:
        _tests_cache = TestRepository.get_tests_with_embeddings(db)
        _cache_valid = True
        _cache_timestamp = current_time
        return _tests_cache

def invalidate_cache():
    """Smart cache invalidation"""
    global _cache_valid, _cache_timestamp
    _cache_valid = False
    _cache_timestamp = 0

def warm_cache():
    """Preload cache on startup"""
    try:
        get_tests_with_embeddings()
        print("Cache warmed up successfully")
    except Exception as e:
        print(f"Failed to warm cache: {e}")


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
def generate_embeddings(test_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Generate embeddings for all tests or a specific test.
    
    Query parameter: test_id (optional) - if provided, only generate for that test
    """
    if test_id:
        # Generate embeddings for a specific test only
        test = TestRepository.get_test_by_id(db, test_id)
        if not test:
            raise HTTPException(status_code=404, detail=f"Test with ID '{test_id}' not found")
        
        embeddings = []
        # Include the actual test name first
        name_emb = model.encode(test.name)
        embeddings.append(name_emb.tolist())
        # Then include all synonyms
        for phrase in test.synonyms or []:
            emb = model.encode(phrase)
            embeddings.append(emb.tolist())
        
        TestRepository.update_test_embeddings(db, test_id, embeddings)
        invalidate_cache()
        return {"status": "ok", "message": f"Embeddings generated for test '{test.name}'", "test_id": test_id}
    else:
        # Generate embeddings for all tests without embeddings
        tests = TestRepository.get_all_tests(db)
        updated = 0
        
        for test in tests:
            if not test.embeddings or len(test.embeddings) == 0:
                embeddings = []
                # Include the actual test name first
                name_emb = model.encode(test.name)
                embeddings.append(name_emb.tolist())
                # Then include all synonyms
                for phrase in test.synonyms or []:
                    emb = model.encode(phrase)
                    embeddings.append(emb.tolist())
                
                TestRepository.update_test_embeddings(db, test.id, embeddings)
                updated += 1
        
        invalidate_cache()
        return {"status": "ok", "tests_count": len(tests), "updated": updated}


@app.post("/match_stream")
def match_stream(req: StreamRequest, db: Session = Depends(get_db)):
    tests = get_tests_with_embeddings(db)
    if not tests:
        # Check if any tests exist at all
        total_tests = TestRepository.get_all_tests(db)
        if not total_tests:
            return {"error": "No tests found in database. Please run migration first."}
        else:
            return {
                "error": f"No tests with embeddings found. Found {len(total_tests)} tests without embeddings. Please run /generate_embeddings first.",
                "total_tests": len(total_tests),
                "tests_with_embeddings": 0
            }

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
def get_tests(db: Session = Depends(get_db)):
    """Get list of available tests for the frontend - OPTIMIZED"""
    # Use optimized query without embeddings for UI
    simplified_tests = TestRepository.get_tests_metadata_only(db)
    return simplified_tests

@app.get("/api/status")  
def api_status(db: Session = Depends(get_db)):
    # Use optimized count queries instead of loading all data
    total_count = db.query(Test).count()
    embeddings_count = TestRepository.get_tests_count_with_embeddings(db)
    
    # Check cache status
    cache_status = {
        "valid": _cache_valid,
        "size": len(_tests_cache) if _tests_cache else 0,
        "age_seconds": int(time.time() - _cache_timestamp) if _cache_timestamp > 0 else 0
    }
    
    return {
        "status": "running",
        "model": MODEL_NAME,
        "tests_total": total_count,
        "tests_with_embeddings": embeddings_count,
        "database_ready": embeddings_count > 0,
        "cache_status": cache_status,
        "performance_mode": "optimized"
    }

@app.get("/api/config")
def get_config():
    """Get configuration for frontend (API keys, etc.)"""
    return {
        "deepgram_api_key": os.getenv("DEEPGRAM_API_KEY", "")
    }

@app.get("/api/categories")
def get_categories(db: Session = Depends(get_db)):
    """Get unique list of categories from existing tests"""
    try:
        categories = TestRepository.get_all_categories(db)
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading categories: {str(e)}")


# Helper functions for test management
def regenerate_embeddings_for_test(db: Session, test_id: str):
    """Regenerate embeddings for a single test (optimized)"""
    test = TestRepository.get_test_by_id(db, test_id)
    if not test:
        return False
    
    embeddings = []
    # Include the actual test name first
    name_emb = model.encode(test.name)
    embeddings.append(name_emb.tolist())
    # Then include all synonyms
    for phrase in test.synonyms or []:
        emb = model.encode(phrase)
        embeddings.append(emb.tolist())
    
    TestRepository.update_test_embeddings(db, test_id, embeddings)
    invalidate_cache()
    return True


def generate_test_id(name):
    """Generate a unique test ID from name"""
    return name.lower().replace(" ", "_").replace("-", "_")


# Test CRUD endpoints
@app.post("/api/tests")
def create_test(test_data: TestCreate, db: Session = Depends(get_db)):
    """Create a new test"""
    # Generate ID from name
    test_id = generate_test_id(test_data.name)

    # Check if test ID already exists
    existing = TestRepository.get_test_by_id(db, test_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"Test with ID '{test_id}' already exists")

    # Create new test
    new_test_data = {
        "id": test_id,
        "name": test_data.name,
        "category": test_data.category,
        "synonyms": test_data.synonyms or [],
        "embeddings": []
    }

    new_test = TestRepository.create_test(db, new_test_data)
    
    # Generate embeddings for the new test (async in background would be better, but this works)
    regenerate_embeddings_for_test(db, test_id)

    return {
        "status": "success",
        "message": f"Test '{test_data.name}' created successfully",
        "test": new_test.to_dict()
    }


@app.put("/api/tests/{test_id}")
def update_test(test_id: str, test_data: TestUpdate, db: Session = Depends(get_db)):
    """Update an existing test"""
    # Prepare update data
    update_data = {}
    if test_data.name is not None:
        update_data["name"] = test_data.name
    if test_data.category is not None:
        update_data["category"] = test_data.category
    if test_data.synonyms is not None:
        update_data["synonyms"] = test_data.synonyms

    # Update test
    updated_test = TestRepository.update_test(db, test_id, update_data)
    if not updated_test:
        raise HTTPException(status_code=404, detail=f"Test with ID '{test_id}' not found")

    # Smart cache invalidation - only invalidate if name or synonyms changed
    should_invalidate_cache = (test_data.name is not None or test_data.synonyms is not None)
    
    # Regenerate embeddings only if name or synonyms changed (embeddings depend on these)
    if should_invalidate_cache:
        regenerate_embeddings_for_test(db, test_id)
        invalidate_cache()  # Only invalidate cache when embeddings change
    
    return {
        "status": "success",
        "message": f"Test '{test_id}' updated successfully",
        "test": updated_test.to_dict()
    }


@app.delete("/api/tests/{test_id}")
def delete_test(test_id: str, db: Session = Depends(get_db)):
    """Delete a test"""
    # Get test before deletion for response
    test = TestRepository.get_test_by_id(db, test_id)
    if not test:
        raise HTTPException(status_code=404, detail=f"Test with ID '{test_id}' not found")
    
    test_dict = test.to_dict()
    
    # Delete test
    success = TestRepository.delete_test(db, test_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete test")
    
    invalidate_cache()

    return {
        "status": "success",
        "message": f"Test '{test_dict['name']}' deleted successfully",
        "test": test_dict
    }


@app.post("/api/tests/{test_id}/synonyms")
def add_synonym(test_id: str, synonym: dict, db: Session = Depends(get_db)):
    """Add a synonym to a test"""
    if "synonym" not in synonym:
        raise HTTPException(status_code=400, detail="Missing 'synonym' field in request body")

    test = TestRepository.get_test_by_id(db, test_id)
    if not test:
        raise HTTPException(status_code=404, detail=f"Test with ID '{test_id}' not found")

    synonym_text = synonym["synonym"].strip()
    synonyms = test.synonyms if isinstance(test.synonyms, list) else []

    # Check if synonym already exists
    if synonym_text in synonyms:
        raise HTTPException(status_code=400, detail=f"Synonym '{synonym_text}' already exists")

    synonyms.append(synonym_text)
    updated_test = TestRepository.update_test(db, test_id, {"synonyms": synonyms})
    
    # Regenerate embeddings since synonyms changed
    regenerate_embeddings_for_test(db, test_id)

    return {
        "status": "success",
        "message": f"Synonym '{synonym_text}' added successfully",
        "test": updated_test.to_dict()
    }


@app.delete("/api/tests/{test_id}/synonyms/{synonym}")
def remove_synonym(test_id: str, synonym: str, db: Session = Depends(get_db)):
    """Remove a synonym from a test"""
    test = TestRepository.get_test_by_id(db, test_id)
    if not test:
        raise HTTPException(status_code=404, detail=f"Test with ID '{test_id}' not found")

    synonyms = test.synonyms if isinstance(test.synonyms, list) else []

    # Check if synonym exists
    if synonym not in synonyms:
        raise HTTPException(status_code=404, detail=f"Synonym '{synonym}' not found")

    synonyms.remove(synonym)
    updated_test = TestRepository.update_test(db, test_id, {"synonyms": synonyms})
    
    # Regenerate embeddings since synonyms changed
    regenerate_embeddings_for_test(db, test_id)

    return {
        "status": "success",
        "message": f"Synonym '{synonym}' removed successfully",
        "test": updated_test.to_dict()
    }
