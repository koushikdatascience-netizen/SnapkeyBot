$ErrorActionPreference = "Stop"

if (-not $env:MSSQL_CONNECTION_STRING) {
    throw "Set MSSQL_CONNECTION_STRING before starting the connector."
}
if (-not $env:CONNECTOR_SECRET) {
    throw "Set CONNECTOR_SECRET before starting the connector."
}

py -3.12 -m uvicorn connector.sqlserver_connector:app --host 127.0.0.1 --port 8090
