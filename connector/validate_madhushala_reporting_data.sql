/*
  Madhushala reporting-data discovery and validation
  Compatible with older SQL Server versions. Read-only.

  This version deliberately avoids hard-coded legacy column names.
  Run it first, then export/send the result grids.
*/

USE [barmanager];
GO

SET NOCOUNT ON;

DECLARE @CompanyCode varchar(20);
SET @CompanyCode = '2';

DECLARE @CoreTables TABLE
(
    sort_order int,
    table_name sysname
);

INSERT INTO @CoreTables (sort_order, table_name)
VALUES
    (1, 'companymast'),
    (2, 'salesbillmain'),
    (3, 'salesbilldetail'),
    (4, 'itemmst'),
    (5, 'categorymst'),
    (6, 'tbl_Stock'),
    (7, 'purchasemain'),
    (8, 'purchasedetail'),
    (9, 'ledger'),
    (10, 'TransactionMain'),
    (11, 'TransactionDetail');

/* 1. Confirm which core tables exist */
SELECT
    core.sort_order,
    core.table_name,
    CASE WHEN table_object.object_id IS NULL THEN 0 ELSE 1 END AS table_exists
FROM @CoreTables AS core
LEFT JOIN sys.tables AS table_object
    ON table_object.name = core.table_name
    AND SCHEMA_NAME(table_object.schema_id) = 'dbo'
ORDER BY core.sort_order;

/* 2. Exact columns and types for every core table */
SELECT
    core.sort_order,
    core.table_name,
    column_object.column_id,
    column_object.name AS column_name,
    type_object.name AS data_type,
    column_object.max_length,
    column_object.precision,
    column_object.scale,
    column_object.is_nullable,
    column_object.is_identity
FROM @CoreTables AS core
JOIN sys.tables AS table_object
    ON table_object.name = core.table_name
    AND SCHEMA_NAME(table_object.schema_id) = 'dbo'
JOIN sys.columns AS column_object
    ON column_object.object_id = table_object.object_id
JOIN sys.types AS type_object
    ON type_object.user_type_id = column_object.user_type_id
ORDER BY core.sort_order, column_object.column_id;

/* 3. Likely company, date, number, item, quantity, and amount columns */
SELECT
    core.sort_order,
    core.table_name,
    column_object.name AS likely_column,
    type_object.name AS data_type,
    CASE
        WHEN LOWER(column_object.name) LIKE '%company%' THEN 'tenant/company key'
        WHEN LOWER(column_object.name) LIKE '%year%' THEN 'financial year key'
        WHEN LOWER(column_object.name) LIKE '%date%' THEN 'date'
        WHEN LOWER(column_object.name) LIKE '%time%' THEN 'date/time'
        WHEN LOWER(column_object.name) LIKE '%tmno%' OR LOWER(column_object.name) LIKE '%billno%'
            OR LOWER(column_object.name) LIKE '%invoice%' OR LOWER(column_object.name) LIKE '%vchno%'
            OR LOWER(column_object.name) LIKE '%serial%' THEN 'document/join key'
        WHEN LOWER(column_object.name) LIKE '%itemcode%' THEN 'product key'
        WHEN LOWER(column_object.name) LIKE '%qty%' OR LOWER(column_object.name) LIKE '%quantity%'
            OR LOWER(column_object.name) LIKE '%loose%' OR LOWER(column_object.name) LIKE '%box%'
            OR LOWER(column_object.name) LIKE '%stock%' THEN 'quantity/stock'
        WHEN LOWER(column_object.name) LIKE '%amount%' OR LOWER(column_object.name) LIKE '%rate%'
            OR LOWER(column_object.name) LIKE '%mrp%' OR LOWER(column_object.name) LIKE '%discount%'
            OR LOWER(column_object.name) LIKE '%debit%' OR LOWER(column_object.name) LIKE '%credit%'
            THEN 'financial value'
        ELSE 'other'
    END AS reporting_role
FROM @CoreTables AS core
JOIN sys.tables AS table_object
    ON table_object.name = core.table_name
    AND SCHEMA_NAME(table_object.schema_id) = 'dbo'
JOIN sys.columns AS column_object
    ON column_object.object_id = table_object.object_id
JOIN sys.types AS type_object
    ON type_object.user_type_id = column_object.user_type_id
