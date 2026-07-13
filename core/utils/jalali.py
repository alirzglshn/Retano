# core/utils/jalali.py
"""
Minimal Jalali (Persian) calendar utilities for the reports/dashboard layer.

Using the `jdatetime` library which is already in requirements.txt.
No custom arithmetic — delegate everything to the library.

ADDITIONS (append these to the existing core/utils/jalali.py — the three
original functions gregorian_to_jalali_year, jalali_year_to_gregorian_range,
current_jalali_year are unchanged and kept as-is above this point).
"""

import jdatetime
from datetime import date


def gregorian_to_jalali_year(gregorian_date: date) -> int:
    """Return the Jalali year that contains the given Gregorian date."""
    return jdatetime.date.fromgregorian(date=gregorian_date).year


def jalali_year_to_gregorian_range(jalali_year: int) -> tuple[date, date]:
    """
    Return (start, end) Gregorian dates for a full Jalali year.

    start — first day of the Jalali year (Farvardin 1) in Gregorian.
    end   — first day of the *next* Jalali year in Gregorian.

    Use as:  order_date >= start AND order_date < end
    """
    start = jdatetime.date(jalali_year, 1, 1).togregorian()
    end = jdatetime.date(jalali_year + 1, 1, 1).togregorian()
    return start, end


def current_jalali_year() -> int:
    """Return today's Jalali year."""
    return jdatetime.date.today().year


# ─────────────────────────────────────────────────────────────────────────
# NEW: month-level range helper
# ─────────────────────────────────────────────────────────────────────────

def jalali_month_to_gregorian_range(
    jalali_year: int, jalali_month: int
) -> tuple[date, date]:
    """
    Return (start, end) Gregorian dates for a single Jalali month.

    start — first day of the Jalali month, in Gregorian.
    end   — first day of the *next* Jalali month, in Gregorian (exclusive).

    Use as:  order_date >= start AND order_date < end
    """
    start = jdatetime.date(jalali_year, jalali_month, 1).togregorian()
    if jalali_month == 12:
        end = jdatetime.date(jalali_year + 1, 1, 1).togregorian()
    else:
        end = jdatetime.date(jalali_year, jalali_month + 1, 1).togregorian()
    return start, end


# ─────────────────────────────────────────────────────────────────────────
# NEW: last-N-years / last-N-months enumerations
# ─────────────────────────────────────────────────────────────────────────

JALALI_MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def last_n_jalali_years(n: int = 4) -> list[int]:
    """
    Return the last `n` Jalali years ending at (and including) the
    current Jalali year, oldest first.

    e.g. if the current Jalali year is 1405 and n=4 -> [1402, 1403, 1404, 1405]
    """
    current = current_jalali_year()
    return list(range(current - n + 1, current + 1))


def last_n_jalali_months(n: int = 6) -> list[tuple[int, int, date, date]]:
    """
    Return the last `n` Jalali months (including the current month) as a
    list of (jalali_year, jalali_month, greg_start, greg_end) tuples,
    oldest first.
    """
    today_j = jdatetime.date.today()
    months = []
    year, month = today_j.year, today_j.month
    for _ in range(n):
        start, end = jalali_month_to_gregorian_range(year, month)
        months.append((year, month, start, end))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    months.reverse()
    return months
