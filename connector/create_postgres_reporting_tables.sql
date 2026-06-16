CREATE TABLE IF NOT EXISTS snapkey_sales (
    tenant_id text NOT NULL,
    sold_at timestamp NOT NULL,
    product_name text NOT NULL,
    category_name text NOT NULL,
    quantity numeric(18, 2) NOT NULL DEFAULT 0,
    net_amount numeric(18, 2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapkey_inventory (
    tenant_id text NOT NULL,
    product_name text NOT NULL,
    category_name text NOT NULL,
    stock_quantity numeric(18, 2) NOT NULL DEFAULT 0,
    reorder_level numeric(18, 2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapkey_bills (
    tenant_id text NOT NULL,
    sold_at timestamp NOT NULL,
    net_amount numeric(18, 2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapkey_payments (
    tenant_id text NOT NULL,
    sold_at timestamp NOT NULL,
    payment_method text NOT NULL,
    amount numeric(18, 2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapkey_purchases (
    tenant_id text NOT NULL,
    purchased_at timestamp NOT NULL,
    net_amount numeric(18, 2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapkey_customers (
    tenant_id text NOT NULL,
    customer_name text NOT NULL,
    visit_count numeric(18, 2) NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_snapkey_sales_tenant_date
    ON snapkey_sales (tenant_id, sold_at);
CREATE INDEX IF NOT EXISTS ix_snapkey_sales_tenant_product
    ON snapkey_sales (tenant_id, product_name);
CREATE INDEX IF NOT EXISTS ix_snapkey_inventory_tenant_stock
    ON snapkey_inventory (tenant_id, stock_quantity);
CREATE INDEX IF NOT EXISTS ix_snapkey_bills_tenant_date
    ON snapkey_bills (tenant_id, sold_at);
CREATE INDEX IF NOT EXISTS ix_snapkey_payments_tenant_date
    ON snapkey_payments (tenant_id, sold_at);
CREATE INDEX IF NOT EXISTS ix_snapkey_purchases_tenant_date
    ON snapkey_purchases (tenant_id, purchased_at);
CREATE INDEX IF NOT EXISTS ix_snapkey_customers_tenant_visits
    ON snapkey_customers (tenant_id, visit_count DESC);

CREATE TABLE IF NOT EXISTS snapkey_sync_status (
    tenant_id text PRIMARY KEY,
    synced_at timestamp with time zone NOT NULL DEFAULT now(),
    row_counts jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS report_sales_daily (
    tenant_id text NOT NULL,
    sale_date date NOT NULL,
    bill_count integer NOT NULL DEFAULT 0,
    gross_sales numeric(18, 2) NOT NULL DEFAULT 0,
    discount_amount numeric(18, 2) NOT NULL DEFAULT 0,
    net_sales numeric(18, 2) NOT NULL DEFAULT 0,
    average_bill numeric(18, 2) NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, sale_date)
);

CREATE TABLE IF NOT EXISTS report_product_sales_daily (
    tenant_id text NOT NULL,
    sale_date date NOT NULL,
    product_code text NOT NULL,
    product_name text NOT NULL,
    category_name text NOT NULL,
    quantity numeric(18, 2) NOT NULL DEFAULT 0,
    sales_amount numeric(18, 2) NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, sale_date, product_code)
);

CREATE TABLE IF NOT EXISTS report_inventory_current (
    tenant_id text NOT NULL,
    product_code text NOT NULL,
    product_name text NOT NULL,
    category_name text NOT NULL,
    store_code text NOT NULL,
    stock_quantity numeric(18, 2) NOT NULL DEFAULT 0,
    reorder_level numeric(18, 2) NOT NULL DEFAULT 0,
    stock_as_of timestamp,
    PRIMARY KEY (tenant_id, product_code, store_code)
);

CREATE TABLE IF NOT EXISTS report_purchase_daily (
    tenant_id text NOT NULL,
    purchase_date date NOT NULL,
    purchase_count integer NOT NULL DEFAULT 0,
    purchase_amount numeric(18, 2) NOT NULL DEFAULT 0,
    purchased_quantity numeric(18, 2) NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, purchase_date)
);

CREATE TABLE IF NOT EXISTS report_supplier_daily (
    tenant_id text NOT NULL,
    purchase_date date NOT NULL,
    supplier_code text NOT NULL,
    supplier_name text NOT NULL,
    purchase_count integer NOT NULL DEFAULT 0,
    purchase_amount numeric(18, 2) NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, purchase_date, supplier_code)
);

CREATE TABLE IF NOT EXISTS report_account_daily (
    tenant_id text NOT NULL,
    transaction_date date NOT NULL,
    transaction_type text NOT NULL,
    transaction_count integer NOT NULL DEFAULT 0,
    transaction_amount numeric(18, 2) NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, transaction_date, transaction_type)
);

CREATE INDEX IF NOT EXISTS ix_report_product_sales_lookup
    ON report_product_sales_daily (tenant_id, sale_date, sales_amount DESC);
CREATE INDEX IF NOT EXISTS ix_report_product_category
    ON report_product_sales_daily (tenant_id, category_name, sale_date);
CREATE INDEX IF NOT EXISTS ix_report_inventory_low_stock
    ON report_inventory_current (tenant_id, stock_quantity, reorder_level);
CREATE INDEX IF NOT EXISTS ix_report_supplier_lookup
    ON report_supplier_daily (tenant_id, purchase_date, purchase_amount DESC);
CREATE INDEX IF NOT EXISTS ix_report_account_lookup
    ON report_account_daily (tenant_id, transaction_date, transaction_type);

ALTER TABLE report_sales_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_product_sales_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_inventory_current ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_purchase_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_supplier_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_account_daily ENABLE ROW LEVEL SECURITY;
