import streamlit as st
import time
import json

from google import genai
from google.genai import errors

from .vocabularyResolver import search_concepts, get_standard_mappings
from .schemaMetadata import get_database_schema
from .schemaFormatter import format_schema_for_llm
from .configManager import load_config


def generate_sql(question, on_retry=None):

    # Retrieve database schema and configuration.
    schema = get_database_schema()
    config = load_config()
    selected_tables = config["allowed_tables"]

    schema_text = format_schema_for_llm(schema, selected_tables)

    # Initialize Gemini.
    client = genai.Client(api_key=st.secrets["gemini"]["api_key"])

    # Retry configuration.
    max_attempts = 4
    retry_delays = [5, 10, 20]

    def call_gemini(prompt):
        for attempt in range(max_attempts):
            try:
                return client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt
                )

            except errors.ServerError as e:
                if e.code != 503 or attempt == max_attempts - 1:
                    raise

                if on_retry is not None:
                    on_retry(
                        attempt + 1,
                        retry_delays[attempt]
                    )

                time.sleep(retry_delays[attempt])

    # STEP 1: Identify clinical terminology.
    extraction_prompt = f"""
        You are a medical terminology assistant specialized
        in the OMOP Common Data Model.

        Identify the clinical concepts mentioned in the user's question.

        For each clinical concept:
        - Normalize its terminology into standard medical English.
        - Translate non-English clinical terms into English.
        - Preserve the original clinical meaning.
        - Do not generalize or broaden the diagnosis.
        - Do not invent OMOP concept IDs.
        - Do not extract generic database terms such as patient,
          person, count, table, or record.

        Return ONLY a valid JSON array containing the normalized
        English clinical terms.

        If no clinical concepts are present, return [].

        USER QUESTION:
        {question}
        """

    extraction_response = call_gemini(extraction_prompt)

    try:
        clinical_terms = json.loads(
            extraction_response.text.strip()
        )
        if not isinstance(clinical_terms, list):
            clinical_terms = []
    except (json.JSONDecodeError, AttributeError):
        clinical_terms = []

    clinical_terms = [
        term.strip()
        for term in clinical_terms
        if isinstance(term, str) and term.strip()
    ][:5]

    # STEP 2: Resolve terms against OMOP vocabularies.
    resolved_concepts = {}

    print("\n========== VOCABULARY DEBUG ==========")
    print("USER QUESTION:", question)
    print("EXTRACTED CLINICAL TERMS:", clinical_terms)

    for term in clinical_terms:

        print(f"\nSearching OMOP vocabulary for: {term}")

        candidates = search_concepts(term, limit=10)

        standard_concepts = {}

        for concept in candidates:

            concept_id = concept["concept_id"]

            if concept["standard_concept"] == "S":

                standard_concepts[concept_id] = {
                    **concept,
                    "source_concept_id": concept_id,
                    "mapping_type": "Already standard"
                }

            else:

                mappings = get_standard_mappings(concept_id)

                for mapped_concept in mappings:

                    mapped_id = mapped_concept["concept_id"]

                    if mapped_id not in standard_concepts:
                        standard_concepts[mapped_id] = {
                            **mapped_concept,
                            "source_concept_id": concept_id,
                            "mapping_type": "Maps to"
                        }

        resolved_concepts[term] = list(standard_concepts.values())

        print(f"Found {len(standard_concepts)} standard concepts:")

        for concept in resolved_concepts[term]:
            print(
                f"  ID: {concept['concept_id']} | "
                f"Name: {concept['concept_name']} | "
                f"Vocabulary: {concept['vocabulary_id']} | "
                f"Mapping: {concept['mapping_type']}"
            )

    print("======================================\n")

    vocabulary_context = json.dumps(resolved_concepts, indent=2, ensure_ascii=False)

    # STEP 3: Generate SQL using schema and vocabulary context.
    prompt = f"""
    You are an expert in PostgreSQL and the OMOP G-CDM database.

    Generate a PostgreSQL SELECT query that answers the user's question.

    Use only the tables and columns provided in the database schema.
    Use the provided relationships to construct JOIN operations.
    Do not invent tables, columns, or relationships.
    Do not generate INSERT, UPDATE, DELETE, DROP, or other
    modifying statements.

    OMOP VOCABULARY CONTEXT:
    {vocabulary_context}

    The vocabulary context contains candidate OMOP concepts
    retrieved directly from the database.

    Use the candidate concepts only when relevant to the question.

    Consider the domain and standard_concept fields when
    selecting concepts.

    Never invent concept IDs.
    
    The vocabulary context contains standard OMOP concepts, either found directly or obtained through valid "Maps to" relationships.
    
    Use only clinically relevant concepts. Do not assume that every candidate is equivalent to the user's diagnosis.
    
    When filtering condition_occurrence.condition_concept_id, prefer relevant standard Condition-domain concepts.
    
    Use concept_ancestor only when a hierarchical search is appropriate and the selected ancestor is a valid standard concept.

    If the question cannot be answered using the provided schema, respond with CANNOT_GENERATE_SQL.

    DATABASE SCHEMA:
    {schema_text}

    USER QUESTION:
    {question}

    Return only the SQL query, without explanations
    or Markdown formatting.
    """

    response = call_gemini(prompt)

    return response.text


#TEST
if __name__ == "__main__":
    question = "How many patients are present in the database?"

    sql = generate_sql(question)

    print("Generated SQL:")
    print(sql)