# core/views_dashboard.py

from datetime import date

import jdatetime
from django.core.cache import cache
from django.db import connection
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Campaign
from core.utils.jalali import gregorian_to_jalali_year, jalali_year_to_gregorian_range

# Cache TTL — 60 seconds as specified in the roadmap.
DASHBOARD_CACHE_TTL = 60


def _current_jalali_month_gregorian_range() -> tuple[date, date]:
    """
    Returns (start, end) Gregorian dates for the current Jalali calendar month.
    end is exclusive (first day of next Jalali month).
    """
    today_j = jdatetime.date.today()
    start_j = jdatetime.date(today_j.year, today_j.month, 1)
    if today_j.month == 12:
        end_j = jdatetime.date(today_j.year + 1, 1, 1)
    else:
        end_j = jdatetime.date(today_j.year, today_j.month + 1, 1)
    return start_j.togregorian(), end_j.togregorian()


def _last_6_jalali_months() -> list[tuple[int, int, date, date]]:
    """
    Returns the last 6 Jalali months (including current) as a list of
    (jalali_year, jalali_month, greg_start, greg_end) tuples, oldest first.
    """
    today_j = jdatetime.date.today()
    months = []
    year, month = today_j.year, today_j.month
    for _ in range(6):
        start_j = jdatetime.date(year, month, 1)
        if month == 12:
            end_j = jdatetime.date(year + 1, 1, 1)
        else:
            end_j = jdatetime.date(year, month + 1, 1)
        months.append((year, month, start_j.togregorian(), end_j.togregorian()))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    months.reverse()
    return months


