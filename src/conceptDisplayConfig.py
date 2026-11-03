GENDER_OPTIONS = {8507: "Male", 8532: "Female"}

FIELD_CONFIG = {
    "gender_concept_id": {"label": "Gender", "widget": "select", "options": GENDER_OPTIONS},
    "race_concept_id": {"label": "Race", "widget": "vocabulary_select", "domain": "Race"},
    "ethnicity_concept_id": {"label": "Ethnicity", "widget": "vocabulary_select", "domain": "Ethnicity"},
    "visit_concept_id": {"label": "Visit type", "widget": "vocabulary_select", "domain": "Visit"},
    "condition_concept_id": {"label": "Clinical condition", "widget": "concept_search", "domain": "Condition"},
    "measurement_concept_id": {"label": "Measurement", "widget": "concept_search", "domain": "Measurement"},
}

# Avoid incorrectly treating type_concept_id as visit_concept_id.
TABLE_FIELDS = {
    "person": {"gender_concept_id", "race_concept_id", "ethnicity_concept_id"},
    "visit_occurrence": {"visit_concept_id"},
    "condition_occurrence": {"condition_concept_id"},
    "measurement": {"measurement_concept_id"},
}

GENDER_OPTIONS = {8507: "Male", 8532: "Female"}

FIELD_CONFIG = {
    "gender_concept_id": {"label": "Gender", "widget": "select", "options": GENDER_OPTIONS},
    "race_concept_id": {"label": "Race", "widget": "vocabulary_select", "domain": "Race"},
    "ethnicity_concept_id": {"label": "Ethnicity", "widget": "vocabulary_select", "domain": "Ethnicity"},
    "visit_concept_id": {"label": "Visit type", "widget": "vocabulary_select", "domain": "Visit"},
    "condition_concept_id": {"label": "Clinical condition", "widget": "concept_search", "domain": "Condition"},
    "measurement_concept_id": {"label": "Measurement", "widget": "concept_search", "domain": "Measurement"},
}

# Avoid incorrectly treating type_concept_id as visit_concept_id.
TABLE_FIELDS = {
    "person": {"gender_concept_id", "race_concept_id", "ethnicity_concept_id"},
    "visit_occurrence": {"visit_concept_id"},
    "condition_occurrence": {"condition_concept_id"},
    "measurement": {"measurement_concept_id"},
}


def get_custom_concept_config(parameter):
    """Resolve a field from SQL AST metadata supplied by visualQueryEditor."""

    parameter_type = parameter.get("type")
    operator = parameter.get("operator")
    field = parameter.get("semantic_field")

    # Support both direct comparisons and clinical descendant filters.
    if parameter_type == "comparison":
        if operator not in ("=", "!="):
            return None

    elif parameter_type == "clinical_descendants":
        if operator != "IN" or field != "condition_concept_id":
            return None

    else:
        return None

    if field == "gender_concept_name":
        return {
            "label": "Gender",
            "widget": "select",
            "options": {
                "Male": "Male",
                "Female": "Female",
            },
        }

    if field == "gender_concept_code":
        return None

    return FIELD_CONFIG.get(field)
