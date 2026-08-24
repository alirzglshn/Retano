import pytest

from users.serializers import OTPVerifySerializer


def test_otp_verify_accepts_exactly_four_digits():
    serializer = OTPVerifySerializer(
        data={"phone_number": "+989120000017", "code": "0123"}
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["code"] == "0123"


@pytest.mark.parametrize(
    "code",
    ["123", "12345", "12a4", " 1234 ", "", "\u06f1\u06f2\u06f3\u06f4"],
)
def test_otp_verify_rejects_codes_that_are_not_four_ascii_digits(code):
    serializer = OTPVerifySerializer(
        data={"phone_number": "+989120000018", "code": code}
    )

    assert not serializer.is_valid()
    assert "code" in serializer.errors
