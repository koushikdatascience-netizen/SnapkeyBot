/*
  Read-only Madhushala views used for Supabase/PostgreSQL synchronization.
  SQL Server 2014 compatible. These views do not modify ERP data.
*/

USE [barmanager];
GO

IF OBJECT_ID('dbo.snapkey_sales_daily', 'V') IS NOT NULL DROP VIEW dbo.snapkey_sales_daily;
GO
CREATE VIEW dbo.snapkey_sales_daily AS
SELECT
    CAST(companycode AS nvarchar(100)) AS tenant_id,
    CONVERT(date, trndate) AS sale_date,
    COUNT(*) AS bill_count,
    CAST(SUM(ISNULL(amount, 0)) AS decimal(18, 2)) AS gross_sales,
    CAST(SUM(ISNULL(discamount, 0)) AS decimal(18, 2)) AS discount_amount,
    CAST(SUM(ISNULL(netamount, 0)) AS decimal(18, 2)) AS net_sales,
    CAST(AVG(ISNULL(netamount, 0)) AS decimal(18, 2)) AS average_bill
FROM dbo.salesbillmain
GROUP BY companycode, CONVERT(date, trndate);
GO

IF OBJECT_ID('dbo.snapkey_product_sales_daily', 'V') IS NOT NULL DROP VIEW dbo.snapkey_product_sales_daily;
GO
CREATE VIEW dbo.snapkey_product_sales_daily AS
SELECT
    CAST(detail.companycode AS nvarchar(100)) AS tenant_id,
    CONVERT(date, main.trndate) AS sale_date,
    detail.itemcode AS product_code,
    COALESCE(NULLIF(item.itemname, ''), detail.itemcode) AS product_name,
    COALESCE(NULLIF(category.categoryname, ''), 'Uncategorized') AS category_name,
    CAST(SUM(CASE WHEN main.salestype = 'RETURN' THEN -ISNULL(detail.qnty, 0) ELSE ISNULL(detail.qnty, 0) END) AS decimal(18, 2)) AS quantity,
    CAST(SUM(CASE WHEN main.salestype = 'RETURN' THEN -ISNULL(detail.itemAmount, 0) ELSE ISNULL(detail.itemAmount, 0) END) AS decimal(18, 2)) AS sales_amount
FROM dbo.salesbilldetail AS detail
JOIN dbo.salesbillmain AS main
  ON main.companycode = detail.companycode
 AND main.yearcode = detail.yearcode
 AND main.trnno = detail.trnno
 AND main.billType = detail.billType
LEFT JOIN dbo.itemmst AS item
  ON item.companycode = detail.companycode
 AND item.itemcode = detail.itemcode
LEFT JOIN dbo.categorymst AS category
  ON category.companycode = item.companycode
 AND category.categorycode = item.categorycode
GROUP BY
    detail.companycode,
    CONVERT(date, main.trndate),
    detail.itemcode,
    COALESCE(NULLIF(item.itemname, ''), detail.itemcode),
    COALESCE(NULLIF(category.categoryname, ''), 'Uncategorized');
GO

IF OBJECT_ID('dbo.snapkey_inventory_current', 'V') IS NOT NULL DROP VIEW dbo.snapkey_inventory_current;
GO
CREATE VIEW dbo.snapkey_inventory_current AS
SELECT
    CAST(stock.companycode AS nvarchar(100)) AS tenant_id,
    stock.itemcode AS product_code,
    COALESCE(NULLIF(item.itemname, ''), NULLIF(stock.itemname, ''), stock.itemcode) AS product_name,
    COALESCE(NULLIF(category.categoryname, ''), 'Uncategorized') AS category_name,
    ISNULL(stock.storecode, 'default') AS store_code,
    CAST(ISNULL(stock.Stock, 0) AS decimal(18, 2)) AS stock_quantity,
    CAST(ISNULL(item.min_qnty, 0) AS decimal(18, 2)) AS reorder_level,
    stock.trndate AS stock_as_of
