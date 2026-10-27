import sqlglot
from sqlglot import exp
from sqlglot.expressions import Subquery as SubqueryExpression

from .configManager import load_config


# SQL expression types allowed for read-only queries.
ALLOWED_EXPRESSIONS = (
    exp.Select,
    exp.Union,
    exp.Distinct,
    SubqueryExpression,

    exp.From,
    exp.Table,
    exp.Column,
    exp.Identifier,
    exp.Star,
    exp.Alias,
    exp.TableAlias,
    exp.Join,
    exp.Where,
    exp.Order,
    exp.Ordered,
    exp.Limit,

    exp.Literal,
    exp.Boolean,
    exp.Null,

    exp.And,
    exp.Or,
    exp.Not,

    exp.EQ,
    exp.NEQ,
    exp.GT,
    exp.GTE,
    exp.LT,
    exp.LTE,

    exp.Is,
    exp.In,
    exp.Between,
    exp.Like,
    exp.ILike,

    exp.Paren,

    exp.Add,
    exp.Sub,
    exp.Mul,
    exp.Div,
)

def validate_sql(sql: str) -> str:

    # Retrieve authorized tables.
    config = load_config()
    allowed_tables = set(config["allowed_tables"])

    # Parse SQL using PostgreSQL syntax.
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        raise ValueError(f"Invalid SQL syntax: {e}") from e

    # Require exactly one statement.
    if len(statements) != 1 or statements[0] is None:
        raise ValueError("Exactly one SQL statement is required.")

    statement = statements[0]

    # Accept SELECT queries and UNION combinations of SELECT queries.
    if not isinstance(statement, (exp.Select, exp.Union)):
        raise ValueError("Only SELECT queries are allowed.")

    # Validate every expression in the syntax tree.
    for node in statement.walk():

        if not isinstance(node, ALLOWED_EXPRESSIONS):
            raise ValueError(
                f"Unsupported SQL expression: {type(node).__name__}"
            )

    # Require at least one table.
    tables = list(statement.find_all(exp.Table))

    if not tables:
        raise ValueError("The query must reference a table.")

    # Validate EVERY referenced table.
    for table in tables:

        if table.catalog or table.db != "cdm":
            raise ValueError(
                "Only tables in the cdm schema are allowed."
            )

        if table.name.lower() not in allowed_tables:
            raise ValueError(
                f"Table '{table.name}' does not exist or is not authorized."
            )

    # Reject locking clauses, including nested SELECT queries.
    for select in statement.find_all(exp.Select):
        if select.args.get("locks"):
            raise ValueError("Locking clauses are not allowed.")

    return statement.sql(dialect="postgres")