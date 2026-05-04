from fastmcp import Context
import io
import csv
import json
import re
import logging
from datetime import date, datetime, time
from decimal import Decimal

from iris_mcp_blueprint.mcp_app import mcp

logger = logging.getLogger(__name__)

# --- SQL DATA TOOLS HELPERS & VALIDATION ---

def validate_table_name(table_name: str, table_schema: str = "SQLUser") -> str:
    if "." in table_name or "_" in table_name:
        raise ValueError(f"Invalid table_name '{table_name}'. Do not include schema or underscores.")
    return f"{table_schema}.{table_name}" if table_schema else table_name

# Identifier check that *does* allow underscores — many real IRIS tables/columns have them.
# Used by export_table when assembling SELECT statements from caller-supplied names.
_SQL_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _check_sql_ident(name: str, label: str) -> str:
    if not _SQL_IDENT_RE.match(name or ""):
        raise ValueError(f"Invalid {label} identifier: {name!r}")
    return name

def _json_default(o):
    """JSON fallback for IRIS values that are not natively serializable."""
    if isinstance(o, (datetime, date, time)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (bytes, bytearray, memoryview)):
        return bytes(o).decode("utf-8", errors="replace")
    return str(o)

def format_as_table(headers: list, rows: list) -> str:
    if not rows: return "No results found."
    header_line = " | ".join(headers)
    separator = "-" * len(header_line)
    data_lines = [" | ".join(map(str, row)) for row in rows]
    return f"{header_line}\n{separator}\n" + "\n".join(data_lines)

def execute_sql_query(db, sql: str, parameters: list | None = None) -> str:
    """Run SQL on an open IRIS db handle. Shared by MCP tools and resources."""
    if db is None:
        return "SQL Error: database connection is not available."
    params = parameters if parameters is not None else []
    try:
        with db.cursor() as cursor:
            cursor.execute(sql, params)
            if not cursor.description:
                db.commit()
                n = cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0
                return f"OK (no result set). Rows affected: {n}"
            rows = cursor.fetchall()
            headers = [col[0] for col in cursor.description] if cursor.description else []
            return format_as_table(headers, rows)
    except Exception as e:
        return f"SQL Error: {e}"

# --- SQL DATA TOOLS ---

@mcp.tool()
def fetch_data(ctx: Context, sql: str, parameters: list | None = None) -> str:
    """
    Execute SQL and return results as a table. For DDL/DML with no result set, returns a short status line.
    Args:
        ctx: The context of the tool call.
        sql: The SQL query to execute.
        parameters: The parameters to pass to the SQL query.
    """
    db = ctx.request_context.lifespan_context["db"]
    return execute_sql_query(db, sql, parameters)

@mcp.tool()
def insert_data(ctx: Context, table_name: str, values: dict, table_schema: str = "SQLUser") -> str:
    """
    Insert a single row into a table.
    Args:
        ctx: The context of the tool call.
        table_name: The name of the table to insert the data into.
        values: The values to insert into the table.
        table_schema: The schema of the table to insert the data into.
    """
    db = ctx.request_context.lifespan_context["db"]
    try:
        full_name = validate_table_name(table_name, table_schema)
        cols, placeholders = ", ".join(values.keys()), ", ".join(["?"] * len(values))
        sql = f"INSERT INTO {full_name} ({cols}) VALUES ({placeholders})"
        with db.cursor() as cur:
            cur.execute(sql, tuple(values.values()))
            db.commit()
        return f"Inserted into {full_name}."
    except Exception as e:
        return f"Insert failed: {e}"

@mcp.tool()
def get_tables(ctx: Context, table_schema: str = "") -> str:
    """
    List all tables in a specific schema.
    Args:
        ctx: The context of the tool call.
        table_schema: The schema of the tables to list.
    """
    db = ctx.request_context.lifespan_context["db"]
    sql = "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
    if table_schema:
        sql += "WHERE TABLE_SCHEMA = ?"
        params = [table_schema]
    else:
        params = []
    with db.cursor() as cur:
        cur.execute(sql, params)
        return format_as_table(["Schema", "Table"], cur.fetchall())

@mcp.tool()
def describe_table(ctx: Context, table_name: str, table_schema: str = "SQLUser") -> str:
    """
    Show columns and types for a table.
    Args:
        ctx: The context of the tool call.
        table_name: The name of the table to describe.
        table_schema: The schema of the table to describe.
    """
    db = ctx.request_context.lifespan_context["db"]
    sql = "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME=? AND TABLE_SCHEMA=?"
    with db.cursor() as cur:
        cur.execute(sql, [table_name, table_schema])
        return format_as_table(["Column", "Type"], cur.fetchall())

@mcp.tool()
def create_index(ctx: Context, table_name: str, column_name: str, index_name: str = None, table_schema: str = "SQLUser") -> str:
    """
    Creates a standard index to speed up queries.
    Args:
        ctx: The context of the tool call.
        table_name: The name of the table to create the index on.
        column_name: The name of the column to create the index on.
        index_name: The name of the index to create.
        table_schema: The schema of the table to create the index on.
    """
    db = ctx.request_context.lifespan_context["db"]
    full_table = validate_table_name(table_name, table_schema)
    idx_name = index_name or f"{table_name}_{column_name}_idx"
    sql = f"CREATE INDEX {idx_name} ON {full_table}({column_name})"
    try:
        with db.cursor() as cur:
            cur.execute(sql)
            db.commit()
        return f"Index {idx_name} created on {full_table}."
    except Exception as e:
        return f"Index creation failed: {e}"

