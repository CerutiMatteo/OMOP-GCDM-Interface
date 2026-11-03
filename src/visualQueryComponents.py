import datetime
import streamlit as st

from .visualQueryEditor import extract_parameters, update_parameter, get_clinical_conditions, set_include_descendants
from .queryAnalyzer import analyze_query
from .conceptDisplayConfig import get_custom_concept_config
from .vocabularyOptions import get_concept, list_field_concepts, search_standard_concepts
from streamlit_searchbox import st_searchbox

def _change(pid, key):
    sql = st.session_state['editable_sql']
    try:
        st.session_state['editable_sql'] = update_parameter(sql, pid, st.session_state[key])
    except ValueError as exc:
        st.session_state['visual_editor_error'] = str(exc)
        original = next((p['value'] for p in extract_parameters(sql) if p['id'] == pid), None)
        if original is not None:
            st.session_state[key] = original



@st.cache_data(ttl=3600, show_spinner=False)
def _load_concept_options(table, field, domain):
    """
    Load the available concepts for a configured OMOP field.
    """
    if not table or not field:
        return {}

    return list_field_concepts(table, field, domain)


def _search_concepts(term, domain):
    """Search OMOP concepts and return formatted options."""
    concepts = search_standard_concepts(term, domain)

    return [
        f"{concept_name} ({concept_id})"
        for concept_id, concept_name in concepts.items()
    ]

def _render_concept_select(parameter, config, key, callback):

    # Render a single searchable dropdown for a customized OMOP field.


    current = parameter["value"]
    options = dict(config.get("options", {}))
    kind = config["widget"]

    if kind == "concept_search" and isinstance(current, int) and not isinstance(current, bool):
        domain = config["domain"]

        existing = get_concept(current)

        if existing:
            current_option = f"{existing['concept_name']} ({current})"
        else:
            current_option = f"Unknown concept ({current})"

        st.markdown(
            f"<p style='font-size: 14px; font-weight: 400; margin-bottom: 4px;'>"
            f"{config['label']}</p>",
            unsafe_allow_html=True,
        )

        selected = st_searchbox(
            search_function=lambda term: _search_concepts(term, domain),
            placeholder=f"Search {config['label']}...",
            label=None,
            key=f"{key}_search",
            default=current_option,
            default_searchterm=current_option,
            default_options=[current_option],
            clear_on_submit=False,
            edit_after_submit="current",
        )

        if selected is not None and selected != current_option:
            try:
                # Extract the numeric concept ID from the selected option.
                selected_id = int(selected.rsplit("(", 1)[1].rstrip(")"))

                st.session_state["editable_sql"] = update_parameter(
                    st.session_state["editable_sql"],
                    parameter["id"],
                    selected_id,
                )
                st.rerun()

            except (ValueError, IndexError) as exc:
                st.session_state["visual_editor_error"] = str(exc)

        return

    if kind in ("vocabulary_select", "concept_search"):

        if not isinstance(current, int) or isinstance(current, bool):
            st.text_input(
                config["label"],
                value=str(current),
                key=key,
                on_change=callback,
            )
            return

        # Always preserve the concept currently used in the SQL.
        existing = get_concept(current)

        if existing:
            options[current] = existing["concept_name"]
        else:
            options[current] = f"Unknown concept ({current})"

        # Retrieve available concepts from the corresponding OMOP table.
        from .conceptDisplayConfig import TABLE_FIELDS

        semantic_field = parameter.get("semantic_field")

        table = next(
            (
                table_name
                for table_name, fields in TABLE_FIELDS.items()
                if semantic_field in fields
            ),
            None,
        )

        # Load complete dropdown options only for supported,
        # relatively small vocabulary fields.
        if (
                kind == "vocabulary_select"
                and table in ("person", "visit_occurrence")
                and semantic_field in (
                "race_concept_id",
                "ethnicity_concept_id",
                "visit_concept_id",
        )
        ):
            options.update(
                _load_concept_options(
                    table,
                    semantic_field,
                    config.get("domain"),
                )
            )

    # Preserve any value that is not part of the predefined options.
    if current not in options:

        if parameter["value_type"] == "integer":
            st.number_input(
                config["label"],
                value=current,
                step=1,
                key=key,
                on_change=callback,
            )

        else:
            st.text_input(
                config["label"],
                value=current,
                key=key,
                on_change=callback,
            )

        return

    values = list(options.keys())

    st.selectbox(
        label=config["label"],
        options=values,
        index=values.index(current),
        format_func=lambda value: (
            options[value]
            if kind == "select"
            else f"{options[value]} ({value})"
        ),
        key=key,
        on_change=callback,
    )

