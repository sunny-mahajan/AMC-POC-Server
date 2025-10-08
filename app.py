from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
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
    embedding_match,
    llm_fallback,
    NEGATION_WORDS,
    SYMPTOM_WORDS
)


load_dotenv()

TESTS_JSON = "tests.json"
TESTS_EMB_JSON = "tests_with_embeddings.json"
MODEL_NAME = "all-MiniLM-L6-v2"

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


@app.post("/generate_embeddings")
def generate_embeddings():
    with open(TESTS_JSON, "r", encoding="utf-8") as f:
        raw_tests = json.load(f)
    for test in raw_tests:
        embeddings = []
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

    aggregated_matches = set()
    detailed = []

    for chunk in chunks:
        norm_chunk = normalize_text(chunk)

        if any(word in norm_chunk for word in NEGATION_WORDS):
            detailed.append({"chunk": chunk, "method": "skipped", "reason": "negation"})
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

        emb_matches = embedding_match(chunk, tests, model)
        if emb_matches:
            for m in emb_matches:
                aggregated_matches.add(m["name"])
            detailed.append({"chunk": chunk, "method": "embedding", "matches": emb_matches})
            continue

        llm_result = llm_fallback(chunk, tests, model, openai_client, top_k=5)
        if llm_result["matches"] == ["Other"]:
            detailed.append({"chunk": chunk, "method": "skipped", "reason": "no_clear_test"})
            continue
        for m in llm_result["matches"]:
            aggregated_matches.add(m)
        detailed.append({"chunk": chunk, "method": "llm", "matches": llm_result["matches"]})

    return {
        "transcript": transcript,
        "detected_tests": sorted(list(aggregated_matches)),
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
