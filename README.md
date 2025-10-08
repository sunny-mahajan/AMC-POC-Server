# Medical Test Speech Recognition System

FastAPI-based service with web interface for real-time medical test identification from doctor's speech using semantic embeddings and LLM fallback.

## Features

- **🎤 Real-time Speech Recognition**: Browser-based speech-to-text with live transcription
- **⚡ Parallel Processing**: Chunked speech processing with concurrent API calls
- **🧠 Semantic Matching**: Uses sentence-transformers (all-MiniLM-L6-v2) for embedding-based test matching
- **🤖 LLM Fallback**: OpenAI GPT-4o-mini for ambiguous cases
- **🎯 Intent Detection**: Filters for test ordering intent vs symptoms
- **❌ Negation Handling**: Skips negated statements ("don't do CBC")
- **✂️ Smart Chunking**: Splits transcripts into meaningful segments
- **📱 Modern Web Interface**: Responsive design with real-time updates

## Setup

### 1. Install Dependencies

```bash
pip install fastapi pydantic sentence-transformers torch openai python-dotenv uvicorn
```

### 2. Configure Environment

Create `.env` file:

```
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Generate Embeddings

Start the server:

```bash
uvicorn app:app --reload
```

Generate embeddings (one-time setup):

```bash
curl -X POST http://127.0.0.1:8000/generate_embeddings
```

## Usage

### Web Interface (Recommended)

1. **Start the server**:
   ```bash
   uvicorn app:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Open your browser** and go to: `http://localhost:8000`

3. **Allow microphone access** when prompted by your browser

4. **Click "Start Recording"** and speak naturally:
   - "Please check CBC and RBS for this patient"
   - "Order a thyroid profile and liver function test"
   - "Don't do the urine test, just blood work"

5. **View results** in real-time as you speak

### API Endpoints

#### Web Interface
```
GET /
```
Returns the speech recognition web interface.

#### Get Available Tests
```
GET /api/tests
```
Returns list of available tests for the frontend.

#### API Status
```
GET /api/status
```
Returns API status and health information.

#### Generate Embeddings
```
POST /generate_embeddings
```
Reads `tests.json` and generates embeddings for all test synonyms. Run this once after setup or when updating tests.

#### Match Stream
```
POST /match_stream
Content-Type: application/json

{
  "transcript": "Check CBC and RBS. Don't do LFT."
}
```

**Response:**
```json
{
  "transcript": "Check CBC and RBS. Don't do LFT.",
  "detected_tests": ["CBC", "RBS"],
  "trace": [
    {"chunk": "Check CBC", "method": "embedding", "matches": [{"name": "CBC", "score": 0.92}]},
    {"chunk": "Check RBS", "method": "embedding", "matches": [{"name": "RBS", "score": 0.88}]},
    {"chunk": "Don't do LFT", "method": "skipped", "reason": "negation"}
  ]
}
```

## Project Structure

```
.
├── app.py                          # FastAPI application
├── utils.py                        # Helper functions
├── tests.json                      # Test definitions (50 popular tests)
├── tests_with_embeddings.json     # Generated embeddings (auto-created)
├── static/                         # Web interface files
│   ├── index.html                  # Main HTML page
│   ├── style.css                   # CSS styling
│   └── script.js                   # JavaScript for speech recognition
├── .env                           # API keys (not in git)
└── README.md
```

## Data Format

`tests.json` structure:

```json
[
  {
    "id": "cbc",
    "name": "CBC",
    "category": "lab",
    "synonyms": [
      "CBC",
      "complete blood count",
      "full blood count",
      "hemogram"
    ]
  }
]
```

## Interactive API Docs

Access Swagger UI at: http://127.0.0.1:8000/docs

## Development

Run server with auto-reload:

```bash
uvicorn app:app --reload
```

Update tests:
1. Edit `tests.json`
2. Call `/generate_embeddings` endpoint
3. Test with `/match_stream`
