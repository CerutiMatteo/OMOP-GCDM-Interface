from graphviz import Digraph
from html import escape


def visualize_database_schema(
    schema: dict,
    selected_table: str,
    show_columns: bool = True,
    visible_tables: list | None = None
) -> Digraph:
    """
    Visualize the selected table and its directly connected
    tables using PostgreSQL foreign keys.

    If visible_tables is provided, only relationships involving
    the selected related tables are displayed.
    The main table is always included.
    """

    if selected_table not in schema:
        raise ValueError(f"Unknown table: {selected_table}")

    # Convert selected tables to a set for faster filtering.
    visible_set = (
        set(visible_tables)
        if visible_tables is not None
        else None
    )

    # Find incoming and outgoing relationships.
    relationships = []
    connected_tables = {selected_table}

    for source_table, table_info in schema.items():
        for fk in table_info["foreign_keys"]:
            target_table = fk["references_table"]

            if (
                source_table == selected_table
                or target_table == selected_table
            ):
                if target_table not in schema:
                    continue

                # Identify the table connected to the selected one.
                related_table = (
                    target_table
                    if source_table == selected_table
                    else source_table
                )

                # Skip relationships with hidden tables.
                # Self-references of the selected table remain visible.
                if (
                    visible_set is not None
                    and related_table != selected_table
                    and related_table not in visible_set
                ):
                    continue

                relationships.append({
                    "source_table": source_table,
                    "source_column": fk["column"],
                    "target_table": target_table,
                    "target_column": fk["references_column"]
                })

                connected_tables.add(source_table)
                connected_tables.add(target_table)

    # Create Graphviz diagram.
    dot = Digraph("DatabaseSchema")

    dot.attr(
        rankdir="LR",
        bgcolor="transparent",
        nodesep="0.5",
        ranksep="1.0",
        pad="0.2"
    )

    dot.attr(
        "edge",
        color="#27A89C",
        penwidth="1.8",
        arrowsize="0.7"
    )

    # Collect FK columns for each visible table.
    table_columns = {
        table: set()
        for table in connected_tables
    }

    for rel in relationships:
        table_columns[rel["source_table"]].add(
            rel["source_column"]
        )
        table_columns[rel["target_table"]].add(
            rel["target_column"]
        )

    # Create table nodes.
    for table_name in sorted(connected_tables):

        is_selected = table_name == selected_table

        header_color = (
            "#176B65" if is_selected else "#234A68"
        )

        rows = [
            '<TABLE BORDER="1" CELLBORDER="0" '
            'CELLSPACING="0" CELLPADDING="7" '
            'COLOR="#6896B4" BGCOLOR="#FFFFFF">',
            f'<TR><TD BGCOLOR="{header_color}">'
            f'<FONT COLOR="#FFFFFF"><B>{escape(table_name)}</B></FONT>'
            '</TD></TR>'
        ]

        if show_columns:
            for column in sorted(table_columns[table_name]):

                is_pk = column in schema[table_name]["primary_keys"]

                label = escape(column)
                if is_pk:
                    label += " (PK)"

                rows.append(
                    f'<TR><TD PORT="{escape(column, quote=True)}" '
                    'ALIGN="LEFT" BGCOLOR="#FFFFFF">'
                    f'<FONT COLOR="#253746">{label}</FONT>'
                    '</TD></TR>'
                )

        rows.append("</TABLE>")

        dot.node(
            table_name,
            label="<" + "".join(rows) + ">",
            shape="plain"
        )

    # Draw relationships.
    for rel in relationships:

        source = rel["source_table"]
        target = rel["target_table"]

        if show_columns:
            dot.edge(
                f'{source}:{rel["source_column"]}:e',
                f'{target}:{rel["target_column"]}:w'
            )
        else:
            dot.edge(source, target)

    return dot
