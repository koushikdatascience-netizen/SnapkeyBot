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
