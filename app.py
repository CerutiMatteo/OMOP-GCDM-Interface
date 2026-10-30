import streamlit as st
import psycopg
import pandas as pd
from datetime import datetime
from pathlib import Path
import json
import streamlit.components.v1 as components

from src.sqlExecutor import execute_sql
from src.textToSQL import generate_sql
from src.configManager import load_config, save_config
from src.historyManager import load_history, save_history, export_history, import_history
from src.configManager import get_supported_tables
from src.configManager import get_next_query_id, increment_next_query_id
from src.visualQueryComponents import render_visual_editor
from src.queryAnalyzer import analyze_query
from src.schemaVisualizer import visualize_query_structure
from src.databaseExplorer import render_database_explorer

#INITIALIZATION

# Configure the Streamlit page.
st.set_page_config(page_title="OMOP G-CDM Interface", page_icon="🧬", layout="wide", initial_sidebar_state="expanded")

# Customize the hover colors of the Query History buttons.

st.markdown("""
<style>
    /* Clear - Red */
    .st-key-clear_query_history button:hover {
        color: #FF4B4B !important;
    }

    /* Save - Green */
    .st-key-save_query_history button:hover {
        color: #00A86B !important;
    }

    /* Load - Blue */
    .st-key-load_query_history button:hover {
        color: #2196F3 !important;
    }

    /* Individual Delete buttons: red text and icon on hover */
    div[class*="st-key-delete_query_"] button:hover {
        color: #FF4B4B !important;
        border-color: #FF4B4B !important;
    }

    div[class*="st-key-delete_query_"] button:hover p,
    div[class*="st-key-delete_query_"] button:hover span,
    div[class*="st-key-delete_query_"] button:hover svg {
        color: #FF4B4B !important;
        stroke: #FF4B4B !important;
    }

    /* Confirmation dialog Delete button - Red */
    .st-key-confirm_delete_single_query button {
        background-color: #D32F2F !important;
        border-color: #D32F2F !important;
        color: #FFFFFF !important;
    }

    /* Confirmation dialog Delete button - Darker red on hover */
    .st-key-confirm_delete_single_query button:hover {
        background-color: #B71C1C !important;
        border-color: #B71C1C !important;
        color: #FFFFFF !important;
    }

    /* Keep confirmation button text and icon white */
    .st-key-confirm_delete_single_query button p,
    .st-key-confirm_delete_single_query button span,
    .st-key-confirm_delete_single_query button svg {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

</style>
""", unsafe_allow_html=True)

