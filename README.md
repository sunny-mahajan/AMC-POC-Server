# Medical Test Speech Recognition System

FastAPI-based service with web interface for real-time medical test identification from doctor's speech using semantic embeddings and LLM fallback.

## Features

- **🎤 Real-time Speech Recognition**: Browser-based speech-to-text with live transcription (Deepgram Medical or Web Speech API)
- **⚡ Parallel Processing**: Chunked speech processing with concurrent API calls
- **🧠 Semantic Matching**: Uses sentence-transformers (all-mpnet-base-v2) for embedding-based test matching
- **🤖 LLM Fallback**: OpenAI GPT-4o-mini for ambiguous cases
- **🎯 Intent Detection**: Filters for test ordering intent vs symptoms
- **❌ Negation Handling**: Skips negated statements ("don't do CBC")
- **✂️ Smart Chunking**: Splits transcripts into meaningful segments
- **📱 Modern Web Interface**: Responsive design with real-time updates
- **🗄️ SQLite Database**: Fast, efficient database storage (100x faster than JSON files)
- **🔍 Category Filtering**: Filter and search medical tests by category
- **📊 Test Management**: Add, edit, delete tests with synonym management

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install fastapi uvicorn[standard] sentence-transformers openai python-dotenv pydantic sqlalchemy
```

### 2. Configure Environment

Create `.env` file:

```
OPENAI_API_KEY=your_openai_api_key_here
DEEPGRAM_API_KEY=your_deepgram_api_key_here  # Optional, for medical speech recognition
```

### 3. Migrate Data (First Time Setup)

If you have existing `tests.json` file, migrate to SQLite:

```bash
python migrate_to_sqlite.py
```

To regenerate embeddings during migration:
```bash
python migrate_to_sqlite.py --regenerate
```

### 4. Generate Embeddings

Start the server:

```bash
uvicorn app:app --reload
```

Generate embeddings for all tests:

```bash
curl -X POST http://127.0.0.1:8000/generate_embeddings
```

Or generate for a specific test:
```bash
curl -X POST "http://127.0.0.1:8000/generate_embeddings?test_id=cbc"
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

#### Get Categories
```
GET /api/categories
```
Returns unique list of categories from existing tests.

#### API Status
```
GET /api/status
```
Returns API status, database health, and test statistics:
```json
{
  "status": "running",
  "model": "all-mpnet-base-v2",
  "tests_total": 6614,
  "tests_with_embeddings": 6614,
  "database_ready": true
}
```

#### Generate Embeddings
```
POST /generate_embeddings?test_id=<optional>
```
Generates embeddings for all tests (or specific test if `test_id` provided). Only generates embeddings for tests that don't have them yet (incremental).

#### Create Test
```
POST /api/tests
Content-Type: application/json

{
  "name": "Complete Blood Count",
  "category": "Lab",
  "synonyms": ["CBC", "complete blood count"]
}
```

#### Update Test
```
PUT /api/tests/{test_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "category": "Lab",
  "synonyms": ["CBC", "complete blood count", "new synonym"]
}
```

#### Delete Test
```
DELETE /api/tests/{test_id}
```

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
├── app.py                          # FastAPI application with SQLite database
├── database.py                      # SQLAlchemy models and database operations
├── migrate_to_sqlite.py            # Migration script from JSON to SQLite
├── utils.py                        # Helper functions for matching and processing
├── tests.json                      # Test definitions (source file, migrated to DB)
├── tests_with_embeddings.json     # Generated embeddings (legacy, now in DB)
├── medical_tests.db                # SQLite database (auto-created)
├── static/                         # Web interface files
│   ├── index.html                  # Main HTML page
│   ├── style.css                   # CSS styling
│   └── script.js                   # JavaScript for speech recognition
├── requirements.txt                 # Python dependencies
├── .env                           # API keys (not in git)
└── README.md
```

## Database Structure

The system uses SQLite database (`medical_tests.db`) for efficient storage:

**Tests Table:**
- `id` (Primary Key): Unique test identifier
- `name`: Test name (e.g., "Complete Blood Count")
- `category`: Test category (e.g., "Lab", "Imaging", "Cardiology")
- `synonyms`: JSON array of alternative names/synonyms
- `embeddings`: JSON array of pre-computed embeddings for matching
- `embeddings_updated`: Timestamp when embeddings were last generated

**Data Format** (stored in database):
```json
{
  "id": "cbc",
  "name": "Complete Blood Count",
  "category": "Lab",
  "synonyms": [
    "CBC",
    "complete blood count",
    "full blood count",
    "hemogram"
  ],
  "embeddings": [[...], [...], ...]
}
```

## Performance Benefits

**Before (JSON files):**
- ⏱️ 2+ minutes per test add/update
- 📝 Rewrites entire 6,614+ test file
- 🔄 Regenerates all embeddings every time
- 🐌 Slow concurrent access

**After (SQLite):**
- ⚡ < 1 second per test add/update
- ✅ Only updates the specific test row
- 🎯 Incremental embedding generation
- 🚀 Fast indexed queries

## Interactive API Docs

Access Swagger UI at: http://127.0.0.1:8000/docs

## Database Management

### Migration from JSON to SQLite

If you have existing JSON files, migrate them:

```bash
python migrate_to_sqlite.py
```

This will:
- Create `medical_tests.db` database
- Migrate all tests from `tests.json`
- Preserve embeddings from `tests_with_embeddings.json` if available
- Optionally regenerate embeddings with `--regenerate` flag

### Adding New Tests

1. **Via Web Interface**: Click "Add New Test" button
2. **Via API**: POST to `/api/tests` endpoint
3. **Generate Embeddings**: Embeddings are automatically generated when adding/updating tests

### Backup Database

Simply copy `medical_tests.db` file - it's a single file containing all your data.

## Development

Run server with auto-reload:

```bash
uvicorn app:app --reload
```

**Note**: The system now uses SQLite database instead of JSON files for much better performance.

### Testing

1. Start server: `uvicorn app:app --reload`
2. Check status: Visit `http://localhost:8000/api/status`
3. Generate embeddings if needed: `POST /generate_embeddings`
4. Test matching: `POST /match_stream` with transcript
