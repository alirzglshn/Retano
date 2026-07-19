# core/services/sms_campaign_client.py
"""
sms.ir client for CAMPAIGN sends — distinct from users/auth/sms.py, which
only ever sends OTP codes via sms.ir's template-based Verify API
(send_verify_code). Campaign messages are freeform, personalized-per-user
Persian text (trigger_results.final_message), which is a different sms.ir
endpoint family entirely:

    send_like_to_like(numbers, messages, linenumber, send_date_time)
        -> submits N different messages to N different numbers in one
           call, pair-to-pair by list index. This is the correct primitive
           for campaign sends because every trigger_results row has its
           own final_message (name, recommended product, coupon code all
           already substituted in) — send_bulk_sms would only send ONE
           identical message to many numbers, which is not what we need.

    report_message(message_id)
        -> delivery status lookup for a previously sent message. Used by
           the delivery-check Celery task to distinguish "submitted"
           (sent_at) from "actually delivered" (delivered_at).

Uses the same underlying HTTP API as users/auth/sms.py's
SMSIROTPSender (sms.ir REST API), but talks to the messaging endpoints
instead of the verify endpoint. Kept as a separate module rather than
extending SMSIROTPSender because the two have different auth scopes in
sms.ir's dashboard (a "line number" for plain sends vs. a template id for
OTP) and mixing them would make SMSIROTPSender's single responsibility
(OTP only) less obvious.

Credentials needed (add to settings / environment):
    SMSIR_API_KEY        — same sms.ir account API key already used for OTP
                            (SMSIR_API_KEY is already configured per
                            users/auth/sms.py; reused here, not duplicated)
    SMSIR_CAMPAIGN_LINE_NUMBER — the "line number" shown in the sms.ir
                            dashboard's line-numbers list, for plain
                            (non-template) sends. This is DIFFERENT from
                            SMSIR_OTP_TEMPLATE_ID. Retrieve it via the
                            sms.ir panel, or programmatically via
                            SmsCampaignClient.get_line_numbers().

sms.ir's official REST endpoints (per their documentation) are used
directly via `requests`, mirroring the existing SMSIROTPSender's style
in users/auth/sms.py, rather than adding a new third-party SDK dependency
(the smsir-python package on PyPI wraps the same endpoints, but pulling
in a new dependency for four HTTP calls isn't worth it here — this file
is intentionally dependency-light, matching the rest of the sms
integration in this codebase).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

logger = logging.getLogger("retano.campaign_sms")


class CampaignSmsError(Exception):
    """Raised on any non-recoverable failure talking to sms.ir for campaign sends."""


@dataclass
class SendLikeToLikeResult:
    """
    One entry per (number, message) pair that was submitted.
    message_id is what report_message() later needs to check delivery.
    """
    number: str
    message_id: Optional[str]
    succeeded: bool
    raw: dict


@dataclass
class DeliveryReport:
    message_id: str
    delivered: bool
    raw: dict


class SmsCampaignClient:
    """
    Thin wrapper around sms.ir's messaging endpoints for campaign sends.
    Framework-agnostic like SMSIROTPSender — Celery tasks call this
    directly, no Django-specific coupling beyond reading settings.
    """

    _BASE_URL = "https://api.sms.ir/v1"
    _SEND_LIKE_TO_LIKE_URL = f"{_BASE_URL}/send/likeToLike"
    _REPORT_URL = f"{_BASE_URL}/send"  # /{message_id}/report, per sms.ir docs

    def __init__(
        self,
        api_key: Optional[str] = None,
        line_number: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or getattr(settings, "SMSIR_API_KEY", "")
        self._line_number = line_number or getattr(
            settings, "SMSIR_CAMPAIGN_LINE_NUMBER", ""
        )
        if not self._api_key:
            raise RuntimeError(
                "SMSIR_API_KEY is not configured. Campaign sends require the "
                "same sms.ir API key already used for OTP."
            )
        if not self._line_number:
            raise RuntimeError(
                "SMSIR_CAMPAIGN_LINE_NUMBER is not configured. Look this up "
                "in the sms.ir dashboard's line-numbers page, or call "
                "SmsCampaignClient.get_line_numbers() once to list what's "
                "available on this account."
            )

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "x-api-key": self._api_key,
        }

    # ── Send ─────────────────────────────────────────────────────────────

    def send_like_to_like(
        self,
        numbers: list[str],
        messages: list[str],
        send_date_time: Optional[str] = None,
    ) -> list[SendLikeToLikeResult]:
        """
        Submits len(numbers) messages, pair-to-pair with `messages` by
        index. numbers and messages must be the same length.

        send_date_time: optional ISO-ish timestamp string for scheduled
        sends. Left None for immediate sending — the Celery beat task
        already only picks up rows that are due *now*, so scheduling at
        the sms.ir level would be redundant; kept as a parameter for
        completeness / future use.

        Raises CampaignSmsError on request-level failure. Per-recipient
        failures (e.g. an invalid number) are reported in the returned
        list's `succeeded` flag rather than raising, since one bad number
        in a batch of hundreds shouldn't fail the whole batch.
        """
        import requests

        if len(numbers) != len(messages):
            raise CampaignSmsError(
                f"numbers ({len(numbers)}) and messages ({len(messages)}) "
                "must be the same length for send_like_to_like."
            )
        if not numbers:
            return []

        payload = {
            "lineNumber": self._line_number,
            "messages": [
                {"mobile": number, "text": message}
                for number, message in zip(numbers, messages)
            ],
        }
        if send_date_time:
            payload["sendDateTime"] = send_date_time

        try:
            response = requests.post(
                self._SEND_LIKE_TO_LIKE_URL,
                json=payload,
                headers=self._headers(),
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.exception("sms.ir send_like_to_like request failed")
            raise CampaignSmsError(f"sms.ir send_like_to_like failed: {exc}") from exc

        data = response.json()
        if data.get("status") != 1:
            logger.error("sms.ir rejected send_like_to_like batch: %s", data)
            raise CampaignSmsError(
                f"sms.ir send_like_to_like rejected: {data.get('message')}"
            )

        results = []
        entries = (data.get("data") or {}).get("messageIds") or []
        # sms.ir returns per-recipient message ids in the same order the
        # recipients were submitted in. If the response shape doesn't
        # include a per-recipient id for some reason, fall back to marking
        # that entry as not-succeeded rather than guessing.
        for i, number in enumerate(numbers):
            entry = entries[i] if i < len(entries) else None
            if entry is None:
                results.append(
                    SendLikeToLikeResult(
                        number=number, message_id=None, succeeded=False, raw=data
                    )
                )
                continue
            message_id = entry.get("messageId") if isinstance(entry, dict) else entry
            results.append(
                SendLikeToLikeResult(
                    number=number,
                    message_id=str(message_id) if message_id is not None else None,
                    succeeded=message_id is not None,
                    raw=entry if isinstance(entry, dict) else {"messageId": entry},
                )
            )
        return results

    # ── Delivery report ──────────────────────────────────────────────────

    def report_message(self, message_id: str) -> DeliveryReport:
        """
        Looks up delivery status for a previously submitted message.

        sms.ir's delivery status codes distinguish states like "sent",
        "delivered", "failed", "not delivered" etc. This wrapper collapses
        that to a boolean `delivered` — treat anything other than an
        explicit delivered confirmation as not-yet-delivered (including
        error/unknown states), since delivered_at should only ever be
        stamped on a positive confirmation, never inferred by absence of
        a negative one.
        """
        import requests

        try:
            response = requests.get(
                f"{self._REPORT_URL}/{message_id}/report",
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.exception("sms.ir report_message request failed for %s", message_id)
            raise CampaignSmsError(
                f"sms.ir report_message failed for {message_id}: {exc}"
            ) from exc

        data = response.json()
        if data.get("status") != 1:
            # Not necessarily an error — sms.ir returns non-1 status for
            # "not found yet" on very recently submitted messages too.
            # Treat as not-delivered rather than raising.
            return DeliveryReport(message_id=message_id, delivered=False, raw=data)

        delivery_state = (data.get("data") or {}).get("deliveryState")
        delivered = delivery_state in ("Delivered", "delivered", 1)
        return DeliveryReport(message_id=message_id, delivered=delivered, raw=data)

    # ── Introspection helpers ────────────────────────────────────────────

    def get_line_numbers(self) -> list[dict]:
        """
        Lists the line numbers available on this sms.ir account. Useful
        once, manually, to find the value for SMSIR_CAMPAIGN_LINE_NUMBER —
        not called by any automated task.
        """
        import requests

        try:
            response = requests.get(
                f"{self._BASE_URL}/line-numbers",
                headers=self._headers(),
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise CampaignSmsError(f"sms.ir get_line_numbers failed: {exc}") from exc

        data = response.json()
        return data.get("data") or []


def get_default_campaign_client() -> SmsCampaignClient:
    """Resolve a client from settings, matching the pattern in users/auth/sms.py."""
    return SmsCampaignClient()
