from graphviz import Digraph
from html import escape


def visualize_query_structure(query_analysis: dict) -> Digraph:
    """Render referenced columns and connect equality JOIN columns by port."""
    dot = Digraph("QueryStructure")
    dot.attr(rankdir="LR", bgcolor="transparent", nodesep="0.45", ranksep="0.85", pad="0.08")
    dot.attr("edge", color="#27A89C", penwidth="1.8", arrowsize="0.7")

    tables = query_analysis.get("tables", [])
    columns = query_analysis.get("columns", [])
    join_columns = query_analysis.get("join_columns", [])
    subquery_columns = query_analysis.get("subquery_columns", [])
    selected_columns = {
        (col["alias"], col["column"])
        for col in query_analysis.get("selected_columns", [])
    }
    joined_columns = set()
    table_columns = {table["alias"]: [] for table in tables}

    def include_column(alias, name):
        if alias in table_columns and name not in table_columns[alias]:
            table_columns[alias].append(name)

    for column in columns:
        include_column(column["alias"], column["column"])

    for relationship in join_columns + subquery_columns:
        left = (relationship["left_alias"], relationship["left_column"])
        right = (relationship["right_alias"], relationship["right_column"])
        joined_columns.update((left, right))
        include_column(*left)
        include_column(*right)

    # Use internal node identifiers rather than SQL aliases to avoid Graphviz
    # reserved-name and punctuation issues. Ports identify individual rows.
    node_ids = {table["alias"]: f"table_{i}" for i, table in enumerate(tables)}
    ports = {}

    for table in tables:
        alias = table["alias"]
        table_name = escape(table["name"])
        rows = [
            '<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" '
            'CELLPADDING="7" COLOR="#6896B4" BGCOLOR="#FFFFFF">',
            '<TR><TD BGCOLOR="#234A68" ALIGN="CENTER">'
            f'<FONT COLOR="#FFFFFF"><B>{table_name}</B></FONT>'
            '</TD></TR>',
        ]

        for index, column in enumerate(table_columns[alias]):
            ports[(alias, column)] = f"col_{index}"
            # Highlight only columns returned by SELECT.
            if (alias, column) in selected_columns:
                background, foreground = "#FDE68A", "#1F2937"
            else:
                background, foreground = "#FFFFFF", "#253746"
            is_selected = (alias, column) in selected_columns
            column_label = escape(column)
            if is_selected:
                column_label = f"<B>{column_label}</B>"
            rows.append(
                f'<TR><TD PORT="col_{index}" ALIGN="LEFT" BGCOLOR="{background}">'
                f'<FONT COLOR="{foreground}">{column_label}</FONT>'
                '</TD></TR>'
            )

        if not table_columns[alias]:
            rows.append(
                '<TR><TD ALIGN="LEFT"><FONT COLOR="#64748B">'
                'No columns referenced</FONT></TD></TR>'
            )

        rows.append('</TABLE>')
        dot.node(node_ids[alias], label='<'+''.join(rows)+'>', shape='plain')


    # Draw explicit JOIN relationships.
    for relationship in join_columns:
        left = (relationship["left_alias"], relationship["left_column"])
        right = (relationship["right_alias"], relationship["right_column"])

        if left not in ports or right not in ports:
            continue

        dot.edge(
            f'{node_ids[left[0]]}:{ports[left]}:e',
            f'{node_ids[right[0]]}:{ports[right]}:w',
        )

    # Draw subquery relationships using the same style as JOINs.
    for relationship in subquery_columns:
        left = (relationship["left_alias"], relationship["left_column"])
        right = (relationship["right_alias"], relationship["right_column"])

        if left not in ports or right not in ports:
            continue

        dot.edge(
            f'{node_ids[left[0]]}:{ports[left]}:e',
            f'{node_ids[right[0]]}:{ports[right]}:w',
        )

    return dot