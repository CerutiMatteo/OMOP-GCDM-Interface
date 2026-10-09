import psycopg
import streamlit as st

# RECUPERIAMO I PARAMETRI PER CONNESSIONE AL DB
db_config = st.secrets["connections"]["omop"]

# APRIAMO CONNESSIONE (SOLA LETTURA)
conn = psycopg.connect(host=db_config["host"], port=db_config["port"], dbname=db_config["database"], user=db_config["username"], password=db_config["password"], options="-c default_transaction_read_only=on")
print("Connessione al database riuscita")

# CREAZIONE 'CURSORE' PER INTERROGARE IL DB
cur = conn.cursor()

# RETRIVE AND PRINT COLUMN NAMES FROM THE DB
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'cdm'
      AND table_type = 'BASE TABLE'
    ORDER BY table_name;
""")

tables = cur.fetchall() # retrieve rows returned by the query

for table in tables:
    print(table[0]) # one column for each row

# RETRIEVE COLUMNS FROM ALL TABLES
for table in tables:
    table_name = table[0]

    print(f"\nTabella: {table_name}")

    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'cdm'
          AND table_name = %s
        ORDER BY ordinal_position;
    """, (table_name,))

    columns = cur.fetchall() # retrieve rows returned by the query

    for column in columns:
        print(column[0], "-", column[1]) # column_name - data_type


# RETRIEVE PRIMARY KEYS FROM ALL TABLES
cur.execute("""
    SELECT
        tc.table_name,
        kcu.column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
       AND tc.constraint_schema = kcu.constraint_schema
       AND tc.table_name = kcu.table_name
    WHERE tc.table_schema = 'cdm'
      AND tc.constraint_type = 'PRIMARY KEY'
    ORDER BY tc.table_name, kcu.ordinal_position;
""")

primary_keys = cur.fetchall()

print("\nPRIMARY KEYS:")

for row in primary_keys:
    print(row[0], "->", row[1])

# RETRIEVE PRIMARY KEY COLUMNS FROM POSTGRESQL
cur.execute("""
    SELECT
        t.relname AS table_name,
        c.conname AS constraint_name,
        a.attname AS column_name
    FROM pg_catalog.pg_constraint AS c
    JOIN pg_catalog.pg_class AS t
        ON c.conrelid = t.oid
    JOIN pg_catalog.pg_namespace AS n
        ON t.relnamespace = n.oid
    JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS k(attnum, position)
        ON TRUE
    JOIN pg_catalog.pg_attribute AS a
        ON a.attrelid = t.oid
       AND a.attnum = k.attnum
    WHERE n.nspname = 'cdm'
      AND c.contype = 'p'
    ORDER BY t.relname, k.position;
""")

primary_key_columns = cur.fetchall()

print("\nPRIMARY KEY COLUMNS:")

for row in primary_key_columns:
    print(row[0], "->", row[2])

print("Numero di colonne PK trovate:", len(primary_key_columns))

# Chiudiamo il cursore
cur.close()