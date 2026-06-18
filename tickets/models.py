# models.py
from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


# class TicketCategory(models.Model):
#     name = models.CharField(max_length=100)
#     description = models.TextField(blank=True)

#     def str(self):
#         return self.name


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tickets")
    subject = models.CharField(max_length=255)
    
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.MEDIUM
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def str(self):
        return f"#{self.id} - {self.subject}"


class TicketMessage(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="messages"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_staff_reply = models.BooleanField(default=False)

    def str(self):
        return f"Message by {self.user} on Ticket #{self.ticket.id}"


# class TicketAttachment(models.Model):
#     message = models.ForeignKey(
#         TicketMessage, on_delete=models.CASCADE, related_name="attachments"
#     )
#     file = models.FileField(upload_to="ticket_attachments/")
#     uploaded_at = models.DateTimeField(auto_now_add=True)