from .schemaMetadata import get_database_schema

def format_schema_for_llm(schema, selected_tables=None):
    # Convert database metadata into a readable text representation
    lines = []

    for table_name, table_info in schema.items():
        if selected_tables is not None and table_name not in selected_tables:
            continue
        lines.append(f"TABLE: cdm.{table_name}")

        # Add column names and data types
        lines.append("COLUMNS:")
        for column_name, data_type in table_info["columns"].items():
            lines.append(f"  - {column_name}: {data_type}")

        # Add primary keys
        lines.append(f"PRIMARY KEYS: {', '.join(table_info['primary_keys']) or 'None'}")

        # Add declared foreign keys
        lines.append("FOREIGN KEYS:")
        for fk in table_info["foreign_keys"]:
            # Include relationships only if the target table is selected
            if (selected_tables is not None
                    and fk["references_table"] not in selected_tables):
                continue
            lines.append(
                f"  - {fk['column']} -> "
                f"{fk['references_table']}.{fk['references_column']}"
            )

        lines.append("")

    return "\n".join(lines)


#TEST: ONLY WHEN WE RUN THIS FILE
if __name__ == "__main__":
    database_schema = get_database_schema()

    # Select the main tables for genomic queries
    selected_tables = [
        "person",
        "specimen",
        "variant_occurrence",
        "target_gene",
        "variant_annotation"
    ]

    schema_text = format_schema_for_llm(
        database_schema,
        selected_tables
    )

    print(schema_text)

