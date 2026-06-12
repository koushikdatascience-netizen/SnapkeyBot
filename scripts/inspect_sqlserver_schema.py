import argparse
import json
import os

try:
    import pyodbc
except ImportError as exc:
    raise SystemExit('Install connector dependencies: py -3.12 -m pip install -e ".[connector]"') from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect an accessible SQL Server database.")
    parser.add_argument(
        "--list-databases",
        action="store_true",
        help="List databases visible to the configured login instead of inspecting table schemas.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    connection_string = os.environ.get("MSSQL_CONNECTION_STRING", "")
    if not connection_string:
        raise SystemExit("Set MSSQL_CONNECTION_STRING")
    try:
        database = pyodbc.connect(connection_string, timeout=8)
    except pyodbc.Error as exc:
        installed_drivers = ", ".join(pyodbc.drivers()) or "none"
        message = str(exc)
        hints = [f"Installed ODBC drivers: {installed_drivers}"]
        if "IM002" in message:
            hints.append(
                "The DRIVER name in MSSQL_CONNECTION_STRING must exactly match one of the installed drivers."
            )
        if "No credentials are available in the security package" in message:
            hints.append(
                "Windows authentication failed. Run this command from your normal Windows PowerShell session, "
                "or use a read-only SQL login with UID and PWD."
            )
        if "Server is not found or not accessible" in message:
            hints.append(
                r"For the local SQL Express instance, use SERVER=.\SQLEXPRESS instead of SERVER=localhost."
            )
        if "Cannot open database" in message or "(4060)" in message:
            hints.append(
                "The requested database does not exist or this login cannot access it. "
                "Set DATABASE=master and run this script with --list-databases."
            )
        raise SystemExit(f"Could not connect to SQL Server:\n{message}\n\n" + "\n".join(hints)) from exc
    try:
        cursor = database.cursor()
        if args.list_databases:
            cursor.execute("SELECT name, state_desc FROM sys.databases ORDER BY name")
            print(json.dumps([{"database": str(name), "state": str(state)} for name, state in cursor], indent=2))
            return
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