def _change_include_descendants():
    """Update the SQL when the global subclasses checkbox changes."""
    try:
        enabled = st.session_state["include_descendants"]

        st.session_state["editable_sql"] = set_include_descendants(
            st.session_state["editable_sql"],
            enabled,
        )

        # Recreate parameter widgets after the SQL structure changes.
        st.session_state["visual_editor_version"] += 1

    except ValueError as exc:
        st.session_state["visual_editor_error"] = str(exc)

def render_visual_editor():
    sql = st.session_state.get('editable_sql', '')
    if not sql.strip():
        st.info('No SQL query available.')
        return
    try:
        parameters = extract_parameters(sql)
    except ValueError as exc:
        st.error(f'Unable to interpret SQL query: {exc}')
        return
    if not parameters:
        st.info('No editable parameters were found in this SQL query.')
    else:
        st.caption('Modify the parameters below to update the SQL query.')

    # Show one global checkbox for all supported clinical conditions.
    clinical_conditions = get_clinical_conditions(sql)

    if clinical_conditions:
        # Read the actual subclasses setting from SQL.
        current_enabled = all(
            condition["include_descendants"]
            for condition in clinical_conditions
        )

        # Synchronize the checkbox with SQL.
        st.session_state["include_descendants"] = current_enabled

        st.checkbox(
            "Include subclasses",
            key="include_descendants",
            on_change=_change_include_descendants,
            help=(
                "Include the selected clinical conditions and all their "
                "descendant concepts from the OMOP vocabulary."
            ),
        )

    version = st.session_state.get('visual_editor_version', 0)
    for p in parameters:
        pid, ptype, value_type = p['id'], p['type'], p['value_type']
        key = f'visual_{version}_{pid}'
        callback = lambda pid=pid, key=key: _change(pid, key)
        if ptype == 'limit':
            label = 'Maximum number of results'
        elif ptype == 'between_lower':
            label = f"{p['column']} - From"
        elif ptype == 'between_upper':
            label = f"{p['column']} - To"
        else:
            label = f"{p['column']} {p['operator']}"
        config = get_custom_concept_config(p)
        if config:
            _render_concept_select(p, config, key, callback)
        elif value_type == 'boolean':
            st.checkbox(label, value=p['value'], key=key, on_change=callback)
        elif value_type == 'integer':
            st.number_input(label, value=p['value'], step=1, key=key, on_change=callback)
        elif value_type == 'float':
            st.number_input(label, value=float(p['value']), step=0.1, key=key, on_change=callback)
        elif value_type == 'date':
            st.date_input(label, value=datetime.date.fromisoformat(str(p['value'])),
                          key=key, on_change=callback)
        elif value_type == 'string':
            st.text_input(label, value=p['value'], key=key, on_change=callback)

    if 'visual_editor_error' in st.session_state:
        st.warning(st.session_state.pop('visual_editor_error'), icon='⚠️')
    # Read the latest SQL, including changes applied by callbacks.
    sql = st.session_state.get('editable_sql', '')
    try:
        analysis = analyze_query(sql)
        tables = list(dict.fromkeys(t['name'] for t in analysis.get('tables', [])))
        st.text_input('Tables Involved (read-only field)', value=',    '.join(tables),
                      disabled=True, key=f'tables_involved_{version}_{hash(sql)}')
    except Exception as exc:
        st.warning(f'Unable to identify tables: {exc}')
    st.markdown('**Current SQL:**')
    st.code(sql, language='sql')
