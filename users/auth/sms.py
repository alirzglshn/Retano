# users/auth/sms.py
"""
SMS delivery backends for OTP codes.

``OTPService`` (see :mod:`users.auth.otp`) depends only on the
:class:`OTPSender` interface, not on Kavenegar directly. This keeps the
OTP flow testable: swap in :class:`FakeOTPSender` via
``settings.OTP_FAKE_MODE = True`` instead of hitting the real SMS API
in tests or local development without credentials.
"""

from __future__ import annotations

import abc
import logging

from django.conf import settings

logger = logging.getLogger("retano.auth.sms")


class OTPSender(abc.ABC):
    """Interface every OTP delivery backend must implement."""

    #: Whether this sender is a non-real backend (dev/test). ``OTPService``
    #: uses this to decide whether it's safe to echo the code back in the
    #: API response for debugging.
    is_fake: bool = False

    @abc.abstractmethod
    def send(self, *, phone_number: str, code: str) -> None:
        """Deliver ``code`` to ``phone_number``. Raise on failure."""
        raise NotImplementedError


class KavenegarOTPSender(OTPSender):
    """Sends OTP codes via the Kavenegar SMS API."""

    is_fake = False

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or getattr(settings, "KAVENEGAR_API_KEY", "")
        if not self._api_key:
            raise RuntimeError(
                "KAVENEGAR_API_KEY is not configured. Set it in the "
                "environment, or use OTP_FAKE_MODE for local development."
            )

    def send(self, *, phone_number: str, code: str) -> None:
        # Imported lazily so the `kavenegar` package is only required when
        # this backend is actually used (e.g. not in test runs that use
        # FakeOTPSender).
        from kavenegar import APIException, HTTPException, KavenegarAPI

        api = KavenegarAPI(self._api_key)
        message = f"کد تایید شما در رتانو: {code}"
        try:
            api.sms_send(
                {
                    "receptor": phone_number,
                    "message": message,
                }
            )
        except (APIException, HTTPException) as exc:
            logger.exception("Kavenegar send failed for %s", phone_number)
            raise RuntimeError(f"Kavenegar SMS send failed: {exc}") from exc


class FakeOTPSender(OTPSender):
    """
    No-op sender for local development and tests.

    Logs the code instead of sending an SMS. ``OTPService`` reads
    ``is_fake`` to decide whether to include the code in its response
    (``OTPIssueResult.debug_code``), which views must never expose
    outside of dev/test environments.
    """

    is_fake = True

    def send(self, *, phone_number: str, code: str) -> None:
        logger.info("[FAKE SMS] OTP for %s: %s", phone_number, code)


def get_default_sender() -> OTPSender:
    """Resolve the sender to use based on ``settings.OTP_FAKE_MODE``."""
    if getattr(settings, "OTP_FAKE_MODE", False):
        return FakeOTPSender()
    return KavenegarOTPSender()
