
import sqlglot
from sqlglot import exp


# Supported comparison operators for the visual editor.
SUPPORTED_OPERATORS = {
    exp.EQ: "=",
    exp.NEQ: "!=",
    exp.GT: ">",
    exp.GTE: ">=",
    exp.LT: "<",
    exp.LTE: "<=",
}


def _parse_sql(sql: str):
    """
    Parse a single PostgreSQL SQL statement.

    This function only checks whether the statement can be parsed.
    Security validation remains the responsibility of sqlValidator.py.
    """

    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        raise ValueError(f"Invalid SQL syntax: {e}") from e

    if len(statements) != 1 or statements[0] is None:
        raise ValueError("Exactly one SQL statement is required.")

    statement = statements[0]

    if not isinstance(statement, (exp.Select, exp.Union)):
        raise ValueError("Only SELECT queries are supported.")

    return statement


def _get_literal_value(node):
    """
    Extract the Python value and type of a SQL literal.

    Return None when the expression cannot be represented
    as a simple editable value.
    """

    if isinstance(node, exp.Literal):

        if node.is_string:
            return {
                "value": node.this,
                "value_type": "string",
            }

        try:
            value = int(node.this)
            value_type = "integer"

        except ValueError:
            try:
                value = float(node.this)
                value_type = "float"

            except ValueError:
                return None

        return {
            "value": value,
            "value_type": value_type,
        }

    if isinstance(node, exp.Boolean):
        return {
            "value": bool(node.this),
            "value_type": "boolean",
        }

    return None


def _create_literal(value, value_type):
    """
    Convert a Python value into a SQLGlot literal.

    The value type is preserved to avoid accidentally
    changing the meaning of the SQL expression.
    """

    if value_type == "string":
        return exp.Literal.string(str(value))

    if value_type == "integer":

        if isinstance(value, bool):
            raise ValueError("An integer value is required.")

        try:
            converted = int(value)
        except (ValueError, TypeError, OverflowError):
            raise ValueError("Invalid integer value.")

        if str(converted) != str(value).strip():
            raise ValueError("Invalid integer value.")

        return exp.Literal.number(converted)

    if value_type == "float":

        if isinstance(value, bool):
            raise ValueError("A numeric value is required.")

        try:
            converted = float(value)
        except (ValueError, TypeError, OverflowError):
            raise ValueError("Invalid numeric value.")

        if not (
            float("-inf") < converted < float("inf")
        ):
            raise ValueError("The numeric value must be finite.")

        return exp.Literal.number(str(converted))

    if value_type == "boolean":

        if not isinstance(value, bool):
            raise ValueError("A boolean value is required.")

        return exp.Boolean(this=value)

    raise ValueError(f"Unsupported value type: {value_type}")


def _get_column_name(node):
    """
    Return the SQL representation of a column.

    Only direct column references are supported.
    Calculations and SQL functions are excluded.
    """

    if isinstance(node, exp.Column):
        return node.sql(dialect="postgres")

    return None


def _get_comparison_parameter(node, parameter_id):
    """
    Extract a simple comparison from the SQL syntax tree.

    Supported forms:
        column OP literal
        literal OP column

    Comparisons between two columns are not editable.
    """

    operator = None

    for expression_type, symbol in SUPPORTED_OPERATORS.items():
        if isinstance(node, expression_type):
            operator = symbol
            break

    if operator is None:
        return None

    left = node.this
    right = node.expression

    left_column = _get_column_name(left)
    right_column = _get_column_name(right)

    left_literal = _get_literal_value(left)
    right_literal = _get_literal_value(right)

    # Example: p.year_of_birth < 1980
    if left_column is not None and right_literal is not None:

        return {
            "id": parameter_id,
            "type": "comparison",
            "column": left_column,
            "operator": operator,
            "value": right_literal["value"],
            "value_type": right_literal["value_type"],
            "literal_side": "right",
        }

    # Example: 1980 > p.year_of_birth
    if right_column is not None and left_literal is not None:

        return {
            "id": parameter_id,
            "type": "comparison",
            "column": right_column,
            "operator": operator,
            "value": left_literal["value"],
            "value_type": left_literal["value_type"],
            "literal_side": "left",
        }

    return None


def _collect_editable_nodes(statement):
    """
    Find editable SQL expressions and assign stable IDs
    for the current version of the query.

    IDs are positional and must be recalculated whenever
    the SQL structure is manually edited.
    """

    editable_nodes = []

    # Inspect WHERE clauses, including nested SELECT queries.
    for where in statement.find_all(exp.Where):

        for node in where.walk():

            if not isinstance(
                node,
                tuple(SUPPORTED_OPERATORS.keys()),
            ):
                continue

            parameter = _get_comparison_parameter(
                node,
                len(editable_nodes),
            )

            if parameter is not None:
                editable_nodes.append((node, parameter))

    # Inspect LIMIT clauses, including nested SELECT queries.
    for limit in statement.find_all(exp.Limit):

        literal = _get_literal_value(
            limit.expression
        )

        if literal is None:
            continue

        if literal["value_type"] != "integer":
            continue

        if literal["value"] < 0:
            continue

        parameter = {
            "id": len(editable_nodes),
            "type": "limit",
            "column": None,
            "operator": None,
            "value": literal["value"],
            "value_type": "integer",
            "literal_side": None,
        }

        editable_nodes.append((limit, parameter))

    return editable_nodes


def extract_parameters(sql: str):
    """
    Extract parameters that can be modified visually.

    Example output:

    [
        {
            "id": 0,
            "type": "comparison",
            "column": "p.year_of_birth",
            "operator": "<",
            "value": 1980,
            "value_type": "integer",
            "literal_side": "right",
        },
        {
            "id": 1,
            "type": "limit",
            "column": None,
            "operator": None,
            "value": 100,
            "value_type": "integer",
            "literal_side": None,
        },
    ]
    """

    statement = _parse_sql(sql)

    editable_nodes = _collect_editable_nodes(statement)

    return [
        parameter
        for _, parameter in editable_nodes
    ]


def update_parameter(sql: str, parameter_id: int, new_value):
    """
    Update one editable parameter in a SQL query.

    The original query is parsed into an AST.
    Only the selected literal is replaced.

    All other expressions remain structurally unchanged.

    Args:
        sql:
            Current PostgreSQL SQL query.

        parameter_id:
            ID returned by extract_parameters().

        new_value:
            Replacement value.

    Returns:
        Updated SQL query as a string.
    """

    statement = _parse_sql(sql)

    editable_nodes = _collect_editable_nodes(statement)

    if (
        not isinstance(parameter_id, int)
        or isinstance(parameter_id, bool)
        or parameter_id < 0
        or parameter_id >= len(editable_nodes)
    ):
        raise ValueError("Invalid parameter ID.")

    node, parameter = editable_nodes[parameter_id]

    value_type = parameter["value_type"]

    new_literal = _create_literal(
        new_value,
        value_type,
    )

    # Update a comparison literal.
    if parameter["type"] == "comparison":

        if parameter["literal_side"] == "right":
            node.set("expression", new_literal)

        else:
            node.set("this", new_literal)

    # Update a LIMIT literal.
    elif parameter["type"] == "limit":
        if (isinstance(new_value, bool) or not isinstance(new_value, int) or new_value < 1):
            raise ValueError("LIMIT must be a positive integer greater than zero.")
        node.set("expression", exp.Literal.number(new_value))

    else:
        raise ValueError("Unsupported parameter type.")

    return statement.sql(dialect="postgres")
