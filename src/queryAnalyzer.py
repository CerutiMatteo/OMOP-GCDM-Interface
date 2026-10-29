import sqlglot
from sqlglot import exp


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
    selected_columns = []

    for table in statement.find_all(exp.Table):
        info = {"schema": table.db, "name": table.name, "alias": table.alias_or_name}
        if info not in tables:
            tables.append(info)
        aliases[table.alias_or_name] = table.name

    single_table_alias = tables[0]["alias"] if len(tables) == 1 else None

    def resolve_alias(column):
        return column.table or single_table_alias

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

    return {
        "tables": tables,
        "columns": columns,
        "joins": joins,
        "join_columns": join_columns,
        "selected_columns": selected_columns,
    }