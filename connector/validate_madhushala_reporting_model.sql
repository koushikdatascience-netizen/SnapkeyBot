/*
  Final Madhushala reporting-model validation
  Read-only and based on joins confirmed from the reverse-engineered ERP code.
*/

USE [barmanager];
GO

SET NOCOUNT ON;

DECLARE @CompanyCode varchar(6);
SET @CompanyCode = '2';

/* 1. Company */
SELECT companycode, companyname
FROM dbo.companymast
WHERE companycode = @CompanyCode;

/* 2. Sales coverage and bill totals */
SELECT
    MIN(trndate) AS first_sale_date,
    MAX(trndate) AS latest_sale_date,
    COUNT(*) AS bill_count,
    SUM(ISNULL(netamount, 0)) AS net_sales,
    AVG(ISNULL(netamount, 0)) AS average_bill
FROM dbo.salesbillmain
WHERE companycode = @CompanyCode;

/* 3. Confirm sales header key uniqueness */
SELECT TOP (20)
    companycode,
    yearcode,
    trnno,
    billType,
    COUNT(*) AS duplicate_count
FROM dbo.salesbillmain
WHERE companycode = @CompanyCode
GROUP BY companycode, yearcode, trnno, billType
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

/* 4. Confirm sales details match headers */
SELECT
    COUNT(*) AS sales_detail_rows,
    SUM(CASE WHEN main.trnno IS NULL THEN 1 ELSE 0 END) AS orphan_sales_detail_rows
FROM dbo.salesbilldetail AS detail
LEFT JOIN dbo.salesbillmain AS main
    ON main.companycode = detail.companycode
    AND main.yearcode = detail.yearcode
    AND main.trnno = detail.trnno
    AND main.billType = detail.billType
WHERE detail.companycode = @CompanyCode;

/* 5. Daily sales preview */
SELECT TOP (31)
    CONVERT(date, trndate) AS sale_date,
    COUNT(*) AS bill_count,
    SUM(ISNULL(netamount, 0)) AS net_sales,
    AVG(ISNULL(netamount, 0)) AS average_bill
FROM dbo.salesbillmain
WHERE companycode = @CompanyCode
GROUP BY CONVERT(date, trndate)
ORDER BY sale_date DESC;

/* 6. Product and category sales preview */
SELECT TOP (30)
    detail.itemcode,
    MAX(ISNULL(item.itemname, detail.itemcode)) AS product_name,
    MAX(ISNULL(category.categoryname, 'Uncategorized')) AS category_name,
    SUM(CASE WHEN main.salestype = 'RETURN' THEN -ISNULL(detail.qnty, 0) ELSE ISNULL(detail.qnty, 0) END) AS net_quantity,
    SUM(CASE WHEN main.salestype = 'RETURN' THEN -ISNULL(detail.itemAmount, 0) ELSE ISNULL(detail.itemAmount, 0) END) AS gross_amount
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
WHERE detail.companycode = @CompanyCode
GROUP BY detail.itemcode
ORDER BY gross_amount DESC;

/* 7. Inventory summary and low stock */
SELECT
    COUNT(*) AS inventory_rows,
    SUM(ISNULL(Stock, 0)) AS total_stock,
    SUM(CASE WHEN ISNULL(Stock, 0) <= 0 THEN 1 ELSE 0 END) AS zero_or_negative_items,
    MAX(trndate) AS stock_as_of
FROM dbo.tbl_Stock
WHERE companycode = @CompanyCode;

SELECT TOP (30)
    stock.itemcode,
    COALESCE(NULLIF(item.itemname, ''), NULLIF(stock.itemname, ''), stock.itemcode) AS product_name,
    stock.storecode,
    stock.Stock AS stock_quantity,
    stock.trndate AS stock_as_of
FROM dbo.tbl_Stock AS stock
LEFT JOIN dbo.itemmst AS item
    ON item.companycode = stock.companycode
    AND item.itemcode = stock.itemcode
WHERE stock.companycode = @CompanyCode
  AND ISNULL(stock.Stock, 0) <= 5
ORDER BY ISNULL(stock.Stock, 0), product_name;

/* 8. Purchase coverage and confirmed header/detail join */
SELECT
    MIN(trndate) AS first_purchase_date,
    MAX(trndate) AS latest_purchase_date,
    COUNT(*) AS purchase_count
FROM dbo.purchasemain
WHERE companycode = @CompanyCode;

SELECT
    COUNT(*) AS purchase_detail_rows,
    SUM(CASE WHEN main.trnno IS NULL THEN 1 ELSE 0 END) AS orphan_purchase_detail_rows
FROM dbo.purchasedetail AS detail
LEFT JOIN dbo.purchasemain AS main
    ON main.companycode = detail.companycode
    AND main.yearcode = detail.yearcode
    AND main.trnno = detail.trnno
WHERE detail.companycode = @CompanyCode;

/* 9. Daily purchase totals */
SELECT TOP (31)
    CONVERT(date, main.trndate) AS purchase_date,
    COUNT(DISTINCT main.trnno) AS purchase_count,
    SUM(ISNULL(detail.itemamount, 0)) AS purchase_amount,
    SUM(ISNULL(detail.itemquantity, 0)) AS purchased_quantity
FROM dbo.purchasemain AS main
JOIN dbo.purchasedetail AS detail
    ON detail.companycode = main.companycode
    AND detail.yearcode = main.yearcode
    AND detail.trnno = main.trnno
WHERE main.companycode = @CompanyCode
GROUP BY CONVERT(date, main.trndate)
ORDER BY purchase_date DESC;

/* 10. Supplier performance */
SELECT TOP (30)
    main.suppliercode,
    MAX(ISNULL(ledger.name, main.suppliercode)) AS supplier_name,
    COUNT(DISTINCT main.trnno) AS purchase_count,
    SUM(ISNULL(detail.itemamount, 0)) AS purchase_amount
FROM dbo.purchasemain AS main
JOIN dbo.purchasedetail AS detail
    ON detail.companycode = main.companycode
    AND detail.yearcode = main.yearcode
    AND detail.trnno = main.trnno
LEFT JOIN dbo.ledger AS ledger
    ON ledger.companycode = main.companycode
    AND ledger.ledcode = main.suppliercode
WHERE main.companycode = @CompanyCode
GROUP BY main.suppliercode
ORDER BY purchase_amount DESC;

/* 11. Accounting transaction coverage */
SELECT
    MIN(VchDate) AS first_transaction_date,
    MAX(VchDate) AS latest_transaction_date,
    COUNT(*) AS transaction_count
FROM dbo.TransactionMain
WHERE companycode = @CompanyCode;

SELECT TOP (30)
    CONVERT(date, main.VchDate) AS transaction_date,
    main.ReceiptType,
    COUNT(DISTINCT main.IndexId) AS transaction_count,
    SUM(ABS(ISNULL(detail.TrnAmount, 0))) AS transaction_amount
FROM dbo.TransactionMain AS main
JOIN dbo.TransactionDetail AS detail
    ON detail.companycode = main.companycode
    AND detail.yearcode = main.yearcode
    AND detail.IndexId = main.IndexId
WHERE main.companycode = @CompanyCode
GROUP BY CONVERT(date, main.VchDate), main.ReceiptType
ORDER BY transaction_date DESC, transaction_amount DESC;