# Customize the Query Editor and Query History panels.
st.markdown(
    """
    <style>
    /* Query Editor panel */
    .st-key-query_editor_panel {
        background-color: #171717;
        color: #F5F5F5;
        border: 1px solid #333333;
        border-radius: 12px;
        padding: 18px;
    }

    /* Query Editor headings, descriptions and labels */
    .st-key-query_editor_panel h1,
    .st-key-query_editor_panel h2,
    .st-key-query_editor_panel h3,
    .st-key-query_editor_panel label,
    .st-key-query_editor_panel [data-testid="stMarkdownContainer"] p,
    .st-key-query_editor_panel [data-testid="stMarkdownContainer"] strong {
        color: #F5F5F5 !important;
        -webkit-text-fill-color: #F5F5F5 !important;
    }

    /* Input fields: dark text on light background */
    .st-key-query_editor_panel input,
    .st-key-query_editor_panel textarea {
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }

    /* Code blocks: preserve readability on light background */
    .st-key-query_editor_panel [data-testid="stCodeBlock"] pre,
    .st-key-query_editor_panel [data-testid="stCodeBlock"] code {
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }

    /* Query History expander */
    div[data-testid="stExpanderDetails"] {
        background-color: #171717 !important;
        color: #F5F5F5 !important;
        padding: 20px !important;
        border-radius: 0 0 10px 10px;
    }

    /* Query History text */
    div[data-testid="stExpanderDetails"] p,
    div[data-testid="stExpanderDetails"] label {
        color: #F5F5F5 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Customize the Download CSV button.
st.markdown("""
<style>
    div[class*="st-key-download_history_"] button {
        background-color: #262730 !important;
        color: #FFFFFF !important;
        border: 1px solid #444444 !important;
    }

    div[class*="st-key-download_history_"] button:hover {
        background-color: #363945 !important;
        color: #FFFFFF !important;
    }

    div[class*="st-key-download_history_"] button p {
        color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)

# Load the saved application configuration.
if "config" not in st.session_state:
    st.session_state["config"] = load_config()

# Restore the saved query history.
if "query_history" not in st.session_state:
    st.session_state["query_history"] = load_history()

# Assign IDs to queries that do not have one.
history = st.session_state["query_history"]

existing_ids = {
    item["id"] for item in history if "id" in item
}

next_id = max(existing_ids, default=0) + 1

for item in history:
    if "id" not in item:
        item["id"] = next_id
        existing_ids.add(next_id)
        next_id += 1

# Synchronize the persistent counter.
highest_id = max(
    (item["id"] for item in history),
    default=0
)

config = load_config()

if config["next_query_id"] <= highest_id:
    config["next_query_id"] = highest_id + 1
    save_config(config)

# Initialize the question input counter.
if "question_number" not in st.session_state:
    st.session_state["question_number"] = len(st.session_state["query_history"])
# Initialize settings from the saved configuration.
if "developer_mode" not in st.session_state:
    st.session_state["developer_mode"] = (st.session_state["config"]["programmer_mode"])
if "max_rows" not in st.session_state:
    st.session_state["max_rows"] = (st.session_state["config"]["max_rows"])
# Keep history expanders collapsed on application startup.
if "collapse_history" not in st.session_state:
    st.session_state["collapse_history"] = True
# Initialize the query editor mode.
if "query_editor_mode" not in st.session_state:
    st.session_state["query_editor_mode"] = "Visual Editor"
# Track visual editor widget versions.
if "visual_editor_version" not in st.session_state:
    st.session_state["visual_editor_version"] = 0

# Create the sidebar navigation menu.
with st.sidebar:
    st.title("📋 OMOP G-CDM")

    page = st.radio(
        "Menu:",
        [
            "💬 Query Interface",
            "🔍 Database Explorer",
            "⚙️ Settings",
            "🛠️ Diagnostics"
        ]
    )

# Read the PostgreSQL connection settings from Streamlit secrets.
db_config = st.secrets["connections"]["omop"]

# Create a read-only connection to the PostgreSQL database.
def connect_db():
    return psycopg.connect(
        host=db_config["host"],
        port=db_config["port"],
        dbname=db_config["database"],
        user=db_config["username"],
        password=db_config["password"],
        options="-c default_transaction_read_only=on"
    )

##############################################################################################

# MAIN PAGE:

if page == "💬 Query Interface":

    st.title("🧬 OMOP G-CDM Interface")
    st.write("Natural language interface for querying the OMOP G-CDM database.")

    st.markdown('<div id="new-question"></div>', unsafe_allow_html=True)

    st.subheader("Question & SQL Generation")

    # Create a new input field after each completed query.
    st.write("Enter a question about clinical and genomic data:")

    col_input, col_button = st.columns([5, 1], gap="small", vertical_alignment="bottom")

    with col_input:
        question = st.text_input(
            "Question",
            placeholder="Ask a question about the OMOP G-CDM database...",
            key=f"question_input_{st.session_state['question_number']}",
            label_visibility="collapsed"
        )

    with col_button:
        generate_clicked = st.button("Generate Query", icon=":material/send:", use_container_width=True)

    if generate_clicked:

        # Collapse previous results when generating a new query.
        st.session_state["collapse_history"] = True

        if question.strip():

            # Create a placeholder for API overload messages.
            retry_message = st.empty()


            # Update the interface when Gemini is overloaded.
            def show_retry(attempt, delay):
                retry_message.warning("The AI model used to generate SQL query queries is currently experiencing high demand. Query generation may take longer than usual." f"Retrying automatically...")

            with st.spinner("Generating SQL query..."):
                try:
                    # Generate SQL query using Gemini with automatic retries.
                    sql = generate_sql(question, on_retry=show_retry)

                    # Clear the overload message after success.
                    retry_message.empty()

                    if sql.strip() == "CANNOT_GENERATE_SQL":
                        st.error("Unable to generate SQL query for this question. Please try rephrasing your request.")
                        st.session_state.pop("generated_sql", None)

                    else:
                        # Save the generated query across Streamlit
                        # reruns.
                        st.session_state["generated_sql"] = sql
                        st.session_state["editable_sql"] = sql

                        # Reset the editors for the new query.
                        st.session_state["query_editor_mode"] = "Visual Editor"
                        st.session_state["previous_query_editor_mode"] = None
                        st.session_state["visual_editor_version"] += 1

                        # Save the question associated with the generated SQL.
                        st.session_state["generated_question"] = question

                        if st.session_state.get("developer_mode", False):
                            st.rerun()

                        else:

                            # Automatically execute the query in standard mode.
                            try:
                                with st.spinner("Executing SQL query..."):
                                    # Open the read-only PostgreSQL connection.
                                    with connect_db() as conn:
                                        df = execute_sql(sql, conn, max_rows=st.session_state.get("max_rows", 1000))

                                    # Save the query and its results to the history.
                                    query_id = get_next_query_id()

                                    st.session_state["query_history"].append({
                                        "id": query_id,
                                        "question": question,
                                        "sql": sql,
                                        "results": df.copy()
                                    })

                                    save_history(st.session_state["query_history"])
                                    increment_next_query_id()

                                    # Clear the pending query.
                                    st.session_state.pop("generated_sql", None)
                                    st.session_state.pop("generated_question", None)

                                    # Expand the latest result.
                                    st.session_state["collapse_history"] = False
                                    st.session_state["history_version"] = (st.session_state.get("history_version", 0) + 1)

                                    # Prepare a new empty question input.
                                    st.session_state["question_number"] += 1

                                # Refresh the page to display the results.
                                st.rerun()

                            except Exception as e:
                                st.error(f"Query execution failed: {e}")

                except Exception as e:
                    # Clear the overload message after failure.
                    retry_message.empty()
                    st.session_state.pop("generated_sql", None)
                    error_message = str(e).lower()
                    if (
                            "503" in error_message
                            or "unavailable" in error_message
                            or "high demand" in error_message
                            or "resource_exhausted" in error_message
                            or "429" in error_message
                    ):
                        st.warning("The AI model used to convert natural language into SQL is currently experiencing high demand. Please wait a moment and try again.")
                    else:
                        st.error("An unexpected error occurred while generating the SQL query.")
                        st.exception(e)

        else:
            st.warning("Please enter a question.")

    # Display the query editors only in Programmer Mode.
    if (st.session_state.get("developer_mode", False) and "generated_sql" in st.session_state):

        with st.container(border=True, key="query_editor_panel"):

            title_col, mode_col = st.columns([3, 1], vertical_alignment="center")

            with title_col:
                st.subheader("Query Editor")

            with mode_col:
                st.markdown(":material/terminal: &nbsp; Programmer Mode")

            previous_mode = st.session_state.get("previous_query_editor_mode", None,)

            editor_mode = st.radio(
                "Query Editor Mode",
                ["Visual Editor", "SQL Editor"],
                key="query_editor_mode",
                horizontal=True,
                label_visibility="collapsed",
            )

            if (
                    editor_mode == "Visual Editor"
                    and previous_mode != "Visual Editor"
            ):
                st.session_state["visual_editor_version"] += 1

            st.session_state["previous_query_editor_mode"] = editor_mode

            if editor_mode == "Visual Editor":

                render_visual_editor()

            else:

                st.text_area(
                    "SQL Query",
                    key="editable_sql",
                    height=250,
                    label_visibility="collapsed",
                    help="Review and modify the SQL query before execution.",
                )

    # Execute the SQL query generated by Gemini.
    if (st.session_state.get("developer_mode", False) and "generated_sql" in st.session_state):
        if st.button("Run Query", key="run_generated_query"):
            try:
                with st.spinner("Executing SQL query..."):

                    # Retrieve the SQL reviewed and edited by the programmer.
                    sql = st.session_state["editable_sql"].strip()

                    if not sql:
                        st.error("SQL query cannot be empty.")
                        st.stop()

                    # Open the read-only PostgreSQL connection.
                    with connect_db() as conn:
                        # Validate and execute the generated query.
                        df = execute_sql(sql, conn, max_rows=st.session_state.get("max_rows", 1000))

                    # Save the completed query with a permanent ID.
                    query_id = get_next_query_id()

                    st.session_state["query_history"].append({
                        "id": query_id,
                        "question": st.session_state["generated_question"],
                        "sql": sql,
                        "results": df.copy()
                    })

                    # Persist the updated query history.
                    save_history(st.session_state["query_history"])
                    increment_next_query_id()

                    # Clear the pending query and SQL editor.
                    st.session_state.pop("generated_sql", None)
                    st.session_state.pop("generated_question", None)
                    st.session_state.pop("editable_sql", None)

                    # Expand the latest result after successful execution.
                    st.session_state["collapse_history"] = False
                    st.session_state["history_version"] = (st.session_state.get("history_version", 0) + 1)

                    # Prepare a new empty question input.
                    st.session_state["question_number"] += 1

                # Refresh the interface.
                st.rerun()

            except Exception as e:
                st.error(f"Query execution failed: {e}")


    @st.dialog("Delete Query")
    def confirm_delete_query(index):

        st.warning(
            "Are you sure you want to delete this query from the history? "
            "This action cannot be undone."
        )

        col_cancel, col_delete = st.columns(2)

        with col_cancel:
            if st.button("Cancel", use_container_width=True):
                st.rerun()

        with col_delete:
            if st.button(
                    "Delete Query",
                    icon=":material/delete_outline:",
                    type="primary",
                    key="confirm_delete_single_query",
                    use_container_width=True
            ):
                # Create an updated history without the selected query.
                updated_history = (
                        st.session_state["query_history"][:index]
                        + st.session_state["query_history"][index + 1:]
                )

                # Persist the updated history.
                save_history(updated_history)

                # Update session history.
                st.session_state["query_history"] = updated_history

                # Refresh the history expanders.
                st.session_state["history_version"] = (
                        st.session_state.get("history_version", 0) + 1
                )

                # Keep the remaining results collapsed.
                st.session_state["collapse_history"] = True

                st.rerun()

    @st.dialog("Clear Query History")
    def confirm_clear_history():

        st.warning("Are you sure you want to delete your entire query history? This action cannot be undone.")

        col_cancel, col_confirm = st.columns(2)

        with col_cancel:
            if st.button("Cancel", use_container_width=True):
                st.rerun()

        with col_confirm:
            if st.button("Delete History", icon=":material/delete_outline:", type="primary", use_container_width=True):
                # Clear persistent history.
                save_history([])

                # Clear session history.
                st.session_state["query_history"] = []

                # Reset question counter.
                st.session_state["question_number"] = 0

                # Remove pending SQL.
                st.session_state.pop("generated_sql", None)
                st.session_state.pop("generated_question", None)

                # Reset history display.
                st.session_state["collapse_history"] = True
                st.session_state["history_version"] = (st.session_state.get("history_version", 0) + 1)

                st.rerun()

    @st.dialog("Save Query History")
    def confirm_save_history():

        config = st.session_state["config"]

        # Generate a default filename.
        default_filename = datetime.now().strftime("history%Y%m%d%H%M%S.json")

        # Get the directory configured in History Settings.
        save_directory = Path(config["history_path"]).parent

        # Display information about the export.
        st.write("Save a copy of the current query history, including questions, generated SQL queries and results.")

        # Allow the user to customize the filename.
        filename = st.text_input("File Name", value=default_filename, key="history_export_filename")

        # Display the fixed destination directory.
        st.info(f"📁 The file will be saved in: **{save_directory}**")

        col_cancel, col_save = st.columns(2)

        with col_cancel:
            if st.button("Cancel", key="cancel_history_export", use_container_width=True):
                st.rerun()

        with col_save:
            if st.button("Save History", icon=":material/save:", key="confirm_history_export", type="primary", use_container_width=True):
                try:
                    destination = export_history(st.session_state["query_history"], filename, str(save_directory))
                    st.session_state["history_export_success"] = (f"History saved successfully to: {destination}")
                    st.rerun()
                except (ValueError, OSError) as e:
                    st.error(str(e))


    @st.dialog("Load Query History")
    def confirm_load_history():
        st.write("Select a previously saved history file to restorequestions, generated SQL queries and results.")
        uploaded_file = st.file_uploader("Select History File", type=["json"], key="history_import_file")
        col_cancel, col_load = st.columns(2)
        
        with col_cancel:
            if st.button("Cancel", key="cancel_history_import", use_container_width=True):
                st.rerun()

        with col_load:
            if st.button("Load History", icon=":material/folder_open:", key="confirm_history_import", type="primary", disabled=uploaded_file is None, use_container_width=True            ):
                try:
                    
                    imported_history = import_history(uploaded_file.getvalue())
                    max_history = st.session_state["config"]["max_history"]
                    
                    if len(imported_history) > max_history:
                        st.warning(f"The file contains {len(imported_history)} queries. " f"Only the most recent {max_history} will be restored.")

                    restored_history = imported_history[-max_history:]

                    # Synchronize the counter with imported query IDs.
                    highest_imported_id = max(
                        (item["id"] for item in restored_history),
                        default=0
                    )

                    config = load_config()

                    if config["next_query_id"] <= highest_imported_id:
                        config["next_query_id"] = highest_imported_id + 1
                        save_config(config)

                    # Persist the imported history.
                    save_history(restored_history)

                    # Update session state only after a successful save.
                    st.session_state["query_history"] = restored_history

                    st.session_state["question_number"] = len(restored_history)

                    st.session_state.pop("generated_sql", None)
                    st.session_state.pop("generated_question", None)

                    # Keep expanders closed after importing.
                    st.session_state["collapse_history"] = True
                    st.session_state["history_version"] = (st.session_state.get("history_version", 0) + 1)

                    st.session_state["history_import_success"] = (f"Successfully loaded {len(restored_history)} queries.")

                    st.rerun()

                except (ValueError, UnicodeError, OSError, TypeError) as e:
                    st.error(f"Unable to load history: {e}")


    if "history_export_success" in st.session_state:
        st.success(st.session_state.pop("history_export_success"))


    # QUERY HISTORY

    st.subheader("Query History")

    if st.session_state["query_history"]:

        # Clear and Save buttons.
        col_clear, col_save, col_space = st.columns([1, 1, 6], gap="small")

        with col_clear:
            if st.button("Clear", icon=":material/delete_outline:", type="tertiary", key="clear_query_history", use_container_width=True):
                confirm_clear_history()

        with col_save:
            if st.button("Save", icon=":material/save:", type="tertiary", key="save_query_history", use_container_width=True):
                confirm_save_history()

        for index, item in enumerate(st.session_state["query_history"]):

            # Expand the latest result only when no new SQL is pending.
            is_latest = index == len(st.session_state["query_history"]) - 1

            with st.expander(
                    f"Question {item['id']} — {item['question']}",
                    expanded=(
                            is_latest
                            and not st.session_state["collapse_history"]
                            and "generated_sql" not in st.session_state
                    ),
                    key=f"history_{item['id']}"
            ):

                # Header with title and Delete button.
                col_title, col_delete = st.columns(
                    [5, 1],
                    vertical_alignment="center"
                )
                with col_title:
                    if st.session_state.get("developer_mode", False):
                        st.subheader("Generated Query")
                    else:
                        st.subheader("Query Results")
                with col_delete:
                    if st.button(
                            "Delete",
                            icon=":material/delete_outline:",
                            key=f"delete_query_{item['id']}",
                            type="tertiary",
                            use_container_width=True
                    ):
                        confirm_delete_query(index)

                # Display executed SQL in Programmer Mode.
                if st.session_state.get("developer_mode", False):
                    st.code(item["sql"], language="sql")

                # Display the query results.
                if st.session_state.get("developer_mode", False):
                    st.subheader("Query Results")

                df = item["results"]

                st.dataframe(
                    df,
                    width="stretch",
                    hide_index=True
                )

                st.write(f"Total rows: {len(df)}")

                # Allow the user to download the results.
                st.download_button(label="Download Table (.CSV)", data=df.to_csv(index=False).encode("utf-8-sig"), file_name=f"query_results_{item['id']}.csv", mime="text/csv", key=f"download_history_{item['id']}")

                # Query tables relationships
                st.subheader("Query Table Relationships")
                try:
                    # Analyze the SQL query that was actually executed.
                    query_analysis = analyze_query(item["sql"])
                    # Generate the diagram using Graphviz.
                    diagram = visualize_query_structure(query_analysis)
                    # Adjust the diagram width based on the number of tables.
                    table_count = len(query_analysis["tables"])
                    if table_count == 1:
                        diagram_width = 300
                    elif table_count == 2:
                        diagram_width = 500
                    else:
                        diagram_width = 800
                    # Display the diagram.
                    st.graphviz_chart(diagram.source,width=diagram_width)
                except Exception as e:
                    st.warning(f"Unable to visualize query table relationships: {e}")

        # Return to the question input and automatically focus the text field
        components.html(
            """
            <style>
                body {
                    margin: 0;
                    padding: 0;
                    background: transparent;
                    font-family: "Source Sans Pro", sans-serif;
                }

                .new-question-button {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                padding: 0.5rem 0.75rem;
                background-color: #262730;
                color: white;
                border: 1px solid #262730;
                border-radius: 0.5rem;
                font-size: 0.875rem;
                font-weight: 400;
                cursor: pointer;
                transition: background-color 0.2s, border-color 0.2s;
            }

            .new-question-button:hover {
                background-color: #363945;
                border-color: #363945;
                color: white;
            }
            </style>

            <button class="new-question-button" onclick="focusQuestion()">
                New Question
            </button>

            <script>
                function focusQuestion() {
                    const input = window.parent.document.querySelector(
                        '[class*="st-key-question_input_"] input'
                    );

                    if (input) {
                        input.focus();
                        input.scrollIntoView({
                            behavior: "smooth",
                            block: "center"
                        });
                    }
                }
            </script>
            """,
            height=45
        )

    else:

        # Show Load only when history is empty.
        col_load, col_space = st.columns([1, 7], gap="small")

        with col_load:
            if st.button("Load", icon=":material/folder_open:", type="tertiary", key="load_query_history", use_container_width=True):
                confirm_load_history()


##############################################################################################

# DATABASE EXPLORER:

elif page == "🔍 Database Explorer":

    render_database_explorer()


##############################################################################################

# SETTINGS:

elif page == "⚙️ Settings":

    st.title("⚙️ Settings")

    st.write("Configure application behavior, SQL generation, query results, and database access.")

    # Save a validated configuration update.
    def update_setting(name, value):

        updated_config = load_config()
        updated_config[name] = value

        try:
            save_config(updated_config)
            st.session_state["config"] = updated_config
            return True

        except (ValueError, OSError) as e:
            st.error(f"Unable to save settings: {e}")
            return False

    # Save Programmer Mode.
    def save_programmer_mode():

        enabled = st.session_state["programmer_mode_input"]

        if update_setting("programmer_mode", enabled):
            st.session_state["developer_mode"] = enabled

    # Save the maximum row limit.
    def save_max_rows():

        value = st.session_state["max_rows_input"]

        if update_setting("max_rows", value):
            st.session_state["max_rows"] = value

    # save max number of questions in history
    def save_max_history():
        value = st.session_state["max_history_input"]

        if update_setting("max_history", value):
            st.session_state["query_history"] = (st.session_state["query_history"][-value:])
            save_history(st.session_state["query_history"])

    # Save Automatic Retry.
    def save_automatic_retry():

        value = st.session_state["automatic_retry_input"]
        update_setting("automatic_retry", value)

    # Save Maximum Retries.
    def save_max_retries():

        value = st.session_state["max_retries_input"]
        update_setting("max_retries", value)

    # Save Retry Delay.
    def save_retry_delay():

        value = st.session_state["retry_delay_input"]
        update_setting("retry_delay_seconds", value)

    # Save Allowed Tables.
    def save_allowed_tables():

        selected_tables = st.session_state["allowed_tables_input"]

        if not selected_tables:
            st.error("At least one table must be selected.")
            return

        update_setting("allowed_tables", selected_tables)


    # PROGRAMMER SETTINGS
    st.subheader("Programmer Settings")
    st.toggle("Programmer Mode", value=st.session_state["config"]["programmer_mode"], key="programmer_mode_input", on_change=save_programmer_mode, help="Show generated SQL queries and technical details.")
    st.divider()


    # QUERY RESULTS SETTINGS
    st.subheader("Query Results Settings")
    st.number_input("Maximum Number of Rows", min_value=1, max_value=10000, step=1, value=st.session_state["config"]["max_rows"], key="max_rows_input", on_change=save_max_rows, help="Maximum number of rows returned by a database query.")
    st.divider()


    # HISTORY SETTINGS
    st.subheader("History Settings")
    st.number_input("Maximum Saved Queries", min_value=10, max_value=500, step=10, value=st.session_state["config"]["max_history"], key="max_history_input", on_change=save_max_history, help="Maximum number of queries stored in history.")
    st.divider()


    # SQL GENERATION SETTINGS
    st.subheader("SQL Generation Settings")
    st.toggle("Automatic Retry", value=st.session_state["config"]["automatic_retry"], key="automatic_retry_input", on_change=save_automatic_retry, help="Automatically retry SQL generation after temporary errors.")
    st.number_input("Maximum Retries", min_value=1, max_value=10, step=1, value=st.session_state["config"]["max_retries"], key="max_retries_input", on_change=save_max_retries, disabled=not st.session_state["config"]["automatic_retry"], help="Number of additional attempts after the initial request.")
    st.number_input("Retry Delay (seconds)", min_value=1, max_value=60, step=1, value=st.session_state["config"]["retry_delay_seconds"], key="retry_delay_input", on_change=save_retry_delay, disabled=not st.session_state["config"]["automatic_retry"], help="Fixed waiting time between retry attempts.")
    st.divider()


    # DATABASE ACCESS SETTINGS
    st.subheader("Database Access Settings")
    st.write("Select which database tables can be used when generating and executing SQL queries.")
    st.multiselect(
        "Allowed Tables",
        options=sorted(get_supported_tables()),
        default=st.session_state["config"]["allowed_tables"],
        key="allowed_tables_input",
        on_change=save_allowed_tables,
        help="Select which database tables can be used for SQL queries."
    )
    st.divider()
    st.caption("Settings are saved automatically to config/settings.json.")


##############################################################################################

# DIAGNOSTICS:

elif page == "🛠️ Diagnostics":

    st.title("🛠️ Diagnostics")


    # Test the PostgreSQL connection.
    st.subheader("Database Connection")
    if st.button("Test Database Connection"):
        try:
            # Open a read-only PostgreSQL connection.
            with connect_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM cdm.person;")
                    patient_count = cur.fetchone()[0]
            st.success("Database connection successful!")
            st.write(f"Total patients: {patient_count}")
        except psycopg.Error as e:
            st.error("Database connection failed.")
            st.error(str(e))
    st.divider()

    # Test the execution of a predefined SQL query.
    st.subheader("SQL Execution Test")
    st.write("Execute a predefined SQL query to verify that PostgreSQL returns the expected results.")

    if st.button("Run SQL Test"):
        try:
            # Open a read-only PostgreSQL connection.
            with connect_db() as conn:
                with conn.cursor() as cur:
                    # Execute a predefined SELECT query.
                    cur.execute("""
                        SELECT person_id, gender_concept_id, year_of_birth
                        FROM cdm.person
                        LIMIT 100;
                    """)
                    # Retrieve column names and query results.
                    columns = [column.name for column in cur.description]
                    rows = cur.fetchall()
            # Convert query results into a DataFrame.
            df = pd.DataFrame(rows, columns=columns)

            st.success("SQL query executed successfully!")

            # Display the results as an interactive table.
            st.subheader("Query Results")
            st.dataframe(df, width="stretch")

            st.write(f"Total rows: {len(df)}")

            # Convert the DataFrame into a downloadable CSV file.
            csv_data = df.to_csv(index=False).encode("utf-8")

            st.download_button(label="Download CSV", data=csv_data, file_name="query_results.csv", mime="text/csv")

        except psycopg.Error as e:
            st.error("SQL query execution failed.")
            st.error(str(e))


    # Verify the PostgreSQL user's permissions.
    if st.button("Check Database Permissions"):
        try:
            with connect_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            current_user,
                            current_setting('default_transaction_read_only'),
                            has_table_privilege(
                                current_user, 'cdm.person', 'SELECT'
                            ),
                            has_table_privilege(
                                current_user, 'cdm.person', 'INSERT'
                            ),
                            has_table_privilege(
                                current_user, 'cdm.person', 'UPDATE'
                            ),
                            has_table_privilege(
                                current_user, 'cdm.person', 'DELETE'
                            );
                    """)

                    result = cur.fetchone()

            st.write("Database user:", result[0])
            st.write("Read-only default:", result[1])
            st.write("SELECT permission:", result[2])
            st.write("INSERT permission:", result[3])
            st.write("UPDATE permission:", result[4])
            st.write("DELETE permission:", result[5])

        except Exception as e:
            st.error(f"Permission check failed: {e}")

    # Check permissions on all authorized tables.
    if st.button("Check Authorized Tables"):

        tables = [
            "person",
            "specimen",
            "variant_occurrence",
            "target_gene",
            "variant_annotation",
        ]

        results = []

        try:
            with connect_db() as conn:
                with conn.cursor() as cur:
                    for table in tables:
                        # Check read and write privileges.
                        cur.execute(
                            """
                            SELECT
                                has_table_privilege(
                                    current_user, %s, 'SELECT'
                                ),
                                has_table_privilege(
                                    current_user, %s, 'INSERT'
                                ),
                                has_table_privilege(
                                    current_user, %s, 'UPDATE'
                                ),
                                has_table_privilege(
                                    current_user, %s, 'DELETE'
                                )
                            """,
                            tuple([f"cdm.{table}"] * 4)
                        )

                        permissions = cur.fetchone()

                        results.append({
                            "Table": table,
                            "SELECT": permissions[0],
                            "INSERT": permissions[1],
                            "UPDATE": permissions[2],
                            "DELETE": permissions[3],
                        })

            st.dataframe(
                pd.DataFrame(results),
                width="stretch"
            )

        except Exception as e:
            st.error(f"Permission check failed: {e}")
