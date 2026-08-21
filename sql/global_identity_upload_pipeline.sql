-- Durable, multi-tenant identity allocation for Retano uploads.
--
-- Deployment requirements:
--   1. Stop/pause Celery upload workers.
--   2. Run the collision audit below (the DO blocks abort on ambiguity).
--   3. Apply this script through migration 0055 or in Supabase SQL Editor.
--   4. Remove the known failed job's legacy staging rows with the separate
--      cleanup statement documented in Commands.md before restarting workers.
--
-- This script intentionally does not delete staging or permanent business data.

SET LOCAL statement_timeout = '0';
SELECT pg_advisory_xact_lock(hashtext('retano-global-identity-v1'));

-- Abort rather than guessing if legacy data contains contradictory identities.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM users_unnormalized_data
        GROUP BY tenant_id, internal_user_id
        HAVING count(DISTINCT user_id) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot bootstrap: a tenant/internal_user_id maps to multiple user_ids';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM users_unnormalized_data
        GROUP BY user_id
        HAVING count(DISTINCT (tenant_id, internal_user_id)) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot bootstrap: a user_id maps to multiple tenant identities';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM users_unnormalized_data
        GROUP BY tenant_id, internal_order_id
        HAVING count(DISTINCT order_id) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot bootstrap: a tenant/internal_order_id maps to multiple order_ids';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM users_unnormalized_data
        GROUP BY order_id
        HAVING count(DISTINCT (tenant_id, internal_order_id)) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot bootstrap: an order_id maps to multiple tenant identities';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT tenant_id, internal_product_id, product_id
            FROM products_unnormalized_data
            UNION ALL
            SELECT tenant_id, internal_product_id, product_id
            FROM users_unnormalized_data
            WHERE product_id IS NOT NULL
        ) product_sources
        GROUP BY tenant_id, internal_product_id
        HAVING count(DISTINCT product_id) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot bootstrap: a tenant/internal_product_id maps to multiple product_ids';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM (
            SELECT tenant_id, internal_product_id, product_id
            FROM products_unnormalized_data
            UNION ALL
            SELECT tenant_id, internal_product_id, product_id
            FROM users_unnormalized_data
            WHERE product_id IS NOT NULL
        ) product_sources
        GROUP BY product_id
        HAVING count(DISTINCT (tenant_id, internal_product_id)) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot bootstrap: a product_id maps to multiple tenant identities';
    END IF;
END;
$$;

CREATE SEQUENCE IF NOT EXISTS global_user_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS global_order_id_seq AS bigint;
CREATE SEQUENCE IF NOT EXISTS global_product_id_seq AS bigint;

-- The sequence type is bigint; every storage column must be able to hold it.
ALTER TABLE users_unnormalized_data
    ALTER COLUMN user_id TYPE bigint,
    ALTER COLUMN order_id TYPE bigint,
    ALTER COLUMN product_id TYPE bigint;
ALTER TABLE users_unnormalized_data_staging
    ALTER COLUMN user_id TYPE bigint,
    ALTER COLUMN order_id TYPE bigint,
    ALTER COLUMN product_id TYPE bigint;
ALTER TABLE products_unnormalized_data
    ALTER COLUMN product_id TYPE bigint;
ALTER TABLE products_unnormalized_data_staging
    ALTER COLUMN product_id TYPE bigint;

ALTER TABLE users_unnormalized_data_staging
    ADD COLUMN IF NOT EXISTS upload_job_id uuid NULL;
ALTER TABLE products_unnormalized_data_staging
    ADD COLUMN IF NOT EXISTS upload_job_id uuid NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'users_staging_upload_job_fk'
    ) THEN
        ALTER TABLE users_unnormalized_data_staging
            ADD CONSTRAINT users_staging_upload_job_fk
            FOREIGN KEY (upload_job_id) REFERENCES upload_job(id)
            ON DELETE CASCADE NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'products_staging_upload_job_fk'
    ) THEN
        ALTER TABLE products_unnormalized_data_staging
            ADD CONSTRAINT products_staging_upload_job_fk
            FOREIGN KEY (upload_job_id) REFERENCES upload_job(id)
            ON DELETE CASCADE NOT VALID;
    END IF;
