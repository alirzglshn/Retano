# core/views_reports.py

from django.db import connection
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import date
from core.utils.jalali import (
    gregorian_to_jalali_year,
    jalali_year_to_gregorian_range,
    current_jalali_year,
)

# ─────────────────────────────────────────────────────────────────────────────
# Segment label mapping
#
# the_users_summary_rfm_segmented uses English keys.
# The API response exposes Persian labels to match Campaign.CUSTOMER_TYPE_CHOICES
# and the frontend's expected values exactly.
# ─────────────────────────────────────────────────────────────────────────────

SEGMENT_LABEL_MAP: dict[str, str] = {
    "new": "تازه وارد",
    "active": "فعال",
    "vip": "ویژه",
    "at_risk": "در خطر ریزش",
    "churned": "از دست رفته",
}

# Canonical display order — stable shape for the frontend regardless of
# which segments actually have users. The frontend always receives all 5.
SEGMENT_ORDER = ["vip", "active", "new", "at_risk", "churned"]


class SegmentsReportView(APIView):
    """
    GET /api/v1/reports/segments/

    Returns the RFM segment distribution for the authenticated tenant.
    Includes per-segment user counts, percentages, and aggregated
    monetary / frequency / recency stats.

    Data source:
        public.the_users_summary_rfm_segmented (Postgres view)
        joined to public.users for tenant scoping.

    No Django ORM model — raw SQL only. The heavy computation (IQR bounds,
    percentile calibration, scoring) is already done in Postgres.
    This endpoint is a thin COUNT + AVG + SUM on top of that view.

    Response shape:
        {
            "total_users": 842,
            "segments": [
                {
                    "segment":        "vip",
                    "label":          "ویژه",
                    "count":          73,
                    "percentage":     8.67,
                    "total_monetary": 182400000.00,
                    "avg_monetary":   2498630.14,
                    "avg_frequency":  11.2,
                    "avg_recency_days": 18.4
                },
                ... (always 5 entries, zero-filled for empty segments)
            ]
        }
    """

    permission_classes = [permissions.IsAuthenticated]

    # Kept as a class constant so it is easy to read in tests and easy
    # to spot in a code review. The %s placeholder is psycopg2/psycopg3
    # parameterised — never string-formatted.
    _QUERY = """
        SELECT
            rfm.user_segment,
            COUNT(*)                                AS count,
            COALESCE(SUM(rfm.monetary),     0)      AS total_monetary,
            COALESCE(AVG(rfm.monetary),     0)      AS avg_monetary,
            COALESCE(AVG(rfm.frequency),    0)      AS avg_frequency,
            COALESCE(AVG(rfm.recency_days), 0)      AS avg_recency_days
        FROM public.the_users_summary_rfm_segmented rfm
        JOIN public.users u ON rfm.user_id = u.user_id
        WHERE u.tenant_id = %s
        GROUP BY rfm.user_segment
    """

    def get(self, request):
        try:
            tenant_id = request.user.tenant.id
        except AttributeError:
            # The post_save signal creates a Tenant on every CustomUser
            # creation, so this path should never be hit in production.
            # Guard exists for superusers created directly via manage.py
            # createsuperuser without the signal firing.
            return Response(
                {"detail": "Tenant record not found for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with connection.cursor() as cursor:
            cursor.execute(self._QUERY, [tenant_id])
            rows = cursor.fetchall()
            col_names = [col[0] for col in cursor.description]

        # Index rows by segment name for O(1) lookup during ordering.
        by_segment: dict[str, dict] = {}
        total_users = 0

        for row in rows:
            data = dict(zip(col_names, row))
            seg = data["user_segment"]
            count = int(data["count"])
            total_users += count
            by_segment[seg] = {
                "segment": seg,
                "label": SEGMENT_LABEL_MAP.get(seg, seg),
                "count": count,
                "total_monetary": round(float(data["total_monetary"]), 2),
                "avg_monetary": round(float(data["avg_monetary"]), 2),
                "avg_frequency": round(float(data["avg_frequency"]), 2),
                "avg_recency_days": round(float(data["avg_recency_days"]), 1),
            }

        # Build the final list in canonical order.
        # Segments with no users for this tenant are zero-filled so the
        # frontend always receives a stable 5-entry array — no conditional
        # rendering needed on the client side.
        segments = []
        for seg_key in SEGMENT_ORDER:
            if seg_key in by_segment:
                entry = by_segment[seg_key]
            else:
                entry = {
                    "segment": seg_key,
                    "label": SEGMENT_LABEL_MAP[seg_key],
                    "count": 0,
                    "total_monetary": 0.0,
                    "avg_monetary": 0.0,
                    "avg_frequency": 0.0,
                    "avg_recency_days": 0.0,
                }

            entry["percentage"] = (
                round(entry["count"] / total_users * 100, 2)
                if total_users > 0
                else 0.0
            )
            segments.append(entry)

        return Response(
            {"total_users": total_users, "segments": segments},
            status=status.HTTP_200_OK,
        )
    




class TrendsReportView(APIView):
    """
    GET /api/v1/reports/trends/
    GET /api/v1/reports/trends/?year=1403

    Returns annual trend data for three metrics shown in the Reports screen:
        - تعداد مشتریان  (customer count)
        - میزان فروش     (revenue / sales volume)
        - CLV            (revenue ÷ distinct customers for that year)

    Granularity: one data point per Persian (Jalali) calendar year.
    Default:     all years present in the tenant's orders data.
    Filter:      ?year=1403 returns only that single year's data point.
                 Frontend uses this when a year is selected in the سال dropdown.

    Data source:
        public.orders (Supabase) joined to public.users for tenant scoping.
        Revenue = SUM(orders.total_amount) per year.
        Customer count = COUNT(DISTINCT orders.user_id) per year.
        CLV = revenue / customer_count (0.0 if no customers).

    Year extraction:
        Done in Python after fetching raw rows, using jdatetime for
        correctness. Postgres EXTRACT tricks for Persian years are
        imprecise around Nowruz. We fetch all rows with their
        order_date and aggregate in Python.

    Response shape:
        {
            "years": [
                {
                    "jalali_year":      1401,
                    "customer_count":   312,
                    "revenue":          4820000000.00,
                    "clv":              15448717.95
                },
                ...
            ]
        }
    """

    permission_classes = [permissions.IsAuthenticated]

    # Fetch order_date + aggregates from Postgres.
    # We pull one row per order (not per year) because year bucketing
    # is done in Python via jdatetime for calendar correctness.
    # For realistic dataset sizes this is fine — orders are one row
    # per transaction. If this becomes a performance concern at very
    # large scale, a Postgres function wrapping jdatetime logic can
    # replace this query.
    _QUERY = """
        SELECT
            o.order_date,
            o.user_id,
            o.total_amount
        FROM public.orders o
        JOIN public.users u ON o.user_id = u.user_id
        WHERE u.tenant_id = %s
          AND o.order_date IS NOT NULL
          AND o.total_amount IS NOT NULL
    """

    _QUERY_FILTERED = """
        SELECT
            o.order_date,
            o.user_id,
            o.total_amount
        FROM public.orders o
        JOIN public.users u ON o.user_id = u.user_id
        WHERE u.tenant_id = %s
          AND o.order_date IS NOT NULL
          AND o.total_amount IS NOT NULL
          AND o.order_date >= %s
          AND o.order_date < %s
    """

    def get(self, request):
        try:
            tenant_id = request.user.tenant.id
        except AttributeError:
            return Response(
                {"detail": "Tenant record not found for this user."},
                status=status.HTTP_403_FORBIDDEN,
            )

        year_param = request.query_params.get("year")
        jalali_year_filter: int | None = None

        if year_param is not None:
            try:
                jalali_year_filter = int(year_param)
            except ValueError:
                return Response(
                    {"detail": "year must be an integer, e.g. ?year=1403"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Sanity range — Jalali years in realistic data range
            if not (1370 <= jalali_year_filter <= 1500):
                return Response(
                    {"detail": "year out of accepted range (1370–1500)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with connection.cursor() as cursor:
            if jalali_year_filter is not None:
                greg_start, greg_end = jalali_year_to_gregorian_range(
                    jalali_year_filter
                )
                cursor.execute(
                    self._QUERY_FILTERED,
                    [tenant_id, greg_start, greg_end],
                )
            else:
                cursor.execute(self._QUERY, [tenant_id])

            rows = cursor.fetchall()

        # ── Aggregate by Jalali year in Python ───────────────────────────
        # Structure: {jalali_year: {"revenue": Decimal, "users": set()}}
        yearly: dict[int, dict] = {}

        for order_date, user_id, total_amount in rows:
            # order_date arrives as datetime.date from psycopg
            if isinstance(order_date, str):
                order_date = date.fromisoformat(order_date)

            jyear = gregorian_to_jalali_year(order_date)

            if jyear not in yearly:
                yearly[jyear] = {"revenue": 0.0, "users": set()}

            yearly[jyear]["revenue"] += float(total_amount)
            yearly[jyear]["users"].add(user_id)

        # ── Build response sorted by Jalali year ascending ───────────────
        result = []
        for jyear in sorted(yearly.keys()):
            bucket = yearly[jyear]
            customer_count = len(bucket["users"])
            revenue = round(bucket["revenue"], 2)
            clv = round(revenue / customer_count, 2) if customer_count > 0 else 0.0

            result.append(
                {
                    "jalali_year": jyear,
                    "customer_count": customer_count,
                    "revenue": revenue,
                    "clv": clv,
                }
            )

        return Response({"years": result}, status=status.HTTP_200_OK)