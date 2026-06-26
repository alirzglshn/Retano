# tickets/tests.py

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

CHAT_URL = "/api/v1/tickets/chat/"
UNREAD_URL = "/api/v1/tickets/unread/"


class ChatAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_get_returns_401(self):
        self.assertEqual(self.client.get(CHAT_URL).status_code, 401)

    def test_unauthenticated_post_returns_401(self):
        self.assertEqual(self.client.post(CHAT_URL, {}).status_code, 401)


class ChatTenantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="pass"
        )
        self.client.force_authenticate(user=self.user)

    def test_get_chat_returns_200_and_empty_messages(self):
        response = self.client.get(CHAT_URL)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("messages", data)
        self.assertIsInstance(data["messages"], list)

    def test_send_message_returns_201(self):
        response = self.client.post(CHAT_URL, {"body": "سلام"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["sender_type"], "tenant")

    def test_empty_body_returns_400(self):
        response = self.client.post(CHAT_URL, {"body": ""}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_sent_message_appears_in_get(self):
        self.client.post(CHAT_URL, {"body": "پیام اول"}, format="json")
        messages = self.client.get(CHAT_URL).json()["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["body"], "پیام اول")


class UnreadCountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121111111", password="pass"
        )
        self.client.force_authenticate(user=self.user)

    def test_unread_count_zero_for_new_tenant(self):
        response = self.client.get(UNREAD_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread_count"], 0)

    def test_get_chat_does_not_increase_unread(self):
        self.client.get(CHAT_URL)
        self.assertEqual(self.client.get(UNREAD_URL).json()["unread_count"], 0)