END;
$$;

ALTER TABLE users_unnormalized_data_staging
    VALIDATE CONSTRAINT users_staging_upload_job_fk;
ALTER TABLE products_unnormalized_data_staging
    VALIDATE CONSTRAINT products_staging_upload_job_fk;

CREATE TABLE IF NOT EXISTS global_user_identity (
    tenant_id bigint NOT NULL REFERENCES core_tenant(id) ON DELETE CASCADE,
    internal_user_id text NOT NULL,
    user_id bigint NOT NULL DEFAULT nextval('global_user_id_seq'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, internal_user_id),
    UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS global_order_identity (
    tenant_id bigint NOT NULL REFERENCES core_tenant(id) ON DELETE CASCADE,
    internal_order_id text NOT NULL,
    order_id bigint NOT NULL DEFAULT nextval('global_order_id_seq'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, internal_order_id),
    UNIQUE (order_id)
);

CREATE TABLE IF NOT EXISTS global_product_identity (
    tenant_id bigint NOT NULL REFERENCES core_tenant(id) ON DELETE CASCADE,
    internal_product_id text NOT NULL,
    product_id bigint NOT NULL DEFAULT nextval('global_product_id_seq'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, internal_product_id),
    UNIQUE (product_id)
);

-- Persistent bootstrap: unlike staging, these rows are never flushed away.
INSERT INTO global_user_identity (tenant_id, internal_user_id, user_id)
SELECT DISTINCT tenant_id, internal_user_id, user_id
FROM users_unnormalized_data
ON CONFLICT (tenant_id, internal_user_id) DO NOTHING;

INSERT INTO global_order_identity (tenant_id, internal_order_id, order_id)
SELECT DISTINCT tenant_id, internal_order_id, order_id
FROM users_unnormalized_data
ON CONFLICT (tenant_id, internal_order_id) DO NOTHING;

INSERT INTO global_product_identity (tenant_id, internal_product_id, product_id)
SELECT DISTINCT tenant_id, internal_product_id, product_id
FROM (
    SELECT tenant_id, internal_product_id, product_id
    FROM products_unnormalized_data
    UNION
    SELECT tenant_id, internal_product_id, product_id
    FROM users_unnormalized_data
    WHERE product_id IS NOT NULL
) product_sources
ON CONFLICT (tenant_id, internal_product_id) DO NOTHING;

-- Align sequences beyond every existing identity, including normalized tables.
SELECT setval(
    'global_user_id_seq',
    GREATEST(
        1,
        COALESCE((SELECT max(user_id) FROM global_user_identity), 0),
        COALESCE((SELECT max(user_id::bigint) FROM users WHERE user_id ~ '^[0-9]+$'), 0),
        COALESCE((SELECT last_value FROM global_user_id_seq), 0)
    ),
    true
);
SELECT setval(
    'global_order_id_seq',
    GREATEST(
        1,
        COALESCE((SELECT max(order_id) FROM global_order_identity), 0),
        COALESCE((SELECT max(order_id::bigint) FROM orders WHERE order_id ~ '^[0-9]+$'), 0),
        COALESCE((SELECT last_value FROM global_order_id_seq), 0)
    ),
    true
);
SELECT setval(
    'global_product_id_seq',
    GREATEST(
        1,
        COALESCE((SELECT max(product_id) FROM global_product_identity), 0),
        COALESCE((SELECT max(product_id::bigint) FROM products WHERE product_id ~ '^[0-9]+$'), 0),
        COALESCE((SELECT last_value FROM global_product_id_seq), 0)
    ),
    true
);

-- Existing customer rows may predate product uploads. Give those internal
-- products permanent identities too, then make the business-table invariant
-- explicit so future writers cannot silently reintroduce NULL product IDs.
INSERT INTO global_product_identity (tenant_id, internal_product_id)
SELECT DISTINCT tenant_id, internal_product_id
FROM users_unnormalized_data
WHERE product_id IS NULL
ON CONFLICT (tenant_id, internal_product_id) DO NOTHING;

UPDATE users_unnormalized_data u
SET product_id = i.product_id
FROM global_product_identity i
WHERE u.product_id IS NULL
  AND i.tenant_id = u.tenant_id
  AND i.internal_product_id = u.internal_product_id;

-- Compatibility guard for the older direct-sync/tenant flush path, which can
-- explicitly insert NULL product_id. It is skipped entirely for the normal
-- set-based upload path because those rows already carry product_id.
CREATE OR REPLACE FUNCTION fill_missing_flat_product_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    SELECT product_id INTO NEW.product_id
    FROM global_product_identity
    WHERE tenant_id = NEW.tenant_id
      AND internal_product_id = NEW.internal_product_id;

    IF NEW.product_id IS NULL THEN
        INSERT INTO global_product_identity (tenant_id, internal_product_id)
        VALUES (NEW.tenant_id, NEW.internal_product_id)
        ON CONFLICT (tenant_id, internal_product_id) DO UPDATE
        SET internal_product_id = EXCLUDED.internal_product_id
        RETURNING product_id INTO NEW.product_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_fill_missing_flat_product_identity
    ON users_unnormalized_data;
CREATE TRIGGER trg_fill_missing_flat_product_identity
BEFORE INSERT OR UPDATE OF product_id, tenant_id, internal_product_id
ON users_unnormalized_data
FOR EACH ROW
WHEN (NEW.product_id IS NULL)
EXECUTE FUNCTION fill_missing_flat_product_identity();

-- The backfill above can queue events for the table's initially-deferred
-- tenant FK. PostgreSQL refuses ALTER TABLE while those events are pending,
-- so fire and validate them before enforcing the final NOT NULL invariant.
SET CONSTRAINTS ALL IMMEDIATE;

ALTER TABLE users_unnormalized_data
    ALTER COLUMN product_id SET NOT NULL;

-- Job and identity lookup indexes used by allocation and flushing.
CREATE INDEX IF NOT EXISTS users_staging_job_user_idx
    ON users_unnormalized_data_staging (upload_job_id, internal_user_id);
CREATE INDEX IF NOT EXISTS users_staging_job_order_idx
    ON users_unnormalized_data_staging (upload_job_id, internal_order_id);
CREATE INDEX IF NOT EXISTS users_staging_job_product_idx
    ON users_unnormalized_data_staging (upload_job_id, internal_product_id);
CREATE INDEX IF NOT EXISTS products_staging_job_product_idx
    ON products_unnormalized_data_staging (upload_job_id, internal_product_id);
CREATE INDEX IF NOT EXISTS users_flat_tenant_user_idx
    ON users_unnormalized_data (tenant_id, internal_user_id);
CREATE INDEX IF NOT EXISTS users_flat_tenant_order_idx
    ON users_unnormalized_data (tenant_id, internal_order_id);
CREATE INDEX IF NOT EXISTS users_flat_tenant_product_idx
    ON users_unnormalized_data (tenant_id, internal_product_id);
CREATE INDEX IF NOT EXISTS products_flat_tenant_product_idx
    ON products_unnormalized_data (tenant_id, internal_product_id);

CREATE OR REPLACE FUNCTION allocate_upload_job_ids(p_job_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_tenant_id bigint;
    v_upload_type text;
BEGIN
    SELECT tenant_id, upload_type
    INTO v_tenant_id, v_upload_type
    FROM upload_job
    WHERE id = p_job_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Upload job % does not exist', p_job_id;
    END IF;
    IF v_upload_type NOT IN ('customers', 'products') THEN
        RAISE EXCEPTION 'Upload job % has unsupported type %', p_job_id, v_upload_type;
    END IF;

    -- Serialize finalization per tenant. Identity uniqueness constraints also
    -- protect cross-tenant and cross-worker concurrency.
    PERFORM pg_advisory_xact_lock(v_tenant_id);

    IF v_upload_type = 'customers' THEN
        INSERT INTO global_user_identity (tenant_id, internal_user_id)
        SELECT d.tenant_id, d.internal_user_id
        FROM (
            SELECT DISTINCT tenant_id, internal_user_id
            FROM users_unnormalized_data_staging
            WHERE upload_job_id = p_job_id
        ) d
        ON CONFLICT (tenant_id, internal_user_id) DO NOTHING;

        INSERT INTO global_order_identity (tenant_id, internal_order_id)
        SELECT d.tenant_id, d.internal_order_id
        FROM (
            SELECT DISTINCT tenant_id, internal_order_id
            FROM users_unnormalized_data_staging
            WHERE upload_job_id = p_job_id
        ) d
        ON CONFLICT (tenant_id, internal_order_id) DO NOTHING;

        -- Customer files establish product identity immediately; a later
        -- products file reuses the ID and supplies product metadata.
        INSERT INTO global_product_identity (tenant_id, internal_product_id)
        SELECT d.tenant_id, d.internal_product_id
        FROM (
            SELECT DISTINCT tenant_id, internal_product_id
            FROM users_unnormalized_data_staging
            WHERE upload_job_id = p_job_id
        ) d
        ON CONFLICT (tenant_id, internal_product_id) DO NOTHING;

        UPDATE users_unnormalized_data_staging s
        SET user_id = i.user_id
        FROM global_user_identity i
        WHERE s.upload_job_id = p_job_id
          AND i.tenant_id = s.tenant_id
          AND i.internal_user_id = s.internal_user_id;

        UPDATE users_unnormalized_data_staging s
        SET order_id = i.order_id
        FROM global_order_identity i
        WHERE s.upload_job_id = p_job_id
          AND i.tenant_id = s.tenant_id
          AND i.internal_order_id = s.internal_order_id;

        UPDATE users_unnormalized_data_staging s
        SET product_id = i.product_id
        FROM global_product_identity i
        WHERE s.upload_job_id = p_job_id
          AND i.tenant_id = s.tenant_id
          AND i.internal_product_id = s.internal_product_id;

        IF EXISTS (
            SELECT 1 FROM users_unnormalized_data_staging
            WHERE upload_job_id = p_job_id
              AND (user_id IS NULL OR order_id IS NULL OR product_id IS NULL)
        ) THEN
            RAISE EXCEPTION 'Identity allocation left NULL IDs for upload job %', p_job_id;
        END IF;
    ELSE
        INSERT INTO global_product_identity (tenant_id, internal_product_id)
        SELECT d.tenant_id, d.internal_product_id
        FROM (
            SELECT DISTINCT tenant_id, internal_product_id
            FROM products_unnormalized_data_staging
            WHERE upload_job_id = p_job_id
        ) d
        ON CONFLICT (tenant_id, internal_product_id) DO NOTHING;

        UPDATE products_unnormalized_data_staging s
        SET product_id = i.product_id
        FROM global_product_identity i
        WHERE s.upload_job_id = p_job_id
          AND i.tenant_id = s.tenant_id
          AND i.internal_product_id = s.internal_product_id;

        IF EXISTS (
            SELECT 1 FROM products_unnormalized_data_staging
            WHERE upload_job_id = p_job_id AND product_id IS NULL
        ) THEN
            RAISE EXCEPTION 'Product allocation left NULL IDs for upload job %', p_job_id;
        END IF;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION flush_customers_upload_job(p_job_id uuid)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    v_tenant_id bigint;
    v_rows_moved integer;
    v_affected_users text[];
BEGIN
    SELECT tenant_id INTO v_tenant_id
    FROM upload_job
    WHERE id = p_job_id AND upload_type = 'customers'
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Customer upload job % does not exist', p_job_id;
    END IF;

    PERFORM pg_advisory_xact_lock(v_tenant_id);

    IF EXISTS (
        SELECT 1 FROM users_unnormalized_data_staging
        WHERE upload_job_id = p_job_id
          AND (user_id IS NULL OR order_id IS NULL OR product_id IS NULL)
    ) THEN
        RAISE EXCEPTION 'Cannot flush upload job % with NULL global IDs', p_job_id;
    END IF;

    UPDATE users_unnormalized_data_staging
    SET subtotal = quantity * then_product_price
    WHERE upload_job_id = p_job_id AND subtotal IS NULL;

    INSERT INTO users (
        user_id, first_name, last_name, gender, phone_number, tenant_id
    )
    SELECT DISTINCT ON (s.user_id)
        s.user_id::text,
        left(normalize_text(s.first_name), 100),
        left(normalize_text(s.last_name), 100),
        normalize_gender(s.gender),
        normalize_phone(s.phone_number),
        s.tenant_id::integer
    FROM users_unnormalized_data_staging s
    WHERE s.upload_job_id = p_job_id
    ORDER BY s.user_id, s.created_at DESC
    ON CONFLICT (user_id) DO UPDATE
    SET first_name = EXCLUDED.first_name,
        last_name = EXCLUDED.last_name,
        gender = EXCLUDED.gender,
        phone_number = EXCLUDED.phone_number,
        tenant_id = EXCLUDED.tenant_id;

    INSERT INTO orders (
        order_id, user_id, order_date, total_amount, product_count, created_at
    )
    SELECT
        s.order_id::text,
        s.user_id::text,
        s.order_date::date,
        sum(s.quantity * s.then_product_price),
        sum(s.quantity),
        min(s.created_at)
    FROM users_unnormalized_data_staging s
    WHERE s.upload_job_id = p_job_id
    GROUP BY s.order_id, s.user_id, s.order_date
    ON CONFLICT (order_id) DO UPDATE
    SET user_id = EXCLUDED.user_id,
        total_amount = EXCLUDED.total_amount,
        product_count = EXCLUDED.product_count,
        order_date = EXCLUDED.order_date,
        created_at = EXCLUDED.created_at;

    -- Customer data establishes product identity before catalog metadata may
    -- exist. Placeholder rows make that identity referentially usable by
    -- order_items; the product upload later fills the same row via upsert.
    INSERT INTO products (product_id, created_at)
    SELECT s.product_id::text, min(s.created_at)::timestamp
    FROM users_unnormalized_data_staging s
    WHERE s.upload_job_id = p_job_id
    GROUP BY s.product_id
    ON CONFLICT (product_id) DO NOTHING;

    INSERT INTO users_unnormalized_data (
        tenant_id, internal_user_id, user_id, first_name, last_name,
        gender, phone_number, internal_order_id, order_id, order_date,
        internal_product_id, product_id, then_product_price, quantity,
        subtotal, column_mapping, created_at
    )
    SELECT
        tenant_id, internal_user_id, user_id, first_name, last_name,
        gender, phone_number, internal_order_id, order_id, order_date,
        internal_product_id, product_id, then_product_price, quantity,
        subtotal, column_mapping, created_at
    FROM users_unnormalized_data_staging
    WHERE upload_job_id = p_job_id;

    GET DIAGNOSTICS v_rows_moved = ROW_COUNT;
    IF v_rows_moved = 0 THEN
        RETURN 0;
    END IF;

    PERFORM populate_order_items_batch(v_tenant_id::integer);

    SELECT array_agg(DISTINCT user_id::text)
    INTO v_affected_users
    FROM users_unnormalized_data_staging
    WHERE upload_job_id = p_job_id;

    IF v_affected_users IS NOT NULL AND array_length(v_affected_users, 1) > 0 THEN
        PERFORM sync_attributes_batch_for_users(v_affected_users);
        PERFORM refresh_user_summary_batch_for_users(v_affected_users);
    END IF;

    DELETE FROM users_unnormalized_data_staging
    WHERE upload_job_id = p_job_id;
    RETURN v_rows_moved;
END;
$$;

CREATE OR REPLACE FUNCTION flush_products_upload_job(p_job_id uuid)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    v_tenant_id bigint;
    v_rows_moved integer;
    v_affected_users text[];
BEGIN
    SELECT tenant_id INTO v_tenant_id
    FROM upload_job
    WHERE id = p_job_id AND upload_type = 'products'
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Product upload job % does not exist', p_job_id;
    END IF;

    PERFORM pg_advisory_xact_lock(v_tenant_id);
    IF EXISTS (
        SELECT 1 FROM products_unnormalized_data_staging
        WHERE upload_job_id = p_job_id AND product_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Cannot flush upload job % with NULL product IDs', p_job_id;
    END IF;

    INSERT INTO products (
        product_id, name, category, price, first_product_attribute,
        second_product_attribute, product_link, created_at
    )
    SELECT DISTINCT ON (s.product_id)
        s.product_id::text,
        normalize_text(s.product_name),
        normalize_text(s.product_category),
        s.current_product_price,
        s.first_product_attribute,
        s.second_product_attribute,
        normalize_product_link(s.product_link),
        s.created_at::timestamp
    FROM products_unnormalized_data_staging s
    WHERE s.upload_job_id = p_job_id
    ORDER BY s.product_id, s.created_at DESC
    ON CONFLICT (product_id) DO UPDATE
    SET name = EXCLUDED.name,
        category = EXCLUDED.category,
        price = EXCLUDED.price,
        first_product_attribute = EXCLUDED.first_product_attribute,
        second_product_attribute = EXCLUDED.second_product_attribute,
        product_link = EXCLUDED.product_link,
        created_at = EXCLUDED.created_at;

    INSERT INTO products_unnormalized_data (
        tenant_id, internal_product_id, product_id, product_name,
        product_category, current_product_price, product_link,
        first_product_attribute, second_product_attribute,
        column_mapping, created_at
    )
    SELECT
        tenant_id, internal_product_id, product_id, product_name,
        product_category, current_product_price, product_link,
        first_product_attribute, second_product_attribute,
        column_mapping, created_at
    FROM products_unnormalized_data_staging
    WHERE upload_job_id = p_job_id;

    GET DIAGNOSTICS v_rows_moved = ROW_COUNT;
    IF v_rows_moved = 0 THEN
        RETURN 0;
    END IF;

    UPDATE users_unnormalized_data u
    SET product_id = i.product_id
    FROM global_product_identity i
    WHERE u.tenant_id = v_tenant_id
      AND i.tenant_id = u.tenant_id
      AND i.internal_product_id = u.internal_product_id
      AND u.product_id IS DISTINCT FROM i.product_id;

    PERFORM populate_order_items_batch(v_tenant_id::integer);

    SELECT array_agg(DISTINCT o.user_id)
    INTO v_affected_users
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    WHERE oi.product_id IN (
        SELECT product_id::text
        FROM products_unnormalized_data_staging
        WHERE upload_job_id = p_job_id
    );

    IF v_affected_users IS NOT NULL AND array_length(v_affected_users, 1) > 0 THEN
        PERFORM sync_attributes_batch_for_users(v_affected_users);
        PERFORM refresh_user_summary_batch_for_users(v_affected_users);
    END IF;

    PERFORM refresh_product_intervals_batch(v_tenant_id::integer);
    DELETE FROM products_unnormalized_data_staging
    WHERE upload_job_id = p_job_id;
    RETURN v_rows_moved;
END;
$$;