class DashboardView(APIView):
    """
    GET /api/v1/dashboard/

    Returns all data needed to render the dashboard in one request.
    Response is cached per tenant for 60 seconds.

    Data sources:
        - Campaign model (Django ORM) — campaign counts
        - public.user_summary (Supabase raw SQL) — customer segments
        - public.orders + public.users (Supabase raw SQL) — monthly sales
        - public.order_items + public.orders + public.products (Supabase) — top products
        - public.retention_history + public.users (Supabase) — monthly churn/retention
        - CustomUser.num_available_sms (Django ORM) — SMS balance
        - Thread.unread_count() (Django ORM) — support badge
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        tenant = user.tenant
        tenant_id = tenant.id
        cache_key = f"dashboard:tenant:{tenant_id}"

        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        data = {}

        # ── 1. Campaign counts ────────────────────────────────────────────
        today = date.today()
        campaigns_qs = Campaign.objects.filter(tenant=tenant)

        active_campaigns = campaigns_qs.filter(
            is_active=True,
            campaign_end_date__gte=today,
        ).count()

        ended_campaigns = campaigns_qs.filter(
            campaign_end_date__lt=today,
        ).count()

        inactive_campaigns = campaigns_qs.filter(
            is_active=False,
        ).count()

        total_campaigns = campaigns_qs.count()

        data["campaigns"] = {
            "active": active_campaigns,
            "ended": ended_campaigns,
            "inactive": inactive_campaigns,
            "total": total_campaigns,
        }

        # ── 2. Customer segment counts ────────────────────────────────────
        # Source: public.user_summary joined to public.users for tenant scope.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE us.rfm_segment = 'active')
                        AS active_customers,
                    COUNT(*) FILTER (WHERE us.rfm_segment != 'active')
                        AS inactive_customers,
                    COUNT(*) FILTER (WHERE us.rfm_segment = 'churned')
                        AS churned_customers,
                    COUNT(*) AS total_customers
                FROM public.user_summary us
                JOIN public.users u ON us.user_id = u.user_id
                WHERE u.tenant_id = %s
                  AND us.rfm_segment IS NOT NULL
                """,
                [tenant_id],
            )
            row = cursor.fetchone()

        active_customers = int(row[0] or 0)
        inactive_customers = int(row[1] or 0)
        churned_customers = int(row[2] or 0)
        total_customers = int(row[3] or 0)

        churn_rate = (
            round(churned_customers / total_customers * 100, 1)
            if total_customers > 0
            else 0.0
        )
        retention_rate = round(100.0 - churn_rate, 1)

        data["customers"] = {
            "active": active_customers,
            "inactive": inactive_customers,
            "churned": churned_customers,
            "total": total_customers,
            "churn_rate_percent": churn_rate,
            "retention_rate_percent": retention_rate,
        }

        # ── 3. Monthly sales (فروش ماه) ───────────────────────────────────
        month_start, month_end = _current_jalali_month_gregorian_range()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(o.total_amount), 0)
                FROM public.orders o
                JOIN public.users u ON o.user_id = u.user_id
                WHERE u.tenant_id = %s
                  AND o.order_date >= %s
                  AND o.order_date < %s
                """,
                [tenant_id, month_start, month_end],
            )
            monthly_sales = float(cursor.fetchone()[0] or 0)

        data["monthly_sales"] = round(monthly_sales, 2)

        # ── 4. Top 4 products by revenue ──────────────────────────────────
        # order_items → orders → users for tenant scope.
        # Product name from public.products (Supabase authoritative side).
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.name                          AS product_name,
                    p.price                         AS product_price,
                    COALESCE(SUM(oi.subtotal), 0)   AS total_revenue
                FROM public.order_items oi
                JOIN public.orders o  ON oi.order_id  = o.order_id
                JOIN public.users  u  ON o.user_id    = u.user_id
                JOIN public.products p ON oi.product_id = p.product_id
                WHERE u.tenant_id = %s
                GROUP BY p.product_id, p.name, p.price
                ORDER BY total_revenue DESC
                LIMIT 4
                """,
                [tenant_id],
            )
            rows = cursor.fetchall()

        data["top_products"] = [
            {
                "name": row[0],
                "price": float(row[1]) if row[1] is not None else 0.0,
                "total_revenue": float(row[2]),
            }
            for row in rows
        ]

        # ── 5. Monthly retention & churn rate (6 months) ─────────────────
        # For each Jalali month we need:
        #   total_users  = users in user_summary for this tenant at that time
        #                  (approximated as current total — acceptable for
        #                   a dashboard; a full time-series would require
        #                   snapshotting user_summary monthly)
        #   churned_that_month = users whose churned_at in retention_history
        #                        falls within that month's Gregorian range.
        #
        # Current-month uses live rfm_segment data.
        # Past months use retention_history.churned_at as the churn signal.

        months = _last_6_jalali_months()

        # Fetch all retention_history rows for this tenant to avoid
        # N+1 queries (one query, aggregate in Python).
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT rh.churned_at
                FROM public.retention_history rh
                JOIN public.users u ON rh.user_id = u.user_id
                WHERE u.tenant_id = %s
                """,
                [tenant_id],
            )
            churn_dates = [row[0] for row in cursor.fetchall()]

        jalali_month_names = [
            "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
        ]

        monthly_trends = []
        for j_year, j_month, greg_start, greg_end in months:
            churned_this_month = sum(
                1 for d in churn_dates
                if greg_start <= d < greg_end
            )
            month_churned_rate = (
                round(churned_this_month / total_customers * 100, 1)
                if total_customers > 0
                else 0.0
            )
            month_retention_rate = round(100.0 - month_churned_rate, 1)

            monthly_trends.append({
                "jalali_year": j_year,
                "jalali_month": j_month,
                "month_name": jalali_month_names[j_month - 1],
                "retention_rate_percent": month_retention_rate,
                "churn_rate_percent": month_churned_rate,
            })

        data["monthly_trends"] = monthly_trends

        # ── 6. RFM segment distribution ───────────────────────────────────
        # Reuse same query result from step 2, add vip/new/at_risk.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    us.rfm_segment,
                    COUNT(*) AS count
                FROM public.user_summary us
                JOIN public.users u ON us.user_id = u.user_id
                WHERE u.tenant_id = %s
                  AND us.rfm_segment IS NOT NULL
                GROUP BY us.rfm_segment
                """,
                [tenant_id],
            )
            segment_rows = cursor.fetchall()

        segment_map = {row[0]: int(row[1]) for row in segment_rows}
        data["rfm_segments"] = {
            "vip": segment_map.get("vip", 0),
            "active": segment_map.get("active", 0),
            "new": segment_map.get("new", 0),
            "at_risk": segment_map.get("at_risk", 0),
            "churned": segment_map.get("churned", 0),
        }

        # ── 7. SMS balance ────────────────────────────────────────────────
        data["sms_balance"] = user.num_available_sms

        # ── 8. Support unread count (dashboard badge) ─────────────────────
        try:
            from tickets.models import Thread
            thread = tenant.thread
            unread = thread.unread_count()
        except Exception:
            unread = 0
        data["support_unread_count"] = unread

        # ── Cache and return ──────────────────────────────────────────────
        cache.set(cache_key, data, DASHBOARD_CACHE_TTL)
        return Response(data, status=status.HTTP_200_OK)