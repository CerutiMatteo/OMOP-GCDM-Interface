import sqlglot
from sqlglot import exp
from sqlglot.expressions import Subquery as SubqueryExpression

from .configManager import load_config


# SQL expression types allowed for read-only queries.
ALLOWED_EXPRESSIONS = (
    exp.Select,
    exp.Union,
    exp.Intersect,
    exp.Except,
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
    exp.Group,
    exp.Having,
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
    exp.Exists,
    exp.Between,
    exp.Like,
    exp.ILike,

    exp.Paren,

    exp.Add,
    exp.Sub,
    exp.Mul,
    exp.Div,

    # Aggregate functions
    exp.Count,
    exp.Sum,
    exp.Avg,
    exp.Min,
    exp.Max,
)

def validate_genomic_joins(statement): # ho notato errore nel creare il join

    for select in statement.find_all(exp.Select):

        # Map table aliases to actual table names
        aliases = {}

        for table in select.find_all(exp.Table):
            # Only consider tables belonging directly
            # to this SELECT scope.
            if table.find_ancestor(exp.Select) is not select:
                continue

            aliases[table.alias_or_name] = table.name.lower()

        # Check JOIN conditions in this SELECT.
        for join in select.args.get("joins") or []:

            condition = join.args.get("on")

            if condition is None:
                continue

            for equality in condition.find_all(exp.EQ):

                left = equality.left
                right = equality.right

                if not (
                    isinstance(left, exp.Column)
                    and isinstance(right, exp.Column)
                ):
                    continue

                left_table = aliases.get(left.table)
                right_table = aliases.get(right.table)

                if {
                    left_table,
                    right_table
                } != {
                    "variant_occurrence",
                    "variant_annotation"
                }:
                    continue

                # Identify columns independently of JOIN order.
                if left_table == "variant_occurrence":
                    vo_column = left.name.lower()
                    va_column = right.name.lower()
                else:
                    vo_column = right.name.lower()
                    va_column = left.name.lower()

                if (
                    vo_column != "variant_occurrence_id"
                    or va_column != "variant_occurrence_id"
                ):
                    raise ValueError(
                        "Invalid genomic JOIN: "
                        "variant_annotation must be joined to "
                        "variant_occurrence using "
                        "variant_annotation.variant_occurrence_id = "
                        "variant_occurrence.variant_occurrence_id."
                    )

def validate_target_gene_joins(statement, require_both_genes=False):

    if not require_both_genes:
        return

    for select in statement.find_all(exp.Select):

        for join in select.args.get("joins") or []:

            joined_table = join.this

            if not isinstance(joined_table, exp.Table):
                continue

            if joined_table.name.lower() != "target_gene":
                continue

            condition = join.args.get("on")

            if condition is None:
                raise ValueError(
                    "Missing JOIN condition for target_gene."
                )

            columns = {
                column.name.lower()
                for column in condition.find_all(exp.Column)
            }

            if not {
                "target_gene1_id",
                "target_gene2_id"
            }.issubset(columns):

                raise ValueError(
                    "Incomplete genomic JOIN: queries requesting "
                    "all genes associated with variants must "
                    "consider both target_gene1_id and "
                    "target_gene2_id."
                )

def validate_sql(sql: str, require_both_genes: bool = False) -> str:

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
    if not isinstance(statement, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
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

    validate_genomic_joins(statement)

    validate_target_gene_joins(
        statement,
        require_both_genes=require_both_genes
    )

    return statement.sql(dialect="postgres")