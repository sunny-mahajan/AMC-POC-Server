import json
import os
import time
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_medical_synonyms(test_name: str, test_code: str, category: str, department: str = "") -> List[str]:
    """
    Generate 10 medically accurate synonyms using OpenAI based on how doctors actually speak with patients.
    """

    prompt = f"""You are a medical terminology expert. Generate exactly 10 diverse synonyms/variations for this medical test that doctors commonly use when speaking with patients.

Test Name: {test_name}
Test Code: {test_code}
Category: {category}
Department: {department}

Requirements:
1. Include how doctors verbally refer to this test in conversations with patients
2. Include common abbreviations and full forms
3. Include casual/informal terms patients might understand
4. Include regional variations if applicable
5. Each synonym should be realistic and medically accurate
6. Avoid overly technical jargon that patients wouldn't understand
7. Include variations with "test", "scan", "examination" etc.

Examples of good synonyms:
- For "Complete Blood Count": ["CBC", "complete blood count", "blood work", "complete blood test", "hemogram", "full blood count", "blood panel", "CBC test", "routine blood work", "complete blood picture"]
- For "Chest X-Ray PA": ["chest X-ray", "chest radiograph", "lung X-ray", "chest film", "chest PA view", "thorax X-ray", "CXR", "chest imaging", "chest X-ray PA view", "posteroanterior chest X-ray"]
- For "Ultrasound Abdomen": ["abdominal ultrasound", "belly ultrasound", "USG abdomen", "sonography abdomen", "stomach ultrasound", "tummy scan", "abdomen sono", "abdominal sonography", "abdomen scan", "ultrasound of the abdomen"]

Return ONLY a JSON array of exactly 10 strings, nothing else. No explanations, no markdown formatting.

Example format:
["synonym1", "synonym2", "synonym3", "synonym4", "synonym5", "synonym6", "synonym7", "synonym8", "synonym9", "synonym10"]"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a medical terminology expert who helps generate realistic medical test synonyms that doctors use in conversations with patients. Always return valid JSON arrays only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )

        # Parse the response
        content = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Parse JSON
        synonyms = json.loads(content)

        # Ensure exactly 10 synonyms
        if len(synonyms) < 10:
            # Add generic variations if needed
            generic = [
                f"{test_name} test",
                f"{test_name} examination",
                f"{test_name} investigation",
                f"{test_code} test" if test_code else f"{test_name} check"
            ]
            for g in generic:
                if len(synonyms) >= 10:
                    break
                if g not in synonyms:
                    synonyms.append(g)

        return synonyms[:10]

    except Exception as e:
        print(f"Error generating synonyms for {test_name}: {str(e)}")
        # Return fallback synonyms
        return [
            test_code,
            test_name,
            f"{test_name} test",
            f"{test_name} examination",
            f"{test_name} investigation",
            f"{test_code} test" if test_code else f"{test_name} check",
            f"{test_name} procedure",
            f"{test_name} diagnostic",
            f"{test_name} screening",
            f"{test_name} analysis"
        ]

def process_consolidated_with_openai(input_file: str, output_file: str, batch_size: int = 10):
    """
    Process consolidated.json and generate synonyms using OpenAI API.
    """

    # Load consolidated data
    with open(input_file, 'r', encoding='utf-8') as f:
        consolidated_data = json.load(f)

    print(f"Loaded {len(consolidated_data)} tests from {input_file}")
    print(f"Starting OpenAI synonym generation...")
    print("=" * 70)

    tests_data = []
    total = len(consolidated_data)

    for idx, item in enumerate(consolidated_data, 1):
        investigation_code = item.get('investigationCode', '')
        investigation_name = item.get('investigationName', '')
        category = item.get('category', '')
        department_name = item.get('departmentName', '')

        print(f"\n[{idx}/{total}] Processing: {investigation_name} ({investigation_code})")
        print(f"Category: {category}, Department: {department_name}")

        # Generate synonyms using OpenAI
        synonyms = generate_medical_synonyms(
            investigation_name,
            investigation_code,
            category,
            department_name
        )

        print(f"Generated {len(synonyms)} synonyms:")
        for i, syn in enumerate(synonyms, 1):
            print(f"  {i}. {syn}")

        # Create test entry
        test_id = investigation_code.lower().replace('/', '-').replace(' ', '-').replace('(', '').replace(')', '')
        if not test_id:
            test_id = investigation_name.lower().replace('/', '-').replace(' ', '-').replace('(', '').replace(')', '')

        test_entry = {
            "id": test_id,
            "name": investigation_name,
            "category": category,
            "synonyms": synonyms
        }

        tests_data.append(test_entry)

        # Rate limiting: sleep after each batch to avoid hitting API limits
        if idx % batch_size == 0:
            print(f"\n--- Completed batch {idx//batch_size}. Waiting 2 seconds... ---")
            time.sleep(2)
        else:
            # Small delay between requests
            time.sleep(0.5)

    # Save to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tests_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"✓ Successfully generated synonyms for {len(tests_data)} tests")
    print(f"✓ Output saved to: {output_file}")

    # Verification
    all_have_10 = all(len(t['synonyms']) == 10 for t in tests_data)
    print(f"✓ All tests have 10 synonyms: {all_have_10}")

    # Category breakdown
    categories = {}
    for t in tests_data:
        cat = t['category']
        categories[cat] = categories.get(cat, 0) + 1

    print("\nTests by category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count} tests")

def test_single_generation():
    """Test the synonym generation with a single example"""
    print("Testing OpenAI synonym generation with a sample test...")
    print("=" * 70)

    # Test with a common test
    test_name = "Complete Blood Count"
    test_code = "CBC"
    category = "Lab"
    department = "Hematology"

    print(f"Test: {test_name} ({test_code})")
    print(f"Category: {category}, Department: {department}\n")

    synonyms = generate_medical_synonyms(test_name, test_code, category, department)

    print(f"Generated {len(synonyms)} synonyms:")
    for i, syn in enumerate(synonyms, 1):
        print(f"  {i}. {syn}")

    print("\n" + "=" * 70)
    print("Test complete! Ready to process all tests.")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Test mode: generate synonyms for a single test
        test_single_generation()
    else:
        # Full processing mode
        input_file = "c:/Users/tf/Downloads/AMC-POC-Server-main/consolidated.json"
        output_file = "c:/Users/tf/Downloads/AMC-POC-Server-main/tests_openai.json"

        # Process all tests with OpenAI
        process_consolidated_with_openai(input_file, output_file, batch_size=10)
