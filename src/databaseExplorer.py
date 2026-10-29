import streamlit as st
import pandas as pd

from .schemaMetadata import get_database_schema
from .databaseSchemaVisualizer import visualize_database_schema


@st.cache_data(show_spinner=False)
def load_database_schema():
    """
    Load and cache the database schema metadata.
    """
    return get_database_schema()


def render_database_explorer():
    """
    Render the Database Explorer page.
    """

    st.title("🗂️ Database Explorer")
    st.write(
        "Explore the structure of the OMOP G-CDM database, "
        "including tables, columns, keys and relationships."
    )

    # Load database metadata.
    try:
        with st.spinner("Loading database schema..."):
            schema = load_database_schema()
    except Exception as e:
        st.error(f"Unable to load database schema: {e}")
        return

    if not schema:
        st.warning("No tables found in the database.")
        return

    # Table selection.
    st.subheader("Database Tables")

    table_names = sorted(schema.keys())

    selected_table = st.selectbox(
        "Select a table",
        options=table_names,
        key="database_explorer_selected_table"
    )

    # Retrieve metadata for the selected table.
    table_info = schema[selected_table]

    st.subheader(f"Table: {selected_table}")

    st.write(f"Total columns: {len(table_info['columns'])}")

    # Build the columns metadata table.
    columns_data = []

    for column_name, data_type in table_info["columns"].items():
        is_primary_key = column_name in table_info["primary_keys"]

        is_foreign_key = any(
            fk["column"] == column_name
            for fk in table_info["foreign_keys"]
        )

        columns_data.append({
            "Column": column_name,
            "Data Type": data_type,
            "Primary Key": is_primary_key,
            "Foreign Key": is_foreign_key
        })

    columns_df = pd.DataFrame(columns_data)

    st.dataframe(
        columns_df,
        width="stretch",
        hide_index=True
    )

    # Display PostgreSQL foreign keys.
    st.subheader("Foreign Keys")

    if table_info["foreign_keys"]:

        foreign_keys_df = pd.DataFrame(
            table_info["foreign_keys"]
        )

        st.dataframe(
            foreign_keys_df,
            width="stretch",
            hide_index=True
        )

    else:
        st.info("No PostgreSQL foreign keys defined for this table.")



    # Database schema visualization.
    st.subheader("Database Schema")

    st.write(
        "Visualize the selected table and its relationships "
        "with other tables in the database."
    )

    show_columns = st.radio(
        "Detail level",
        options=[
            "Tables and FK columns",
            "Tables only"
        ],
        horizontal=True,
        key="database_schema_detail_level"
    )

    diagram = visualize_database_schema(
        schema=schema,
        selected_table=selected_table,
        show_columns=(show_columns == "Tables and FK columns")
    )

    st.graphviz_chart(
        diagram.source,
        width="stretch"
    )

