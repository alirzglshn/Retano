# core/migrations/0045_attribute_column_refactor.py
#
# What this migration does:
#
#   1.  On the managed model ProductsUnNormalizedData:
#         - Removes hair_tag and skin_tag fields
#         - Adds first_product_attribute and second_product_attribute fields
#
#   2.  RunSQL block applies the same column changes to all unmanaged /
#       Postgres-side tables that Django does not control directly:
#         - products_unnormalized_data_staging
#         - products
#         - user_summary  (with CASCADE handling for dependent views)
#         - user_attribute_scores  (schema restructure)
#
#   Dependent objects on user_summary that reference dominant_skin_type /
#   dominant_hair_type are dropped first and recreated with the new column
#   names:
#         - the_users_summary_rfm          (materialized view)
#         - the_users_summary_rfm_segmented (view — depends on the mat view)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0044_split_unnormalized_pipelines"),
    ]

    operations = [

        # ── Step 1: ProductsUnNormalizedData — remove hair_tag / skin_tag ─────
        migrations.RemoveField(
            model_name="productsunnormalizeddata",
            name="hair_tag",
        ),
        migrations.RemoveField(
            model_name="productsunnormalizeddata",
            name="skin_tag",
        ),

        # ── Step 2: ProductsUnNormalizedData — add first / second attribute ───
        migrations.AddField(
            model_name="productsunnormalizeddata",
            name="first_product_attribute",
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="productsunnormalizeddata",
            name="second_product_attribute",
            field=models.TextField(null=True, blank=True),
        ),

        # ── Step 3: Raw SQL for all Postgres-side tables ──────────────────────
        migrations.RunSQL(
            sql="""
-- ═════════════════════════════════════════════════════════════════════════════
-- products_unnormalized_data_staging  (unmanaged — Django does not touch DDL)
-- ═════════════════════════════════════════════════════════════════════════════
ALTER TABLE products_unnormalized_data_staging
    DROP COLUMN IF EXISTS hair_tag,
    DROP COLUMN IF EXISTS skin_tag;

ALTER TABLE products_unnormalized_data_staging
    ADD COLUMN IF NOT EXISTS first_product_attribute  TEXT NULL,
    ADD COLUMN IF NOT EXISTS second_product_attribute TEXT NULL;


-- ═════════════════════════════════════════════════════════════════════════════
-- products
-- ═════════════════════════════════════════════════════════════════════════════
ALTER TABLE products
    DROP COLUMN IF EXISTS hair_tag,
    DROP COLUMN IF EXISTS skin_tag;

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS first_product_attribute  TEXT NULL,
    ADD COLUMN IF NOT EXISTS second_product_attribute TEXT NULL;


-- ═════════════════════════════════════════════════════════════════════════════
-- user_summary
--
-- Two objects depend on dominant_skin_type / dominant_hair_type:
--   1. the_users_summary_rfm          (materialized view)
--   2. the_users_summary_rfm_segmented (view, depends on the mat view)
--
-- Order of operations:
--   A. Drop the view first (it depends on the mat view)
--   B. Drop the materialized view
--   C. Drop old columns, add new columns
--   D. Recreate the materialized view with new column names
--   E. Recreate the view (unchanged — it only uses r_score/f_score/m_score)
-- ═════════════════════════════════════════════════════════════════════════════

-- A. Drop dependent view first
DROP VIEW IF EXISTS the_users_summary_rfm_segmented;

-- B. Drop materialized view
DROP MATERIALIZED VIEW IF EXISTS the_users_summary_rfm;

-- C. Drop old columns, add new columns
ALTER TABLE user_summary
    DROP COLUMN IF EXISTS dominant_skin_type,
    DROP COLUMN IF EXISTS dominant_hair_type;

ALTER TABLE user_summary
    ADD COLUMN IF NOT EXISTS first_user_attribute  TEXT NULL,
    ADD COLUMN IF NOT EXISTS second_user_attribute TEXT NULL;

-- D. Recreate the_users_summary_rfm with new column names
--    dominant_skin_type → first_user_attribute
--    dominant_hair_type → second_user_attribute
--    All other columns, CTEs, and RFM scoring logic are identical.
CREATE MATERIALIZED VIEW the_users_summary_rfm AS
WITH
  base AS (
    SELECT
      user_summary.user_id,
      user_summary.total_spent,
      user_summary.num_orders,
      user_summary.aov,
      user_summary.last_purchase_date,
      user_summary.average_money_spent,
      user_summary.next_predicted_purchase_date,
      user_summary.buying_power,
      user_summary.first_user_attribute,
      user_summary.second_user_attribute,
      user_summary.profile_confidence,
      user_summary.last_purchase_product_id,
      user_summary.top_1,
      user_summary.top_2,
      user_summary.top_3,
      user_summary.rep_top1,
      user_summary.rep_top2,
      user_summary.rep_top3,
      user_summary.rfm_segment,
      user_summary.computed_at,
      user_summary.recency_days,
      user_summary.frequency,
      user_summary.monetary,
      user_summary.updated_at,
      user_summary.gender
    FROM user_summary
    WHERE
      user_summary.recency_days IS NOT NULL
      AND user_summary.frequency  IS NOT NULL
      AND user_summary.monetary   IS NOT NULL
  ),
  quartiles AS (
    SELECT
      percentile_cont(0.25) WITHIN GROUP (ORDER BY base.recency_days::DOUBLE PRECISION) AS r_q1,
      percentile_cont(0.75) WITHIN GROUP (ORDER BY base.recency_days::DOUBLE PRECISION) AS r_q3,
      percentile_cont(0.25) WITHIN GROUP (ORDER BY base.frequency::DOUBLE PRECISION)    AS f_q1,
      percentile_cont(0.75) WITHIN GROUP (ORDER BY base.frequency::DOUBLE PRECISION)    AS f_q3,
      percentile_cont(0.25) WITHIN GROUP (ORDER BY base.monetary::DOUBLE PRECISION)     AS m_q1,
      percentile_cont(0.75) WITHIN GROUP (ORDER BY base.monetary::DOUBLE PRECISION)     AS m_q3
    FROM base
  ),
  cleaned AS (
    SELECT
      b.user_id,
      b.total_spent,
      b.num_orders,
      b.aov,
      b.last_purchase_date,
      b.average_money_spent,
      b.next_predicted_purchase_date,
      b.buying_power,
      b.first_user_attribute,
      b.second_user_attribute,
      b.profile_confidence,
      b.last_purchase_product_id,
      b.top_1,
      b.top_2,
      b.top_3,
      b.rep_top1,
      b.rep_top2,
      b.rep_top3,
      b.rfm_segment,
      b.computed_at,
      b.recency_days,
      b.frequency,
      b.monetary,
      b.updated_at,
      b.gender
    FROM base b
    CROSS JOIN quartiles q
    WHERE
      b.recency_days::DOUBLE PRECISION >= (q.r_q1 - 1.5::DOUBLE PRECISION * (q.r_q3 - q.r_q1))
      AND b.recency_days::DOUBLE PRECISION <= (q.r_q3 + 1.5::DOUBLE PRECISION * (q.r_q3 - q.r_q1))
      AND b.frequency::DOUBLE PRECISION  >= (q.f_q1 - 1.5::DOUBLE PRECISION * (q.f_q3 - q.f_q1))
      AND b.frequency::DOUBLE PRECISION  <= (q.f_q3 + 1.5::DOUBLE PRECISION * (q.f_q3 - q.f_q1))
      AND b.monetary::DOUBLE PRECISION   >= (q.m_q1 - 1.5::DOUBLE PRECISION * (q.m_q3 - q.m_q1))
      AND b.monetary::DOUBLE PRECISION   <= (q.m_q3 + 1.5::DOUBLE PRECISION * (q.m_q3 - q.m_q1))
  ),
  rfm_percentiles AS (
    SELECT
      percentile_cont(0.2) WITHIN GROUP (ORDER BY cleaned.recency_days::DOUBLE PRECISION) AS r20,
      percentile_cont(0.4) WITHIN GROUP (ORDER BY cleaned.recency_days::DOUBLE PRECISION) AS r40,
      percentile_cont(0.6) WITHIN GROUP (ORDER BY cleaned.recency_days::DOUBLE PRECISION) AS r60,
      percentile_cont(0.8) WITHIN GROUP (ORDER BY cleaned.recency_days::DOUBLE PRECISION) AS r80,
      percentile_cont(0.2) WITHIN GROUP (ORDER BY cleaned.frequency::DOUBLE PRECISION)    AS f20,
      percentile_cont(0.4) WITHIN GROUP (ORDER BY cleaned.frequency::DOUBLE PRECISION)    AS f40,
      percentile_cont(0.6) WITHIN GROUP (ORDER BY cleaned.frequency::DOUBLE PRECISION)    AS f60,
      percentile_cont(0.8) WITHIN GROUP (ORDER BY cleaned.frequency::DOUBLE PRECISION)    AS f80,
      percentile_cont(0.2) WITHIN GROUP (ORDER BY cleaned.monetary::DOUBLE PRECISION)     AS m20,
      percentile_cont(0.4) WITHIN GROUP (ORDER BY cleaned.monetary::DOUBLE PRECISION)     AS m40,
      percentile_cont(0.6) WITHIN GROUP (ORDER BY cleaned.monetary::DOUBLE PRECISION)     AS m60,
      percentile_cont(0.8) WITHIN GROUP (ORDER BY cleaned.monetary::DOUBLE PRECISION)     AS m80
    FROM cleaned
  ),
  scored AS (
    SELECT
      b.user_id,
      CASE
        WHEN b.recency_days::DOUBLE PRECISION <= p.r20 THEN 5
        WHEN b.recency_days::DOUBLE PRECISION <= p.r40 THEN 4
        WHEN b.recency_days::DOUBLE PRECISION <= p.r60 THEN 3
        WHEN b.recency_days::DOUBLE PRECISION <= p.r80 THEN 2
        ELSE 1
      END AS r_score,
      CASE
        WHEN b.frequency::DOUBLE PRECISION <= p.f20 THEN 1
        WHEN b.frequency::DOUBLE PRECISION <= p.f40 THEN 2
        WHEN b.frequency::DOUBLE PRECISION <= p.f60 THEN 3
        WHEN b.frequency::DOUBLE PRECISION <= p.f80 THEN 4
        ELSE 5
      END AS f_score,
      CASE
        WHEN b.monetary::DOUBLE PRECISION <= p.m20 THEN 1
        WHEN b.monetary::DOUBLE PRECISION <= p.m40 THEN 2
        WHEN b.monetary::DOUBLE PRECISION <= p.m60 THEN 3
        WHEN b.monetary::DOUBLE PRECISION <= p.m80 THEN 4
        ELSE 5
      END AS m_score
    FROM base b
    CROSS JOIN rfm_percentiles p
  )
SELECT
  user_id,
  r_score,
  f_score,
  m_score
FROM scored;

-- E. Recreate the_users_summary_rfm_segmented — body is 100% unchanged
--    (it only references r_score, f_score, m_score — no attribute columns)
CREATE VIEW the_users_summary_rfm_segmented AS
SELECT
  user_id,
  r_score,
  f_score,
  m_score,
  CASE
    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'vip'
    WHEN r_score >= 4 AND f_score <= 2 AND m_score <= 2 THEN 'new'
    WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'at_risk'
    WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'churned'
    ELSE 'active'
  END AS user_segment
FROM the_users_summary_rfm;


-- ═════════════════════════════════════════════════════════════════════════════
-- user_attribute_scores
-- Schema restructure:
--   • Remove attribute_type column
--   • Add attribute_slot TEXT NOT NULL  (values: 'first' | 'second')
--   • Rebuild PK as (user_id, attribute_slot)
--   • Drop the old separate unique constraint (PK now covers uniqueness)
--
-- Data migration:
--   'Hair Type' → 'first'
--   'Skin Type'  → 'second'
--   Any other value is deleted (safety guard — should not exist).
-- ═════════════════════════════════════════════════════════════════════════════

-- Step A: Add new column (nullable first — existing rows cannot violate NOT NULL)
ALTER TABLE user_attribute_scores
    ADD COLUMN IF NOT EXISTS attribute_slot TEXT NULL;

-- Step B: Migrate existing data
UPDATE user_attribute_scores
SET attribute_slot = CASE
    WHEN attribute_type = 'Hair Type' THEN 'first'
    WHEN attribute_type = 'Skin Type' THEN 'second'
    ELSE NULL
END;

-- Step C: Delete any unmapped rows
DELETE FROM user_attribute_scores
WHERE attribute_slot IS NULL;

-- Step D: Enforce NOT NULL now that all rows have a valid value
ALTER TABLE user_attribute_scores
    ALTER COLUMN attribute_slot SET NOT NULL;

-- Step E: Drop the old primary key (user_id, attribute_type, attribute_value)
ALTER TABLE user_attribute_scores
    DROP CONSTRAINT IF EXISTS user_attribute_scores_pkey;

-- Step F: Drop the old unique constraint (user_id, attribute_type)
ALTER TABLE user_attribute_scores
    DROP CONSTRAINT IF EXISTS uq_user_attribute;

-- Step G: Drop the old attribute_type column
ALTER TABLE user_attribute_scores
    DROP COLUMN IF EXISTS attribute_type;

-- Step H: Add new PK (user_id, attribute_slot)
--         Enforces exactly two rows per user_id ('first' and 'second').
--         Replaces both the old PK and the old unique constraint.
ALTER TABLE user_attribute_scores
    ADD CONSTRAINT user_attribute_scores_pkey
    PRIMARY KEY (user_id, attribute_slot);
""",
            reverse_sql="""
-- ── Reverse user_attribute_scores ────────────────────────────────────────────
ALTER TABLE user_attribute_scores
    ADD COLUMN IF NOT EXISTS attribute_type TEXT NULL;

UPDATE user_attribute_scores
SET attribute_type = CASE
    WHEN attribute_slot = 'first'  THEN 'Hair Type'
    WHEN attribute_slot = 'second' THEN 'Skin Type'
END;

ALTER TABLE user_attribute_scores
    ALTER COLUMN attribute_type SET NOT NULL;

ALTER TABLE user_attribute_scores
    DROP CONSTRAINT IF EXISTS user_attribute_scores_pkey;

ALTER TABLE user_attribute_scores
    DROP COLUMN IF EXISTS attribute_slot;

ALTER TABLE user_attribute_scores
    ADD CONSTRAINT user_attribute_scores_pkey
    PRIMARY KEY (user_id, attribute_type, attribute_value);

ALTER TABLE user_attribute_scores
    ADD CONSTRAINT uq_user_attribute
    UNIQUE (user_id, attribute_type);

-- ── Reverse user_summary ─────────────────────────────────────────────────────
DROP VIEW IF EXISTS the_users_summary_rfm_segmented;
DROP MATERIALIZED VIEW IF EXISTS the_users_summary_rfm;

ALTER TABLE user_summary
    DROP COLUMN IF EXISTS first_user_attribute,
    DROP COLUMN IF EXISTS second_user_attribute;

ALTER TABLE user_summary
    ADD COLUMN IF NOT EXISTS dominant_skin_type TEXT NULL,
    ADD COLUMN IF NOT EXISTS dominant_hair_type TEXT NULL;

-- Recreate materialized view with original column names
CREATE MATERIALIZED VIEW the_users_summary_rfm AS
WITH
  base AS (
    SELECT
      user_summary.user_id,
      user_summary.total_spent,
      user_summary.num_orders,
      user_summary.aov,
      user_summary.last_purchase_date,
      user_summary.average_money_spent,
      user_summary.next_predicted_purchase_date,
      user_summary.buying_power,
      user_summary.dominant_skin_type,
      user_summary.dominant_hair_type,
      user_summary.profile_confidence,
      user_summary.last_purchase_product_id,
      user_summary.top_1,
      user_summary.top_2,
      user_summary.top_3,
      user_summary.rep_top1,
      user_summary.rep_top2,
      user_summary.rep_top3,
      user_summary.rfm_segment,
      user_summary.computed_at,
      user_summary.recency_days,
      user_summary.frequency,
      user_summary.monetary,
      user_summary.updated_at,
      user_summary.gender
    FROM user_summary
    WHERE
      user_summary.recency_days IS NOT NULL
      AND user_summary.frequency  IS NOT NULL
      AND user_summary.monetary   IS NOT NULL
  ),
  quartiles AS (
    SELECT
      percentile_cont(0.25) WITHIN GROUP (ORDER BY base.recency_days::DOUBLE PRECISION) AS r_q1,
      percentile_cont(0.75) WITHIN GROUP (ORDER BY base.recency_days::DOUBLE PRECISION) AS r_q3,
      percentile_cont(0.25) WITHIN GROUP (ORDER BY base.frequency::DOUBLE PRECISION)    AS f_q1,
      percentile_cont(0.75) WITHIN GROUP (ORDER BY base.frequency::DOUBLE PRECISION)    AS f_q3,
      percentile_cont(0.25) WITHIN GROUP (ORDER BY base.monetary::DOUBLE PRECISION)     AS m_q1,
      percentile_cont(0.75) WITHIN GROUP (ORDER BY base.monetary::DOUBLE PRECISION)     AS m_q3
    FROM base
  ),
  cleaned AS (
    SELECT
      b.user_id, b.total_spent, b.num_orders, b.aov,
      b.last_purchase_date, b.average_money_spent,
      b.next_predicted_purchase_date, b.buying_power,
      b.dominant_skin_type, b.dominant_hair_type,
      b.profile_confidence, b.last_purchase_product_id,
      b.top_1, b.top_2, b.top_3,
      b.rep_top1, b.rep_top2, b.rep_top3,
      b.rfm_segment, b.computed_at,
      b.recency_days, b.frequency, b.monetary,
      b.updated_at, b.gender
    FROM base b CROSS JOIN quartiles q
    WHERE
      b.recency_days::DOUBLE PRECISION BETWEEN
        (q.r_q1 - 1.5 * (q.r_q3 - q.r_q1)) AND (q.r_q3 + 1.5 * (q.r_q3 - q.r_q1))
      AND b.frequency::DOUBLE PRECISION BETWEEN
        (q.f_q1 - 1.5 * (q.f_q3 - q.f_q1)) AND (q.f_q3 + 1.5 * (q.f_q3 - q.f_q1))
      AND b.monetary::DOUBLE PRECISION BETWEEN
        (q.m_q1 - 1.5 * (q.m_q3 - q.m_q1)) AND (q.m_q3 + 1.5 * (q.m_q3 - q.m_q1))
  ),
  rfm_percentiles AS (
    SELECT
      percentile_cont(0.2) WITHIN GROUP (ORDER BY cleaned.recency_days::DOUBLE PRECISION) AS r20,
      percentile_cont(0.4) WITHIN GROUP (ORDER BY cleaned.recency_days::DOUBLE PRECISION) AS r40,
      percentile_cont(0.6) WITHIN GROUP (ORDER BY cleaned.recency_days::DOUBLE PRECISION) AS r60,
      percentile_cont(0.8) WITHIN GROUP (ORDER BY cleaned.recency_days::DOUBLE PRECISION) AS r80,
      percentile_cont(0.2) WITHIN GROUP (ORDER BY cleaned.frequency::DOUBLE PRECISION)    AS f20,
      percentile_cont(0.4) WITHIN GROUP (ORDER BY cleaned.frequency::DOUBLE PRECISION)    AS f40,
      percentile_cont(0.6) WITHIN GROUP (ORDER BY cleaned.frequency::DOUBLE PRECISION)    AS f60,
      percentile_cont(0.8) WITHIN GROUP (ORDER BY cleaned.frequency::DOUBLE PRECISION)    AS f80,
      percentile_cont(0.2) WITHIN GROUP (ORDER BY cleaned.monetary::DOUBLE PRECISION)     AS m20,
      percentile_cont(0.4) WITHIN GROUP (ORDER BY cleaned.monetary::DOUBLE PRECISION)     AS m40,
      percentile_cont(0.6) WITHIN GROUP (ORDER BY cleaned.monetary::DOUBLE PRECISION)     AS m60,
      percentile_cont(0.8) WITHIN GROUP (ORDER BY cleaned.monetary::DOUBLE PRECISION)     AS m80
    FROM cleaned
  ),
  scored AS (
    SELECT
      b.user_id,
      CASE WHEN b.recency_days::DOUBLE PRECISION <= p.r20 THEN 5
           WHEN b.recency_days::DOUBLE PRECISION <= p.r40 THEN 4
           WHEN b.recency_days::DOUBLE PRECISION <= p.r60 THEN 3
           WHEN b.recency_days::DOUBLE PRECISION <= p.r80 THEN 2
           ELSE 1 END AS r_score,
      CASE WHEN b.frequency::DOUBLE PRECISION  <= p.f20 THEN 1
           WHEN b.frequency::DOUBLE PRECISION  <= p.f40 THEN 2
           WHEN b.frequency::DOUBLE PRECISION  <= p.f60 THEN 3
           WHEN b.frequency::DOUBLE PRECISION  <= p.f80 THEN 4
           ELSE 5 END AS f_score,
      CASE WHEN b.monetary::DOUBLE PRECISION   <= p.m20 THEN 1
           WHEN b.monetary::DOUBLE PRECISION   <= p.m40 THEN 2
           WHEN b.monetary::DOUBLE PRECISION   <= p.m60 THEN 3
           WHEN b.monetary::DOUBLE PRECISION   <= p.m80 THEN 4
           ELSE 5 END AS m_score
    FROM base b CROSS JOIN rfm_percentiles p
  )
SELECT user_id, r_score, f_score, m_score FROM scored;

CREATE VIEW the_users_summary_rfm_segmented AS
SELECT user_id, r_score, f_score, m_score,
  CASE
    WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'vip'
    WHEN r_score >= 4 AND f_score <= 2 AND m_score <= 2 THEN 'new'
    WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'at_risk'
    WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'churned'
    ELSE 'active'
  END AS user_segment
FROM the_users_summary_rfm;

-- ── Reverse products ─────────────────────────────────────────────────────────
ALTER TABLE products
    DROP COLUMN IF EXISTS first_product_attribute,
    DROP COLUMN IF EXISTS second_product_attribute;

ALTER TABLE products
    ADD COLUMN IF NOT EXISTS hair_tag TEXT NULL,
    ADD COLUMN IF NOT EXISTS skin_tag TEXT NULL;

-- ── Reverse products_unnormalized_data_staging ────────────────────────────────
ALTER TABLE products_unnormalized_data_staging
    DROP COLUMN IF EXISTS first_product_attribute,
    DROP COLUMN IF EXISTS second_product_attribute;

ALTER TABLE products_unnormalized_data_staging
    ADD COLUMN IF NOT EXISTS hair_tag CHARACTER VARYING(100) NULL,
    ADD COLUMN IF NOT EXISTS skin_tag CHARACTER VARYING(100) NULL;
""",
        ),
    ]
