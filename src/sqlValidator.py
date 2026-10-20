
import sqlglot
from sqlglot import exp


# Tables authorized for SQL execution.
ALLOWED_TABLES = {
    "person",
    "specimen",
    "variant_occurrence",
    "target_gene",
    "variant_annotation",
}

# SQL expression types allowed in the first execution version.
ALLOWED_EXPRESSIONS = (
    exp.Select,
    exp.From,
    exp.Table,
    exp.Column,
    exp.Identifier,
    exp.Star,
    exp.Alias,
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
    exp.Paren,
    exp.Add,
    exp.Sub,
    exp.Mul,
    exp.Div,
)


def validate_sql(sql: str) -> str:
    # Parse SQL using PostgreSQL syntax.
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError as e:
        raise ValueError(f"Invalid SQL syntax: {e}") from e

    # Require exactly one statement.
    if len(statements) != 1 or statements[0] is None:
        raise ValueError("Exactly one SQL statement is required.")

    statement = statements[0]

    # Accept only SELECT statements.
    if not isinstance(statement, exp.Select):
        raise ValueError("Only SELECT queries are allowed.")

    # Reject any SQL expression not explicitly supported.
    for node in statement.walk():
        if not isinstance(node, ALLOWED_EXPRESSIONS):
            raise ValueError(
                f"Unsupported SQL expression: {type(node).__name__}"
            )

    # Require at least one table.
    tables = list(statement.find_all(exp.Table))

    if not tables:
        raise ValueError("The query must reference a table.")

    # Check every referenced table.
    for table in tables:
        if table.catalog or table.db != "cdm":
            raise ValueError("Only tables in the cdm schema are allowed.")

        if table.name.lower() not in ALLOWED_TABLES:
            raise ValueError(f"Table '{table.name}' does not exist or is not authorized.")

    # Reject locking clauses.
    if statement.args.get("locks"):
        raise ValueError("Locking clauses are not allowed.")

    return statement.sql(dialect="postgres")
