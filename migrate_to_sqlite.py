"""Migration script to convert JSON files to SQLite database"""
import json
import sys
import os
from database import init_db, get_db_session, TestRepository, Test
from sentence_transformers import SentenceTransformer

TESTS_JSON = "tests.json"
TESTS_EMB_JSON = "tests_with_embeddings.json"
MODEL_NAME = "all-mpnet-base-v2"

def migrate_json_to_sqlite(regenerate_embeddings: bool = False):
    """Migrate tests from JSON files to SQLite database"""
    print("Initializing database...")
    init_db()
    
    db = get_db_session()
    
    try:
        # Try to load from embeddings file first (has embeddings)
        if not regenerate_embeddings and os.path.exists(TESTS_EMB_JSON):
            print(f"Loading tests from {TESTS_EMB_JSON}...")
            with open(TESTS_EMB_JSON, "r", encoding="utf-8") as f:
                tests_data = json.load(f)
        elif os.path.exists(TESTS_JSON):
            print(f"Loading tests from {TESTS_JSON}...")
            with open(TESTS_JSON, "r", encoding="utf-8") as f:
                tests_data = json.load(f)
        else:
            print("No JSON files found to migrate.")
            return
        
        print(f"Found {len(tests_data)} tests to migrate.")
        
        # Check if database already has data
        existing_count = db.query(Test).count()
        if existing_count > 0:
            response = input(f"Database already has {existing_count} tests. Do you want to clear and re-migrate? (y/N): ")
            if response.lower() != 'y':
                print("Migration cancelled.")
                return
            # Clear existing data
            db.query(Test).delete()
            db.commit()
            print("Cleared existing data.")
        
        # Import model for embeddings if needed
        model = None
        if regenerate_embeddings:
            print(f"Loading embedding model {MODEL_NAME}...")
            model = SentenceTransformer(MODEL_NAME)
        
        # Migrate tests
        migrated = 0
        skipped = 0
        
        for i, test in enumerate(tests_data, 1):
            try:
                test_id = test.get("id") or test["name"].lower().replace(" ", "_").replace("-", "_")
                
                # Check if test already exists
                existing = TestRepository.get_test_by_id(db, test_id)
                if existing:
                    skipped += 1
                    continue
                
                # Prepare test data
                test_data = {
                    "id": test_id,
                    "name": test.get("name", ""),
                    "category": test.get("category", "Other"),
                    "synonyms": test.get("synonyms", [])
                }
                
                # Handle embeddings
                if regenerate_embeddings and model:
                    print(f"Generating embeddings for test {i}/{len(tests_data)}: {test_data['name']}")
                    embeddings = []
                    # Embed test name
                    name_emb = model.encode(test_data["name"])
                    embeddings.append(name_emb.tolist())
                    # Embed synonyms
                    for phrase in test_data["synonyms"]:
                        emb = model.encode(phrase)
                        embeddings.append(emb.tolist())
                    test_data["embeddings"] = embeddings
                elif test.get("embeddings"):
                    test_data["embeddings"] = test["embeddings"]
                else:
                    test_data["embeddings"] = []
                
                # Create test in database
                TestRepository.create_test(db, test_data)
                migrated += 1
                
                if i % 100 == 0:
                    print(f"Migrated {i}/{len(tests_data)} tests...")
                    
            except Exception as e:
                print(f"Error migrating test {test.get('name', 'unknown')}: {e}")
                skipped += 1
                continue
        
        print(f"\nMigration complete!")
        print(f"  Migrated: {migrated} tests")
        print(f"  Skipped: {skipped} tests")
        print(f"  Total in database: {db.query(Test).count()} tests")
        
    finally:
        db.close()


if __name__ == "__main__":
    import os
    regenerate = "--regenerate" in sys.argv or "-r" in sys.argv
    migrate_json_to_sqlite(regenerate_embeddings=regenerate)

