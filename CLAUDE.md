# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI-based medical test matching service that uses semantic search (sentence transformers) and LLM fallback (OpenAI GPT-4o-mini) to identify medical tests from doctor's speech/text input.

## Architecture

### Core Workflow
1. **Embedding Generation** (`/generate_embeddings`): Loads test definitions from `tests.json`, generates embeddings using `all-MiniLM-L6-v2` model, saves to `tests_with_embeddings.json`
2. **Test Matching** (`/match`): Single-text matching using embedding similarity (threshold 0.75) with LLM fallback
3. **Stream Matching** (`/match_stream`): Processes full transcripts by splitting into chunks, applies intent detection, negation handling, and symptom filtering before matching

### Key Components
- **Text Chunking** ([app.py:131-151](app.py#L131-L151)): Splits sentences on punctuation and conjunctions, preserves action words across subparts
- **Intent Detection** ([app.py:57-70](app.py#L57-L70)): Requires ORDER_KEYWORDS + test reference OR direct test mention
- **Negation Filtering** ([app.py:197-199](app.py#L197-L199)): Skips chunks containing NEGATION_WORDS
- **Symptom Filtering** ([app.py:202-204](app.py#L202-L204)): Prevents symptom descriptions from being matched as tests
- **LLM Fallback** ([app.py:94-122](app.py#L94-L122)): Uses top-5 embedding candidates as context for GPT-4o-mini to select best match

### Data Files
- `tests.json`: Test definitions with names and synonyms (no embeddings)
- `tests_with_embeddings.json`: Same as above plus pre-computed embeddings for each synonym
- `.env`: Contains `OPENAI_API_KEY` (excluded from git)

## Common Commands

### Setup
```bash
# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Unix/Mac

# Install dependencies
pip install fastapi pydantic sentence-transformers torch openai python-dotenv uvicorn
```

### Running
```bash
# Start FastAPI server
uvicorn app:app --reload

# Access API docs
# http://127.0.0.1:8000/docs
```

### Typical Usage Flow
1. Ensure `tests.json` exists with test definitions
2. POST to `/generate_embeddings` (one-time setup or after updating tests.json)
3. POST to `/match` for single text matching
4. POST to `/match_stream` for full transcript processing

## Important Notes

- **Embeddings must be generated** before using `/match` or `/match_stream` endpoints
- Model uses `all-MiniLM-L6-v2` from sentence-transformers (384-dim embeddings)
- LLM fallback uses OpenAI's `gpt-4o-mini` model (requires API key in .env)
- Matching threshold is 0.75 cosine similarity for embedding matches
- Text normalization uses NFKD unicode normalization and ASCII conversion
