# forms.py
from django import forms
from .models import Ticket, TicketMessage


class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["subject", "priority"]
        widgets = {
            "subject": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "عنوان تیکت را وارد کنید"
            }),
            "priority": forms.Select(attrs={
                "class": "form-control"
            }),
        }

    

class TicketReplyForm(forms.ModelForm):
    class Meta:
        model = TicketMessage
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Write your reply here..."
            }),
        }


class TicketStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["status"]
        widgets = {
            "status": forms.Select(attrs={"class": "form-control"}),
        }