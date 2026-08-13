from decimal import Decimal

import pytest

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from billing.admin import BillAdmin
from billing.models import BILLING_ID_LENGTH, Bill, BillingConstant

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(
        phone_number="+989120000001",
        username="billing-user",
    )


@pytest.fixture
def other_user():
    return get_user_model().objects.create_user(
        phone_number="+989120000002",
        username="other-billing-user",
    )


@pytest.fixture
def client(user):
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client


@pytest.mark.parametrize(
    (
        "sms_count",
        "discount_percentage",
        "actual_price",
        "discount_amount",
        "final_price",
    ),
    [
        (1_000, "0.00", "400000", "0", "400000"),
        (5_000, "5.00", "2000000", "100000", "1900000"),
        (25_000, "10.00", "10000000", "1000000", "9000000"),
        (60_000, "15.00", "24000000", "3600000", "20400000"),
        (150_000, "20.00", "60000000", "12000000", "48000000"),
        (300_000, "30.00", "120000000", "36000000", "84000000"),
        (500_000, "40.00", "200000000", "80000000", "120000000"),
    ],
)
def test_pricing(
    user,
    sms_count,
    discount_percentage,
    actual_price,
    discount_amount,
    final_price,
):
    bill = Bill.objects.create(tenant=user.tenant, sms_count=sms_count)

    assert bill.sms_unit_price == Decimal("400")
    assert bill.discount_percentage == Decimal(discount_percentage)
    assert bill.actual_price == Decimal(actual_price)
    assert bill.discount_amount == Decimal(discount_amount)
    assert bill.final_price == Decimal(final_price)


def test_billing_id_is_public_random_identifier(user):
    bill = Bill.objects.create(tenant=user.tenant, sms_count=1_000)

    assert len(bill.billing_id) == BILLING_ID_LENGTH
    assert bill.billing_id.isalnum()
    assert any(character.isalpha() for character in bill.billing_id)
    assert any(character.isdigit() for character in bill.billing_id)


def test_create_derives_protected_fields(client, user):
    response = client.post(reverse("bill-list"), {"sms_count": 5_000})

    assert response.status_code == status.HTTP_201_CREATED
    bill = Bill.objects.get(tenant=user.tenant)
    assert bill.status == Bill.Status.PENDING
    assert bill.card_number == "5029081043096987"
    assert bill.bale_id == "@Retano_Admin"
    assert "id" not in response.data


