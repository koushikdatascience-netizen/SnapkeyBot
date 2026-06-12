import json
import os

try:
    import pyodbc
except ImportError as exc:
    raise SystemExit('Install connector dependencies: py -3.12 -m pip install -e ".[connector]"') from exc


def main() -> None:
    connection_string = os.environ.get("MSSQL_CONNECTION_STRING", "")
    if not connection_string:
        raise SystemExit("Set MSSQL_CONNECTION_STRING")
    database = pyodbc.connect(connection_string, timeout=8)
    try:
        cursor = database.cursor()
        cursor.timeout = 8
        cursor.execute(
            """
            SELECT
                s.name AS schema_name,
                t.name AS table_name,
                c.column_id,
                c.name AS column_name,
                TYPE_NAME(c.user_type_id) AS data_type
            FROM sys.tables t
            JOIN sys.schemas s ON s.schema_id = t.schema_id
            JOIN sys.columns c ON c.object_id = t.object_id
            ORDER BY s.name, t.name, c.column_id
            """
        )
        tables: dict[str, list[dict[str, str]]] = {}
        for schema_name, table_name, _column_id, column_name, data_type in cursor.fetchall():
            tables.setdefault(f"{schema_name}.{table_name}", []).append(
                {"column": str(column_name), "type": str(data_type)}
            )
        print(json.dumps(tables, indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()
