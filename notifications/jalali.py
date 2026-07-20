# notifications/jalali.py
"""
Gregorian -> Jalali date formatting for API responses.

The model stores plain Gregorian DateTimeField (see notifications/
models.py for why), but the frontend needs Jalali strings to display
(matching the "1405/03/10" style already used across the UI). This is
computed on the way out, in the serializer, never stored.

Kept as a single small function so the conversion library is an
implementation detail — swapping jdatetime for something else later
only means changing this file.
"""

from __future__ import annotations

from datetime import datetime

import jdatetime
from django.utils import timezone


def to_jalali_string(dt: datetime, fmt: str = "%Y/%m/%d %H:%M") -> str:
    """
    Convert an aware (or naive) Gregorian datetime to a Jalali string.

    Converts to the current timezone first (Django stores UTC
    internally when USE_TZ=True), matching what an admin or tenant in
    Iran would expect to see, then maps onto the Jalali calendar.
    """
    local_dt = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    jalali_dt = jdatetime.datetime.fromgregorian(datetime=local_dt)
    return jalali_dt.strftime(fmt)
