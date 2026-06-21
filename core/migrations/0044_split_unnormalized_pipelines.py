# IMPORTANT: adjust the dependency below to match your actual last migration.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0043_remove_unnormalizeddata_tag"),
    ]

    operations = [

        # ── Step 1: Remove old managed models ────────────────────────────────
        # Django issues DROP TABLE IF EXISTS for each of these.
        migrations.DeleteModel(name="CampaignColumnMapping"),
        migrations.DeleteModel(name="TenantFileUpload"),
        migrations.DeleteModel(name="UnNormalizedData"),

        # ── Step 2: Create CustomerFileUpload ─────────────────────────────────
        migrations.CreateModel(
            name="CustomerFileUpload",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                (
                    "customers_file",
                    models.FileField(upload_to="campaign_customers/"),
                ),
                (
                    "customers_mapping",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Maps field names to zero-based column indices "
                            "in the customers Excel file."
                        ),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.tenant",
                    ),
                ),
            ],
        ),

        # ── Step 3: Create ProductFileUpload ──────────────────────────────────
        migrations.CreateModel(
            name="ProductFileUpload",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                (
                    "products_file",
                    models.FileField(upload_to="campaign_products/"),
                ),
                (
                    "products_mapping",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Maps field names to zero-based column indices "
                            "in the products Excel file."
                        ),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.tenant",
                    ),
                ),
            ],
        ),

        # ── Step 4: Create CouponFileUpload ───────────────────────────────────
        migrations.CreateModel(
            name="CouponFileUpload",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                (
                    "coupons_file",
                    models.FileField(upload_to="campaign_coupons/"),
                ),
                (
                    "coupons_mapping",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "Maps field names to zero-based column indices "
                            "in the coupons Excel file."
                        ),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.tenant",
                    ),
                ),
            ],
        ),

        # ── Step 5: Create UsersUnNormalizedData (managed) ────────────────────
        migrations.CreateModel(
            name="UsersUnNormalizedData",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                ("internal_user_id", models.TextField(default="null")),
                ("user_id", models.IntegerField()),
                ("first_name", models.CharField(max_length=200)),
                ("last_name", models.TextField(null=True, blank=True)),
                (
                    "gender",
                    models.TextField(null=True, blank=True, default="زن"),
                ),
                ("phone_number", models.TextField(null=True, blank=True)),
                ("internal_order_id", models.TextField(default="null")),
                ("order_id", models.IntegerField()),
                ("order_date", models.DateTimeField(null=True, blank=True)),
                ("internal_product_id", models.TextField(default="null")),
                (
                    "product_id",
                    models.IntegerField(null=True, blank=True),
                ),
                (
                    "then_product_price",
                    models.DecimalField(max_digits=10, decimal_places=2),
                ),
                ("quantity", models.IntegerField()),
                (
                    "subtotal",
                    models.DecimalField(
                        max_digits=12, decimal_places=2,
                        null=True, blank=True,
                    ),
                ),
                (
                    "column_mapping",
                    models.JSONField(default=dict, blank=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.tenant",
                    ),
                ),
            ],
            options={"db_table": "users_unnormalized_data"},
        ),
        migrations.AddIndex(
            model_name="usersunnormalizeddata",
            index=models.Index(
                fields=["tenant_id"],
                name="users_unnorm_tenant_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usersunnormalizeddata",
            index=models.Index(
                fields=["internal_product_id"],
                name="users_unnorm_int_prod_idx",
            ),
        ),

        # ── Step 6: Create ProductsUnNormalizedData (managed) ─────────────────
        migrations.CreateModel(
            name="ProductsUnNormalizedData",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                ("internal_product_id", models.TextField(default="null")),
                ("product_id", models.IntegerField()),
                ("product_name", models.CharField(max_length=255)),
                ("product_category", models.CharField(max_length=100)),
                (
                    "current_product_price",
                    models.DecimalField(max_digits=10, decimal_places=2),
                ),
                (
                    "product_link",
                    models.URLField(max_length=2000, blank=True),
                ),
                (
                    "hair_tag",
                    models.CharField(max_length=100, null=True, blank=True),
                ),
                (
                    "skin_tag",
                    models.CharField(max_length=100, null=True, blank=True),
                ),
                (
                    "column_mapping",
                    models.JSONField(default=dict, blank=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="core.tenant",
                    ),
                ),
            ],
            options={"db_table": "products_unnormalized_data"},
        ),
        migrations.AddIndex(
            model_name="productsunnormalizeddata",
            index=models.Index(
                fields=["tenant_id"],
                name="products_unnorm_tenant_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="productsunnormalizeddata",
            index=models.Index(
                fields=["internal_product_id"],
                name="products_unnorm_int_prod_idx",
            ),
        ),

        # ── Step 7: Raw SQL — staging tables, sequences, trigger ──────────────
        migrations.RunSQL(
            sql="""
-- Drop the old unified staging table if it still exists
DROP TABLE IF EXISTS unnormalized_data_staging CASCADE;

-- Ensure all three global ID sequences exist (idempotent)
CREATE SEQUENCE IF NOT EXISTS global_user_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE SEQUENCE IF NOT EXISTS global_order_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE SEQUENCE IF NOT EXISTS global_product_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

-- ─────────────────────────────────────────────────────────────────────────────
-- users_unnormalized_data_staging
-- Mirrors users_unnormalized_data exactly; own bigserial; no triggers.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users_unnormalized_data_staging (
    id                  BIGSERIAL                    NOT NULL,
    tenant_id           BIGINT                       NOT NULL,
    internal_user_id    TEXT                         NOT NULL DEFAULT 'null',
    user_id             INTEGER                      NOT NULL,
    first_name          CHARACTER VARYING(200)       NOT NULL,
    last_name           TEXT                         NULL,
    gender              TEXT                         NULL     DEFAULT 'زن',
    phone_number        TEXT                         NULL,
    internal_order_id   TEXT                         NOT NULL DEFAULT 'null',
    order_id            INTEGER                      NOT NULL,
    order_date          TIMESTAMP WITHOUT TIME ZONE  NULL,
    internal_product_id TEXT                         NOT NULL DEFAULT 'null',
    product_id          INTEGER                      NULL,
    then_product_price  NUMERIC(10, 2)               NOT NULL,
    quantity            INTEGER                      NOT NULL,
    subtotal            NUMERIC(12, 2)               NULL,
    column_mapping      JSONB                        NOT NULL DEFAULT '{}',
    created_at          TIMESTAMP WITH TIME ZONE     NOT NULL DEFAULT NOW(),
    CONSTRAINT users_unnormalized_data_staging_pkey PRIMARY KEY (id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- products_unnormalized_data_staging
-- Mirrors products_unnormalized_data exactly; own bigserial; no triggers.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products_unnormalized_data_staging (
    id                      BIGSERIAL                   NOT NULL,
    tenant_id               BIGINT                      NOT NULL,
    internal_product_id     TEXT                        NOT NULL DEFAULT 'null',
    product_id              INTEGER                     NOT NULL,
    product_name            CHARACTER VARYING(255)      NOT NULL,
    product_category        CHARACTER VARYING(100)      NOT NULL,
    current_product_price   NUMERIC(10, 2)              NOT NULL,
    product_link            CHARACTER VARYING(2000)     NOT NULL DEFAULT '',
    hair_tag                CHARACTER VARYING(100)      NULL,
    skin_tag                CHARACTER VARYING(100)      NULL,
    column_mapping          JSONB                       NOT NULL DEFAULT '{}',
    created_at              TIMESTAMP WITH TIME ZONE    NOT NULL DEFAULT NOW(),
    CONSTRAINT products_unnormalized_data_staging_pkey PRIMARY KEY (id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- a_trg_set_user_tenant on users_unnormalized_data
-- Stamps users.tenant_id when a customer row is inserted.
-- NOT created on products_unnormalized_data (intentional — no user_id there).
-- ─────────────────────────────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS a_trg_set_user_tenant ON users_unnormalized_data;

CREATE TRIGGER a_trg_set_user_tenant
    AFTER INSERT ON users_unnormalized_data
    FOR EACH ROW
    EXECUTE FUNCTION set_user_tenant_id_once();
""",
            reverse_sql="""
DROP TRIGGER IF EXISTS a_trg_set_user_tenant ON users_unnormalized_data;
DROP TABLE  IF EXISTS products_unnormalized_data_staging CASCADE;
DROP TABLE  IF EXISTS users_unnormalized_data_staging    CASCADE;
""",
        ),
    ]
