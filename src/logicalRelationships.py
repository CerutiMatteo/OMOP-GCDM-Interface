# UNDECLARED RELATIONSHIPS INSIDE PostgreSQL DB.

LOGICAL_RELATIONSHIPS = [
    # PERSON - VISIT_OCCURRENCE
    {
        "source_table": "visit_occurrence",
        "source_column": "person_id",
        "target_table": "person",
        "target_column": "person_id"
    },

    # PERSON - CONDITION_OCCURRENCE
    {
        "source_table": "condition_occurrence",
        "source_column": "person_id",
        "target_table": "person",
        "target_column": "person_id"
    },

    # VISIT_OCCURRENCE - CONDITION_OCCURRENCE
    {
        "source_table": "condition_occurrence",
        "source_column": "visit_occurrence_id",
        "target_table": "visit_occurrence",
        "target_column": "visit_occurrence_id"
    },

    # PERSON - PROCEDURE_OCCURRENCE
    {
        "source_table": "procedure_occurrence",
        "source_column": "person_id",
        "target_table": "person",
        "target_column": "person_id"
    },

    # VISIT_OCCURRENCE - PROCEDURE_OCCURRENCE
    {
        "source_table": "procedure_occurrence",
        "source_column": "visit_occurrence_id",
        "target_table": "visit_occurrence",
        "target_column": "visit_occurrence_id"
    },

    # PERSON - SPECIMEN
    {
        "source_table": "specimen",
        "source_column": "person_id",
        "target_table": "person",
        "target_column": "person_id"
    },

    # PERSON - CONCEPT (genere)
    {
        "source_table": "person",
        "source_column": "gender_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # VISIT_OCCURRENCE - CONCEPT
    {
        "source_table": "visit_occurrence",
        "source_column": "visit_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # CONDITION_OCCURRENCE - CONCEPT
    {
        "source_table": "condition_occurrence",
        "source_column": "condition_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # PROCEDURE_OCCURRENCE - CONCEPT
    {
        "source_table": "procedure_occurrence",
        "source_column": "procedure_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # SPECIMEN - CONCEPT
    {
        "source_table": "specimen",
        "source_column": "specimen_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # CONCEPT_SYNONYM - CONCEPT
    {
        "source_table": "concept_synonym",
        "source_column": "concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # PERSON - CONCEPT: race
    {
        "source_table": "person",
        "source_column": "race_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # PERSON - CONCEPT: ethnicity
    {
        "source_table": "person",
        "source_column": "ethnicity_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # VISIT_OCCURRENCE - CONCEPT: visit type
    {
        "source_table": "visit_occurrence",
        "source_column": "visit_type_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # CONDITION_OCCURRENCE - CONCEPT: condition type
    {
        "source_table": "condition_occurrence",
        "source_column": "condition_type_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # PROCEDURE_OCCURRENCE - CONCEPT: procedure type
    {
        "source_table": "procedure_occurrence",
        "source_column": "procedure_type_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    },

    # SPECIMEN - CONCEPT: specimen type
    {
        "source_table": "specimen",
        "source_column": "specimen_type_concept_id",
        "target_table": "concept",
        "target_column": "concept_id"
    }

]