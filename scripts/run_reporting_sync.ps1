$ErrorActionPreference = "Stop"

if (-not $env:MSSQL_CONNECTION_STRING) {
    throw "Set MSSQL_CONNECTION_STRING."
}
if (-not ($env:REPORT_SYNC_DATABASE_URL -or $env:DATABASE_URL)) {
    throw "Set REPORT_SYNC_DATABASE_URL to Railway PostgreSQL's public connection URL."
}
if (-not $env:REPORT_TENANT_ID) {
    throw "Set REPORT_TENANT_ID to the local companycode being synchronized."
}

py -3.12 scripts/sync_sqlserver_to_postgres.py
