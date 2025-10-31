import json
import re

def create_id(name):
    """Create a URL-friendly ID from the test name"""
    # Convert to lowercase and replace spaces and special chars with hyphens
    test_id = name.lower()
    test_id = re.sub(r'[^\w\s-]', '', test_id)
    test_id = re.sub(r'[-\s]+', '-', test_id)
    test_id = test_id.strip('-')
    return test_id

def generate_synonyms(investigation_name, investigation_code, department_name, category):
    """Generate 10 relevant synonyms for each test"""
    synonyms = []

    # Add the original code and name
    if investigation_code:
        synonyms.append(investigation_code)
    if investigation_name and investigation_name != investigation_code:
        synonyms.append(investigation_name)

    # Add lowercase variations
    if investigation_code and investigation_code.lower() not in [s.lower() for s in synonyms]:
        synonyms.append(investigation_code.lower())

    # Add variations with common terms
    base_name = investigation_name.lower() if investigation_name else investigation_code.lower()

    # Category-specific synonym generation
    if category == "X-Ray":
        # Add X-ray specific terms
        if "AP" in investigation_name:
            synonyms.append(investigation_name.replace("AP", "anteroposterior"))
        if "PA" in investigation_name:
            synonyms.append(investigation_name.replace("PA", "posteroanterior"))
        if "Lateral" in investigation_name:
            synonyms.append(investigation_name.replace("Lateral", "lat"))

        # Add "X-ray" prefix variations
        if "x-ray" not in base_name and "xray" not in base_name:
            synonyms.append(f"X-ray {investigation_name}")
            synonyms.append(f"radiograph {investigation_name}")

        # Add department
        synonyms.append(f"{investigation_name} imaging")
        synonyms.append(f"{investigation_name} radiography")

    elif category == "USG":
        # Add ultrasound specific terms
        synonyms.append(f"ultrasound {investigation_name}")
        synonyms.append(f"USG {investigation_name}")
        synonyms.append(f"sonography {investigation_name}")
        synonyms.append(f"{investigation_name} ultrasound")
        synonyms.append(f"{investigation_name} sonography")
        synonyms.append(f"{investigation_name} scan")

    elif category == "CT-Scan":
        # Add CT specific terms
        synonyms.append(f"CT {investigation_name}")
        synonyms.append(f"CT scan {investigation_name}")
        synonyms.append(f"computed tomography {investigation_name}")
        synonyms.append(f"{investigation_name} CT")
        synonyms.append(f"{investigation_name} scan")
        synonyms.append(f"CAT scan {investigation_name}")

    elif category == "Cardio":
        # Add cardio specific terms
        synonyms.append(f"{investigation_name} test")
        synonyms.append(f"cardiac {investigation_name}")
        synonyms.append(f"heart {investigation_name}")
        synonyms.append(f"{investigation_name} examination")
        synonyms.append(f"{investigation_name} screening")

    elif category == "Lab":
        # Add lab specific terms
        synonyms.append(f"{investigation_name} test")
        synonyms.append(f"lab {investigation_name}")
        synonyms.append(f"{investigation_name} blood test")
        if "serum" not in base_name:
            synonyms.append(f"serum {investigation_name}")

    # Add generic variations
    synonyms.append(f"{investigation_name} investigation")
    synonyms.append(f"{investigation_code} test" if investigation_code else f"{investigation_name} test")

    # Remove duplicates while preserving order and case variations
    seen = set()
    unique_synonyms = []
    for syn in synonyms:
        if syn and syn.lower() not in seen:
            seen.add(syn.lower())
            unique_synonyms.append(syn)

    # Ensure we have at least 10 synonyms
    while len(unique_synonyms) < 10:
        # Add more generic terms
        if len(unique_synonyms) == len(synonyms):
            unique_synonyms.append(f"{investigation_name} procedure")
            unique_synonyms.append(f"{investigation_name} diagnostic")
            unique_synonyms.append(f"{investigation_name} clinical test")
            unique_synonyms.append(f"{investigation_name} medical test")
            unique_synonyms.append(f"{investigation_name} examination")
            unique_synonyms.append(f"{investigation_name} workup")
            unique_synonyms.append(f"{investigation_name} screening")
            unique_synonyms.append(f"{investigation_name} evaluation")
        else:
            break

    # Return exactly 10 synonyms (or all if less than 10)
    return unique_synonyms[:10]

def convert_consolidated_to_tests(input_file, output_file):
    """Convert consolidated.json format to tests.json format"""

    # Load consolidated data
    with open(input_file, 'r', encoding='utf-8') as f:
        consolidated_data = json.load(f)

    tests_data = []

    for item in consolidated_data:
        investigation_code = item.get('investigationCode', '')
        investigation_name = item.get('investigationName', '')
        category = item.get('category', '')
        department_name = item.get('departmentName', '')

        # Create test entry
        test_entry = {
            "id": create_id(investigation_code or investigation_name),
            "name": investigation_name,
            "category": category,
            "synonyms": generate_synonyms(investigation_name, investigation_code, department_name, category)
        }

        tests_data.append(test_entry)

    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tests_data, f, indent=2, ensure_ascii=False)

    print(f"Conversion complete!")
    print(f"Total tests converted: {len(tests_data)}")
    print(f"Output file: {output_file}")

if __name__ == "__main__":
    input_file = "c:/Users/tf/Downloads/AMC-POC-Server-main/consolidated.json"
    output_file = "c:/Users/tf/Downloads/AMC-POC-Server-main/tests_new.json"
    convert_consolidated_to_tests(input_file, output_file)