@mcp.tool()
def import_csv_to_iris(ctx: Context, table_name: str, csv_content: str, table_schema: str = "SQLUser") -> str:
    """
    Creates a table and imports data from a CSV string.
    The first row of the CSV must be the header (column names).
    All columns will be created as VARCHAR(255) for this blueprint.
    Args:
        ctx: The context of the tool call.
        table_name: The name of the table to import the data into.
        csv_content: The content of the CSV file to import.
        table_schema: The schema of the table to import the data into.
    """
    # 1. Access IRIS resources from context
    db = ctx.request_context.lifespan_context["db"]
    
    try:
        # Use io.StringIO to treat the string like a file
        f = io.StringIO(csv_content.strip())
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)

        if not headers:
            return "Error: CSV has no headers."

        # 2. Validate and Create Table
        # In a blueprint, we assume columns are VARCHAR(255) for simplicity
        full_name = validate_table_name(table_name, table_schema)
        col_defs = [f"{col.replace(' ', '_')} VARCHAR(255)" for col in headers]
        create_sql = f"CREATE TABLE {full_name} ({', '.join(col_defs)})"

        with db.cursor() as cursor:
            # Create the table
            cursor.execute(create_sql)
            
            # 3. Prepare Batch Insert
            clean_headers = [h.replace(' ', '_') for h in headers]
            placeholders = ", ".join(["?"] * len(clean_headers))
            insert_sql = f"INSERT INTO {full_name} ({', '.join(clean_headers)}) VALUES ({placeholders})"
            
            # Convert list of dicts to list of tuples for executemany
            data_to_insert = [tuple(row[h] for h in headers) for row in rows]
            
            cursor.executemany(insert_sql, data_to_insert)
            db.commit()

        return f"Successfully created {full_name} and imported {len(rows)} rows."

    except Exception as e:
        if db: db.rollback()
        return f"Failed to import CSV: {e}"

@mcp.tool()
def export_table(
    ctx: Context,
    table_name: str,
    table_schema: str = "SQLUser",
    format: str = "json",
    columns: list | None = None,
    where: str = "",
    limit: int = 1000,
) -> str:
    """
    Export rows from an existing IRIS table as JSON, CSV, or TXT (pipe-separated).

    The result is returned as a single string the caller can preview, copy to a file,
    or stream to a downstream client. For large tables narrow the result with
    `columns`, `where`, and/or `limit` to keep responses manageable.

    Args:
        ctx: The context of the tool call.
        table_name: Bare table name (letters, digits, underscore; no schema, no dot).
        table_schema: Schema of the table (default 'SQLUser').
        format: Output format — 'json' (list of objects), 'csv' (RFC 4180, comma
            delimiter, CRLF line terminator), or 'txt' (pipe-separated columns +
            ruler, same look as other tools' output). Case-insensitive.
        columns: Optional list of column names to export. None or empty = all columns.
        where: Optional SQL fragment placed after WHERE (do **not** include the
            'WHERE' keyword). Example: "Age > 30 AND City = 'Rome'". Caller is
            responsible for escaping; consider parameterized fetch_data for
            untrusted input.
        limit: Maximum number of rows to return. Pass 0 or a negative value to
            disable the cap (use only for known-small tables).
    """
    db = ctx.request_context.lifespan_context["db"]
    if db is None:
        return "Export Error: database connection is not available."

    fmt = (format or "json").strip().lower()
    if fmt not in {"json", "csv", "txt"}:
        return f"Export Error: unsupported format '{format}'. Use 'json', 'csv', or 'txt'."

    try:
        _check_sql_ident(table_name, "table_name")
        _check_sql_ident(table_schema, "table_schema")
        if columns:
            for c in columns:
                _check_sql_ident(c, "column")
            select_list = ", ".join(columns)
        else:
            select_list = "*"

        sql = f"SELECT {select_list} FROM {table_schema}.{table_name}"
        if where.strip():
            sql += f" WHERE {where.strip()}"
        if limit and limit > 0:
            # IRIS SQL: TOP comes right after SELECT, so re-emit the statement.
            sql = f"SELECT TOP {int(limit)} {select_list} FROM {table_schema}.{table_name}"
            if where.strip():
                sql += f" WHERE {where.strip()}"

        with db.cursor() as cur:
            cur.execute(sql)
            headers = [col[0] for col in cur.description] if cur.description else []
            rows = cur.fetchall()

        if not headers:
            return f"Export Error: no result set returned for {table_schema}.{table_name}."

        if fmt == "json":
            payload = [dict(zip(headers, row)) for row in rows]
            return json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default)

        if fmt == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf, lineterminator="\r\n")
            writer.writerow(headers)
            for row in rows:
                writer.writerow(["" if v is None else _json_default(v) if not isinstance(v, (str, int, float, bool)) else v for v in row])
            return buf.getvalue()

        # fmt == "txt"
        return format_as_table(headers, rows)

    except ValueError as ve:
        return f"Export Error: {ve}"
    except Exception as e:
        return f"Export failed for {table_schema}.{table_name}: {e}"
