from src.vocabularyResolver import get_standard_mappings

source_concept_id = 45470219

results = get_standard_mappings(source_concept_id)

print("Source concept ID:", source_concept_id)
print("Standard mappings:")

for concept in results:
    print(
        f"ID: {concept['concept_id']} | "
        f"Name: {concept['concept_name']} | "
        f"Vocabulary: {concept['vocabulary_id']} | "
        f"Standard: {concept['standard_concept']}"
    )