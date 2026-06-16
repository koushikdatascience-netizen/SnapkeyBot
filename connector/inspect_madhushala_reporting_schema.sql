/*
  Madhushala reporting-schema inspection
  Read-only: this script does not modify any data.

  Run in SQL Server Management Studio against the Madhushala database.
  Change barmanager below if the live database uses another name.
*/

USE [barmanager];
GO

SET NOCOUNT ON;

/* 1. Database identity and size */
SELECT
    DB_NAME() AS database_name,
    DATABASEPROPERTYEX(DB_NAME(), 'Status') AS database_status,
    SUM(size) * 8.0 / 1024 AS allocated_mb
FROM sys.database_files;

/* 2. Tables with estimated row counts, largest first */
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    SUM(p.rows) AS estimated_rows
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.partitions AS p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
GROUP BY s.name, t.name
ORDER BY estimated_rows DESC, s.name, t.name;

/* 3. Columns for likely reporting tables */
DECLARE @CandidateTables TABLE (table_name sysname PRIMARY KEY);
INSERT INTO @CandidateTables (table_name)
VALUES
    ('companymast'),
    ('salesbillmain'),
    ('salesbilldetail'),
    ('itemmst'),
    ('categorymst'),
    ('groupmst'),
    ('tbl_Stock'),
    ('openingstockmst'),
    ('openingStockDetail'),
    ('purchasemain'),
    ('purchasedetail'),
    ('PurchaseTaxDetail'),
    ('ledger'),
    ('ledger_opening'),
    ('TransactionMain'),
    ('TransactionDetail'),
    ('membersale'),
    ('customerDetails'),
    ('payment_main'),
    ('payment_detail');

SELECT
    s.name AS schema_name,
    t.name AS table_name,
    c.column_id,
    c.name AS column_name,
    ty.name AS data_type,
    CASE
        WHEN ty.name IN ('varchar', 'char', 'varbinary', 'binary')
            THEN CASE WHEN c.max_length = -1 THEN 'MAX' ELSE CAST(c.max_length AS varchar(10)) END
        WHEN ty.name IN ('nvarchar', 'nchar')
            THEN CASE WHEN c.max_length = -1 THEN 'MAX' ELSE CAST(c.max_length / 2 AS varchar(10)) END
        WHEN ty.name IN ('decimal', 'numeric')
            THEN CONCAT(c.precision, ',', c.scale)
        ELSE ''
    END AS type_detail,
    c.is_nullable,
    c.is_identity
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.columns AS c ON c.object_id = t.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
JOIN @CandidateTables AS wanted ON wanted.table_name = t.name
ORDER BY t.name, c.column_id;

/* 4. Primary keys, unique keys, and indexes on candidate tables */
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    i.name AS index_name,
    i.is_primary_key,
    i.is_unique,
    STUFF(
        (
            SELECT ', ' + indexed_column.name
            FROM sys.index_columns AS indexed_ic
            JOIN sys.columns AS indexed_column
                ON indexed_column.object_id = indexed_ic.object_id
                AND indexed_column.column_id = indexed_ic.column_id
            WHERE indexed_ic.object_id = i.object_id
              AND indexed_ic.index_id = i.index_id
              AND indexed_ic.is_included_column = 0
            ORDER BY indexed_ic.key_ordinal
            FOR XML PATH(''), TYPE
        ).value('.', 'nvarchar(max)'),
        1,
        2,
        ''
    ) AS indexed_columns
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.indexes AS i ON i.object_id = t.object_id AND i.index_id > 0
JOIN @CandidateTables AS wanted ON wanted.table_name = t.name
ORDER BY t.name, i.is_primary_key DESC, i.name;

/* 5. Foreign-key relationships */
SELECT
    OBJECT_SCHEMA_NAME(fk.parent_object_id) AS child_schema,
    OBJECT_NAME(fk.parent_object_id) AS child_table,
    child_col.name AS child_column,
    OBJECT_SCHEMA_NAME(fk.referenced_object_id) AS parent_schema,
    OBJECT_NAME(fk.referenced_object_id) AS parent_table,
    parent_col.name AS parent_column,
    fk.name AS constraint_name
