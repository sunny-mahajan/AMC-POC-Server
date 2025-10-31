import json
import re

# Medical synonym mappings for common abbreviations and terms
MEDICAL_SYNONYMS = {
    # Common medical abbreviations
    "CBC": ["complete blood count", "full blood count", "hemogram", "blood work", "blood count", "complete blood picture"],
    "ESR": ["erythrocyte sedimentation rate", "sed rate", "sedimentation rate", "inflammation marker"],
    "HBA1c": ["glycated hemoglobin", "A1C", "hemoglobin A1c", "glycosylated hemoglobin", "diabetes control test"],
    "RFT": ["renal function test", "kidney function test", "kidney panel", "renal profile"],
    "LFT": ["liver function test", "liver panel", "liver profile", "hepatic function test"],
    "ECG": ["electrocardiogram", "EKG", "heart tracing", "cardiac monitoring"],
    "ECHO": ["echocardiography", "cardiac ultrasound", "heart echo", "cardiac echo"],
    "USG": ["ultrasound", "sonography", "ultrasonography", "sono"],
    "CT": ["computed tomography", "CAT scan", "computerized tomography"],
    "MRI": ["magnetic resonance imaging", "nuclear magnetic resonance"],

    # Body parts
    "chest": ["thorax", "thoracic", "pulmonary", "lung"],
    "abdomen": ["abdominal", "belly", "stomach area", "peritoneal"],
    "pelvis": ["pelvic", "hip area", "pelvic region"],
    "brain": ["cerebral", "cranial", "head", "intracranial"],
    "spine": ["spinal", "vertebral", "backbone", "vertebrae"],
    "knee": ["patella", "knee joint", "genicular"],
    "shoulder": ["glenohumeral", "shoulder joint", "scapular"],
    "hip": ["hip joint", "acetabular", "femoral head"],

    # Directions
    "AP": ["anteroposterior", "front to back", "anterior posterior"],
    "PA": ["posteroanterior", "back to front", "posterior anterior"],
    "lateral": ["side view", "lat", "side projection"],
    "oblique": ["angled view", "diagonal", "oblique projection"],

    # Common tests
    "culture": ["C/S", "culture and sensitivity", "bacterial culture", "microbiology"],
    "smear": ["microscopy", "slide examination", "cytology"],
    "biopsy": ["tissue sample", "histopathology", "tissue examination"],
}

def get_medical_variants(word):
    """Get medical variants for a word"""
    word_lower = word.lower()
    variants = []
    for key, synonyms in MEDICAL_SYNONYMS.items():
        if key.lower() in word_lower:
            variants.extend(synonyms)
    return variants

def enhance_synonyms(test_entry):
    """Enhance synonyms to ensure exactly 10 unique, valid medical terms"""
    name = test_entry['name']
    code = test_entry['id']
    category = test_entry['category']
    current_synonyms = test_entry['synonyms']

    # Start with existing synonyms
    enhanced = list(current_synonyms)

    # Add medical variants based on the name
    words = name.lower().split()
    for word in words:
        variants = get_medical_variants(word)
        for variant in variants:
            if variant not in [s.lower() for s in enhanced]:
                enhanced.append(variant)

    # Category-specific enhancements
    if category == "X-Ray":
        additions = [
            f"{name} X-ray",
            f"{name} radiograph",
            f"radiographic {name}",
            f"{name} film",
            f"{name} view",
            f"{name} projection",
            f"plain {name}",
            f"{name} series"
        ]
    elif category == "USG":
        additions = [
            f"ultrasound {name}",
            f"USG {name}",
            f"{name} ultrasound",
            f"{name} sonography",
            f"sonographic {name}",
            f"{name} sono",
            f"{name} US",
            f"doppler {name}"
        ]
    elif category == "CT-Scan":
        additions = [
            f"CT {name}",
            f"{name} CT",
            f"CT scan {name}",
            f"computed tomography {name}",
            f"{name} tomography",
            f"CAT scan {name}",
            f"{name} CT scan",
            f"axial CT {name}"
        ]
    elif category == "Cardio":
        additions = [
            f"{name} test",
            f"cardiac {name}",
            f"heart {name}",
            f"{name} study",
            f"{name} monitoring",
            f"cardiovascular {name}",
            f"{name} assessment",
            f"{name} evaluation"
        ]
    elif category == "Lab":
        additions = [
            f"{name} test",
            f"{name} level",
            f"serum {name}",
            f"blood {name}",
            f"{name} screening",
            f"{name} assay",
            f"{name} measurement",
            f"laboratory {name}"
        ]
    else:
        additions = [
            f"{name} test",
            f"{name} examination",
            f"{name} study",
            f"{name} investigation",
            f"{name} procedure",
            f"{name} diagnostic",
            f"{name} screening",
            f"{name} workup"
        ]

    # Add new synonyms while avoiding duplicates
    for addition in additions:
        if len(enhanced) >= 10:
            break
        # Check if this synonym (case-insensitive) is already in the list
        if addition.lower() not in [s.lower() for s in enhanced]:
            enhanced.append(addition)

    # If still not enough, add generic medical terms
    generic_additions = [
        f"{name} investigation",
        f"{name} procedure",
        f"{name} diagnostic test",
        f"{name} clinical test",
        f"{name} medical examination",
        f"{name} workup",
        f"{name} evaluation",
        f"{name} assessment",
        f"{name} analysis",
        f"{name} check"
    ]

    for addition in generic_additions:
        if len(enhanced) >= 10:
            break
        if addition.lower() not in [s.lower() for s in enhanced]:
            enhanced.append(addition)

    # Return exactly 10 synonyms
    return enhanced[:10]

def enhance_tests_file(input_file, output_file):
    """Enhance all tests to have exactly 10 synonyms"""

    with open(input_file, 'r', encoding='utf-8') as f:
        tests_data = json.load(f)

    enhanced_data = []

    for test in tests_data:
        enhanced_synonyms = enhance_synonyms(test)
        test['synonyms'] = enhanced_synonyms
        enhanced_data.append(test)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(enhanced_data, f, indent=2, ensure_ascii=False)

    # Verify all have 10 synonyms
    all_have_10 = all(len(t['synonyms']) == 10 for t in enhanced_data)

    print(f"Enhancement complete!")
    print(f"Total tests: {len(enhanced_data)}")
    print(f"All tests have 10 synonyms: {all_have_10}")

    # Show distribution
    counts = {}
    for t in enhanced_data:
        count = len(t['synonyms'])
        counts[count] = counts.get(count, 0) + 1

    print("\nSynonym count distribution:")
    for count in sorted(counts.keys()):
        print(f"  {count} synonyms: {counts[count]} tests")

if __name__ == "__main__":
    input_file = "c:/Users/tf/Downloads/AMC-POC-Server-main/tests_new.json"
    output_file = "c:/Users/tf/Downloads/AMC-POC-Server-main/tests_new.json"
    enhance_tests_file(input_file, output_file)