WHERE
       LOWER(column_object.name) LIKE '%company%'
    OR LOWER(column_object.name) LIKE '%year%'
    OR LOWER(column_object.name) LIKE '%date%'
    OR LOWER(column_object.name) LIKE '%time%'
    OR LOWER(column_object.name) LIKE '%tmno%'
    OR LOWER(column_object.name) LIKE '%billno%'
    OR LOWER(column_object.name) LIKE '%invoice%'
    OR LOWER(column_object.name) LIKE '%vchno%'
    OR LOWER(column_object.name) LIKE '%serial%'
    OR LOWER(column_object.name) LIKE '%itemcode%'
    OR LOWER(column_object.name) LIKE '%qty%'
    OR LOWER(column_object.name) LIKE '%quantity%'
    OR LOWER(column_object.name) LIKE '%loose%'
    OR LOWER(column_object.name) LIKE '%box%'
    OR LOWER(column_object.name) LIKE '%stock%'
    OR LOWER(column_object.name) LIKE '%amount%'
    OR LOWER(column_object.name) LIKE '%rate%'
    OR LOWER(column_object.name) LIKE '%mrp%'
    OR LOWER(column_object.name) LIKE '%discount%'
    OR LOWER(column_object.name) LIKE '%debit%'
    OR LOWER(column_object.name) LIKE '%credit%'
ORDER BY core.sort_order, reporting_role, column_object.column_id;

/* 4. Primary keys and indexed columns, one row per indexed column */
SELECT
    core.sort_order,
    core.table_name,
    index_object.name AS index_name,
    index_object.is_primary_key,
    index_object.is_unique,
    index_column.key_ordinal,
    column_object.name AS indexed_column
FROM @CoreTables AS core
JOIN sys.tables AS table_object
    ON table_object.name = core.table_name
    AND SCHEMA_NAME(table_object.schema_id) = 'dbo'
JOIN sys.indexes AS index_object
    ON index_object.object_id = table_object.object_id
    AND index_object.index_id > 0
JOIN sys.index_columns AS index_column
    ON index_column.object_id = index_object.object_id
    AND index_column.index_id = index_object.index_id
    AND index_column.is_included_column = 0
JOIN sys.columns AS column_object
    ON column_object.object_id = index_column.object_id
    AND column_object.column_id = index_column.column_id
ORDER BY core.sort_order, index_object.is_primary_key DESC, index_object.name, index_column.key_ordinal;

/* 5. Common column names between likely header/detail pairs */
SELECT
    left_table.name AS left_table,
    right_table.name AS right_table,
    left_column.name AS common_column,
    left_type.name AS left_type,
    right_type.name AS right_type
FROM
(
    SELECT 'salesbillmain' AS left_name, 'salesbilldetail' AS right_name
    UNION ALL SELECT 'purchasemain', 'purchasedetail'
    UNION ALL SELECT 'TransactionMain', 'TransactionDetail'
) AS pairs
JOIN sys.tables AS left_table
    ON left_table.name = pairs.left_name AND SCHEMA_NAME(left_table.schema_id) = 'dbo'
JOIN sys.tables AS right_table
    ON right_table.name = pairs.right_name AND SCHEMA_NAME(right_table.schema_id) = 'dbo'
JOIN sys.columns AS left_column
    ON left_column.object_id = left_table.object_id
JOIN sys.columns AS right_column
    ON right_column.object_id = right_table.object_id
    AND LOWER(right_column.name) = LOWER(left_column.name)
JOIN sys.types AS left_type
    ON left_type.user_type_id = left_column.user_type_id
JOIN sys.types AS right_type
    ON right_type.user_type_id = right_column.user_type_id
ORDER BY left_table.name, left_column.column_id;

/* 6. Row counts for the core tables */
SELECT
    core.sort_order,
    core.table_name,
    SUM(partition_object.rows) AS estimated_rows
FROM @CoreTables AS core
JOIN sys.tables AS table_object
    ON table_object.name = core.table_name
    AND SCHEMA_NAME(table_object.schema_id) = 'dbo'
JOIN sys.partitions AS partition_object
    ON partition_object.object_id = table_object.object_id
    AND partition_object.index_id IN (0, 1)
GROUP BY core.sort_order, core.table_name
ORDER BY core.sort_order;

/* 7. Generate safe sample commands. Copy/run only the tables you need. */
SELECT
    core.sort_order,
    'SELECT TOP (10) * FROM dbo.' + QUOTENAME(core.table_name) + ';' AS sample_query
FROM @CoreTables AS core
JOIN sys.tables AS table_object
    ON table_object.name = core.table_name
    AND SCHEMA_NAME(table_object.schema_id) = 'dbo'
ORDER BY core.sort_order;

/* 8. Generate tenant-filtered count commands only where companycode exists */
SELECT
    core.sort_order,
    'SELECT ''' + core.table_name + ''' AS table_name, COUNT(*) AS tenant_rows FROM dbo.'
        + QUOTENAME(core.table_name)
        + ' WHERE companycode = ''' + REPLACE(@CompanyCode, '''', '''''') + ''';' AS tenant_count_query
FROM @CoreTables AS core
JOIN sys.tables AS table_object
    ON table_object.name = core.table_name
    AND SCHEMA_NAME(table_object.schema_id) = 'dbo'
JOIN sys.columns AS company_column
    ON company_column.object_id = table_object.object_id
    AND LOWER(company_column.name) = 'companycode'
ORDER BY core.sort_order;
