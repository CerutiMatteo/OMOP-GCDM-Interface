import streamlit as st
from google import genai

from schemaMetadata import get_database_schema
from schemaFormatter import format_schema_for_llm


def generate_sql(question):
    # Retrieve the database schema.
    schema = get_database_schema()

    # Select the tables for the initial Text-to-SQL prototype.
    selected_tables = [
        "person",
        "specimen",
        "variant_occurrence",
        "target_gene",
        "variant_annotation"
    ]

    # Convert schema metadata into a readable text representation.
    schema_text = format_schema_for_llm(schema, selected_tables)

    # Build the prompt for the language model.
    prompt = f"""
    You are an expert in PostgreSQL and the OMOP G-CDM database.

    Generate a PostgreSQL SELECT query that answers the user's question.

    Use only the tables and columns provided in the database schema.
    Use the provided relationships to construct JOIN operations.
    Do not invent tables, columns, or relationships.
    Do not generate INSERT, UPDATE, DELETE, DROP, or other modifying statements.

    If the question cannot be answered using the provided schema,
    respond with CANNOT_GENERATE_SQL.

    DATABASE SCHEMA:
    {schema_text}

    USER QUESTION:
    {question}

    Return only the SQL query, without explanations or Markdown formatting.
    """

    # Initialize the Gemini client.
    client = genai.Client(
        api_key=st.secrets["gemini"]["api_key"]
    )

    # Generate SQL using Gemini.
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    return response.text

#TEST
if __name__ == "__main__":
    question = "How many patients are present in the database?"

    sql = generate_sql(question)

    print("Generated SQL:")
    print(sql)