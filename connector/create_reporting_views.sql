/*
Replace the source table and column names below with the real Madhushala schema.
The Snapkey connector reads only these two views.
*/

CREATE OR ALTER VIEW dbo.snapkey_sales AS
SELECT
    CAST(shop_id AS nvarchar(100)) AS tenant_id,
    bill_datetime AS sold_at,
    item_name AS product_name,
    category_name,
    quantity,
    net_amount
FROM dbo.your_sales_items_source;
GO

CREATE OR ALTER VIEW dbo.snapkey_inventory AS
SELECT
    CAST(shop_id AS nvarchar(100)) AS tenant_id,
    item_name AS product_name,
    current_stock AS stock_quantity,
    reorder_level
FROM dbo.your_inventory_source;
GO

/*
Run after creating the snapkey_reports SQL Server login.
*/
GRANT SELECT ON dbo.snapkey_sales TO snapkey_reports;
GRANT SELECT ON dbo.snapkey_inventory TO snapkey_reports;
GO
