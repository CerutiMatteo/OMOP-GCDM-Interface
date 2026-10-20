import streamlit as st
import psycopg
import pandas as pd
from datetime import datetime
from pathlib import Path

from src.sqlExecutor import execute_sql
from src.textToSQL import generate_sql
from src.configManager import load_config, save_config
from src.historyManager import load_history, save_history, export_history, import_history

#INITIALIZATION

# Configure the Streamlit page.
st.set_page_config(
    page_title="OMOP G-CDM Interface",
    page_icon="🧬",
    layout="wide"
)

# Load the saved application configuration.
if "config" not in st.session_state:
    st.session_state["config"] = load_config()
# Restore the saved query history.
if "query_history" not in st.session_state:
    st.session_state["query_history"] = load_history()
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

# Create the sidebar navigation menu.
with st.sidebar:
    st.title("📋 OMOP G-CDM")

    page = st.radio(
        "Menu:",
        ["🔍 Interrogazione", "⚙️ Impostazioni", "🛠️ Diagnostica"]
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

if page == "🔍 Interrogazione":

    st.title("🧬 OMOP G-CDM Interface")
    st.write("Natural language interface for querying the OMOP G-CDM database.")

    st.subheader("Question & SQL Generation")

    # Create a new input field after each completed query.
    st.write("Enter a question about clinical and genomic data:")

    col_input, col_button = st.columns(
        [5, 1],
        gap="small",
        vertical_alignment="bottom"
    )

    with col_input:
        question = st.text_input(
            "Question",
            key=f"question_input_{st.session_state['question_number']}",
            label_visibility="collapsed"
        )

    with col_button:
        generate_clicked = st.button(
            "Generate Query",
            icon=":material/send:",
            use_container_width=True
        )

    if generate_clicked:

        # Collapse previous results when generating a new query.
        st.session_state["collapse_history"] = True
        st.session_state["history_version"] = (st.session_state.get("history_version", 0) + 1)

        if question.strip():

            # Create a placeholder for API overload messages.
            retry_message = st.empty()


            # Update the interface when Gemini is overloaded.
            def show_retry(attempt, delay):
                retry_message.warning(
                    "The AI model used to generate SQL query queries is currently "
                    "experiencing high demand. Query generation may take "
                    "longer than usual. "
                    f"Retrying automatically..."
                )


            with st.spinner("Generating SQL query..."):
                try:
                    # Generate SQL query using Gemini with automatic retries.
                    sql = generate_sql(
                        question,
                        on_retry=show_retry
                    )

                    # Clear the overload message after success.
                    retry_message.empty()

                    if sql.strip() == "CANNOT_GENERATE_SQL":
                        st.error("Unable to generate SQL query for this question.")
                        st.session_state.pop("generated_sql", None)

                    else:
                        # Save the generated query across Streamlit
                        # reruns.
                        st.session_state["generated_sql"] = sql
                        st.session_state["editable_sql"] = sql

                        # Save the question associated with the generated SQL.
                        st.session_state["generated_question"] = question

                        if st.session_state.get("developer_mode", False):
                            st.success("SQL query generated successfully!")

                        else:

                            # Automatically execute the query in standard mode.
                            try:
                                with st.spinner("Executing SQL query..."):
                                    # Open the read-only PostgreSQL connection.
                                    with connect_db() as conn:
                                        df = execute_sql(
                                            sql,
                                            conn,
                                            max_rows=st.session_state.get("max_rows", 1000)
                                        )

                                    # Save the query and its results to the history.
                                    st.session_state["query_history"].append({
                                        "question": question,
                                        "sql": sql,
                                        "results": df.copy()
                                    })

                                    # Persist the updated query history.
                                    save_history(st.session_state["query_history"])

                                    # Clear the pending query.
                                    st.session_state.pop("generated_sql", None)
                                    st.session_state.pop("generated_question", None)

                                    # Expand the latest result.
                                    st.session_state["collapse_history"] = False
                                    st.session_state["history_version"] = (
                                            st.session_state.get("history_version", 0) + 1
                                    )

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
                        st.warning(
                            "The AI model used to convert natural language into SQL "
                            "is currently experiencing high demand. "
                            "Please wait a moment and try again."
                        )
                    else:
                        st.error("An unexpected error occurred while generating the SQL query. Please try again later.")

        else:
            st.warning("Please enter a question.")

    # Display editable SQL only when developer mode is enabled.
    if (
            st.session_state.get("developer_mode", False)
            and "generated_sql" in st.session_state
    ):
        st.subheader("Generated SQL")

        st.text_area(
            "SQL Query",
            key="editable_sql",
            height=250,
            label_visibility="collapsed",
            help="Review and modify the generated SQL before execution."
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
                        df = execute_sql(
                            sql,
                            conn,
                            max_rows=st.session_state.get("max_rows", 1000)
                        )

                    # Save the completed query only once.
                    st.session_state["query_history"].append({
                        "question": st.session_state["generated_question"],
                        "sql": sql,
                        "results": df.copy()
                    })

                    # Persist the updated query history.
                    save_history(st.session_state["query_history"])

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


    @st.dialog("Clear Query History")
    def confirm_clear_history():

        st.warning(
            "Are you sure you want to delete your entire query history? "
            "This action cannot be undone."
        )

        col_cancel, col_confirm = st.columns(2)

        with col_cancel:
            if st.button(
                    "Cancel",
                    use_container_width=True
            ):
                st.rerun()

        with col_confirm:
            if st.button(
                    "Delete History",
                    icon=":material/delete_outline:",
                    type="primary",
                    use_container_width=True
            ):
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
                st.session_state["history_version"] = (
                        st.session_state.get("history_version", 0) + 1
                )

                st.rerun()

    @st.dialog("Save Query History")
    def confirm_save_history():

        config = st.session_state["config"]

        # Generate a default name when opening the dialog.
        default_filename = datetime.now().strftime(
            "history%Y%m%d%H%M%S.json"
        )

        # Use the directory configured in History Settings.
        default_directory = str(
            Path(config["history_path"]).parent
        )

        st.write(
            "Save a copy of the current query history, "
            "including questions, generated SQL queries and results."
        )

        filename = st.text_input(
            "File Name",
            value=default_filename,
            key="history_export_filename"
        )

        directory = st.text_input(
            "Save Directory",
            value=default_directory,
            key="history_export_directory",
            help="Choose a directory inside the project's data folder."
        )

        col_cancel, col_save = st.columns(2)

        with col_cancel:
            if st.button(
                    "Cancel",
                    key="cancel_history_export",
                    use_container_width=True
            ):
                st.rerun()

        with col_save:
            if st.button(
                    "Save History",
                    icon=":material/save:",
                    key="confirm_history_export",
                    type="primary",
                    use_container_width=True
            ):
                try:
                    destination = export_history(
                        st.session_state["query_history"],
                        filename,
                        directory
                    )

                    st.session_state["history_export_success"] = (
                        f"History saved successfully to: {destination}"
                    )

                    st.rerun()

                except (ValueError, OSError) as e:
                    st.error(str(e))


    @st.dialog("Load Query History")
    def confirm_load_history():

        st.write(
            "Select a previously saved history file to restore "
            "questions, generated SQL queries and results."
        )

        uploaded_file = st.file_uploader(
            "Select History File",
            type=["json"],
            key="history_import_file"
        )

        col_cancel, col_load = st.columns(2)

        with col_cancel:
            if st.button(
                    "Cancel",
                    key="cancel_history_import",
                    use_container_width=True
            ):
                st.rerun()

        with col_load:
            if st.button(
                    "Load History",
                    icon=":material/folder_open:",
                    key="confirm_history_import",
                    type="secondary",
                    disabled=uploaded_file is None,
                    use_container_width=True
            ):
                try:
                    imported_history = import_history(
                        uploaded_file.getvalue()
                    )

                    max_history = st.session_state["config"]["max_history"]

                    if len(imported_history) > max_history:
                        st.warning(
                            f"The file contains {len(imported_history)} queries. "
                            f"Only the most recent {max_history} will be restored."
                        )

                    restored_history = imported_history[-max_history:]

                    # Persist the imported history first.
                    save_history(restored_history)

                    # Update session state only after a successful save.
                    st.session_state["query_history"] = restored_history
                    st.session_state["question_number"] = len(restored_history)

                    st.session_state.pop("generated_sql", None)
                    st.session_state.pop("generated_question", None)

                    # Keep expanders closed after importing.
                    st.session_state["collapse_history"] = True
                    st.session_state["history_version"] = (
                            st.session_state.get("history_version", 0) + 1
                    )

                    st.session_state["history_import_success"] = (
                        f"Successfully loaded {len(restored_history)} queries."
                    )

                    st.rerun()

                except (ValueError, UnicodeError, OSError, TypeError) as e:
                    st.error(f"Unable to load history: {e}")


    if "history_export_success" in st.session_state:
        st.success(st.session_state.pop("history_export_success"))


    # QUERY HISTORY

    st.subheader("Query History")

    if st.session_state["query_history"]:

        # Clear and Save buttons.
        col_clear, col_save, col_space = st.columns(
            [1, 1, 6],
            gap="small"
        )

        with col_clear:
            if st.button(
                    "Clear",
                    icon=":material/delete_outline:",
                    type="tertiary",
                    key="clear_query_history",
                    use_container_width=True
            ):
                confirm_clear_history()

        with col_save:
            if st.button(
                    "Save",
                    icon=":material/save:",
                    type="tertiary",
                    key="save_query_history",
                    use_container_width=True
            ):
                confirm_save_history()

        for index, item in enumerate(st.session_state["query_history"]):

            # Expand the latest result only when no new SQL is pending.
            is_latest = index == len(st.session_state["query_history"]) - 1

            with st.expander(
                    f"Question {index + 1} — {item['question']}",
                    expanded=(
                            is_latest
                            and not st.session_state["collapse_history"]
                            and "generated_sql" not in st.session_state
                    ),
                    key=f"history_{index}_{st.session_state.get('history_version', 0)}"
            ):

                # Display executed SQL in developer mode.
                if st.session_state.get("developer_mode", False):
                    st.subheader("Generated Query")
                    st.code(item["sql"], language="sql")

                # Display the query results.
                st.subheader("Query Results")

                df = item["results"]

                st.dataframe(
                    df,
                    width="stretch",
                    hide_index=True
                )

                st.write(f"Total rows: {len(df)}")

                # Allow the user to download the results.
                st.download_button(
                    label="Download CSV",
                    data=df.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"query_results_{index + 1}.csv",
                    mime="text/csv",
                    key=f"download_history_{index}"
                )

    else:

        # Show Load only when history is empty.
        col_load, col_space = st.columns([1, 7], gap="small")

        with col_load:
            if st.button(
                    "Load",
                    icon=":material/folder_open:",
                    type="secondary",
                    key="load_query_history",
                    use_container_width=True
            ):
                confirm_load_history()


##############################################################################################

# SETTINGS:

elif page == "⚙️ Impostazioni":

    st.title("⚙️ Settings")

    st.write(
        "Configure application behavior, SQL generation, "
        "query results, and database access."
    )

    # Save a validated configuration update.
    def update_setting(name, value):

        updated_config = st.session_state["config"].copy()
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
            st.session_state["query_history"] = (
                st.session_state["query_history"][-value:]
            )
            save_history(st.session_state["query_history"])

    # save path of saved history
    def save_history_path():
        new_path = st.session_state["history_path_input"]
        old_path = st.session_state["config"]["history_path"]

        if new_path == old_path:
            return

        if update_setting("history_path", new_path):
            # Preserve the current history in the new location.
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

    st.toggle(
        "Programmer Mode",
        value=st.session_state["config"]["programmer_mode"],
        key="programmer_mode_input",
        on_change=save_programmer_mode,
        help="Show generated SQL queries and technical details."
    )

    st.divider()


    # QUERY RESULTS SETTINGS

    st.subheader("Query Results Settings")

    st.number_input(
        "Maximum Number of Rows",
        min_value=1,
        max_value=10000,
        step=1,
        value=st.session_state["config"]["max_rows"],
        key="max_rows_input",
        on_change=save_max_rows,
        help="Maximum number of rows returned by a database query."
    )

    st.divider()


    # HISTORY SETTINGS

    st.subheader("History Settings")

    st.number_input(
        "Maximum Saved Queries",
        min_value=10,
        max_value=500,
        step=10,
        value=st.session_state["config"]["max_history"],
        key="max_history_input",
        on_change=save_max_history,
        help="Maximum number of queries stored in history."
    )

    st.text_input(
        "History Save Path",
        value=st.session_state["config"]["history_path"],
        key="history_path_input",
        on_change=save_history_path,
        help="JSON file path relative to the project directory."
    )

    st.divider()


    # SQL GENERATION SETTINGS

    st.subheader("SQL Generation Settings")

    st.toggle(
        "Automatic Retry",
        value=st.session_state["config"]["automatic_retry"],
        key="automatic_retry_input",
        on_change=save_automatic_retry,
        help="Automatically retry SQL generation after temporary errors."
    )

    st.number_input(
        "Maximum Retries",
        min_value=1,
        max_value=10,
        step=1,
        value=st.session_state["config"]["max_retries"],
        key="max_retries_input",
        on_change=save_max_retries,
        disabled=not st.session_state["config"]["automatic_retry"],
        help="Number of additional attempts after the initial request."
    )

    st.number_input(
        "Retry Delay (seconds)",
        min_value=1,
        max_value=60,
        step=1,
        value=st.session_state["config"]["retry_delay_seconds"],
        key="retry_delay_input",
        on_change=save_retry_delay,
        disabled=not st.session_state["config"]["automatic_retry"],
        help="Fixed waiting time between retry attempts."
    )

    st.divider()


    # DATABASE ACCESS SETTINGS

    st.subheader("Database Access Settings")

    st.write(
        "Select which database tables can be used "
        "when generating and executing SQL queries."
    )

    from src.configManager import SUPPORTED_TABLES

    st.multiselect(
        "Allowed Tables",
        options=sorted(SUPPORTED_TABLES),
        default=st.session_state["config"]["allowed_tables"],
        key="allowed_tables_input",
        on_change=save_allowed_tables,
        help="At least one table must remain selected."
    )

    st.divider()

    st.caption(
        "Settings are saved automatically to config/settings.json."
    )



##############################################################################################

# DIAGNOSTICS:

elif page == "🛠️ Diagnostica":

    st.title("🛠️ Database Diagnostics")


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

    st.write(
        "Execute a predefined SQL query to verify "
        "that PostgreSQL returns the expected results."
    )

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

            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name="query_results.csv",
                mime="text/csv"
            )

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