FROM dbo.tbl_Stock AS stock
LEFT JOIN dbo.itemmst AS item
  ON item.companycode = stock.companycode
 AND item.itemcode = stock.itemcode
LEFT JOIN dbo.categorymst AS category
  ON category.companycode = item.companycode
 AND category.categorycode = item.categorycode;
GO

IF OBJECT_ID('dbo.snapkey_purchase_daily', 'V') IS NOT NULL DROP VIEW dbo.snapkey_purchase_daily;
GO
CREATE VIEW dbo.snapkey_purchase_daily AS
SELECT
    CAST(main.companycode AS nvarchar(100)) AS tenant_id,
    CONVERT(date, main.trndate) AS purchase_date,
    COUNT(DISTINCT main.trnno) AS purchase_count,
    CAST(SUM(ISNULL(detail.itemamount, 0)) AS decimal(18, 2)) AS purchase_amount,
    CAST(SUM(ISNULL(detail.itemquantity, 0)) AS decimal(18, 2)) AS purchased_quantity
FROM dbo.purchasemain AS main
JOIN dbo.purchasedetail AS detail
  ON detail.companycode = main.companycode
 AND detail.yearcode = main.yearcode
 AND detail.trnno = main.trnno
GROUP BY main.companycode, CONVERT(date, main.trndate);
GO

IF OBJECT_ID('dbo.snapkey_supplier_daily', 'V') IS NOT NULL DROP VIEW dbo.snapkey_supplier_daily;
GO
CREATE VIEW dbo.snapkey_supplier_daily AS
SELECT
    CAST(main.companycode AS nvarchar(100)) AS tenant_id,
    CONVERT(date, main.trndate) AS purchase_date,
    ISNULL(main.suppliercode, 'unknown') AS supplier_code,
    MAX(COALESCE(NULLIF(ledger.name, ''), NULLIF(main.suppliercode, ''), 'Unknown supplier')) AS supplier_name,
    COUNT(DISTINCT main.trnno) AS purchase_count,
    CAST(SUM(ISNULL(detail.itemamount, 0)) AS decimal(18, 2)) AS purchase_amount
FROM dbo.purchasemain AS main
JOIN dbo.purchasedetail AS detail
  ON detail.companycode = main.companycode
 AND detail.yearcode = main.yearcode
 AND detail.trnno = main.trnno
LEFT JOIN dbo.ledger AS ledger
  ON ledger.companycode = main.companycode
 AND ledger.ledcode = main.suppliercode
GROUP BY main.companycode, CONVERT(date, main.trndate), ISNULL(main.suppliercode, 'unknown');
GO

IF OBJECT_ID('dbo.snapkey_account_daily', 'V') IS NOT NULL DROP VIEW dbo.snapkey_account_daily;
GO
CREATE VIEW dbo.snapkey_account_daily AS
SELECT
    CAST(main.companycode AS nvarchar(100)) AS tenant_id,
    CONVERT(date, main.VchDate) AS transaction_date,
    ISNULL(main.ReceiptType, 'Other') AS transaction_type,
    COUNT(DISTINCT main.IndexId) AS transaction_count,
    CAST(SUM(ABS(ISNULL(detail.TrnAmount, 0))) AS decimal(18, 2)) AS transaction_amount
FROM dbo.TransactionMain AS main
JOIN dbo.TransactionDetail AS detail
  ON detail.companycode = main.companycode
 AND detail.yearcode = main.yearcode
 AND detail.IndexId = main.IndexId
GROUP BY main.companycode, CONVERT(date, main.VchDate), ISNULL(main.ReceiptType, 'Other');
GO

SELECT TOP (10) * FROM dbo.snapkey_sales_daily ORDER BY sale_date DESC;
SELECT TOP (10) * FROM dbo.snapkey_product_sales_daily ORDER BY sale_date DESC, sales_amount DESC;
SELECT TOP (10) * FROM dbo.snapkey_inventory_current ORDER BY stock_quantity ASC;
GO
