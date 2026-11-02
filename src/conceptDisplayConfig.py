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
    if parameter.get("type") != "comparison" or parameter.get("operator") not in ("=", "!="):
        return None
    field = parameter.get("semantic_field")
    if field == "gender_concept_name":
        return {"label": "Gender", "widget": "select", "options": {"Male": "Male", "Female": "Female"}}
    if field == "gender_concept_code":
        # A concept_code is vocabulary-specific; don't assume 8507/8532 are codes.
        return None
    if field in FIELD_CONFIG:
        return FIELD_CONFIG[field]
    return None
