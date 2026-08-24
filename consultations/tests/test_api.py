from uuid import uuid4

import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from consultations.models import FreeConsult

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def regular_user():
    return get_user_model().objects.create_user(
        phone_number="+989120000021",
        password="test-password",
    )


@pytest.fixture
def staff_user():
    return get_user_model().objects.create_user(
        phone_number="+989120000022",
        password="test-password",
        is_staff=True,
    )


@pytest.fixture
def superuser():
    return get_user_model().objects.create_superuser(
        phone_number="+989120000023",
        password="test-password",
    )


@pytest.mark.parametrize("phone_number", ["09123456789", "+989123456789"])
def test_create_is_public_and_preserves_phone_format(client, phone_number):
    response = client.post(
        reverse("consultations:free-consult-create"),
        {"phone_number": phone_number},
        format="json",
        HTTP_AUTHORIZATION="Bearer invalid-token",
        REMOTE_ADDR=f"valid-{phone_number}",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["phone_number"] == phone_number
    assert FreeConsult.objects.filter(phone_number=phone_number).exists()


@pytest.mark.parametrize(
    "phone_number",
    ["9123456789", "0912345678", "+98912345678", "0912345678a"],
)
def test_create_rejects_invalid_phone_numbers(client, phone_number):
    response = client.post(
        reverse("consultations:free-consult-create"),
        {"phone_number": phone_number},
        format="json",
        REMOTE_ADDR=f"invalid-{phone_number}",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_is_rate_limited(client):
    url = reverse("consultations:free-consult-create")
    request_data = {"phone_number": "09123456789"}
    remote_addr = f"rate-limit-{uuid4()}"

    for _ in range(5):
        response = client.post(
            url,
            request_data,
            format="json",
            REMOTE_ADDR=remote_addr,
        )
        assert response.status_code == status.HTTP_201_CREATED

    response = client.post(
        url,
        request_data,
        format="json",
        REMOTE_ADDR=remote_addr,
    )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.parametrize("url_name", ["free-consult-list", "free-consult-detail"])
def test_reads_require_authentication(client, url_name):
    response = client.get(reverse(f"consultations:{url_name}"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("user_fixture", ["regular_user", "staff_user"])
@pytest.mark.parametrize("url_name", ["free-consult-list", "free-consult-detail"])
def test_non_superusers_cannot_read(client, request, user_fixture, url_name):
    client.force_authenticate(request.getfixturevalue(user_fixture))

    response = client.get(reverse(f"consultations:{url_name}"))

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_superuser_can_list_all_requests(client, superuser):
    first = FreeConsult.objects.create(phone_number="09123456789")
    second = FreeConsult.objects.create(phone_number="+989123456789")
    client.force_authenticate(superuser)

    response = client.get(reverse("consultations:free-consult-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data == [
        {"id": first.id, "phone_number": first.phone_number},
        {"id": second.id, "phone_number": second.phone_number},
    ]


def test_superuser_can_get_request_by_id(client, superuser):
    consultation = FreeConsult.objects.create(phone_number="09123456789")
    client.force_authenticate(superuser)

    response = client.get(
        reverse("consultations:free-consult-detail"),
        {"id": consultation.id},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "id": consultation.id,
        "phone_number": consultation.phone_number,
    }


def test_detail_requires_id_parameter(client, superuser):
    client.force_authenticate(superuser)

    response = client.get(reverse("consultations:free-consult-detail"))

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_detail_returns_not_found_for_unknown_id(client, superuser):
    client.force_authenticate(superuser)

    response = client.get(
        reverse("consultations:free-consult-detail"),
        {"id": 999999},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
