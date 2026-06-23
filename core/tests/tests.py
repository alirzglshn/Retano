# core/tests.py
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from users.models import CustomUser

from ..models import Campaign, Tenant


def make_user_with_tenant(phone_number):
    user = CustomUser.objects.create_user(phone_number=phone_number)
    # Tenant is created via the post_save signal on CustomUser.
    return user, Tenant.objects.get(owner=user)


class CampaignListCreateTests(APITestCase):
    def setUp(self):
        self.user, self.tenant = make_user_with_tenant("+989121111111")
        self.client.force_authenticate(user=self.user)
        self.url = reverse("campaign-list")

    def test_list_empty_by_default(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_create_campaign_assigns_own_tenant(self):
        response = self.client.post(
            self.url, {"name": "Spring Sale", "is_active": True}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        campaign = Campaign.objects.get(id=response.data["id"])
        self.assertEqual(campaign.tenant_id, self.tenant.id)
        self.assertEqual(campaign.rule_number, 1)

    def test_create_ignores_client_supplied_tenant(self):
        other_user, other_tenant = make_user_with_tenant("+989122222222")

        response = self.client.post(
            self.url, {"name": "Hijack Attempt", "tenant": other_tenant.id}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        campaign = Campaign.objects.get(id=response.data["id"])
        self.assertEqual(campaign.tenant_id, self.tenant.id)

    def test_rule_number_increments_per_tenant(self):
        self.client.post(self.url, {"name": "First"})
        response = self.client.post(self.url, {"name": "Second"})

        self.assertEqual(response.data["rule_number"], 2)

    def test_create_rejects_end_date_before_start_date(self):
        response = self.client.post(
            self.url,
            {
                "name": "Bad Dates",
                "campaign_start_date": "2026-06-01",
                "campaign_end_date": "2026-05-01",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("campaign_end_date", response.data["details"])

    def test_list_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_uses_condensed_serializer(self):
        self.client.post(self.url, {"name": "Condensed Check"})

        response = self.client.get(self.url)
        result = response.data["results"][0]

        self.assertIn("name", result)
        self.assertIn("is_active", result)
        self.assertNotIn("message_pattern", result)
        self.assertNotIn("activation_base", result)


class CampaignDetailTests(APITestCase):
    def setUp(self):
        self.user, self.tenant = make_user_with_tenant("+989121111111")
        self.client.force_authenticate(user=self.user)
        self.campaign = Campaign.objects.create(tenant=self.tenant, name="Detail Me")
        self.url = reverse("campaign-detail", args=[self.campaign.id])

    def test_retrieve_own_campaign(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Detail Me")

    def test_patch_updates_fields(self):
        response = self.client.patch(self.url, {"name": "Renamed"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.name, "Renamed")

    def test_patch_cannot_move_campaign_to_another_tenant(self):
        _, other_tenant = make_user_with_tenant("+989122222222")

        response = self.client.patch(self.url, {"tenant": other_tenant.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.tenant_id, self.tenant.id)

    def test_delete_campaign(self):
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Campaign.objects.filter(id=self.campaign.id).exists())


class CampaignToggleTests(APITestCase):
    def setUp(self):
        self.user, self.tenant = make_user_with_tenant("+989121111111")
        self.client.force_authenticate(user=self.user)
        self.campaign = Campaign.objects.create(
            tenant=self.tenant, name="Toggle Me", is_active=True
        )
        self.url = reverse("campaign-toggle", args=[self.campaign.id])

    def test_toggle_with_no_body_flips_is_active(self):
        response = self.client.patch(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.campaign.refresh_from_db()
        self.assertFalse(self.campaign.is_active)

    def test_toggle_with_explicit_value_sets_is_active(self):
        response = self.client.patch(
            self.url, {"is_active": False}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.campaign.refresh_from_db()
        self.assertFalse(self.campaign.is_active)

    def test_toggle_twice_returns_to_original_state(self):
        self.client.patch(self.url, {}, format="json")
        self.client.patch(self.url, {}, format="json")

        self.campaign.refresh_from_db()
        self.assertTrue(self.campaign.is_active)


class CampaignFilterSearchOrderTests(APITestCase):
    def setUp(self):
        self.user, self.tenant = make_user_with_tenant("+989121111111")
        self.client.force_authenticate(user=self.user)
        self.url = reverse("campaign-list")

        Campaign.objects.create(tenant=self.tenant, name="Alpha Sale", is_active=True)
        Campaign.objects.create(
            tenant=self.tenant, name="Beta Promo", is_active=False
        )
        Campaign.objects.create(
            tenant=self.tenant, name="Gamma Sale", is_active=True
        )

    def test_filter_by_is_active(self):
        response = self.client.get(self.url, {"is_active": "true"})

        names = {item["name"] for item in response.data["results"]}
        self.assertEqual(names, {"Alpha Sale", "Gamma Sale"})

    def test_search_by_name(self):
        response = self.client.get(self.url, {"search": "Sale"})

        names = {item["name"] for item in response.data["results"]}
        self.assertEqual(names, {"Alpha Sale", "Gamma Sale"})

    def test_ordering_by_created_at_descending_by_default(self):
        response = self.client.get(self.url)

        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Gamma Sale", "Beta Promo", "Alpha Sale"])

    def test_ordering_by_name_ascending(self):
        response = self.client.get(self.url, {"ordering": "name"})

        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Alpha Sale", "Beta Promo", "Gamma Sale"])

    def test_list_is_paginated(self):
        response = self.client.get(self.url)

        for key in ("count", "next", "previous", "total_pages", "current_page", "results"):
            self.assertIn(key, response.data)


class CampaignMetaTests(APITestCase):
    def setUp(self):
        user, _ = make_user_with_tenant("+989121111111")
        self.client.force_authenticate(user=user)
        self.url = reverse("campaign-meta")

    def test_meta_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_meta_returns_all_expected_choice_fields(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field in (
            "activation_base",
            "comparison_type",
            "value_unit",
            "gender",
            "buying_power",
            "priority",
            "product_source",
            "customer_type",
            "coupon_discount_percentage",
        ):
            self.assertIn(field, response.data)
            self.assertGreater(len(response.data[field]), 0)
            self.assertIn("value", response.data[field][0])
            self.assertIn("label", response.data[field][0])

    def test_meta_gender_choices_match_model(self):
        response = self.client.get(self.url)

        values = {item["value"] for item in response.data["gender"]}
        self.assertEqual(values, {"آقایان", "بانوان", "همه"})


class CampaignTenantIsolationTests(APITestCase):
    """
    Spec requirement: user A cannot see, modify, or otherwise discover
    the existence of user B's campaigns.
    """

    def setUp(self):
        self.user_a, self.tenant_a = make_user_with_tenant("+989121111111")
        self.user_b, self.tenant_b = make_user_with_tenant("+989122222222")

        self.campaign_a = Campaign.objects.create(
            tenant=self.tenant_a, name="Tenant A Campaign"
        )
        self.campaign_b = Campaign.objects.create(
            tenant=self.tenant_b, name="Tenant B Campaign"
        )

    def test_list_only_shows_own_tenants_campaigns(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(reverse("campaign-list"))

        names = {item["name"] for item in response.data["results"]}
        self.assertEqual(names, {"Tenant A Campaign"})

    def test_cannot_retrieve_other_tenants_campaign(self):
        self.client.force_authenticate(user=self.user_a)
        url = reverse("campaign-detail", args=[self.campaign_b.id])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_update_other_tenants_campaign(self):
        self.client.force_authenticate(user=self.user_a)
        url = reverse("campaign-detail", args=[self.campaign_b.id])

        response = self.client.patch(url, {"name": "Hijacked"})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.campaign_b.refresh_from_db()
        self.assertEqual(self.campaign_b.name, "Tenant B Campaign")

    def test_cannot_delete_other_tenants_campaign(self):
        self.client.force_authenticate(user=self.user_a)
        url = reverse("campaign-detail", args=[self.campaign_b.id])

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Campaign.objects.filter(id=self.campaign_b.id).exists())

    def test_cannot_toggle_other_tenants_campaign(self):
        self.client.force_authenticate(user=self.user_a)
        url = reverse("campaign-toggle", args=[self.campaign_b.id])

        response = self.client.patch(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_search_does_not_leak_other_tenants_campaigns(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(reverse("campaign-list"), {"search": "Tenant B"})

        self.assertEqual(response.data["count"], 0)