FROM sys.foreign_keys AS fk
JOIN sys.foreign_key_columns AS fkc ON fkc.constraint_object_id = fk.object_id
JOIN sys.columns AS child_col
    ON child_col.object_id = fkc.parent_object_id
    AND child_col.column_id = fkc.parent_column_id
JOIN sys.columns AS parent_col
    ON parent_col.object_id = fkc.referenced_object_id
    AND parent_col.column_id = fkc.referenced_column_id
ORDER BY child_table, constraint_name;

/* 6. Candidate date/time columns, needed for daily/monthly reports */
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    c.name AS date_column,
    ty.name AS data_type
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.columns AS c ON c.object_id = t.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE ty.name IN ('date', 'datetime', 'datetime2', 'smalldatetime', 'time')
   OR c.name LIKE '%date%'
   OR c.name LIKE '%time%'
ORDER BY t.name, c.column_id;

/* 7. Existing views and stored procedures that may already contain report logic */
SELECT
    'VIEW' AS object_type,
    s.name AS schema_name,
    v.name AS object_name
FROM sys.views AS v
JOIN sys.schemas AS s ON s.schema_id = v.schema_id
UNION ALL
SELECT
    'PROCEDURE',
    s.name,
    p.name
FROM sys.procedures AS p
JOIN sys.schemas AS s ON s.schema_id = p.schema_id
ORDER BY object_type, object_name;

/* 8. Company/tenant codes. Use this as tenant_id in the cloud reporting tables. */
IF OBJECT_ID('dbo.companymast', 'U') IS NOT NULL
BEGIN
    SELECT * FROM dbo.companymast;
END;

/* 9. Small samples from the core reporting candidates. */
IF OBJECT_ID('dbo.salesbillmain', 'U') IS NOT NULL SELECT TOP (5) * FROM dbo.salesbillmain ORDER BY 1 DESC;
IF OBJECT_ID('dbo.salesbilldetail', 'U') IS NOT NULL SELECT TOP (5) * FROM dbo.salesbilldetail ORDER BY 1 DESC;
IF OBJECT_ID('dbo.itemmst', 'U') IS NOT NULL SELECT TOP (5) * FROM dbo.itemmst ORDER BY 1;
IF OBJECT_ID('dbo.tbl_Stock', 'U') IS NOT NULL SELECT TOP (5) * FROM dbo.tbl_Stock ORDER BY 1;
IF OBJECT_ID('dbo.purchasemain', 'U') IS NOT NULL SELECT TOP (5) * FROM dbo.purchasemain ORDER BY 1 DESC;
IF OBJECT_ID('dbo.purchasedetail', 'U') IS NOT NULL SELECT TOP (5) * FROM dbo.purchasedetail ORDER BY 1 DESC;
IF OBJECT_ID('dbo.ledger', 'U') IS NOT NULL SELECT TOP (5) * FROM dbo.ledger ORDER BY 1;
IF OBJECT_ID('dbo.TransactionMain', 'U') IS NOT NULL SELECT TOP (5) * FROM dbo.TransactionMain ORDER BY 1 DESC;
IF OBJECT_ID('dbo.TransactionDetail', 'U') IS NOT NULL SELECT TOP (5) * FROM dbo.TransactionDetail ORDER BY 1 DESC;

/* 10. Search SQL modules for references to the important reporting tables. */
SELECT
    OBJECT_SCHEMA_NAME(m.object_id) AS schema_name,
    OBJECT_NAME(m.object_id) AS object_name,
    o.type_desc
FROM sys.sql_modules AS m
JOIN sys.objects AS o ON o.object_id = m.object_id
WHERE m.definition LIKE '%salesbillmain%'
   OR m.definition LIKE '%salesbilldetail%'
   OR m.definition LIKE '%purchasemain%'
   OR m.definition LIKE '%purchasedetail%'
   OR m.definition LIKE '%tbl_Stock%'
   OR m.definition LIKE '%TransactionMain%'
ORDER BY o.type_desc, object_name;
