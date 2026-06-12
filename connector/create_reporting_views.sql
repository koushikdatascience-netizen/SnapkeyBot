/*
Run this script inside the barmanager database as an administrator.

It creates the only two views Snapkey can query. The connector never accepts
raw SQL from users.
*/

USE barmanager;
GO

/*
SQL Server 2014 does not support CREATE OR ALTER VIEW, so use dynamic SQL to
create or replace the views.
*/
IF OBJECT_ID('dbo.snapkey_sales', 'V') IS NOT NULL
    DROP VIEW dbo.snapkey_sales;
GO

EXEC(N'
CREATE VIEW dbo.snapkey_sales AS
SELECT
    CAST(d.companycode AS nvarchar(100)) AS tenant_id,
    COALESCE(m.trndate, d.trndate) AS sold_at,
    COALESCE(NULLIF(i.itemname, ''''), d.itemcode) AS product_name,
    COALESCE(NULLIF(c.categoryname, ''''), ''Uncategorized'') AS category_name,
    CAST(COALESCE(d.qnty, 0) AS decimal(18, 2)) AS quantity,
    CAST(
        COALESCE(d.itemAmount, 0) - COALESCE(d.itemDiscountAmount, 0)
        AS decimal(18, 2)
    ) AS net_amount
FROM dbo.salesbilldetail AS d
INNER JOIN dbo.salesbillmain AS m
    ON m.companycode = d.companycode
   AND m.yearcode = d.yearcode
   AND m.trnno = d.trnno
   AND m.billType = d.billType
LEFT JOIN dbo.itemmst AS i
    ON i.companycode = d.companycode
   AND i.itemcode = d.itemcode
LEFT JOIN dbo.categorymst AS c
    ON c.companycode = i.companycode
   AND c.categorycode = i.categorycode
WHERE COALESCE(d.iscompliment, 0) = 0;
');
GO

IF OBJECT_ID('dbo.snapkey_inventory', 'V') IS NOT NULL
    DROP VIEW dbo.snapkey_inventory;
GO

EXEC(N'
CREATE VIEW dbo.snapkey_inventory AS
SELECT
    CAST(s.companycode AS nvarchar(100)) AS tenant_id,
    COALESCE(NULLIF(i.itemname, ''''), NULLIF(s.itemname, ''''), s.itemcode) AS product_name,
    COALESCE(NULLIF(c.categoryname, ''''), ''Uncategorized'') AS category_name,
    CAST(COALESCE(s.Stock, 0) AS decimal(18, 2)) AS stock_quantity,
    CAST(COALESCE(i.min_qnty, 0) AS decimal(18, 2)) AS reorder_level
FROM dbo.tbl_Stock AS s
LEFT JOIN dbo.itemmst AS i
    ON i.companycode = s.companycode
   AND i.itemcode = s.itemcode
LEFT JOIN dbo.categorymst AS c
    ON c.companycode = i.companycode
   AND c.categorycode = i.categorycode;
');
GO

IF OBJECT_ID('dbo.snapkey_bills', 'V') IS NOT NULL DROP VIEW dbo.snapkey_bills;
GO
EXEC(N'
CREATE VIEW dbo.snapkey_bills AS
SELECT
    CAST(companycode AS nvarchar(100)) AS tenant_id,
    COALESCE(trntime, trndate) AS sold_at,
    CAST(COALESCE(netamount, amount, 0) AS decimal(18, 2)) AS net_amount
FROM dbo.salesbillmain;
');
GO

IF OBJECT_ID('dbo.snapkey_payments', 'V') IS NOT NULL DROP VIEW dbo.snapkey_payments;
GO
EXEC(N'
CREATE VIEW dbo.snapkey_payments AS
SELECT CAST(companycode AS nvarchar(100)) AS tenant_id, COALESCE(trntime, trndate) AS sold_at,
       ''Cash'' AS payment_method, CAST(COALESCE(CashAmount, 0) AS decimal(18, 2)) AS amount
FROM dbo.salesbillmain WHERE COALESCE(CashAmount, 0) > 0
UNION ALL
SELECT CAST(companycode AS nvarchar(100)), COALESCE(trntime, trndate), ''Card'',
       CAST(COALESCE(CardAmount, 0) AS decimal(18, 2))
FROM dbo.salesbillmain WHERE COALESCE(CardAmount, 0) > 0
UNION ALL
SELECT CAST(companycode AS nvarchar(100)), COALESCE(trntime, trndate), ''UPI'',
       CAST(COALESCE(UPIAmount, 0) AS decimal(18, 2))
FROM dbo.salesbillmain WHERE COALESCE(UPIAmount, 0) > 0
UNION ALL
SELECT CAST(companycode AS nvarchar(100)), COALESCE(trntime, trndate), ''Credit / Party'',
       CAST(COALESCE(PartyAmount, 0) AS decimal(18, 2))
FROM dbo.salesbillmain WHERE COALESCE(PartyAmount, 0) > 0;
');
GO

IF OBJECT_ID('dbo.snapkey_purchases', 'V') IS NOT NULL DROP VIEW dbo.snapkey_purchases;
GO
EXEC(N'
CREATE VIEW dbo.snapkey_purchases AS
SELECT
    CAST(companycode AS nvarchar(100)) AS tenant_id,
    trndate AS purchased_at,
    CAST(COALESCE(totnetamt, totamount, 0) AS decimal(18, 2)) AS net_amount
FROM dbo.purchasemain;
');
GO

IF OBJECT_ID('dbo.snapkey_customers', 'V') IS NOT NULL DROP VIEW dbo.snapkey_customers;
GO
EXEC(N'
CREATE VIEW dbo.snapkey_customers AS
SELECT
    CAST(companyCode AS nvarchar(100)) AS tenant_id,
    COALESCE(NULLIF(customerName, ''''), customerCode) AS customer_name,
    CAST(COALESCE(visitCount, 0) AS decimal(18, 2)) AS visit_count
FROM dbo.customerDetails;
');
GO

/*
Guarded indexes keep the reporting views fast without recreating existing
indexes. Review storage and write-performance impact before production rollout.
*/
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.salesbillmain')
      AND name = 'IX_snapkey_salesbillmain_join_date'
)
CREATE NONCLUSTERED INDEX IX_snapkey_salesbillmain_join_date
ON dbo.salesbillmain (companycode, yearcode, trnno, billType, trndate);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.salesbilldetail')
      AND name = 'IX_snapkey_salesbilldetail_join_item'
)
CREATE NONCLUSTERED INDEX IX_snapkey_salesbilldetail_join_item
ON dbo.salesbilldetail (companycode, yearcode, trnno, billType, itemcode)
INCLUDE (trndate, qnty, itemAmount, itemDiscountAmount, iscompliment);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.itemmst')
      AND name = 'IX_snapkey_itemmst_lookup'
)
CREATE NONCLUSTERED INDEX IX_snapkey_itemmst_lookup
ON dbo.itemmst (companycode, itemcode)
INCLUDE (itemname, categorycode, min_qnty);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.categorymst')
      AND name = 'IX_snapkey_categorymst_lookup'
)
CREATE NONCLUSTERED INDEX IX_snapkey_categorymst_lookup
ON dbo.categorymst (companycode, categorycode)
INCLUDE (categoryname);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.tbl_Stock')
      AND name = 'IX_snapkey_stock_lookup'
)
CREATE NONCLUSTERED INDEX IX_snapkey_stock_lookup
ON dbo.tbl_Stock (companycode, itemcode)
INCLUDE (itemname, Stock, storecode, trndate);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('dbo.purchasemain')
      AND name = 'IX_snapkey_purchasemain_date'
)
CREATE NONCLUSTERED INDEX IX_snapkey_purchasemain_date
ON dbo.purchasemain (companycode, trndate)
INCLUDE (totnetamt, totamount);
GO

/*
Create the read-only login once, then grant access only to the reporting views:

CREATE LOGIN snapkey_reports WITH PASSWORD = 'replace-with-a-long-random-password';
CREATE USER snapkey_reports FOR LOGIN snapkey_reports;
*/
IF DATABASE_PRINCIPAL_ID('snapkey_reports') IS NOT NULL
BEGIN
    GRANT SELECT ON dbo.snapkey_sales TO snapkey_reports;
    GRANT SELECT ON dbo.snapkey_inventory TO snapkey_reports;
    GRANT SELECT ON dbo.snapkey_bills TO snapkey_reports;
    GRANT SELECT ON dbo.snapkey_payments TO snapkey_reports;
    GRANT SELECT ON dbo.snapkey_purchases TO snapkey_reports;
    GRANT SELECT ON dbo.snapkey_customers TO snapkey_reports;
END;
GO

SELECT TOP (10) * FROM dbo.snapkey_sales ORDER BY sold_at DESC;
SELECT TOP (10) * FROM dbo.snapkey_inventory ORDER BY stock_quantity ASC;
GO
