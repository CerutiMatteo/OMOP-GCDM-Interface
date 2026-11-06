import psycopg
import streamlit as st


def search_concepts(term: str, limit: int = 20) -> list[dict]:
    """Search OMOP concepts by name and synonyms."""

    if not isinstance(term, str) or not term.strip():
        raise ValueError("Search term must be a non-empty string.")

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("Limit must be an integer.")

    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100.")

    term = term.strip()

    normalized_code = term

    if term.upper().startswith("HP:"):
        normalized_code = "HP_" + term[3:]

    db_config = st.secrets["connections"]["omop"]

    with psycopg.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["database"],
        user=db_config["username"],
        password=db_config["password"],
        options="-c default_transaction_read_only=on"
    ) as conn:

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.concept_id,
                    c.concept_name,
                    c.vocabulary_id,
                    c.domain_id,
                    c.standard_concept,
                    c.invalid_reason
                FROM cdm.concept AS c
                WHERE
                    c.invalid_reason IS NULL
                    AND (
                        c.concept_name ILIKE %s
                        OR c.concept_code = %s
                        OR EXISTS (
                            SELECT 1
                            FROM cdm.concept_synonym AS cs
                            WHERE cs.concept_id = c.concept_id
                              AND cs.concept_synonym_name ILIKE %s
                        )
                    )
                ORDER BY
                    CASE
                        WHEN LOWER(c.concept_name) = LOWER(%s) THEN 0
                        ELSE 1
                    END,
                    CASE
                        WHEN c.standard_concept = 'S' THEN 0
                        ELSE 1
                    END,
                    c.concept_name,
                    c.concept_id
                LIMIT %s;
                """,
                (
                    f"%{term}%",
                    normalized_code,
                    f"%{term}%",
                    term,
                    limit
                )
            )

            columns = [column.name for column in cur.description]

            return [
                dict(zip(columns, row))
                for row in cur.fetchall()
            ]


def get_standard_mappings(concept_id: int) -> list[dict]:

    # Retrieve valid OMOP 'Maps to' relationships from a source concept to standard concepts.

    if not isinstance(concept_id, int) or isinstance(concept_id, bool):
        raise ValueError("concept_id must be an integer.")

    db_config = st.secrets["connections"]["omop"]

    with psycopg.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["database"],
        user=db_config["username"],
        password=db_config["password"],
        options="-c default_transaction_read_only=on"
    ) as conn:

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT
                    c.concept_id,
                    c.concept_name,
                    c.vocabulary_id,
                    c.domain_id,
                    c.standard_concept
                FROM cdm.concept_relationship AS cr
                JOIN cdm.concept AS c
                    ON cr.concept_id_2 = c.concept_id
                WHERE cr.concept_id_1 = %s
                  AND cr.relationship_id = 'Maps to'
                  AND cr.invalid_reason IS NULL
                  AND c.invalid_reason IS NULL
                  AND c.standard_concept = 'S';
                """,
                (concept_id,)
            )

            columns = [column.name for column in cur.description]

            return [
                dict(zip(columns, row))
                for row in cur.fetchall()
            ]