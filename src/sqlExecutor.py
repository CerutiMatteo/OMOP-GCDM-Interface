
import pandas as pd
from .sqlValidator import validate_sql


def execute_sql(sql: str, connection, max_rows: int = 1000) -> pd.DataFrame:
    # Validate the requested row limit.
    if not isinstance(max_rows, int) or isinstance(max_rows, bool):
        raise ValueError("The row limit must be an integer.")

    if not 1 <= max_rows <= 10000:
        raise ValueError("The row limit must be between 1 and 10000.")

    # Validate the generated SQL statement.
    validated_sql = validate_sql(sql)

    # Apply an outer limit to the validated SELECT query.
    limited_sql = (
        f"SELECT * FROM ({validated_sql}) AS query_results "
        f"LIMIT {max_rows}"
    )

    # Execute the query within a read-only transaction.
    with connection.transaction():
        with connection.cursor() as cur:

            # Enforce read-only execution and a query timeout.
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '180s'")

            # Execute the validated and limited query.
            cur.execute(limited_sql)

            # Retrieve column names and rows.
            columns = [column.name for column in cur.description]
            rows = cur.fetchall()

    # Return the query results as a DataFrame.
    return pd.DataFrame(rows, columns=columns)
