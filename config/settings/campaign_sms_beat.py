# config/settings/campaign_sms_beat.py
"""
Celery beat schedule + settings additions for the Campaign Detail phase's
SMS send/delivery pipeline (core/tasks/campaign_sms.py).

This is a STANDALONE settings module, not a patch to
config/settings/base.py. See the precise integration instructions
provided separately for the one import line to add to base.py — nothing
in this file should be hand-merged into base.py; it's designed to be
imported wholesale instead, so re-running this phase's setup never
requires re-diffing base.py by hand.

Everything here is additive: it does not redefine CELERY_BEAT_SCHEDULE
from scratch (which would silently drop any schedule entries a future
phase adds elsewhere) — instead it updates whatever CELERY_BEAT_SCHEDULE
dict already exists in the importing module's namespace. See the
integration instructions for exactly how that import must be ordered.
"""

from celery.schedules import crontab

# ─────────────────────────────────────────────────────────────────────────────
# sms.ir campaign-send credentials
#
# SMSIR_API_KEY is already defined in base.py for OTP (users/auth/sms.py) —
# this module does NOT redefine it; core/services/sms_campaign_client.py
# reads the same settings.SMSIR_API_KEY.
#
# SMSIR_CAMPAIGN_LINE_NUMBER is NEW — set this to the line number shown in
# your sms.ir dashboard for plain (non-template) sends. Get it from:
#   https://app.sms.ir  ->  خطوط اختصاصی (line numbers) section
# or programmatically, once, via:
#   from core.services.sms_campaign_client import SmsCampaignClient
#   SmsCampaignClient().get_line_numbers()
# ─────────────────────────────────────────────────────────────────────────────

import os

SMSIR_CAMPAIGN_LINE_NUMBER = os.environ.get("SMSIR_CAMPAIGN_LINE_NUMBER", "")


# ─────────────────────────────────────────────────────────────────────────────
# Celery beat schedule additions
# ─────────────────────────────────────────────────────────────────────────────

CAMPAIGN_SMS_BEAT_SCHEDULE = {
    "send-due-campaign-sms": {
        "task": "core.tasks.campaign_sms.send_due_campaign_sms",
        # Every 2 minutes. Chosen as a balance between send latency (a
        # campaign becoming due shouldn't sit unsent for long) and not
        # hammering sms.ir / the DB with a query every few seconds.
        # Tune based on real campaign volume once observed in production.
        "schedule": crontab(minute="*/2"),
    },
    "check-campaign-sms-delivery": {
        "task": "core.tasks.campaign_sms.check_campaign_sms_delivery",
        # Every 5 minutes. Delivery confirmations from sms.ir aren't
        # instant, so checking more often than this has limited value and
        # just adds API load.
        "schedule": crontab(minute="*/5"),
    },
}
