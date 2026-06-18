from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    UpdateView,
    DetailView,
    ListView,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Prefetch

from .models import Ticket, TicketMessage
from .forms import (
    TicketCreateForm,
    TicketReplyForm,
    TicketStatusUpdateForm,
)


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "tickets/tickets-list.html"
    context_object_name = "tickets"
    paginate_by = 20

    def get_queryset(self):
        return Ticket.objects.filter(
            user=self.request.user
        ).order_by("-created_at")


class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketCreateForm
    template_name = "tickets/ticket-create.html"
    success_url = reverse_lazy("ticket-list")

    def form_valid(self, form):
        ticket = form.save(commit=False)
        ticket.user = self.request.user
        ticket.save()

        # First message is usually created with the ticket
        initial_message = self.request.POST.get("message")
        if initial_message:
            TicketMessage.objects.create(
                ticket=ticket,
                user=self.request.user,
                message=initial_message,
            )

        return redirect("ticket-detail", pk=ticket.pk)


class TicketDetailView(LoginRequiredMixin, DetailView):
    model = Ticket
    template_name = "tickets/chat.html"
    context_object_name = "ticket"

    def get_object(self):
        return get_object_or_404(
            Ticket,
            pk=self.kwargs["pk"],
            user=self.request.user
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["messages"] = self.object.messages.select_related("user").order_by("created_at")

        context["reply_form"] = TicketReplyForm()
        context["status_form"] = TicketStatusUpdateForm(instance=self.object)

        return context

    def post(self, request, *args, **kwargs):
        """
        Handles ticket replies.
        """
        self.object = self.get_object()
        form = TicketReplyForm(request.POST, request.FILES)

        if form.is_valid():
            message = form.save(commit=False)
            message.ticket = self.object
            message.user = request.user
            message.is_staff_reply = request.user.is_staff
            message.save()


        return redirect("ticket-detail", pk=self.object.pk)


class TicketStatusUpdateView(LoginRequiredMixin, UpdateView):
    model = Ticket
    form_class = TicketStatusUpdateForm
    template_name = "tickets/ticket-status-update.html"

    def get_object(self):
        return get_object_or_404(
            Ticket,
            pk=self.kwargs["pk"],
            user=self.request.user
        )

    def get_success_url(self):
        return reverse_lazy("ticket-detail", kwargs={"pk": self.object.pk})


