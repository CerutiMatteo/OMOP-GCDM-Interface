import psycopg
import streamlit as st


def _connection():
    cfg = st.secrets["connections"]["omop"]
    return psycopg.connect(
        host=cfg["host"], port=cfg["port"], dbname=cfg["database"],
        user=cfg["username"], password=cfg["password"],
        options="-c default_transaction_read_only=on",
    )


@st.cache_data(ttl=3600, show_spinner=False)
def get_concept(concept_id: int):
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT concept_id, concept_name, domain_id
            FROM cdm.concept WHERE concept_id = %s AND invalid_reason IS NULL
        """, (concept_id,))
        row = cur.fetchone()
        return {"concept_id": row[0], "concept_name": row[1], "domain_id": row[2]} if row else None



@st.cache_data(ttl=3600, show_spinner=False)
def list_field_concepts(
    table: str,
    column: str,
    domain: str,
    limit: int = 200
):
    """
    Retrieve available standard OMOP concepts for a field.

    Concepts are retrieved from the vocabulary, not only
    from values already present in clinical tables.
    """

    allowed = {
        "person": {
            "race_concept_id",
            "ethnicity_concept_id",
        },
        "visit_occurrence": {
            "visit_concept_id",
        },
    }

    if column not in allowed.get(table, set()):
        raise ValueError("Unsupported vocabulary field")

    # Associate each supported field with its expected OMOP domain.
    field_domains = {
        "race_concept_id": "Race",
        "ethnicity_concept_id": "Ethnicity",
        "visit_concept_id": "Visit",
    }

    expected_domain = field_domains[column]

    if domain != expected_domain:
        raise ValueError("Unexpected OMOP concept domain")

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500:
        raise ValueError("Invalid concept limit")

    with _connection() as conn, conn.cursor() as cur:

        cur.execute("""
            SELECT
                concept_id,
                concept_name
            FROM cdm.concept
            WHERE invalid_reason IS NULL
              AND standard_concept = 'S'
              AND domain_id = %s
            ORDER BY concept_name, concept_id
            LIMIT %s
        """, (expected_domain, limit))

        return {
            int(cid): name
            for cid, name in cur.fetchall()
        }


@st.cache_data(ttl=3600, show_spinner=False)
def search_standard_concepts(term: str, domain: str, limit: int = 1000):
    term = term.strip()
    if len(term) < 2:
        return {}
    with _connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT concept_id, concept_name
            FROM cdm.concept
            WHERE invalid_reason IS NULL
              AND standard_concept = 'S'
              AND domain_id = %s
              AND concept_name ILIKE %s
            ORDER BY CASE WHEN LOWER(concept_name) = LOWER(%s) THEN 0 ELSE 1 END,
                     concept_name, concept_id
            LIMIT %s
        """, (domain, f"%{term}%", term, limit))
        return {int(cid): name for cid, name in cur.fetchall()}
