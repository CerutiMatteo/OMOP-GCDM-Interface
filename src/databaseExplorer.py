import pandas as pd
import streamlit as st
import os
import shutil

from graphviz import Source

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

    # Ensure Graphviz is available in the process PATH.
    graphviz_bin = os.path.expanduser(
        "~/.conda/envs/omop_interface/bin"
    )
    os.environ["PATH"] = (
            graphviz_bin + os.pathsep + os.environ.get("PATH", "")
    )

    st.title("📁 Database Explorer")

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

    # --------------------------------------------------
    # TABLE SELECTION
    # --------------------------------------------------

    st.subheader("Database Tables")

    table_names = sorted(schema.keys())

    allowed_tables = st.session_state["config"]["allowed_tables"]

    authorized_tables = [
        table for table in table_names
        if table in allowed_tables
    ]

    if not authorized_tables:
        st.warning(
            "No authorized tables available. "
            "Enable tables in Settings to use Database Explorer."
        )
        return

    # Persistent selection.
    if "explorer_selected_table" not in st.session_state:
        st.session_state["explorer_selected_table"] = None

    # Reset selection if authorization has been removed.
    if st.session_state["explorer_selected_table"] not in authorized_tables:
        st.session_state["explorer_selected_table"] = None

    # Restore the saved selection.
    def save_explorer_selection():
        st.session_state["explorer_selected_table"] = (
            st.session_state["explorer_table_selectbox"]
        )

    st.session_state["explorer_table_selectbox"] = (
        st.session_state["explorer_selected_table"]
    )

    selected_table = st.selectbox(
        "Select an authorized table",
        options=authorized_tables,
        index=None,
        placeholder="Select an authorized table...",
        key="explorer_table_selectbox",
        on_change=save_explorer_selection
    )

    if selected_table is None:
        st.info(
            "Select a table to explore its structure and relationships."
        )
        return

    # --------------------------------------------------
    # TABLE DETAILS
    # --------------------------------------------------

    table_info = schema[selected_table]

    st.subheader(f"Table: {selected_table}")

    st.write(
        f"Total columns: {len(table_info['columns'])}"
    )

    columns_data = []

    for column_name, data_type in table_info["columns"].items():

        is_primary_key = (
            column_name in table_info["primary_keys"]
        )

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

    # --------------------------------------------------
    # FOREIGN KEYS
    # --------------------------------------------------

    st.subheader("Foreign Keys")

    if table_info["foreign_keys"]:

        foreign_keys_df = pd.DataFrame(
            table_info["foreign_keys"]
        )

        foreign_keys_df = foreign_keys_df.rename(
            columns={
                "column": "Source Column",
                "references_table": "Referenced Table",
                "references_column": "Referenced Column"
            }
        )

        st.dataframe(
            foreign_keys_df,
            width="stretch",
            hide_index=True
        )

    else:
        st.info(
            "No PostgreSQL foreign keys defined for this table."
        )


    # --------------------------------------------------
    # DATABASE SCHEMA VISUALIZATION
    # --------------------------------------------------

    st.subheader("Database Schema")

    st.write("Visualize the selected table and its relationships with other tables in the database.")

    show_columns = st.radio(
        "Detail level",
        options=[
            "Tables and FK columns",
            "Tables only"
        ],
        horizontal=True,
        key="database_schema_detail_level"
    )

    # Find tables directly connected to the selected table.
    related_tables = set()

    for source_table, table_data in schema.items():
        for fk in table_data["foreign_keys"]:
            target_table = fk["references_table"]

            if source_table == selected_table:
                related_tables.add(target_table)

            elif target_table == selected_table:
                related_tables.add(source_table)

    # The main table is always displayed.
    related_tables.discard(selected_table)
    related_tables = sorted(related_tables)

    # Select which related tables to display.
    visible_tables = st.multiselect(
        "Related tables to display",
        options=related_tables,
        default=related_tables,
        key=f"explorer_related_tables_{selected_table}",
        help="Remove tables to hide them from the relationship diagram."
    )


    try:
        with st.spinner(
            f"Rendering relationship diagram for {selected_table}...",
            show_time=True
        ):
            diagram = visualize_database_schema(
                schema=schema,
                selected_table=selected_table,
                show_columns=(
                        show_columns == "Tables and FK columns"
                ),
                visible_tables=visible_tables
            )

            # Render the diagram on the server as PNG.
            png_data = Source(diagram.source).pipe(
                format="png"
            )

        # Display the completed diagram.
        st.image(
            png_data,
            width="stretch"
        )

    except Exception as e:
        st.error(
            f"Unable to generate database schema diagram: {e}"
        )


