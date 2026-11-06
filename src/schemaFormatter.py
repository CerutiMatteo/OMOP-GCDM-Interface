from .schemaMetadata import get_database_schema
from .schemaSemantics import SCHEMA_SEMANTICS


def format_schema_for_llm(schema, selected_tables=None):
    lines = []

    for table_name, table_info in schema.items():

        if selected_tables is not None and table_name not in selected_tables:
            continue

        lines.append(f"TABLE: cdm.{table_name}")

        lines.append("COLUMNS:")
        for column_name, data_type in table_info["columns"].items():
            lines.append(f"  - {column_name}: {data_type}")

        lines.append(
            f"PRIMARY KEYS: "
            f"{', '.join(table_info['primary_keys']) or 'None'}"
        )

        lines.append("FOREIGN KEYS:")
        for fk in table_info["foreign_keys"]:
            if (
                selected_tables is not None
                and fk["references_table"] not in selected_tables
            ):
                continue

            lines.append(
                f"  - {fk['column']} -> "
                f"{fk['references_table']}.{fk['references_column']}"
            )

        semantics = SCHEMA_SEMANTICS.get(table_name, {})

        if semantics:

            if "description" in semantics:
                lines.append(
                    f"DESCRIPTION: {semantics['description']}"
                )

            if "relationships" in semantics:
                lines.append("ADDITIONAL RELATIONSHIPS:")

                for relationship in semantics["relationships"]:
                    if (
                        selected_tables is not None
                        and relationship["references_table"]
                        not in selected_tables
                    ):
                        continue

                    lines.append(
                        f"  - {relationship['column']} -> "
                        f"{relationship['references_table']}."
                        f"{relationship['references_column']}"
                    )

            if "columns" in semantics:
                lines.append("COLUMN SEMANTICS:")

                for column_name, description in semantics["columns"].items():
                    if column_name in table_info["columns"]:
                        lines.append(
                            f"  - {column_name}: {description}"
                        )

        lines.append("")

    return "\n".join(lines)