import pytest

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from consultations.admin import FreeConsultAdmin
from consultations.models import FreeConsult

pytestmark = pytest.mark.django_db


@pytest.fixture
def regular_user():
    return get_user_model().objects.create_user(
        phone_number="+989120000024",
        password="test-password",
    )


@pytest.fixture
def staff_user():
    return get_user_model().objects.create_user(
        phone_number="+989120000025",
        password="test-password",
        is_staff=True,
    )


@pytest.fixture
def superuser():
    return get_user_model().objects.create_superuser(
        phone_number="+989120000026",
        password="test-password",
    )


def test_free_consult_is_registered_in_admin():
    assert isinstance(admin.site._registry[FreeConsult], FreeConsultAdmin)


@pytest.mark.parametrize(
    "permission_method",
    [
        "has_module_permission",
        "has_view_permission",
        "has_add_permission",
        "has_change_permission",
        "has_delete_permission",
    ],
)
def test_admin_permissions_are_superuser_only(
    regular_user,
    staff_user,
    superuser,
    permission_method,
):
    model_admin = FreeConsultAdmin(FreeConsult, admin.site)
    request_factory = RequestFactory()

    for user in [regular_user, staff_user]:
        request = request_factory.get("/admin/consultations/freeconsult/")
        request.user = user
        assert not getattr(model_admin, permission_method)(request)

    request = request_factory.get("/admin/consultations/freeconsult/")
    request.user = superuser
    assert getattr(model_admin, permission_method)(request)
