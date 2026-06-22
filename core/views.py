# core/views.py

import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction, connection

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Campaign,
    Tenant,
    Coupon,
    CustomerFileUpload,
    ProductFileUpload,
    CouponFileUpload,
    UsersUnNormalizedDataStaging,
    ProductsUnNormalizedDataStaging,
)
from .forms import (
    ColumnMappingForm,
    CustomerFileUploadForm,
    ProductFileUploadForm,
    CouponFileUploadForm,
)
from .serializers import (
    CampaignListSerializer,
    CampaignSerializer,
    CampaignToggleSerializer,
)
from .utils.excel_mapper import (
    CustomerExcelMapper,
    ProductExcelMapper,
    CouponExcelMapper,
)


# ─────────────────────────────────────────────────────────────────────────────
# Campaigns — DRF (Phase 4)
#
# Replaces the legacy CampaignCreateView / CampaignUpdateView /
# CampaignListView / CampaignDetailView / CampaignDeleteView CBVs, per the
# SSR → DRF roadmap (Django CBVs are explicitly out for the DRF layer).
# ─────────────────────────────────────────────────────────────────────────────


class CampaignViewSet(viewsets.ModelViewSet):
    """
    /api/v1/campaigns/                 — list, create
    /api/v1/campaigns/{id}/            — retrieve, update, partial_update, destroy
    /api/v1/campaigns/{id}/toggle/     — PATCH, flips/sets is_active

    Tenant isolation: every queryset is scoped to the requesting user's
    own tenant. A campaign belonging to another tenant is invisible —
    not "403 Forbidden", just a 404, since DRF's get_object() raises
    Http404 when the filtered queryset doesn't contain the pk.
    """

    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active"]
    search_fields = ["name"]
    ordering_fields = ["created_at", "name", "rule_number"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Campaign.objects.filter(tenant__owner=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return CampaignListSerializer
        if self.action == "toggle":
            return CampaignToggleSerializer
        return CampaignSerializer

    def perform_create(self, serializer):
        # tenant is never trusted from the client — derived from the
        # authenticated user's own Tenant (created via signal at registration).
        serializer.save(tenant=self.request.user.tenant)

    @action(detail=True, methods=["patch"])
    def toggle(self, request, pk=None):
        """
        PATCH /api/v1/campaigns/{id}/toggle/

        Body {} or omitted        → flips is_active.
        Body {"is_active": true}  → sets it explicitly.
        """
        campaign = self.get_object()

        if "is_active" in request.data:
            serializer = self.get_serializer(
                campaign, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
        else:
            campaign.is_active = not campaign.is_active
            campaign.save(update_fields=["is_active"])
            serializer = self.get_serializer(campaign)

        return Response(serializer.data, status=status.HTTP_200_OK)


class CampaignMetaView(APIView):
    """
    GET /api/v1/campaigns/meta/

    Returns every choice-field's available options so the frontend can
    build selects/dropdowns without hardcoding Persian labels.

    Shape:
        {
            "activation_base": [{"value": "...", "label": "..."}, ...],
            "comparison_type": [...],
            ...
        }
    """

    permission_classes = [permissions.IsAuthenticated]

    #: Campaign fields whose `choices` should be exposed. Listed explicitly
    #: rather than introspected so the response shape is stable even if
    #: unrelated choice fields get added to the model later.
    CHOICE_FIELDS = [
        "coupon_discount_percentage",
        "activation_base",
        "comparison_type",
        "value_unit",
        "gender",
        "buying_power",
        "priority",
        "product_source",
        "customer_type",
    ]

    def get(self, request):
        data = {}
        for field_name in self.CHOICE_FIELDS:
            field = Campaign._meta.get_field(field_name)
            choices = field.choices or []
            data[field_name] = [
                {"value": value, "label": label} for value, label in choices
            ]
        return Response(data, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# Excel file upload — single view, three fully independent pipelines
#
# Unchanged from the pre-DRF version. Will be wrapped behind DRF APIViews
# in Phase 6 (Uploads) — the pipeline logic itself (_process_coupons,
# _process_customers, _process_products) is reused as-is, not rewritten.
# ─────────────────────────────────────────────────────────────────────────────

class CampaignExcelFilesView(LoginRequiredMixin, View):
    template_name = "campaigns/excel_upload.html"

    def _get_context(
        self,
        customer_form=None,
        product_form=None,
        coupon_form=None,
        mapping_form=None,
    ):
        return {
            "customer_form":  customer_form or CustomerFileUploadForm(),
            "product_form":   product_form  or ProductFileUploadForm(),
            "coupon_form":    coupon_form   or CouponFileUploadForm(),
            "mapping_form":   mapping_form  or ColumnMappingForm(),
            "customers_instructions": CustomerExcelMapper.INSTRUCTIONS,
            "customers_fields_desc":  CustomerExcelMapper.FIELDS_DESCRIPTION,
            "products_instructions":  ProductExcelMapper.INSTRUCTIONS,
            "products_fields_desc":   ProductExcelMapper.FIELDS_DESCRIPTION,
            "coupons_instructions":   CouponExcelMapper.INSTRUCTIONS,
            "coupons_fields_desc":    CouponExcelMapper.FIELDS_DESCRIPTION,
            "sample_customers_mapping": CustomerExcelMapper.get_sample_mapping(),
            "sample_products_mapping":  ProductExcelMapper.get_sample_mapping(),
            "sample_coupons_mapping":   CouponExcelMapper.get_sample_mapping(),
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self._get_context())

    def post(self, request, *args, **kwargs):
        uploaded_files = {
            "customers_file": request.FILES.get("customers_file"),
            "products_file":  request.FILES.get("products_file"),
            "coupons_file":   request.FILES.get("coupons_file"),
        }

        if not any(uploaded_files.values()):
            messages.error(request, "حداقل یکی از فایل‌ها باید آپلود شود.")
            return redirect("campaign-excel-files")

        customer_form = CustomerFileUploadForm(request.POST, request.FILES)
        product_form  = ProductFileUploadForm(request.POST,  request.FILES)
        coupon_form   = CouponFileUploadForm(request.POST,  request.FILES)
        mapping_form  = ColumnMappingForm(request.POST, uploaded_files=uploaded_files)

        customer_form_valid = (
            customer_form.is_valid() if uploaded_files["customers_file"] else True
        )
        product_form_valid = (
            product_form.is_valid() if uploaded_files["products_file"] else True
        )
        coupon_form_valid = (
            coupon_form.is_valid() if uploaded_files["coupons_file"] else True
        )
        mapping_form_valid = mapping_form.is_valid()

        if not all([
            customer_form_valid,
            product_form_valid,
            coupon_form_valid,
            mapping_form_valid,
        ]):
            return render(
                request,
                self.template_name,
                self._get_context(
                    customer_form=customer_form,
                    product_form=product_form,
                    coupon_form=coupon_form,
                    mapping_form=mapping_form,
                ),
            )

        tenant = Tenant.objects.get(owner=request.user)

        if uploaded_files["coupons_file"]:
            self._process_coupons(request, tenant, coupon_form, mapping_form)

        if uploaded_files["customers_file"]:
            self._process_customers(request, tenant, customer_form, mapping_form)

        if uploaded_files["products_file"]:
            self._process_products(request, tenant, product_form, mapping_form)

        return redirect("campaign-excel-files")

    # ── Coupons pipeline (unchanged) ──────────────────────────────────────────

    def _process_coupons(self, request, tenant, coupon_form, mapping_form):
        existing_available = Coupon.objects.filter(
            tenant=tenant, status="available"
        ).exists()
        if existing_available:
            messages.error(
                request,
                "شما هنوز کوپن‌های استفاده نشده دارید. "
                "تا زمانی که همه کوپن‌ها استفاده نشده‌اند، "
                "امکان آپلود فایل کوپن جدید وجود ندارد.",
            )
            return

        coupons_mapping = mapping_form.get_coupons_mapping()

        with transaction.atomic():
            coupon_upload = coupon_form.save(commit=False)
            coupon_upload.tenant = tenant
            coupon_upload.coupons_mapping = coupons_mapping
            coupon_upload.save()

        try:
            coupons_df, _ = CouponExcelMapper.validate_and_map_file(
                coupon_upload.coupons_file.path, coupons_mapping
            )
        except Exception as e:
            messages.error(request, f"خطا در پردازش فایل کوپن: {str(e)}")
            return

        coupon_objects = []
        for _, row in coupons_df.iterrows():
            coupon_code = str(row.get("coupon_code", "")).strip()
            if not coupon_code:
                continue
            try:
                discount_val = float(row.get("discount_percentage", 0))
            except (ValueError, TypeError):
                discount_val = 0
            coupon_objects.append(
                Coupon(
                    tenant=tenant,
                    coupon_code=coupon_code,
                    discount_percentage=discount_val,
                    status="available",
                )
            )

        if coupon_objects:
            Coupon.objects.bulk_create(
                coupon_objects, batch_size=1000, ignore_conflicts=True
            )
            messages.success(
                request,
                f"{len(coupon_objects)} کوپن با موفقیت در دیتابیس ذخیره شد.",
            )
        else:
            messages.warning(request, "هیچ کوپن معتبری در فایل یافت نشد.")

    # ── Customers pipeline (unchanged) ────────────────────────────────────────

    def _process_customers(self, request, tenant, customer_form, mapping_form):
        customers_mapping = mapping_form.get_customers_mapping()

        is_valid, error_msg = CustomerExcelMapper.validate_mapping_integrity(
            customers_mapping
        )
        if not is_valid:
            messages.error(
                request, f"خطا در نگاشت ستون‌های فایل مشتریان: {error_msg}"
            )
            return

        with transaction.atomic():
            customer_upload = customer_form.save(commit=False)
            customer_upload.tenant = tenant
            customer_upload.customers_mapping = customers_mapping
            customer_upload.save()

        try:
            customers_df, actual_mapping = CustomerExcelMapper.validate_and_map_file(
                customer_upload.customers_file.path, customers_mapping
            )
        except ValueError as e:
            messages.error(request, f"خطا در پردازش فایل مشتریان: {str(e)}")
            return
        except Exception as e:
            messages.error(request, f"خطای غیرمنتظره در فایل مشتریان: {str(e)}")
            return

        if customers_df["order_date"].isna().any():
            invalid_rows = (
                customers_df[customers_df["order_date"].isna()].index.tolist()
            )
            messages.warning(
                request,
                f"اخطار: تاریخ برای ردیف‌های {invalid_rows} قابل پردازش نیست. "
                "این ردیف‌ها با تاریخ خالی ذخیره می‌شوند.",
            )

        customers_df["internal_id"]         = customers_df["internal_id"].astype(str)
        customers_df["internal_order_id"]   = customers_df["internal_order_id"].astype(str)
        customers_df["internal_product_id"] = customers_df["internal_product_id"].astype(str)

        # Allocate globally-unique user_ids
        unique_internal_ids = (
            customers_df[["internal_id"]].drop_duplicates()["internal_id"].tolist()
        )
        user_id_mapping: dict = {}

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT internal_user_id, user_id
                FROM users_unnormalized_data
                WHERE tenant_id = %s
                  AND internal_user_id = ANY(%s)
                """,
                [tenant.id, unique_internal_ids],
            )
            for internal_id, uid in cursor.fetchall():
                user_id_mapping[internal_id] = uid

        new_internal_ids = [
            iid for iid in unique_internal_ids if iid not in user_id_mapping
        ]
        if new_internal_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT nextval('global_user_id_seq') "
                    "FROM generate_series(1, %s)",
                    [len(new_internal_ids)],
                )
                for internal_id, (new_id,) in zip(
                    new_internal_ids, cursor.fetchall()
                ):
                    user_id_mapping[internal_id] = new_id

        # Allocate globally-unique order_ids
        unique_internal_order_ids = (
            customers_df[["internal_order_id"]]
            .drop_duplicates()["internal_order_id"]
            .tolist()
        )
        order_id_mapping: dict = {}

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT internal_order_id, order_id
                FROM users_unnormalized_data
                WHERE tenant_id = %s
                  AND internal_order_id = ANY(%s)
                """,
                [tenant.id, unique_internal_order_ids],
            )
            for internal_order_id, oid in cursor.fetchall():
                order_id_mapping[internal_order_id] = oid

        new_internal_order_ids = [
            iid for iid in unique_internal_order_ids if iid not in order_id_mapping
        ]
        if new_internal_order_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT nextval('global_order_id_seq') "
                    "FROM generate_series(1, %s)",
                    [len(new_internal_order_ids)],
                )
                for internal_order_id, (new_id,) in zip(
                    new_internal_order_ids, cursor.fetchall()
                ):
                    order_id_mapping[internal_order_id] = new_id

        staging_objects = []
        for _, row in customers_df.iterrows():
            internal_id         = str(row.get("internal_id", ""))
            internal_order_id   = str(row.get("internal_order_id", ""))
            internal_product_id = str(row.get("internal_product_id", ""))

            if not internal_id or not internal_order_id or not internal_product_id:
                continue

            try:
                then_price = (
                    float(row["then_product_price"])
                    if pd.notna(row.get("then_product_price"))
                    else 0.0
                )
            except (ValueError, TypeError):
                then_price = 0.0

            try:
                qty = (
                    int(row["quantity"])
                    if pd.notna(row.get("quantity"))
                    else 0
                )
            except (ValueError, TypeError):
                qty = 0

            staging_objects.append(
                UsersUnNormalizedDataStaging(
                    tenant=tenant,
                    internal_user_id=internal_id,
                    user_id=user_id_mapping[internal_id],
                    first_name=str(row.get("first_name", ""))[:200],
                    last_name=str(row.get("last_name", "")) or None,
                    gender=str(row.get("gender", "")) or None,
                    phone_number=(
                        str(row["phone_number"])[:20]
                        if pd.notna(row.get("phone_number"))
                        else None
                    ),
                    internal_order_id=internal_order_id,
                    order_id=order_id_mapping[internal_order_id],
                    order_date=(
                        row["order_date"]
                        if pd.notna(row.get("order_date"))
                        else None
                    ),
                    internal_product_id=internal_product_id,
                    product_id=None,
                    then_product_price=then_price,
                    quantity=qty,
                    subtotal=None,
                    column_mapping={
                        "customers_file_mapping":  actual_mapping,
                        "customers_index_mapping": customers_mapping,
                        "uploaded_at":             str(customer_upload.created_at),
                    },
                )
            )

        if not staging_objects:
            messages.warning(
                request, "هیچ رکورد معتبری در فایل مشتریان یافت نشد."
            )
            return

        try:
            UsersUnNormalizedDataStaging.objects.bulk_create(
                staging_objects, batch_size=1000
            )
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '600000';")
                cursor.execute(
                    "SELECT flush_customers_staging(%s)", [tenant.id]
                )
                rows_moved = cursor.fetchone()[0] or 0

            messages.success(
                request,
                f"{rows_moved} رکورد مشتریان با موفقیت در دیتابیس ذخیره شد.",
            )
        except Exception as e:
            messages.error(
                request, f"خطای غیرمنتظره در ذخیره‌سازی مشتریان: {str(e)}"
            )

    # ── Products pipeline
    # hair_tag / skin_tag replaced with
    # first_product_attribute / second_product_attribute.
    # Empty cells stored as NULL — no normalisation.
    # ─────────────────────────────────────────────────────────────────────────

    def _process_products(self, request, tenant, product_form, mapping_form):
        products_mapping = mapping_form.get_products_mapping()

        is_valid, error_msg = ProductExcelMapper.validate_mapping_integrity(
            products_mapping
        )
        if not is_valid:
            messages.error(
                request, f"خطا در نگاشت ستون‌های فایل محصولات: {error_msg}"
            )
            return

        with transaction.atomic():
            product_upload = product_form.save(commit=False)
            product_upload.tenant = tenant
            product_upload.products_mapping = products_mapping
            product_upload.save()

        try:
            products_df, actual_mapping = ProductExcelMapper.validate_and_map_file(
                product_upload.products_file.path, products_mapping
            )
        except ValueError as e:
            messages.error(request, f"خطا در پردازش فایل محصولات: {str(e)}")
            return
        except Exception as e:
            messages.error(
                request, f"خطای غیرمنتظره در فایل محصولات: {str(e)}"
            )
            return

        products_df["internal_product_id"] = (
            products_df["internal_product_id"].astype(str)
        )

        # Allocate globally-unique product_ids
        unique_internal_product_ids = (
            products_df[["internal_product_id"]]
            .drop_duplicates()["internal_product_id"]
            .tolist()
        )
        product_id_mapping: dict = {}

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT internal_product_id, product_id
                FROM products_unnormalized_data
                WHERE tenant_id = %s
                  AND internal_product_id = ANY(%s)
                """,
                [tenant.id, unique_internal_product_ids],
            )
            for internal_product_id, pid in cursor.fetchall():
                product_id_mapping[internal_product_id] = pid

        new_internal_product_ids = [
            iid
            for iid in unique_internal_product_ids
            if iid not in product_id_mapping
        ]
        if new_internal_product_ids:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT nextval('global_product_id_seq') "
                    "FROM generate_series(1, %s)",
                    [len(new_internal_product_ids)],
                )
                for internal_product_id, (new_id,) in zip(
                    new_internal_product_ids, cursor.fetchall()
                ):
                    product_id_mapping[internal_product_id] = new_id

        def _attr_value(row, field_name):
            """
            Returns the raw string value from the row, or None if the cell
            was empty / NaN.  No normalisation is applied.
            """
            val = row.get(field_name)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            val = str(val).strip()
            return val if val else None

        staging_objects = []
        for _, row in products_df.iterrows():
            internal_product_id = str(row.get("internal_product_id", ""))
            if not internal_product_id:
                continue

            try:
                price = (
                    float(row["current_product_price"])
                    if pd.notna(row.get("current_product_price"))
                    else 0.0
                )
            except (ValueError, TypeError):
                price = 0.0

            staging_objects.append(
                ProductsUnNormalizedDataStaging(
                    tenant=tenant,
                    internal_product_id=internal_product_id,
                    product_id=product_id_mapping[internal_product_id],
                    product_name=str(row.get("product_name", ""))[:255],
                    product_category=str(row.get("category", ""))[:100],
                    current_product_price=price,
                    product_link=(
                        str(row["product_link"])[:2000]
                        if pd.notna(row.get("product_link"))
                        else ""
                    ),
                    # Raw values — NULL if empty, no normalisation
                    first_product_attribute=_attr_value(row, "first_product_attribute"),
                    second_product_attribute=_attr_value(row, "second_product_attribute"),
                    column_mapping={
                        "products_file_mapping":  actual_mapping,
                        "products_index_mapping": products_mapping,
                        "uploaded_at":            str(product_upload.created_at),
                    },
                )
            )

        if not staging_objects:
            messages.warning(
                request, "هیچ رکورد معتبری در فایل محصولات یافت نشد."
            )
            return

        try:
            ProductsUnNormalizedDataStaging.objects.bulk_create(
                staging_objects, batch_size=1000
            )
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '600000';")
                cursor.execute(
                    "SELECT flush_products_staging(%s)", [tenant.id]
                )
                rows_moved = cursor.fetchone()[0] or 0

            messages.success(
                request,
                f"{rows_moved} رکورد محصولات با موفقیت در دیتابیس ذخیره شد.",
            )
        except Exception as e:
            messages.error(
                request, f"خطای غیرمنتظره در ذخیره‌سازی محصولات: {str(e)}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
#
# Unchanged SSR placeholder. Will be replaced by the real
# GET /api/v1/dashboard/ DRF endpoint in Phase 7.
# ─────────────────────────────────────────────────────────────────────────────

def DashBoardView(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return render(request, "campaigns/dashboard.html", {})
