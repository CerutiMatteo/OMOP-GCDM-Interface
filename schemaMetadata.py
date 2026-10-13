import psycopg
import streamlit as st

from logicalRelationships import LOGICAL_RELATIONSHIPS

def get_database_schema():
    # RETRIVE DB CONF
    db_config = st.secrets["connections"]["omop"]

    # DICTIONARY STRUCTURE
    schema = {}

    # READ-ONLY CONNECTION
    with psycopg.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["database"],
        user=db_config["username"],
        password=db_config["password"],
        options="-c default_transaction_read_only=on"
    ) as conn:

        with conn.cursor() as cur:

            # RETRIVE TABLES FROM cdm DB
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'cdm'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)

            tables = cur.fetchall()

            for table in tables:
                table_name = table[0]

                # RETRIVE COLUMNS FOR EACH TABLE
                cur.execute("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'cdm'
                      AND table_name = %s
                    ORDER BY ordinal_position;
                """, (table_name,))

                columns = cur.fetchall()

                # ADD INFORMATIONS INSIDE STRUCTURE schema
                schema[table_name] = {
                    "columns": {
                        column_name: data_type
                        for column_name, data_type in columns
                    },
                    "primary_keys": [],
                    "foreign_keys": [],
                    "logical_relationships": []
                }


            # RECUPERIAMO LE PRIMARY KEY
            cur.execute("""
                SELECT
                    t.relname AS table_name,
                    a.attname AS column_name
                FROM pg_catalog.pg_constraint AS c
                JOIN pg_catalog.pg_class AS t
                    ON c.conrelid = t.oid
                JOIN pg_catalog.pg_namespace AS n
                    ON t.relnamespace = n.oid
                JOIN LATERAL unnest(c.conkey)
                    WITH ORDINALITY AS k(attnum, position)
                    ON TRUE
                JOIN pg_catalog.pg_attribute AS a
                    ON a.attrelid = t.oid
                   AND a.attnum = k.attnum
                WHERE n.nspname = 'cdm'
                  AND c.contype = 'p'
                ORDER BY t.relname, k.position;
            """)

            primary_keys = cur.fetchall()

            # add PKs into schema dictionary
            for table_name, column_name in primary_keys:
                schema[table_name]["primary_keys"].append(column_name)


            # RETRIVE FOREIGN KEYS
            cur.execute("""
                SELECT
                    source_table.relname AS source_table,
                    source_column.attname AS source_column,
                    target_table.relname AS target_table,
                    target_column.attname AS target_column
                FROM pg_catalog.pg_constraint AS fk
                JOIN pg_catalog.pg_class AS source_table
                    ON fk.conrelid = source_table.oid
                JOIN pg_catalog.pg_namespace AS source_schema
                    ON source_table.relnamespace = source_schema.oid
                JOIN pg_catalog.pg_class AS target_table
                    ON fk.confrelid = target_table.oid
                JOIN LATERAL unnest(fk.conkey, fk.confkey)
                    AS cols(source_attnum, target_attnum)
                    ON TRUE
                JOIN pg_catalog.pg_attribute AS source_column
                    ON source_column.attrelid = source_table.oid
                   AND source_column.attnum = cols.source_attnum
                JOIN pg_catalog.pg_attribute AS target_column
                    ON target_column.attrelid = target_table.oid
                   AND target_column.attnum = cols.target_attnum
                WHERE source_schema.nspname = 'cdm'
                  AND fk.contype = 'f'
                ORDER BY source_table.relname, fk.conname;
            """)

            foreign_keys = cur.fetchall()

            # add PostgreSQL FKs into schema dictionary
            for source_table, source_column, target_table, target_column in foreign_keys:
                schema[source_table]["foreign_keys"].append({
                    "column": source_column,
                    "references_table": target_table,
                    "references_column": target_column
                })

            # add relationships defined inside logicalRelationships -> LOGICAL_RELATIONSHIPS inside schema dictionary
            for relationship in LOGICAL_RELATIONSHIPS:
                source_table = relationship["source_table"]
                source_column = relationship["source_column"]
                target_table = relationship["target_table"]
                target_column = relationship["target_column"]

                if source_table not in schema or target_table not in schema:
                    raise ValueError(f"Tabella inesistente nella relazione: {relationship}")

                if (source_column not in schema[source_table]["columns"]
                        or target_column not in schema[target_table]["columns"]):
                    raise ValueError(f"Colonna inesistente nella relazione: {relationship}")

                schema[source_table]["logical_relationships"].append(relationship.copy())

    return schema

#TEST: ONLY WHEN WE RUN THIS FILE
if __name__ == "__main__":
    database_schema = get_database_schema()

    tables_to_inspect = [
        "person",
        "specimen",
        "variant_occurrence",
        "target_gene",
        "genomic_test",
        "genomic_test_target_gene",
        "procedure_occurrence"
    ]

    for table_name in tables_to_inspect:
        print(f"\n--- {table_name} ---")
        print("Colonne:", list(database_schema[table_name]["columns"].keys()))
        print("Primary keys:", database_schema[table_name]["primary_keys"])
        print("Foreign keys:", database_schema[table_name]["foreign_keys"])
        print("Relazioni logiche:", database_schema[table_name]["logical_relationships"])
