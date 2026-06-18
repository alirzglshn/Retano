# core/migrations/0005_add_global_user_id_sequence.py
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_unnormalizeddatastaging'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE SEQUENCE IF NOT EXISTS global_user_id_seq
                    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

                CREATE SEQUENCE IF NOT EXISTS global_order_id_seq
                    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

                CREATE SEQUENCE IF NOT EXISTS global_product_id_seq
                    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
            """,
            reverse_sql="""
                DROP SEQUENCE IF EXISTS global_user_id_seq;
                DROP SEQUENCE IF EXISTS global_order_id_seq;
                DROP SEQUENCE IF EXISTS global_product_id_seq;
            """,
        ),
    ]