def test_create_rejects_protected_fields(client):
    response = client.post(
        reverse("bill-list"),
        {
            "sms_count": 1_000,
            "status": Bill.Status.PAID,
            "actual_price": "1",
            "card_number": "0000000000000000",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Bill.objects.count() == 0


def test_only_one_pending_bill_per_tenant(client):
    first_response = client.post(reverse("bill-list"), {"sms_count": 1_000})
    second_response = client.post(reverse("bill-list"), {"sms_count": 5_000})

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_409_CONFLICT
    assert Bill.objects.count() == 1


def test_new_bill_allowed_after_previous_bill_is_paid(client, user):
    bill = Bill.objects.create(tenant=user.tenant, sms_count=1_000)
    bill.status = Bill.Status.PAID
    bill.save(update_fields={"status"})

    response = client.post(reverse("bill-list"), {"sms_count": 5_000})

    assert response.status_code == status.HTTP_201_CREATED
    assert Bill.objects.filter(tenant=user.tenant).count() == 2


def test_list_is_tenant_isolated(client, user, other_user):
    own_bill = Bill.objects.create(tenant=user.tenant, sms_count=1_000)
    Bill.objects.create(tenant=other_user.tenant, sms_count=5_000)

    response = client.get(reverse("bill-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["billing_id"] == own_bill.billing_id


def test_retrieve_is_tenant_isolated(client, other_user):
    other_bill = Bill.objects.create(
        tenant=other_user.tenant,
        sms_count=1_000,
    )

    response = client.get(reverse("bill-detail", args=[other_bill.billing_id]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_patch_updates_only_sms_count_and_recalculates(client, user):
    bill = Bill.objects.create(tenant=user.tenant, sms_count=1_000)

    response = client.patch(
        reverse("bill-detail", args=[bill.billing_id]),
        {"sms_count": 25_000},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    bill.refresh_from_db()
    assert bill.sms_count == 25_000
    assert bill.discount_percentage == Decimal("10.00")
    assert bill.final_price == Decimal("9000000")


def test_put_rejects_fields_other_than_sms_count(client, user):
    bill = Bill.objects.create(tenant=user.tenant, sms_count=1_000)

    response = client.put(
        reverse("bill-detail", args=[bill.billing_id]),
        {"sms_count": 5_000, "status": Bill.Status.PAID},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    bill.refresh_from_db()
    assert bill.sms_count == 1_000
    assert bill.status == Bill.Status.PENDING


def test_paid_bill_cannot_be_updated(client, user):
    bill = Bill.objects.create(tenant=user.tenant, sms_count=1_000)
    bill.status = Bill.Status.PAID
    bill.save(update_fields={"status"})

    response = client.patch(
        reverse("bill-detail", args=[bill.billing_id]),
        {"sms_count": 5_000},
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_paid_bill_cannot_return_to_pending(user):
    bill = Bill.objects.create(tenant=user.tenant, sms_count=1_000)
    bill.status = Bill.Status.PAID
    bill.save(update_fields={"status"})
    bill.status = Bill.Status.PENDING

    with pytest.raises(ValidationError):
        bill.save(update_fields={"status"})


def test_pending_bill_can_be_deleted(client, user):
    bill = Bill.objects.create(tenant=user.tenant, sms_count=1_000)

    response = client.delete(reverse("bill-detail", args=[bill.billing_id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Bill.objects.filter(pk=bill.pk).exists()


def test_paid_bill_cannot_be_deleted(client, user):
    bill = Bill.objects.create(tenant=user.tenant, sms_count=1_000)
    bill.status = Bill.Status.PAID
    bill.save(update_fields={"status"})

    response = client.delete(reverse("bill-detail", args=[bill.billing_id]))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert Bill.objects.filter(pk=bill.pk).exists()


def test_unauthenticated_requests_are_rejected():
    response = APIClient().get(reverse("bill-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_billing_constants_are_public():
    response = APIClient().get(reverse("billing-constants"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "sms_unit_price": "400",
        "packages": [
            {"sms_count": 1_000, "discount_percentage": "0.00"},
            {"sms_count": 5_000, "discount_percentage": "5.00"},
            {"sms_count": 25_000, "discount_percentage": "10.00"},
            {"sms_count": 60_000, "discount_percentage": "15.00"},
            {"sms_count": 150_000, "discount_percentage": "20.00"},
            {"sms_count": 300_000, "discount_percentage": "30.00"},
            {"sms_count": 500_000, "discount_percentage": "40.00"},
        ],
        "privileges": "this is retano 360",
    }


def test_constants_update_pending_bills_and_leave_paid_bills_unchanged(
    user,
    other_user,
):
    pending_bill = Bill.objects.create(tenant=user.tenant, sms_count=5_000)
    paid_bill = Bill.objects.create(tenant=other_user.tenant, sms_count=5_000)
    paid_bill.status = Bill.Status.PAID
    paid_bill.save(update_fields={"status"})
    paid_snapshot = (
        paid_bill.sms_unit_price,
        paid_bill.discount_percentage,
        paid_bill.actual_price,
        paid_bill.discount_amount,
        paid_bill.final_price,
    )

    constants = BillingConstant.get_solo()
    constants.sms_unit_price = Decimal("500")
    constants.discount_percentage_5000 = Decimal("25.00")
    constants.privileges = "Updated privileges"
    constants.save()

    pending_bill.refresh_from_db()
    paid_bill.refresh_from_db()
    assert pending_bill.sms_unit_price == Decimal("500")
    assert pending_bill.discount_percentage == Decimal("25.00")
    assert pending_bill.actual_price == Decimal("2500000")
    assert pending_bill.discount_amount == Decimal("625000")
    assert pending_bill.final_price == Decimal("1875000")
    assert (
        paid_bill.sms_unit_price,
        paid_bill.discount_percentage,
        paid_bill.actual_price,
        paid_bill.discount_amount,
        paid_bill.final_price,
    ) == paid_snapshot


def test_only_one_billing_constants_row_is_allowed():
    BillingConstant.get_solo()

    with pytest.raises(ValidationError):
        BillingConstant.objects.create()


def test_protected_admin_fields_are_read_only_for_staff(user):
    user.is_staff = True
    request = RequestFactory().get("/admin/billing/bill/")
    request.user = user
    model_admin = BillAdmin(Bill, admin.site)

    readonly_fields = model_admin.get_readonly_fields(request)

    assert "card_number" in readonly_fields
    assert "bale_id" in readonly_fields


def test_protected_admin_fields_are_editable_for_superusers(user):
    user.is_staff = True
    user.is_superuser = True
    request = RequestFactory().get("/admin/billing/bill/")
    request.user = user
    model_admin = BillAdmin(Bill, admin.site)

    readonly_fields = model_admin.get_readonly_fields(request)

    assert "card_number" not in readonly_fields
    assert "bale_id" not in readonly_fields
