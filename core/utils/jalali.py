# core/utils/jalali.py
"""
Minimal Jalali (Persian) calendar utilities for the reports layer.

Using the `jdatetime` library which is already in requirements.txt.
No custom arithmetic — delegate everything to the library.
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