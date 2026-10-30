import streamlit as st

from .visualQueryEditor import extract_parameters, update_parameter
from .queryAnalyzer import analyze_query


def render_visual_editor():
    """
    Render the visual query editor.
    Editable parameters are extracted from the current SQL query.
    Changes to visual controls immediately update the SQL stored in Streamlit session state.
    """

    sql = st.session_state.get("editable_sql", "")

    if not sql.strip():
        st.info("No SQL query available.")
        return

    # Extract parameters only when the visual editor is opened or when a visual control changes the query.
    try:
        parameters = extract_parameters(sql)
    except ValueError as e:
        st.error(f"Unable to interpret SQL query: {e}")
        return

    if not parameters:
        st.info("No editable parameters were found in this SQL query.")
    else:
        st.caption("Modify the parameters below to update the SQL query.")

    # Identify the current query version. The version changes when switching from SQL to visual mode.
    version = st.session_state.get("visual_editor_version", 0)

    for parameter in parameters:

        parameter_id = parameter["id"]
        parameter_type = parameter["type"]
        value_type = parameter["value_type"]

        widget_key = f"visual_{version}_{parameter_id}"

        # Build a user-friendly label.
        if parameter_type == "limit":
            label = "Maximum number of results"
        else:
            label = (f"{parameter['column']} "f"{parameter['operator']}")

        # Callback executed when a parameter changes.
        def on_parameter_change(pid=parameter_id, key=widget_key,):
            sql = st.session_state["editable_sql"]
            new_value = st.session_state[key]

            try:
                updated_sql = update_parameter(sql, pid, new_value,)
                st.session_state["editable_sql"] = updated_sql

            except ValueError as e:

                st.session_state["visual_editor_error"] = str(e)

                # Restore the last valid value in the widget.
                current_parameters = extract_parameters(st.session_state["editable_sql"])

                original_value = next((
                        p["value"]
                        for p in current_parameters
                        if p["id"] == pid
                    ),
                    None,
                )

                if original_value is not None:
                    st.session_state[key] = original_value

        # Render a widget based on the SQL literal type.
        if value_type == "boolean":
            st.checkbox(label, value=parameter["value"], key=widget_key, on_change=on_parameter_change,)

        elif value_type == "integer":
            st.number_input(label, value=parameter["value"], step=1, key=widget_key, on_change=on_parameter_change,)

        elif value_type == "float":
            st.number_input(label, value=parameter["value"], step=0.1, key=widget_key, on_change=on_parameter_change,)

        elif value_type == "string":
            st.text_input(label, value=parameter["value"], key=widget_key, on_change=on_parameter_change,)

    # Show errors caused by invalid parameter updates.
    if "visual_editor_error" in st.session_state:
        st.warning(st.session_state.pop("visual_editor_error"), icon="⚠️",)

    # TABLES INVOLVED (READ-ONLY)

    try:
        query_analysis = analyze_query(sql)

        tables_involved = list(dict.fromkeys(
            table["name"]
            for table in query_analysis.get("tables", [])
        ))

        st.text_input(
            "Tables Involved (read-only field)",
            value=",    ".join(tables_involved),
            disabled=True,
            key=f"tables_involved_{sql}"
        )

    except Exception as e:
        st.warning(f"Unable to identify tables: {e}")


    # CURRENT SQL

    st.markdown("**Current SQL:**")
    st.code(sql, language="sql")