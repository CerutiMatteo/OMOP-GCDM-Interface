import sqlglot
from sqlglot import exp

from .schemaMetadata import get_database_schema


def analyze_query(sql: str) -> dict:
    """Analyze tables, referenced/selected columns and explicit equality JOINs.

    Unqualified columns are associated with a table only when the query has
    exactly one physical table. Ambiguous multi-table columns are not guessed.
    """
    try:
        statement = sqlglot.parse_one(sql, read="postgres")
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"Invalid SQL syntax: {exc}") from exc

    if statement is None or not isinstance(statement, (exp.Select, exp.Union)):
        raise ValueError("Only SELECT or UNION queries are supported.")

    tables = []
    aliases = {}
    columns = []
    joins = []
    join_columns = []
    subquery_columns = []
    selected_columns = []

    for table in statement.find_all(exp.Table):
        info = {"schema": table.db, "name": table.name, "alias": table.alias_or_name}
        if info not in tables:
            tables.append(info)
        aliases[table.alias_or_name] = table.name

    single_table_alias = tables[0]["alias"] if len(tables) == 1 else None

    # Load table columns only when needed for SELECT *.
    def get_table_columns(table_name):
        schema = get_database_schema()
        table_metadata = schema.get(table_name)

        if table_metadata is None:
            return []

        return list(table_metadata["columns"].keys())

    def resolve_alias(column):
        if column.table:
            return column.table

        # Resolve unqualified columns within their own SELECT scope.
        select = column.find_ancestor(exp.Select)

        if select is not None:
            local_tables = []

            from_clause = select.args.get("from_")
            if from_clause is not None:
                local_tables.extend(from_clause.find_all(exp.Table))

            for join in select.args.get("joins") or []:
                if isinstance(join.this, exp.Table):
                    local_tables.append(join.this)

            local_aliases = list(dict.fromkeys(
                table.alias_or_name for table in local_tables
            ))

            if len(local_aliases) == 1:
                return local_aliases[0]

        return single_table_alias

    def add_column(column):
        alias = resolve_alias(column)
        info = {
            "table": aliases.get(alias, alias),
            "alias": alias,
            "column": column.name,
        }
        if info not in columns:
            columns.append(info)

    for column in statement.find_all(exp.Column):
        # Ignore the wildcard p.* because it is not a physical column.
        if isinstance(column.this, exp.Star):
            continue

        add_column(column)

    # SELECT expressions may contain nested functions, arithmetic and aliases.
    # Restrict to the outer SELECT so subquery projections aren't confused with
    # the columns returned by the main query.
    select_statements = [statement] if isinstance(statement, exp.Select) else []
    if isinstance(statement, exp.Union):
        # UNION output columns are determined by its leftmost SELECT.
        left = statement
        while isinstance(left, exp.Union):
            left = left.left
        if isinstance(left, exp.Select):
            select_statements = [left]

    for select in select_statements:
        for projection in select.expressions:
            expression = projection.this if isinstance(projection, exp.Alias) else projection
            # Handle SELECT *.
            if isinstance(expression, exp.Star):
                for table in tables:
                    alias = table["alias"]

                    for column_name in get_table_columns(table["name"]):
                        column_info = {
                            "table": table["name"],
                            "alias": alias,
                            "column": column_name,
                        }

                        if column_info not in columns:
                            columns.append(column_info)

                        selected_info = {
                            "alias": alias,
                            "column": column_name,
                        }

                        if selected_info not in selected_columns:
                            selected_columns.append(selected_info)

                continue

            # Handle SELECT alias.*.
            if isinstance(expression, exp.Column) and isinstance(expression.this, exp.Star):
                alias = expression.table

                if alias in aliases:
                    for column_name in get_table_columns(aliases[alias]):
                        column_info = {
                            "table": aliases[alias],
                            "alias": alias,
                            "column": column_name,
                        }

                        if column_info not in columns:
                            columns.append(column_info)

                        selected_info = {
                            "alias": alias,
                            "column": column_name,
                        }

                        if selected_info not in selected_columns:
                            selected_columns.append(selected_info)

                continue

            candidates = [expression] if isinstance(expression, exp.Column) else list(expression.find_all(exp.Column))
            for column in candidates:
                alias = resolve_alias(column)
                if alias is None or alias not in aliases:
                    continue
                info = {"alias": alias, "column": column.name}
                if info not in selected_columns:
                    selected_columns.append(info)

    for join in statement.find_all(exp.Join):
        joined_table = join.this
        if not isinstance(joined_table, exp.Table):
            continue

        join_type = " ".join(
            str(part) for part in (join.args.get("side"), join.args.get("kind")) if part
        ).strip() or "INNER"
        condition = join.args.get("on")
        joins.append({
            "table": joined_table.name,
            "alias": joined_table.alias_or_name,
            "type": join_type,
            "condition": condition.sql(dialect="postgres") if condition is not None else None,
        })
        if condition is None:
            continue

        for equality in condition.find_all(exp.EQ):
            left, right = equality.left, equality.right
            if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
                continue
            if not left.table or not right.table or left.table == right.table:
                continue
            if left.table not in aliases or right.table not in aliases:
                continue
            relationship = {
                "left_alias": left.table,
                "left_column": left.name,
                "right_alias": right.table,
                "right_column": right.name,
            }
            if relationship not in join_columns:
                join_columns.append(relationship)

    # Identify relationships introduced by IN subqueries.
    for in_expression in statement.find_all(exp.In):
        outer_column = in_expression.this
        query = in_expression.args.get("query")

        if not isinstance(outer_column, exp.Column):
            continue

        if isinstance(query, exp.Subquery):
            subquery = query.this
        else:
            subquery = query

        if not isinstance(subquery, exp.Select):
            continue

        if len(subquery.expressions) != 1:
            continue

        inner_column = subquery.expressions[0]

        if not isinstance(inner_column, exp.Column):
            continue

        inner_from = subquery.args.get("from_")

        if inner_from is None or not isinstance(inner_from.this, exp.Table):
            continue

        if subquery.args.get("joins"):
            continue

        inner_table = inner_from.this
        inner_alias = inner_table.alias_or_name
        outer_alias = resolve_alias(outer_column)

        if outer_alias not in aliases or inner_alias not in aliases:
            continue

        relationship = {
            "left_alias": outer_alias,
            "left_column": outer_column.name,
            "right_alias": inner_alias,
            "right_column": inner_column.name,
        }

        if relationship not in subquery_columns:
            subquery_columns.append(relationship)

    return {
        "tables": tables,
        "columns": columns,
        "joins": joins,
        "join_columns": join_columns,
        "subquery_columns": subquery_columns,
        "selected_columns": selected_columns,
    }