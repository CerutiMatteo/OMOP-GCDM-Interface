import streamlit as st
import time
import json

from google import genai
from google.genai import errors

from .vocabularyResolver import search_concepts, get_standard_mappings
from .schemaMetadata import get_database_schema
from .schemaFormatter import format_schema_for_llm
from .configManager import load_config
from .sqlValidator import validate_sql


def generate_sql(question, on_retry=None):

    # Retrieve database schema and configuration.
    schema = get_database_schema()
    config = load_config()
    selected_tables = config["allowed_tables"]

    schema_text = format_schema_for_llm(schema, selected_tables)

    print("\n========== SCHEMA DEBUG ==========")

    print("ALLOWED TABLES:", selected_tables)

    for table_name in (
            "variant_annotation",
            "variant_occurrence",
            "target_gene"
    ):
        print(
            f"TABLE {table_name} INCLUDED:",
            f"TABLE: cdm.{table_name}" in schema_text
        )

    print("==================================\n")

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
        You are a medical terminology assistant specialized in the OMOP Common Data Model.

        Identify the clinical concepts mentioned in the user's question.

        For each clinical concept:
        - Normalize its terminology into standard medical English.
        - Translate non-English clinical terms into English.
        - Preserve the original clinical meaning.
        - Do not generalize or broaden the diagnosis.
        - Do not invent OMOP concept IDs.
        - Do not extract generic database terms such as patient, person, count, table, or record.

        Return ONLY a valid JSON array containing the normalized English clinical terms.

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

    # Remove duplicate clinical terms while preserving their order.
    clinical_terms = list(dict.fromkeys(clinical_terms))

    # STEP 2: Resolve terms against OMOP vocabularies.
    resolved_concepts = {}

    print("\n========== VOCABULARY DEBUG ==========")
    print("USER QUESTION:", question)
    print("EXTRACTED CLINICAL TERMS:", clinical_terms)

    for term in clinical_terms:

        print(f"\nSearching OMOP vocabulary for: {term}")

        candidates = search_concepts(term, limit=10)

        resolved = {}

        for concept in candidates:

            concept_id = concept["concept_id"]

            # Preserve the original vocabulary concept,
            # including non-standard concepts.
            resolved[concept_id] = {
                **concept,
                "source_concept_id": concept_id,
                "mapping_type": (
                    "Already standard"
                    if concept["standard_concept"] == "S"
                    else "Original non-standard concept"
                )
            }

            # Retrieve standard mappings when available.
            if concept["standard_concept"] != "S":

                mappings = get_standard_mappings(concept_id)

                for mapped_concept in mappings:

                    mapped_id = mapped_concept["concept_id"]

                    if mapped_id not in resolved:
                        resolved[mapped_id] = {
                            **mapped_concept,
                            "source_concept_id": concept_id,
                            "mapping_type": "Maps to"
                        }

        resolved_concepts[term] = list(resolved.values())

        print(f"Found {len(resolved)} resolved concepts:")

        for concept in resolved_concepts[term]:
            print(
                f"  ID: {concept['concept_id']} | "
                f"Name: {concept['concept_name']} | "
                f"Vocabulary: {concept['vocabulary_id']} | "
                f"Mapping: {concept['mapping_type']}"
            )

    print("======================================\n")

    vocabulary_context = json.dumps(resolved_concepts, indent=2, ensure_ascii=False)

    # Determine whether both target_gene relationships are required.
    gene_scope_prompt = f"""
    You are analyzing a user's question about an OMOP G-CDM database.

    The variant_occurrence table has two gene relationships:
    - target_gene1_id
    - target_gene2_id
    
    Determine whether answering the user's question requires considering both gene relationships.

    Return ONLY one of these JSON objects:

    {{"require_both_genes": true}}
    {{"require_both_genes": false}}

    Return true when:
    - The user asks for genes associated with genomic variants.
    - The user asks for patients carrying variants in a specified gene.
    - The user asks to count patients or variants associated with a gene.
    - The question requires a complete search across gene associations.

    Return false when:
    - The question does not involve genomic gene relationships.
    - The user explicitly restricts the search to target_gene1_id or target_gene2_id.

    USER QUESTION:
    {question}
    """

    gene_scope_response = call_gemini(gene_scope_prompt)

    try:
        gene_scope = json.loads(gene_scope_response.text.strip())

        require_both_genes = (
            isinstance(gene_scope, dict)
            and gene_scope.get("require_both_genes") is True
        )

    except (json.JSONDecodeError, AttributeError):
        raise ValueError("Unable to determine the required genomic gene scope.")

    print("GENOMIC GENE SCOPE:", require_both_genes)

    # STEP 3: Generate SQL using schema and vocabulary context.
    prompt = f"""
    You are an expert in PostgreSQL and the OMOP G-CDM database.

    Generate a PostgreSQL SELECT query that answers the user's question.
    
    The user's question may be written in Italian, English, or another language.

    Interpret the question in its original language and internally normalize its meaning into English before generating SQL.

    Use English OMOP terminology to identify the appropriate database tables, columns, and clinical concepts.

    Preserve the exact meaning of the original question, including filters, quantities, dates, and clinical conditions.

    Do not output the translated question. Return only the final SQL query.

    Use only the tables and columns provided in the database schema.

    DATABASE RELATIONSHIP AND JOIN RULES:
    
    The database schema explicitly provides PRIMARY KEYS, FOREIGN KEYS, and additional semantic relationships.
    
    When generating JOIN operations, always identify the relationship between the tables before writing the ON clause.
    
    Prefer explicitly declared FOREIGN KEY relationships over assumptions based on similar column names.
    
    For every JOIN:
    - Use the exact source and referenced columns defined by the provided relationships.
    - Do not assume that two columns are related simply because their names are similar or both contain "id".
    - Do not join a foreign key to an unrelated primary key.
    - Do not replace a foreign key column with the primary key of its own table.
    - Apply the same relationship rules inside subqueries, EXISTS, NOT EXISTS, IN, and NOT IN expressions.
    - If multiple relationships exist between two tables, select the relationship that matches the user's question.
    - If no relationship is available, do not invent one.
    
    A valid SQL query is not necessarily a semantically correct SQL query. All JOIN conditions must respect the relationships provided in the database schema.
    
    Do not invent tables, columns, or relationships. Do not generate INSERT, UPDATE, DELETE, DROP, or other modifying statements.
    
    GENOMIC GENE RELATIONSHIP RULES:

    The variant_occurrence table contains two foreign keys referencing target_gene:
    
    - variant_occurrence.target_gene1_id
    - variant_occurrence.target_gene2_id
    
    When the user asks for all genes associated with variants,
    or asks which patients have variants in a specified gene
    without restricting the relationship to one gene field,
    consider BOTH foreign keys.
    
    For these queries, use:
    
    JOIN cdm.target_gene AS tg
      ON (
        vo.target_gene1_id = tg.target_gene_id
        OR vo.target_gene2_id = tg.target_gene_id
      )
    
    Do not use only target_gene1_id unless the user's question explicitly restricts the search to that relationship.
    
    Do not invent additional relationships.
    
    OMOP CONCEPT FILTERING RULES:

    When filtering records by OMOP clinical or demographic concepts, prefer comparisons using concept_id columns rather than comparisons using concept_name or concept_code.
    For example:
    - person.gender_concept_id
    - person.race_concept_id
    - person.ethnicity_concept_id
    - visit_occurrence.visit_concept_id
    - condition_occurrence.condition_concept_id
    - measurement.measurement_concept_id
    
    When a valid concept ID is available, use it directly in the appropriate concept_id column. Avoid unnecessary JOIN operations with the concept table when the concept ID is already known. Never invent concept IDs.
    
    Use only concept IDs that are explicitly provided in the OMOP vocabulary context or otherwise verified against the database.

    If the concept ID cannot be determined reliably, do not guess it.

    JOIN the concept table when necessary for retrieving concept metadata or answering questions about concepts.

    Preserve the exact clinical meaning of the user's question.
    
    OMOP SCHEMA SEMANTICS:

    In the OMOP Common Data Model, the person table represents the individuals recorded in the database.

    Natural-language terms such as "patient", "patients", "paziente", "pazienti", "person" and "people" generally refer to records in the person table.

    When the user asks to list or count patients, use the person table, if available in the provided schema.

    When the user asks for patients with specific clinical conditions, use the appropriate clinical event tables and join them through person_id when necessary.

    Do not invent tables named patient or patients. Always respect the provided database schema.
    
    HPO PHENOTYPE SEMANTICS:

    Phenotypic features imported from Phenopackets are stored in cdm.observation.
    
    The original HPO identifier is stored in observation.observation_source_value.
    
    HPO identifiers may appear as HP:0000467 in source data and HP_0000467 in the OMOP vocabulary.
    
    When the user specifies an exact HPO identifier, filter observation.observation_source_value using the original colon-separated identifier.
    
    Do not assume that HPO vocabulary concepts are standard OMOP concepts.
    
    Use observation.observation_concept_id only when its relationship to the requested phenotype has been verified.
    
    Do not use condition_occurrence for Phenopacket HPO phenotypic features.
    
    
    CLINICAL CONDITIONS AND PHENOTYPE DISAMBIGUATION:
    
    Clinical diagnoses are stored in cdm.condition_occurrence. Phenotypic features imported from Phenopackets are stored in cdm.observation.
    
    When the user explicitly asks for a diagnosis or diagnosed patients, prefer condition_occurrence.
    
    When the user explicitly asks for an HPO phenotype, use observation and the appropriate HPO source identifier.
    
    Some clinical characteristics can be represented both as diagnoses and as HPO phenotypes.
    
    When the user asks for patients with such a characteristic without specifying whether it is a diagnosis or a phenotype, consider both representations if the relevant concepts and identifiers can be reliably established.
    
    Use OR or EXISTS to combine matching patients from different representations without duplicating patients.
    
    Never assume that a patient lacks a clinical characteristic solely because it is absent from condition_occurrence.
    
    Do not invent HPO identifiers or OMOP concept IDs. Use only verified vocabulary identifiers and preserve the clinical meaning of the requested characteristic.

    OMOP VOCABULARY CONTEXT:
    {vocabulary_context}

    The vocabulary context contains candidate OMOP concepts retrieved directly from the database.

    Use the candidate concepts only when relevant to the question. Consider the domain and standard_concept fields when selecting concepts.

    Never invent concept IDs.
    
    The vocabulary context contains valid OMOP candidate concepts, including standard and non-standard concepts.
    
    Some non-standard concepts may also have verified "Maps to" relationships to standard concepts.
    
    Use the domain_id, standard_concept, and mapping_type fields to determine how each concept should be used.
    
    VOCABULARY DISCOVERY RULES:

    When the user asks which codes or concepts correspond to a clinical term in a vocabulary, search the concept table using the requested vocabulary and the relevant clinical terminology.
    
    Do not restrict vocabulary discovery queries only to the concept IDs provided by the vocabulary resolver.
    
    The vocabulary resolver provides candidate concepts to support SQL generation, not an exhaustive list of all matching vocabulary entries.
    
    Use concept_name or concept_code filters when discovering vocabulary concepts.
    
    Use concept_id filters when retrieving clinical records associated with already resolved concepts.
    
    CLINICAL CONCEPT SELECTION RULES:

    The OMOP vocabulary context contains candidate concepts, not necessarily concepts that should all be used.
    
    Select concept IDs based on their precise clinical meaning, not merely on similarities between concept names.
    
    When the user asks for patients affected by a disease, select concepts that represent diagnoses or conditions of the patients themselves.
    
    Do not include concepts representing:
    - Family history of a disease.
    - Personal history of a resolved disease.
    - Risk factors or predispositions.
    - Screening or preventive encounters.
    - Suspected or ruled-out diagnoses.
    
    These concepts may be included only when the user explicitly requests them.
    
    For filters on condition_occurrence.condition_concept_id, prefer valid standard concepts belonging to the Condition domain.
    
    Do not automatically include every concept returned by the vocabulary resolver.
    
    Preserve all clinically relevant concepts when multiple concept IDs are necessary to represent the user's request.
    
    Use concept_ancestor only when a hierarchical search is appropriate and the selected ancestor is a valid standard concept.

    If the question cannot be answered using the provided schema, respond with CANNOT_GENERATE_SQL.

    DATABASE SCHEMA:
    {schema_text}

    USER QUESTION:
    {question}

    Return only the SQL query, without explanations or Markdown formatting.
    """

    # Generate SQL and validate it before returning.
    max_sql_attempts = 3
    current_prompt = prompt

    for attempt in range(max_sql_attempts):

        response = call_gemini(current_prompt)
        generated_sql = response.text.strip()

        try:
            validated_sql = validate_sql(
                generated_sql,
                require_both_genes=require_both_genes
            )

            print(
                f"SQL validated successfully "
                f"(attempt {attempt + 1})"
            )

            return validated_sql

        except ValueError as error:

            print(
                f"SQL validation failed "
                f"(attempt {attempt + 1}): {error}"
            )

            if attempt == max_sql_attempts - 1:
                raise ValueError(
                    "Unable to generate valid SQL after "
                    f"{max_sql_attempts} attempts. "
                    f"Last error: {error}"
                ) from error

            current_prompt = f"""
            {prompt}

            PREVIOUS SQL QUERY:
            {generated_sql}

            VALIDATION ERROR:
            {error}

            The previous SQL query failed validation.

            Generate a corrected PostgreSQL SELECT query.

            Follow the provided database schema and its declared FOREIGN KEY relationships exactly.

            Fix the validation error without changing the meaning of the original user question.

            Return only the corrected SQL query.
            """


#TEST
if __name__ == "__main__":
    question = "How many patients are present in the database?"

    sql = generate_sql(question)

    print("Generated SQL:")
    print(sql)